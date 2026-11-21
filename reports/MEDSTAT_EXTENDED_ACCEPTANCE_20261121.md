# MedStat 扩展预测评估验收 · 2026-11-21

统一工作台新增 `prediction_evaluation_extended`：HL、DCA，以及有同一行旧概率时的NRI/IDI。提供统计表、新旧模型DCA曲线及结果JSON下载；修复旧MedStat模板对null HL p值、IDI Z值直接调用toFixed的错误。原基础预测评估入口及统计默认策略保持兼容。

## 数学口径与结果边界

| 指标 | 当前实现 | 验收依据及边界 |
|---|---|---|
| HL | 沿用0–1等宽分箱，事件及非事件两项；实际非空组数减2自由度 | 四组各2例、每组1事件、预测概率0.1/0.3/0.7/0.9，统计量496/63，df=2，p=exp(−统计量/2)。与ResourceSelection的分位数组不同，不自动改策略。小期望单元格提示，零期望或组数不足时p不可计算 |
| DCA | 用户明确指定阈值，概率≥阈值为高风险；当前/旧模型、全部治疗、不治疗 | 独立逐人效用加总与有理数权重核对；阈值0保留算术，阈值1模型及全部治疗为null，曲线不连该点。不推荐临床阈值 |
| NRI | 每个指定阈值分别定义二分类，输出事件/非事件上移下移计数及分量 | 原手算计数继续通过；新旧模型互换时符号反转，同模型为0。不是多类别或连续NRI |
| IDI | 事件组平均概率变化减非事件组变化，标准误使用逐人配对差值样本方差 | 事件变化0.1/0.3、非事件−0.1/0.1时IDI=0.2，SE=√0.02，Z=√2。组内不足2例或零方差保留状态/null；仅固定预测近似，不涵盖重新拟合不确定性，不自动给显著性结论 |

公式来源核对：[ResourceSelection作者实现](https://raw.githubusercontent.com/psolymos/ResourceSelection/master/R/hoslem.test.R)、[dcurves作者文档](https://www.danieldsjoberg.com/dcurves/articles/dca.html)、[Pencina等原始论文，2008](https://pubmed.ncbi.nlm.nih.gov/17569110/)。测试同时保留旧报告`EVALUATION_EXTENDED_20261120.md`中的12项反例；不把同公式的重复实现当唯一正确性依据。

## 输入与产物

示例`examples/evaluation_extended.json`可直接用于CLI/HTTP通用statistics任务。桌面有独立“预测评估补充”表单。

- 每行：observed整数0/1、probability为新模型概率；可选old_probability，但比较时所有行都必须有旧概率。
- 2–10000行、两类结局齐全；不自动剔除缺失或对齐数据。比较时须`paired_confirmed=true`，确认同受试者和同结局时间点；此为用户声明。
- `n_bins`显式指定2–20且不超过样本数；DCA阈值显式递增、无重复、最多201个，范围[0,1]；NRI最多50个，范围(0,1)。没有旧概率时不接受配对声明/NRI阈值。
- `evaluation_scope`为training/held_out/external，来源为用户声明。仅允许synthetic分类；统计过程零模型调用。
- 输出记录样本量、事件/非事件数、输入哈希、库版本、实际分组/阈值/配对口径、警告与推断状态；原始JSON保留数值精度，表格按6位有效数字显示。严格JSON不写NaN/Infinity。

## 验收范围

完整Python：151项基础/HTTP/单元+58项统计=209通过。Chromium：38项流程通过。新增8项适配器检查、1项HTTP流程、3项浏览器检查。

- 后端包含独立HL有理数/df=2闭式尾概率、DCA逐人加权和、IDI配对方差、模型互换对称性、行顺序不变性、同模型、端点、小组、常数概率、错误配对/输入入库前拒绝。
- HTTP实际入队/执行/产物持久化和能力列表验证。
- 桌面实际执行两个合成任务，验证四指标表格、DCA图、JSON下载、表格宽度和null状态。
- 旧MedStat模板的实际展示函数在隔离浏览器DOM中调用，验证null HL/IDI不崩溃，DCA的null原样传给Plotly；Plotly在此检查中为记录调用的替身。此项不是旧Flask全应用或Plotly库完整端到端验收。

复现：`.venv/bin/python scripts/validate.py`；桌面命令见`scripts/browser/README.md`。结果为`reports/validation-summary.json`、`validation-core.log`、`medstat-validation-run.log`及`reports/browser/summary.json`。截图/导出：`reports/browser/medstat-extended-evaluation.png`、`medstat-undefined-values.png`、`medstat-extended-evaluation.json`。

新增实现为`workbench/evaluation_extended.py`、`web/evaluation.js`，局部接入adapters/server/index/app及修复`modules/MedStat/templates/index.html`。未改Hunter/Writer业务逻辑。Gemini空白、手机暂缓、无GitHub推送；真实病例、临床验证及生产部署仍不在本轮验收范围。
