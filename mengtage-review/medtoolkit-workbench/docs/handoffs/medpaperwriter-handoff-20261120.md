# MedPaperWriter 开发交接 · 2026-11-20

## 最新交付 · 完整整合包（2026-11-21）

已整理research/deliverables/MedToolkit-desktop-20261121.zip，为独立完整源码包，无需历史增量ZIP。README/PROGRESS/NEXT_STEPS/验收摘要统一为当前状态，旧说明保留docs/history；三个handoff随包提供。新增scripts/start_local.py（本机令牌、强制空Gemini）和verify_package.py（SHA256清单校验）。保留旧模块、tests、examples、skills和合成报告；排除runtime、数据库、凭据、.git、虚拟环境及浏览器/Office运行时。

独立暂存目录中完整Python235项、桌面38+7+3=48项通过，另测从包外目录启动、4个页面、401、模型配置空白和重启后项目持久化。测试借用已有已验证依赖，未重新联网安装一套依赖；不把源码独立解压验证说成全新系统安装测试。完整包为新安装入口，现有真实项目升级前备份runtime并合并自己的修改，不自动覆盖人工数据。无GitHub推送，模型/手机限制保持。


## 最新接续 · Office兼容引擎实际排版验收（2026-11-21）

已用LibreOffice Writer 26.2.6.3实际DOCX→PDF渲染，逐页检查中英混排、65行跨页表格及长引用。修复writer_docx.py：A4页边距、正文段距、去掉空行叠加空段、按内容分配表格列宽、读取Markdown对齐、行禁止拆页、重复表头、长哈希9pt、页脚PAGE/NUMPAGES。合成压力稿由5页变4页，65行齐全且页码/字符/页面边界自动核对通过；实际下载普通稿及Hunter稿均为1页A4。

报告medtoolkit-workbench/reports/PAPERWRITER_OFFICE_20261121.md；前后DOCX/PDF和页图在reports/office-layout。新增脚本office_layout_fixture.py、office_render.py、check_office_layout.py。235项Python、Writer7+Hunter3桌面本轮通过，主桌面38项为上轮且源码哈希未变。临时LibreOffice运行时仅本地.office-tools，交付包不含运行时。

本轮包research/deliverables/MedPaperWriter-office-20261121.zip，基于hunter累计版本。当前已更新，不重复应用。这里验证的是LibreOffice，不是Microsoft Word/WPS；字体替代使不同客户端分页仍可能变化。模型和手机仍暂缓，无推送。


## 最新接续 · MedHunter原生证据绑定（2026-11-21）

/writer新增Hunter全文入口，由该批次真实人类裁决者令牌经/api/review/writer_candidates及writer_capture访问。仅已揭盲、全部全文裁决完成且研究映射有效的最终纳入报告可捕获。writer_hunter.py固定原文及报告/study/裁决/映射/来源/父版本绑定，Writer证据自动继承ID，进入章节审核及Markdown/Word/审计JSON。

全文裁决或映射更新使旧绑定拒绝继续审核/导出；须重新捕获新证据并审核新稿。父题名摘要修订保持既有全文历史父版本语义，页面提示父版本变化。study_ids限所选批次；不自动合并跨批次研究。原件和来源清单替换拒绝；作者仍判断摘录支持性。

完整235项Python、48项桌面本轮通过（38主工作台+7Writer+3Hunter→Writer）。报告medtoolkit-workbench/reports/PAPERWRITER_HUNTER_20261121.md；专项实际下载/截图在reports/writer-hunter-browser。包research/deliverables/MedPaperWriter-hunter-20261121.zip，基于statistics及此前累计版本。当前源码已更新，不重放补丁。

Hunter/Stat原生证据绑定现均完成本机合成验收；下文未绑定描述为历史。真实模型/双语、临床数据、Office排版、手机仍待验证或授权。Gemini空白，无推送。


## 最新接续 · MedStat原生证据绑定（2026-11-21）

