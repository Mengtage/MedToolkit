# 预测评估统一入口验收 · 2026-11-20

新增prediction_evaluation任务、HTTP和桌面表单，示例examples/evaluation.json。CLI以statistics任务提交该JSON。

## 输入与结果

仅合成数据，每行observed为整数0/1，probability为[0,1]有限数值；不接收缺失，不自动剔除。样本2至10000且必须包含两类结局。显式阈值[0,1]，阳性判据probability>=threshold。显式等宽分箱2至20且不超过样本数；最后一箱包含概率1。

必须声明evaluation_scope为training、held_out或external。该来源是用户声明，程序不独立验证拆分、泄漏或外部来源，不把声明当成已完成外部验证。

输出混淆矩阵、基础指标、ROC/AUC、Brier和校准分箱（均值及数量），保存输入哈希及软件版本。PPV、NPV、MCC零分母时返回null并列入undefined_metrics；其余基础指标沿用旧模块。ROC的Youden阈值保留为该数据集上的探索结果，不替换输入阈值。ROC起始无限阈值保留旧模块的null表示。

仅调用对应基础方法，不调用evaluate全套流程。校准方法内部仍计算旧HL和等渗拟合，但这些结果不向统一入口暴露；输出明确excluded_outputs包含HL、等渗重拟合、DCA、NRI、IDI。上述功能尚未完成对应验收；本轮未修改旧模型评估模块。

## 验收

`.venv/bin/python scripts/validate.py`通过52项基础/HTTP测试、23项组间/分类、14项原回归、21项缺失数据检查，共110项。`node --check web/app.js`通过。

新增5项适配器测试与1项真实HTTP测试：AUC对照阳性/阴性概率两两比较含并列秩；Brier对照平方误差均值；混淆矩阵及灵敏度对照手工频数；校准箱均值/样本数；概率0与1、阈值等号；常量概率AUC=0.5及不可估计指标；无效输入拒绝入库；HTTP实际提交、执行和产物读取。没有真实病例、网络请求或模型调用。

## 未完成

GLM、插补、HL/DCA/NRI/IDI等仍未接入已验收统一入口。桌面表单已接线，真实浏览器点击验收未完成。完整写作agent及证据语义核验待继续；Gemini保持空白，手机端暂缓，未提交/推送GitHub。
