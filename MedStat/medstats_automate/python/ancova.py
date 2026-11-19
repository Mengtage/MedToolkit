#!/usr/bin/env python3
# ============================================
# 基线校正的组间比较（ANCOVA / logistic 回归）
#
# 对应 SAP 第 6、14 节：
#   - 主要终点：ANCOVA（治疗臂为固定效应，校正基线值与分层因素）
#   - 多臂：先做总体 Wald 检验，再做全部两两比较
#   - 两两比较的多重性校正：Holm（可切换 Bonferroni / BH-FDR）
#   - 所有模型在 m 个插补数据集上分别拟合，按 Rubin's rules 合并
#
# 与旧实现的差异：旧版仅做未校正的组间检验（t 检验/方差分析），
# 无法给出"校正后组间差值及其 95% CI"，也不支持多臂两两比较。
# ============================================

from __future__ import annotations

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from statsmodels.stats.multitest import multipletests

from rubin import pool_params, wald_test, contrast


def _arm_term(group: str, arm) -> str:
    return f"C({group})[T.{arm}]"


def _arms_of(df: pd.DataFrame, group: str) -> list:
    return sorted(pd.unique(df[group].dropna()))


def _describe(series: pd.Series) -> dict:
    """描述性统计：n、均值(SD)、中位数(IQR)。"""
    x = pd.Series(series).dropna()
    q1, q3 = (x.quantile(0.25), x.quantile(0.75)) if len(x) else (np.nan, np.nan)
    return {
        "n": int(len(x)),
        "mean": float(x.mean()) if len(x) else np.nan,
        "sd": float(x.std(ddof=1)) if len(x) > 1 else np.nan,
        "median": float(x.median()) if len(x) else np.nan,
        "q1": float(q1) if len(x) else np.nan,
        "q3": float(q3) if len(x) else np.nan,
    }


def format_mean_sd(stats_dict: dict, digits: int = 2) -> str:
    if stats_dict["n"] == 0 or np.isnan(stats_dict["mean"]):
        return "—"
    return f"{stats_dict['mean']:.{digits}f} ({stats_dict['sd']:.{digits}f})"


def format_median_iqr(stats_dict: dict, digits: int = 2) -> str:
    if stats_dict["n"] == 0:
        return "—"
    return (f"{stats_dict['median']:.{digits}f} "
            f"({stats_dict['q1']:.{digits}f} to {stats_dict['q3']:.{digits}f})")


