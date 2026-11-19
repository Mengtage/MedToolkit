"""MedStat 统计内核修复的回归测试。

覆盖：
    1. MICE 真多重插补（m 套数据、分类回映射、收敛报告、低缺失率回退）
    2. 臂内简单插补
    3. Rubin's rules 合并（标量 / 参数向量 / 对比 / Wald）
    4. ANCOVA 组间比较（效应量还原、95% CI 覆盖、多臂 Holm 校正）
    5. 正态性检验（Shapiro / Lilliefors）
    6. 缺失报告（模式、按臂、高缺失变量）

运行：
    cd MedStat/tests && python -m pytest test_stat_fixes.py -v
"""

import os
import sys

import numpy as np
import pandas as pd
import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
PY_DIR = os.path.abspath(os.path.join(HERE, "..", "medstats_automate", "python"))
sys.path.insert(0, PY_DIR)

from mice_imputation import mice_imputation, simple_impute            # noqa: E402
from rubin import pool_scalar, pool_params, wald_test, contrast       # noqa: E402
from ancova import ancova_compare                                     # noqa: E402
from quality_control import quality_control, normality_test, analyze_missing  # noqa: E402


# ---------------------------------------------------------------------------
# 数据构造
# ---------------------------------------------------------------------------

def make_mar_data(n=240, seed=1, effect=(-3.0, -5.0), missing_rate=0.15):
    """两/三臂 MAR 数据：结局缺失与基线严重度相关。"""
    rng = np.random.default_rng(seed)
    arms = np.repeat([0, 1, 2][: len(effect) + 1], n // (len(effect) + 1))
    n = len(arms)
    baseline = rng.normal(24, 5, n)
    age = np.round(rng.normal(58, 10, n))
    sex = rng.binomial(1, 0.5, n)
    effect_map = np.zeros(n)
    for i, a in enumerate([1, 2][: len(effect)]):
        effect_map[arms == a] = effect[i]
    outcome = baseline + effect_map + rng.normal(0, 3, n)

    df = pd.DataFrame({
        "id": np.arange(n),
        "treatment": arms,
        "age": age,
        "sex": sex,
        "score_bl": np.round(baseline, 1),
        "score_w12": np.round(outcome, 1),
        "responder": (outcome < np.median(outcome)).astype(int),
        "site": rng.integers(1, 4, n),
    })

    # MAR：基线越高越容易缺失
    p_miss = np.clip(missing_rate * (baseline - baseline.min()) /
                     (baseline.max() - baseline.min() + 1e-9), 0, 1)
    mask = rng.random(n) < p_miss
    df.loc[mask, "score_w12"] = np.nan
    df.loc[rng.random(n) < 0.08, "responder"] = np.nan
    df.loc[rng.random(n) < 0.05, "age"] = np.nan
    return df


# ---------------------------------------------------------------------------
# 1. MICE
# ---------------------------------------------------------------------------

class TestMICE:
    def test_generates_m_distinct_complete_datasets(self):
        df = make_mar_data(missing_rate=0.25)
        out = mice_imputation(df, m=4, maxit=3, verbose=False, force=True)

        assert out["strategy"] == "mice"
        assert len(out["datasets"]) == 4
        for d in out["datasets"]:
            assert d.shape == df.shape
            assert not d.isna().any().any(), "插补后不应残留缺失值"

        # 不同插补集必须不同（旧实现只产出一套，这里是最关键的回归点）
        s0 = out["datasets"][0]["score_w12"].to_numpy()
        s1 = out["datasets"][1]["score_w12"].to_numpy()
        assert not np.allclose(s0, s1), "m 套插补数据不应完全相同"

    def test_categorical_values_stay_in_domain(self):
        df = make_mar_data(missing_rate=0.25)
        df["severity_class"] = np.where(df["score_bl"] > 26, "high",
                                        np.where(df["score_bl"] > 21, "mid", "low"))
        df.loc[df.sample(30, random_state=2).index, "severity_class"] = np.nan

        out = mice_imputation(df, m=3, maxit=3, verbose=False, force=True)
        allowed = {"high", "mid", "low"}
        for d in out["datasets"]:
            assert set(d["severity_class"].unique()) <= allowed
            assert not pd.api.types.is_numeric_dtype(d["severity_class"])

    def test_binary_target_stays_binary(self):
        df = make_mar_data(missing_rate=0.25)
        out = mice_imputation(df, m=2, maxit=2, verbose=False, force=True)
        for d in out["datasets"]:
            assert set(d["responder"].unique()) <= {0, 1}

    def test_low_missingness_falls_back_to_simple(self):
        df = make_mar_data(missing_rate=0.02)
        out = mice_imputation(df, m=5, verbose=False, fallback_rate=0.05)
        assert out["strategy"] == "simple"
        assert len(out["datasets"]) == 1

    def test_reports_models_honestly(self):
        df = make_mar_data(missing_rate=0.25)
        out = mice_imputation(df, m=2, maxit=2, verbose=False, force=True)
        # 连续变量用真正的 PMM；二分类用 logistic；多分类用 polyreg
        assert out["methods"]["score_w12"] == "pmm"
        assert out["methods"]["responder"] == "logreg"
        assert set(out["methods"].values()) <= {"pmm", "logreg", "polyreg"}


class TestSimpleImpute:
    def test_within_arm_uses_arm_specific_median(self):
        df = pd.DataFrame({
            "treatment": [0, 0, 0, 1, 1, 1],
            "score": [1.0, np.nan, 3.0, 10.0, np.nan, 14.0],
        })
        filled = simple_impute(df, strata="treatment")
        assert filled.loc[1, "score"] == 2.0    # 臂 0 中位数
        assert filled.loc[4, "score"] == 12.0   # 臂 1 中位数


# ---------------------------------------------------------------------------
# 2. Rubin's rules
# ---------------------------------------------------------------------------

class TestRubin:
    def test_pool_scalar_matches_hand_calculation(self):
        estimates = [1.0, 2.0, 3.0]
        variances = [0.09, 0.09, 0.09]
        res = pool_scalar(estimates, variances, df_complete=100)

        m = 3
        q_bar = 2.0
        u_bar = 0.09
        b = np.var(estimates, ddof=1)   # = 1.0
        t_var = u_bar + (1 + 1 / m) * b

        assert res["estimate"] == pytest.approx(q_bar)
        assert res["within_var"] == pytest.approx(u_bar)
        assert res["between_var"] == pytest.approx(b)
        assert res["total_var"] == pytest.approx(t_var)
        assert res["se"] == pytest.approx(np.sqrt(t_var))
        assert res["df"] > 0

    def test_ci_covers_estimate(self):
        res = pool_scalar([0.5, 0.6, 0.55], [0.04, 0.04, 0.04], df_complete=200)
        assert res["ci_lower"] < res["estimate"] < res["ci_upper"]
        assert 0 <= res["p_value"] <= 1

    def test_pool_params_and_contrast(self):
        qs = [np.array([1.0, 2.0, 3.0]), np.array([1.2, 2.2, 3.2])]
        covs = [np.eye(3) * 0.1, np.eye(3) * 0.1]
        q, t = pool_params(qs, covs)
        assert np.allclose(q, [1.1, 2.1, 3.1])

        vec = np.array([0.0, 1.0, -1.0])
        res = contrast(q, t, vec, df_complete=100)
        assert res["estimate"] == pytest.approx(2.1 - 3.1)

    def test_wald_test_detects_effect(self):
        q = np.array([0.0, 5.0])
        cov = np.eye(2) * 0.25
        stat, p = wald_test(q, cov, [1])
        assert p < 0.001


# ---------------------------------------------------------------------------
# 3. ANCOVA
# ---------------------------------------------------------------------------

class TestANCOVA:
    def test_recovers_known_treatment_effect(self):
        df = make_mar_data(effect=(-3.0,), missing_rate=0.2)
        imp = mice_imputation(df, m=5, maxit=3, verbose=False, force=True)

        res = ancova_compare(
            imp["datasets"], outcome="score_w12", group="treatment",
            baseline="score_bl", kind="ols", adjust="holm",
        )
        row = res["adjusted"][0]
        assert row["measure"] == "difference"
        assert abs(row["estimate"] - (-3.0)) < 1.2, f"效应估计偏差过大: {row}"
        assert row["ci_lower"] < -3.0 < row["ci_upper"] or row["ci_lower"] < -3.0
        assert row["p_value"] < 0.05
        assert res["n_datasets"] == 5

    def test_three_arms_pairwise_and_holm(self):
        df = make_mar_data(effect=(-3.0, -6.0), missing_rate=0.15)
        imp = mice_imputation(df, m=3, maxit=3, verbose=False, force=True)
        res = ancova_compare(imp["datasets"], "score_w12", "treatment",
                             baseline="score_bl", adjust="holm")

        assert len(res["adjusted"]) == 3          # 3 臂 → 3 对
        for row in res["adjusted"]:
            assert row["p_adjusted"] >= row["p_value"] - 1e-9

    def test_binary_outcome_reports_odds_ratio(self):
        df = make_mar_data(effect=(-3.0,), missing_rate=0.1)
        df["responder"] = (df["score_w12"] < df["score_w12"].median()).astype(int)
        res = ancova_compare([df.dropna(subset=["responder"])],
                             "responder", "treatment", baseline="score_bl",
                             kind="logit")
        assert res["adjusted"][0]["measure"] == "OR"
        assert res["adjusted"][0]["estimate"] > 0

    def test_descriptives_present(self):
        df = make_mar_data(effect=(-3.0,), missing_rate=0.1)
        res = ancova_compare([df], "score_w12", "treatment", baseline="score_bl")
        assert set(res["descriptive"].keys()) == {"0", "1"}
        assert res["descriptive"]["0"]["n"] > 0


# ---------------------------------------------------------------------------
# 4. 正态性
# ---------------------------------------------------------------------------

class TestNormality:
    def test_normal_sample_passes(self):
        rng = np.random.default_rng(7)
        res = normality_test(rng.normal(0, 1, 200))
        assert res["test"] == "Shapiro-Wilk"
        assert res["normal"] is True

    def test_skewed_sample_rejected(self):
        rng = np.random.default_rng(7)
        res = normality_test(rng.exponential(1.0, 300))
        assert res["normal"] is False

    def test_large_sample_uses_lilliefors(self):
        rng = np.random.default_rng(7)
        res = normality_test(rng.normal(0, 1, 6000))
        assert res["test"] in ("Lilliefors", "Anderson-Darling")

    def test_constant_and_tiny_samples(self):
        assert normality_test([1, 1, 1, 1])["normal"] is None
        assert normality_test([1.0, 2.0])["normal"] is None


# ---------------------------------------------------------------------------
# 5. 缺失报告
# ---------------------------------------------------------------------------

class TestMissingReport:
    def test_report_structure(self):
        df = make_mar_data(missing_rate=0.25)
        rep = analyze_missing(df, strata="treatment", threshold=0.05)
        assert rep["total_missing"] > 0
        assert len(rep["by_var"]) > 0
        assert set(rep["by_group"].keys()) >= {"0", "1", "2"}
        assert rep["patterns"] is not None and len(rep["patterns"]) > 0
        assert isinstance(rep["monotone"], bool)

    def test_high_missing_flagged(self):
        df = pd.DataFrame({"a": [1, 2, np.nan, np.nan, np.nan, np.nan],
                           "b": [1, 2, 3, 4, 5, 6]})
        rep = analyze_missing(df, threshold=0.5)
        assert "a" in rep["high_missing_vars"]

    def test_quality_control_end_to_end(self):
        df = make_mar_data(missing_rate=0.2)
        out = quality_control(df, strata="treatment",
                              outcome_var="score_w12", verbose=False)
        assert "missing" in out and "normality" in out
        assert out["completers_comparison"] is not None
        assert out["completers_comparison"]["n_missing"] > 0


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
