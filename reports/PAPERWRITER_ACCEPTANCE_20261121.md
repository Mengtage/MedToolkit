# PaperWriter 本地证据与作者审核 · 2026-11-21

统一工作台新增 `/writer`：原文快照 → 逐字证据包 → 提纲/章节编辑 → 固定稿件版本 → 作者批准/返修 → Markdown与审计JSON下载。Gemini保持空白、无模型调用；未改变旧版Word自动翻译或未批准内容的导出策略。

## 已实现

- `workbench/writer.py`复用Store项目和SQLite，新增writer_objects、writer_heads、writer_reviews。本机工作台令牌可访问；独立筛选令牌不能访问此管理员接口。作者姓名和核验人是本机所有者声明，非多人实名认证。
- 原件仅公开/合成PDF或UTF-8 TXT，复用fulltext.snapshot的原件哈希、页文本哈希、提取版本；PDF最多200页/5MB，TXT按换页符分段，不冒充PDF物理页；本轮桌面验收使用TXT。
- 证据1–30项，ID唯一，摘录必须逐字存在于指定页；固定原文/证据哈希，保留人工支持性说明与核验人。证据包可通过API指定parent_id；桌面每次冻结独立新包。report_id/study_ids为手工字段，未验证Hunter纳入/映射关系，不靠题名匹配。
- 提纲通过章节增删/上下移动调整；正文及证据包每次保存为新版本。更新需携带当前版本，阻止并发覆盖；历史版本可读、可导出，不能追加当前批准。证据替换或正文修改都产生未审核新版本。
- 引用规则阻止未知/缺失/格式错误ID以及待补证据标记被批准；无引用段落（含数字时注明）为人工复核提示。这是格式及覆盖启发式，不是逐句事实证明。
- 作者审核要求显式确认和意见，支持approved/changes_requested，记录稿件哈希及审核事件哈希链。存在未保存修改时桌面拒绝审核/导出，防止误以为批准的是编辑中的正文。
- 导出冻结指定版本、当时审核记录和证据包；未批准稿有明显标记。正文引用ID与引用证据列表关联，JSON包含摘录、定位、原件与文本哈希、版本关联及核验声明。仅列已使用证据；原文二进制不嵌入导出包，仍在项目Store内。
- 旧模块`api/routes_export.py`两处`services.reference_formatter`更正为实际存在的`core.reference_formatter`。旧版生成/翻译/Word导出行为保持原样。

## 验收

- 完整Python：163项基础/HTTP/单元 + 58项统计 = 221项通过。新增Writer 11项单元、1项HTTP；错页、错摘录、未知原件、重复证据ID、跨项目、原件/包/审核记录篡改、并发编辑、审核与版本失效均覆盖。
- 原工作台Chromium 38项回归；Writer独立Chromium 5项通过。真实HTTP、真实点击、实际下载；检查未知引用阻断、保存后批准、修改后重审、历史版本保护、未保存修改阻断、401、退出清屏与无浏览器令牌持久化。
- 旧参考文献两条实际路由函数体隔离执行通过，未启动旧FastAPI完整应用或调用模型。
- 证据：`reports/validation-summary.json`、`reports/validation-core.log`、`reports/browser/summary.json`、`reports/writer-browser/summary.json`、`writer-reviewed.png`、实际下载`audit.json`/`manuscript.md`、`reports/writer-legacy-check.log`。

复现：`.venv/bin/python scripts/validate.py`；`.venv/bin/python scripts/check_writer_legacy.py`；按scripts/browser/README.md设置浏览器依赖后运行`node scripts/browser/acceptance.cjs`和`node scripts/browser/writer.cjs`。两个脚本用隔离临时Store、合成资料、空Gemini配置。

## 尚未完成

Hunter筛选/研究映射向Writer的原生绑定、MedStat结果artifact/hash绑定、真实模型运行和提示/usage追踪、统一Word/双语导出、旧FastAPI全栈验收。新流程不宣称已经完成这些集成。原件和数据库由本机可信管理员保管；哈希检测意外替换，不对可同时重写数据库的管理员提供防篡改保证。手机仍暂缓，无GitHub推送。
