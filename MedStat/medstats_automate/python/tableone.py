#!/usr/bin/env python3
# ============================================
# TableOne基线资料表模块
# ============================================

import pandas as pd
import numpy as np
from scipy import stats
import warnings

try:
    from quality_control import normality_test
except ImportError:  # 独立运行时回退到本地实现
    normality_test = None


def _normality(vals):
    """正态性判断：统一走 quality_control.normality_test（Shapiro / Lilliefors）。"""
    if normality_test is not None:
        res = normality_test(vals)
        if res["normal"] is None:
            return None
        return {"test": res["test"], "statistic": res["statistic"],
                "p_value": res["p_value"], "normal": res["normal"]}
    vals = pd.Series(vals).dropna()
    if len(vals) < 3 or vals.nunique() < 2:
        return None
    stat, p = stats.shapiro(vals) if len(vals) <= 5000 else (np.nan, np.nan)
    return {"test": "Shapiro-Wilk", "statistic": stat, "p_value": p, "normal": p > 0.05}

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
    # 注意：bool 变量必须按分类处理——旧版本漏了 'bool'，
    # 导致 True/False 列进入连续变量分支，np.percentile 直接抛 TypeError
    factor_vars = data.select_dtypes(include=['category', 'object', 'bool']).columns.tolist()
    cont_vars = [v for v in all_vars
                 if v not in factor_vars and pd.api.types.is_numeric_dtype(data[v])]
    
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
            res = _normality(vals)
            if res is None:
                continue
            normality_results[var] = {
                'test': res['test'],
                'statistic': res['statistic'],
                'p_value': res['p_value'],
                'normal': res['normal']
            }
            if config.get('auto_detect_nonnormal', True) and not res['normal']:
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
    """计算组间比较 P 值（Table 1 描述性比较）。

    修复点（v2.0）：
        1. 旧版读取 normality_results[...]['is_normal']，但该字典的键是 'normal'，
           导致所有连续变量都被判为非正态、一律走秩检验；
        2. 旧版用"观察频数最小值 < 5"决定是否用 Fisher——正确做法是比较
           **期望频数**（chi2_contingency 的 expected）；且 Fisher 仅适用于 2×2；
        3. 旧版对 P 值做跨变量 Bonferroni 校正（p × 变量数），SAP 明确
           基线比较的 P 为描述性，不应校正——已移除；
        4. 对整形/布尔输入与异常返回值做健壮处理，避免 ndarray 直接 round 报错。
    """
    p_values = []

    if strata is None:
        return pd.DataFrame(p_values)

    arm_names = list(data[strata].dropna().unique())

    # ---------------- 连续变量 ----------------
    for var in cont_vars:
        try:
            samples = []
            for a in arm_names:
                s = pd.to_numeric(data.loc[data[strata] == a, var], errors="coerce").dropna()
                if len(s) > 1 and s.nunique() > 1:
                    samples.append(s.to_numpy(dtype=float))
            if len(samples) < 2:
                continue

            is_normal = normality_results.get(var, {}).get('normal', None)

            if len(samples) == 2:
                if is_normal is True:
                    stat, p = stats.ttest_ind(samples[0], samples[1], equal_var=False)
                    method = "Welch t-test"
                else:
                    stat, p = stats.mannwhitneyu(samples[0], samples[1])
                    method = "Mann-Whitney U"
            else:
                if is_normal is True:
                    stat, p = stats.f_oneway(*samples)
                    method = "ANOVA"
                else:
                    stat, p = stats.kruskal(*samples)
                    method = "Kruskal-Wallis"

            p_values.append({
                'Variable': var,
                'Test': method,
                'Statistic': float(stat),
                'P_value': round(float(p), 4),
                'P_adjusted': None,   # 基线比较为描述性，不做多重性校正
            })
        except Exception as exc:  # 单个变量失败不影响整表
            p_values.append({
                'Variable': var, 'Test': f'N/A ({exc})',
                'Statistic': None, 'P_value': None, 'P_adjusted': None,
            })

    # ---------------- 分类变量 ----------------
    for var in factor_vars:
        try:
            tab = pd.crosstab(data[strata], data[var])
            if tab.shape[0] < 2 or tab.shape[1] < 2:
                continue

            chi2, p_chi, dof, expected = stats.chi2_contingency(tab, correction=False)
            min_expected = float(expected.min())

            if tab.shape == (2, 2) and min_expected < 5:
                _, p = stats.fisher_exact(tab)
                stat, method = float('nan'), "Fisher exact"
            else:
                stat, method = float(chi2), "Chi-square"
                if min_expected < 1:
                    method += " (expected count <1, interpret with caution)"
                p = float(p_chi)

            p_values.append({
                'Variable': var,
                'Test': method,
                'Statistic': None if np.isnan(stat) else float(stat),
                'P_value': round(float(p), 4) if np.isfinite(p) else None,
                'P_adjusted': None,
            })
        except Exception as exc:
            p_values.append({
                'Variable': var, 'Test': f'N/A ({exc})',
                'Statistic': None, 'P_value': None, 'P_adjusted': None,
            })

    return pd.DataFrame(p_values)
