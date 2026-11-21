# MedToolkit · 本地桌面整合版

本目录包含截至2026-11-21的累计源码，无需先应用历史增量ZIP。统一入口覆盖MedHunter、MedStat和PaperWriter；Gemini保持空白，统计限合成数据，手机暂缓。当前为本机单所有者研发版本。

## 启动

已验收Linux/Python 3.14；Windows使用WSL。原生Windows不在支持范围（文件锁依赖fcntl）。Python依赖需要联网安装，本包不含虚拟环境。

```bash
cd mengtage-review/medtoolkit-workbench  # 从仓库根目录进入；ZIP用户进入解压目录
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python scripts/start_local.py
```

打开 `http://127.0.0.1:8765/`，将终端显示的本次访问令牌输入页面。该令牌不写入文件或浏览器存储；退出服务后重新启动会产生新令牌，项目数据保留。也可预先设置至少32字符的 `WORKBENCH_ACCESS_TOKEN`，使用已有令牌。启动器固定清空Gemini密钥和型号，不调用模型。

数据默认保存于本包的 `runtime/`。可使用 `--data /绝对路径/项目数据 --port 8765` 指定位置和端口。按Ctrl+C停止服务。只监听127.0.0.1，不直接用于公网部署；工作台令牌代表该数据目录的本机所有者。

精确验收环境版本见 `requirements-tested.txt`，是Linux/Python 3.14环境快照；一般安装使用 `requirements.txt`。离线设备需另行准备适配自身系统的依赖轮子。

## 入口与流程

| 入口 | 已接入能力 |
|---|---|
| `/` 工作台 | 创建项目、有限PubMed检索、去重与冲突复核、统计任务、产物查看、RIS导出 |
| `/sources` 来源集合 | 数据库/注册库来源登记、集合版本、跨来源去重；不是所有数据库的在线连接器 |
| `/screening` 筛选 | 筛选前checkpoint、独立人类/模型提交、揭盲、人工裁决、全文、研究映射和所选来源链PRISMA |
| `/writer` 写作 | 公开/合成原文、Hunter/Stat证据绑定、章节编辑与版本、作者审核、Markdown/Word/审计JSON |

筛选入口需从工作台准备批次后使用带批次ID的链接。人类与模型侧使用独立评审令牌；模型判断当前由人工导入，不代表真实LLM运行。Writer捕获Hunter全文需该批次人类裁决者令牌；工作台令牌不能冒充它。

MedStat包含相关性、列联表、组间检验、TableOne、OLS/Logistic、Poisson/Gamma、插补和预测评估（含HL/DCA/NRI/IDI）。输入示例见 `examples/`；保留原统计默认口径。真实病例数据尚未接入。

Writer从已保存版本导出，修改正文或证据需重新审核。Hunter裁决/映射更新或原文替换使旧绑定停止新审核/导出；已导出文件不覆盖。旧统计任务若缺少完成时哈希不能自动追认为原生证据。逐字匹配与引用ID校验不等于论断正确，支持性由作者核对。

## 附加依赖

- PDF原文解析：系统安装Poppler的 `pdfinfo`、`pdftotext`；扫描PDF需先OCR，本包不自动OCR。
- Word生成：python-docx随Python依赖安装；无需安装Office。
- 实际PDF排版预览：安装LibreOffice Writer及中文字体，运行 `scripts/office_render.py 输入.docx 输出目录`。不影响只导出Word。
- 桌面自动化验收：另装Node、Playwright和Chromium，见 [浏览器说明](scripts/browser/README.md)。正常使用应用不需要这些测试依赖。

## 验证与交接

完整ZIP发行包包含MANIFEST.json，可运行 `python3 scripts/verify_package.py` 核对文件哈希；Git检出以提交记录为准，不附带ZIP清单。执行测试后reports会更新。

```bash
.venv/bin/python scripts/validate.py
```

最近完整Python检查235项通过；主工作台38项、Writer7项、Hunter接入3项桌面流程均有验收记录，具体运行轮次见 [当前验收摘要](reports/ACCEPTANCE_SUMMARY.md)。Word已用LibreOffice实际渲染；Microsoft Word/WPS桌面未实测。

- [当前进展](PROGRESS.md) / [后续计划](NEXT_STEPS.md)
- [总交接](docs/handoffs/medtoolkit-handoff-20261120.md)
- [Writer交接](docs/handoffs/medpaperwriter-handoff-20261120.md)
- [Stat交接](docs/handoffs/medstat-handoff-20261121.md)
- `reports/`：分阶段报告与合成验收证据；`docs/history/`：整理前历史说明。
- `modules/`：保留的旧模块及适配来源。不要直接把旧模块的README当作统一工作台能力；其独立应用及模型客户端未因此完成验收。

完整包不含真实项目数据库、凭据、.git历史、虚拟环境或本机浏览器/Office运行时。保留AUTHORS、NOTICE、AI_DISCLOSURE及原模块文档；继承的source-version.json记录历史来源，Git版本以当前提交为准；完整ZIP发行包另附RELEASE.json与MANIFEST.json。
