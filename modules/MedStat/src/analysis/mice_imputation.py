"""Continuous numeric iterative imputation and scalar Rubin pooling.

Missing categorical/count outcomes are rejected: encoding categories as numbers
and rounding a Gaussian regression is not a validated categorical MI model.
"""
import numpy as np
import pandas as pd
from scipy import stats
from sklearn.experimental import enable_iterative_imputer  # noqa: F401
from sklearn.impute import IterativeImputer
from sklearn.linear_model import BayesianRidge, LinearRegression, Ridge


class MICEImputer:
    def __init__(self, df, variable_types, n_imputations=5, max_iter=10,
                 strategy='bayesian_ridge'):
        if type(n_imputations) is not int or not 1 <= n_imputations <= 100:
            raise ValueError('插补次数必须为1至100的整数')
        if type(max_iter) is not int or not 1 <= max_iter <= 1000:
            raise ValueError('迭代次数必须为1至1000的整数')
        if strategy not in ('bayesian_ridge', 'linear', 'ridge'):
            raise ValueError('未知插补策略')
        if n_imputations > 1 and strategy != 'bayesian_ridge':
            raise ValueError('linear/ridge仅支持单次插补，不能提供多重插补间不确定性')
        self.df = df.copy()
        self.variable_types = variable_types or {}
        self.n_imputations = n_imputations
        self.max_iter = max_iter
        self.strategy = strategy
        self.imputed_datasets = None
        self.comparison_stats = {}

    def impute(self):
        if self.df.empty or self.df.columns.duplicated().any():
            raise ValueError('数据不能为空或有重复列名')
        if self.df.isna().all().any():
            raise ValueError('全缺失列不可估计，请补充数据或明确移除该变量')
        missing_cols = self.df.columns[self.df.isna().any()].tolist()
        if any(self.variable_types.get(c) != 'numeric_continuous' for c in missing_cols):
            raise ValueError('当前仅支持连续数值缺失插补；分类、离散或未定义类型需专用模型')
        numeric_cols = [c for c in self.df if self.variable_types.get(c) in
                        ('numeric_continuous', 'numeric_discrete')]
        if not missing_cols:
            self.imputed_datasets = [self.df.copy()]
            return self.imputed_datasets
        matrix = self.df[numeric_cols].apply(pd.to_numeric, errors='raise').to_numpy(dtype=float)
        if np.isinf(matrix).any():
            raise ValueError('插补数据不接受无穷值')
        if any(self.df[c].notna().sum() < 2 for c in missing_cols):
            raise ValueError('缺失变量至少需要两个已观测值')
        self.imputed_datasets = []
        for index in range(self.n_imputations):
            estimator = {'bayesian_ridge': BayesianRidge, 'linear': LinearRegression,
                         'ridge': Ridge}[self.strategy]()
            imputer = IterativeImputer(estimator=estimator, max_iter=self.max_iter,
                                      random_state=42 + index,
                                      sample_posterior=self.strategy == 'bayesian_ridge', tol=1e-3)
            values = imputer.fit_transform(matrix)
            if values.shape != matrix.shape or not np.isfinite(values).all():
                raise ValueError('插补未产生完整有限数值矩阵')
            result = self.df.copy()
            for position, col in enumerate(numeric_cols):
                mask = self.df[col].isna()
                if mask.any():
                    result[col] = result[col].astype(float)
                    result.loc[mask, col] = values[mask.to_numpy(), position]
            self.imputed_datasets.append(result)
        self.comparison_stats = self._compute_comparison(numeric_cols)
        return self.imputed_datasets

    def _compute_comparison(self, numeric_cols):
        def finite(value):
            return float(value) if np.isfinite(value) else None
        result = {}
        for col in numeric_cols:
            original = self.df[col]
            mask = original.isna()
            if not mask.any():
                continue
            values = [ds[col] for ds in self.imputed_datasets]
            # Dispersion of inserted values is descriptive, not an inferential SE.
            inserted = np.concatenate([v[mask].to_numpy() for v in values])
            result[col] = {
                'original_mean': finite(original.mean()),
                'original_std': finite(original.std(ddof=1)),
                'original_missing': int(mask.sum()),
                'imputed_mean': finite(np.mean([v.mean() for v in values])),
                'imputed_std': finite(np.mean([v.std(ddof=1) for v in values])),
                'imputed_values_mean': finite(inserted.mean()),
                'imputed_values_std': finite(inserted.std(ddof=1)) if len(inserted) > 1 else None,
            }
        return result

    def pool_results(self, analysis_func, *args, df_complete=None, **kwargs):
        """Pool scalar (estimate, variance) pairs; never silently omit failed fits.

        df_complete must be the complete-data analysis residual degrees of freedom
        when finite-sample CI is wanted. None explicitly assumes large-sample df.
        Formula specification: mice pool.scalar / Barnard-Rubin (1999).
        """
        if not self.imputed_datasets or len(self.imputed_datasets) < 2:
            raise ValueError('Rubin合并至少需要两个插补数据集；单次插补不提供MI推断')
        if df_complete is not None and (not np.isscalar(df_complete) or
                                       not np.isfinite(df_complete) or df_complete <= 0):
            raise ValueError('完整数据模型的残差自由度必须为正有限数；未知时传None并采用大样本假设')
        estimates, variances = [], []
        for index, dataset in enumerate(self.imputed_datasets):
            try:
                estimate, variance = analysis_func(dataset, *args, **kwargs)
                estimate, variance = float(estimate), float(variance)
                if not np.isfinite(estimate) or not np.isfinite(variance) or variance < 0:
                    raise ValueError('估计值和方差必须有限，方差非负')
            except Exception as error:
                raise ValueError(f'第{index + 1}份插补分析失败，未输出部分合并结果') from error
            estimates.append(estimate)
            variances.append(variance)
        m = len(estimates)
        q_bar, u_bar = float(np.mean(estimates)), float(np.mean(variances))
        b = float(np.var(estimates, ddof=1))
        total = u_bar + (1 + 1 / m) * b
        if u_bar <= 0 or total <= 0:
            raise ValueError('合并方差退化，不能提供有限样本置信区间')
        fraction = (1 + 1 / m) * b / total
        df_old = (m - 1) / fraction ** 2 if fraction > 0 else np.inf
        if df_complete is None:
            degrees = df_old
        else:
            df_observed = ((df_complete + 1) / (df_complete + 3)) * df_complete * (1 - fraction)
            degrees = 1 / (1 / df_old + 1 / df_observed)
        se = np.sqrt(total)
        critical = stats.norm.ppf(.975) if np.isinf(degrees) else stats.t.ppf(.975, degrees)
        riv = (1 + 1 / m) * b / u_bar
        fmi = (riv + (0 if np.isinf(degrees) else 2 / (degrees + 3))) / (riv + 1)
        return {
            'pooled_estimate': q_bar, 'pooled_standard_error': float(se),
            'ci_lower': float(q_bar - critical * se), 'ci_upper': float(q_bar + critical * se),
            'degrees_of_freedom': None if np.isinf(degrees) else float(degrees),
            'complete_data_df': None if df_complete is None else float(df_complete),
            'df_assumption': 'large_sample' if df_complete is None else 'supplied_complete_data_df',
            'within_variance': u_bar, 'between_variance': b, 'total_variance': total,
            'relative_increase_variance': riv, 'fraction_missing_information': float(fmi),
            'n_imputations_used': m, 'n_imputations_failed': 0,
        }

    def pooled_means(self):
        """Shared Web/CLI mean-pooling path: each U is sample variance / n."""
        if not self.imputed_datasets:
            raise ValueError('请先执行插补')
        if len(self.imputed_datasets) < 2:
            return []
        rows = []
        for column in self.comparison_stats:
            n = len(self.df)
            pooled = self.pool_results(lambda ds: (ds[column].mean(), ds[column].var(ddof=1) / n),
                                       df_complete=n - 1)
            rows.append({'variable': column, 'q_bar': pooled['pooled_estimate'],
                         'u_bar': pooled['within_variance'], 'b': pooled['between_variance'],
                         't': pooled['total_variance'], 'fmi': pooled['fraction_missing_information'],
                         'riv': pooled['relative_increase_variance'], **pooled})
        return rows

    def get_comparison(self):
        return self.comparison_stats
