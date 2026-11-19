"""
相关性分析模块
"""

import pandas as pd
import numpy as np
from scipy import stats


class CorrelationAnalyzer:
    """
    相关性分析器
    """
    
    def __init__(self, df, variable_types):
        self.df = df
        self.variable_types = variable_types
        self.numeric_cols = [col for col, t in variable_types.items()
                            if t in ['numeric_continuous', 'numeric_discrete']]
    
    def pearson(self, x, y):
        """
        Pearson相关系数
        """
        data = self.df[[x, y]].dropna()
        if len(data) < 3:
            return None
        
        r, p = stats.pearsonr(data[x], data[y])
        return {
            'coefficient': float(r),
            'p_value': float(p),
            'n': len(data)
        }
    
    def spearman(self, x, y):
        """
        Spearman秩相关系数
        """
        data = self.df[[x, y]].dropna()
        if len(data) < 3:
            return None
        
        r, p = stats.spearmanr(data[x], data[y])
        return {
            'coefficient': float(r),
            'p_value': float(p),
            'n': len(data)
        }
    
    def calculate_all(self, method='pearson'):
        """
        计算所有数值变量对之间的相关性
        
        Parameters:
        -----------
        method : str
            'pearson' 或 'spearman'
            
        Returns:
        --------
        dict
            包含相关系数矩阵和p值矩阵
        """
        if len(self.numeric_cols) < 2:
            return None
        
        corr_matrix = pd.DataFrame(index=self.numeric_cols, columns=self.numeric_cols)
        p_matrix = pd.DataFrame(index=self.numeric_cols, columns=self.numeric_cols)
        
        for i, x in enumerate(self.numeric_cols):
            for j, y in enumerate(self.numeric_cols):
                if i == j:
                    corr_matrix.loc[x, y] = 1.0
                    p_matrix.loc[x, y] = 1.0
                else:
                    if method == 'pearson':
                        result = self.pearson(x, y)
                    else:
                        result = self.spearman(x, y)
                    
                    if result:
                        corr_matrix.loc[x, y] = result['coefficient']
                        p_matrix.loc[x, y] = result['p_value']
        
        return {
            'correlation_matrix': corr_matrix.astype(float).to_dict(),
            'p_value_matrix': p_matrix.astype(float).to_dict(),
            'method': method,
            'variables': self.numeric_cols
        }
    
    def pairwise_analysis(self):
        """
        对每一对变量进行详细的相关性分析
        
        Returns:
        --------
        list
            每个变量对的分析结果
        """
        results = []
        
        for i in range(len(self.numeric_cols)):
            for j in range(i + 1, len(self.numeric_cols)):
                x, y = self.numeric_cols[i], self.numeric_cols[j]
                
                pearson_result = self.pearson(x, y)
                spearman_result = self.spearman(x, y)
                
                results.append({
                    'x': x,
                    'y': y,
                    'pearson': pearson_result,
                    'spearman': spearman_result
                })
        
        return results
