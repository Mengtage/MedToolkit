#!/usr/bin/env python3
# ============================================
# 效应量计算模块
# ============================================

import pandas as pd
import numpy as np
from scipy import stats

def calculate_effect_size(data, vars=None, groups=2, strata=None, config=None, verbose=True):
    """
    计算效应量及其95%置信区间
    
    支持:
    - 连续变量: Cohen's d, Hedges' g, Mean Difference
    - 二分类变量: OR, RR, RD, NNT
    """
    print("开始计算效应量...\n")
    
    if config is None:
        config = {}
    
    # 确定变量
    if vars is None:
        vars = data.select_dtypes(include=[np.number]).columns.tolist()
    
    print(f"效应量计算变量: {len(vars)}个")
    print(f"分组数量: {groups}\n")
    
    effect_sizes = []
    
    for var in vars:
        if strata is None:
            continue
            
        x = data[var]
        
        # 判断变量类型
        unique_vals = x.dropna().unique()
        is_binary = len(unique_vals) <= 2
        
        if is_binary:
            result = calculate_binary_effect_size(data, var, strata, groups)
        else:
            result = calculate_continuous_effect_size(data, var, strata, groups)
        
        if result:
            effect_sizes.append(result)
    
    # 多重比较校正
    if len(effect_sizes) > 1:
        p_values = [e['p_value'] for e in effect_sizes if 'p_value' in e]
        if p_values:
            p_adjusted = stats.fdr_bonferroni(p_values)
            for i, e in enumerate(effect_sizes):
                if 'p_value' in e:
                    e['p_adjusted'] = p_adjusted[i]
    
    # 格式化结果
    results_df = format_effect_size_results(effect_sizes)
    
    if verbose and len(results_df) > 0:
        print("\n" + "="*50)
        print("效应量计算结果")
        print("="*50)
        print(results_df.to_string(index=False))
    
    return {
        'effect_sizes': effect_sizes,
        'results_table': results_df,
        'vars_analyzed': vars
    }

def calculate_continuous_effect_size(data, variable, group, groups):
    """计算连续变量的效应量"""
    group_levels = data[group].unique()
    
    if len(group_levels) < 2:
        return None
    
    if groups == 2:
        group1 = data[data[group] == group_levels[0]][variable].dropna()
        group2 = data[data[group] == group_levels[1]][variable].dropna()
        
        n1, n2 = len(group1), len(group2)
        mean1, mean2 = group1.mean(), group2.mean()
        sd1, sd2 = group1.std(), group2.std()
        
        # 均值差
        md = mean1 - mean2
        
        # Cohen's d
        pooled_sd = np.sqrt(((n1 - 1) * sd1**2 + (n2 - 1) * sd2**2) / (n1 + n2 - 2))
        cohens_d = md / pooled_sd if pooled_sd > 0 else 0
        
        # Hedges' g
        correction = 1 - (3 / (4 * (n1 + n2) - 9))
        hedges_g = cohens_d * correction
        
        # 95% CI
        se_d = np.sqrt((n1 + n2) / (n1 * n2) + cohens_d**2 / (2 * (n1 + n2)))
        ci_lower = cohens_d - 1.96 * se_d
        ci_upper = cohens_d + 1.96 * se_d
        
        return {
            'variable': variable,
            'type': 'continuous',
            'comparison': f"{group_levels[0]} vs {group_levels[1]}",
            'n1': n1, 'n2': n2,
            'mean1': mean1, 'mean2': mean2,
            'sd1': sd1, 'sd2': sd2,
            'mean_diff': md,
            'cohens_d': cohens_d,
            'hedges_g': hedges_g,
            'ci_95_lower': ci_lower,
            'ci_95_upper': ci_upper
        }
    else:
        return None

def calculate_binary_effect_size(data, exposure, outcome, groups):
    """计算二分类变量的效应量"""
    if groups != 2:
        return None
    
    outcome_levels = data[outcome].unique()
    if len(outcome_levels) != 2:
        return None
    
    # 创建列联表
    exposed = data[data[exposure] == 1]
    unexposed = data[data[exposure] == 0]
    
    if len(exposed) == 0 or len(unexposed) == 0:
        return None
    
    # 计算率
    p1 = exposed[outcome].mean()  # 暴露组事件率
    p2 = unexposed[outcome].mean()  # 非暴露组事件率
    
    # OR
    a = exposed[exposed[outcome] == 1].shape[0]
    b = exposed[exposed[outcome] == 0].shape[0]
    c = unexposed[unexposed[outcome] == 1].shape[0]
    d = unexposed[unexposed[outcome] == 0].shape[0]
    
    if b == 0 or c == 0:
        return None
    
    or_val = (a * d) / (b * c)
    rr_val = p1 / p2 if p2 > 0 else np.inf
    rd_val = p1 - p2
    nnt_val = 1 / rd_val if rd_val > 0 else np.inf
    
    # 95% CI for OR
    log_or = np.log(or_val)
    se_log_or = np.sqrt(1/a + 1/b + 1/c + 1/d)
    or_lower = np.exp(log_or - 1.96 * se_log_or)
    or_upper = np.exp(log_or + 1.96 * se_log_or)
    
    return {
        'variable': exposure,
        'type': 'binary',
        'rate_exposed': p1,
        'rate_unexposed': p2,
        'odds_ratio': or_val,
        'or_ci_lower': or_lower,
        'or_ci_upper': or_upper,
        'risk_ratio': rr_val,
        'risk_difference': rd_val,
        'nnt': nnt_val
    }

def format_effect_size_results(effect_sizes):
    """格式化效应量结果"""
    results = []
    for e in effect_sizes:
        if e['type'] == 'continuous':
            results.append({
                'Variable': e['variable'],
                'Type': '连续变量',
                'Comparison': e['comparison'],
                'Mean1_SD1': f"{e['mean1']:.2f}±{e['sd1']:.2f}",
                'Mean2_SD2': f"{e['mean2']:.2f}±{e['sd2']:.2f}",
                'Mean_Diff': f"{e['mean_diff']:.3f}",
                "Cohen's_d": f"{e['cohens_d']:.3f}",
                "Hedges'_g": f"{e['hedges_g']:.3f}",
                'CI_95': f"({e['ci_95_lower']:.3f}, {e['ci_95_upper']:.3f})"
            })
        elif e['type'] == 'binary':
            results.append({
                'Variable': e['variable'],
                'Type': '二分类变量',
                'Rate_Exposed': f"{e['rate_exposed']*100:.1f}%",
                'Rate_Unexposed': f"{e['rate_unexposed']*100:.1f}%",
                'OR': f"{e['odds_ratio']:.2f}",
                'OR_CI': f"({e['or_ci_lower']:.2f}, {e['or_ci_upper']:.2f})",
                'RR': f"{e['risk_ratio']:.2f}",
                'RD': f"{e['risk_difference']:.3f}",
                'NNT': f"{e['nnt']:.1f}" if np.isfinite(e['nnt']) else 'N/A'
            })
    
    return pd.DataFrame(results) if results else pd.DataFrame()
