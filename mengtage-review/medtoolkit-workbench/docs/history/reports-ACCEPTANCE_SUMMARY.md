# 当前验收汇总 · 2026-11-20

2026-11-21 Office排版：已用LibreOffice实际渲染验收，修复A4纸张、段距、跨页表格行、列宽/对齐、长哈希和页码；压力样稿65行表格完整，5页优化为4页。235项Python及10项Writer相关桌面本轮通过，Microsoft Word客户端仍未实测。见[排版报告](PAPERWRITER_OFFICE_20261121.md)。


2026-11-21 Hunter证据接续：人类裁决者可从已完成全文裁决且研究映射有效的批次捕获报告，固定原件/报告/研究/裁决版本，进入Writer审核与导出。235项Python、48项桌面通过。见[本轮报告](PAPERWRITER_HUNTER_20261121.md)。此前Hunter未绑定描述由本段覆盖。


2026-11-21统计证据接续：MedStat完成时固定输入/产物哈希；Writer可原生选择当前项目已完成合成分析，固定结果并进入证据/审核/导出链。完整229项Python、45项桌面通过。见[本轮报告](PAPERWRITER_STATISTICS_20261121.md)。Hunter绑定仍待做；此前Stat未绑定描述由本段覆盖。


2026-11-21 Word接续：统一Writer新增固定版本DOCX及配套审计JSON导出；保留草稿/历史标记、中文英文与引用，标准Markdown表格转为Word表格。225项Python、Writer桌面6项通过。详见[本轮验收](PAPERWRITER_WORD_20261121.md)。此前“统一Word尚未完成”由本段覆盖；双语/自动翻译与Hunter/Stat原生绑定仍待做。


2026-11-21 PaperWriter接续：新增 `/writer` 本地证据包、章节编辑/版本、作者审核与Markdown/审计JSON导出；保留旧Word/翻译行为。221项Python检查通过，原桌面38项及Writer独立5项通过。详见 [Writer验收](PAPERWRITER_ACCEPTANCE_20261121.md)。Hunter细化仍暂停；本次按用户要求从MedStat转到Writer。下文旧状态以本段及专项报告为准。


| 范围 | 结果 | 证据 |
|---|---|---|
| 基础/HTTP及新增单元检查 | 107 项通过 | `validation-core.log` |
| 相关、组间、分类、TableOne | 23 项通过 | `acceptance-groups.md` |
| 回归与预测评估 | 14 项通过 | `acceptance-regression.md` |
| 缺失、插补与合并 | 21 项通过 | `acceptance-missing.md` |
| Chromium 桌面流程 | 38 项通过，覆盖统计、去重复核及独立筛选 | `browser/summary.json`、`DESKTOP_ACCEPTANCE_20261120.md` |

Python 当前209项检查全部通过：151项基础/HTTP/单元检查，58项统计检查。MedStat扩展评估新增8项后端、1项HTTP及3项桌面检查；最新时间和源码哈希见 `validation-summary.json`。

统一入口现支持相关性、列联表、数值组间、TableOne、OLS/Logistic、Poisson/Gamma、基础预测评估及连续插补。按模块阅读 `CATEGORICAL`、`GROUPS`、`TABLEONE`、`REGRESSION_ADAPTER`、`EVALUATION`、`GLM`、`IMPUTATION_ACCEPTANCE_20261120.md`。原失败结果保留于 `baseline/`，历史正文于 `history/pre-desktop-20261120/`。

原模块已修复包括 MH 条件检验与区间、RxC Monte Carlo、样本 SD 与百分比分母、概率接口、缺失掩码、Rubin/Barnard–Rubin 合并等；这些修复不等于所有旧模块均迁入统一入口。TableOne 与独立组间入口保留各自检验策略；Gamma 保留 inverse 链接。

全部统计使用合成数据，没有 Gemini 调用。HL/DCA/NRI/IDI新增有限合成核验与修复见 `EVALUATION_EXTENDED_20261120.md`，现已沿旧口径接入独立扩展评估页面，见 `MEDSTAT_EXTENDED_ACCEPTANCE_20261121.md`。分类/离散插补、回归参数 MI 合并、完整写作 agent、真实病例及生产安全未完成对应验收。浏览器检索使用合成传输响应；此前真实 PubMed 结果留在 `validation-live.json`，不能作为本轮联网验证。

复现 Python：`.venv/bin/python scripts/validate.py`。复现桌面：[浏览器说明](../scripts/browser/README.md)。

题名摘要筛选新增5项身份/流程单元、1项HTTP权限检查及4项双浏览器身份流程，见SCREENING_DESKTOP_20261120.md。模型结果为合成导入，无真实调用。

规范化排除原因与CSV：新增6项单元及1项浏览器检查，权限检查覆盖提前导出与模型身份导出；见SCREENING_CSV_20261120.md。

全文快照及跨阶段筛选验收见 [FULLTEXT_ACCEPTANCE_20261121.md](FULLTEXT_ACCEPTANCE_20261121.md)。PDF用后端合成文件验证提取；桌面以TXT贯通上传、原件下载、checkpoint、独立提交、摘录拒绝、裁决和审计导出。人工映射与单来源链PRISMA现已完成；数据库/注册库集合合并后重筛已接入；既有筛选分支直接汇总仍未实现。

研究映射与单来源链PRISMA计数：[STUDIES_PRISMA_20261121.md](STUDIES_PRISMA_20261121.md)。

多来源集合、增量版本与逐来源PRISMA验收：[SOURCES_COLLECTION_20261121.md](SOURCES_COLLECTION_20261121.md)。