/writer可选当前项目已完成的合成MedStat任务。core.py在统计完成时写入artifact_sha256与payload_sha256；writer_statistics.py验证项目/状态/哈希后冻结结果文本，进入既有摘录和证据包。native_statistics绑定贯穿作者审核、Markdown、Word与审计JSON；结果或输入被替换时拒绝审核/导出。统计公式和产物内容不变，任务result增加元数据。

旧任务无完成时哈希不能进入新绑定；相同payload会复用旧任务，当前可在新项目重做后引用，不伪造历史哈希。真实临床数据未授权接入，仍限合成。完整229项Python、原桌面38项和Writer7项本轮通过。报告medtoolkit-workbench/reports/PAPERWRITER_STATISTICS_20261121.md，证据reports/writer-browser/statistics-audit.json及writer-statistics.png。

包research/deliverables/MedPaperWriter-statistics-20261121.zip，基于Word及此前累计版本；本地已更新勿重放，其他副本按差异合并。Hunter原生绑定、真实模型、Office排版和手机仍待做；Gemini空白，无GitHub推送。以下Stat未绑定的历史描述由本节覆盖。


## 最新接续 · 固定版本Word导出（2026-11-21）

统一/writer新增“导出 Word（已保存原文）”。workbench/writer_docx.py基于python-docx 1.2.0，从固定稿件导出DOCX并同时返回审计JSON，记录版本、原JSON导出哈希、Word文件哈希和审核状态。中文/英文/特殊字符和证据引用保留，标准竖线Markdown表格转Word表格，其他语法按普通文本保留。草稿/历史版本标记明确；未保存修改不能导出。正文不翻译、不调用模型，旧独立应用导出/翻译路由不变。

完整225项Python通过，Writer Chromium6项通过，真实双下载并重新解析DOCX。原38项主工作台桌面结果为上一轮，源码哈希未变。本机无Word/LibreOffice，尚未验收Office排版渲染。报告medtoolkit-workbench/reports/PAPERWRITER_WORD_20261121.md；依赖更新requirements.txt及requirements-tested.txt。

本轮包research/deliverables/MedPaperWriter-word-20261121.zip，基于此前local-review累计版本。当前工作区已更新，不重放补丁。下文“统一Word未完成”由本节覆盖；Hunter/MedStat原生产物绑定、真实模型和双语生成仍待接。Gemini留空、手机暂缓、无推送。


## 最新接续 · 2026-11-21

用户重新授权本会话完善Writer。已完成手工零模型闭环：`workbench/writer.py` + `/writer`页面，公开/合成原文快照、逐字定位证据包、可排序提纲/章节、乐观锁版本、作者批准/返修、Markdown和审计JSON导出。修改正文或证据包必须新版本、重新审核；旧版批准留存。统一工作台令牌代表本机所有者；作者名为声明，不是多人独立身份。证据支持性仍需作者判断。

原文读取复用已完成的fulltext快照工具；当前入口为手工上传，没有自动绑定Hunter最终纳入集或study映射。旧正文第4节“全文仍是草稿”等依赖描述已过时：Hunter全文、study映射、多来源PRISMA已验收，但其向Writer的原生证据选择仍未接通。MedStat已完成扩展评估，写作统计证据的job/artifact绑定仍待做。

本轮额外修复旧参考文献格式路由的错误导入，两条真实函数体已隔离运行验证；未改变旧Word导出、自动翻译、SSE行为，未启动旧FastAPI全栈。统一新流程输出Markdown/JSON，未宣称已有统一Word导出。

完整检查163+58=221项Python通过，38项原桌面回归和5项Writer桌面通过。源码报告：`medtoolkit-workbench/reports/PAPERWRITER_ACCEPTANCE_20261121.md`。新增测试tests/test_writer.py、test_writer_http.py；桌面scripts/browser/writer.cjs，证据reports/writer-browser/。包为research/deliverables/MedPaperWriter-local-review-20261121.zip，含补丁/源码/报告/本handoff；基于MedStat-extended及之前累计接续版本，当前工作区已更新，不重放补丁。

