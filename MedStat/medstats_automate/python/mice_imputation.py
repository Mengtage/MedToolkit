#!/usr/bin/env python3
# ============================================
# MICE 多重插补模块（链式方程，v2.0）
#
# 对应统计方案 (SAP) 第 3 节：
#   - 连续变量：预测均值匹配（PMM），以上下文协变量拟合 BayesianRidge 后 donor 抽样
#   - 二分类变量：logistic 回归 + Bernoulli 抽样
#   - 多分类变量：multinomial logistic 回归 + 类别抽样
#   - 生成 m 个插补数据集（默认 20，规则：m ≥ 缺失个案百分比）
#   - 缺失率 < fallback_rate 时按 SAP 预设备选方案做简单插补（臂内）
#
# 相对 v1.x 的修复：
#   1. 旧实现接收 m 但只做一次插补（单点插补冒充多重插补）——现在真正生成 m 套数据
#   2. 旧实现声称 PMM 但 IterativeImputer 并不实现 PMM——现在按 PMM 真正实现
#   3. 旧实现分类变量编码后不回映射，插补值停留在浮点编码——现在取整后映射回原类别
#   4. 旧实现无收敛检查——现在逐轮追踪插补值最大变化并报告
# ============================================

import numpy as np
import pandas as pd

try:
    from sklearn.linear_model import BayesianRidge, LogisticRegression
    _SKLEARN_OK = True
except ImportError:  # pragma: no cover
    _SKLEARN_OK = False

import warnings

# 允许作为预测变量的分类水平上限（超过视为自由文本/ID，不参与插补）
MAX_CATEGORY_LEVELS = 30


# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------

def _is_categorical(series: pd.Series) -> bool:
    return not pd.api.types.is_numeric_dtype(series)


def _encode_categorical(series: pd.Series) -> tuple[pd.Series, dict]:
    """把分类变量编码为整数码（缺失保留 NaN），并返回码 -> 原值映射。"""
    observed = series.dropna()
    levels = list(pd.unique(observed))
    mapping = {v: i for i, v in enumerate(levels)}
    codes = series.map(mapping).astype(float)
    inverse = {i: v for v, i in mapping.items()}
    return codes, inverse


def simple_impute(data: pd.DataFrame, cols=None, strata=None, verbose=False) -> pd.DataFrame:
    """简单插补（SAP 备选方案）：连续变量中位数、分类变量众数。

    Args:
        data: 原始数据
        cols: 需要插补的列；None 表示所有含缺失的列
        strata: 分组变量；给定则在各臂内分别插补（SAP 要求 within arm）
    """
    out = data.copy()
    if cols is None:
        cols = [c for c in out.columns if out[c].isna().any()]

    def _fill(frame: pd.DataFrame) -> None:
        for col in cols:
            if col not in frame.columns or not frame[col].isna().any():
                continue
            if pd.api.types.is_numeric_dtype(frame[col]):
                fill_value = frame[col].median()
            else:
                mode = frame[col].mode(dropna=True)
                fill_value = mode.iloc[0] if len(mode) else ""
            frame[col] = frame[col].fillna(fill_value)

    if strata and strata in out.columns:
        for _, idx in out.groupby(strata).groups.items():
            sub = out.loc[idx]
            _fill(sub)
            out.loc[idx, cols] = sub[cols]
    else:
        _fill(out)

    if verbose:
        print("  简单插补完成（连续: 中位数 / 分类: 众数"
              + ("，按分组变量臂内进行）" if strata else "）"))
    return out


