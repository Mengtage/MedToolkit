# MedHunter到PaperWriter原生证据绑定 · 2026-11-21

统一Writer新增“引用MedHunter全文”：输入所选全文批次的人类裁决者令牌及批次ID，加载最终纳入报告，确认公开/合成属性后固定全文与裁决版本。后续复用逐字摘录、章节版本、作者审核和Word/Markdown/审计JSON导出。

## 权限和来源

新增`/api/review/writer_candidates`与`writer_capture`，由实际评审令牌认证，要求该批次指定人类裁决者；不得在请求中自报actor。模型评审及其他人员拒绝，未揭盲/未完成全部全文裁决/没有与当前裁决一致的研究映射均拒绝。Writer工作台令牌仍负责后续项目写作管理，不冒用裁决者身份。

捕获固定record_id、report_id、批次局部study_ids、完整裁决尾/单报告裁决/研究映射事件哈希、方案与原始记录哈希、全文来源清单哈希、取得事件及父批次固定版本。原文复用Hunter已冻结的PDF/TXT和页码；不重解析、不按标题匹配。用户声明材料public/synthetic；系统不自动验证授权或内容公开性。

证据包从绑定自动写入report_id/study_ids；手工值与原生映射冲突则拒绝。引用来源、章节、作者审核、Markdown、Word与审计JSON保留绑定。进入纳入集不等于摘录支持任意论断，逐字存在性与人工支持性判断继续分别保存。

## 修订行为

全文裁决或研究映射后来修订，旧Writer绑定禁止再次审核/导出，须重新捕获并保存/审核新稿；此前导出文件与旧版本不被覆盖。原始全文/清单被替换时同样拒绝。

题名摘要父批次后续修订沿用Hunter现有冻结父版本语义：只要原父版本仍存在，所选全文批次的历史父关联有效；页面显示父阶段已有更新。绑定明确记录父版本，不宣称代表所有最新筛选分支。study_id仅在指定全文批次内有效，不自动进行全项目研究归并。

## 验收

完整Python177基础/HTTP/单元 + 58统计 = 235通过；原桌面38、Writer桌面7、Hunter到Writer专项桌面3，共48项本轮通过。

新增6项后端：原生报告/研究关联进入审核及Word；模型/其他评审/跨项目/未确认拒绝；无研究映射或非全文拒绝；映射版本冲突与旧证据失效；原件/来源清单替换；父版本历史语义与手工ID冲突。桌面通过真实HTTP校验模型身份拒绝、人类裁决者捕获、自动study关联、作者批准及Word/审计实际双下载与文件哈希。合成fixture使用真实筛选/全文/研究映射服务建批次，不调用模型。

证据：reports/validation-summary.json、validation-core.log、writer-hunter-tests.log；reports/writer-hunter-browser/summary.json、hunter-audit.json、hunter.docx、hunter-writer.png；原桌面与Writer回归报告维持原路径。

复现：`.venv/bin/python scripts/validate.py`；按浏览器README配置依赖后运行`node scripts/browser/acceptance.cjs`、`node scripts/browser/writer.cjs`、`node scripts/browser/writer_hunter.cjs`。专项脚本只在隔离临时Store创建合成筛选链。

真实模型与双语生成、真实临床数据、Office排版渲染、手机仍未验收。Gemini保持空白，无GitHub推送。
