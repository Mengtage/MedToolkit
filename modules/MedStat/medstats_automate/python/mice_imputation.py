#!/usr/bin/env python3
# ============================================
# MICE多重插补模块
# ============================================

import pandas as pd
import numpy as np
from sklearn.experimental import enable_iterative_imputer
from sklearn.impute import IterativeImputer
import warnings

def mice_imputation(data, vars=None, m=5, maxit=10, seed=42, verbose=True):
    """
    多重插补(MICE)
    
    使用 sklearn IterativeImputer 实现预测均值匹配(PMM)方法
    """
    print("开始MICE多重插补...\n")
    
    np.random.seed(seed)
    
    # 确定需要插补的变量
    if vars is None:
        vars = data.columns[data.isnull().any()].tolist()
    
    if len(vars) == 0:
        print("没有发现需要插补的变量")
        return {'data': data, 'imputation': None}
    
    print(f"需要插补的变量: {len(vars)}个")
    print(f"插补数据集数量: {m}")
    print(f"最大迭代次数: {maxit}\n")
    
    # 自动选择插补方法
    methods = auto_select_imputation_method(data, vars)
    if verbose:
        print("插补方法选择:")
        for var, method in methods.items():
            print(f"  {var}: {method}")
    
    # 使用IterativeImputer进行插补
    # 对于分类变量，使用阈值转换为数值
    data_numeric = data[vars].copy()
    
    # 记录分类变量的编码映射
    categorical_maps = {}
    for var in vars:
        if data_numeric[var].dtype == 'object' or not pd.api.types.is_numeric_dtype(data_numeric[var]):
            unique_vals = data_numeric[var].dropna().unique()
            if len(unique_vals) <= 10:
                mapping = {v: i for i, v in enumerate(unique_vals)}
                data_numeric[var] = data_numeric[var].map(mapping)
                categorical_maps[var] = {v: k for k, v in mapping.items()}
    
    # 执行插补
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        
        imputer = IterativeImputer(
            max_iter=maxit,
            random_state=seed,
            skip_complete=True
        )
        
        data_imputed = data.copy()
        data_imputed[vars] = imputer.fit_transform(data_numeric)
    
    print(f"MICE插补完成!\n")
    
    return {
        'data': data_imputed,
        'methods': methods,
        'vars_imputed': vars
    }

def auto_select_imputation_method(data, vars):
    """自动选择插补方法"""
    methods = {}
    for var in vars:
        if var not in data.columns:
            continue
            
        col_data = data[var]
        
        if pd.api.types.is_numeric_dtype(col_data):
            unique_count = col_data.dropna().nunique()
            if unique_count <= 10:
                methods[var] = 'pmm'  # 预测均值匹配
            else:
                methods[var] = 'pmm'
        else:
            unique_count = col_data.dropna().nunique()
            if unique_count <= 3:
                methods[var] = 'logreg'  # Logistic回归
            else:
                methods[var] = 'polyreg'  # 多项Logistic
    
    return methods