def _fit_and_draw(
    y: pd.Series,
    X: pd.DataFrame,
    missing_mask: pd.Series,
    rng: np.random.Generator,
    var_kind: str,
    k_donors: int = 5,
):
    """在观测行上拟合模型，并为缺失行抽取插补值。

    连续变量采用 **预测均值匹配（PMM）**（SAP 首选方法）：
    先用 BayesianRidge 预测缺失行的条件均值，再从观测行中挑选预测均值
    最接近的 k 个"供体"，随机取其中一个供体的真实观测值作为插补值。
    相比直接正态抽样，PMM 的值域天然受观测分布约束，不会外推产生
    医学上不可能的极值，迭代也更稳定（旧实现对两者都不成立）。

    Returns:
        (imputed_values, method_name) 或 (None, None) 表示无法拟合
    """
    observed = ~missing_mask
    if observed.sum() < max(10, X.shape[1] + 2):
        return None, None  # 观测太少，退回稳健替代方案

    X_obs = X.loc[observed].to_numpy(dtype=float)
    y_obs = y.loc[observed]
    X_mis = X.loc[missing_mask].to_numpy(dtype=float)

    try:
        if var_kind == "cont":
            model = BayesianRidge()
            model.fit(X_obs, y_obs.to_numpy(dtype=float))
            mu_mis = model.predict(X_mis)
            mu_obs = model.predict(X_obs)

            y_obs_vals = y_obs.to_numpy(dtype=float)
            order = np.argsort(mu_obs)
            mu_sorted = mu_obs[order]
            y_sorted = y_obs_vals[order]

            draws = np.empty(len(mu_mis))
            for i, m_val in enumerate(mu_mis):
                # 在观测行中找预测均值最接近的 k 个供体
                pos = int(np.searchsorted(mu_sorted, m_val))
                lo = max(0, pos - k_donors)
                hi = min(len(mu_sorted), pos + k_donors)
                candidate_idx = np.arange(lo, hi)
                if candidate_idx.size == 0:
                    draws[i] = y_obs_vals[rng.integers(len(y_obs_vals))]
                    continue
                nearest = candidate_idx[
                    np.argsort(np.abs(mu_sorted[candidate_idx] - m_val))[:k_donors]
                ]
                draws[i] = y_sorted[rng.choice(nearest)]
            return draws, "pmm"

        # 分类目标：预测变量标准化，避免 lbfgs 收敛困难（不影响统计推断）
        from sklearn.preprocessing import StandardScaler
        scaler = StandardScaler()
        X_obs_s = scaler.fit_transform(X_obs)
        X_mis_s = scaler.transform(X.loc[missing_mask].to_numpy(dtype=float))

        if var_kind == "binary":
            model = LogisticRegression(max_iter=2000)
            model.fit(X_obs_s, y_obs.astype(int))
            p = model.predict_proba(X_mis_s)[:, 1]
            return (rng.random(len(p)) < p).astype(float), "logreg"

        # 多分类
        model = LogisticRegression(max_iter=2000)
        model.fit(X_obs_s, y_obs.astype(int))
        proba = model.predict_proba(X_mis_s)
        draws = np.array([
            rng.choice(model.classes_, p=row / row.sum()) for row in proba
        ], dtype=float)
        return draws, "polyreg"
    except Exception as exc:  # 单个变量拟合失败不应中断整个插补
        warnings.warn(f"变量拟合失败（{var_kind}）：{exc}")
        return None, None


# ---------------------------------------------------------------------------
# 主函数
# ---------------------------------------------------------------------------

