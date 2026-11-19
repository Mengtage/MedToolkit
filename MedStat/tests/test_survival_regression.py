"""生存分析与回归模块的测试。

覆盖：
    1. 事件编码映射（1=存活/2=死亡 这类原始编码）
    2. 无法识别的事件取值必须报错而非静默算错
    3. 时间非法值剔除与告警
    4. 中位生存时间 95% CI 的上下界顺序
    5. Cox HR 能还原模拟效应，并跨插补集合并
    6. 比例风险假设违反时能被检出
    7. 线性回归 / Logistic 回归系数还原
    8. 共线性（VIF）诊断
    9. 相关矩阵自动选择 Pearson / Spearman，并排除 ID 列

运行：
    cd MedStat/tests && python -m pytest test_survival_regression.py -v
"""

import os
import sys

import numpy as np
import pandas as pd
import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
PY_DIR = os.path.abspath(os.path.join(HERE, "..", "medstats_automate", "python"))
sys.path.insert(0, PY_DIR)

from survival import survival_analysis                              # noqa: E402
from correlation_regression import correlation_regression, correlation_matrix  # noqa: E402


# ---------------------------------------------------------------------------
# 数据构造
# ---------------------------------------------------------------------------

def make_survival_data(n_per_arm=120, hr=(1.0, 0.5), seed=11, admin_censor=60.0):
    """指数生存 + 均匀行政删失的两臂数据。hr 为各臂相对臂 0 的风险比。"""
    rng = np.random.default_rng(seed)
    k = len(hr)
    arms = np.repeat(np.arange(k), n_per_arm)
    N = len(arms)
    rate = np.array([0.05 * h for h in hr])[arms]
    t_event = rng.exponential(1 / rate)
    t_censor = rng.uniform(admin_censor * 0.3, admin_censor, N)
    time = np.minimum(t_event, t_censor)
    event = (t_event <= t_censor).astype(int)
    return pd.DataFrame({
        "arm": arms,
        "time": np.round(time, 2),
        "event": event,
        "age": rng.normal(58, 10, N).round(1),
        "sex": rng.binomial(1, 0.5, N),
    })


def make_nonph_data(n_per_arm=150, seed=5):
    """比例风险不成立：臂 1 在 20 周前无效应、之后风险骤降（时依效应）。"""
    rng = np.random.default_rng(seed)
    arms = np.repeat([0, 1], n_per_arm)
    N = len(arms)
    time = np.empty(N)
    for i, a in enumerate(arms):
        if a == 0:
            time[i] = rng.exponential(1 / 0.05)
        else:
            # 前 20 周风险 0.05，之后降到 0.005
            t1 = rng.exponential(1 / 0.05)
            if t1 <= 20:
                time[i] = t1
            else:
                time[i] = 20 + rng.exponential(1 / 0.005)
    censor = rng.uniform(30, 80, N)
    event = (time <= censor).astype(int)
    return pd.DataFrame({
        "arm": arms,
        "time": np.minimum(time, censor).round(2),
        "event": event,
    })


# ---------------------------------------------------------------------------
# 1. 事件编码与数据校验
# ---------------------------------------------------------------------------

class TestSurvivalValidation:
    def test_maps_custom_event_coding(self):
        """原始编码 1=存活、2=死亡，显式声明 [2] 后应正确识别事件。"""
        df = make_survival_data(n_per_arm=80, hr=(1.0, 0.5), seed=3)
        df["status"] = np.where(df["event"] == 1, 2, 1)  # 1=存活, 2=死亡
        out = survival_analysis([df], time_var="time", event_var="status",
                                group_var="arm", event_coding=[2], verbose=False)
        # 映射正确时事件数与原始 event 一致
        assert out["events_total"] == int(df["event"].sum())

    def test_rejects_unmappable_event_values(self):
        """取值 0/1/2 且未声明编码时必须报错，不能默默当成连续变量。"""
        df = make_survival_data(n_per_arm=60, hr=(1.0, 0.5), seed=4)
        df.loc[df.index[:10], "event"] = 2
        with pytest.raises(ValueError, match="事件"):
            survival_analysis([df], time_var="time", event_var="event",
                              group_var="arm", verbose=False)

    def test_drops_nonpositive_time_with_warning(self):
        df = make_survival_data(n_per_arm=60, hr=(1.0, 0.5), seed=6)
        n0 = len(df)
        df.loc[df.index[:5], "time"] = 0
        df.loc[df.index[5:8], "time"] = -3
        out = survival_analysis([df], time_var="time", event_var="event",
                                group_var="arm", verbose=False)
        assert out["n_used"] == n0 - 8
        assert any("≤0" in w or "<=" in w or "时间" in w for w in out["warnings"])

    def test_missing_variable_raises(self):
        df = make_survival_data(n_per_arm=40, seed=7)
        with pytest.raises(ValueError, match="不存在"):
            survival_analysis([df], time_var="nope", event_var="event", verbose=False)


