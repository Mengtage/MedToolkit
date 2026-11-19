#!/usr/bin/env python3
# ============================================
# 数据质量控制模块
# ============================================

import pandas as pd
import numpy as np
from scipy import stats

def quality_control(data, missing_threshold=0.5, normality_alpha=0.05, verbose=True):
    """数据质量控制主函数"""
    print("开始数据质量控制...\n")
    
    missing_report = analyze_missing(data)
    if verbose:
        print("\n" + "="*50)
        print("缺失值报告")
        print("="*50)
        print(missing_report['summary'])
    
    numeric_vars = data.select_dtypes(include=[np.number]).columns.tolist()
    normality_results = normality_tests(data, numeric_vars, normality_alpha)
    
    if verbose and normality_results:
        print("\n" + "="*50)
        print("正态性检验结果")
        print("="*50)
        for var, res in normality_results.items():
            status = "正态" if res['is_normal'] else "非正态"
            print(f"  {var}: {res['test']}, p={res['p_value']:.4f} [{status}]")
    
    return {
        'missing': missing_report,
        'normality': normality_results
    }

def analyze_missing(data):
    """缺失值分析"""
    total = data.isnull().sum()
    rate = (total / len(data) * 100).round(2)
    missing_df = pd.DataFrame({
        'variable': data.columns,
        'n_missing': total.values,
        'missing_rate_%': rate.values
    })
    missing_df = missing_df[missing_df['n_missing'] > 0].sort_values('missing_rate_%', ascending=False)
    
    return {
        'by_var': missing_df,
        'total_missing': total.sum(),
        'total_rate': rate.mean(),
        'summary': missing_df
    }

def normality_tests(data, vars_list, alpha=0.05):
    """正态性检验"""
    results = {}
    for var in vars_list:
        vals = data[var].dropna()
        if len(vals) < 3:
            continue
        
        if len(vals) <= 5000:
            stat, p = stats.shapiro(vals)
            test_name = "Shapiro-Wilk"
        else:
            stat, p = stats.kstest(vals, 'norm', args=(vals.mean(), vals.std()))
            test_name = "Kolmogorov-Smirnov"
        
        results[var] = {
            'test': test_name,
            'statistic': stat,
            'p_value': p,
            'is_normal': p > alpha
        }
    return results

def detect_outliers_iqr(data, vars_list, multiplier=1.5):
    """使用IQR方法检测异常值"""
    outliers = {}
    for var in vars_list:
        Q1 = data[var].quantile(0.25)
        Q3 = data[var].quantile(0.75)
        IQR = Q3 - Q1
        lower = Q1 - multiplier * IQR
        upper = Q3 + multiplier * IQR
        is_outlier = (data[var] < lower) | (data[var] > upper)
        outliers[var] = {
            'count': is_outlier.sum(),
            'lower_bound': lower,
            'upper_bound': upper,
            'indices': data[is_outlier].index.tolist()
        }
    return outliers
