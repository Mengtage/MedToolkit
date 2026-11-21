# MedToolkit handoff · 2026-11-20

## 最新交付 · 完整整合包（2026-11-21）

已整理research/deliverables/MedToolkit-desktop-20261121.zip，为独立完整源码包，无需历史增量ZIP。README/PROGRESS/NEXT_STEPS/验收摘要统一为当前状态，旧说明保留docs/history；三个handoff随包提供。新增scripts/start_local.py（本机令牌、强制空Gemini）和verify_package.py（SHA256清单校验）。保留旧模块、tests、examples、skills和合成报告；排除runtime、数据库、凭据、.git、虚拟环境及浏览器/Office运行时。

独立暂存目录中完整Python235项、桌面38+7+3=48项通过，另测从包外目录启动、4个页面、401、模型配置空白和重启后项目持久化。测试借用已有已验证依赖，未重新联网安装一套依赖；不把源码独立解压验证说成全新系统安装测试。完整包为新安装入口，现有真实项目升级前备份runtime并合并自己的修改，不自动覆盖人工数据。无GitHub推送，模型/手机限制保持。


## 接续更新 · Office实际排版（2026-11-21）

用LibreOffice26.2.6.3实际渲染DOCX→PDF，已修复统一writer_docx的Letter默认、空行叠加段距、表格跨页拆行、等列宽、数值对齐、长哈希孤立字符和无页码。改为A4、正文11pt/1.2行距、按内容列宽、重复表头/禁止行拆分、元数据9pt、页码域。65行中英文压力稿5页→4页，全部行/字符/页码/边界检查通过并逐页目视；实际普通稿与Hunter稿另渲染为1页A4。

235项Python、Writer7+Hunter3桌面本轮通过；主38项是上轮，哈希未变。报告reports/PAPERWRITER_OFFICE_20261121.md，前后样稿/PDF/截图在reports/office-layout。运行时独立解包至.office-tools，不修改系统、不放入ZIP。

交付research/deliverables/MedPaperWriter-office-20261121.zip，1344892字节，SHA256 3f3db8a6129a18cf54e3e1bb286c1c2f05a31419416cdf706f3cab3500c763d1；基于hunter累计版本，补丁和源码哈希/ZIP核对通过，当前代码不重复应用。专项handoff已更新。实际Microsoft Word/WPS、不同字体分页、模型与手机仍未验收；无推送。


## 接续更新 · Hunter到Writer原生全文证据（2026-11-21）

人类裁决者真实令牌可将已完成全文裁决且研究映射有效的最终纳入报告固定到Writer，原文/报告/研究ID与裁决/映射/来源/父版本贯穿证据、作者审核和Markdown/Word/审计JSON。全文裁决/映射更新使旧绑定停止新审核/导出，原已导出文件不覆盖；父阶段更新沿用选定全文批次的固定历史父版本。原件或来源清单替换拒绝，模型/外人/跨项目/未揭盲等拒绝。

235项Python、48项桌面（38+7+3）本轮通过。包research/deliverables/MedPaperWriter-hunter-20261121.zip，469805字节，SHA256 8657e589ddad782c9b2cd2be603ba06be0a1e43df86f7648e28e56d0d8d1d98e；基于statistics累计版本，dry-run、实际应用字节比较、源码验收哈希及ZIP完整性通过。源码已更新，不重放。专项handoff及reports/PAPERWRITER_HUNTER_20261121.md已更新，实际DOCX/JSON/截图见reports/writer-hunter-browser。

本机合成环境下Hunter/Stat证据→Writer章节/版本/审核/导出已接通。真实模型与双语、临床数据、Office排版和手机仍待验证或授权；Gemini空白，无推送。


## 接续更新 · MedStat到Writer原生证据（2026-11-21）

已完成统计任务完成时哈希、Writer捕获、全文结果快照及native_statistics关联；逐字摘录/证据包/稿件/作者审核/Markdown/Word/审计JSON贯通。仅合成数据；旧任务没有完成时哈希不得追认，相同payload复用旧任务，可新项目重算后引用。原统计公式及产物内容不变，core任务result新增输入/结果哈希。Hunter原生绑定仍待做。

完整229项Python，原桌面38项+Writer7项本轮通过。包research/deliverables/MedPaperWriter-statistics-20261121.zip，398658字节，SHA256 0e2818044b5b48c13e7976a604d7842a1d4b7399e2fa01d59a4beb7b5c2eb16e；基于Word累计版本，补丁dry-run、应用字节比较、ZIP及源码测试哈希核对通过。专项handoff已更新，报告reports/PAPERWRITER_STATISTICS_20261121.md。当前源码已更新，不重放补丁。Gemini空白、无真实调用、手机暂缓、无推送。


