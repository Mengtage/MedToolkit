#!/usr/bin/env python3
# ============================================
# 相关与回归分析模块
#
# 对应 SAP 中的"协变量校正模型"与"相关结构"：
#   - 相关矩阵：按变量正态性自动选择 Pearson / Spearman
#   - 线性回归（OLS）：主结局 ~ 分组 + 基线 + 协变量
#   - Logistic 回归：二分类结局 ~ 同上，输出 OR 及 95% CI
#   - 多重共线性诊断：VIF
#   - 多套插补数据集按 Rubin's rules 合并系数与协方差
#
# 该模块同时补齐 medstats_main.py 第 8 步原本引用但不存在的实现。
# ============================================

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

try:
    import statsmodels.api as sm
    import statsmodels.formula.api as smf
    from statsmodels.stats.outliers_influence import variance_inflation_factor
    HAS_SM = True
except ImportError:  # pragma: no cover
    HAS_SM = False

from rubin import pool_params


def _cfg_get(config, path: str, default=None):
    """从嵌套 config 中按 'a.b' 取值，缺失时返回默认值。"""
    if not config:
        return default
    cur = config
    for key in path.split("."):
        if isinstance(cur, dict) and key in cur:
            cur = cur[key]
        else:
            return default
    return cur if cur is not None else default


def _normality_p(x: pd.Series) -> float:
    x = x.dropna()
    if len(x) < 3:
        return np.nan
    if len(x) <= 5000:
        return float(stats.shapiro(x).pvalue)
    try:
        from statsmodels.stats.diagnostic import lilliefors
        return float(lilliefors(x)[1])
    except Exception:
        return float(stats.kstest(x, "norm", args=(x.mean(), x.std())).pvalue)


def _is_id_like(s: pd.Series) -> bool:
    """近唯一且为整数/命名含 id 的列视为标识列（不参与相关分析）。"""
    if len(s) == 0:
        return False
    if s.nunique() < 0.98 * len(s):
        return False
    name = str(s.name).lower() if s.name is not None else ""
    return bool(pd.api.types.is_integer_dtype(s)) or ("id" in name) or ("编号" in name)


def correlation_matrix(data: pd.DataFrame, vars_: list[str] | None = None,
                       method: str = "auto", max_vars: int = 15) -> pd.DataFrame:
    """相关矩阵。method='auto' 时逐对按正态性选择 Pearson / Spearman。

    Returns:
        相关系数矩阵（下三角）；上三角留空，便于直接写入论文表格。
    """
    cols = vars_ or [
        c for c in data.columns
        if pd.api.types.is_numeric_dtype(data[c])
        and data[c].nunique() > 2      # 排除二分类与常数
        and not _is_id_like(data[c])   # 排除 ID 类近唯一列
    ]
    cols = [c for c in cols if c in data.columns][:max_vars]
    if len(cols) < 2:
        return pd.DataFrame()

    out = pd.DataFrame(index=cols, columns=cols, dtype=object)
    for i, a in enumerate(cols):
        for j, b in enumerate(cols):
            if j > i:
                out.loc[a, b] = ""
            elif j == i:
                out.loc[a, b] = "1.00"
            else:
                pair = data[[a, b]].dropna()
                if len(pair) < 3:
                    out.loc[a, b] = "NA"
                    continue
                use_spearman = method == "spearman"
                if method == "auto":
                    pa, pb = _normality_p(pair[a]), _normality_p(pair[b])
                    use_spearman = (np.isfinite(pa) and pa < 0.05) or \
                                   (np.isfinite(pb) and pb < 0.05)
                if use_spearman:
                    r, p = stats.spearmanr(pair[a], pair[b])
                else:
                    r, p = stats.pearsonr(pair[a], pair[b])
                star = "**" if p < 0.01 else ("*" if p < 0.05 else "")
                out.loc[a, b] = f"{r:.2f}{star}"
    return out


