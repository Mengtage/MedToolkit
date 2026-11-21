# PaperWriter实际排版验收 · 2026-11-21

使用LibreOffice Writer 26.2.6.3实际打开DOCX并转换PDF，检查渲染页面；不是只解析DOCX XML，也不是Microsoft Word桌面版验收。

## 已修复

| 问题 | 修改 | 实际渲染结果 |
|---|---|---|
| 默认Letter纸张 | A4；上下20mm、左右22mm页边距 | PDF页面595.304×841.89pt |
| 空行叠加段间距，版面松散 | 空行由段距表达，正文11pt/1.2倍行距/段后6pt | 同一压力样本5页缩至4页，无正文或表格行丢失 |
| 表格等列宽，说明列频繁换行 | 按内容长度分配列宽，表格固定在可用宽度内 | 65行3列表格内容完整；不超出版心 |
| 表格行跨页被拆开 | 行禁止跨页拆分、表头重复、表头浅色底 | 逐页检查没有半行落入页脚区域 |
| 数字未体现Markdown对齐 | 读取分隔行冒号，支持左/中/右对齐 | 数值列右对齐 |
| 长哈希挤出孤立字符 | 哈希/版本元数据9pt并保持段内完整 | 64位哈希在本例中完整单行 |
| 无页码 | 页脚8pt，状态+版本+PAGE/NUMPAGES | 四页分别显示1/4至4/4 |

保持章节、引用、审核状态和版本记录内容；未改统计/筛选口径、翻译或模型配置。修改范围为workbench/writer_docx.py。

## 实际样本与检查

- 压力样稿：中英文、α β、≤ ≥ ±、特殊字符、65行跨页表格、长来源与哈希、作者审核字段。样本是人为构造的合成版式fixture，其中审核字段用于测试显示，不代表真实研究稿批准。
- 页图逐页检查：after/page-1.png至page-4.png；前后PDF、DOCX均保留。自动检查65行按序齐全、中文与符号、每个表格页重复表头、每页页码、所有渲染单词边界在页面内部。通过摘要after/checks.json记录PDF/DOCX哈希。
- 本轮桌面流程实际下载的普通Writer稿和Hunter关联稿另经LibreOffice打开，均生成1页A4 PDF；Hunter页图已目视核查。
- 完整Python仍235项通过；Writer 7项+Hunter接入3项桌面本轮通过。主工作台38项本轮未重复，原源码哈希未变。

## 复现与环境

新增scripts/office_layout_fixture.py、office_render.py、check_office_layout.py。标准环境安装LibreOffice Writer及中文字体后：

```
.venv/bin/python scripts/office_layout_fixture.py reports/office-layout/after
.venv/bin/python scripts/office_render.py reports/office-layout/after/layout-stress.docx reports/office-layout/after
.venv/bin/python scripts/check_office_layout.py reports/office-layout/after
```

本机无root安装：通过系统APT索引下载66个包（约100MB，核对索引大小/摘要），只解包到项目.office-tools/sysroot；修复解包后本地配置链接及BRAND_BASE_DIR，用liblangtag提供的lt_db_set_datadir将语言数据目录指向本地解包文件。未修改系统Office配置或服务。该临时运行时不放入交付包，安装版LibreOffice直接适用上述脚本。

服务器字体实际替代为DejaVu和Noto CJK，PDF已嵌入所用字形；DOCX不嵌入商业字体。Microsoft Word/WPS及不同字体环境可能分页不同，尚未做这些客户端的实际验收；本次验证的3列表格不代表任意超宽表格都能自动适配。手机和真实模型仍暂缓。