## 接续更新 · PaperWriter固定版本Word导出（2026-11-21）

/writer新增Word已保存原文导出，配套审计JSON绑定稿件/审核/文件SHA256；支持中英文、引用、标准竖线Markdown表格，保留草稿和历史标记。新增writer_docx.py及python-docx依赖，旧版翻译逻辑不变。完整Python225项、Writer桌面6项通过，实际下载后重新打开解析；未做Office排版渲染验收。原38项桌面回归为上轮结果，源哈希未变。

包research/deliverables/MedPaperWriter-word-20261121.zip，562087字节，SHA256 351e61fd0a9ea292369ebbfa68047cb1beef3f43eb949d1051d9c10a17017af6。基于local-review及此前累计版本；补丁dry-run、应用字节对比、ZIP及测试源码哈希核对通过。当前工作区已有修改；其他副本先装依赖、按差异合并。专项handoff已更新，报告reports/PAPERWRITER_WORD_20261121.md。Hunter/Stat原生证据绑定、真实模型、双语仍待接；Gemini空白，手机暂缓，无推送。


## 接续更新 · PaperWriter本地证据与作者审核闭环（2026-11-21）

用户要求根据Writer handoff完善。已实现workbench/writer.py、web/writer.html/js、统一/writer入口：手工上传公开/合成原件、固定文本及文件哈希、精确页码摘录、人工支持性说明、证据包、可编辑/排序章节、版本乐观锁、作者批准/返修、Markdown及审计JSON下载。正文/证据更改后重新审核，历史批准不覆盖。审核身份为本机所有者，署名为声明；没有独立作者令牌。

旧参考文献路由两处错误导入修复，并隔离执行真实函数体验证；不改变旧Word/自动翻译/SSE。新增手工流程未接Hunter纳入/study映射或MedStat产物绑定，未配置/调用模型；统一Word导出和旧FastAPI全栈尚未验收。沿用Gemini空白、手机暂缓、无推送。

完整Python 163基础/HTTP/单元+58统计=221通过；原Chromium38项回归和Writer独立5项通过。报告medtoolkit-workbench/reports/PAPERWRITER_ACCEPTANCE_20261121.md；专项handoff research/medpaperwriter-handoff-20261120.md已加顶部最新更新。补丁dry-run、实际应用字节对比、源码哈希、ZIP完整性通过。

增量包research/deliverables/MedPaperWriter-local-review-20261121.zip，SHA256 937e98242e5286ff29f05dce92e41a8fcedceda1d797ff87eacf416f095e3d7b，517568字节，29项源码/证据文件。基于MedStat-extended及以前累计改动；当前工作区已有修改，无需重放，其他LLM共编副本须按差异合并。无须重开会话。


## 接续更新 · MedStat扩展预测评估完成（2026-11-21）

用户最新要求暂停MedHunter细化，按handoff完善MedStat；此前“MedStat交其他LLM”的分工由本次明确授权覆盖。已新增独立prediction_evaluation_extended适配器和统一桌面入口，接入HL、DCA、NRI、IDI，支持DCA曲线/逐阈值数表、分组表、配对比较及JSON下载。原基础prediction_evaluation输出不变；沿用旧版等宽HL分组、逐阈值二分类NRI、配对IDI公式，DCA阈值1保留null。阈值显式指定、旧新预测逐行配对由用户确认，非有限数及不完整配对在持久化前拒绝。

修复旧版MedStat模板直接对null调用toFixed导致的渲染错误；HL/IDI不可计算显示N/A，统一界面显示不可计算。未改旧统计公式、Writer或Hunter业务代码；Gemini保持空白、无真实模型调用、手机暂缓、无GitHub推送。

验证：151项基础/HTTP/单元+58项统计=209项通过，Chromium桌面38项通过；含HL有理数手算、独立DCA净收益、IDI配对SE、模型交换符号与行序不变性。统一界面通过实际HTTP和浏览器验收；旧模板只隔离执行实际渲染函数并stub Plotly，未启动旧Flask全栈。仅合成数据验收。

