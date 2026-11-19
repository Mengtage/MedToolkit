#!/usr/bin/env python3
# ============================================
# Rubin's rules 结果合并模块
#
# 对应 SAP 第 3/6/14 节：各插补数据集分别分析，结果按 Rubin's rules 合并；
# 区间估计采用 Barnard–Rubin 调整自由度（小 m 时更保守、更准确）。
#
# 提供两类接口：
#   - pool_scalar: 单个估计值（如组间差值）
#   - pool_params: 完整参数向量 + 协方差矩阵（如回归系数），支持 Wald 检验
# ============================================

from __future__ import annotations

import numpy as np
from scipy import stats


def _barnard_rubin_df(q_bar, u_bar, b, m, df_complete):
    """Barnard–Rubin 调整自由度（标量情形）。

    df_old = (m-1) / r^2,  r = (1+1/m)B / U
    df_obs = (df_complete+1)/(df_complete+3) * df_complete * (1 - r)
    df     = df_old * df_obs / (df_old + df_obs)
    """
    if m <= 1 or u_bar <= 0:
        return float(df_complete) if df_complete else np.inf

    r = (1 + 1 / m) * b / u_bar
    if r <= 0:
        return float(df_complete) if df_complete else np.inf

    df_old = (m - 1) / (r ** 2)
    if not df_complete or not np.isfinite(df_complete):
        return float(df_old)
    lam = (df_complete + 1) / (df_complete + 3)
    df_obs = df_complete * (1 - r) * lam
    if df_obs <= 0:
        return float(df_old)
    return float(df_old * df_obs / (df_old + df_obs))


def pool_scalar(estimates, variances, df_complete=None, alpha: float = 0.05) -> dict:
    """合并单个估计值（Rubin's rules）。

    Args:
        estimates: 各插补数据集的点估计列表
        variances: 对应的方差列表（标准误的平方）
        df_complete: 完整数据自由度（如 n - k）；None 时使用大样本近似
        alpha: 显著性水平（双侧）

    Returns:
        dict: estimate / se / ci_lower / ci_upper / p_value / df /
              within_var / between_var / total_var / n_imputations
    """
    estimates = np.asarray(estimates, dtype=float)
    variances = np.asarray(variances, dtype=float)
    if estimates.size == 0:
        raise ValueError("没有可合并的估计值")

    m = estimates.size
    q_bar = float(np.mean(estimates))
    u_bar = float(np.mean(variances))
    b = float(np.var(estimates, ddof=1)) if m > 1 else 0.0
    t_var = u_bar + (1 + 1 / m) * b

    df = _barnard_rubin_df(q_bar, u_bar, b, m, df_complete)
    se = float(np.sqrt(max(t_var, 1e-16)))

    if np.isfinite(df) and df > 0:
        crit = float(stats.t.ppf(1 - alpha / 2, df))
        p = float(2 * stats.t.sf(abs(q_bar / se), df))
    else:  # 大样本正态近似
        crit = float(stats.norm.ppf(1 - alpha / 2))
        p = float(2 * stats.norm.sf(abs(q_bar / se)))

    return {
        "estimate": q_bar,
        "se": se,
        "ci_lower": q_bar - crit * se,
        "ci_upper": q_bar + crit * se,
        "p_value": p,
        "df": df,
        "within_var": u_bar,
        "between_var": b,
        "total_var": t_var,
        "n_imputations": m,
    }


def pool_params(params_list, cov_list, df_complete=None) -> tuple[np.ndarray, np.ndarray]:
    """合并完整参数向量与协方差矩阵（Rubin's rules，逐元素）。

    Args:
        params_list: m 个一维参数向量
        cov_list: m 个协方差矩阵
        df_complete: 完整数据自由度（用于记录，不参与矩阵合并）

    Returns:
        (q_bar, t_cov): 合并后的参数向量与总协方差矩阵
    """
    qs = [np.asarray(p, dtype=float) for p in params_list]
    us = [np.asarray(c, dtype=float) for c in cov_list]
    if not qs:
        raise ValueError("没有可合并的参数向量")

    m = len(qs)
    q_bar = np.mean(qs, axis=0)
    u_bar = np.mean(us, axis=0)
    if m > 1:
        b = np.var(np.vstack(qs), axis=0, ddof=1)
    else:
        b = np.zeros_like(u_bar)
    t_cov = u_bar + (1 + 1 / m) * b
    return q_bar, t_cov


def wald_test(q: np.ndarray, cov: np.ndarray, idx: list[int]) -> tuple[float, float]:
    """对参数子集做 Wald 卡方检验（用于多臂总体检验）。

    Returns:
        (chi2_stat, p_value)
    """
    idx = list(idx)
    if not idx:
        return np.nan, np.nan
    beta = q[idx]
    v = cov[np.ix_(idx, idx)]
    stat = float(beta @ np.linalg.pinv(v) @ beta)
    return stat, float(stats.chi2.sf(stat, len(idx)))


def contrast(q: np.ndarray, cov: np.ndarray, vec: np.ndarray, df_complete=None) -> dict:
    """线性对比的合并估计（用于"臂 vs 参照"差值）。

    Args:
        q: 合并后参数向量
        cov: 合并后协方差矩阵
        vec: 对比向量（如 arm_A = 1, arm_B = -1）
        df_complete: 完整数据自由度（t 分布临界值；None 用正态近似）
    """
    est = float(vec @ q)
    var = float(vec @ cov @ vec)
    se = float(np.sqrt(max(var, 1e-16)))

    if df_complete and np.isfinite(df_complete) and df_complete > 0:
        p = float(2 * stats.t.sf(abs(est / se), df_complete))
        crit = float(stats.t.ppf(0.975, df_complete))
    else:
        p = float(2 * stats.norm.sf(abs(est / se)))
        crit = float(stats.norm.ppf(0.975))

    return {
        "estimate": est,
        "se": se,
        "ci_lower": est - crit * se,
        "ci_upper": est + crit * se,
        "p_value": p,
    }
