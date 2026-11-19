# 收件与整合评估（2026-11-19）

收到3个可读附件，对应2个不同技能；MedExtract的.skill和.zip解包后3个文件逐字节相同。medical-search-strategy-builder-v2.zip内部SKILL与package.json均标注3.0.0。两技能均是Markdown/YAML/JSON指导材料，无可执行应用后端；检索策略包不负责实际搜索或下载，MedExtract限定本地文献库且不做统计合并。

MedPaperHunter.zip和MedStat.zip在消息记录中确认是文件，但附件入库状态为partial，各有一个下载失败资源；当前未获取源码。先前“只发了文件名”的判断已纠正。未发现可自动重试的公开CLI入口，不读取应用密钥绕过平台。

已改进：
1. 命中上限不再通过新增限定/排除词缩小范围；改用分页与完整分片。
2. 检索不再默认四个PICO概念全部AND；不把未指定疾病亚型自动补成2型。
3. 标题相似度95%和作者+年份+关键词不再直接判重复；标识冲突保留复核。
4. 提取区分原文未报告、全文不可得、不可读；增加页码/表格、分母、时间点、来源哈希。
5. 区分record/report/study，明确未获取全文；替换原始串联式PRISMA图的设计。
6. 原包多轮确认转为复用已有课题信息、一次一个关键决定和持久化项目文件。
7. 版本、名称规范化；不将原始作者字段Assistant或MedPaperHunter视为来源真实性与方法验证。

依赖：本地辅助脚本仅Python标准库；联网检索需要现有搜索工具或合法数据库接口；PDF使用已有pdftotext/OCR。技能文本不提供数据库授权或后台运行服务。

许可：检索包metadata声明MIT，但未附独立LICENSE文件；MedExtract未声明许可证。当前基于用户提供材料做本地工作流改写，保留出处；不把原包重新标为我方开源，不作对外开源发行。

方法核验：[Cochrane搜索研究标准](https://www.cochrane.org/ms/authors/handbooks-and-manuals/mecir-manual/standards-conduct-new-cochrane-intervention-reviews-c1-c75/performing-review-c24-c75/searching-studies-c24-c38)。此为静态审查与辅助脚本验证，不是临床研究实测、统计正确性认证或完整工作台验收。