专项handoff：research/medstat-handoff-20261121.md；报告medtoolkit-workbench/reports/MEDSTAT_EXTENDED_ACCEPTANCE_20261121.md。增量包research/deliverables/MedStat-extended-20261121.zip，SHA256 6eadab187daaaf7b2b310a34c99afdd5bb0cae3f039b908387c85ea7a8a3346d，450389字节、25项源码/证据文件。包内含MEDSTAT_HANDOFF.md、应用说明、文件哈希、补丁和截图。基于已有sources及之前累计修改；源码已更新，无需重放；并行副本须合并共享文件差异。源码哈希、补丁dry-run、实际应用逐字节比较及ZIP完整性已核验。

本轮核心缺口已完成，无需重开对话。后续只按成员实际使用反馈推进；不默认恢复MedHunter精细化。旧版Flask完整浏览器验收、真实临床数据验证尚未完成；改变HL分组或NRI统计口径须先征询成员。

## 接续更新 · 多来源清单与增量集合完成（2026-11-21）

继续MedHunter，新增workbench/sources.py、web/sources.html/js、tests/test_sources.py及test_sources_http.py。独立管理员页面/sources可登记当前项目已完成的PubMed检索（保留原产物哈希、实际检索式及任务创建时间），或人工确认数据库/注册库公开书目JSON。每个来源冻结名称、类型、检索式、ISO时间、命中/下载/完整性和覆盖说明；导入完整性是人类声明，非独立验证。

来源集合显式选择本轮全部source_id，支持父集合关联的增量版本、旧版保留及请求幂等；每条原始记录保留来源ID/序号/快照哈希。先合并原始记录再复用标题/PMID/DOI去重及冲突复核；新集合重新人工checkpoint和筛选，不直接相加旧筛选分支、不自动复用旧判断。上限50来源、合计1–1000原始记录；单来源导入内容2MB，集合10MB。零结果来源可登记但全空集合不建筛选；其他网站/引文追溯来源、RIS/CSV解析和外部数据库原生API未接。

PRISMA核对每个来源文件及原生检索原件哈希，保留筛选记录→去重组→来源原始位置；JSON/CSV/SVG显示逐来源信息。命中数是各检索次数求和、未去重；任一来源未知则总命中/未下载为null，任一未取全则局部标记。单来源旧流程不变。source_collection产物依赖source_runs/source_collections表登记；资料原件仍由Store保存。仅局部修改server/prisma/index/studies网页及浏览器脚本，未改Writer/Stat业务代码。

完整142基础/HTTP/单元+58统计=200通过；Chromium35项通过。新增10后端、2HTTP、2桌面流程。报告medtoolkit-workbench/reports/SOURCES_COLLECTION_20261121.md。合成桌面例：PubMed导入1/命中2，注册库导入2/命中2，集合原始3条、重复1条、筛选2条；图仍标部分检索。证据reports/browser/source-collections.png、sources-prisma-*。大于1MB的有效JSON导入与2MB内容拒绝另有HTTP检查。

本轮增量包research/deliverables/MedHunter-sources-20261121.zip，SHA256 204344d0294405ddcf37cd9bda0a0cd4021c4ddac97e114ee876f915ef67cd3f。基准是已经依次包含screening-csv、fulltext、studies-prisma修改的源码；打包工具按上述层次回查未在上一增量包出现的旧文件，避免将既有index.html误作新文件。dry-run、实际应用逐字节比对、ZIP完整性和源码哈希核对通过。当前工作区已有改动，不重放补丁，并行修改须按差异合并。

下一步优先增量集合差异预览，再实现旧判断复用的人工确认及方案/材料一致性校验。不能把重复来源或旧分支简单求和，也不能在背对背筛选前把旧人类理由泄露给模型。Gemini保持空白，手机暂缓，无真实模型或外部数据库新调用，无GitHub推送。

## 接续更新 · 人工研究映射与单来源链PRISMA完成（2026-11-21）

本轮继续MedHunter，新增workbench/studies.py、prisma.py、web/studies.js和tests/test_studies_prisma.py，局部接入screening_http/server/独立筛选页面。仅指定人类裁决者可确认每篇最终纳入报告的study_ids（支持多对多）、理由、页号和逐字摘录。映射追加版本、携带裁决与映射事件尾防止覆盖；裁决修订使旧映射失效。研究ID仅在当前选定批次内计数，不做跨批次全局归并。

PRISMA预览逐级核对选定检索/去重/复核来源哈希与数量守恒，区分records/reports/studies、未下载、未取得与全文排除。父批次后续变化仍使用子批次固定的历史父版本并提示。来源缺失/变化、部分检索、待裁决/映射显示局部/未知，不填伪零；全排除或全未取得时可由题名摘要批次直接生成视图。每次导出保存JSON快照，支持CSV和自绘SVG，均带报告哈希/快照标识。

