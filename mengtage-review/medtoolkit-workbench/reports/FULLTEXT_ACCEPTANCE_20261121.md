# MedHunter 全文快照与跨阶段筛选验收 · 2026-11-21

全文登记、固定快照、第二次人工 checkpoint、独立判断、裁决与导出已接入本机 HTTP 和桌面。9 项新增后端测试通过；完整 Python 检查为 116 项基础/HTTP/单元 + 58 项统计 = 174 项；Chromium 31 项流程通过，含新增 3 项全文流程。均为合成材料，Gemini 配置为空，无模型调用。

## 实现范围

| 操作 | 行为与留痕 |
|---|---|
| 从父批次进入 | 仅题名摘要阶段，须已揭盲且全部记录完成最终裁决；仅指定人类裁决者登记最终纳入记录的全文 |
| 登记取得情况 | 每条分别登记 retrieved / not_retrieved；两者说明均必填。未取得全文不进入全文筛选分母，也不计作读完全文后的排除；全部未取得时不建空子批次，仍可下载取得登记 JSON |
| 上传与提取 | PDF 或 UTF-8 TXT，每件最多5MB、文本最多1MB、最多200页/段。PDF 使用本机 pdfinfo/pdftotext -layout，记录提取器版本及物理页码；TXT使用换页符分段，明确不是原PDF页码。空白/无可读文本拒绝，无自动OCR |
| 固定材料 | 原文件按SHA256存储，页文本逐页哈希、整份文本哈希；子批次固定快照和取得历史。准备/下载核对原文件哈希；不向外部地址抓取全文 |
| 阶段关联 | parent_review_id、parent_record_id、parent_record_sha256、parent_decision_hash、retrieval_event_hash、report_id；记录父批次事件尾哈希、拟获取/已取得/未取得报告及说明 |
| 人工checkpoint | 新的全文方案、标准、词表、材料与评审分工重新批准。指定人类在批准前可查看全文文本及下载原件，模型评审批准前不可领取判断表或下载原件 |
| 独立判断与裁决 | 双方判断和最终裁决均要求 p:页号 + 逐字摘录，摘录须出现在该页快照。仍保留原因代码、理由、提交锁定、双边完成后揭盲与追加裁决修订 |
| 修订 | 取得记录追加历史；父记录最终裁决变化后，旧取得登记在新的准备流程中变为待登记。已建子批次不回写，页面提示父批次后续已有修订，便于选择重建 |
| 导出 | 子批次审计JSON含冻结的取得记录与阶段关联；CSV新增父记录/报告ID、文件/文本哈希、页码口径、双方摘录及最终裁决位置和摘录；取得登记可单独导出JSON |

登记写入使用 SQLite 写事务，准备子批次时核对父审计尾及取得审计尾未变化，拒绝读取期间发生的更新。权限沿用独立评审令牌；模型不收到人类独立理由或父阶段裁决理由。

## 复现与证据

```bash
.venv/bin/python scripts/validate.py
LD_LIBRARY_PATH="$PWD/.browser-tools/sysroot/usr/lib/x86_64-linux-gnu" node scripts/browser/acceptance.cjs
```

- `tests/test_fulltext.py`：真实本机解析合成 PDF；UTF-8 分页；取得状态与角色校验；不合法/空白文件；未取得报告；人工批准前后隔离；错误页号/伪造摘录拒绝；跨阶段JSON/CSV；父裁决修订；原件及审计篡改拒绝；旧子批次保持冻结并提示父版本变化。
- `reports/validation-summary.json`、`validation-core.log`、`fulltext-validation-run.log`：完整运行结果及Python源码哈希。
- `reports/browser/summary.json`、`run.log`：31项桌面检查、浏览器版本、网页/脚本哈希。
- `reports/browser/fulltext-adjudication.png`：裁决页面。
- `reports/browser/fulltext-audit.json`、`fulltext-decisions.csv`、`synthetic-fulltext.txt`：合成审计与下载原件。桌面测试使用TXT；PDF解析由后端合成PDF测试覆盖，不混称为浏览器PDF上传验收。

新增业务文件 `workbench/fulltext.py`、`web/fulltext.js`。接入文件 `screening.py`、`screening_http.py`、`screening_exports.py`、`server.py`、`web/screening.html/js`。未改 Writer 和 MedStat 业务代码。

## 当前限制与下一步

逐字匹配证明摘录来自该页，不能证明摘录支持纳排结论。PDF布局、表格、乱码及扫描件仍需人工核对；无OCR、付费全文获取或语义自动核验。当前report_id以父批次和记录确定，尚未完成跨批次/多报告研究归并；不得把报告数量称为研究数量。

下一步建立人工确认的 report→study 映射，再从明确选定的已完成批次及检索/去重历史计算PRISMA，分清records/reports/studies、未取得与全文排除、分支及修订版本。本文报告的取得数量不是完整PRISMA。

权限验收范围是本机HTTP；管理员/文件所有者/直接CLI受信任，哈希链没有外部锚定。模型来源为合成手工导入，未验证真实模型；手机暂缓，无GitHub推送。
