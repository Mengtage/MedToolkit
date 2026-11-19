"""
数据可视化辅助模块
"""

import pandas as pd
import numpy as np


class Visualizer:
    """
    可视化数据准备类
    """
    
    @staticmethod
    def prepare_histogram_data(df, column, bins=20):
        """
        准备直方图数据
        """
        data = df[column].dropna().astype(float)
        
        hist, bin_edges = np.histogram(data, bins=bins)
        
        bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2
        bin_widths = bin_edges[1:] - bin_edges[:-1]
        
        return {
            'values': data.tolist(),
            'histogram': {
                'counts': hist.tolist(),
                'bin_edges': bin_edges.tolist(),
                'bin_centers': bin_centers.tolist(),
                'bin_widths': bin_widths.tolist()
            }
        }
    
    @staticmethod
    def prepare_boxplot_data(df, column, group_var=None):
        """
        准备箱线图数据
        """
        data = df[column].dropna().astype(float)
        
        q1 = data.quantile(0.25)
        median = data.median()
        q3 = data.quantile(0.75)
        iqr = q3 - q1
        
        lower_fence = q1 - 1.5 * iqr
        upper_fence = q3 + 1.5 * iqr
        
        outliers = data[(data < lower_fence) | (data > upper_fence)]
        
        result = {
            'min': float(data.min()),
            'q1': float(q1),
            'median': float(median),
            'q3': float(q3),
            'max': float(data.max()),
            'outliers': outliers.tolist()
        }
        
        if group_var and group_var in df.columns:
            result['groups'] = {}
            for g in df[group_var].unique():
                group_data = df[df[group_var] == g][column].dropna().astype(float)
                if len(group_data) > 0:
                    g_q1 = group_data.quantile(0.25)
                    g_median = group_data.median()
                    g_q3 = group_data.quantile(0.75)
                    result['groups'][str(g)] = {
                        'min': float(group_data.min()),
                        'q1': float(g_q1),
                        'median': float(g_median),
                        'q3': float(g_q3),
                        'max': float(group_data.max())
                    }
        
        return result
    
    @staticmethod
    def prepare_barplot_data(df, column, group_var=None):
        """
        准备条形图数据
        """
        counts = df[column].value_counts().sort_index()
        
        result = {
            'categories': [str(c) for c in counts.index.tolist()],
            'counts': counts.tolist(),
            'percents': (counts / counts.sum() * 100).round(1).tolist()
        }
        
        if group_var and group_var in df.columns:
            result['groups'] = {}
            crosstab = pd.crosstab(df[group_var], df[column])
            for g in crosstab.index:
                result['groups'][str(g)] = crosstab.loc[g].tolist()
        
        return result
    
    @staticmethod
    def prepare_scatterplot_data(df, x, y):
        """
        准备散点图数据
        """
        data = df[[x, y]].dropna().astype(float)
        
        return {
            'x': data[x].tolist(),
            'y': data[y].tolist(),
            'labels': [f"({row[x]:.2f}, {row[y]:.2f})" for _, row in data.iterrows()]
        }
    
    @staticmethod
    def prepare_missing_pattern(df):
        """
        准备缺失值模式图数据
        """
        missing_matrix = df.isnull().astype(int)
        return {
            'matrix': missing_matrix.to_dict('list'),
            'columns': df.columns.tolist(),
            'index': df.index.tolist()
        }