参考官方PRISMA流程图说明 https://www.prisma-statement.org/prisma-2020-flow-diagram；本实现仅单一选定来源链计数，不代表整个综述来源汇总或PRISMA合规认证。未改Writer/Stat业务代码；Gemini空白、零调用、手机暂缓、无GitHub推送。

完整130基础/HTTP/单元+58统计=188通过；Chromium33项通过，新增14项后端及2项桌面。报告medtoolkit-workbench/reports/STUDIES_PRISMA_20261121.md，图与实际导出在reports/browser/prisma-*，映射截图study-mapping.png。示例两篇报告属于同研究，计数reports=2、studies=1；多对多、旧版本失效、未知前段计数、全排除/全未取得等已测。

增量包research/deliverables/MedHunter-studies-prisma-20261121.zip，基于上一轮MedHunter-fulltext-20261121.zip，SHA256 af754f454df2ce3884bde078bf2001e127064425f391a594c405f1af32a846ed。补丁dry-run、实际应用逐字节核对、ZIP完整性通过。当前工作区已包含修改，不重放补丁；并行修改先核对再合并。

下一步是综述级多来源清单、跨检索去重与版本选择、跨批次report/study关联及增量检索汇总；不能简单相加多个分支。旧版study映射/PRISMA未实现描述均由本节覆盖；多来源汇总仍未实现。当前UI导出逐次产生不同snapshot_id，但相同预览共用report_sha256，三格式按此关联。

## 接续更新 · MedHunter全文桌面闭环完成（2026-11-21）

用户已将MedPaperWriter和MedStat分交另外LLM，本会话继续MedHunter。此前fulltext.py草稿现已接入并验收：父批次全部裁决后，指定人类为最终纳入记录登记PDF/TXT或未取得原因；固定文件/页文本哈希、提取版本、父记录/裁决/取得事件关联；重新人工checkpoint，双方按页号和逐字摘录独立提交，揭盲后人工裁决及JSON/CSV导出。未取得全文单独记录，全部未取得不建空子批次，可下载取得登记JSON；后续父裁决改变不覆盖原事件/子批次，页面提示父版本变化。

新增workbench/fulltext.py、web/fulltext.js、tests/test_fulltext.py；局部修改screening.py、screening_http.py、screening_exports.py、server.py及独立筛选网页。未改Writer/Stat业务代码。PDF依赖本机pdfinfo/pdftotext，5MB原件/1MB文本/200页段，无OCR；TXT编号不是PDF物理页。摘录匹配不是语义支持性判断。默认模型空白，零调用，手机暂缓，无推送。

完整116项基础/HTTP/单元+58统计=174通过；Chromium31项通过。新增9项后端及3项桌面流程；PDF为后端合成文件解析验收，桌面TXT贯通。报告medtoolkit-workbench/reports/FULLTEXT_ACCEPTANCE_20261121.md，证据reports/browser/fulltext-*及synthetic-fulltext.txt。父批次所有纳入后来改为排除，旧取得历史仍可下载；源文件及取得链篡改拒绝已覆盖。

本次交付是范围限定的增量包research/deliverables/MedHunter-fulltext-20261121.zip，基于此前MedToolkit-d3486d0-screening-csv-20261120.zip，而非直接基于d3486d0；SHA256 dad1a1b9335cbac990142979727705bc648e33589065110bc860e8875ad878ce。patch dry-run、实际应用字节比对及ZIP完整性通过。当前工作区已有全部改动，不重复应用；其他副本按差异合并，勿覆盖其他LLM的共享文件修改。

下一步：人工report→study映射与PRISMA。尚未实现跨批次报告归并/研究计数、完整PRISMA流程图、真实LLM运行器。NEXT_STEPS已更新。旧MedPaperWriter handoff中“fulltext.py草稿未接入”是当时状态，本节覆盖该依赖状态，但Writer自身未因此完成证据包集成。

## 接续更新 · MedPaperWriter 独立交接（2026-11-20 晚）

用户要求单独整理 Writer handoff，见 `research/medpaperwriter-handoff-20261120.md`。已核对统一单章节适配器、旧版路由/导出/会话实现、验证边界及下一步；本次未改 Writer 业务代码。定向写作入库前校验测试 1 项通过，无模型调用。

