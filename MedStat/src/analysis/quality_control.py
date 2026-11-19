"""
数据质量控制模块
包含缺失值分析和异常值检测功能
"""

import pandas as pd
import numpy as np
from scipy import stats


class MissingDataAnalyzer:
    """
    缺失值分析器
    """
    
    def __init__(self, df):
        self.df = df
        self.missing_stats = None
    
    def analyze(self):
        """
        分析缺失值情况
        
        Returns:
        --------
        dict
            包含缺失值统计信息
        """
        results = []
        
        for col in self.df.columns:
            null_count = self.df[col].isnull().sum()
            
            other_missing_count = 0
            if self.df[col].dtype == 'object' or self.df[col].dtype.name == 'category':
                str_values = self.df[col].astype(str).str.strip()
                missing_placeholders = ['', ' ', 'na', 'n/a', 'n.a.', 'nan', 'none',
                                      'null', 'nil', '.', '-', '--', '---',
                                      '?', '??', '???', 'missing', 'unknown',
                                      '不适用', '缺失', '无', '空']
                for placeholder in missing_placeholders:
                    other_missing_count += (str_values.str.lower() == placeholder.lower()).sum()
            elif pd.api.types.is_numeric_dtype(self.df[col]):
                numeric_placeholders = [-999, -9999, -99999, 999, 9999]
                for placeholder in numeric_placeholders:
                    other_missing_count += (self.df[col] == placeholder).sum()
            
            total_missing = null_count + other_missing_count
            total = len(self.df[col])
            missing_percent = round(total_missing / total * 100, 2) if total > 0 else 0
            
            results.append({
                'variable': col,
                'missing_count': int(total_missing),
                'missing_percent': missing_percent,
                'total': int(total)
            })
        
        self.missing_stats = pd.DataFrame(results)
        return self.missing_stats.to_dict('records')
    
    def get_missing_matrix(self):
        """
        获取缺失值矩阵（用于可视化）
        """
        return self.df.isnull().astype(int)
    
    def has_missing_data(self):
        """
        检查是否存在缺失值
        """
        return self.df.isnull().sum().sum() > 0


class OutlierDetector:
    """
    异常值检测器
    """
    
    def __init__(self, df, variable_types):
        self.df = df
        self.variable_types = variable_types
        self.outlier_stats = None
    
    def _detect_zscore(self, col, threshold=3):
        """
        使用 Z-score 方法检测异常值
        """
        data = self.df[col].dropna().astype(float)
        if len(data) == 0:
            return [], []
        
        z_scores = np.abs((data - data.mean()) / data.std())
        outliers = data[z_scores > threshold]
        outlier_indices = outliers.index.tolist()
        return outlier_indices, outliers.tolist()
    
    def _detect_iqr(self, col):
        """
        使用 IQR 方法检测异常值
        """
        data = self.df[col].dropna().astype(float)
        if len(data) == 0:
            return [], []
        
        Q1 = data.quantile(0.25)
        Q3 = data.quantile(0.75)
        IQR = Q3 - Q1
        lower_bound = Q1 - 1.5 * IQR
        upper_bound = Q3 + 1.5 * IQR
        
        outliers = data[(data < lower_bound) | (data > upper_bound)]
        outlier_indices = outliers.index.tolist()
        return outlier_indices, outliers.tolist()
    
    def detect(self):
        """
        检测所有数值型变量的异常值
        
        Returns:
        --------
        list
            异常值统计信息列表
        """
        results = []
        
        numeric_cols = [col for col, t in self.variable_types.items()
                       if t in ['numeric_continuous', 'numeric_discrete']]
        
        for col in numeric_cols:
            zscore_indices, zscore_values = self._detect_zscore(col)
            iqr_indices, iqr_values = self._detect_iqr(col)
            
            total = len(self.df[col].dropna())
            
            zscore_count = len(zscore_indices)
            iqr_count = len(iqr_indices)
            
            zscore_percent = round(zscore_count / total * 100, 2) if total > 0 else 0
            iqr_percent = round(iqr_count / total * 100, 2) if total > 0 else 0
            
            results.append({
                'variable': col,
                'total': int(total),
                'zscore_outliers': int(zscore_count),
                'zscore_percent': zscore_percent,
                'zscore_values': zscore_values,
                'zscore_indices': zscore_indices,
                'iqr_outliers': int(iqr_count),
                'iqr_percent': iqr_percent,
                'iqr_values': iqr_values,
                'iqr_indices': iqr_indices
            })
        
        self.outlier_stats = pd.DataFrame(results)
        return results
    
    def get_outlier_details(self, col):
        """
        获取特定变量的异常值详情
        
        Returns:
        --------
        list
            包含行索引、值和检测方法的异常值详情
        """
        zscore_indices, zscore_values = self._detect_zscore(col)
        iqr_indices, iqr_values = self._detect_iqr(col)
        
        details = []
        for idx, val in zip(zscore_indices, zscore_values):
            details.append({'row_index': int(idx), 'value': float(val), 'method': 'Z-score'})
        
        for idx, val in zip(iqr_indices, iqr_values):
            if idx not in zscore_indices:
                details.append({'row_index': int(idx), 'value': float(val), 'method': 'IQR'})
        
        return details
