> 最新插补验收：63项基础/HTTP＋58项统计检查通过。详见IMPUTATION_ACCEPTANCE_20261120.md。以下含历史记录。

> 最新GLM验收：57项基础/HTTP＋58项统计检查通过。详见GLM_ACCEPTANCE_20261120.md。以下含历史记录。

> 最新：基础预测评估已接入；52项基础/HTTP＋58项统计检查通过。详见EVALUATION_ACCEPTANCE_20261120.md。以下含历史记录。

> 最新：OLS/Logistic已接入，旧Logistic概率接口已修复；46项基础/HTTP＋58项统计检查通过。详见REGRESSION_ADAPTER_ACCEPTANCE_20261120.md。以下含历史记录。

> 最新：TableOne已接入；40项基础/HTTP＋58项统计检查通过。详见TABLEONE_ACCEPTANCE_20261120.md。以下包含历史记录。

> 最新：数值组间比较已接入；34项基础/HTTP＋58项统计检查通过。详见GROUPS_ACCEPTANCE_20261120.md。

> 最新接续：已接入列联表检验；27项基础/HTTP＋58项统计检查通过。详见CATEGORICAL_ACCEPTANCE_20261120.md。以下含历史记录。

> 2026-11-20 更新：已核对并同步 GitHub `d3486d0` 审核版；当前20项基础/HTTP测试及58项统计检查通过。详见 [接续验收](CONTINUATION_20261120.md)。以下保留此前版本记录。

# 修复后统计验收汇总

基础工作台15项回归、统计58项固定合成数据检查全部通过。原41项中的20个失败场景已处理，并新增边界检查；未支持的统计情形通过明确拒绝处理，不冒充方法实现。旧结果保存在baseline/。

| 范围 | 通过 | 失败 | 报告 |
|---|---:|---:|---|
| 相关、组间、分类、TableOne | 23 | 0 | acceptance-groups.md |
| 回归与预测评估 | 14 | 0 | acceptance-regression.md |
| 缺失数据、插补与合并 | 21 | 0 | acceptance-missing.md |

修复了MH条件检验和合并区间、同质性检验、真实RxC Monte Carlo、森林图、样本SD及百分比分母、预测概率与校准边界、分类公式矩阵、缺失掩码、Rubin合并与有限样本自由度。详见各组报告及源文件哈希记录validation-summary.json。

支持范围收紧：分类/离散缺失暂不插补；linear/ridge仅允许单次插补；全缺失列明确拒绝；单份或无缺失数据不产生多重插补推断。实际Web路由函数已以合成请求执行，未启动旧WebApp做完整HTTP或临床验收。

本次没有调用Gemini，没有使用真实病例。固定样例通过不等于全部统计方法或参数范围已验证；HL、NRI、DCA等未覆盖项仍见各组报告。统一工作台入口仍只开放已接通的相关性计算，其他已修正模块尚待逐项迁移。

运行全部验证：`.venv/bin/python scripts/validate.py`。任一套件非零退出、缺失报告或含FAIL/BLOCKED，整包验证均失败。