此前继续全文阶段时新增 `medtoolkit-workbench/workbench/fulltext.py`，目前仅开发草稿，尚未接入筛选账本/HTTP/桌面或通过测试；不在上一轮 screening-csv 已验收包中，不应把该模块或完整全文流程标为完成。继续 Hunter 时需接续这份未完成代码，勿覆盖。

## 接续更新 · 排除原因与CSV审计已完成

用户“继续”后完成原因词表及CSV。新增workbench/screening_exports.py；新HTTP批次把reason_codes/reason_codebook_version冻结到protocol并纳入哈希，在checkpoint展示。排除必须有有效代码及具体理由，非排除不能带代码；旧批次保持自由文本，不追填。默认8类，API可显式配置自定义词表。

独立筛选页新增screening-decisions.csv（每条记录、双方意见、最新最终结论、pending、来源与事件哈希、模型名/运行ID）和screening-history.csv（独立提交与每次裁决/修订）。CSV仅揭盲后指定人类裁决者可导出，UTF-8 BOM，正常处理引用和换行，公式样式文本加单引号保护；JSON保留原文与完整事件。新单元测试6项、浏览器1项，旧权限测试扩展CSV。

完整107项基础/HTTP/单元＋58统计＝165通过；Chromium28项通过，源码哈希核对无差异。报告reports/SCREENING_CSV_20261120.md，截图及两份合成CSV、最终JSON在reports/browser/。下一步全文快照、跨阶段父记录关联、报告—研究映射与PRISMA；NEXT_STEPS中写明待实现结构，不能把CSV条目计数当作研究数或完整PRISMA。

最新累计包research/deliverables/MedToolkit-d3486d0-screening-csv-20261120.zip，SHA256 4d13289448f28ad0677c3b65523b665f3b5e6067c2e13ad292579396ecfc09f9；patch dry-run、实际应用字节核对、ZIP完整性通过。Gemini仍空白、无真实模型调用、手机暂缓、未推送GitHub。

## 接续更新 · 独立评审身份与筛选桌面已完成

用户再次“继续”后，已接入题名摘要人工checkpoint、独立筛选页面、服务端角色/批次权限、揭盲裁决与审计JSON下载。新增workbench/review_access.py、screening_http.py、web/screening.html/js；工作台可创建/撤销human/model随机令牌，数据库只存令牌摘要；评审端/筛选接口从令牌确定actor，拒绝请求体冒用、跨批次、普通评审读取项目产物和管理员令牌直接充当评审。

仅已完成冲突处理的去重产物可准备批次。作者可核对冻结标准、哈希与题名后批准；双方独立提交锁定后才由指定人类裁决者揭盲。原始判断与追加修订保留，裁决页显示题名摘要、双方意见、已有最终结论；JSON导出包括pending_final。模型侧仍仅导入结果，无真实模型调用，Gemini空白；不保证手工导入的模型来源真实性。

验收101项基础/HTTP/单元＋58统计＝159通过；Chromium27项通过，新增两个BrowserContext模拟人类/模型的四项流程；源码/截图哈希匹配。报告reports/SCREENING_DESKTOP_20261120.md，截图reports/browser/screening-adjudication.png，合成审计导出reports/browser/screening-audit.json。测试凭据不写日志或审计导出。

权限边界为本机HTTP，管理员、文件所有者和直接CLI/数据库仍受信任；哈希链无外部锚定，未验证生产部署或HTTPS网关。旧CLI声明actor是管理入口，不能当成受限评审认证。手机暂缓。

下一步优先补规范化排除代码及CSV导出，再做全文快照/定位、研究—报告关联与PRISMA；真实模型运行器需后续配置授权。NEXT_STEPS已更新第2/3步及第4步JSON部分完成。

最新累计包research/deliverables/MedToolkit-d3486d0-screening-desktop-20261120.zip，SHA256 40389d3183e0e47ae613ef716498d96b198c0751b9e480677c533105802142df；patch dry-run、实际应用逐字节核对、ZIP完整性通过，未推送GitHub。

## 接续更新 · 桌面去重闭环已完成

用户“继续实施”后，完成NEXT_STEPS第1步：统一任务新增deduplicate/dedup_review，HTTP /api/dedup，桌面检索产物“去重并复核”，冲突理由必填、保留/合并生成新任务和产物，全部raw_records与历史版本保留。输入绑定source_sha256，入队/执行均核对，同输入复用任务；跨项目/非法路径拒绝，传递合并不能违背同分支既有保留决定。

