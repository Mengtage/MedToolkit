---
name: mengtage-research-workbench
description: 为 Mengtage 编排医学科研项目的检索策略、导出记录归档、文献筛选与证据提取，并向统计和成文模块交接版本化材料；适用于当前科研工作台项目及其后续课题。
---

# Mengtage 科研工作流

本技能整合用户提供的 MedExtract 2.0 与 Medical Search Strategy Builder（包名v2、内部3.0.0）的流程设计。脚本只实现项目初始化、CSV记录归档与保守去重、状态检查；检索式、筛选和证据提取由Agent按本技能执行。MedPaperHunter、MedStat 源码附件尚未成功下载，统计与成文为交接规范，不宣称已接通应用或自动生成有效科研结果。

先遵守 [安全、严谨性与模型路由](references/security-and-model-policy.md)：统计零 LLM、检索少量 Gemini、写作 Gemini agent；旧版冲突须由 Mengtage 决定。

## 项目入口与恢复

先读取项目 `project.json` 和 `status.json`；已有课题直接续接，不重新询问已确认信息。用户未指定目录时用当前工作区的 `projects/<课题短名>`。用下述命令初始化，目录已存在时拒绝覆盖：

`python3 scripts/workbench.py init <项目目录> --question '<研究问题>'`

手机回复只给：当前阶段、最新产物、一个必要决定。缺材料或用户离开时保存状态；不把沉默当批准。长表和原文定位留在文件/文档，避免逐篇刷屏。

## 流程与路由

1. **问题与检索**：读取 [search.md](references/search.md)。依据问题选择PICO/PEO等框架；确认真正影响范围的歧义。保存每个数据库和检索平台的完整检索式、日期、条件、命中数、导出数。构建策略与实际执行分开记录。
2. **导入与筛选**：CSV用 `python3 scripts/workbench.py import <项目目录> <输入CSV>`。要求每行有 `source,title`，可选 `doi,pmid,authors,year,abstract`。程序保留输入文件、来源行与哈希；只合并无冲突的同DOI或同PMID记录，缺少标识或标识冲突时保留并标记复核。相似标题不能直接删除。人工筛选读 [extraction.md](references/extraction.md)。
3. **提取**：按变量字典提取，保存全文版本、页码/表格/段落、短证据片段、原值、单位、提取者、复核者；无法访问/无法解析与原文未报告分开编码。只有确实检查原文后才能写“原文未报告”。
4. **统计交接**：读 [handoffs.md](references/handoffs.md)。冻结数据与分析计划后交给获准的统计工具。该技能不自动选择显著性更好的模型，不把描述性输出当因果证据。
5. **写作交接**：仅使用已确认的证据表与已复核结果；未知内容留缺项，不补造数字、作者贡献或前期基础。目标期刊要求按实际期刊核验。
6. **查看进展**：`python3 scripts/workbench.py status <项目目录>` 返回记录数、当前阶段与阻塞。该状态不代表研究已通过人工或机构审批。

## 关键规则

- 命中截断用分页或覆盖完整范围的互补分片解决，不能缩小课题范围来伪装检索完整。
- 文献记录、全文报告和研究分别使用 record_id、report_id、study_id；多篇报告可属于同一研究。
- PRISMA计数由决策记录汇总；未获取全文单列，排除原因明确；不能照搬原包中将不同来源串联的流程图。
- 若是正式系统综述，按选定方法规定独立筛选、复核与分歧裁决；两个Agent同意不等同于完成独立人工双审。
- 来源授权按数据库、全文许可证和机构协议分别判断；不把本技能视作全文下载授权。
- 伦理、基金和投稿材料可准备；正式提交依已授权范围和责任人确认，不承诺审批或录用。

来源、已修正问题及限制见 [integration-review.md](references/integration-review.md)。原始包保持在独立收件目录，不加载原有有缺陷规则作为并行生效指令。
