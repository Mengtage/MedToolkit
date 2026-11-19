# 相关性、组间比较、分类检验与TableOne验收

固定合成数据共 23 项：PASS 23，FAIL 0，BLOCKED 0。本轮按用户授权修复原模块；原有19项反例保留并增加4项边界/数值验证。

独立性说明：相关系数、Welch统计量、ANOVA、Cohen d、2×2 Fisher采用直接公式/组合枚举；MH使用条件独立与同质性构造反例。未把调用同一SciPy函数视为独立验证。未做临床数据验证；PASS只覆盖所列样例。

| 检查 | 结果 | 基准/判据 |
|---|---|---|
| Pearson非平凡相关系数 | PASS | 独立中心化乘积公式；不独立验证p值 |
| Spearman无并列秩 | PASS | 独立秩差平方公式 |
| 相关性成对缺失剔除 | PASS | 固定3对完全线性观测 |
| 相关性常量列 | PASS | 零方差导致相关性未定义 |
| 相关性未知方法 | PASS | 输入契约 |
| Welch统计量 | PASS | 独立均值、样本方差、标准误公式 |
| Mann-Whitney完全分离小样本 | PASS | 所有20种秩分配，两端各一种 |
| Cohen d | PASS | 两组样本SD均1，均值差-3 |
| 单因素ANOVA | PASS | 手算组间/组内平方和 |
| 分类变量某组全缺失 | PASS | 缺失数据边界 |
| Pearson列联表卡方 | PASS | 独立期望频数与平方残差公式 |
| 2×2 Fisher精确P值 | PASS | 独立超几何组合枚举 |
| 稀疏RxC方法名称与执行一致 | PASS | 独立枚举固定边际全部3×3表；模拟P值按六标准误容差对照 |
| MH分层检验抵抗混杂 | PASS | 每层独立性构造；层内a-Ea=0 |
| 同质层的同质性检验 | PASS | 完全相同列联表，共同比值比恰与层比值比一致 |
| MH区间随信息增加 | PASS | 独立复制样本的信息量单调性 |
| 森林图上下误差方向 | PASS | 已给定中心4、区间[2,8]的绘图代数 |
| TableOne样本SD | PASS | [1,2,3]样本方差=1；GroupAnalyzer同变量采用ddof=1 |
| TableOne分类百分比分母一致性 | PASS | 单层/无分层不变性 |
| MH非零条件得分 | PASS | 独立分层超几何均值与方差公式 |
| 共同OR为1的同质性边界 | PASS | OR=1的Breslow-Day二次方程退化线性极限 |
| 列联表频数输入验证 | PASS | 非整数不能作为独立计数表 |
| 分层森林图采用估计区间 | PASS | 独立Woolf log-OR标准误；不使用固定倍数 |

## 未通过项具体证据

## 实现与适用边界

- 常量相关返回不可估计；未知方法拒绝。分类变量全缺失组保留有效/缺失数及不可估计百分比，不制造零百分比。
- RxC稀疏表实际调用SciPy条件Monte Carlo，19999次、固定种子，统计量是条件表概率；用独立全枚举小表检验P值偏差。
- MH条件得分和Robins–Breslow–Greenland区间采用statsmodels StratifiedTable；Breslow-Day期望使用稳定二次式，单层不输出同质性P值。零边际、无效二分类和边界OR明确拒绝。
- 森林图使用实际层区间，纠正上下误差方向；TableOne改用样本SD，分类百分比分母统一为组内非缺失样本并返回分母/缺失数。
- GroupAnalyzer仍同时返回Welch和Mann–Whitney；TableOne仍依原有方法选择逻辑。方法选择须按预先分析计划，当前并非全部方法学认证。
- 当前固定样例通过不等于全部参数范围、CI覆盖率、临床输入或所有边界均已验证。

## 方法依据

- [statsmodels StratifiedTable](https://www.statsmodels.org/stable/generated/statsmodels.stats.contingency_tables.StratifiedTable.html)：CMH、Breslow-Day与Robins/Breslow/Greenland方差；本机0.15.0源码已对照。
- [SciPy fisher_exact](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.fisher_exact.html)：RxC固定边际表概率及MonteCarloMethod；需SciPy>=1.15。

执行：`.venv/bin/python tests/acceptance_groups.py`。输入仅合成数据，无LLM调用。

存在FAIL或BLOCKED时脚本以退出码1结束；生成报告不等同于验收通过。