文件workbench/dedup_jobs.py及web/app.js等已更新。报告reports/DEDUP_DESKTOP_20261120.md；当前95项基础/HTTP/单元＋58统计=153通过，Chromium23项通过，截图reports/browser/dedup-review.png。无LLM调用，PubMed仍为合成传输fixture，手机暂缓。

支持从旧产物另起复核分支，不自动选择唯一最终文献集；下一阶段checkpoint应要求作者选择并冻结具体产物。当前候选按原记录对呈现，关联候选保留逐对历史。尚未接入筛选checkpoint页面和独立评审认证，下一步为NEXT_STEPS第2/3步。

最新累计包research/deliverables/MedToolkit-d3486d0-dedup-desktop-20261120.zip，SHA256 885bf157e6f7f7e05af0ce641f3d1a53a28af3cf42408592456e3c5aa38e56bc；patch dry-run、实际应用比对和ZIP完整性通过，无推送。

## 接续更新 · 默认规则确认与下一步计划

2026-11-20 16:54用户回复“可以。完成后计划下一步”，确认同标题但PMID/DOI冲突保留待人工核对。去重API/CLI默认review，已同步当前文档；历史待确认描述不再有效。

下一步计划已写入medtoolkit-workbench/NEXT_STEPS.md：优先将去重及冲突处理接入统一任务/HTTP/桌面，再接人工checkpoint与独立筛选界面、身份权限、裁决与审计导出、全文和PRISMA。真正多评审使用前须完成独立认证与权限；Gemini空白、手机暂缓继续有效。

本轮仅落实确认的默认值与制定计划，不代表上述下一阶段已经实现。累计包为research/deliverables/MedToolkit-d3486d0-review-confirmed-20261120.zip。

## 接续更新 · 统计核验与筛选审计（2026-11-20）

- 用户新授权：MedStat继续核验；MedHunter标题+唯一码（PMID/DOI）去重不使用LLM；筛选前人工checkpoint，人类作者与LLM背对背筛选，过程可追溯。
- MedStat已修复HL遗漏非事件项、IDI未用配对差值方差、DCA阈值1伪零值；补NRI/IDI/DCA输入验证。保留等宽HL和逐阈值二分类NRI，未新增到统一页面。12项反例修复前8失败3报错，修复后全通过。详见reports/EVALUATION_EXTENDED_20261120.md。
- 新增workbench/deduplication.py及CLI，保留raw_records、规范化键、合并组、匹配理由及冲突候选。默认冲突策略尚未获回复：已询问“同标题但唯一码冲突，是否保留待核对”；必须显式传review/title_wins，现有检索按钮/旧Hunter行为尚未改。
- 新增workbench/screening.py及CLI：冻结快照和方案、指定人类批准、双方提交锁定、揭盲、人工最终确认、追加修订；题名摘要阶段原型，尚无独立账号认证，actor为声明身份，不宣称真实多人盲法。未配置/调用模型。全文与PRISMA、桌面界面待接入。详细设计reports/SCREENING_TRACEABILITY_20261120.md。
- 当前完整验证87项基础/HTTP/新增单元＋58统计=145通过。当前validation-summary.json哈希已核对。前轮20项桌面通过记录保留，不把新增CLI当桌面已测。
- 最新累计包research/deliverables/MedToolkit-d3486d0-review-audit-20261120.zip，SHA256 8b2ef130bb98c94b40f35a61e214652ce99247c59b63d5039b5b4adf292ce917；dry-run、实际应用文本比对、ZIP完整性均通过。无推送。

## 接续更新 · 桌面验收完成（2026-11-20 16:29 CST）

本节覆盖下文同名旧状态；原记录保留供追溯。

- README、PROGRESS、STRUCTURE_AND_CHANGES、reports/ACCEPTANCE_SUMMARY 已整理为当前状态，整理前版本保存在 reports/history/pre-desktop-20261120/。
- 真实 Chromium 159.0.8154.6（无头、1440×1000）20项流程检查通过，涵盖14个统计方法、鉴权、项目切换/持久化、错误提示、TableOne/回归表格、RIS下载；报告 reports/DESKTOP_ACCEPTANCE_20261120.md、原始证据 reports/browser/。
- 修复桌面回归长小数表格溢出：仅 ≥900px 的CSS横向滚动及单元格间距，数值、统计和旧默认策略不变。手机保持暂缓。
- 浏览器脚本 scripts/browser/acceptance.cjs，隔离服务 scripts/browser/server.py，复现见 scripts/browser/README.md。开发依赖 .browser-tools/ 不进入交付；缺库只在项目内解包，未改共享服务。
- PubMed使用合成出站响应，实际运行解析/Store/HTTP/RIS链路；不算本轮在线PubMed验收。Gemini子进程两项配置强制空白、零调用。
- 原121项Python验证未重复运行；与 validation-summary.json 的被测源码哈希逐项核对无差异。网页和浏览器脚本另有哈希。
- 最新累计交付 research/deliverables/MedToolkit-d3486d0-desktop-20261120.zip；SHA256 728c149de48aed10dec814df99fbdf58e82159967a42b320d19e9d86a0eb2780。基准patch dry-run及实际应用后文本字节比对、ZIP完整性均通过；PNG截图在files/内单独复制。
- 无git可执行程序，未提交/推送。下一步转入证据提取/引用核验与HL/DCA/NRI/IDI独立验收；与旧版行为冲突先问用户。本轮优先的文档整理及桌面验收已完成。