后续按实际需求选原生Hunter/Stat证据绑定或统一Word导出；涉及旧版翻译/未批准内容策略先问用户。真实模型仍须明确解除Gemini留空并授权外部处理。手机暂缓，不推GitHub。以下为原始handoff，冲突处以上述最新状态为准。


当前统一工作台仅实现基于显式证据的单章节写作适配器；Gemini 配置保持空白，未做真实模型生成验收。旧版 MedPaperWriter 有独立 FastAPI 应用、提纲、章节审核、文件解析和 Word 导出代码，但尚未迁入统一工作台。本文件是代码核对后的开发交接，不代表旧版所有功能已通过运行验收。

## 1. 工作位置与约束

- 工作区：`/home/workspace/agents/agent-20261111-144433-e19368`。
- 当前源码：上述目录的 `medtoolkit-workbench/`。下文源码路径均相对此目录。
- 总交接：工作区 `research/medtoolkit-handoff-20261120.md`，最新状态以顶部更新为准；下方历史段落有已过时的未完成项。
- 上游比较基准：`d3486d0b6d7139ddbc4dd7f189567f3839c553b1`；不可变快照在工作区 `research/upstream-d3486d0/MedToolkit-d3486d0b6d7139ddbc4dd7f189567f3839c553b1/mengtage-review/medtoolkit-workbench/`。
- 本地已包含多轮修改，不要从上游覆盖，也不要重新叠加旧补丁。未获 GitHub 推送指令。
- Gemini 密钥及型号保持空白；不读取凭据，不换用旧版模型配置绕过此限制。测试使用 mock，不发真实请求。
- 手机暂缓；与旧产品行为冲突先问用户。允许继续本地实现、测试与文档整理。
- 用户本轮明确要求为 MedPaperWriter 写 handoff；本轮未修改 Writer 业务代码。

## 2. 当前实现边界

| 能力 | 代码入口 | 已实现范围 / 缺口 |
|---|---|---|
| 统一写作任务 | `workbench/core.py`、`workbench/__main__.py`、`workbench/server.py` | kind=`write`；统一任务持久化、执行、恢复和重试；HTTP 通过通用 `/api/jobs` 入队 |
| 入库前校验 | `workbench/adapters.py::validate_payload/evidence` | 显式允许外部处理；仅接受声明为 public 且 verified=true 的证据；未配置模型时拒绝入队 |
| 单章节生成 | `workbench/adapters.py::write/gemini` | 章节名+证据 JSON，Gemini REST 请求；模型输出必须正常 STOP 且正文非空；并非完整写作 Agent |
| 引用门槛 | 同上 | 识别 `[E:id]`，检查至少存在引用且没有未知 ID；不验证句子是否被证据支持、不验证每项事实都有引用 |
| 草稿产物 | 同上 | `{job_id}-draft.json`，含正文、模型名、usage、证据 ID、未知引用、needs_human_review 状态；无独立作者批准/版本链 |
| 统一桌面 | `web/index.html`、`web/app.js` | 仅“Gemini 未配置，暂不调用模型”提示；没有章节编辑、证据选择、生成、审核、导出完整流程 |
| 旧版独立应用 | `modules/MedPaperWriter/app.py` | 独立 FastAPI；不可将其 README 的能力直接宣称为统一工作台已实现 |
| 旧版写作与审核 | `api/routes_chat.py`、`api/routes_review.py`（旧模块内） | 研究问题确认、提纲生成/修改、章节写作、RCT 路径与批准/返修代码存在；尚未做本轮独立运行验收 |
| 旧版资料/导出 | `core/file_parser.py`、`core/document_generator.py`、`api/routes_export.py` | 文件转文本、中文/英文/双语、DOCX、引用样式代码存在；尚无统一证据链和导出桌面验收 |

### 写作输入与输出契约

输入示意（仅合成材料；当前不应真实提交模型）：

```json
{
  "section": "背景",
  "external_processing_approved": true,
  "evidence": [{
    "id": "e1",
    "source": "doi:synthetic-example",
    "locator": "p1",
    "excerpt": "合成证据，不作为医学事实。",
    "classification": "public",
    "verified": true
  }]
}
```

