#!/usr/bin/env python3
# ============================================
# 数据质量控制模块
#
# 对应 SAP 第 2 节（缺失数据探查）与第 5 节（正态性判断）：
#   - 逐变量缺失数量与比例（总体 + 按治疗臂）
#   - 缺失模式（单调 / 任意）与缺失图谱数据
#   - 有无主要结局缺失者之间的基线特征比较（探查缺失机制）
#   - 正态性：n ≤ 5000 用 Shapiro–Wilk；n > 5000 用 Lilliefors 校正的 KS
#     （旧的直接 KS 检验使用样本估计的均值方差，p 值偏大、易误判正态）
# ============================================

import numpy as np
import pandas as pd
from scipy import stats

try:
    from statsmodels.stats.diagnostic import lilliefors
    _STATSMODELS_OK = True
except ImportError:  # pragma: no cover
    _STATSMODELS_OK = False

SHAPIRO_MAX_N = 5000


def normality_test(values) -> dict:
    """单变量正态性检验。

    Returns:
        dict: test / statistic / p_value / normal / note
    """
    x = pd.Series(values).dropna()
    n = len(x)
    if n < 3:
        return {"test": "NA", "statistic": np.nan, "p_value": np.nan,
                "normal": None, "note": "样本量不足"}
    if x.nunique() < 2:
        return {"test": "NA", "statistic": np.nan, "p_value": np.nan,
                "normal": None, "note": "常数变量"}

    if n <= SHAPIRO_MAX_N:
        stat, p = stats.shapiro(x)
        return {"test": "Shapiro-Wilk", "statistic": float(stat),
                "p_value": float(p), "normal": bool(p > 0.05), "note": ""}

    if _STATSMODELS_OK:
        stat, p = lilliefors(x.to_numpy(dtype=float), dist="norm")
        return {"test": "Lilliefors", "statistic": float(stat),
                "p_value": float(p), "normal": bool(p > 0.05),
                "note": "n>5000，使用 Lilliefors 校正"}
    # 无 statsmodels 时的保守回退：Anderson-Darling，取 5% 临界值
    res = stats.anderson(x, dist="norm")
    crit_idx = 2  # 5% 显著性水平
    return {"test": "Anderson-Darling", "statistic": float(res.statistic),
            "p_value": np.nan, "normal": bool(res.statistic < res.critical_values[crit_idx]),
            "note": "statsmodels 不可用，改用 Anderson-Darling（5% 临界值）"}


def quality_control(data, missing_threshold=0.5, normality_alpha=0.05,
                    strata=None, outcome_var=None, verbose=True):
    """数据质量控制主函数。

    Args:
        data: 输入数据
        missing_threshold: 缺失率告警阈值
        normality_alpha: 正态性检验显著性水平
        strata: 分组变量（用于按臂统计缺失、组间比较）
        outcome_var: 主要结局变量（用于"完成者 vs 未完成者"比较）
        verbose: 是否打印报告
    """
    print("开始数据质量控制...\n")

    missing_report = analyze_missing(data, strata=strata,
                                     threshold=missing_threshold)
    if verbose:
        print("\n" + "=" * 50)
        print("缺失值报告")
        print("=" * 50)
        print(missing_report["summary"])

    numeric_vars = data.select_dtypes(include=[np.number]).columns.tolist()
    normality_results = normality_tests(data, numeric_vars, normality_alpha)

    if verbose and normality_results:
        print("\n" + "=" * 50)
        print("正态性检验结果")
        print("=" * 50)
        for var, res in normality_results.items():
            if res["normal"] is None:
                continue
            status = "正态" if res["normal"] else "非正态"
            p_txt = f"{res['p_value']:.4f}" if np.isfinite(res["p_value"]) else "—"
            print(f"  {var}: {res['test']}, p={p_txt} [{status}]")

    completers = None
    if outcome_var and outcome_var in data.columns:
        completers = completers_vs_missing(data, outcome_var, strata=strata,
                                           verbose=verbose)

    return {
        "missing": missing_report,
        "normality": normality_results,
        "completers_comparison": completers,
    }