## 目标与用户约束

继续完善 Mengtage/MedToolkit。用户已持续授权本地开发、测试和统计错误修复。Gemini 密钥、型号保持空白；手机端暂缓；与旧版行为冲突先问用户，已授权的统计错误修复不用重复询问。统计不调用LLM。仅用合成数据验收，不能宣称支持真实病例或完成临床验证。不读取、打印、提交凭据，保留第三方许可。未获得本轮GitHub推送指令，不自动推送。

## 当前权威工作位置

- 工作区：`/home/workspace/agents/agent-20261111-144433-e19368`
- 当前源码：`medtoolkit-workbench/`，所有接续改动已在此，不需要重新应用补丁。
- 原始交接与逐轮记录：`research/medtoolkit-next-session.md`，保留了历史版本，不应将开头的旧状态当作当前状态。
- 上游核对基准：GitHub main `d3486d0b6d7139ddbc4dd7f189567f3839c553b1`，关注仓库内 `mengtage-review/medtoolkit-workbench/`。
- 不可变上游快照：`research/upstream-d3486d0/MedToolkit-d3486d0b6d7139ddbc4dd7f189567f3839c553b1/mengtage-review/medtoolkit-workbench/`。
- 上游7个变更源文件已同步，记录 `medtoolkit-workbench/reports/upstream-sync.json`；同步前备份 `research/medtoolkit-pre-sync-20261120/`。
- 当时环境无git可执行程序，使用GitHub归档下载并逐文件核对。没有提交/推送；旧git HEAD为46113fb，不能据此判断当前源码内容。新会话可重新检测工具，但不要重置工作树或用上游覆盖本地。

## 已接入的统一能力

统一CLI、持久任务、HTTP和桌面表单支持：

| 任务方法 | 范围 | 适配器 |
|---|---|---|
| pearson / spearman | 成对缺失剔除、相关性 | workbench/adapters.py |
| categorical_auto / chi2 / fisher / yates | 列联表，保留旧自动选择；RxC条件Monte Carlo | workbench/categorical.py |
| group_numeric | 两组Welch/MWU/Cohen d；多组ANOVA/Kruskal | workbench/groups.py |
| tableone | 显式变量类型、分层/总体、缺失分母；保留旧检验策略 | workbench/tableone.py |
| linear_regression / logistic_regression | 数值预测变量、含截距、完整案例、设计秩检查 | workbench/regression.py |
| poisson_regression / gamma_regression | Poisson/log；Gamma/inverse；无offset/exposure | workbench/glm.py |
| prediction_evaluation | 混淆矩阵、基础指标、ROC/AUC、Brier、等宽校准 | workbench/evaluation.py |
| mice_imputation | 连续插补、多份Bayesian Ridge/单次linear或ridge；可选列均值Rubin合并 | workbench/imputation.py |

仍有项目/任务持久化、重试与恢复、PubMed有限检索、原始来源保存、RIS导出。写作仅单章节Gemini适配器，配置未填写，未做真实模型调用。HTTP非法输入防护和写作输入入库前校验已补充。

本轮各统计入口均有独立样例及HTTP覆盖，但覆盖不等于所有参数范围验证。TableOne和回归有桌面表格展示，其他多数结果仍用JSON展示。

## 必须保留的实现事实

