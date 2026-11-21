# 当前开发进展 · 2026-11-20

2026-11-21 Office排版：已用LibreOffice实际渲染验收，修复A4纸张、段距、跨页表格行、列宽/对齐、长哈希和页码；压力样稿65行表格完整，5页优化为4页。235项Python及10项Writer相关桌面本轮通过，Microsoft Word客户端仍未实测。见[排版报告](reports/PAPERWRITER_OFFICE_20261121.md)。


2026-11-21 Hunter证据接续：人类裁决者可从已完成全文裁决且研究映射有效的批次捕获报告，固定原件/报告/研究/裁决版本，进入Writer审核与导出。235项Python、48项桌面通过。见[本轮报告](reports/PAPERWRITER_HUNTER_20261121.md)。此前Hunter未绑定描述由本段覆盖。


2026-11-21统计证据接续：MedStat完成时固定输入/产物哈希；Writer可原生选择当前项目已完成合成分析，固定结果并进入证据/审核/导出链。完整229项Python、45项桌面通过。见[本轮报告](reports/PAPERWRITER_STATISTICS_20261121.md)。Hunter绑定仍待做；此前Stat未绑定描述由本段覆盖。


2026-11-21 Word接续：统一Writer新增固定版本DOCX及配套审计JSON导出；保留草稿/历史标记、中文英文与引用，标准Markdown表格转为Word表格。225项Python、Writer桌面6项通过。详见[本轮验收](reports/PAPERWRITER_WORD_20261121.md)。此前“统一Word尚未完成”由本段覆盖；双语/自动翻译与Hunter/Stat原生绑定仍待做。


2026-11-21 PaperWriter接续：新增 `/writer` 本地证据包、章节编辑/版本、作者审核与Markdown/审计JSON导出；保留旧Word/翻译行为。221项Python检查通过，原桌面38项及Writer独立5项通过。详见 [Writer验收](reports/PAPERWRITER_ACCEPTANCE_20261121.md)。Hunter细化仍暂停；本次按用户要求从MedStat转到Writer。下文旧状态以本段及专项报告为准。


桌面去重闭环已完成：来源哈希固定、冲突默认保留、人工保留/合并另存产物、重复提交复用任务。

题名摘要筛选已接入HTTP与独立桌面页面：创建/撤销human或model评审令牌，冻结方案和文献快照，人类批准，双方独立完整提交锁定，指定人类裁决者揭盲及逐条裁决，下载完整审计JSON，以及逐条决定/判断历史两份CSV。新HTTP批次冻结排除原因词表，排除须选代码并填写理由，旧批次保留自由文本。服务端从令牌确定身份，拒绝跨批次、冒用actor、普通评审访问项目产物及提前揭盲。详见 [本轮报告](reports/SCREENING_DESKTOP_20261120.md)。

管理员与本机文件所有者仍受信任；直接CLI不等于受限评审接口。模型结果只提供人工导入，未配置或调用Gemini，不证明其真实模型来源。全文快照、页码/摘录校验及全文阶段关联已接入，见 [全文验收](reports/FULLTEXT_ACCEPTANCE_20261121.md)。报告—研究映射和单来源链PRISMA计数已完成，见 [映射/计数验收](reports/STUDIES_PRISMA_20261121.md)。数据库/注册库多来源清单、增量集合与合并后重筛计数已完成，见 [来源集合验收](reports/SOURCES_COLLECTION_20261121.md)。待接：增量差异预览与旧判断人工复用、其他检索来源路径、真实模型运行器和生产部署。手机暂缓。

MedStat已接入扩展预测评估任务及桌面：等宽HL、DCA、新旧模型逐阈值二分类NRI和配对IDI，含曲线、表格、JSON；旧模板null显示已修复。见reports/MEDSTAT_EXTENDED_ACCEPTANCE_20261121.md。当前完整检查151项基础/HTTP/单元＋58项统计＝209项；Chromium38项。精确结果与时间见reports/validation-summary.json和reports/browser/summary.json。

无GitHub提交/推送，累计包基于d3486d0审核子目录。
