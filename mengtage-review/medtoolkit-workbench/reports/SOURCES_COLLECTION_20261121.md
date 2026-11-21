# MedHunter 多来源集合与增量版本验收 · 2026-11-21

已接入来源登记、数据库/注册库书目JSON导入、完整来源清单冻结、增量集合版本、跨来源去重及PRISMA来源拆分。完整Python检查142项基础/HTTP/单元+58项统计=200项通过；Chromium35项流程通过。本轮新增10项后端、2项HTTP和2项桌面流程；未调用模型，未改MedStat/MedPaperWriter业务代码。

## 实现及计数

| 环节 | 行为 |
|---|---|
| 已有PubMed检索 | 只能登记当前项目已完成search任务的产物；保存原产物哈希、原检索式、命中/下载/完整性及任务创建时间。创建时间不是数据库更新时间或精确完成时间 |
| 其他数据库/注册库 | 人工确认公开书目JSON及来源名称、类型、检索式、ISO日期/时间、命中数、完整性与覆盖说明。未知命中填null；完整导入要求命中数等于记录数。完整性为导入者声明，非系统独立验证 |
| 冻结集合 | 显式选择本轮全部source_id；来源不得重复。每条原始记录保留source_id、来源内序号和快照哈希。相同请求复用既有快照/集合，不重复创建 |
| 增量版本 | 可引用旧集合为父版本，保留旧文件及哈希；新版本按显式清单重新组装，可新增/撤换来源。不会把父集合数量再次相加，不继承旧筛选判断 |
| 跨来源去重 | 复用既有标题/PMID/DOI确定性去重与冲突人工复核；同一报告在不同来源出现，保留所有原始记录及位置。无LLM |
| 进入筛选 | 从集合建立去重任务，回工作台运行/复核并选定产物，再建人工checkpoint。旧筛选分支不能直接相加 |
| PRISMA | 核验每个来源快照、集合记录/来源位置、原生检索原件哈希及去重链；列出每次来源的名称、类型、检索式、时间、导入与命中数、完整性及覆盖依据；审计JSON含筛选记录→去重组→来源原始位置 |

各次命中数求和是未去重的检索次数层面数量，不是唯一文献数。任何来源命中未知时，总命中与未下载数量为null；任何来源未取全时标为局部流程。数据库和注册库合并后进入同一去重/筛选流程，图表按最终选定集合计数，不宣称覆盖整个综述的全部来源。

SVG流程图补充逐来源导入/命中明细；CSV逐来源指标使用source_id，详细名称及检索信息可与同一报告哈希的审计JSON关联。旧单来源流程保持可用。

## 使用入口

工作台“检索文献”区域进入“管理多来源与增量检索集合”（`/sources`）；使用管理员令牌选择项目，登记原生检索或导入书目JSON，勾选完整来源、名称和建版理由，确认后冻结。可从父集合预选既有来源再增加新来源。集合卡片可发起去重任务，回工作台运行。

导入字段仅允许title、abstract、pmid、doi、authors、journal、pub_date；authors可为文本列表。示例：

```json
{
  "metadata": {
    "database": "Synthetic registry",
    "kind": "register",
    "query": "synthetic query",
    "searched_at": "2026-11-21",
    "total_hits": 1,
    "complete": true,
    "coverage_note": "合成示例，非实际检索"
  },
  "records": [{"title":"Synthetic trial report","pmid":"123"}]
}
```

API为管理员入口：GET `/api/sources?project=...`；POST `/api/sources/capture`、`import_records`、`create`。独立评审令牌不能读取来源管理数据。来源列表和集合摘要在身份改变/退出时清除；令牌不写浏览器持久存储。

## 测试证据

- 后端：`tests/test_sources.py`，覆盖幂等、确认、字段/覆盖校验、跨来源重复、原始位置、增量选择与旧版保留、重复快照/跨项目拒绝、原件/来源位置篡改、未知命中/零结果来源、原生登记、合并上限、集合→筛选→PRISMA。
- HTTP：`tests/test_sources_http.py`，验证大于1MB但小于2MB的有效书目导入、超内容预算拒绝、字段白名单、幂等、来源列表、建版和跨项目边界。
- 桌面：先登记不完整PubMed检索（导入1、命中2），建初版集合；再导入注册库2条（其中1条与PubMed相同），在保留初版基础上建增量集合。合并原始3条、去重后2条、各次命中和4、未下载1；两条合成记录最终排除，报告/研究均0；PRISMA仍标记部分检索。
- 运行命令：`.venv/bin/python scripts/validate.py`；浏览器复现见`scripts/browser/README.md`。
- 结果：`reports/validation-summary.json`、`validation-core.log`、`sources-validation-run.log`；`reports/browser/summary.json`、`run.log`。
- 图及导出：`reports/browser/source-collections.png`、`sources-prisma-counts.png`、`sources-prisma-flow.png`、`sources-prisma-flow.svg`、`sources-prisma-audit.json`。这些文件均为合成材料。

## 文件和后续边界

新增`workbench/sources.py`、`web/sources.html/js`、两份测试。局部修改`server.py`、`prisma.py`、`web/index.html`、`web/studies.js`及浏览器脚本。去重规则及旧筛选默认值未改变。

每来源最多1000条，单集合最多50个来源、合计1–1000条原始记录；JSON导入内容上限2MB，集合10MB。合并记录为0时暂不建筛选集合，但零结果来源可与非空来源一起登记。其他网站/引文追溯路径、RIS/CSV解析、外部数据库直接API检索、大规模分片和既有筛选分支合并尚未实现。手工声明公开书目不能自动识别字段内容是否含敏感信息。

下一步先做增量集合差异预览：明确新增、删除、来源变化及潜在重复；再设计旧筛选判断可否复用的人工确认及方案/材料一致性检查。当前新版本默认重新筛选，不静默迁移旧判断。Gemini空白、手机暂缓、无GitHub推送；本机管理员与磁盘访问仍受信任。
