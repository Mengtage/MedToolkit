#!/usr/bin/env python3
# ============================================
# TableOne基线资料表模块
# ============================================

import pandas as pd
import numpy as np
from scipy import stats
import warnings

def generate_tableone(data, groups=2, strata=None, config=None, verbose=True):
    """
    生成TableOne基线资料表
    
    Parameters:
    -----------
    data : pd.DataFrame
        输入数据
    groups : int
        实验组数(1/2/3+)
    strata : str
        分组变量名
    config : dict
        配置参数
        
    Returns:
    --------
    dict : 包含tableone结果和分析详情
    """
    print("开始生成TableOne基线资料表...\n")
    
    if config is None:
        config = {}
    
    # 确定变量类型
    all_vars = data.columns.tolist()
    factor_vars = data.select_dtypes(include=['category', 'object']).columns.tolist()
    cont_vars = [v for v in all_vars if v not in factor_vars]
    
    if strata and strata in factor_vars:
        factor_vars.remove(strata)
    
    print(f"分类变量: {len(factor_vars)}个")
    print(f"连续变量: {len(cont_vars)}个\n")
    
    # 正态性检验
    normality_results = {}
    auto_nonnormal = []
    
    for var in cont_vars:
        vals = data[var].dropna()
        if len(vals) >= 3:
            if len(vals) <= 5000:
                stat, p = stats.shapiro(vals)
                test_name = "Shapiro-Wilk"
            else:
                stat, p = stats.kstest(vals, 'norm', args=(vals.mean(), vals.std()))
                test_name = "Kolmogorov-Smirnov"
            
            normality_results[var] = {
                'test': test_name,
                'statistic': stat,
                'p_value': p,
                'normal': p > 0.05
            }
            
            if config.get('auto_detect_nonnormal', True) and p <= 0.05:
                auto_nonnormal.append(var)
    
    # 生成描述性统计表
    results = []
    
    # 连续变量
    for var in cont_vars:
        vals = data[var].dropna()
        
        if strata:
            groups_data = data.groupby(strata)[var].apply(list).to_dict()
            
            for group_name, group_vals in groups_data.items():
                group_vals = [v for v in group_vals if v is not None and not np.isnan(v)]
                if len(group_vals) > 0:
                    results.append({
                        'Variable': var,
                        'Group': group_name,
                        'Type': 'Continuous',
                        'N': len(group_vals),
                        'Mean': np.mean(group_vals),
                        'SD': np.std(group_vals),
                        'Median': np.median(group_vals),
                        'Q25': np.percentile(group_vals, 25),
                        'Q75': np.percentile(group_vals, 75)
                    })
        else:
            results.append({
                'Variable': var,
                'Group': 'Overall',
                'Type': 'Continuous',
                'N': len(vals),
                'Mean': np.mean(vals),
                'SD': np.std(vals),
                'Median': np.median(vals),
                'Q25': np.percentile(vals, 25),
                'Q75': np.percentile(vals, 75)
            })
    
    # 分类变量
    for var in factor_vars:
        if strata:
            crosstab = pd.crosstab(data[strata], data[var], normalize='index') * 100
            counts = pd.crosstab(data[strata], data[var])
            
            for group_name in crosstab.index:
                for level in crosstab.columns:
                    results.append({
                        'Variable': var,
                        'Group': str(group_name),
                        'Level': str(level),
                        'Type': 'Categorical',
                        'N': int(counts.loc[group_name, level]),
                        'Percent': round(crosstab.loc[group_name, level], 1)
                    })
        else:
            counts = data[var].value_counts()
            for level, count in counts.items():
                results.append({
                    'Variable': var,
                    'Group': 'Overall',
                    'Level': str(level),
                    'Type': 'Categorical',
                    'N': int(count),
                    'Percent': round(count / len(data) * 100, 1)
                })
    
    results_df = pd.DataFrame(results)
    
    # 组间比较P值
    p_values = calculate_pvalues(data, cont_vars, factor_vars, strata, groups, normality_results)
    
    if verbose:
        print("\n" + "="*50)
        print("TableOne生成完成")
        print("="*50)
        print(f"分组数量: {groups}")
        print(f"分组变量: {strata if strata else '无'}")
    
    return {
        'tableone': results_df,
        'normality': normality_results,
        'p_values': p_values,
        'groups': groups,
        'strata': strata,
        'factor_vars': factor_vars,
        'cont_vars': cont_vars,
        'nonnormal_vars': auto_nonnormal
    }

def calculate_pvalues(data, cont_vars, factor_vars, strata, groups, normality_results):
    """计算组间比较P值"""
    p_values = []
    
    if strata is None:
        return pd.DataFrame(p_values)
    
    for var in cont_vars:
        group_vals = data.groupby(strata)[var].apply(list).to_dict()
        group_vals = {k: [v for v in vals if v is not None and not np.isnan(v)] 
                      for k, vals in group_vals.items()}
        
        group_list = list(group_vals.values())
        group_names = list(group_vals.keys())
        
        if len(group_list) >= 2:
            # 检查正态性
            is_normal = bool(normality_results.get(var, {}).get('is_normal', False))
            is_nonnormal = False
            
            # 两组比较
            if groups == 2:
                if is_normal:
                    stat, p = stats.ttest_ind(group_list[0], group_list[1])
                    method = "t-test"
                else:
                    stat, p = stats.mannwhitneyu(group_list[0], group_list[1])
                    method = "Mann-Whitney U"
            else:
                # 多组比较
                if is_normal:
                    stat, p = stats.f_oneway(*group_list)
                    method = "ANOVA"
                else:
                    stat, p = stats.kruskal(*group_list)
                    method = "Kruskal-Wallis"
            
            # 多重比较校正
            p_adj = min(p * len(cont_vars), 1.0)
            
            p_values.append({
                'Variable': var,
                'Test': method,
                'Statistic': stat,
                'P_value': round(p, 4),
                'P_adjusted': round(p_adj, 4)
            })
    
    # 分类变量卡方检验
    for var in factor_vars:
        contingency = pd.crosstab(data[strata], data[var])
        
        if contingency.size > 0:
            min_expected = contingency.values.min()
            
            if min_expected < 5:
                try:
                    stat, p = stats.fisher_exact(contingency)
                    method = "Fisher exact"
                except:
                    stat, p = np.nan, np.nan
                    method = "N/A"
            else:
                stat, p, dof, expected = stats.chi2_contingency(contingency)
                method = "Chi-square"
            
            p_values.append({
                'Variable': var,
                'Test': method,
                'Statistic': stat if not np.isnan(stat) else None,
                'P_value': round(p, 4) if not np.isnan(p) else None,
                'P_adjusted': None
            })
    
    return pd.DataFrame(p_values)
