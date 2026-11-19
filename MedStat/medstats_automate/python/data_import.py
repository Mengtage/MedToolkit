#!/usr/bin/env python3
# ============================================
# 数据导入模块
# 医学统计分析自动化系统
# 
# 支持格式: CSV, Excel, SPSS, STATA
# ============================================

import pandas as pd
import numpy as np
from pathlib import Path

def import_data(file_path, encoding='UTF-8', na_values=None):
    """
    导入数据文件
    
    Parameters:
    -----------
    file_path : str
        数据文件路径
    encoding : str
        文件编码，默认UTF-8
    na_values : list, optional
        自定义缺失值标记列表，例如 [12345, -999]
        如果为None，使用默认的 ['NA', 'N/A', 'null', '']
        
    Returns:
    --------
    pd.DataFrame
        导入的数据框
    """
    print(f"开始导入数据: {file_path}")
    
    if not Path(file_path).exists():
        raise FileNotFoundError(f"文件不存在: {file_path}")
    
    # 设置缺失值标记
    default_na = ['NA', 'N/A', 'null', '']
    if na_values is not None:
        # 合并默认缺失值和自定义缺失值
        all_na = list(set(default_na + [str(v) for v in na_values] + na_values))
    else:
        all_na = default_na
    
    # 根据扩展名选择导入方法
    ext = Path(file_path).suffix.lower()
    
    if ext == '.csv':
        data = pd.read_csv(file_path, encoding=encoding, na_values=all_na, keep_default_na=False)
    elif ext in ['.xlsx', '.xls']:
        data = pd.read_excel(file_path, na_values=all_na)
    elif ext == '.sav':
        try:
            import pyreadstat
            data, _ = pyreadstat.read_sav(file_path)
        except ImportError:
            raise ImportError("需要安装 pyreadstat 包来读取SPSS文件")
    elif ext == '.dta':
        try:
            data = pd.read_stata(file_path)
        except Exception as e:
            raise ValueError(f"读取STATA文件失败: {e}")
    else:
        raise ValueError(f"不支持的文件格式: {ext}")
    
    # 数据基本信息
    print(f"\n数据维度: {data.shape[0]} 行 × {data.shape[1]} 列")
    print(f"内存占用: {data.memory_usage(deep=True).sum() / 1024**2:.2f} MB")
    
    # 自动识别变量类型
    data = auto_detect_types(data)
    
    return data


def auto_detect_types(data):
    """
    自动检测变量类型
    
    Parameters:
    -----------
    data : pd.DataFrame
        输入数据框
        
    Returns:
    --------
    pd.DataFrame
        类型转换后的数据框
    """
    print("\n开始自动识别变量类型...")
    
    for col in data.columns:
        # 跳过已经是数值型的列
        if pd.api.types.is_numeric_dtype(data[col]):
            continue
        
        # 获取唯一值
        unique_vals = data[col].dropna().unique()
        n_unique = len(unique_vals)
        n_total = len(data[col])
        
        # 二分类变量
        if n_unique <= 2:
            data[col] = data[col].astype('category')
            print(f"  {col} -> 二分类因子 (levels: {list(data[col].cat.categories)})")
        
        # 多分类变量
        elif n_unique <= 10 and data[col].dtype == 'object':
            data[col] = data[col].astype('category')
            print(f"  {col} -> 多分类因子 ({n_unique} levels)")
        
        # 字符型 -> 尝试转换为数值
        elif data[col].dtype == 'object':
            try:
                numeric_vals = pd.to_numeric(data[col], errors='coerce')
                valid_ratio = numeric_vals.notna().sum() / len(data[col])
                
                if valid_ratio > 0.5:
                    data[col] = numeric_vals
                    print(f"  {col} -> 数值型 (自动转换)")
                else:
                    data[col] = data[col].astype('category')
                    print(f"  {col} -> 分类因子")
            except:
                data[col] = data[col].astype('category')
    
    return data


def preview_data(data, n=10):
    """
    数据预览
    
    Parameters:
    -----------
    data : pd.DataFrame
        数据框
    n : int
        预览行数
    """
    print("\n" + "="*50)
    print(f"数据预览 (前{n}行):")
    print("="*50)
    print(data.head(n))
    print("\n数据类型:")
    print(data.dtypes)
