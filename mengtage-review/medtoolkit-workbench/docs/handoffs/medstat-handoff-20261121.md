# MedStat 交接 · 2026-11-21

工作区：/home/workspace/agents/agent-20261111-144433-e19368；源码：medtoolkit-workbench/。用户最新要求暂停MedHunter细化，按handoff优先完善MedStat；无需重开对话。Writer由另一个LLM接续，不覆盖其改动。

原14个统一统计方法继续可用；新增第15个prediction_evaluation_extended，接入CLI/HTTP持久任务、桌面表单、HL/NRI/IDI表格、当前/旧模型DCA曲线和JSON下载。入口workbench/evaluation_extended.py、web/evaluation.js；示例examples/evaluation_extended.json。基础prediction_evaluation原输出不变。

HL沿用等宽分组及非空组数减2自由度，零期望或组数不足返回不可计算状态；小期望数提示近似可能不可靠。DCA沿用概率≥阈值，阈值1返回null。NRI逐阈值二分类，非多类别/连续NRI。IDI使用逐人新旧预测差的样本方差；SE/Z仅固定预测近似，不含重拟合不确定性，不自动提供显著性结论。比较新旧模型要求每行同受试者/结局时间点的明确配对声明，仍属于用户声明。统计默认策略未变。

旧modules/MedStat/templates/index.html已修复HL/IDI null的toFixed错误及缺失NRI/IDI保护。旧模板展示函数经隔离浏览器DOM和Plotly调用替身核验，不应声称旧Flask完整应用已通过全流程验收。

当前完整151项基础/HTTP/单元+58统计=209通过；Chromium38项通过。新增8个适配器测试、1个HTTP、3个浏览器检查。独立证据包括HL的有理数统计量及df=2闭式尾概率、DCA逐人效用加总、IDI配对样例、模型互换符号与行顺序不变性；不是仅重复被测公式。

详细报告medtoolkit-workbench/reports/MEDSTAT_EXTENDED_ACCEPTANCE_20261121.md，原公式修复报告EVALUATION_EXTENDED_20261120.md继续保留。结果与源码哈希见reports/validation-summary.json、reports/browser/summary.json；合成截图/JSON见reports/browser/medstat-*。复现命令：.venv/bin/python scripts/validate.py；浏览器配置见scripts/browser/README.md。

保留约束：仅合成数据，无LLM调用；Gemini密钥/型号空白；手机暂缓；不推GitHub。TableOne等方差t与group_numeric的Welch、Gamma inverse链接、现有插补范围不改变。与旧产品或统计默认冲突先问用户，明确数学/程序错误直接修复。当前本地源码已包含全部修改，不重复应用旧补丁。

后续可选扩展包括分位数HL、多类别/连续NRI、模型重拟合推断、分类插补及真实数据接入；本轮没有将其包装为已支持。先按用户实际分析需求选下一项，不恢复MedHunter的细化计划或无边界扩展功能。
