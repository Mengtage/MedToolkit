# Mengtage MedToolkit 科研工作台

2026-11-21 Office排版：已用LibreOffice实际渲染验收，修复A4纸张、段距、跨页表格行、列宽/对齐、长哈希和页码；压力样稿65行表格完整，5页优化为4页。235项Python及10项Writer相关桌面本轮通过，Microsoft Word客户端仍未实测。见[排版报告](reports/PAPERWRITER_OFFICE_20261121.md)。


2026-11-21 Hunter证据接续：人类裁决者可从已完成全文裁决且研究映射有效的批次捕获报告，固定原件/报告/研究/裁决版本，进入Writer审核与导出。235项Python、48项桌面通过。见[本轮报告](reports/PAPERWRITER_HUNTER_20261121.md)。此前Hunter未绑定描述由本段覆盖。


2026-11-21统计证据接续：MedStat完成时固定输入/产物哈希；Writer可原生选择当前项目已完成合成分析，固定结果并进入证据/审核/导出链。完整229项Python、45项桌面通过。见[本轮报告](reports/PAPERWRITER_STATISTICS_20261121.md)。Hunter绑定仍待做；此前Stat未绑定描述由本段覆盖。


2026-11-21 Word接续：统一Writer新增固定版本DOCX及配套审计JSON导出；保留草稿/历史标记、中文英文与引用，标准Markdown表格转为Word表格。225项Python、Writer桌面6项通过。详见[本轮验收](reports/PAPERWRITER_WORD_20261121.md)。此前“统一Word尚未完成”由本段覆盖；双语/自动翻译与Hunter/Stat原生绑定仍待做。


2026-11-21 PaperWriter接续：新增 `/writer` 本地证据包、章节编辑/版本、作者审核与Markdown/审计JSON导出；保留旧Word/翻译行为。221项Python检查通过，原桌面38项及Writer独立5项通过。详见 [Writer验收](reports/PAPERWRITER_ACCEPTANCE_20261121.md)。Hunter细化仍暂停；本次按用户要求从MedStat转到Writer。下文旧状态以本段及专项报告为准。


本地研发版，基于上游 `d3486d0` 审核版继续整合。统一 CLI、持久任务、HTTP 与桌面表单；统计只使用合成数据、不调用 LLM。Gemini 密钥及型号保持空白，手机端暂缓。

## 当前能力

| 入口 | 已接入范围 | 输入示例 |
|---|---|---|
| 项目与任务 | SQLite 持久化、状态、产物、显式重试、中断恢复 | CLI / 桌面 |
| PubMed | 有限检索、命中数与取得数、原始响应、RIS 导出 | `{"query":"anesthesia AND postoperative pain","limit":20}` |
| 相关性 | Pearson / Spearman；成对剔除缺失 | [statistics.json](examples/statistics.json) |
| 列联表 | 自动、Pearson 卡方、Fisher、Yates；RxC 条件 Monte Carlo | [categorical.json](examples/categorical.json) |
| 数值组间 | 两组 Welch / MWU / Cohen d；多组 ANOVA / Kruskal | [groups.json](examples/groups.json) |
| TableOne | 显式变量类型、分层/总体、非缺失分母、缺失数 | [tableone.json](examples/tableone.json) |
| 回归 | 含截距、数值预测变量、完整案例的 OLS / Logistic | [linear.json](examples/linear.json)、[logistic.json](examples/logistic.json) |
| GLM | Poisson/log、Gamma/inverse；无 offset/exposure | [poisson.json](examples/poisson.json)、[gamma.json](examples/gamma.json) |
| 预测评估 | 混淆矩阵、基础指标、ROC/AUC、Brier、等宽校准分箱 | [evaluation.json](examples/evaluation.json) |
| 连续插补 | Bayesian Ridge 多份插补；linear/ridge 单次；可选列均值 Rubin 合并 | [imputation.json](examples/imputation.json) |
| 扩展预测评估 | 等宽HL、DCA、新旧模型逐阈值二分类NRI及配对IDI；表格/曲线/JSON | [验收](reports/MEDSTAT_EXTENDED_ACCEPTANCE_20261121.md) |
| 写作 | 保留证据约束的单章节 Gemini 适配器；未配置时拒绝接收任务 | [write.json](examples/write.json)，未运行模型 |

桌面页面包含上述统计表单、运行/刷新/查看产物及 RIS 下载。TableOne 和四种回归提供表格，其余结果以 JSON 展示。写作暂由 CLI 接入，完整自然语言编排、写作证据自动提取、语义事实核验及完整多步写作 agent 未完成。

## 运行与验证

