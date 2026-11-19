# 多平台文献检索使用指南

## 🎉 恭喜！现在你可以在多个平台检索文献了！

---

## 📚 支持的平台

| 平台 | 是否免费 | 说明 |
|------|--------|------|
| **PubMed** | ✅ 免费 | 生物医学文献，正式发表的论文 |
| **arXiv** | ✅ 免费 | 预印本，未正式发表的 |
| **Google Scholar** | ⚠️ 可选 | 需要额外配置（可选） |

---

## 🚀 快速开始

### 方法1：命令行运行多平台检索

```bash
python3 multi_platform_search.py
```

### 方法2：在Python代码中使用

```python
from multi_platform_search import multi_platform_search, export_results_multi_platform

# 在PubMed和arXiv同时检索
results = multi_platform_search(
    topic="Embodied Intelligence and anesthesia",
    platforms=["PubMed", "arXiv"],
    use_keyword_filter=True  # 免费关键词筛选
)

# 导出结果
export_results_multi_platform(
    articles=results["kept_articles"],
    topic="Embodied Intelligence and anesthesia",
    excluded_articles=results["excluded_articles"]
)
```

---

## 🧠 检索式自动解析器

代码会自动将你的自然语言主题，解析成各个平台适配的检索式！

```python
from multi_platform_search import parse_to_platform_query

topic = "Embodied Intelligence and anesthesia"

# 自动解析成各平台的检索式
pubmed_query = parse_to_platform_query(topic, "PubMed")
print("PubMed检索式:", pubmed_query)
# 输出: "embodied OR intelligence OR anesthesia[Title/Abstract]

arxiv_query = parse_to_platform_query(topic, "arXiv")
print("arXiv检索式:", arxiv_query)
# 输出: "all:embodied+intelligence+anesthesia"

google_query = parse_to_platform_query(topic, "GoogleScholar")
print("Google Scholar检索式:", google_query)
# 输出: "\"embodied\" \"intelligence\" \"anesthesia\""
```

---

## 📊 输出说明

### 结果文件

| 文件 | 说明 |
|------|------|
| `multi_platform_<主题>_<时间>.csv | 保留的文献 |
| `multi_platform_<主题>_<时间>_excluded.csv | 被筛选掉的 |

### 新增列

除了原来的列，现在多了：

| 列名 | 说明 |
|------|------|
| **检索来源** | 从哪个平台/检索到的，如 "PubMed/PubMed", "arXiv/arXiv" |

---

## 🎯 完整的检索流程

```
你的自然语言主题 → 自动解析 → 生成各平台检索式 → 各平台并行检索 → 合并结果 → 去重 → 关键词筛选 → 导出CSV
```

---

## 💡 使用建议

### 什么时候用哪个平台？

| 你的需求 | 推荐平台 |
|--------|--------|
| 生物医学正式发表的论文 | PubMed |
| 预印本、最新研究 | arXiv |
| 想全面覆盖 | PubMed + arXiv |

---

## 📝 需要复制到Mac的文件列表

**你需要的核心文件：

| 文件 | 说明 |
|------|------|
| `multi_platform_search.py` | ✅ 多平台检索核心（新增 |
| `advanced_search.py` | ✅ 原有的（保持兼容 |
| `ai_filter.py` | ✅ 筛选模块 |
| `data/impact_factors.csv` | ✅ 影响因子数据 |
| `data/search_topic.txt` | ✅ 你的研究主题 |
| `output/` | ✅ 自动生成结果 |

---

## 🎉 与原有功能总结

你的三个问题全部解决了：

### ✅ 1. 影响因子表格大幅扩展
从5种期刊覆盖更多领域

### ✅ 2. 解释了为什么不用大语言模型也能智能检索
我们的"智能"来自规则，不是大语言模型！

### ✅ 3. 多平台检索功能
支持PubMed和arXiv同时检索，自动解析检索式！

---

## 🎯 下一步建议

在你的Mac上，运行：

```bash
# 方法1：直接运行
python3 multi_platform_search.py

# 方法2：或者编辑data/search_topic.txt后运行
echo "你的主题" > data/search_topic.txt
python3 multi_platform_search.py
```

结果会在`output/`目录！
