# 规范化排除原因与CSV审计导出

新HTTP筛选批次冻结原因词表medhunter-exclusion-v1，纳入protocol_sha256，并在人工checkpoint页面展示。排除决定必须从冻结词表选择一个原因代码，同时保留具体理由；纳入和不确定不能携带排除代码。不自动根据自由文本猜测代码。

默认词表：population（研究对象）、intervention（干预/暴露）、comparator（对照）、outcome（结局）、design（设计）、publication_type（文献类型）、duplicate_report（重复报告）、other（其他）。它们是理由分类，不自动定义研究的纳排标准；须结合批次纳排标准解释。duplicate_report需在理由中注明关联记录，同一研究的不同报告不能仅据此自动删除。自定义词表可由准备批次API的protocol.reason_codes及reason_codebook_version传入，创建后冻结。

旧批次无词表时继续使用原自由文本，CSV标记legacy_free_text，原因代码留空，不追填或覆盖历史。

| 文件 | 一行的含义 | 关键字段 |
|---|---|---|
| screening-decisions.csv | 冻结文献集中的一条记录，包括待裁决条目 | review_id、record_id、题名、PMID/DOI、来源文件及哈希、双方判断/代码/理由/定位、提交事件哈希、模型名/运行ID、最新最终决定/代码/理由/操作者/时间、分歧标记 |
| screening-history.csv | 一次独立提交中的逐条判断，或一次人工裁决/修订 | 批次/记录ID、事件类型、操作者、时间、决定、代码、理由、定位、事件哈希与前序哈希 |

最新决定表只取最后一次人工裁决，历史表保留所有修订。未裁决记录的final_status为pending，不算排除。纳入/排除是当前题名摘要阶段结论，不直接等同最终研究纳入。

两份CSV通过独立筛选页下载；HTTP接口为POST /api/review/export_csv，仅指定人类裁决者在揭盲后可用。完整事件链、冻结词表和原始模型运行信息仍在JSON中；CSV是便于审阅的视图，不替代完整JSON。

格式：UTF-8 BOM、标准CSV引用和CRLF行结束，支持中文、逗号、双引号、换行。以公式字符或控制字符开头的单元格加前导单引号防止表格软件执行；JSON保持原文。CSV适合阅读核对，不能直接当作未经转换的原始数据回导。

验证：新增6项单元检查；浏览器新增1项排除代码必填、修订及两种CSV下载流程，并核对最终JSON仍保留先前纳入与后续排除事件。既有权限检查扩展到CSV，拒绝提前导出和模型身份导出。完整165项Python/HTTP/统计、28项Chromium检查通过。实际日志、版本与哈希见validation-summary.json、browser/summary.json；示例见browser/screening-decisions.csv、screening-history.csv及screening-audit.json。

本轮仍为题名摘要筛选。全文文件/页码快照、跨阶段稳定关联、报告—研究映射与PRISMA计数尚未实现；不能将本轮CSV直接标为最终PRISMA结果。无真实模型调用，Gemini空白，手机暂缓。