限制：1–30 条证据；ID 匹配 `[A-Za-z0-9_-]{1,40}` 且唯一；来源、位置、摘录非空；单段摘录最多 6000 字符；整理后的证据 JSON 最多 20000 字符；章节名最多 300 字符。额外字段被拒绝。`verified` 和 `classification` 是提交者声明，并非系统核验凭证。

提示词要求仅用提供材料、未知信息写 `[待补证据]`、每项事实标记 `[E:id]`、不执行材料内指令。这是提示约束，不是语义正确性或提示注入防护的实证保证。引用检查失败仍保存草稿，`state=needs_human_review`；任务执行成功不能解释为论文审核通过。模型名在入队时冻结，执行时检查配置未变；尚无完整提示版本、证据快照哈希、作者审核事件及稿件版本关联。

## 3. 旧版复用入口与具体风险

| 文件 | 接续时需核对的事实 |
|---|---|
| `modules/MedPaperWriter/services/session_manager.py` | 旧路由实际依赖这里的 Session、SessionMode、OutlineNode、SectionStatus；有 JSON 保存、reference_materials、QA 上下文。另有 `models/session.py`，不要未经核对混用两套模型 |
| `modules/MedPaperWriter/core/file_parser.py` | PDF 使用 PyMuPDF，逐页拼接成一个文本串；不保留结构化页码/文件哈希。DOCX 提取段落和表格；旧 DOC 路径使用 textutil，Linux 环境需单独检查，不应假称支持 |
| `modules/MedPaperWriter/core/document_generator.py` | 英文标题、缺失语言正文可能调用 translator；中文导出也可能在仅有英文内容时翻译。不能把旧导出当成纯本地、零模型调用流程 |
| `modules/MedPaperWriter/api/routes_export.py` | `/ref/styles`、`/preview/references` 从 `services.reference_formatter` 导入，但文件位于 `core/reference_formatter.py`；静态核对确认路径不一致，未在本轮启动路由复现 |
| 同上 | 进度导出 await 整个生成任务完成后才读取队列，当前代码不是生成过程中即时推送；完成后下载路由又调用生成器，需验证重复生成/翻译行为 |
| `modules/MedPaperWriter/core/llm_client.py`、`llm/client.py`、`legacy/` | 存在多个客户端及历史实现；先画清实际 import 链，不批量替换，不启动旧客户端来规避 Gemini 留空 |
| `modules/MedPaperWriter/README.md`、`tests/`、`test_export.py` | 是旧模块文档/测试资产；统一根目录验证脚本并不运行这些测试，不能拿统一测试总数替其背书 |

若要把“导出时自动翻译”改成“必须先人工触发翻译，导出只读已有稿件”，这是明确的旧行为变更，应先提出冲突让用户决定。错误导入等不改变产品语义的修复可直接完成并测试。

## 4. 与 Hunter / Stat 的边界

MedHunter 已完成题名摘要筛选：冻结方案与材料、人工 checkpoint、独立身份、双边提交后揭盲、最终裁决及追加修订、JSON/CSV 审计。排除原因词表已冻结；模型侧目前为导入结果，不代表真实模型运行。

2026-11-20 本轮在编写本 handoff 前，已经新增 `workbench/fulltext.py` 开发草稿，拟实现全文上传/文本快照/页码定位/父批次关联。但尚未接入 screening ledger、HTTP、桌面或测试，不能视为可用依赖，也不在上一轮已验收 ZIP 中。后续接手应先查看实际文件及调用关系，保留未完成工作。全文筛选、报告—研究映射与 PRISMA 尚不能宣称完成。

Writer 的拟议证据链：选定筛选版本 → report_id / study_id（研究映射需人工确认）→ 全文快照 → 具体摘录/页码 → 章节事实及引用 → 作者审核 → 导出版本。保留显式 ID，不靠题名再次匹配。进入最终纳入集不等于摘录足以支持任意论断。

