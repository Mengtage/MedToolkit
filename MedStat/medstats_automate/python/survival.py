#!/usr/bin/env python3
# ============================================
# 生存分析模块
#
# 对应 SAP（statistical_analysis_methods.md）中的时间-事件结局分析：
#   - Kaplan-Meier 中位生存时间及 95% CI（Greenwood 方差，lifelines 实现）
#   - log-rank 检验：多臂总体 + 两两比较（Holm 校正）
#   - Cox 比例风险模型：各臂 vs 参照臂的 HR（95% CI），可纳入协变量
#   - 多套插补数据集按 Rubin's rules 合并（在 log HR 尺度合并，再取 exp）
#   - 比例风险（PH）假设检验：Schoenfeld 残差，PH 不成立时 HR 不可直接解释
#
# 设计原则（相对参考实现加固）：
#   1. 事件编码与时间取值做前置校验，避免"3=死亡"被当成连续变量
#   2. EPV（events per variable）< 10 时告警，提示过拟合风险
#   3. PH 假设逐变量检验，违反者明确标注
#   4. 合并只在 log HR 尺度进行，不在 HR 尺度平均
# ============================================

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

try:
    from lifelines import CoxPHFitter, KaplanMeierFitter
    from lifelines.statistics import logrank_test, multivariate_logrank_test, proportional_hazard_test
    HAS_LIFELINES = True
except ImportError:  # pragma: no cover
    HAS_LIFELINES = False

from rubin import pool_params


def _fmt_p(p, threshold: float = 0.001) -> str:
    if p is None or not np.isfinite(p):
        return ""
    if p < threshold:
        return f"<{threshold}"
    return f"{p:.3f}"


def _validate_survival_input(
    data: pd.DataFrame,
    time_var: str,
    event_var: str,
    event_coding,
) -> tuple[pd.DataFrame, list[str]]:
    """校验时间与事件变量，返回清洗后的数据与警告列表。

    生存分析最常见的错误是事件编码被误解（如 1=存活、2=死亡，
    或 0=事件、1=删失），这类错误不会报错，只会静默算出相反的结果。
    因此在分析前强制约定：事件变量取值必须是 0/1，或显式给出事件编码。
    """
    warnings: list[str] = []
    for col in (time_var, event_var):
        if col not in data.columns:
            raise ValueError(f"生存分析变量不存在：{col}")

    df = data.copy()
    n0 = len(df)

    # ---- 事件变量 ----
    ev_raw = df[event_var]
    if ev_raw.isna().any():
        n_na = int(ev_raw.isna().sum())
        warnings.append(f"事件变量 {event_var} 有 {n_na} 行缺失，已剔除")
        df = df.loc[ev_raw.notna()].copy()

    uniq = sorted(pd.unique(df[event_var].dropna()))
    vals = set(uniq)
    coding = set(event_coding or [1])
    if vals <= {0, 1}:
        pass
    elif vals <= coding | {0}:
        # 例如 1/2 编码且已声明 [2] 为事件
        df[event_var] = df[event_var].isin(coding).astype(int)
        warnings.append(
            f"事件变量 {event_var} 取值 {uniq} 已按事件编码 {sorted(coding)} 映射为 0/1"
        )
    elif len(vals) == 2 and len(vals & coding) == 1:
        # 常见的"1=存活 / 2=死亡"：恰好一个取值被声明为事件，另一个视为未发生事件
        other = sorted(vals - coding)[0]
        df[event_var] = df[event_var].isin(coding).astype(int)
        warnings.append(
            f"事件变量 {event_var} 取值 {uniq} 中仅 {sorted(coding)} 视为事件，"
            f"{other} 按未发生事件处理（如编码含义相反，请改 event_coding）"
        )
    else:
        raise ValueError(
            f"事件变量 {event_var} 的取值 {uniq} 无法识别为 0/1 事件指示。"
            f"请用 event_coding 显式声明哪些取值代表'发生事件'（如 [1] 或 [2]）。"
        )

    # ---- 时间变量 ----
    df[time_var] = pd.to_numeric(df[time_var], errors="coerce")
    bad_time = df[time_var].isna() | (df[time_var] <= 0)
    if bad_time.any():
        warnings.append(
            f"时间变量 {time_var} 有 {int(bad_time.sum())} 行缺失或 ≤0，已剔除"
        )
        df = df.loc[~bad_time].copy()

    if len(df) == 0:
        raise ValueError("生存分析可用样本为 0，请检查时间/事件变量定义")
    if len(df) < n0:
        warnings.append(f"样本量 {n0} → {len(df)}（剔除 {n0 - len(df)} 行）")

    n_event = int(df[event_var].sum())
    if n_event == 0:
        warnings.append("未观察到任何事件，仅能报告随访时间分布，无法估计生存曲线")
    elif n_event < 10:
        warnings.append(f"事件数仅 {n_event}，生存估计不稳定，结果仅供探索")

    return df, warnings


