# MedPaperHunter AI 筛选功能使用指南

## 🎯 你的问题回答

### 1. 这个智能检索工作流依赖什么模型？
- **主检索功能（从PubMed找文献）**：**不依赖任何模型！** 只是调用PubMed的免费API
- **AI筛选功能（可选）**：默认配置为**OpenAI GPT-3.5-turbo**，但完全可选
- **关键词筛选（免费）**：不需要任何API，完全本地运行

### 2. 关闭Trae后还能运行吗？
**完全可以！** 这个项目是：
- 完全独立的Python程序
- 不依赖Trae或其他平台
- 只需要：Python + requests + beautifulsoup4 + pandas + flask
- 可以在任何电脑上运行

### 3. 是否可以接入其他模型？
**完全可以！** `ai_filter.py`是模块化设计：
- 可以轻松添加Claude API
- 可以添加Azure OpenAI
- 可以添加本地模型（比如Llama）
- 甚至可以接入你自己的API

---

## 📦 新增文件一览

| 文件 | 用途 |
|------|------|
| `ai_filter.py` | AI/关键词筛选核心模块 |
| `data/ai_config.json` | AI配置（自动创建） |

---

## 🚀 快速开始（三种筛选方式）

### 方式 1：关键词筛选（免费，推荐先试试）
不需要任何API！

在命令行运行：
```python
from advanced_search import LiteratureSearcher
searcher = LiteratureSearcher()
articles = searcher.run_progressive_search(
    topic="你的研究主题",
    use_keyword_filter=True  # 开启关键词筛选
)
```

### 方式 2：AI筛选（需要OpenAI API Key）
1. 创建 `data/ai_config.json`：
```json
{
    "api_type": "openai",
    "api_key": "sk-your-key-here",
    "api_base": "https://api.openai.com/v1",
    "model": "gpt-3.5-turbo",
    "enabled": true
}
```

2. 运行：
```python
articles = searcher.run_progressive_search(
    topic="你的主题",
    use_ai=True
)
```

### 方式 3：不筛选（默认）
```python
articles = searcher.run_progressive_search("你的主题")
```

---

## 📊 输出文件说明

运行后会生成：
1. `literature_search_<主题>_<时间>.csv` - **保留**的文献
2. `literature_search_<主题>_<时间>_excluded.csv` - **排除**的文献（仅筛选时生成）

CSV包含这些新增列：
- `AI筛选结果`："保留" 或 "排除"
- `AI筛选理由`：为什么这样判断
- `AI筛选置信度`：0-1 之间的分数

---

## 🔧 自定义模型接入指南

想要接入Claude、Azure或其他模型？

修改 `ai_filter.py` 中的 `analyze_relevance_openai` 函数，或添加新函数：

```python
def analyze_relevance_claude(topic, article, config):
    """接入Claude API（示例）"""
    # 你在这里实现Claude的调用
    pass
```

然后在 `filter_articles` 函数中调用即可。

---

## 💡 工作流程图

```
用户输入主题
    ↓
5种检索策略同时搜索PubMed
    ↓
PMID去重
    ↓
【可选】AI/关键词筛选
    ↓
智能分段摘要
    ↓
导出CSV（保留的 + 排除的）
```

---

## ⚙️ 配置说明

### 关键词筛选逻辑
- 从你的主题中提取关键词
- 检查文献的标题和摘要
- 匹配一半以上关键词 → 保留
- 否则 → 排除

### AI筛选提示词
```
你是一个专业的文献筛选助手。请判断这篇文献是否与研究主题相关。
研究主题：{topic}
文献：标题 + 摘要
请输出JSON：
{
  "relevant": true/false,
  "reason": "理由",
  "confidence": 0-1
}
```
