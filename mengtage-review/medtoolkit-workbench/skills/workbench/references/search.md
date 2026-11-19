# 检索策略模块

输入：研究问题、研究设计、纳排标准、目标数据库及平台、已知关键论文、日期范围。
输出：`01_search/strategy.md` 和 `01_search/search_log.csv`。

- 临床问题的PICO字段与真正放入检索式的概念分开；不能默认 P AND I AND C AND O。优先建立覆盖充分的核心概念组；对照和结局仅在有理由、并经过已知文献测试时加入。
- 不把“糖尿病”默认为2型。未确认的疾病亚型、年龄或终点保留未知。
- 主题词查当前官方词表并记录查阅日期；自由词补充非索引和新文献。Embase必须区分Embase.com与Ovid平台；不能把MeSH当作Emtree。
- 不机械加 humans 或年龄过滤器；明确它们可能依赖索引，记录过滤理由和版本。研究设计过滤器要标明出处和适用数据库。
- 检索结果超过接口上限：优先分页；不支持完整分页时采用无遗漏的日期/其他可穷尽分片，记录每片边界并跨片去重。API限制与结果少不代表课题范围应缩小。
- 用人工已知关键论文测试召回，检查漏项原因，保存策略修订。仅生成检索式时状态为 strategy_draft，不能写 searched。
- 一次询问最关键缺项，支持“稍后继续”；完整已确认的问题不重新走多轮漏斗。

方法依据：[Cochrane 搜索研究标准](https://www.cochrane.org/ms/authors/handbooks-and-manuals/mecir-manual/standards-conduct-new-cochrane-intervention-reviews-c1-c75/performing-review-c24-c75/searching-studies-c24-c38)，查阅2026-11-19；使用适当的PICO要素构建检索，避免无意排除相关记录。
