# 相关性、组间比较、分类检验与TableOne验收

固定合成数据共 19 项：PASS 9，FAIL 10，BLOCKED 0。未修改原模块；所有发现待决定后修复。

独立性说明：相关系数、Welch统计量、ANOVA、Cohen d、2×2 Fisher采用直接公式/组合枚举；MH使用条件独立与同质性构造反例。未把调用同一SciPy函数视为独立验证。未做临床数据验证；PASS只覆盖所列样例。

| 检查 | 结果 | 基准/判据 |
|---|---|---|
| Pearson非平凡相关系数 | PASS | 独立中心化乘积公式；不独立验证p值 |
| Spearman无并列秩 | PASS | 独立秩差平方公式 |
| 相关性成对缺失剔除 | PASS | 固定3对完全线性观测 |
| 相关性常量列 | FAIL | 零方差导致相关性未定义 |
| 相关性未知方法 | FAIL | 输入契约 |
| Welch统计量 | PASS | 独立均值、样本方差、标准误公式 |
| Mann-Whitney完全分离小样本 | PASS | 所有20种秩分配，两端各一种 |
| Cohen d | PASS | 两组样本SD均1，均值差-3 |
| 单因素ANOVA | PASS | 手算组间/组内平方和 |
| 分类变量某组全缺失 | FAIL | 缺失数据边界 |
| Pearson列联表卡方 | PASS | 独立期望频数与平方残差公式 |
| 2×2 Fisher精确P值 | PASS | 独立超几何组合枚举 |
| 稀疏RxC方法名称与执行一致 | FAIL | 静态调用核对 + 数值返回，不宣称精确P值独立基准 |
| MH分层检验抵抗混杂 | FAIL | 每层独立性构造；层内a-Ea=0 |
| 同质层的同质性检验 | FAIL | 完全相同列联表，共同比值比恰与层比值比一致 |
| MH区间随信息增加 | FAIL | 独立复制样本的信息量单调性 |
| 森林图上下误差方向 | FAIL | 已给定中心4、区间[2,8]的绘图代数 |
| TableOne样本SD | FAIL | [1,2,3]样本方差=1；GroupAnalyzer同变量采用ddof=1 |
| TableOne分类百分比分母一致性 | FAIL | 单层/无分层不变性 |

## 未通过项具体证据

### 相关性常量列

预期：明确拒绝或结构化不可估计，不能返回NaN数值

实际：```{"coefficient": "nan", "p_value": "nan", "n": 4}```

### 相关性未知方法

预期：拒绝未知方法，不能静默运行Spearman

实际：```{"correlation_matrix": {"x": {"x": 1.0, "y": 0.5}, "y": {"x": 0.5, "y": 1.0}}, "p_value_matrix": {"x": {"x": 1.0, "y": 0.6666666666666666}, "y": {"x": 0.6666666666666666, "y": 1.0}}, "method": "unsupported", "variables": ["x", "y"]}```

### 分类变量某组全缺失

预期：可处理的结构化结果或明确拒绝

实际：```"KeyError: 'b'"```

### 稀疏RxC方法名称与执行一致

预期：{'not_acceptable': 'Fisher/Monte Carlo标签实际调用chi2_contingency；此处不提供Fisher基准值'}

实际：```{"method": "Fisher精确检验(Monte Carlo模拟)", "statistic": 3.0, "statistic_name": "χ²", "p_value": 0.5578254003710748, "expected": [[0.6666666666666666, 0.6666666666666666, 0.6666666666666666], [0.6666666666666666, 0.6666666666666666, 0.6666666666666666], [0.6666666666666666, 0.6666666666666666, 0.6666666666666666]], "min_expected": 0.6666666666666666, "reason": "R×C表，期望频数条件不满足卡方检验", "recommended": true}```

### MH分层检验抵抗混杂

预期：{'MH_conditional_score': 0, 'pooled_OR': 1, 'explanation': '各层a恰等于独立性期望；无连续性修正的条件得分为0'}