1. TableOne按全样本正态性选择展示/检验，正态两组为等方差t；group_numeric两组为Welch。已明确标注，未统一更改二者。
2. 旧LogisticRegressionAnalyzer.predict_proba()无新数据分支曾错误返回Xβ。已在 `modules/MedStat/src/analysis/regression.py` 改为results.predict()，独立二项闭式解验证通过。累计补丁必须包含这一旧模块修改。
3. Gamma保留inverse链接，不自动换log。其DomainWarning类别被记录；系数不解释为OR。
4. 预测评估的数据来源(training/held_out/external)为用户声明，不作独立验证承诺；Youden最优阈值为探索结果，不替换输入阈值。零分母PPV/NPV/MCC返回null。
5. prediction_evaluation只暴露基础指标；旧校准函数内部仍会算HL/等渗拟合，但统一结果排除它们。HL、DCA、NRI、IDI未完成对应验收。
6. 插补只支持显式连续数据；不猜测999等缺失码；缺失用null；保留原观测、每份数据及种子42+i。单次插补无MI推断，无缺失返回一份原数据。合并仅列均值，非回归参数。资源上限与拒绝范围详见适配器和报告。
7. 新适配器对不支持情形显式拒绝，旧模块未因此全面改写。检索标题去重/LLM筛选默认策略仍未定，不擅自改变。

## 当前验证和交付

- 命令（源码目录）：`.venv/bin/python scripts/validate.py`
- 最近完整验证：2026-11-20 08:02:40 UTC，PASS。
- 63项基础/HTTP测试＋58项统计检查（23组间/分类、14回归、21缺失），总121项通过。
- `node --check web/app.js`通过；未完成真实浏览器点击级验收。
- `reports/validation-summary.json`记录被测Python源码哈希；创建本handoff时已重新比对，零差异。该哈希清单不涵盖所有网页/文档，不应扩大声明。
- `reports/validation-*.log`为实际输出；逐轮报告从CONTINUATION、CATEGORICAL、GROUPS、TABLEONE、REGRESSION_ADAPTER、EVALUATION、GLM到IMPUTATION_ACCEPTANCE_20261120.md。
- 最新交付：`research/deliverables/MedToolkit-d3486d0-imputation-20261120.zip`。
- ZIP SHA256：`58a30788c46878e0c180c59a0aa2b6d08c42b7865a03f935da3f8cee592b7a04`。
- ZIP内有changes.patch、files/、验证日志；是基于d3486d0审核版的累计补丁，包含前面所有轮次，不要依次叠加旧包。已对不可变基准运行patch --dry-run，ZIP完整性检查通过。

## 下一步优先级

1. **先整理当前状态与桌面流程验收**。README/PROGRESS/STRUCTURE/ACCEPTANCE_SUMMARY累积多轮提示，正文仍含过时能力描述。整理为唯一当前状态，历史保留在CHANGELOG和逐轮报告，不能删除验证证据。勿把“此前未接入”复制成当前结论。
2. **补真实浏览器测试**。此前仅检查常见位置，未发现playwright/puppeteer/jsdom/Chrome；不等于永远不可用。重新检测当前工具与本机能力，必要时采用项目隔离的开发依赖，避免修改共享服务。覆盖鉴权、建项目、各类统计表单、执行/刷新/查看产物、TableOne/回归渲染、错误提示、RIS导出。只测试桌面，Gemini保持空白。HTTP测试已存在，不需反复重做无关检查。
3. **证据提取与引用核验**。现有写作evidence有来源/位置/摘录和ID检查，但未实现自动全文提取、语义事实核验和完整写作agent。先核对原Writer/Hunter接口与现有Skill材料，建立可追溯证据链；不能因缺Gemini配置假称完整生成流程已验收。
4. **独立验收HL/DCA/NRI/IDI等剩余统计**。先检查原公式与适用条件，旧HL实现此前观察到仅事件侧项等疑点，尚未修正。数值错误按既有授权修复；若涉及旧默认策略或产品行为选择，先提出具体冲突供用户决定。
5. 完成改动后只做必要的验证与累计交付；不要机械每加一个小模块就停下要求用户继续。没有配置、浏览器或远端授权时，应准确区分未验证和真正阻塞。

## 新会话启动建议

先读本文件及工作区AGENTS.md，按需读取能力目录。检查当前源码、最新报告和用户新指令，然后继续上述优先工作。无需重新下载同一上游版本、重建环境或重新应用累计补丁；若用户称GitHub再次更新，再比较新提交并保留本地改动。

RemoteLab规则恢复指针（仅在规则上下文缺失时读取，不代替新会话规则）：`/home/workspace/remotelab-eao-instance/config/rule-context/71fadec971cf5a38dc3be9fa/f04e7ba9d9cae4fa04d255a81c4ab2b14d2dd65f49491c2ba493b8f0741665fa.json`。
