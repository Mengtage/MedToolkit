"""
分组分析和统计检验模块
"""

import pandas as pd
import numpy as np
from scipy import stats
from .categorical_tests import CategoricalTestSelector


class GroupAnalyzer:
    """
    分组分析器
    """
    
    def __init__(self, df, variable_types, group_var):
        self.df = df
        self.variable_types = variable_types
        self.group_var = group_var
        self.groups = df[group_var].dropna().unique()
        self.n_groups = len(self.groups)
    
    def analyze_numeric(self, var):
        """
        分析数值型变量
        
        Returns:
        --------
        dict
            分析结果
        """
        results = {'variable': var, 'type': 'numeric', 'groups': {}}
        
        for g in self.groups:
            group_data = self.df[self.df[self.group_var] == g][var].dropna()
            results['groups'][str(g)] = {
                'n': len(group_data),
                'mean': float(group_data.mean()),
                'sd': float(group_data.std()),
                'median': float(group_data.median()),
                'min': float(group_data.min()),
                'max': float(group_data.max())
            }
        
        if self.n_groups == 2:
            g1_data = self.df[self.df[self.group_var] == self.groups[0]][var].dropna()
            g2_data = self.df[self.df[self.group_var] == self.groups[1]][var].dropna()
            
            stat_ttest, p_ttest = stats.ttest_ind(g1_data, g2_data, equal_var=False)
            stat_mwu, p_mwu = stats.mannwhitneyu(g1_data, g2_data)
            
            cohens_d = self._cohens_d(g1_data, g2_data)
            
            results['tests'] = {
                'welch_t_test': {
                    'statistic': float(stat_ttest),
                    'p_value': float(p_ttest)
                },
                'mann_whitney_u': {
                    'statistic': float(stat_mwu),
                    'p_value': float(p_mwu)
                },
                'cohens_d': float(cohens_d)
            }
        elif self.n_groups > 2:
            group_values = []
            for g in self.groups:
                vals = self.df[self.df[self.group_var] == g][var].dropna()
                if len(vals) >= 2:
                    group_values.append(vals)
            
            if len(group_values) >= 2:
                stat_anova, p_anova = stats.f_oneway(*group_values)
                stat_kruskal, p_kruskal = stats.kruskal(*group_values)
                
                results['tests'] = {
                    'anova': {
                        'statistic': float(stat_anova),
                        'p_value': float(p_anova)
                    },
                    'kruskal_wallis': {
                        'statistic': float(stat_kruskal),
                        'p_value': float(p_kruskal)
                    }
                }
        
        return results
    
    def analyze_categorical(self, var):
        """
        分析分类型变量
        
        Returns:
        --------
        dict
            分析结果
        """
        results = {'variable': var, 'type': 'categorical', 'groups': {}}
        
        crosstab = pd.crosstab(self.df[self.group_var], self.df[var]).reindex(self.groups, fill_value=0)
        valid_counts = crosstab.sum(axis=1)
        crosstab_pct = crosstab.div(valid_counts.replace(0, np.nan), axis=0) * 100
        results['missing'] = {str(g): int(self.df.loc[self.df[self.group_var] == g, var].isna().sum()) for g in self.groups}
        results['valid_counts'] = {str(g): int(valid_counts.loc[g]) for g in self.groups}
        results['percentage_denominator'] = 'nonmissing_within_group'
        
        for g in self.groups:
            g_str = str(g)
            results['groups'][g_str] = {}
            for level in crosstab.columns:
                results['groups'][g_str][str(level)] = {
                    'n': int(crosstab.loc[g, level]),
                    'percent': round(float(crosstab_pct.loc[g, level]), 1) if valid_counts.loc[g] else None
                }
        
        try:
            test_result = CategoricalTestSelector.select_test(crosstab.values)
            results['tests'] = {
                'selected_method': {
                    'method': test_result['method'],
                    'statistic': test_result['statistic'],
                    'statistic_name': test_result['statistic_name'],
                    'p_value': test_result['p_value'],
                    'reason': test_result['reason'],
                    'recommended': test_result['recommended']
                }
            }
            
            if 'or_ci' in test_result and test_result['or_ci'][0] is not None:
                results['tests']['selected_method']['or_ci'] = test_result['or_ci']
            
            results['contingency_table'] = crosstab.values.tolist()
            results['expected_table'] = test_result.get('expected', [])
            results['min_expected'] = test_result.get('min_expected', 0)
        except Exception as e:
            results['tests'] = {'error': str(e)}
        
        return results
    
    def analyze_all(self):
        """
        分析所有变量
        
        Returns:
        --------
        list
            所有变量的分析结果
        """
        results = []
        
        numeric_cols = [col for col, t in self.variable_types.items()
                       if t in ['numeric_continuous', 'numeric_discrete']
                       and col != self.group_var]
        
        for col in numeric_cols:
            results.append(self.analyze_numeric(col))
        
        categorical_cols = [col for col, t in self.variable_types.items()
                          if t in ['categorical', 'boolean']
                          and col != self.group_var]
        
        for col in categorical_cols:
            results.append(self.analyze_categorical(col))
        
        return results
    
    def _cohens_d(self, g1, g2):
        """
        计算Cohen's d效应量
        """
        n1, n2 = len(g1), len(g2)
        s1, s2 = g1.std(), g2.std()
        
        s_pooled = np.sqrt(((n1 - 1) * s1**2 + (n2 - 1) * s2**2) / (n1 + n2 - 2))
        d = (g1.mean() - g2.mean()) / s_pooled
        
        return d