实际：```{"method": "Mantel-Haenszel分层分析", "strata": [{"stratum": 0, "a": 9, "b": 81, "c": 1, "d": 9, "or": 1.0, "total": 100}, {"stratum": 1, "a": 9, "b": 1, "c": 81, "d": 9, "or": 1.0, "total": 100}], "pooled_or": 1.0, "pooled_or_ci": [0.0459690802796592, 21.75375260754322], "mh_statistic": 81.9072005, "mh_p_value": 1.42628724991688e-19, "homogeneity_statistic": 0.0, "homogeneity_p": 1.0, "has_heterogeneity": false, "n_strata": 2}```

### 同质层的同质性检验

预期：{'Breslow_Day_statistic': 0, 'common_OR': 4}

实际：```{"method": "Mantel-Haenszel分层分析", "strata": [{"stratum": 0, "a": 20, "b": 10, "c": 10, "d": 20, "or": 4.0, "total": 60}, {"stratum": 1, "a": 20, "b": 10, "c": 10, "d": 20, "or": 4.0, "total": 60}], "pooled_or": 4.0, "pooled_or_ci": [0.8764398404042836, 18.255673991975907], "mh_statistic": 13.322224537037037, "mh_p_value": 0.0002622788361300638, "homogeneity_statistic": 13.333333333333334, "homogeneity_p": 0.0002607296328553165, "has_heterogeneity": true, "n_strata": 2}```

### MH区间随信息增加

预期：增加独立同分布层后区间应变窄，而非变宽

实际：```{"one": [1.3672178038905072, 11.702597753240894], "two": [0.8764398404042836, 18.255673991975907], "logwidth_ratio": 1.414213562373095}```

### 森林图上下误差方向

预期：{'array': [4], 'arrayminus': [2]}

实际：```{"type": "data", "symmetric": false, "array": [2], "arrayminus": [4]}```

### TableOne样本SD

预期：{'sample_sd': 1, 'population_sd': 0.816496580927726}

实际：```{"variable": "v", "group": "Overall", "type": "numeric", "n": 3, "mean": 2.0, "sd": 0.816496580927726, "median": 2.0, "q25": 1.5, "q75": 2.5, "display": "2.00 (0.82)"}```

### TableOne分类百分比分母一致性

预期：同一份数据仅增加单一分层，不应静默切换分母；两种口径须显式说明

实际：```{"unstratified_yes_pct": 50.0, "single_group_yes_pct": 66.7}```

## 判断与待确认项

- 正常有限输入下基础Pearson/Spearman、Welch统计量、Mann–Whitney小样本、Cohen d、ANOVA及2×2 Fisher所列样例通过。不能由此推出全部统计模块验收通过。
- 分类RxC“Fisher/Monte Carlo”分支实际返回Pearson近似P值，方法标签与执行不符，应阻止作为精确检验报告。
- MH检验使用合并总频数而非分层条件得分；同质性检验以OR=1独立性期望代替共同OR期望；区间对层方差直接求和，更多独立层反而变宽；森林图误差方向颠倒且单层区间被固定设为OR×0.5/2。
- TableOne的SD采用总体分母，与同项目GroupAnalyzer的样本SD不一致；分类缺失值分母无分层/分层不一致。
- GroupAnalyzer数值两组同时返回Welch和Mann–Whitney，TableOne依总体正态性结果自动选检验且t检验默认等方差。这些是方法选择与分析计划兼容性事项，尚不自动更改。
- TableOne缺少完整效应量/置信区间及显式缺失汇总；这些为验收范围外的缺项，不应称为已满足完整科研报告要求。

执行：`.venv/bin/python tests/acceptance_groups.py`。JSON记录包含全部输入构造对应的实际返回值；失败案例不会被计作通过。

存在FAIL或BLOCKED时脚本以退出码1结束；生成报告不等同于验收通过。
