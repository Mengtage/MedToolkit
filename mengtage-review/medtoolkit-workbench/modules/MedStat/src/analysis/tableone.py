"""
TableOne 基线特征表模块
"""

import pandas as pd
import numpy as np
from scipy import stats


class TableOne:
    """
    基线特征表生成器
    """
    
    def __init__(self, df, variable_types, strata=None):
        """
        初始化TableOne
        
        Parameters:
        -----------
        df : pd.DataFrame
            输入数据
        variable_types : dict
            变量类型映射
        strata : str, optional
            分层变量名
        """
        self.df = df
        self.variable_types = variable_types
        self.strata = strata
        self.normality_results = {}
        self.table = None
        self.p_values = None
        
        self.numeric_vars = [col for col, t in self.variable_types.items()
                            if t in ['numeric_continuous', 'numeric_discrete']]
        self.categorical_vars = [col for col, t in self.variable_types.items()
                               if t in ['categorical', 'boolean']]
        
        if strata and strata in self.categorical_vars:
            self.categorical_vars.remove(strata)
    
    def generate(self):
        """
        生成基线特征表
        
        Returns:
        --------
        dict
            包含table和p值的完整结果
        """
        self._test_normality()
        
        results = []
        
        for var in self.numeric_vars:
            results.extend(self._process_numeric(var))
        
        for var in self.categorical_vars:
            results.extend(self._process_categorical(var))
        
        self.table = pd.DataFrame(results)
        self._calculate_pvalues()
        
        return {
            'table': self.table,
            'p_values': self.p_values,
            'normality': self.normality_results,
            'strata': self.strata
        }
    
    def _test_normality(self):
        """
        测试数值变量的正态性。检验失败时记录原因，不再静默吞掉。
        """
        for var in self.numeric_vars:
            vals = self.df[var].dropna()
            if len(vals) >= 3:
                if len(vals) <= 5000:
                    try:
                        stat, p = stats.shapiro(vals)
                        self.normality_results[var] = {
                            'test': 'Shapiro-Wilk',
                            'statistic': float(stat),
                            'p_value': float(p),
                            'is_normal': bool(p > 0.05)
                        }
                    except Exception as error:
                        self.normality_results[var] = self._normality_failure(
                            'Shapiro-Wilk', error)
                else:
                    try:
                        mu = float(vals.mean())
                        sigma = float(vals.std(ddof=1))
                        if not np.isfinite(sigma) or sigma <= 0:
                            raise ValueError('方差为0，正态性检验不可估计')
                        stat, p = stats.kstest(
                            vals.to_numpy(),
                            stats.norm(loc=mu, scale=sigma).cdf)
                        self.normality_results[var] = {
                            'test': 'Kolmogorov-Smirnov',
                            'statistic': float(stat),
                            'p_value': float(p),
                            'is_normal': bool(p > 0.05),
                            'note': '参数由样本估计，P值为近似值；建议同时参考Lilliefors检验'
                        }
                    except Exception as error:
                        self.normality_results[var] = self._normality_failure(
                            'Kolmogorov-Smirnov', error)

    @staticmethod
    def _normality_failure(test, error):
        """把正态性检验失败记录为结构化结果，供界面与审计追溯。"""
        return {
            'test': test,
            'error': f'{type(error).__name__}: {error}',
            'is_normal': False,
            'method_fallback': '正态性检验失败，组间比较回退为秩检验'
        }
    
    def _process_numeric(self, var):
        """
        处理数值变量
        """
        results = []
        
        if self.strata and self.strata in self.df.columns:
            grouped = self.df.groupby(self.strata)[var]
            for group_name, group_data in grouped:
                vals = group_data.dropna()
                if len(vals) > 0:
                    is_normal = self.normality_results.get(var, {}).get('is_normal', False)
                    
                    if is_normal:
                        display = f"{np.mean(vals):.2f} ({format(np.std(vals, ddof=1), '.2f') if len(vals)>1 else '不可估计'})"
                    else:
                        display = f"{np.median(vals):.2f} [{np.percentile(vals, 25):.2f}, {np.percentile(vals, 75):.2f}]"
                    
                    results.append({
                        'variable': var,
                        'group': str(group_name),
                        'type': 'numeric',
                        'n': len(vals),
                        'mean': float(np.mean(vals)),
                        'sd': float(np.std(vals, ddof=1)) if len(vals) > 1 else None,
                        'median': float(np.median(vals)),
                        'q25': float(np.percentile(vals, 25)),
                        'q75': float(np.percentile(vals, 75)),
                        'display': display
                    })
        else:
            vals = self.df[var].dropna()
            if len(vals) > 0:
                is_normal = self.normality_results.get(var, {}).get('is_normal', False)
                
                if is_normal:
                    display = f"{np.mean(vals):.2f} ({format(np.std(vals, ddof=1), '.2f') if len(vals)>1 else '不可估计'})"
                else:
                    display = f"{np.median(vals):.2f} [{np.percentile(vals, 25):.2f}, {np.percentile(vals, 75):.2f}]"
                
                results.append({
                    'variable': var,
                    'group': 'Overall',
                    'type': 'numeric',
                    'n': len(vals),
                    'mean': float(np.mean(vals)),
                    'sd': float(np.std(vals, ddof=1)) if len(vals) > 1 else None,
                    'median': float(np.median(vals)),
                    'q25': float(np.percentile(vals, 25)),
                    'q75': float(np.percentile(vals, 75)),
                    'display': display
                })
        
        return results
    
    def _process_categorical(self, var):
        """
        处理分类变量
        """
        results = []
        if self.strata and self.strata in self.df.columns:
            groups = [(str(g), self.df.loc[self.df[self.strata] == g, var])
                      for g in self.df[self.strata].dropna().unique()]
        else:
            groups = [('Overall', self.df[var])]
        levels = self.df[var].dropna().unique()
        for group_name, values in groups:
            valid = values.dropna()
            denominator = len(valid)
            missing = int(values.isna().sum())
            counts = valid.value_counts()
            for level in levels:
                n = int(counts.get(level, 0))
                pct = round(n / denominator * 100, 1) if denominator else None
                results.append({'variable': var, 'level': str(level), 'group': group_name,
                    'type': 'categorical', 'n': n, 'percent': pct,
                    'n_valid': denominator, 'n_missing': missing,
                    'percentage_denominator': 'nonmissing_within_group',
                    'display': f"{n} ({pct}%)" if pct is not None else '0 (不可估计)'})
        return results
    
    def _calculate_pvalues(self):
        """
        计算组间比较的P值
        """
        if not self.strata or self.strata not in self.df.columns:
            self.p_values = []
            return
        
        groups = self.df[self.strata].dropna().unique()
        n_groups = len(groups)
        p_results = []
        
        for var in self.numeric_vars:
            group_values = []
            for g in groups:
                vals = self.df[self.df[self.strata] == g][var].dropna()
                if len(vals) >= 2:
                    group_values.append(vals)
            
            if len(group_values) >= 2:
                is_normal = self.normality_results.get(var, {}).get('is_normal', False)
                
                if n_groups == 2:
                    if is_normal:
                        stat, p = stats.ttest_ind(group_values[0], group_values[1])
                        method = 'Independent t-test'
                    else:
                        stat, p = stats.mannwhitneyu(group_values[0], group_values[1])
                        method = 'Mann-Whitney U'
                else:
                    if is_normal:
                        stat, p = stats.f_oneway(*group_values)
                        method = 'One-way ANOVA'
                    else:
                        stat, p = stats.kruskal(*group_values)
                        method = 'Kruskal-Wallis'
                
                p_results.append({
                    'variable': var,
                    'type': 'numeric',
                    'test': method,
                    'statistic': float(stat),
                    'p_value': float(p)
                })
        
        for var in self.categorical_vars:
            contingency = pd.crosstab(self.df[self.strata], self.df[var])
            if contingency.size > 0:
                try:
                    min_expected = np.min(stats.chi2_contingency(contingency)[3])
                    
                    if min_expected < 5 and contingency.shape == (2, 2):
                        stat, p = stats.fisher_exact(contingency)
                        method = "Fisher's Exact"
                    else:
                        stat, p, _, _ = stats.chi2_contingency(contingency)
                        method = 'Chi-square'
                    
                    p_results.append({
                        'variable': var,
                        'type': 'categorical',
                        'test': method,
                        'statistic': float(stat),
                        'p_value': float(p)
                    })
                except Exception as error:
                    p_results.append({
                        'variable': var,
                        'type': 'categorical',
                        'test': 'not_estimable',
                        'statistic': None,
                        'p_value': None,
                        'error': f'{type(error).__name__}: {error}'
                    })
        
        self.p_values = p_results