def _vif_table(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    """方差膨胀因子（共线性诊断）。VIF > 10 提示严重共线。"""
    if not HAS_SM or len(cols) < 2:
        return pd.DataFrame()
    sub = df[cols].dropna()
    if len(sub) <= len(cols):
        return pd.DataFrame()
    X = sm.add_constant(sub.to_numpy(dtype=float))
    rows = []
    for i, c in enumerate(cols, start=1):
        try:
            v = float(variance_inflation_factor(X, i))
        except Exception:
            v = np.nan
        rows.append({"variable": c, "VIF": v})
    return pd.DataFrame(rows)


def _fit_models(datasets: list[pd.DataFrame], formula: str, kind: str):
    """在各插补集上拟合模型，返回 (params 列表, cov 列表, 参数名)。"""
    q_list, u_list, names = [], [], None
    for d in datasets:
        need = [c for c in d.columns if c in formula or True]
        try:
            if kind == "logit":
                res = smf.logit(formula, data=d).fit(disp=0, maxiter=200)
            else:
                res = smf.ols(formula, data=d).fit()
        except Exception:
            continue
        p = res.params
        cov = res.cov_params()
        if names is None:
            names = list(p.index)
        if list(p.index) != names:
            continue
        q_list.append(p.to_numpy(dtype=float))
        u_list.append(cov.loc[names, names].to_numpy(dtype=float))
    return q_list, u_list, names


def _format_model_table(names, q, cov, kind: str, alpha: float) -> pd.DataFrame:
    rows = []
    for i, term in enumerate(names):
        est, se = float(q[i]), float(np.sqrt(cov[i, i]))
        p = float(2 * stats.norm.sf(abs(est / se)))
        if kind == "logit":
            val, lo, hi = np.exp(est), np.exp(est - 1.96 * se), np.exp(est + 1.96 * se)
            effect_label = "OR (95% CI)"
            eff_txt = f"{val:.2f} ({lo:.2f} to {hi:.2f})"
        else:
            val = est
            lo, hi = est - 1.96 * se, est + 1.96 * se
            effect_label = "β (95% CI)"
            eff_txt = f"{val:.3f} ({lo:.3f} to {hi:.3f})"
        rows.append({
            "term": term,
            "effect": eff_txt,
            "p": p,
            "p_text": "<0.001" if p < 0.001 else f"{p:.3f}",
            "_label": effect_label,
        })
    return pd.DataFrame(rows)


def correlation_regression(
    data: pd.DataFrame | None = None,
    config: dict | None = None,
    datasets: list[pd.DataFrame] | None = None,
    output_dir: str | None = None,
    verbose: bool = True,
) -> dict:
    """相关与回归分析。

    模型设定来源（优先级从高到低）：
        1. 显式传参（本函数参数）
        2. config['regression'] 下的 dependent / independents / binary_outcome
        3. config 的 primary_outcome / strata / primary_baseline（与 CLI 主流程一致）

    Returns:
        dict: correlation / linear / logistic / vif / notes
    """
    if data is None and not datasets:
        raise ValueError("data 或 datasets 至少提供一个")

    base = data if data is not None else datasets[0]
    data_sets = datasets or [base]

    notes: list[str] = []
    if not HAS_SM:
        notes.append("statsmodels 不可用，相关分析可用但回归不可用")

    # ---------------- 相关矩阵 ----------------
    method = _cfg_get(config, "regression.correlation_method", "auto")
    max_vars = int(_cfg_get(config, "visualization.max_correlation_vars", 15) or 15)
    corr = correlation_matrix(base, method=method, max_vars=max_vars)

    # ---------------- 模型设定 ----------------
    dependent = _cfg_get(config, "regression.dependent") or _cfg_get(config, "primary_outcome")
    group = _cfg_get(config, "regression.group") or _cfg_get(config, "strata")
    binary_outcome = _cfg_get(config, "regression.binary_outcome")
    covars = _cfg_get(config, "regression.independents") or []
    if not covars:
        covars = [c for c in [_cfg_get(config, "primary_baseline")] if c]
        extra = _cfg_get(config, "regression.covariates") or []
        covars += [c for c in extra if c not in covars]
    covars = [c for c in covars if c and c in base.columns]
    alpha = float(_cfg_get(config, "statistics.normality_alpha", 0.05) or 0.05)
    vif_threshold = float(_cfg_get(config, "regression.vif_threshold", 10) or 10)

    linear = pd.DataFrame()
    logistic = pd.DataFrame()
    vif = pd.DataFrame()

    if not HAS_SM:
        return {"correlation": corr, "linear": linear, "logistic": logistic,
                "vif": vif, "notes": notes}

    # ---------------- 线性回归 ----------------
    if dependent and dependent in base.columns and \
            pd.api.types.is_numeric_dtype(base[dependent]):
        parts = []
        if group and group in base.columns:
            parts.append(f"C({group})")
        parts += covars
        if parts:
            formula = f"{dependent} ~ " + " + ".join(parts)
            q_list, u_list, names = _fit_models(data_sets, formula, "ols")
            if q_list:
                q, cov = pool_params(q_list, u_list)
                linear = _format_model_table(names, q, cov, "ols", alpha)
                linear.insert(0, "model", f"Linear: {dependent}")
                vif = _vif_table(base, covars)
                if len(vif):
                    bad = vif.loc[vif["VIF"] > vif_threshold, "variable"].tolist()
                    if bad:
                        notes.append(
                            f"共线性警告：{bad} 的 VIF > {vif_threshold:.0f}，"
                            f"系数估计不稳定，建议剔除或合并"
                        )
            else:
                notes.append("线性回归拟合失败（可能样本不足或变量全部缺失）")
    elif dependent:
        notes.append(f"主结局 {dependent} 不存在或非数值，跳过线性回归")

    # ---------------- Logistic 回归 ----------------
    if binary_outcome and binary_outcome in base.columns:
        ev = base[binary_outcome].dropna()
        if ev.nunique() == 2:
            parts = []
            if group and group in base.columns:
                parts.append(f"C({group})")
            parts += covars
            if parts:
                formula = f"{binary_outcome} ~ " + " + ".join(parts)
                q_list, u_list, names = _fit_models(data_sets, formula, "logit")
                if q_list:
                    q, cov = pool_params(q_list, u_list)
                    logistic = _format_model_table(names, q, cov, "logit", alpha)
                    logistic.insert(0, "model", f"Logistic: {binary_outcome}")
                    n_ev = min(int(ev.sum()), int((1 - ev).sum()))
                    n_par = len(names)
                    if n_par and n_ev * 2 / n_par < 10:
                        notes.append(
                            f"EPV 偏低（较少结局类别 {n_ev}，参数 {n_par}），"
                            f"OR 估计可能不稳定"
                        )
                else:
                    notes.append("Logistic 回归拟合失败（可能存在完全分离）")
        else:
            notes.append(f"{binary_outcome} 不是二分类变量，跳过 Logistic 回归")
    elif dependent:
        notes.append("未指定二分类结局，跳过 Logistic 回归（config.regression.binary_outcome）")

    if verbose:
        print(f"  相关与回归：相关矩阵 {corr.shape[0]}×{corr.shape[1]}，"
              f"线性回归 {len(linear)} 项，Logistic {len(logistic)} 项")
        for n in notes:
            print(f"    ! {n}")

    return {
        "correlation": corr,
        "linear": linear,
        "logistic": logistic,
        "vif": vif,
        "notes": notes,
    }
