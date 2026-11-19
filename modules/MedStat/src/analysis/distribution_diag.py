"""
分布诊断和正态性检验模块
"""

import pandas as pd
import numpy as np
from scipy import stats


class DistributionDiagnostics:
    """
    分布诊断和正态性检验类
    """
    
    def __init__(self, df, variable_types):
        self.df = df
        self.variable_types = variable_types
    
    def test_normality(self, column):
        """
        检验单个变量的正态性
        
        Parameters:
        -----------
        column : str
            列名
            
        Returns:
        --------
        dict
            包含多种正态性检验的结果
        """
        data = self.df[column].dropna().astype(float)
        n = len(data)
        
        if n < 3:
            return {
                'column': column,
                'n': n,
                'error': '样本量不足，无法检验'
            }
        
        results = {'column': column, 'n': n}
        
        # Shapiro-Wilk 检验
        if n <= 5000:
            try:
                sw_stat, sw_p = stats.shapiro(data)
                results['shapiro_wilk'] = {
                    'statistic': float(sw_stat),
                    'p_value': float(sw_p),
                    'is_normal': sw_p > 0.05
                }
            except:
                results['shapiro_wilk'] = None
        
        # Kolmogorov-Smirnov 检验
        try:
            ks_stat, ks_p = stats.kstest(data, 'norm', args=(data.mean(), data.std()))
            results['kolmogorov_smirnov'] = {
                'statistic': float(ks_stat),
                'p_value': float(ks_p),
                'is_normal': ks_p > 0.05
            }
        except:
            results['kolmogorov_smirnov'] = None
        
        # D'Agostino-Pearson 检验
        if n >= 20:
            try:
                dp_stat, dp_p = stats.normaltest(data)
                results['dagostino_pearson'] = {
                    'statistic': float(dp_stat),
                    'p_value': float(dp_p),
                    'is_normal': dp_p > 0.05
                }
            except:
                results['dagostino_pearson'] = None
        
        # 统计描述
        results['stats'] = {
            'mean': float(data.mean()),
            'median': float(data.median()),
            'std': float(data.std()),
            'skewness': float(data.skew()),
            'kurtosis': float(data.kurtosis())
        }
        
        # 判断是否符合正态分布（综合判断）
        tests = []
        if 'shapiro_wilk' in results and results['shapiro_wilk']:
            tests.append(results['shapiro_wilk']['is_normal'])
        if 'kolmogorov_smirnov' in results and results['kolmogorov_smirnov']:
            tests.append(results['kolmogorov_smirnov']['is_normal'])
        if 'dagostino_pearson' in results and results['dagostino_pearson']:
            tests.append(results['dagostino_pearson']['is_normal'])
        
        if tests:
            results['is_normal_majority'] = sum(tests) / len(tests) > 0.5
        else:
            results['is_normal_majority'] = None
        
        return results

    def analyze_variable(self, column):
        """
        分析单个变量的分布和正态性（test_normality的别名）

        Parameters:
        -----------
        column : str
            列名

        Returns:
        --------
        dict
            包含检验结果
        """
        return self.test_normality(column)

    def analyze_all_numeric(self):
        """
        分析所有数值型变量的分布和正态性
        
        Returns:
        --------
        list
            所有数值型变量的检验结果
        """
        numeric_cols = [col for col, t in self.variable_types.items()
                       if t in ['numeric_continuous', 'numeric_discrete']]
        
        results = []
        for col in numeric_cols:
            result = self.test_normality(col)
            results.append(result)
        
        return results
    
    def get_summary(self):
        """
        获取简要摘要
        
        Returns:
        --------
        dict
            分布诊断摘要
        """
        numeric_cols = [col for col, t in self.variable_types.items()
                       if t in ['numeric_continuous', 'numeric_discrete']]
        
        normal_count = 0
        non_normal_count = 0
        inconclusive_count = 0
        
        for col in numeric_cols:
            test_result = self.test_normality(col)
            if test_result.get('is_normal_majority') is True:
                normal_count += 1
            elif test_result.get('is_normal_majority') is False:
                non_normal_count += 1
            else:
                inconclusive_count += 1
        
        return {
            'numeric_variables': len(numeric_cols),
            'normal_distribution': normal_count,
            'non_normal_distribution': non_normal_count,
            'inconclusive': inconclusive_count
        }