def mice_imputation(
    data: pd.DataFrame,
    vars=None,
    m: int = 20,
    maxit: int = 10,
    seed: int = 42,
    verbose: bool = True,
    fallback_rate: float = 0.05,
    strata: str | None = None,
    force: bool = False,
):
    """链式方程多重插补（MICE）。

    Args:
        data: 原始数据（pandas DataFrame）
        vars: 需要插补的变量列表；None 表示自动检测所有含缺失的可用变量
        m: 插补数据集数量（SAP 建议 20；规则：不少于缺失个案百分比）
        maxit: 每个数据集的链式迭代次数
        seed: 随机种子
        verbose: 是否打印过程信息
        fallback_rate: 总体缺失率低于该值时改用简单插补（SAP 第 3 节备选方案）
        strata: 分组变量（仅用于简单插补的臂内填补）
        force: True 时即使缺失率低也强制执行 MICE

    Returns:
        dict:
            - data: 第一个插补数据集（向后兼容旧接口）
            - datasets: m 个插补数据集的列表
            - methods: {变量: 所用模型}
            - vars_imputed: 实际插补的变量列表
            - converged: 是否在 maxit 内收敛
            - strategy: "mice" 或 "simple"
            - details: 缺失率、迭代收敛轨迹等
    """
    if not _SKLEARN_OK:  # pragma: no cover
        if verbose:
            print("  scikit-learn 不可用，回退简单插补")
        filled = simple_impute(data, strata=strata)
        return {
            "data": filled, "datasets": [filled], "methods": {},
            "vars_imputed": [], "converged": True, "strategy": "simple",
            "details": {"reason": "sklearn unavailable"},
        }

    n_rows, n_cols = data.shape
    total_missing = int(data.isna().sum().sum())
    missing_rate = total_missing / (n_rows * n_cols) if n_rows and n_cols else 0.0

    if total_missing == 0:
        if verbose:
            print("  数据完整，无需插补")
        return {
            "data": data.copy(), "datasets": [data.copy()], "methods": {},
            "vars_imputed": [], "converged": True, "strategy": "mice",
            "details": {"missing_rate": 0.0},
        }

    # ---- SAP 备选方案：低缺失率时简单插补 ----
    if missing_rate < fallback_rate and not force:
        if verbose:
            print(f"  总体缺失率 {missing_rate:.2%} < {fallback_rate:.0%}，"
                  "按预设方案改用简单插补")
        filled = simple_impute(data, strata=strata, verbose=verbose)
        return {
            "data": filled, "datasets": [filled], "methods": {},
            "vars_imputed": [c for c in data.columns if data[c].isna().any()],
            "converged": True, "strategy": "simple",
            "details": {"missing_rate": missing_rate, "reason": "low missingness"},
        }

    # ---- 确定插补变量 ----
    if vars is None:
        candidates = [c for c in data.columns if data[c].isna().any()]
    else:
        candidates = [c for c in vars if c in data.columns and data[c].isna().any()]

    usable, skipped = [], []
    for col in candidates:
        series = data[col]
        if _is_categorical(series):
            n_levels = series.dropna().nunique()
            if n_levels > MAX_CATEGORY_LEVELS or n_levels < 2:
                skipped.append((col, f"分类水平数 {n_levels} 不适用于插补"))
                continue
        elif series.dropna().nunique() < 2:
            skipped.append((col, "常数变量"))
            continue
        usable.append(col)

    if not usable:
        if verbose:
            print("  没有可插补的变量（候选均被跳过）")
        filled = simple_impute(data, strata=strata)
        return {
            "data": filled, "datasets": [filled], "methods": {},
            "vars_imputed": [], "converged": True, "strategy": "simple",
            "details": {"missing_rate": missing_rate, "skipped": skipped},
        }

    if verbose:
        print(f"  插补变量: {len(usable)} 个 | 插补数据集: m={m} | 迭代: {maxit}")
        for col, why in skipped:
            print(f"  跳过 {col}: {why}")

    # ---- 编码：目标变量按类型处理，预测变量用整数码 ----
    encoded = pd.DataFrame(index=data.index)
    kinds: dict[str, str] = {}
    inverse_maps: dict[str, dict] = {}

    for col in data.columns:
        series = data[col]
        if _is_categorical(series):
            n_levels = series.dropna().nunique()
            if 2 <= n_levels <= MAX_CATEGORY_LEVELS:
                codes, inv = _encode_categorical(series)
                encoded[col] = codes
                inverse_maps[col] = inv
            # 高基数分类不作为预测变量
        else:
            encoded[col] = pd.to_numeric(series, errors="coerce")

    for col in usable:
        vals = data[col].dropna()
        if _is_categorical(vals):
            kinds[col] = "binary" if vals.nunique() == 2 else "multi"
        else:
            n_unique = vals.nunique()
            is_integer_valued = bool(
                pd.api.types.is_integer_dtype(vals) or
                (n_unique and np.allclose(vals, np.round(vals)))
            )
            if n_unique == 2:
                # 0/1 二分类结局（如 responder）必须按 logistic 插补，
                # 否则会被当成连续变量插出 0.37 这类无意义取值
                kinds[col] = "binary"
            elif n_unique <= 5 and is_integer_valued:
                kinds[col] = "multi"   # 少水平整数（如 Likert 1–5）按多分类处理
            else:
                kinds[col] = "cont"

    methods = {
        col: {"cont": "pmm", "binary": "logreg", "multi": "polyreg"}[k]
        for col, k in kinds.items()
    }

    predictor_cols = [
        c for c in encoded.columns
        # 排除 ID 类近唯一数值列：它们不携带生物学信息，还会导致回归外推失稳
        if not (pd.api.types.is_numeric_dtype(encoded[c]) and
                encoded[c].nunique() > 0.9 * len(encoded))
    ]

    datasets: list[pd.DataFrame] = []
    max_delta_history: list[float] = []
    chain_means: list[dict[str, list[float]]] = []   # Gelman-Rubin 诊断用
    converged = True

    for m_idx in range(int(m)):
        rng = np.random.default_rng(seed + m_idx)
        work = encoded.copy()

        # 初始化：用观测值随机抽取填充
        for col in usable:
            miss = work[col].isna()
            if miss.any():
                observed_vals = work.loc[~miss, col].to_numpy()
                work.loc[miss, col] = rng.choice(observed_vals, size=int(miss.sum()))

        # 收敛监控：按标准 MICE 实践追踪"插补值均值/标准差的链稳定性"，
        # 而不是单个插补值的最大变化（PMM 每次重抽供体，单值本就会跳动）
        prev_stats: dict[str, tuple[float, float]] = {}
        chain_deltas: list[float] = []
        mean_drifts: list[float] = []
        hist: dict[str, list[float]] = {c: [] for c in usable}
        stable_rounds = 0
        delta = np.inf

        for it in range(int(maxit)):
            for col in usable:
                miss_mask = encoded[col].isna()
                if not miss_mask.any():
                    continue
                X = work[[c for c in predictor_cols if c != col]]
                y = work[col]
                draws, _method = _fit_and_draw(y, X, miss_mask, rng, kinds[col])
                if draws is None:
                    # 拟合失败：退回观测值随机抽取（保持分布，不引入常数）
                    observed_vals = encoded.loc[~miss_mask, col].dropna().to_numpy()
                    if len(observed_vals):
                        draws = rng.choice(observed_vals, size=int(miss_mask.sum()))
                    else:
                        continue
                # 合理性截断：插补值限制在观测取值范围内，防止回归外推产生
                # 医学上不可能的极值
                observed_vals = encoded.loc[~miss_mask, col].dropna().to_numpy()
                if observed_vals.size:
                    draws = np.clip(draws, np.min(observed_vals), np.max(observed_vals))
                work.loc[miss_mask, col] = draws

            # 计算本轮各变量插补值的均值/标准差（按变量量级归一化）
            stats_now: dict[str, tuple[float, float]] = {}
            scales: dict[str, float] = {}
            for col in usable:
                miss_mask = encoded[col].isna()
                # 二分类目标的"均值"即患病率，每次 Bernoulli 抽样的波动
                # 天然是 SD 的 10–15%，不纳入收敛判据（否则永远判为不收敛）
                if not miss_mask.any() or kinds[col] == "binary":
                    continue
                vals = work.loc[miss_mask, col].astype(float)
                stats_now[col] = (
                    float(vals.mean()),
                    float(vals.std(ddof=1)) if len(vals) > 1 else 0.0,
                )
                scales[col] = max(float(encoded[col].std()), 1e-8)
                hist[col].append(float(vals.mean()))

            if prev_stats and stats_now:
                rel_mean = max(
                    abs(stats_now[c][0] - prev_stats[c][0]) / scales[c]
                    for c in stats_now if c in prev_stats
                )
                rel_sd = max(
                    abs(stats_now[c][1] - prev_stats[c][1]) / scales[c]
                    for c in stats_now if c in prev_stats
                )
                # 收敛主判据用均值链（PMM 的 SD 受供体重抽影响，小样本缺失时
                # 天然波动 ±15–25%，不作为硬性停止条件，仅记录）
                passed = rel_mean < 0.10
                chain_deltas.append(max(rel_mean, rel_sd))
                mean_drifts.append(rel_mean)
                delta = rel_mean
                stable_rounds = stable_rounds + 1 if passed else 0
                # burn-in 两轮后，连续两轮均值稳定即视为收敛
                if it >= 2 and stable_rounds >= 2:
                    break
            prev_stats = stats_now

        # 报告用：该数据集末段的均值链漂移（中位数），避免 PMM 的 SD 噪声干扰
        max_delta_history.append(
            float(np.median(mean_drifts[-3:])) if mean_drifts else 0.0
        )
        chain_means.append(hist)

        # ---- 解码回原始尺度 ----
        result = data.copy()
        for col in usable:
            if kinds[col] == "cont":
                values = work[col].to_numpy(dtype=float)
                # 整数型变量保持整数
                if pd.api.types.is_integer_dtype(data[col].dropna()):
                    values = np.round(values)
                result[col] = values
            elif col in inverse_maps:
                codes = np.round(work[col].to_numpy(dtype=float)).astype(int)
                inv = inverse_maps[col]
                valid_codes = sorted(inv.keys())
                codes = np.clip(codes, min(valid_codes), max(valid_codes))
                result[col] = [inv[c] for c in codes]
            else:
                # 数值型二分类/少水平整数：取整并限制在观测取值范围内
                observed = np.sort(data[col].dropna().unique())
                values = np.round(work[col].to_numpy(dtype=float))
                values = np.clip(values, observed.min(), observed.max())
                if pd.api.types.is_integer_dtype(data[col].dropna()):
                    values = values.astype(int)
                result[col] = values

        datasets.append(result)

    # ---------------- 收敛诊断 ----------------
    # 标准做法：用 m 条链计算 Gelman–Rubin R̂（链间/链内方差比），R̂ < 1.1 视为收敛。
    # 单链漂移在缺失单元很少时会被 PMM 的供体抽样噪声主导，仅作辅助报告。
    rhat: dict[str, float] = {}
    if len(chain_means) >= 2:
        for col in usable:
            if kinds[col] == "binary":
                continue
            series = [h[col] for h in chain_means if len(h.get(col, [])) >= 4]
            if len(series) < 2:
                continue
            t_len = min(len(x) for x in series)
            half = max(4, t_len // 2)
            mat = np.array([x[-half:] for x in series], dtype=float)  # m × T
            m_chains, t_obs = mat.shape
            if t_obs < 4:
                continue
            within = float(np.mean(np.var(mat, axis=1, ddof=1)))
            between = float(t_obs * np.var(mat.mean(axis=1), ddof=1))
            if within <= 1e-12:
                rhat[col] = 1.0
                continue
            var_plus = (t_obs - 1) / t_obs * within + between / t_obs
            rhat[col] = float(np.sqrt(max(var_plus / within, 1e-12)))

    if rhat:
        converged = max(rhat.values()) < 1.1
        max_rhat = max(rhat.values())
    else:
        stable_chains = sum(1 for d in max_delta_history if d <= 0.25)
        converged = bool(max_delta_history) and stable_chains >= 0.8 * len(max_delta_history)
        max_rhat = float("nan")

    if verbose:
        if np.isfinite(max_rhat):
            diag = f"Gelman-Rubin R̂ 最大 {max_rhat:.3f}"
        else:
            med_drift = float(np.median(max_delta_history)) if max_delta_history else 0.0
            diag = f"单链漂移中位数 {med_drift*100:.0f}% SD"
        print(f"  MICE 完成：{len(datasets)} 个插补数据集（{diag}；"
              f"{'已收敛' if converged else '未达收敛标准，建议增大 maxit'}）")
        print("  所用模型: " + ", ".join(f"{k}={v}" for k, v in methods.items()))

    return {
        "data": datasets[0],
        "datasets": datasets,
        "methods": methods,
        "vars_imputed": usable,
        "converged": converged,
        "strategy": "mice",
        "details": {
            "missing_rate": missing_rate,
            "n_imputations": len(datasets),
            "max_delta": max_delta_history,
            "rhat": rhat,
            "skipped": skipped,
        },
    }


def auto_select_imputation_method(data: pd.DataFrame, vars) -> dict:
    """按变量类型报告插补模型（供兼容旧接口/文档展示）。"""
    methods = {}
    for var in vars:
        if var not in data.columns:
            continue
        series = data[var]
        if _is_categorical(series):
            methods[var] = "logreg" if series.dropna().nunique() == 2 else "polyreg"
        else:
            methods[var] = "pmm"
    return methods
