"""
MICE多重插补模块
实现完整的多重插补和Rubin规则合并
"""

import pandas as pd
import numpy as np
from scipy import stats
from sklearn.experimental import enable_iterative_imputer
from sklearn.impute import IterativeImputer
from sklearn.linear_model import BayesianRidge, LinearRegression, Ridge
from sklearn.preprocessing import LabelEncoder
import warnings


class MICEImputer:
    """
    MICE多重插补器
    
    参考文献：
    - van Buuren, S. (2018). Flexible Imputation of Missing Data. 2nd Ed. CRC Press.
    - Rubin, D. B. (1987). Multiple Imputation for Nonresponse in Surveys.
    - White, I. R., et al. (2011). Multiple imputation using chained equations. Statistics in Medicine.
    """
    
    def __init__(self, df, variable_types, n_imputations=5, max_iter=10, 
                 strategy='bayesian_ridge'):
        """
        初始化MICE插补器
        
        Parameters:
        -----------
        df : pd.DataFrame
            原始数据
        variable_types : dict
            变量类型映射
        n_imputations : int
            插补数据集数量 (m)
        max_iter : int
            每个插补过程的最大迭代次数
        strategy : str
            回归策略 ('bayesian_ridge', 'linear', 'ridge')
        """
        self.df = df
        self.variable_types = variable_types if variable_types is not None else {}
        self.n_imputations = n_imputations
        self.max_iter = max_iter
        self.strategy = strategy
        self.imputed_datasets = None
        self.comparison_stats = None
    
    def impute(self):
        """
        执行多重插补
        
        Returns:
        --------
        list
            m个插补后的DataFrame
        """
        numeric_cols = [col for col, t in self.variable_types.items()
                       if t in ['numeric_continuous', 'numeric_discrete']]
        
        categorical_cols = [col for col, t in self.variable_types.items()
                          if t in ['categorical', 'boolean']]
        
        if self.df.isnull().sum().sum() == 0:
            self.imputed_datasets = [self.df.copy()]
            return self.imputed_datasets
        
        encoded_df = self.df.copy()
        label_encoders = {}
        
        for col in categorical_cols:
            le = LabelEncoder()
            temp_series = self.df[col].astype(str).fillna('__MISSING__')
            le.fit(temp_series)
            encoded_df[col + '_encoded'] = le.transform(temp_series).astype(float)
            missing_mask = self.df[col].isnull()
            encoded_df.loc[missing_mask, col + '_encoded'] = np.nan
            label_encoders[col] = le
        
        impute_features = []
        for col in numeric_cols:
            if col in encoded_df.columns:
                impute_features.append(col)
        
        for col in categorical_cols:
            if (col + '_encoded') in encoded_df.columns:
                impute_features.append(col + '_encoded')
        
        if not impute_features:
            self.imputed_datasets = [self.df.copy()]
            return self.imputed_datasets
        
        impute_matrix = encoded_df[impute_features].values.copy()
        
        estimator = self._get_estimator()
        
        imputed_datasets = []
        convergence_history = {}
        
        for m_idx in range(self.n_imputations):
            imputer = IterativeImputer(
                estimator=estimator,
                max_iter=self.max_iter,
                random_state=42 + m_idx,
                sample_posterior=(self.strategy == 'bayesian_ridge'),
                tol=1e-3
            )
            
            imputed_matrix = imputer.fit_transform(impute_matrix)
            
            if m_idx == 0:
                convergence_history['success'] = True
            
            result_df = self.df.copy()
            
            for i, col in enumerate(impute_features):
                if col in numeric_cols:
                    result_df[col] = imputed_matrix[:, i]
            
            for col in categorical_cols:
                encoded_col = col + '_encoded'
                if encoded_col in impute_features:
                    idx = impute_features.index(encoded_col)
                    imputed_codes = np.round(imputed_matrix[:, idx]).astype(int)
                    valid_classes = list(range(len(label_encoders[col].classes_)))
                    imputed_codes = np.clip(imputed_codes, min(valid_classes), max(valid_classes))
                    result_df[col] = label_encoders[col].inverse_transform(imputed_codes)
            
            imputed_datasets.append(result_df)
        
        self.imputed_datasets = imputed_datasets
        self.comparison_stats = self._compute_comparison(numeric_cols)
        
        return self.imputed_datasets
    
    def _get_estimator(self):
        """
        获取回归估计器
        """
        if self.strategy == 'bayesian_ridge':
            return BayesianRidge()
        elif self.strategy == 'linear':
            return LinearRegression()
        elif self.strategy == 'ridge':
            return Ridge(alpha=1.0)
        else:
            return BayesianRidge()
    
    def _compute_comparison(self, numeric_cols):
        """
        计算插补前后对比统计
        """
        comparison = {}
        
        for col in numeric_cols:
            original = self.df[col]
            imputed_values = [ds[col] for ds in self.imputed_datasets]
            
            if original.isnull().sum() == 0:
                continue
            
            comparison[col] = {
                'original_mean': round(float(original.mean()), 4),
                'original_std': round(float(original.std()), 4),
                'original_missing': int(original.isnull().sum()),
                'imputed_mean': round(float(np.mean([v.mean() for v in imputed_values])), 4),
                'imputed_std': round(float(np.mean([v.std() for v in imputed_values])), 4),
                'imputed_values_mean': round(float(np.mean([
                    v[original.isnull()].mean() for v in imputed_values
                ])), 4),
                'imputed_values_std': round(float(np.nanmean([
                    v[original.isnull()].std() for v in imputed_values
                ])), 4)
            }
        
        return comparison
    
    def pool_results(self, analysis_func, *args, **kwargs):
        """
        使用Rubin规则合并结果
        
        Parameters:
        -----------
        analysis_func : function
            对每个插补数据集进行分析的函数，返回 (estimate, variance)
        *args, **kwargs : 
            传递给analysis_func的参数
            
        Returns:
        --------
        dict
            合并后的估计结果
        """
        if not self.imputed_datasets:
            raise ValueError("请先执行插补")
        
        estimates = []
        variances = []
        
        for df in self.imputed_datasets:
            try:
                est, var = analysis_func(df, *args, **kwargs)
                estimates.append(est)
                variances.append(var)
            except:
                continue
        
        if not estimates:
            raise ValueError("所有数据集分析失败")
        
        m = len(estimates)
        Q_bar = np.mean(estimates)
        U_bar = np.mean(variances)
        
        B = np.var(estimates, ddof=1) if m > 1 else 0
        T = U_bar + (1 + 1/m) * B
        df_complete = len(self.df) - 1
        
        if B > 0 and m > 1:
            gamma = ((1 + 1/m) * B) / T
            df_old = (m - 1) / (gamma ** 2)
            lambda_ = df_complete / (df_complete + 3)
            df_adj = df_old * lambda_
        else:
            df_adj = df_complete
        
        se = np.sqrt(T)
        t_crit = stats.t.ppf(0.975, df_adj) if df_adj > 0 else 1.96
        ci_lower = Q_bar - t_crit * se
        ci_upper = Q_bar + t_crit * se
        
        return {
            'pooled_estimate': float(Q_bar),
            'pooled_standard_error': float(se),
            'ci_lower': float(ci_lower),
            'ci_upper': float(ci_upper),
            'degrees_of_freedom': float(df_adj) if df_adj > 0 else None,
            'within_variance': float(U_bar),
            'between_variance': float(B),
            'total_variance': float(T),
            'n_imputations_used': m
        }
    
    def get_comparison(self):
        """
        获取插补前后对比统计
        """
        return self.comparison_stats
