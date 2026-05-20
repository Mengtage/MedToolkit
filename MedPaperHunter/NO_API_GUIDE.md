# 无需API的使用指南（完全免费）

## 🎉 好消息：主功能完全不依赖任何API！

从PubMed检索文献这个核心功能，**不需要任何API Key，完全免费！**

---

## 🚀 三种使用方式（推荐从第1种开始）

### 方式 1：只用检索，不筛选（最简单）
什么都不用配置！
```bash
python3 advanced_search.py
```

### 方式 2：关键词筛选（推荐，完全免费）
不需要任何API，效果也很好！
```python
from advanced_search import LiteratureSearcher

searcher = LiteratureSearcher()
articles = searcher.run_progressive_search(
    topic="你的研究主题",
    use_keyword_filter=True  # 开启关键词筛选
)
```

### 方式 3：AI筛选（需要API，可选）
如果你有API Key才用这个。

---

## 🔧 强化版关键词筛选（我帮你做）

让我增强一下关键词筛选，让它更智能，不需要API也能很好地工作！
