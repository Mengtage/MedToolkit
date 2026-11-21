# 文件结构与当前实现

2026-11-21 PaperWriter接续：新增 `/writer` 本地证据包、章节编辑/版本、作者审核与Markdown/审计JSON导出；保留旧Word/翻译行为。221项Python检查通过，原桌面38项及Writer独立5项通过。详见 [Writer验收](reports/PAPERWRITER_ACCEPTANCE_20261121.md)。Hunter细化仍暂停；本次按用户要求从MedStat转到Writer。下文旧状态以本段及专项报告为准。


当前源码在 `medtoolkit-workbench/`，上游核对基准为 `d3486d0` 中的 `mengtage-review/medtoolkit-workbench/`。以文件和验收哈希为准，旧 Git HEAD 不代表当前内容；未提交或推送。

| 路径 | 职责 |
|---|---|
| `workbench/core.py` | 项目、SQLite 任务、输入校验入口、进程锁、重试与恢复 |
| `workbench/adapters.py` | PubMed、相关性、统计分派、证据约束章节写作 |
| `workbench/categorical.py`、`groups.py`、`tableone.py` | 列联表、独立组比较、基线表 |
| `workbench/regression.py`、`glm.py` | 数值 OLS/Logistic、Poisson/Gamma |
| `workbench/evaluation.py`、`imputation.py` | 基础预测评估、连续插补及可选均值合并 |
| `workbench/server.py`、`__main__.py`、`exports.py` | 本机 HTTP、CLI、RIS |
| `web/` | 桌面统计表单、任务、TableOne/回归表格与 JSON 产物 |
| `examples/` | 合成统计输入及未配置写作模板 |
| `tests/`、`scripts/validate.py` | 107 项基础/HTTP/单元检查及 58 项统计检查 |
| `workbench/deduplication*.py`、`screening*.py` | 去重CLI与dedup_jobs.py任务/HTTP/桌面闭环、人工checkpoint与双评审审计原型，非多人身份认证 |
| `workbench/review_access.py`、`screening_http.py`、`web/screening.*` | 独立评审令牌、批次权限与题名摘要/全文筛选桌面 |
| `workbench/screening_exports.py` | 冻结排除原因词表、逐条决定和完整判断历史CSV |
| `scripts/browser/` | 独立服务、合成 PubMed 响应、真实 Chromium 点击验收 |
| `reports/` | 当前验收、数值结果、日志、哈希及逐轮证据 |
| `reports/history/`、`CHANGELOG.md` | 整理前文档与历史状态 |
| `modules/` | MedPaperHunter、MedPaperWriter、MedStat 原模块及本地修复，保留许可 |
| `skills/` | med-extract、search-strategy、workbench、catalog、catalog-resources、zotero 参考材料 |

已同步的 7 个上游源文件见 `reports/upstream-sync.json`。早期原模块差异清单 `source-diff.json` 仅反映当时快照，不是后续累计改动总数。尤其旧 `modules/MedStat/src/analysis/regression.py` 的无新数据 `predict_proba()` 已修正为概率，累计交付必须保留此项。

统一适配器显式拒绝未支持输入，不代表旧模块已全面改写。保留 TableOne 等方差 t、group_numeric Welch、Gamma inverse 等各自行为；完整能力与限制以 [README](README.md) 为准。旧模块 WebApp 没有本轮浏览器验收，也不应直接开放公网。

本轮浏览器依赖仅在 `.browser-tools/`，临时项目使用系统临时目录，运行后清理；不进入累计补丁。源码、复现说明及测试证据保留在项目内。

全文：`workbench/fulltext.py`负责原件/文本快照、取得审计与阶段关联，`web/fulltext.js`负责登记、材料预览和原件下载；验证见 `tests/test_fulltext.py` 及 `reports/FULLTEXT_ACCEPTANCE_20261121.md`。

研究映射：`workbench/studies.py`；来源链计数与导出：`workbench/prisma.py`；桌面：`web/studies.js`；后端测试：`tests/test_studies_prisma.py`。

多来源：`workbench/sources.py`负责来源快照和完整集合版本，`web/sources.html/js`提供独立管理员页面；`prisma.py`增加逐来源核验/明细和记录位置关联。

MedStat扩展评估：`workbench/evaluation_extended.py`负责严格输入和原统计模块适配，`web/evaluation.js`提供HL/NRI/IDI表格、DCA曲线和下载；旧模板null处理在`modules/MedStat/templates/index.html`。