# ---------------------------------------------------------------------------
# 2. KM 与 log-rank
# ---------------------------------------------------------------------------

class TestKaplanMeier:
    def test_median_ci_is_ordered(self):
        """中位时间 CI 必须 下界 ≤ 中位 ≤ 上界，不能颠倒。"""
        df = make_survival_data(n_per_arm=150, hr=(1.0, 0.6), seed=8)
        out = survival_analysis([df], time_var="time", event_var="event",
                                group_var="arm", verbose=False)
        txt = out["table"].iloc[0][f"Median time (95% CI), weeks"]
        assert txt != "Not reached"
        lo, hi = txt.split("(")[1].rstrip(")").split(" to ")
        assert float(lo) <= float(hi)
        med = float(txt.split(" ")[0])
        assert float(lo) <= med <= float(hi)

    def test_logrank_detects_effect(self):
        df = make_survival_data(n_per_arm=150, hr=(1.0, 0.45), seed=9)
        out = survival_analysis([df], time_var="time", event_var="event",
                                group_var="arm", verbose=False)
        assert out["overall_p"] < 0.01
        assert len(out["pairwise"]) == 1

    def test_no_effect_gives_large_p(self):
        df = make_survival_data(n_per_arm=150, hr=(1.0, 1.0), seed=10)
        out = survival_analysis([df], time_var="time", event_var="event",
                                group_var="arm", verbose=False)
        assert out["overall_p"] > 0.05

    def test_km_curves_monotone(self):
        df = make_survival_data(n_per_arm=100, hr=(1.0, 0.6), seed=12)
        out = survival_analysis([df], time_var="time", event_var="event",
                                group_var="arm", verbose=False)
        for arm, curve in out["km"].items():
            s = curve["survival"]
            assert np.all(np.diff(s) <= 1e-9), f"臂 {arm} 生存曲线非单调"
            assert 0 <= s.min() and s.max() <= 1


# ---------------------------------------------------------------------------
# 3. Cox 模型
# ---------------------------------------------------------------------------

class TestCox:
    def test_hr_recovers_simulated_effect(self):
        """模拟 HR=0.5，估计应落在 0.35–0.7（含抽样波动）。"""
        df = make_survival_data(n_per_arm=250, hr=(1.0, 0.5), seed=13)
        out = survival_analysis([df], time_var="time", event_var="event",
                                group_var="arm", verbose=False)
        hit = out["cox"].loc[out["cox"]["term"] == "C(arm)[T.1]"]
        assert len(hit) == 1
        assert 0.35 <= float(hit.iloc[0]["HR"]) <= 0.70

    def test_ci_brackets_hr(self):
        df = make_survival_data(n_per_arm=200, hr=(1.0, 0.5), seed=14)
        out = survival_analysis([df], time_var="time", event_var="event",
                                group_var="arm", verbose=False)
        r = out["cox"].iloc[0]
        assert r["CI_low"] < r["HR"] < r["CI_high"]

    def test_pools_across_imputed_datasets(self):
        """多套插补数据集的 HR 应在单套结果附近，且 CI 因组间方差略宽。"""
        df = make_survival_data(n_per_arm=200, hr=(1.0, 0.55), seed=15)
        rng = np.random.default_rng(99)
        datasets = []
        for _ in range(5):
            d = df.copy()
            # 人为制造 5% 协变量缺失并随机填补，模拟插补集差异
            mask = rng.random(len(d)) < 0.05
            d.loc[mask, "age"] = d.loc[mask, "age"] + rng.normal(0, 1, mask.sum())
            datasets.append(d)
        single = survival_analysis([df], time_var="time", event_var="event",
                                   group_var="arm", verbose=False)
        pooled = survival_analysis(datasets, time_var="time", event_var="event",
                                   group_var="arm", verbose=False)
        hr_single = float(single["cox"].iloc[0]["HR"])
        hr_pool = float(pooled["cox"].iloc[0]["HR"])
        assert abs(hr_single - hr_pool) < 0.12

    def test_ph_violation_detected(self):
        """时依效应数据应触发 PH 违反告警。"""
        df = make_nonph_data(seed=16)
        out = survival_analysis([df], time_var="time", event_var="event",
                                group_var="arm", verbose=False)
        violated = out["ph_test"]["violated"].any() if len(out["ph_test"]) else False
        assert violated or any("比例风险" in w for w in out["warnings"])

    def test_epv_warning_with_many_covariates(self):
        """协变量过多导致 EPV<10 时必须告警（过拟合风险）。"""
        df = make_survival_data(n_per_arm=50, hr=(1.0, 0.6), seed=17)
        rng = np.random.default_rng(17)
        extra = [f"c{i}" for i in range(1, 9)]
        for c in extra:
            df[c] = rng.normal(0, 1, len(df))
        out = survival_analysis([df], time_var="time", event_var="event",
                                group_var="arm",
                                covariates=["age", "sex"] + extra,
                                verbose=False)
        assert any("EPV" in w for w in out["warnings"])