MedStat 目前统一入口只接受合成数据验收。将统计结果用于 Writer，应建立明确的 analysis job/artifact/hash 绑定，不把任意数值文本标成“已核验”；真实病例资料和外部模型处理不在当前授权范围。

## 5. 建议下一步与完成标准（待实施）

1. **先建立证据包，保持零模型调用。** 人工选定报告/全文版本、摘录、位置及核验人；保存不可变快照和哈希。校验摘录确在对应文本位置存在，并单独保留人工支持性判断。验收错文件、错页、未知 ID、修订历史、跨项目访问及材料替换。
2. **做可编辑章节与作者 checkpoint。** 人工制定/修改提纲、选择本节证据、保存草稿及版本，作者显式批准后才标为已审核；修改正文或证据后需新版本/重新审核。先支持手工稿及 mock 输出，不依赖 Gemini 配置。
3. **补引用与事实覆盖面检查。** 未知/缺失/格式错误引用、无来源数字、撤换证据导致的旧引用失效进入待复核；展示“论断—摘录—来源”对照，语义支持性保留人工判断。不要把 ID 存在改名为事实核验通过。
4. **接导出与桌面验收。** 冻结稿件版本，正文引用与文末文献一一对应；明确未批准章节处理策略；验证表格、中文、英文、特殊字符与下载。旧版自动翻译/未批准内容导出策略先核对，涉及改变旧行为再问用户。
5. **最后才接真实模型。** 等用户明确解除 Gemini 留空要求、配置模型及同意外部处理后，记录模型/参数/提示版本/证据哈希/运行 ID/usage/失败重试。继续要求作者审核，真实输出另做验收。

可先修旧模块已确认的导入错误并加隔离测试，但不应因此把旧应用整体迁入或新增第二套统一会话状态。全文未就绪时可用合成快照测试证据包，不宣称已接通 Hunter 全文产物。

## 6. 验证事实与复现

上一轮完整结果：107 项基础/HTTP/单元 + 58 项统计 = 165 通过；Chromium 28 项通过。来源为 `reports/validation-summary.json`、`reports/validation-*.log`、`reports/browser/summary.json`。这些是上一轮结果，不覆盖本轮新增的未接入全文草稿，也不覆盖旧 Writer 的完整生成/导出流程。

现有 Writer 相关测试：`tests/test_write_preflight.py`（不合法输入不入库）、`tests/test_core.py`（拒绝非公开证据、mock 未知引用）、`tests/test_http_workflow.py`（HTTP 非法写作输入）。浏览器仅覆盖未配置提示。`scripts/validate.py` 扫描根目录 tests，并运行统计验收，不运行旧 Writer 内部 tests。

本 handoff 整理时重新执行以下命令，1 项通过，未调用模型：

```bash
cd /home/workspace/agents/agent-20261111-144433-e19368/medtoolkit-workbench
.venv/bin/python -m unittest discover -s tests -p test_write_preflight.py -v
```

有代码修改后再按范围执行根目录测试及桌面验收；仅改 handoff 无需重新跑全部统计。全面复现入口为 `.venv/bin/python scripts/validate.py`；浏览器配置见 `scripts/browser/README.md`。

上一轮累计包：工作区 `research/deliverables/MedToolkit-d3486d0-screening-csv-20261120.zip`；SHA256 `4d13289448f28ad0677c3b65523b665f3b5e6067c2e13ad292579396ecfc09f9`。当前源码优先于旧包；不要据此包推断本轮全文已完成。

## 7. 新会话可直接使用的任务说明

> 先读本工作区 AGENTS.md 和 research/medpaperwriter-handoff-20261120.md，核对 medtoolkit-workbench 当前文件。继续 MedPaperWriter，优先构建不可变证据包、章节版本与人工审核闭环，复用统一 Store/项目权限；核对旧 Writer 实际路由及导出行为。Gemini 密钥和型号保持空白、使用合成材料和 mock、手机暂缓、不推 GitHub、旧行为冲突先询问。保留 MedHunter 未完成的 fulltext.py 草稿，不将其视为已验收依赖。交付时明确代码已实现、测试已覆盖和仍待完成的边界。