def analyze_missing(data, strata=None, threshold=0.5):
    """缺失值分析（总体 + 可选按臂）。"""
    total = data.isnull().sum()
    rate = (total / len(data) * 100).round(2) if len(data) else total * 0
    missing_df = pd.DataFrame({
        "variable": data.columns,
        "n_missing": total.values,
        "missing_rate_%": rate.values,
    })
    missing_df = missing_df[missing_df["n_missing"] > 0] \
        .sort_values("missing_rate_%", ascending=False)

    by_group = {}
    if strata and strata in data.columns:
        for arm, sub in data.groupby(strata):
            arm_total = sub.isnull().sum()
            by_group[str(arm)] = pd.DataFrame({
                "variable": sub.columns,
                "n_missing": arm_total.values,
                "missing_rate_%": (arm_total / len(sub) * 100).round(2).values,
            })
            by_group[str(arm)] = by_group[str(arm)][by_group[str(arm)]["n_missing"] > 0]

    # 缺失模式：按"哪些变量缺失"的组合统计频次
    pattern_cols = [c for c in missing_df["variable"].tolist()]
    patterns = None
    if pattern_cols:
        pattern = data[pattern_cols].isna()
        pattern_key = pattern.apply(lambda r: "|".join(r.index[r].tolist()) or "complete",
                                    axis=1)
        patterns = pattern_key.value_counts().rename_axis("missing_pattern").reset_index(name="n")
        patterns["%"] = (patterns["n"] / len(data) * 100).round(1)
        # 单调缺失判定：除 complete 外仅一种模式且变量数递增（简易判定）
        non_complete = pattern_key[pattern_key != "complete"]
        monotone = non_complete.nunique() <= 1

    high_missing = missing_df[missing_df["missing_rate_%"] > threshold * 100]

    return {
        "by_var": missing_df,
        "by_group": by_group,
        "patterns": patterns,
        "total_missing": int(total.sum()),
        "total_rate": float((total.sum() / (data.shape[0] * data.shape[1]) * 100)
                            if data.shape[0] and data.shape[1] else 0.0),
        "high_missing_vars": high_missing["variable"].tolist(),
        "summary": missing_df,
        "monotone": bool(monotone) if pattern_cols else True,
    }


def normality_tests(data, vars_list, alpha=0.05):
    """批量正态性检验（复用 normality_test）。"""
    results = {}
    for var in vars_list:
        if var not in data.columns:
            continue
        res = normality_test(data[var])
        if res["normal"] is None:
            continue
        res["is_normal"] = bool(res["p_value"] > alpha) if np.isfinite(res["p_value"]) \
            else bool(res["normal"])
        results[var] = res
    return results


def completers_vs_missing(data, outcome_var, strata=None, verbose=True):
    """比较"有结局数据"与"结局缺失"两组人的基线特征（探查缺失机制）。

    这是 SAP 第 2 节要求的步骤：若两组基线差异明显，提示缺失可能非 MCAR。
    返回各基线变量的组间比较结果（连续：Mann-Whitney；分类：卡方）。
    """
    miss_mask = data[outcome_var].isna()
    n_miss = int(miss_mask.sum())
    n_obs = int((~miss_mask).sum())
    if n_miss == 0 or n_obs == 0:
        return {"n_missing": n_miss, "n_observed": n_obs, "comparisons": []}

    comparisons = []
    for col in data.columns:
        if col in (outcome_var, strata) or data[col].isna().all():
            continue
        if pd.api.types.is_numeric_dtype(data[col]):
            a = data.loc[~miss_mask, col].dropna()
            b = data.loc[miss_mask, col].dropna()
            if len(a) < 3 or len(b) < 3:
                continue
            try:
                p = float(stats.mannwhitneyu(a, b).pvalue)
            except ValueError:
                continue
            comparisons.append({
                "variable": col,
                "observed": f"{a.median():.2f} (IQR {a.quantile(0.25):.2f}–{a.quantile(0.75):.2f})",
                "missing": f"{b.median():.2f} (IQR {b.quantile(0.25):.2f}–{b.quantile(0.75):.2f})",
                "p_value": p,
            })
        else:
            tab = pd.crosstab(data[col], miss_mask)
            if tab.shape != (2, 2):
                continue
            try:
                p = float(stats.chi2_contingency(tab, correction=False)[1])
            except ValueError:
                continue
            comparisons.append({
                "variable": col,
                "observed": "—", "missing": "—", "p_value": p,
            })

    if verbose and comparisons:
        print("\n" + "=" * 50)
        print(f"完成者 (n={n_obs}) vs 结局缺失者 (n={n_miss}) 基线比较")
        print("=" * 50)
        for c in comparisons:
            flag = " *" if c["p_value"] < 0.05 else ""
            print(f"  {c['variable']}: P={c['p_value']:.3f}{flag}")

    return {"n_missing": n_miss, "n_observed": n_obs,
            "comparisons": comparisons}


def detect_outliers_iqr(data, vars_list, multiplier=1.5):
    """使用IQR方法检测异常值"""
    outliers = {}
    for var in vars_list:
        s = data[var].dropna()
        if len(s) < 4:
            continue
        Q1 = s.quantile(0.25)
        Q3 = s.quantile(0.75)
        IQR = Q3 - Q1
        lower = Q1 - multiplier * IQR
        upper = Q3 + multiplier * IQR
        is_outlier = (data[var] < lower) | (data[var] > upper)
        outliers[var] = {
            "count": int(is_outlier.sum()),
            "lower_bound": lower,
            "upper_bound": upper,
            "indices": data[is_outlier].index.tolist(),
        }
    return outliers