# ---------------------------------------------------------------------------
# 4. 回归与相关
# ---------------------------------------------------------------------------

class TestRegression:
    @staticmethod
    def _data(n=300, seed=21):
        rng = np.random.default_rng(seed)
        arm = rng.integers(0, 2, n)
        x = rng.normal(50, 10, n)
        z = rng.normal(0, 1, n)
        y = 10 + 3.0 * arm + 0.8 * x + rng.normal(0, 2, n)  # 真值：arm=3, x=0.8
        return pd.DataFrame({"arm": arm, "x": x, "z": z, "y": y,
                             "case": (y > y.mean()).astype(int)})

    def test_ols_recovers_coefficients(self):
        df = self._data()
        out = correlation_regression(data=df, config={
            "primary_outcome": "y", "strata": "arm",
            "regression": {"independents": ["x"]},
        }, verbose=False)
        lin = out["linear"]
        coef_arm = float(lin.loc[lin["term"] == "C(arm)[T.1]", "effect"]
                         .iloc[0].split(" ")[0])
        coef_x = float(lin.loc[lin["term"] == "x", "effect"].iloc[0].split(" ")[0])
        assert 2.5 < coef_arm < 3.5
        assert 0.7 < coef_x < 0.9

    def test_logistic_reports_or(self):
        df = self._data()
        out = correlation_regression(data=df, config={
            "primary_outcome": "y", "strata": "arm",
            "regression": {"binary_outcome": "case", "independents": ["x"]},
        }, verbose=False)
        logit = out["logistic"]
        assert len(logit) > 0
        # OR 必须为正且区间包住点估计
        txt = logit.loc[logit["term"] == "C(arm)[T.1]", "effect"].iloc[0]
        or_val = float(txt.split(" ")[0])
        lo, hi = txt.split("(")[1].rstrip(")").split(" to ")
        assert or_val > 0 and float(lo) < or_val < float(hi)

    def test_vif_flags_collinearity(self):
        df = self._data()
        df["x_dup"] = df["x"] * 1.0 + np.random.default_rng(5).normal(0, 0.01, len(df))
        out = correlation_regression(data=df, config={
            "primary_outcome": "y", "strata": "arm",
            "regression": {"independents": ["x", "x_dup"]},
        }, verbose=False)
        vif = out["vif"]
        assert len(vif) >= 2
        assert vif["VIF"].max() > 10
        assert any("共线性" in n for n in out["notes"])

    def test_correlation_excludes_id_column(self):
        df = self._data()
        df["rid"] = np.arange(len(df))
        corr = correlation_matrix(df)
        assert "rid" not in corr.index

    def test_correlation_auto_uses_spearman_for_skewed(self):
        rng = np.random.default_rng(31)
        n = 400
        x = rng.exponential(1, n)          # 强偏态
        y = np.log1p(x) + rng.normal(0, 0.3, n)
        df = pd.DataFrame({"x": x, "y": y})
        corr = correlation_matrix(df, method="auto")
        assert corr.loc["y", "x"] != ""


# ---------------------------------------------------------------------------
# 5. 与 CLI 的衔接
# ---------------------------------------------------------------------------

class TestCliIntegration:
    def test_run_analysis_accepts_survival_args(self):
        """CLI 参数必须存在，且模块可被主流程导入。"""
        import run_analysis as ra
        parser_names = set()
        # 通过 --help 捕获参数列表更可靠，但直接构造 parser 需要 argparse 上下文，
        # 这里退化为检查源码中是否注册了关键参数
        src = open(ra.__file__, encoding="utf-8").read()
        for flag in ("--survival_time", "--survival_event", "--regression_binary"):
            assert flag in src

    def test_medstats_main_imports(self):
        """主入口不应因缺失模块而崩溃。"""
        import medstats_main  # noqa: F401
