# 替代API接入指南

如果你有其他API（Claude、国产API等），可以很容易接入！

---

## 🚀 方式1：Claude API接入（示例）

修改 `ai_filter.py`，添加这个函数：

```python
def analyze_relevance_claude(topic: str, article: Dict, config: Dict) -> Tuple[bool, str, float]:
    """
    使用Claude API分析相关性
    
    配置示例:
    {
        "api_type": "claude",
        "api_key": "sk-ant-your-key",
        "api_base": "https://api.anthropic.com/v1",
        "model": "claude-3-haiku-20240307",
        "enabled": true
    }
    """
    try:
        from anthropic import Anthropic
        
        client = Anthropic(
            api_key=config["api_key"],
            base_url=config.get("api_base", "https://api.anthropic.com/v1")
        )
        
        prompt = build_prompt(topic, article["title"], article["abstract"])
        
        response = client.messages.create(
            model=config.get("model", "claude-3-haiku-20240307"),
            max_tokens=1000,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        
        result_text = response.content[0].text.strip()
        
        # 解析结果
        try:
            import json
            result = json.loads(result_text)
            return (
                result.get("relevant", True),
                result.get("reason", ""),
                result.get("confidence", 0.5)
            )
        except:
            if "false" in result_text.lower() or "不相关" in result_text:
                return (False, "Claude判断不相关", 0.5)
            return (True, "Claude判断相关", 0.5)
            
    except Exception as e:
        return (True, f"Claude筛选出错: {str(e)}", 0.0)
```

然后修改 `filter_articles` 函数：
```python
def filter_articles(topic, articles, config=None):
    # ...
    if config["api_type"] == "claude":
        result = analyze_relevance_claude(topic, article, config)
    else:
        result = analyze_relevance_openai(topic, article, config)
    # ...
```

---

## 🔧 方式2：国产API接入（示例）

修改 `ai_filter.py`：

```python
def analyze_relevance_chinese_api(topic: str, article: Dict, config: Dict) -> Tuple[bool, str, float]:
    """
    接入国产API（示例）
    
    配置示例:
    {
        "api_type": "chinese",
        "api_key": "your-key",
        "api_base": "https://api.example.com",
        "model": "your-model",
        "enabled": true
    }
    """
    try:
        import requests
        
        prompt = build_prompt(topic, article["title"], article["abstract"])
        
        response = requests.post(
            f"{config['api_base']}/chat/completions",
            headers={
                "Authorization": f"Bearer {config['api_key']}",
                "Content-Type": "application/json"
            },
            json={
                "model": config.get("model", "your-model"),
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 1000
            },
            timeout=60
        )
        
        data = response.json()
        result_text = data["choices"][0]["message"]["content"].strip()
        
        # 解析结果...
        # ...（同上）
        
    except Exception as e:
        return (True, f"国产API筛选出错: {str(e)}", 0.0)
```

---

## 💡 不想用API？完全没问题！

关键词筛选功能已经很智能了：

```python
articles = searcher.run_progressive_search(
    topic="你的主题",
    use_keyword_filter=True  # 只用这个就行！
)
```

关键词筛选特点：
- ✅ 完全免费
- ✅ 不需要网络
- ✅ 支持同义词
- ✅ 标题匹配权重更高
- ✅ 显示匹配的关键词
