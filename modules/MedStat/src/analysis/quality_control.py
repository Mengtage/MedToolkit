"""
数据质量控制模块
包含缺失值分析和异常值检测功能
"""

import pandas as pd
import numpy as np
from scipy import stats


class MissingDataAnalyzer:
    """One missing mask for summaries, plots and downstream normalization.

    Numeric sentinels are missing only when declared for a column. An explicit
    column list replaces the default text-code policy (use [] for native NA only).
    """
    DEFAULT_TEXT_CODES = ('', 'na', 'n/a', 'n.a.', 'nan', 'none', 'null',
                          'nil', '.', '-', '--', '---', '?', '??', '???',
                          'missing', 'unknown', '不适用', '缺失', '无', '空')

    def __init__(self, df, missing_codes=None):
        self.df = df
        if missing_codes is not None and not isinstance(missing_codes, dict):
            raise ValueError('missing_codes必须是按变量名定义的字典')
        self.missing_codes = missing_codes or {}
        if set(self.missing_codes) - set(df.columns):
            raise ValueError('缺失码字典包含不存在的变量')
        if any(not isinstance(v, (list, tuple)) for v in self.missing_codes.values()):
            raise ValueError('每个变量的缺失码必须是列表')
        self.missing_stats = None

    def get_missing_matrix(self):
        mask = self.df.isna().copy()
        for col in self.df:
            codes = self.missing_codes.get(col, self.DEFAULT_TEXT_CODES)
            text_codes = {v.strip().casefold() for v in codes if isinstance(v, str)}
            numeric_codes = [v for v in codes if not isinstance(v, str) and v is not None]
            # Test values, rather than dtype, so object/string/category behave alike.
            text_mask = self.df[col].map(lambda v: isinstance(v, str) and v.strip().casefold() in text_codes)
            mask[col] = mask[col] | text_mask.fillna(False).astype(bool)
            if numeric_codes:
                mask[col] = mask[col] | self.df[col].isin(numeric_codes)
        return mask.astype(int)

    def normalized_data(self):
        return self.df.mask(self.get_missing_matrix().astype(bool))

    def analyze(self):
        mask = self.get_missing_matrix()
        total = len(self.df)
        results = [{'variable': col, 'missing_count': int(mask[col].sum()),
                    'missing_percent': round(float(mask[col].sum()) / total * 100, 2) if total else 0,
                    'total': total} for col in self.df]
        self.missing_stats = pd.DataFrame(results)
        return results

    def has_missing_data(self):
        return bool(self.get_missing_matrix().to_numpy().any())


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
