# 缺失数据与多重插补修复验收

本轮21项合成数据检查：21通过，0失败，0阻塞。原12项反例保留并调整为修复后的行为契约；新增9项覆盖实际Web函数、缺失码字典、类别拒绝、失败分析、自由度、无缺失输入及严格JSON。未使用患者数据或LLM。

## 修复及有意收窄的支持范围

| 原问题 | 修复后的行为 |
|---|---|
| object/string/category缺失码口径不同、热力图只识别NaN | MissingDataAnalyzer使用同一个逐值缺失掩码生成统计、矩阵和规范化数据；Web缺失摘要与热力图直接共用该掩码 |
| 999等值无字典自动判缺失 | 无字典仅识别公开列出的默认文本缺失码与原生NA；数字缺失码必须在变量字典显式指定，单列空列表表示仅原生NA |
| linear/ridge返回重复数据冒充多重插补 | m>1时明确拒绝linear/ridge；m=1仍允许单次插补，但不产生Rubin合并推断 |
| 全缺失列导致IndexError | 提前ValueError；Web返回400并提示不可估计 |
| 分类变量编码后连续回归再round/clip | 暂不支持分类/离散缺失值插补，明确拒绝；完整分类变量保留但不当成连续预测变量。当前插补仅支持连续数值缺失；该项是能力收紧，并非分类插补已实现 |
| Web端用平均SD差构造B | Web调用MICEImputer.pooled_means，对每份数据集实际计算均值Q和样本方差/n，再调用共同Rubin实现 |
| CI默认盲猜n−1并缩放 | 通用pool_results接受完整数据模型的df_complete；明确未知时采用标记的大样本假设。仅均值助手使用其明确适用的n−1；有限样本采用Barnard–Rubin自由度 |
| 单份分析失败静默丢弃 | 任意数据集拟合失败即明确拒绝整个合并，不输出部分结果；失败索引保留于异常说明 |
| 无缺失只返回1份仍尝试合并 | 返回一份完整数据及“无MI推断”状态、空Rubin结果，不冒充m份插补 |

## 数值与实际函数测试

- 固定seed序列重复性、观测值保留、Bayesian posterior多份差异通过。
- 手算Q=(1,2,3)、U=(0.25,0.25,0.25)：Qbar=2、Ubar=0.25、B=1、T=1.5833333333通过。
- Barnard–Rubin在df_complete=19下与独立算式核对通过；未把该测试解释为所有分析模型CI覆盖率认证。
- Web均值合并使用实际app.py的mice_impute函数：AST提取函数体，去除路由装饰器，用合成session/request和临时目录执行。函数调用真实MICEImputer和pooled_means，核对实际返回Q/U/B与数据集级手算。不是继续计算旧公式，也不是仅检查源码字符串。实际Web函数的linear多次插补与全缺失输入返回400已分别验证。
- 同样执行实际missing_analysis函数，['NA','ok',None]的摘要和热力图都计2个缺失。
- 全缺失、未支持的分类缺失、确定性多次插补均通过明确拒绝测试。拒绝表示边界保护生效，不表示实现了对应统计方法。

本轮测试没有启动Flask HTTP服务器；路由函数与统计代码已执行，session接入、认证、实际部署与浏览器仍属于独立工程验收范围。

## 公式依据

- [mice pool.scalar官方文档](https://amices.org/mice/reference/pool.scalar.html)：逐份估计量及方差合并、完整数据残差自由度。
- [mice pool官方文档](https://amices.org/mice/reference/pool.html)：先对每份插补数据拟合，再合并估计，采用Barnard–Rubin小样本调整。
- [mice Barnard–Rubin实现](https://github.com/amices/mice/blob/master/R/barnard.rubin.R)：用于核验自由度公式。

计算中T=Ubar+(1+1/m)B，r=(1+1/m)B/Ubar；有限df_complete时1/df=1/df_old+1/df_observed。均值合并显示的FMI来自该自由度下的Rubin定义，不再使用旧SD差简化量。

## 保留限制

插补适用性仍取决于缺失机制、预测变量与条件模型，不能把固定样例通过视为MAR假设或临床研究结论的验证。分类、离散及全部缺失变量需另建适用模型；当前明确阻止输出未经验证的相关结果。默认文本缺失码也需要研究者核对，可通过变量字典覆盖，数值型哨兵不自动推断。

运行：`.venv/bin/python tests/acceptance_missing.py`。存在FAIL或BLOCKED时返回非零退出码；逐项证据见acceptance-missing.json。
