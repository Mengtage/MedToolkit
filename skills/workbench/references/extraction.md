# 筛选与证据提取

保存原始记录不变；规范化标识与去重关系单独记录。自动去重只处理明确标识一致的记录；矛盾标识、相似题名和作者年份关键词匹配仅提示。预印本、正式论文、二次分析和同一试验的不同报告保留关联，不直接消失。

筛选记录字段：record_id、stage、decision（include/exclude/uncertain）、reason、reviewer、timestamp、protocol_version。全文未获取不是研究不符合纳入标准，单独记录retrieval_status。独立复核记录不覆盖首轮结果；裁决新增记录。

提取表每行表达“某报告的某字段/某时间点/某组别”：report_id、study_id、field、value_raw、unit_raw、group、timepoint、denominator、value_standardized、conversion_rule、source_file_hash、page、table_or_section、evidence_excerpt、missing_reason、extractor、reviewer、review_status。

missing_reason采用not_reported / inaccessible / unreadable / not_applicable / unclear；not_reported只用于已查看相应全文仍未发现的信息。每个数值保留对应时间点、组别和分母；转换值不覆盖原值。只截取足以核验的短证据，不默认大量复制正文。

PRISMA保留记录→报告→研究三个层次，分别汇总识别、去重、题摘排除、寻求全文、未获取全文、全文评估、按原因排除、纳入报告和独立研究数。生成图前核对各分支计数守恒；定量合并数量不能替代最终纳入研究数。