def _km_summary(kmf: KaplanMeierFitter, t_max: float) -> dict:
    """提取 KM 中位时间及 95% CI、各时点生存率。"""
    med = kmf.median_survival_time_
    ci = kmf.confidence_interval_survival_function_
    lo_t = hi_t = np.nan
    if len(ci):
        # lifelines 的列序为 [S(t) lower, S(t) upper]。
        # 中位时间的下界：生存率下界曲线首次跌破 0.5 的时点；
        # 中位时间的上界：生存率上界曲线首次跌破 0.5 的时点。
        lower_s = ci.iloc[:, 0]
        upper_s = ci.iloc[:, 1]
        cross_low = lower_s[lower_s <= 0.5]
        cross_high = upper_s[upper_s <= 0.5]
        if len(cross_low):
            lo_t = float(cross_low.index[0])
        if len(cross_high):
            hi_t = float(cross_high.index[0])

    reached = np.isfinite(med) and med <= t_max
    return {
        "median": float(med) if np.isfinite(med) else np.nan,
        "median_ci_low": lo_t,
        "median_ci_high": hi_t,
        "median_reached": bool(reached),
    }


def _median_text(s: dict) -> str:
    """格式化中位时间。CI 上界未达到时按惯例写作 NR（not reached）。"""
    if not (s["median_reached"] and np.isfinite(s["median_ci_low"])):
        return "Not reached"
    hi = f"{s['median_ci_high']:.1f}" if np.isfinite(s["median_ci_high"]) else "NR"
    return f"{s['median']:.1f} ({s['median_ci_low']:.1f} to {hi})"


