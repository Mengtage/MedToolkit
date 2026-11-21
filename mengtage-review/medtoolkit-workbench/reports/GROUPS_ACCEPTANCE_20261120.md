# 数值组间比较接续验收 · 2026-11-20

新增统一任务方法 `group_numeric`，复用 `MedStat/src/analysis/group_analysis.py`。两组同时输出Welch t、Mann–Whitney U、Cohen d；多组输出经典单因素ANOVA和Kruskal–Wallis。沿用旧版检验组合，未自动选择主要检验或改写旧模块。

## 输入与输出

CLI示例：`.venv/bin/python -m workbench enqueue PROJECT_ID statistics examples/groups.json`；随后运行返回的JOB_ID。页面新增“数值组间比较”表单。

输入必须为synthetic；指定不同的分组列和数值列，仅接受这两列。2至10个独立组，总行数4至10000；分组标签须为非空字符串，各组至少2个非缺失值。数值缺失使用null，分组缺失拒绝。数值必须有限且绝对值不超过1e100。

结果保留首次出现的组顺序；两组差值和Cohen d为首组减第二组，U对应首组。记录原始行数、有效行数、各组缺失数、总剔除数、输入哈希及软件版本。

新统一入口拒绝所有组内方差均为零，以及任一组有效样本不足的输入；不会沿旧模块的多组分支静默跳过不足样本组。此为新入口的支持范围，旧模块行为不改。计算若仍产生NaN/Infinity，任务失败且不保存统计产物。单个组为常量、其他组有变异时可计算，已纳入验收。

## 验证

34项基础/接口测试、23项组间/分类检查、14项回归检查、21项缺失数据检查通过，共92项；`node --check web/app.js`通过。运行命令：`.venv/bin/python scripts/validate.py`。

新增6项适配器测试与1项真实HTTP测试：Welch及Cohen d对照手算公式；Mann–Whitney完全分离小样本对照秩排列；ANOVA对照独立平方和；Kruskal–Wallis对照秩和公式；组序/缺失计数；单组常量；无效输入不入库；非有限结果不产生统计文件；HTTP任务提交、执行及产物读取。测试仅用合成数据，未调用模型。

## 下一步与边界

当前统一入口覆盖相关性、列联表、数值组间比较。TableOne、回归、预测评估和插补尚未接入统一入口；配对/重复测量方法不在本入口支持范围。桌面表单已接线，真实浏览器点击级验收仍未完成。证据提取与完整写作agent待继续。Gemini配置留空，手机端暂缓；未提交或推送GitHub。
