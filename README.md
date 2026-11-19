# Mengtage 科研工作台

本地研发版：统一项目、可恢复任务队列、PubMed检索、MedStat相关性计算、Gemini证据约束章节草稿，以及适配竖屏的项目/检索页面。原始模块集中在modules，用户提供的Skill集中在skills，仅作为流程参考，未安装进全局Agent环境。

## 运行

Linux/macOS、Python 3.11以上；在本目录建立独立虚拟环境并安装requirements.txt。

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m workbench create '研究问题'
.venv/bin/python -m workbench projects
```

任务输入为JSON文件，使用返回的项目/任务ID：

```bash
.venv/bin/python -m workbench enqueue PROJECT_ID search search.json
.venv/bin/python -m workbench run JOB_ID
.venv/bin/python -m workbench jobs PROJECT_ID
```

`search.json`：`{"query":"anesthesia AND postoperative pain","limit":20}`。
检索调用PubMed，复用Hunter XML解析；显示命中数和取得数，超过上限明确标记不完整。不会自动筛除或按标题合并文献；旧版去重/LLM筛选保持在原模块，默认策略仍待决定。

统计任务输入见examples/statistics.json，仅合成数据验收；复用MedStat Pearson/Spearman实现，不调用模型。其他统计方法保留在modules，尚未接入统一队列或通过方法学验证。

写作任务输入见examples/write.json。服务端通过环境变量配置GEMINI_API_KEY、GEMINI_MODEL；不在聊天或仓库填写密钥。每次仅送显式批准的公开证据，字符限额20000、最多一次生成请求、最多3000输出token。结果记录服务端实际token用量。引用ID错误与没有引用均不能通过机器检查；所有草稿仍需人工核验事实与数字。当前为单章节生成适配器，完整多步写作agent与自动证据检索尚未完成；不会将其称为已完成的完整agent。

## 手机布局预览

服务端配置至少32字符的WORKBENCH_ACCESS_TOKEN后：

```bash
.venv/bin/python -m workbench serve --port 8765
```

默认只监听127.0.0.1。浏览器打开本地地址，在页面输入访问令牌。令牌仅保留在页面内存，不写浏览器持久存储。该页面支持自然语言填写研究问题、检索任务提交、运行及产物查看；统计可在页面输入合成数据JSON，写作暂通过CLI输入，完整自然语言编排尚未接入。远程手机访问需经带HTTPS的认证网关，不直接公网暴露本地服务。

## 状态与安全边界

SQLite保存任务和输入，项目目录权限0700、数据库及产物0600；磁盘未加密，属于单所有者本地研发版。不得用于真实病例；身份映射、敏感字段检查、加密存储、保留期/删除、备份恢复、分用户权限仍需生产实现。统计入口仅允许synthetic标记，写作仅允许public标记，这不是自动识别敏感信息的能力。

任务状态queued/running/completed/failed/needs_review。完成任务不可重复运行，同项目同输入复用任务ID。进程中断后先确认没有工作线程，再运行`python -m workbench recover`将不确定任务标记为待复核，避免重复远端调用。未提供自动重试付费任务或强制取消正在进行的HTTP请求。

Skills中旧版流程不自动生效；本目录README与统一入口描述当前实际能力。modules中的旧版应用仅作为源码与迁移对象，不要直接运行并开放公网。本版已按修复要求更新统计逻辑；后续改变研究范围或方法选择仍需决定，来源版本见source-version.json。

Gemini接口依据：[Google官方generateContent文档](https://ai.google.dev/api/generate-content)。

## 新增资料与复核

20份他山Skill主说明见skills/catalog，58份配套文档见skills/catalog-resources。脚本仅有清单，未把缺失脚本伪装成可运行工具。Zotero的4个组件已按原材料提取至skills/zotero，仅完成语法检查，未连接用户桌面、未重启Zotero或写入文献库。当前可在检索任务后导出RIS。

失败/待复核任务可使用`retry JOB_ID --confirmed`建立新任务，旧任务及产物保留；重复确认同一失败任务不会生成多个重试任务。执行中的任务持有跨进程锁，恢复操作不会将活跃工作误标记为中断。

已通过15项本地测试；真实PubMed查询抓取3条并导出RIS，完整命中数大于获取数时标注不完整；合成数据Pearson计算返回r=1、n=4。没有Gemini调用。完整验证记录见validation-tests.txt与validation-live.json。

## 统计修复版

基础15项与统计58项检查通过，完整运行命令：`.venv/bin/python scripts/validate.py`。修复前后对照见reports/ACCEPTANCE_SUMMARY.md、reports/baseline及source-diff.json。统计依赖现要求SciPy>=1.15与statsmodels>=0.14。

分类/离散缺失尚无适用模型，明确拒绝；linear/ridge只允许单次插补，不输出多重插补推断。数值缺失码需按变量字典显式给出，999不再自动认作缺失。Web端均值合并使用真实逐份估计及方差，有限样本自由度采用Barnard–Rubin。