Python 3.11 以上，在本目录使用独立环境：

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m workbench create '研究问题'
.venv/bin/python -m workbench projects
.venv/bin/python -m workbench enqueue PROJECT_ID statistics examples/tableone.json
.venv/bin/python -m workbench run JOB_ID
.venv/bin/python -m workbench jobs PROJECT_ID
```

服务端安全配置至少 32 字符的 `WORKBENCH_ACCESS_TOKEN` 后运行：

```bash
.venv/bin/python -m workbench serve --port 8765
```

默认监听 `127.0.0.1`；浏览器访问本机端口并输入令牌。令牌仅保留在页面内存，不写浏览器持久存储。不要将此单所有者研发服务直接开放公网。

```bash
.venv/bin/python scripts/validate.py
# 桌面浏览器依赖与复现命令见 scripts/browser/README.md
```

当前验证证据集中于 [验收汇总](reports/ACCEPTANCE_SUMMARY.md)，任务状态见 [PROGRESS](PROGRESS.md)，架构见 [STRUCTURE_AND_CHANGES](STRUCTURE_AND_CHANGES.md)。历史变化见 [CHANGELOG](CHANGELOG.md) 和逐轮报告；整理前文档保存在 `reports/history/pre-desktop-20261120/`，不作为当前能力说明。

新增HTTP筛选批次冻结排除原因词表；旧批次保留自由文本。逐条决定与全部判断历史可分别导出CSV，详见 [CSV验收](reports/SCREENING_CSV_20261120.md)。

## 方法与行为边界

- TableOne 沿用全样本正态性选择及正态两组等方差 t 检验；独立 `group_numeric` 两组为 Welch。Gamma 保留 inverse 链接，系数不解释为 OR。
- 预测评估的 training/held_out/external 为用户声明；探索性 Youden 阈值不替换输入阈值；零分母 PPV/NPV/MCC 返回 null。HL、DCA、NRI、IDI 已完成12项有限合成检查及数值修复，见 [专项报告](reports/EVALUATION_EXTENDED_20261120.md)；尚未新增到统一页面，保留等宽分箱和逐阈值二分类NRI。
- 插补仅支持显式连续变量，缺失用 null，不自动识别 999。保留观测值与每份插补数据，种子为 42+i；无缺失返回原数据一份，单次插补无 MI 推断。合并限列均值，不是回归参数合并。
- 标题/PMID/DOI去重已接入CLI、统一任务、HTTP和桌面检索产物按钮，零LLM调用；默认冲突保留待人工核对。桌面可填写理由并保留/合并，生成新的历史可追溯产物，详见 [验收报告](reports/DEDUP_DESKTOP_20261120.md)。题名摘要筛选已接入独立评审令牌、人工checkpoint、双方锁定提交、揭盲裁决、规范化排除原因及JSON/CSV审计下载，见 [桌面筛选验收](reports/SCREENING_DESKTOP_20261120.md)。
- 写作仅允许显式批准的公开证据，字符预算 20000、单次请求、最多 3000 输出 token；引用 ID 检查不等于语义事实核验。当前未配置、未调用模型。

## 数据与资源

仅合成统计与公开写作证据；输入标记不能自动识别敏感信息。本版不用于真实病例，未完成临床验证或生产安全验收。项目目录权限 0700、数据库/产物 0600，磁盘未加密；分用户权限、敏感字段识别、保留期/删除及备份恢复仍待生产实现。

任务状态为 queued/running/completed/failed/needs_review。同项目同输入复用任务 ID，完成任务不能重复运行。失败/待复核任务通过 `retry JOB_ID --confirmed` 建立关联新任务；`recover` 使用跨进程锁识别中断任务，不自动重试付费调用。

`modules/` 保留原模块与许可，尚未整体迁移；`skills/` 为流程材料，未全局安装或全部启用。Zotero 组件仅完成语法检查，未连接用户桌面或写入文献库，现有互操作为 RIS。未自动推送 GitHub。

全文筛选已接入：从题名摘要最终纳入记录登记PDF/TXT或未取得状态，冻结原件/文本哈希与父阶段关联，重新人工批准，按页号及逐字摘录独立判断/裁决，导出JSON/CSV。全文阶段详见 [全文验收](reports/FULLTEXT_ACCEPTANCE_20261121.md)。

人工报告—研究多对多映射及单一来源链PRISMA计数已接入，可导出带版本哈希的JSON/CSV/SVG；未取全、缺失来源、待裁决或未确认映射均显式提示，不补伪零。数据库/注册库集合合并后重筛已接入；既有筛选分支直接汇总尚不支持，见 [映射与PRISMA验收](reports/STUDIES_PRISMA_20261121.md)。

多来源管理入口 `/sources`：登记已有PubMed检索或导入数据库/注册库书目JSON，冻结完整来源清单，创建增量版本并合并去重。保留原始来源位置和历史集合；新版本重新筛选，不自动复用旧判断。详见 [来源集合验收](reports/SOURCES_COLLECTION_20261121.md)。