def ancova_compare(
    datasets: list[pd.DataFrame],
    outcome: str,
    group: str,
    baseline: str | None = None,
    covariates: list[str] | None = None,
    kind: str = "ols",
    alpha: float = 0.05,
    adjust: str = "holm",
) -> dict:
    """在多套（插补）数据上拟合基线校正模型并按 Rubin's rules 合并。

    Args:
        datasets: m 个数据集的列表（单套数据也可，此时 m=1，退化为常规模型）
        outcome: 结局变量
        group: 治疗臂变量（分类）
        baseline: 基线值变量（校正用）
        covariates: 额外协变量（如年龄、性别、分层因素）
        kind: "ols"（连续结局）或 "logit"（二分类结局，报告 OR）
        alpha: 显著性水平
        adjust: 两两比较校正方法："holm" / "bonferroni" / "fdr_bh"

    Returns:
        dict:
            - descriptive: {臂: 描述统计}
            - omnibus_p: 总体 Wald 检验 P（多臂时）
            - adjusted: [{comparison, estimate, ci_lower, ci_upper, p_value, p_adjusted}]
            - model: 模型说明文字
            - n_datasets: 实际使用的数据集数
    """
    if not datasets:
        raise ValueError("datasets 不能为空")

    dat = [d.dropna(subset=[outcome]) for d in datasets]
    dat = [d for d in dat if len(d) >= 3] or datasets

    rhs = f"C({group})"
    if baseline:
        rhs += f" + {baseline}"
    if covariates:
        rhs += "".join(f" + {c}" for c in covariates if c in dat[0].columns)
    formula = f"{outcome} ~ {rhs}"

    params_list, cov_list, names = [], [], None
    for d in dat:
        if kind == "logit":
            fitted = smf.logit(formula, data=d).fit(disp=0, maxiter=200)
        else:
            fitted = smf.ols(formula, data=d).fit()
        names = list(fitted.params.index)
        params_list.append(fitted.params.values)
        cov_list.append(fitted.cov_params().values)

    q, t_cov = pool_params(params_list, cov_list)

    arms = _arms_of(dat[0], group)
    ref = arms[0]
    df_complete = max(len(dat[0]) - len(names), 1)

    # ---- 总体检验（多臂时用 Wald 卡方）----
    arm_idx = [names.index(_arm_term(group, a)) for a in arms
               if _arm_term(group, a) in names]
    omnibus_p = wald_test(q, t_cov, arm_idx)[1] if len(arm_idx) >= 1 else np.nan

    # ---- 两两比较 ----
    pairs = [(a, b) for i, a in enumerate(arms) for b in arms[i + 1:]]
    rows, raw_ps = [], []
    for a, b in pairs:
        vec = np.zeros(len(names))
        t_a, t_b = _arm_term(group, a), _arm_term(group, b)
        # 对比向量必须与报告方向一致：估计值 = β_b - β_a（"b vs a"）
        if t_b in names:
            vec[names.index(t_b)] = 1
        if t_a in names:
            vec[names.index(t_a)] = -1
        est = contrast(q, t_cov, vec, df_complete)

        # 约定：报告 "b vs a"，与参考实现一致
        if kind == "logit":
            rows.append({
                "comparison": f"{b} vs {a}",
                "estimate": float(np.exp(est["estimate"])),
                "ci_lower": float(np.exp(est["ci_lower"])),
                "ci_upper": float(np.exp(est["ci_upper"])),
                "p_value": est["p_value"],
                "measure": "OR",
            })
        else:
            rows.append({
                "comparison": f"{b} vs {a}",
                "estimate": est["estimate"],
                "ci_lower": est["ci_lower"],
                "ci_upper": est["ci_upper"],
                "p_value": est["p_value"],
                "measure": "difference",
            })
        raw_ps.append(est["p_value"])

    if raw_ps:
        adjusted = multipletests(raw_ps, alpha=alpha, method=adjust)[1]
        for row, p_adj in zip(rows, adjusted):
            row["p_adjusted"] = float(p_adj)

    descriptive = {
        str(a): _describe(dat[0].loc[dat[0][group] == a, outcome]) for a in arms
    }

    baseline_txt = f"，校正 {baseline}" if baseline else ""
    cov_txt = f"、{', '.join(covariates)}" if covariates else ""
    model = ("logistic 回归（OR）" if kind == "logit" else "ANCOVA（校正后差值）") + \
            f"{baseline_txt}{cov_txt}"

    return {
        "outcome": outcome,
        "group": group,
        "arms": [str(a) for a in arms],
        "reference": str(ref),
        "descriptive": descriptive,
        "omnibus_p": float(omnibus_p),
        "adjusted": rows,
        "adjust_method": adjust,
        "model": model,
        "n_datasets": len(dat),
    }


def ancova_to_dataframe(result: dict, decimals: int = 2) -> pd.DataFrame:
    """把 ancova_compare 的结果转成可导出的表格（对应 SAP 表 2/3 风格）。"""
    rows = []
    desc = result["descriptive"]
    arms = result["arms"]
    for comp_row in result["adjusted"]:
        measure = comp_row["measure"]
        if measure == "OR":
            est_txt = (f"OR {comp_row['estimate']:.2f} "
                       f"({comp_row['ci_lower']:.2f} to {comp_row['ci_upper']:.2f})")
        else:
            est_txt = (f"{comp_row['estimate']:.{decimals}f} "
                       f"({comp_row['ci_lower']:.{decimals}f} to "
                       f"{comp_row['ci_upper']:.{decimals}f})")
        rows.append({
            "Outcome": result["outcome"],
            "Comparison": comp_row["comparison"],
            "Estimate (95% CI)": est_txt,
            "P value": _fmt_p(comp_row["p_value"]),
            "Adjusted P value": _fmt_p(comp_row.get("p_adjusted", np.nan)),
        })

    # 表头附一列各臂描述（放在单独 sheet 更清晰，这里附加在行内）
    for a in arms:
        d = desc.get(a, {})
        rows[0][f"n ({a})"] = d.get("n", "")
    return pd.DataFrame(rows)


def _fmt_p(p: float) -> str:
    if p is None or (isinstance(p, float) and np.isnan(p)):
        return ""
    return "<0.001" if p < 0.001 else f"{p:.3f}"
