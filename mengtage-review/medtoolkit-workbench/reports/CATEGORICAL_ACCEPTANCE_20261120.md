# 列联表统一入口验收 · 2026-11-20

本轮在已同步 d3486d0 审核版及第一轮接续修复的工作台上，新增列联表统计适配器、桌面页面入口、示例与回归测试。未修改旧版统计模块、自动方法选择、检索去重或LLM筛选规则。

## 使用

页面“列联表检验”可提交频数表及行列标签；也可使用 CLI：

```bash
.venv/bin/python -m workbench enqueue PROJECT_ID statistics examples/categorical.json
.venv/bin/python -m workbench run JOB_ID
```

方法为 `categorical_auto`、`chi2`、`fisher`、`yates`。自动方法选择直接调用旧版 CategoricalTestSelector；Fisher对2×2表使用精确检验，对RxC表使用固定边际Monte Carlo，19999次、固定种子20261119。结果保留实际方法、近似标识、模拟参数、标签、频数、总样本数、输入哈希、SciPy版本与源模块路径。2×2 OR的方向为左上×右下/右上×左下。

统一入口仅接收synthetic标记、2至10行且2至10列的整数频数表，总频数上限1000000。拒绝负数、小数、布尔数、零边际、重复/缺失标签、额外字段和非2×2 Yates输入。这些限制用于新统一入口，旧模块不变。频数表没有行级缺失信息，本接口不声称计算原始数据的缺失剔除数。

## 验收

统一验证命令 `.venv/bin/python scripts/validate.py` 通过：27项基础/接口测试、23项组间与分类检查、14项回归检查、21项缺失数据检查，共85项。`node --check web/app.js`通过。

新增6项适配器测试：Fisher对照独立超几何枚举，Pearson/Yates对照独立公式，自动选择与旧版分支一致，Monte Carlo重复性及元数据，零单元格OR边界序列化，非法输入不入库。新增1项真实HTTP测试覆盖提交、幂等、运行、状态、产物内容与能力清单。

## 尚未完成

桌面页面已接线，但本机未检测到浏览器自动化工具或Chrome，未完成真实浏览器点击验收。其余统计模块仍待逐项接入；证据提取、语义引用核验及完整写作agent尚未完成。手机端暂缓，Gemini配置保持空白，未调用模型。未提交或推送GitHub。