def survival_analysis(
    datasets: list[pd.DataFrame],
    time_var: str,
    event_var: str,
    group_var: str | None = None,
    covariates: list[str] | None = None,
    event_coding=(1,),
    time_unit: str = "weeks",
    alpha: float = 0.05,
    correction: str = "holm",
    reference_arm=None,
    verbose: bool = True,
) -> dict:
    """时间-事件结局分析。

    Args:
        datasets: 数据集列表。第一套用于 KM 曲线与 log-rank；
            全部数据集用于 Cox 模型并按 Rubin's rules 合并
            （单套时等价于普通 Cox）。
        time_var: 随访时间列名。
        event_var: 事件指示列名（1=事件，0=删失）。
        group_var: 分组变量（治疗臂）。为 None 时只做单组 KM。
        covariates: Cox 模型协变量（不含分组）。
        event_coding: 事件取值的原始编码，如原始数据 1=存活/2=死亡 则传 [2]。
        time_unit: 时间单位，仅用于表头展示。
        alpha: 显著性水平。
        correction: 两两 log-rank 的多重比较校正方法（holm/bonferroni/BH）。
        reference_arm: 参照臂，默认取分组变量排序后第一个。
        verbose: 是否打印摘要。

    Returns:
        dict，键包括：
            table        — 可直接写入论文的生存分析表（DataFrame）
            overall_p    — 总体 log-rank P
            pairwise     — 两两 log-rank 结果（含校正 P）
            cox          — 合并后的 Cox 结果（HR / 95% CI / P）
            ph_test      — 比例风险假设检验
            km           — 各臂 KM 曲线数据（供绘图）
            warnings     — 数据校验与统计诊断告警
            n_used       — 实际纳入样本量
            events_total — 事件总数
    """
    if not HAS_LIFELINES:
        raise ImportError(
            "生存分析需要 lifelines：pip install lifelines（requirements.txt 已列）"
        )
    if not datasets:
        raise ValueError("datasets 为空")

    warnings: list[str] = []
    d0, w = _validate_survival_input(datasets[0], time_var, event_var, event_coding)
    warnings.extend(w)
    t_max = float(d0[time_var].max())

    covars = [c for c in (covariates or []) if c and c in d0.columns]
    dropped_cov = [c for c in (covariates or []) if c and c not in d0.columns]
    if dropped_cov:
        warnings.append(f"协变量不存在，已忽略：{dropped_cov}")

    # ---------------- 单组（无分组变量） ----------------
    if not group_var or group_var not in d0.columns:
        kmf = KaplanMeierFitter()
        kmf.fit(d0[time_var], d0[event_var])
        s = _km_summary(kmf, t_max)
        med_txt = _median_text(s)
        table = pd.DataFrame(
            [{
                "Group": "All",
                "n": len(d0),
                "Events, n (%)": f"{int(d0[event_var].sum())} ({d0[event_var].mean() * 100:.1f}%)",
                f"Median time (95% CI), {time_unit}": med_txt,
            }]
        )
        return {
            "table": table,
            "overall_p": np.nan,
            "pairwise": pd.DataFrame(),
            "cox": pd.DataFrame(),
            "ph_test": pd.DataFrame(),
            "km": {"All": {
                "timeline": kmf.survival_function_.index.to_numpy(),
                "survival": kmf.survival_function_.iloc[:, 0].to_numpy(),
                "ci_low": kmf.confidence_interval_.iloc[:, 0].to_numpy(),
                "ci_high": kmf.confidence_interval_.iloc[:, 1].to_numpy(),
            }},
            "warnings": warnings,
            "n_used": len(d0),
            "events_total": int(d0[event_var].sum()),
        }

    # ---------------- 分组生存 ----------------
    arms = [a for a in pd.unique(d0[group_var]) if pd.notna(a)]
    try:
        arms = sorted(arms)
    except TypeError:
        arms = list(arms)
    ref = reference_arm if reference_arm in arms else arms[0]

    if len(arms) < 2:
        warnings.append(f"分组变量 {group_var} 只有 1 个水平，无法做组间比较")

    # 总体 log-rank
    if len(arms) >= 3:
        overall_p = float(
            multivariate_logrank_test(d0[time_var], d0[group_var], d0[event_var]).p_value
        )
    elif len(arms) == 2:
        a0, a1 = arms
        overall_p = float(
            logrank_test(
                d0.loc[d0[group_var] == a0, time_var],
                d0.loc[d0[group_var] == a1, time_var],
                d0.loc[d0[group_var] == a0, event_var],
                d0.loc[d0[group_var] == a1, event_var],
            ).p_value
        )
    else:
        overall_p = np.nan

    # 两两 log-rank
    pair_rows = []
    pairs = [(a, b) for i, a in enumerate(arms) for b in arms[i + 1:]]
    raw_ps = []
    for a, b in pairs:
        da = d0.loc[d0[group_var] == a]
        db = d0.loc[d0[group_var] == b]
        lr = logrank_test(da[time_var], db[time_var], da[event_var], db[event_var])
        raw_ps.append(float(lr.p_value))
        pair_rows.append({"comparison": f"{b} vs {a}", "p_raw": float(lr.p_value)})

    if raw_ps:
        try:
            from statsmodels.stats.multitest import multipletests
            adj = multipletests(raw_ps, alpha=alpha, method=correction)[1]
        except Exception:
            adj = np.minimum(np.array(raw_ps) * len(raw_ps), 1.0)
        for row, pa in zip(pair_rows, adj):
            row["p_adjusted"] = float(pa)
    pairwise = pd.DataFrame(pair_rows)

    # ---------------- Cox（多套插补合并） ----------------
    cox_df = pd.DataFrame()
    ph_df = pd.DataFrame()
    cox_terms: list[str] = []

    formula_parts = [f"C({group_var})"] + covars
    formula = " + ".join(formula_parts)

    q_list, u_list, names = [], [], None
    ph_pvalues: dict[str, list[float]] = {}
    n_used_cox = 0

    for ds in datasets:
        dd, _w = _validate_survival_input(ds, time_var, event_var, event_coding)
        need = [time_var, event_var, group_var] + covars
        dd = dd.dropna(subset=[c for c in need if c in dd.columns])
        if len(dd) < 10:
            continue
        try:
            cph = CoxPHFitter()
            cph.fit(dd[[c for c in need if c in dd.columns]],
                    duration_col=time_var, event_col=event_var, formula=formula)
        except Exception as exc:  # 单一数据集拟合失败不阻断整体
            warnings.append(f"某套数据 Cox 拟合失败，已跳过：{type(exc).__name__}: {exc}")
            continue

        params = cph.params_
        names = list(params.index)
        q_list.append(params.to_numpy(dtype=float))
        u_list.append(cph.variance_matrix_.loc[names, names].to_numpy(dtype=float))
        n_used_cox = len(dd)

        # PH 假设检验（Schoenfeld 残差）
        try:
            ph = proportional_hazard_test(cph, dd, time_transform="rank")
            for term, row in ph.summary.iterrows():
                ph_pvalues.setdefault(term, []).append(float(row["p"]))
        except Exception:
            pass

    if q_list:
        q_bar, t_cov = pool_params(q_list, u_list)
        rows = []
        for i, term in enumerate(names):
            est, se = float(q_bar[i]), float(np.sqrt(t_cov[i, i]))
            rows.append({
                "term": term,
                "HR": float(np.exp(est)),
                "CI_low": float(np.exp(est - 1.96 * se)),
                "CI_high": float(np.exp(est + 1.96 * se)),
                "p": float(2 * stats.norm.sf(abs(est / se))),
            })
        cox_df = pd.DataFrame(rows)

        # EPV：事件数 / 参数个数
        events = int(d0[event_var].sum())
        n_par = len(names)
        if n_par and events / n_par < 10:
            warnings.append(
                f"EPV = {events}/{n_par} = {events / n_par:.1f} < 10，"
                f"Cox 模型存在过拟合风险，HR 估计不稳定"
            )

        if ph_pvalues:
            ph_rows = []
            for term, ps in ph_pvalues.items():
                p_med = float(np.median(ps))
                ph_rows.append({
                    "term": term,
                    "p": p_med,
                    "violated": p_med < alpha,
                })
            ph_df = pd.DataFrame(ph_rows)
            viol = [r["term"] for r in ph_rows if r["violated"]]
            if viol:
                warnings.append(
                    f"比例风险假设不成立（P<{alpha}）：{viol}。"
                    f"此时 HR 只能解释为随访期内的平均效应，建议改用 RMST 或时依系数模型"
                )
    else:
        warnings.append("Cox 模型未能拟合，未输出 HR")

    # ---------------- 组装表格 ----------------
    km_data: dict[str, dict] = {}
    rows = []
    for k, a in enumerate(arms):
        da = d0.loc[d0[group_var] == a]
        if da[event_var].sum() == 0:
            warnings.append(f"臂 {a} 无事件，中位时间与 HR 无法估计")

        kmf = KaplanMeierFitter()
        kmf.fit(da[time_var], da[event_var], label=str(a))
        s = _km_summary(kmf, t_max)
        km_data[str(a)] = {
            "timeline": kmf.survival_function_.index.to_numpy(),
            "survival": kmf.survival_function_.iloc[:, 0].to_numpy(),
            "ci_low": kmf.confidence_interval_.iloc[:, 0].to_numpy(),
            "ci_high": kmf.confidence_interval_.iloc[:, 1].to_numpy(),
        }

        med_txt = _median_text(s)

        hr_txt, p_txt = "Reference", ""
        if a != ref and len(cox_df):
            wanted = f"C({group_var})[T.{a}]"
            hit = cox_df.loc[cox_df["term"] == wanted]
            if len(hit):
                r = hit.iloc[0]
                hr_txt = f"{r['HR']:.2f} ({r['CI_low']:.2f} to {r['CI_high']:.2f})"
                p_txt = _fmt_p(r["p"])

        rows.append({
            "Arm": str(a),
            "n": len(da),
            "Events, n (%)": f"{int(da[event_var].sum())} ({da[event_var].mean() * 100:.1f}%)",
            f"Median time (95% CI), {time_unit}": med_txt,
            "Log-rank P": _fmt_p(overall_p) if k == 0 else "",
            "Cox HR (95% CI)": hr_txt,
            "Cox P": p_txt,
        })

    table = pd.DataFrame(rows)

    if verbose:
        print(f"  生存分析：n={len(d0)}，事件 {int(d0[event_var].sum())}，"
              f"{len(arms)} 臂，总体 log-rank P={_fmt_p(overall_p) or 'NA'}")
        if len(cox_df):
            for _, r in cox_df.iterrows():
                if r["term"].startswith(f"C({group_var})"):
                    print(f"    {r['term']}: HR {r['HR']:.2f} "
                          f"({r['CI_low']:.2f}-{r['CI_high']:.2f}), P={_fmt_p(r['p'])}")
        for w_ in warnings:
            print(f"    ! {w_}")

    return {
        "table": table,
        "overall_p": overall_p,
        "pairwise": pairwise,
        "cox": cox_df,
        "ph_test": ph_df,
        "km": km_data,
        "warnings": warnings,
        "n_used": len(d0),
        "events_total": int(d0[event_var].sum()),
    }
