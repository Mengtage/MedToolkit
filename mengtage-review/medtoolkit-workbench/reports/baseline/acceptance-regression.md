# 回归与预测模型评估验收

本轮10项合成数据用例：6通过、4失败、0阻塞。主进程补齐statsmodels后已实际运行。未修改原模块，未运行Web应用，未使用真实数据或调用模型。

运行：`.venv/bin/python tests/acceptance_regression.py`。逐项结果见`reports/acceptance-regression.json`。该脚本是验收记录器，会保存失败而不以退出码代表全部通过。

## 已通过范围

- OLS公式入口：8个样本，人工构造截距2、斜率3且残差与常数/自变量正交；输出与独立NumPy最小二乘解一致。
- Logistic公式入口：两个x层各8例，事件率分别1/4与3/4；输出截距−log(3)、斜率2log(3)、OR=9，与解析MLE一致。
- OLS公式入口缺失结局剔除：6行中1行缺失，输出n_obs=5。
- Logistic对超出[0,1]的结果变量返回错误；当前原模块同时打印traceback，整合层应避免将数据或公式内容写入不受控日志。
- 混淆矩阵与accuracy的手算用例，以及AUC=0.75的四样本已知排序用例通过。

## 必须在迁移前处理的反例

|模块|输入与观察|影响|
|---|---|---|
|model_evaluation.ModelEvaluator.__init__|y=[0,1,0,1]、分数全部0.8、阈值0.5；被误判为分类标签并取整为0，返回TP=0/FN=2；预期所有预测为1，TP=2/FP=2|恒定概率的阈值分类错误，灵敏度等指标错误|
|calculate_calibration_metrics|y=[0,0,1,1]、p=[0,.2,.8,1]、2个bin；calibration_curve的n之和为3而非4|概率恰为1的观察被分箱排除，校准统计不完整|
|calculate_roc_curve|恒定0.5分数的optimal_threshold为inf；thresholds列表虽清理，但该字段未清理|严格JSON序列化失败，可能中断接口或导出|
|FormulaParser.parse_formula|y~C(g)，g=a/b；生成g_b名称后从原df取该列，抛KeyError|辅助解析器分类变量路径不可用；不能据此判断smf公式拟合入口也失败，两者分开|

这些问题涉及旧版行为或统计输出，应先交由Mengtage确认修复方案。当前不应把模型评估全部功能标记为通过。

## 尚未覆盖

未验收GLM/Poisson/Gamma、完全分离、奇异设计矩阵、Logistic边际效应、NRI/IDI/DCA、Hosmer–Lemeshow公式或全部诊断项。预测评估已有的TRIPOD/PROBAST文字不构成方法学认证。formula与y_var/X_vars两种入口的缺失处理和变量名称行为仍需后续分别验收；本轮通过结论只适用于明确列出的公式入口与固定样例。
