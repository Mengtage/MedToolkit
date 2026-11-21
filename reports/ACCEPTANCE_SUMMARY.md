# 当前验收摘要 · 2026-11-21

| 范围 | 最近结果 | 证据 |
|---|---|---|
| 完整Python | 177基础/HTTP/单元+58统计=235通过 | validation-summary.json、validation-core.log |
| 主工作台桌面 | 38通过；完整包独立副本重新完成 | browser/summary.json |
| Writer桌面 | 7通过；完整包独立副本重新完成 | writer-browser/summary.json |
| Hunter→Writer桌面 | 3通过；完整包独立副本重新完成 | writer-hunter-browser/summary.json |
| Word实际排版 | LibreOffice26.2.6.3，65行表格/4页A4压力稿通过 | office-layout/after/checks.json、PAPERWRITER_OFFICE_20261121.md |

模型配置空白，统计/浏览器使用合成材料。Microsoft Word/WPS、真实模型、真实临床数据和手机不在验收范围。旧独立模块不因统一测试通过而被视为全栈验收通过。

完整包的干净解压检查见PACKAGE_CHECKS.json（该文件由打包过程生成）。合成测试会在reports写入新结果；文件哈希清单描述的是原始交付状态。
