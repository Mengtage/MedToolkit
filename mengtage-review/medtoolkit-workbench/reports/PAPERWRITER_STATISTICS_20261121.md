# MedStat到PaperWriter原生证据绑定 · 2026-11-21

Writer可选择当前项目已完成的MedStat合成任务，确认后固定完整结果为只读文本快照；通过既有逐字摘录、证据包、章节版本和作者审核进入Markdown/Word/审计JSON。同一证据包可同时包含文献与统计结果。

## 来源链

Store完成统计任务时将结果文件字节SHA256和完整任务payload的规范JSON SHA256写入任务result；计算产物和统计口径不变。Writer捕获时验证任务类型/状态、项目、合成分类、输入哈希、文件哈希及方法一致性。随后固定完整结果文本、文档哈希和native_statistics：job_id、artifact、artifact_sha256、payload_sha256、分析自带input_sha256及environment。

任务payload_sha256包含方法、参数、数据和可选重试关联；分析input_sha256沿用各适配器自己的范围，二者不混用。证据条目携带原生绑定，Markdown和Word列任务/输入/结果哈希，审计JSON保留完整绑定。原始结果全文保存在项目Writer文档快照，审计证据仍以选择的摘录及来源关联为主，不复制原始输入数据。

建立证据、保存稿件、审核和导出时重新核对。原始分析文件或任务输入变化/缺失时拒绝继续；不能通过手工上传将任意数值标成原生MedStat结果。保存的历史版本不因新的独立分析任务产生而自动改变。哈希用于检测替换，可信磁盘/数据库管理员仍可修改底层数据，不构成对管理员的密码学认证。

旧统计任务缺少完成时哈希，不自动追认。旧结果仍可查看，进入新绑定功能需新建分析任务（相同payload会复用旧任务，需用新项目执行同一分析，或明确建立新的执行入口后再绑定）。当前接口没有强制重算已完成任务功能。

## 验收

完整Python 171基础/HTTP/单元 + 58统计 = 229通过；原桌面38项、Writer桌面7项均本轮通过。新增4项后端测试：审核与Word绑定、捕获前后结果篡改、输入变化、旧任务无哈希、跨项目、未完成任务、人工确认和手工文档不获原生身份。真实桌面通过HTTP运行合成Pearson任务、捕获、逐字摘录、证据包、保存稿件及审计JSON下载。

证据：reports/validation-summary.json、validation-core.log、writer-stat-tests.log；reports/browser/summary.json；reports/writer-browser/summary.json、statistics-audit.json、writer-statistics.png。全程Gemini空白，未调用模型。

新文件workbench/writer_statistics.py、tests/test_writer_statistics.py；共享core.py只新增统计完成时哈希，writer/docx/web局部接入。旧统计结果字段保持原样，任务返回额外元数据。复现`.venv/bin/python scripts/validate.py`及按浏览器README配置后运行acceptance.cjs、writer.cjs。

Hunter原生筛选/全文/研究映射绑定仍待做；真实临床统计输入、模型生成、Office排版渲染和手机验收未完成。
