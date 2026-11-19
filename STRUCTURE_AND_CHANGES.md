# 文件结构与修改清单

截至本次交付，所有工作在独立目录完成，没有推送或修改GitHub仓库，也没有替换现有WebApp。

```text
medtoolkit-workbench/
├── modules/
│   ├── MedPaperHunter/       32个上游文件
│   ├── MedPaperWriter/       62个上游文件
│   └── MedStat/              68个上游文件
├── skills/
│   ├── med-extract/          两个相同原附件合并收录一份
│   ├── search-strategy/      包内版本3.0.0
│   ├── workbench/            统一流程参考
│   ├── catalog/              20份Skill说明与按需索引
│   ├── catalog-resources/    58份配套文档
│   └── zotero/               说明、路由参考、配置、辅助脚本
├── workbench/
│   ├── core.py               项目、SQLite任务、进程锁、重试与恢复
│   ├── adapters.py           检索、统计及待配置Gemini接口
│   ├── exports.py            RIS格式输出
│   ├── server.py             单所有者本地HTTP接口与访问令牌检查
│   └── __main__.py           命令行入口
├── web/                      竖屏页面、检索、合成数据统计及RIS导出
├── tests/                    15项回归测试
├── examples/                 合成统计输入与未授权写作模板
├── source-version.json       源码提交版本
├── source-diff.json          原模块逐文件差异清单
├── requirements-tested.txt   本机验证的依赖版本
├── validation-tests.txt      测试输出
├── validation-live.json      真实检索及合成统计验收摘要
└── README.md                 运行方法、接口边界、未完成项
```

## 对原模块的改动

原模块162个文件完整收录，159个内容与源提交一致。3个文件仅有说明或项目署名调整：

- MedPaperHunter/docs/AI_FEATURE_GUIDE.md
- MedStat/medstats_automate/python/medstats_main.py
- MedStat/medstats_automate/python/run_analysis.py

没有修改旧版统计公式、插补算法、去重和筛选逻辑。旧应用仍保留原有配置与历史文档，不能将其当作经过安全加固的公网服务直接启动。

## 新增整合代码

- 检索适配器复用Hunter的PubMed XML解析，记录查询、命中总数、实际取得数和原始响应；默认不做删除式去重，不把有限结果当完整系统综述检索。
- 统计适配器复用MedStat的Pearson/Spearman计算，记录数据哈希、软件版本、原始行数、有效行数和缺失剔除数；仅合成数据验收，零模型调用。
- 任务写入前校验类型、字段白名单及数据分类；额外字段不落盘。重复任务复用ID，显式重试创建关联任务；执行和恢复使用跨进程锁。原任务和结果保留。
- 写作接口保留但未配置；未配置时不接收写作任务。它目前是证据约束的章节生成适配器，尚非完整多步写作agent。
- 本地HTTP入口要求访问令牌，监听127.0.0.1；前端用textContent呈现用户文本。无公网发布、无远程手机认证网关。
- 新增RIS出口供Zotero导入，未连接用户桌面、未改动Zotero配置或文献库。
- Skill及配套文档按模块索引保存，不全量加入提示词；只有说明的脚本不视为已经实现。第三方资源尚未全套安装或自动启用。

## 验证结果与限制

15项回归测试通过，覆盖鉴权、路径隔离、输入未落盘、重试幂等、中断恢复、引用标识、RIS字段换行以及已知合成相关性结果。真实查询“anesthesia AND postoperative pain”命中43256条，本轮仅获取3条并标记不完整，成功导出RIS。合成统计r=1、n=4，没有Gemini调用。

当前版本提供可运行的非LLM基础链路，尚未完成全部统计方法迁移、临床方法学验证、自动全文提取、完整写作agent或生产安全验收。真实患者数据、自动画像/记忆、付费检索、对外投稿均未接入。Gemini按当前安排留空。
