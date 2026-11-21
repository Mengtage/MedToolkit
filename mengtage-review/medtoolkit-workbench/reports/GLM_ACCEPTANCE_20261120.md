# GLM统一入口验收 · 2026-11-20

新增poisson_regression、gamma_regression，复用旧GLMAnalyzer的数值变量入口；统一任务、HTTP和桌面回归表单已接通。示例examples/poisson.json、examples/gamma.json以statistics任务提交。

Poisson沿用log链接、计数结果必须非负整数；Gamma沿用inverse链接、结果须严格为正。均含截距，仅接收显式数值预测变量，按所选变量完整案例处理；继承数值回归的行数、变量数、设计秩及非有限输入校验。const和Intercept保留给截距。不支持自由公式、分类自动编码、offset/exposure；额外字段拒绝入库。

结果记录分布、链接、系数及区间尺度、离散参数scale、残差自由度、样本内预测均值、完整案例原始行号及输入哈希。Poisson另给exp(系数)均值比；未使用exposure，不直接称为发生率比。Gamma系数为inverse_mean尺度，不指数化为OR或均值比。沿用旧BIC的log_likelihood定义。拟合失败、不收敛、分离警告、非有限估计及非正预测均值拒绝生成统计产物。

验证命令`.venv/bin/python scripts/validate.py`：57项基础/HTTP、23项组间/分类、14项原回归、21项缺失数据检查全部通过，共115项。JS语法检查通过。

新增4项适配器测试及1项HTTP测试（覆盖两个模型）。两组均值2和4的独立闭式解：Poisson截距log(2)、斜率log(2)，斜率标准误sqrt(1/8+1/16)；Gamma inverse链接截距1/2、斜率1/4-1/2。两模型拟合均值均对照2和4；另验证缺失行号、负数/小数计数、非正Gamma结果、额外exposure字段及真实HTTP产物。未修改旧GLM拟合设定，未调用模型或使用真实病例。

尚未完成插补、HL/DCA/NRI/IDI、完整写作agent和浏览器点击级验收；离散分布适配、过度离散、临床预测与区间覆盖率不因固定样例通过而视为已验证。Gamma沿用inverse链接的DomainWarning类别保留在产物，不自动改换链接。Gemini保持空白，手机暂缓，未提交或推送GitHub。
