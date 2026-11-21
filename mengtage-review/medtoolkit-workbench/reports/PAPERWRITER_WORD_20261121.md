# PaperWriter 固定版本 Word 导出 · 2026-11-21

`/writer`新增“导出 Word（已保存原文）”。从指定已保存版本生成DOCX，同时下载审计JSON。未保存修改先保存；未批准稿标记草稿，历史稿明确标记历史版本。旧版独立应用自动翻译/Word路由未修改。

## 输出与关联

正文保持保存的语言与字面内容，不请求翻译或模型。中文/英文/特殊字符和`[E:id]`引用保留；标准带首尾竖线、分隔行和等列数据行的Markdown表格转为Word表格，转义`\|`保留为单元格竖线。其他Markdown按普通文本输出，不宣称完整Markdown渲染。章节使用Word标题样式，表格带边框及重复表头；引用证据列来源、摘录、定位、支持说明与原件哈希。末尾附本版作者审核及待核对事项。

每次导出先固定原有JSON导出快照，再生成独立DOCX文件和word_export登记。登记保留稿件版本、JSON快照ID/哈希、Word文件名/哈希、审核状态和零调用记录。失败不产生伪成功Word登记；已创建的JSON快照可保留。审计JSON含完整固定稿件及证据，不包含原文PDF/TXT二进制。

新增`workbench/writer_docx.py`，接入`WriterService.export_word`及已有统一写作路由；桌面下载走认证POST，文件名使用版本和导出ID。依赖`python-docx==1.2.0`，其`lxml`等安装版本列于requirements-tested.txt；按requirements.txt或精确版本文件安装。

## 验收事实

- 完整Python：167项基础/HTTP/单元 + 58统计 = 225项通过。新增4个Word测试，并扩展既有HTTP测试。
- Writer Chromium桌面6项通过，新增真实DOCX和审计JSON双下载、SHA256与版本一致性检查。下载原件再用python-docx重新打开核验；证据在reports/writer-browser/manuscript.docx和word-audit.json。
- 单元测试覆盖中文英文特殊字符、Word表格及转义竖线、原件篡改/跨项目拒绝、草稿/历史批准标记、控制字符明确报错、非标准表格保留原文、无网络调用。
- 原工作台38项桌面回归是上一轮结果，本轮未重复；其所记录源码哈希保持一致。手机、真实模型仍未验收。

复现：`.venv/bin/python scripts/validate.py`；按scripts/browser/README.md设置依赖后`node scripts/browser/writer.cjs`。本机未安装Word/LibreOffice，已核验DOCX结构、内容及下载，未做Office实际排版渲染验收。

## 后续缺口

Hunter/MedStat证据原生绑定、统一双语生成与真实模型仍未接通。当前Word导出为新本地写作流程的已保存原文导出；若需改变旧版自动翻译规则，须先确认。
