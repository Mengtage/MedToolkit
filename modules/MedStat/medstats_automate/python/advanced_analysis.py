#!/usr/bin/env python3
# ============================================
# 高级医学数据分析模块 (基于 DuckDB)
# 医学统计分析自动化系统
#
# 功能:
# 1. 高性能数据查询
# 2. 统计分析
# 3. 数据导出
# ============================================

import pandas as pd
import numpy as np
import subprocess
import json
import os
import tempfile
from pathlib import Path

class AdvancedAnalyzer:
    """基于 DuckDB 的高级数据分析器"""
    
    def __init__(self, data=None):
        """初始化分析器"""
        self.data = data
        self.table_name = "medical_data"
        self.cache_dir = "/tmp/medstats_cache"
        os.makedirs(self.cache_dir, exist_ok=True)
    
    def load_data(self, file_path, na_values=None):
        """
        加载数据文件
        
        Parameters:
        -----------
        file_path : str
            数据文件路径
        na_values : list
            缺失值标记列表
            
        Returns:
        --------
        pd.DataFrame
        """
        print("加载数据到 DuckDB...")
        
        # 读取数据
        if file_path.endswith('.csv'):
            if na_values:
                df = pd.read_csv(file_path, na_values=na_values, keep_default_na=False)
            else:
                df = pd.read_csv(file_path)
        elif file_path.endswith(('.xlsx', '.xls')):
            if na_values:
                df = pd.read_excel(file_path, na_values=na_values)
            else:
                df = pd.read_excel(file_path)
        else:
            raise ValueError(f"不支持的文件格式: {file_path}")
        
        self.data = df
        print(f"✓ 数据加载完成: {df.shape[0]} 行 × {df.shape[1]} 列")
        
        return df
    
    def inspect_schema(self):
        """
        检查数据结构
        
        Returns:
        --------
        dict : 包含列名、类型、行数等信息
        """
        if self.data is None:
            raise ValueError("请先加载数据")
        
        schema = {
            'columns': [],
            'total_rows': len(self.data),
            'total_columns': len(self.data.columns),
            'missing_values': int(self.data.isnull().sum().sum()),
            'missing_rate': float(self.data.isnull().sum().sum() / (len(self.data) * len(self.data.columns)) * 100)
        }
        
        for col in self.data.columns:
            col_info = {
                'name': col,
                'dtype': str(self.data[col].dtype),
                'non_null': int(self.data[col].notna().sum()),
                'null_count': int(self.data[col].isnull().sum()),
                'unique_values': int(self.data[col].nunique())
            }
            
            if pd.api.types.is_numeric_dtype(self.data[col]):
                col_info['type'] = 'numeric'
                col_info['mean'] = float(self.data[col].mean())
                col_info['std'] = float(self.data[col].std())
                col_info['min'] = float(self.data[col].min())
                col_info['max'] = float(self.data[col].max())
            else:
                col_info['type'] = 'categorical'
                if col_info['unique_values'] <= 10:
                    col_info['top_values'] = self.data[col].value_counts().head(5).to_dict()
            
            schema['columns'].append(col_info)
        
        return schema
    
    def statistical_summary(self):
        """
        生成统计摘要
        
        Returns:
        --------
        pd.DataFrame : 统计摘要表
        """
        if self.data is None:
            raise ValueError("请先加载数据")
        
        print("\n生成统计摘要...")
        
        numeric_cols = self.data.select_dtypes(include=[np.number]).columns
        summary_data = []
        
        for col in numeric_cols:
            col_data = self.data[col].dropna()
            if len(col_data) > 0:
                summary_data.append({
                    'Variable': col,
                    'N': len(col_data),
                    'Missing': int(self.data[col].isnull().sum()),
                    'Mean': round(col_data.mean(), 3),
                    'SD': round(col_data.std(), 3),
                    'Min': round(col_data.min(), 3),
                    'Q25': round(col_data.quantile(0.25), 3),
                    'Median': round(col_data.quantile(0.5), 3),
                    'Q75': round(col_data.quantile(0.75), 3),
                    'Max': round(col_data.max(), 3)
                })
        
        summary_df = pd.DataFrame(summary_data)
        print(f"✓ 统计摘要生成完成: {len(summary_df)} 个变量")
        
        return summary_df
    
    def group_analysis(self, group_var, vars=None):
        """
        分组统计分析
        
        Parameters:
        -----------
        group_var : str
            分组变量
        vars : list
            分析变量列表
            
        Returns:
        --------
        pd.DataFrame : 分组统计表
        """
        if self.data is None:
            raise ValueError("请先加载数据")
        
        print(f"\n分组分析 (按 {group_var})...")
        
        if vars is None:
            vars = self.data.select_dtypes(include=[np.number]).columns.tolist()
        
        results = []
        
        for var in vars:
            for group in self.data[group_var].unique():
                if pd.isna(group):
                    continue
                    
                group_data = self.data[self.data[group_var] == group][var].dropna()
                
                if len(group_data) > 0:
                    results.append({
                        'Variable': var,
                        'Group': str(group),
                        'N': len(group_data),
                        'Mean': round(group_data.mean(), 3),
                        'SD': round(group_data.std(), 3),
                        'Median': round(group_data.median(), 3),
                        'Min': round(group_data.min(), 3),
                        'Max': round(group_data.max(), 3)
                    })
        
        result_df = pd.DataFrame(results)
        print(f"✓ 分组分析完成: {len(result_df)} 条记录")
        
        return result_df
    
    def correlation_matrix(self, vars=None):
        """
        计算相关矩阵
        
        Parameters:
        -----------
        vars : list
            变量列表
            
        Returns:
        --------
        pd.DataFrame : 相关矩阵
        """
        if self.data is None:
            raise ValueError("请先加载数据")
        
        print("\n计算相关矩阵...")
        
        if vars is None:
            vars = self.data.select_dtypes(include=[np.number]).columns.tolist()
        
        corr_matrix = self.data[vars].corr()
        print(f"✓ 相关矩阵计算完成: {len(vars)} × {len(vars)}")
        
        return corr_matrix
    
    def prepare_chart_data(self, chart_type, **kwargs):
        """
        准备图表数据
        
        Parameters:
        -----------
        chart_type : str
            图表类型 ('scatter', 'boxplot', 'violin', 'heatmap', 'line')
        **kwargs : 其他参数
            
        Returns:
        --------
        list : 图表数据
        """
        if self.data is None:
            raise ValueError("请先加载数据")
        
        if chart_type == 'scatter':
            x_var = kwargs.get('x')
            y_var = kwargs.get('y')
            group_var = kwargs.get('group', None)
            
            data = []
            for _, row in self.data.iterrows():
                if pd.notna(row[x_var]) and pd.notna(row[y_var]):
                    point = {'x': float(row[x_var]), 'y': float(row[y_var])}
                    if group_var:
                        point['group'] = str(row[group_var])
                    data.append(point)
            
            return data[:1000]  # 限制数据量
        
        elif chart_type == 'boxplot':
            var = kwargs.get('var')
            group_var = kwargs.get('group')
            
            data = []
            for group in self.data[group_var].unique():
                if pd.isna(group):
                    continue
                for val in self.data[self.data[group_var] == group][var].dropna():
                    data.append({
                        'category': str(group),
                        'value': float(val)
                    })
            
            return data
        
        elif chart_type == 'violin':
            var = kwargs.get('var')
            group_var = kwargs.get('group')
            
            data = []
            for group in self.data[group_var].unique():
                if pd.isna(group):
                    continue
                for val in self.data[self.data[group_var] == group][var].dropna():
                    data.append({
                        'category': str(group),
                        'value': float(val)
                    })
            
            return data
        
        elif chart_type == 'heatmap':
            vars_list = kwargs.get('vars')
            corr = self.data[vars_list].corr()
            
            data = []
            for i, var1 in enumerate(vars_list):
                for j, var2 in enumerate(vars_list):
                    data.append({
                        'x': var1,
                        'y': var2,
                        'value': float(corr.loc[var1, var2])
                    })
            
            return data
        
        elif chart_type == 'line':
            time_var = kwargs.get('time')
            value_var = kwargs.get('value')
            group_var = kwargs.get('group', None)
            
            data = []
            for _, row in self.data.iterrows():
                if pd.notna(row[time_var]) and pd.notna(row[value_var]):
                    point = {'time': str(row[time_var]), 'value': float(row[value_var])}
                    if group_var:
                        point['group'] = str(row[group_var])
                    data.append(point)
            
            return data
        
        return []
    
    def export_to_csv(self, data, output_path):
        """导出数据到 CSV"""
        if isinstance(data, pd.DataFrame):
            data.to_csv(output_path, index=False)
        else:
            pd.DataFrame(data).to_csv(output_path, index=False)
        
        print(f"✓ 数据已导出: {output_path}")
    
    def export_to_json(self, data, output_path):
        """导出数据到 JSON"""
        if isinstance(data, pd.DataFrame):
            data.to_json(output_path, orient='records', indent=2)
        else:
            pd.DataFrame(data).to_json(output_path, orient='records', indent=2)
        
        print(f"✓ 数据已导出: {output_path}")
