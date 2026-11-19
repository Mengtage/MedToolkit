# MedPaperHunter - 医学文献检索系统

## 项目概述

MedPaperHunter 是一款面向医学研究者的文献检索辅助工具，基于LLM智能助手帮助用户完成系统评价/Meta分析的全流程文献筛选工作。

### 核心功能

1. **自然语言研究问题解析** - 将用户输入的研究问题智能拆解为PICO/PEO框架
2. **检索词扩展** - 自动生成MeSH词、同义词、缩写、拼写变体
3. **多平台检索式生成** - 支持PubMed、Web of Science、Scopus、arXiv
4. **PubMed直接检索** - 通过NCBI E-utilities API实时检索
5. **多平台合并去重** - 基于PMID和标题相似度智能去重
6. **AI文献筛选** - 自动评估文献相关性并提供筛选理由
7. **Excel导出** - 包含影响因子、筛选结果的完整文献列表

### 技术栈

**后端**
- FastAPI (异步Web框架)
- httpx (异步HTTP客户端)
- openpyxl (Excel文件生成)
- deepseek-chat (LLM模型)

**前端**
- 原生HTML/CSS/JavaScript (无框架依赖)
- Fetch API (异步数据请求)

---

## 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                      前端 (index.html)                     │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐          │
│  │研究问题输入│→│PICO分析 │→│检索执行 │→│结果展示 │          │
│  └─────────┘ └─────────┘ └─────────┘ └─────────┘          │
└─────────────────────────┬───────────────────────────────────┘
                          │ HTTP API
┌─────────────────────────▼───────────────────────────────────┐
│                    后端 (app.py)                             │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐        │
│  │LLMMedicalSearch│ │PubMedFetcher │ │Exporter     │        │
│  │Builder       │ │              │ │             │        │
│  └──────────────┘ └──────────────┘ └──────────────┘        │
└─────────────────────────────────────────────────────────────┘
```

---

## API 设计规范

### 请求/响应模型

使用Pydantic定义强类型模型：

```python
from pydantic import BaseModel, Field
from typing import Optional

class PICOAnalysisRequest(BaseModel):
    question: str = Field(..., description="研究问题")
    frameworks: list[str] = Field(default=["PICO"], description="分析框架")

class SearchStrategiesRequest(BaseModel):
    concepts: dict[str, dict] = Field(..., description="PICO分析结果")
    databases: list[str] = Field(..., description="目标数据库列表")

class ExecuteRequest(BaseModel):
    databases: list[str] = Field(..., description="要检索的数据库")
    strategies: dict[str, str] = Field(..., description="各数据库检索式")
    max_results: int = Field(default=500, description="最大结果数")
    date_range: Optional[str] = Field(None, description="日期范围")
```

### API 端点规范

**1. PICO分析**
```
POST /api/search/analyze
Request: PICOAnalysisRequest
Response: { concepts: dict, strategies: dict, frameworks_detected: list }
```

**2. 执行检索**
```
POST /api/search/execute
Request: ExecuteRequest
Response: { 
    articles: list[Article],
    counts: dict[str, int],
    total: int,
    errors: list[dict]
}
```

**3. 导入CSV**
```
POST /api/search/import-csv
Request: multipart/form-data (file: CSV)
Response: { articles: list[Article], count: int }
```

**4. 去重**
```
POST /api/process/dedup
Request: { articles: list[Article] }
Response: { articles: list[Article], total: int, duplicates_removed: int }
```

**5. AI筛选**
```
POST /api/process/screen
Request: { articles: list[Article], question: str }
Response: { 
    articles: list[Article],
    included_count: int,
    excluded_count: int,
    total: int
}
```

**6. 导出Excel**
```
POST /api/export/excel
Request: { articles: list[Article] }
Response: Binary file (application/vnd.openxmlformats-officedocument.spreadsheetml.sheet)
```

### Article 数据结构

```python
Article = {
    "pmid": str | None,
    "title": str,
    "authors": list[str],
    "journal": str,
    "pub_date": str,
    "abstract": str,
    "doi": str | None,
    "source": str,  # "pubmed" | "wos" | "scopus" | "arxiv" | "csv_import"
    "screening": str | None,  # "included" | "excluded"
    "screening_reason": str | None
}
```

---

## 前端开发规范

### HTML结构规范

使用语义化HTML5标签，清晰的区块划分：

```html
<div class="workflow-container">
    <!-- 步骤1: 研究问题 -->
    <section id="step1-question" class="workflow-step">
        <h3>研究问题</h3>
        <textarea id="researchQuestion" class="input-large"></textarea>
        <button onclick="analyzeQuestion()">分析</button>
    </section>
    
    <!-- 步骤2: PICO展示 -->
    <section id="step2-pico" class="workflow-step" style="display:none;">
        <!-- PICO概念编辑区域 -->
    </section>
    
    <!-- 步骤3: 检索执行 -->
    <section id="step3-search" class="workflow-step" style="display:none;">
        <!-- 检索按钮和进度条 -->
    </section>
    
    <!-- 步骤4: 结果展示 -->
    <section id="step4-results" class="workflow-step" style="display:none;">
        <!-- 去重、AI筛选、导出按钮 -->
    </section>
</div>
```

### CSS 样式规范

**1. 颜色系统**
```css
:root {
    --primary-color: #0066CC;      /* 主色调 - 医学专业蓝 */
    --secondary-color: #1B2A4A;   /* 深蓝色 - 标题/页眉 */
    --success-color: #4CAF50;      /* 成功绿 */
    --warning-color: #FF9800;      /* 警告橙 */
    --danger-color: #F44336;       /* 错误红 */
    --background-light: #F5F7FA;   /* 浅灰背景 */
    --text-primary: #333333;
    --text-secondary: #666666;
}
```

**2. 组件样式**
```css
.btn {
    padding: 10px 24px;
    border: none;
    border-radius: 4px;
    font-size: 14px;
    cursor: pointer;
    transition: all 0.2s;
}

.btn-primary {
    background: var(--primary-color);
    color: white;
}

.btn-primary:hover {
    background: #0052A3;
}

.btn-primary:disabled {
    background: #CCCCCC;
    cursor: not-allowed;
}

.progress-bar-container {
    height: 8px;
    background: #E0E0E0;
    border-radius: 4px;
    overflow: hidden;
}

.progress-bar {
    height: 100%;
    background: var(--primary-color);
    transition: width 0.3s;
}
```

**3. 响应式设计**
```css
@media (max-width: 768px) {
    .process-grid {
        grid-template-columns: 1fr;
    }
    
    .term-tags {
        flex-wrap: wrap;
    }
}
```

### JavaScript 规范

**1. API调用模式**
```javascript
const API_BASE = 'http://localhost:8000';

async function analyzeQuestion() {
    const question = document.getElementById('researchQuestion').value.trim();
    if (!question) {
        alert('请输入研究问题');
        return;
    }
    
    try {
        showLoading('btnAnalyze');
        const response = await fetch(API_BASE + '/api/search/analyze', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                question: question,
                frameworks: ['PICO', 'PEO']
            })
        });
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        
        const data = await response.json();
        displayPICOAnalysis(data.concepts);
        
    } catch (error) {
        console.error('分析失败:', error);
        alert('分析失败: ' + error.message);
    } finally {
        hideLoading('btnAnalyze');
    }
}
```

**2. 错误处理模式**
```javascript
function showError(elementId, message) {
    const errorEl = document.getElementById(elementId);
    errorEl.textContent = message;
    errorEl.style.display = 'block';
}

function hideError(elementId) {
    document.getElementById(elementId).style.display = 'none';
}

function setLoading(buttonId, isLoading) {
    const btn = document.getElementById(buttonId);
    if (isLoading) {
        btn.disabled = true;
        btn.dataset.originalText = btn.textContent;
        btn.textContent = '加载中...';
    } else {
        btn.disabled = false;
        btn.textContent = btn.dataset.originalText || '提交';
    }
}
```

---

## 后端开发规范

### 模块组织

```
backend/
├── app.py                    # FastAPI主应用
├── llm_medical_search.py     # LLM调用和PICO分析
├── medical_search_strategy_builder.py  # 检索式生成
├── pubmed_fetcher.py         # PubMed API调用
├── dedup.py                  # 去重和AI筛选
├── exporter.py               # Excel/CSV导出
└── models.py                 # 共享数据模型
```

### LLM 调用规范

**1. 系统提示词结构**
```python
SYSTEM_PROMPT = """\
You are an expert medical librarian specializing in systematic review search strategy development...

IMPORTANT RULES:
1. Search terms MUST be in English
2. Provide comprehensive synonym expansion
3. MeSH terms should be official NLM descriptors
4. Output ONLY valid JSON, no extra text.

PLATFORM-SPECIFIC SEARCH SYNTAX GUIDES:

=== PubMed (NCBI E-utilities) ===
- MeSH terms: "Term"[MeSH]
- Title/Abstract: "term"[Title/Abstract]
- Boolean: AND, OR, NOT
- Truncation: term*
...
"""
```

**2. 异步LLM调用**
```python
async def _call_llm(client, messages: list[dict]) -> str:
    """异步调用LLM API"""
    response = await client.chat.completions.create(
        model=LLM_MODEL,
        messages=messages,
        temperature=0.3,  # 较低温度保证稳定性
        max_tokens=2000
    )
    return response.choices[0].message.content
```

**3. JSON解析容错**
```python
async def _analyze_question(question: str) -> dict:
    """解析LLM返回的JSON，带容错处理"""
    # ... 调用LLM ...
    content = response.strip()
    
    # 尝试提取JSON
    if content.startswith("```json"):
        content = content[7:]
    if content.endswith("```"):
        content = content[:-3]
    
    # 清理并解析
    content = content.strip()
    return json.loads(content)
```

### 数据库访问规范

**PubMed E-utilities**
```python
PUBMED_EUTILITIES = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

async def fetch_pubmed(query: str, max_results: int = 500) -> list[dict]:
    """通过NCBI E-utilities检索PubMed"""
    search_url = f"{PUBMED_EUTILITIES}/esearch.fcgi"
    fetch_url = f"{PUBMED_EUTILITIES}/efetch.fcgi"
    
    # 1. 搜索获取ID列表
    params = {
        "db": "pubmed",
        "term": query,
        "retmax": max_results,
        "retmode": "json"
    }
    # ... 获取PMID列表 ...
    
    # 2. 获取详细记录
    params = {
        "db": "pubmed",
        "id": ",".join(pmids),
        "retmode": "xml"
    }
    # ... 解析XML获取文章信息 ...
```

---

## 成功的开发经验

### 1. LLM提示词工程

**经验1: 提供平台语法指南**
```python
# ❌ 错误：生成通用检索式
query = "ketamine AND spine surgery"

# ✅ 正确：为每个平台生成正确语法的检索式
wos_query = "TS=(ketamine) AND TS=(spine surgery)"  # Web of Science
scopus_query = "TITLE-ABS-KEY(ketamine AND spine)"  # Scopus
pubmed_query = '"ketamine"[MeSH] OR "ketamine"[Title/Abstract]'  # PubMed
```

**经验2: 多格式兼容解析**
```python
# LLM可能返回多种格式，系统应兼容
# 格式1: ANSWER: YES\nREASON: 理由
# 格式2: YES\t理由
# 格式3: NO - 理由

def parse_response(text):
    # 使用灵活的正则表达式
    match = re.search(r"(?:ANSWER\s*:\s*)?(YES|NO)", text, re.I)
    if match:
        result = match.group(1).upper()
    # 处理reason...
```

### 2. 错误处理策略

**分级错误提示**
```python
# 信息性错误 - 提示用户操作
if not CARSI_credentials:
    return {
        "error": "Web of Science需要机构账号登录",
        "suggestion": "请在官网检索后导入CSV文件",
        "url": "https://www.webofscience.com"
    }

# 预期错误 - 静默处理继续
try:
    articles = await fetch_pubmed(query)
except Exception as e:
    logger.warning(f"PubMed检索失败: {e}")
    articles = []  # 继续处理其他数据库

# 严重错误 - 中止并报告
if not LLM_API_KEY:
    raise HTTPException(500, "LLM API密钥未配置")
```

### 3. 用户体验优化

**渐进式展示**
```javascript
// 步骤1完成后再显示步骤2
function showStep(stepNumber) {
    for (let i = 1; i <= 6; i++) {
        const section = document.getElementById(`step${i}`);
        if (i <= stepNumber) {
            section.style.display = 'block';
        }
    }
}

// 分步进度反馈
function updateProgress(progress, message) {
    document.getElementById('progressBar').style.width = progress + '%';
    document.getElementById('progressText').textContent = message;
}
```

**中间结果导出**
```python
# 去重后即可导出，用户可检查中间结果
@app.post("/api/process/dedup")
async def dedup_articles(request):
    articles = request.articles
    deduped = await perform_dedup(articles)
    
    # 添加"下载初步结果"按钮
    return {
        "articles": deduped,
        "download_url": "/api/export/preliminary"  # 提供中间结果下载
    }
```

### 4. 数据质量保障

**字段标准化**
```python
def normalize_article(raw: dict) -> dict:
    """标准化来自不同来源的文章数据"""
    return {
        "pmid": raw.get("PMID") or raw.get("pmid"),
        "title": normalize_title(raw.get("TI") or raw.get("title", "")),
        "authors": normalize_authors(raw.get("FAU") or raw.get("authors", [])),
        "journal": normalize_journal(raw.get("JT") or raw.get("journal", "")),
        "pub_date": normalize_date(raw.get("DP") or raw.get("pub_date", "")),
        "abstract": normalize_abstract(raw.get("AB") or raw.get("abstract", "")),
        "doi": normalize_doi(raw.get("AID") or raw.get("doi")),
        "source": detect_source(raw)
    }
```

**影响因子自动匹配**
```python
def match_impact_factor(journal: str, if_database: dict) -> str:
    """智能匹配期刊影响因子"""
    journal_lower = journal.lower().strip()
    
    # 精确匹配
    if journal_lower in if_database:
        return str(if_database[journal_lower])
    
    # 部分匹配
    for known, if_value in if_database.items():
        if known in journal_lower or journal_lower in known:
            return str(if_value)
    
    return ""  # 未找到
```

---

## 集成指南

### 1. 前端集成

将MedPaperHunter的工作流程集成到更大的科研工作流应用：

```javascript
// 在您的应用中嵌入文献检索模块
class LiteratureSearchModule {
    constructor(containerId, options = {}) {
        this.container = document.getElementById(containerId);
        this.apiBase = options.apiBase || 'http://localhost:8000';
        this.onComplete = options.onComplete || (() => {});
    }
    
    async start() {
        this.renderQuestionInput();
    }
    
    async analyzeQuestion(question) {
        const response = await fetch(`${this.apiBase}/api/search/analyze`, {
            method: 'POST',
            body: JSON.stringify({ question })
        });
        return response.json();
    }
    
    // ... 其他方法
}
```

### 2. 后端集成

作为微服务集成到更大的系统：

```python
# 您的应用可以直接调用MedPaperHunter的API
import httpx

async def integrated_search(question: str, databases: list[str]):
    async with httpx.AsyncClient() as client:
        # 1. 分析问题
        analysis = await client.post(
            "http://medpaperhunter:8000/api/search/analyze",
            json={"question": question}
        )
        
        # 2. 执行检索
        results = await client.post(
            "http://medpaperhunter:8000/api/search/execute",
            json={
                "databases": databases,
                "strategies": analysis.json()["strategies"]
            }
        )
        
        # 3. 去重
        deduped = await client.post(
            "http://medpaperhunter:8000/api/process/dedup",
            json={"articles": results.json()["articles"]}
        )
        
        return deduped.json()
```

### 3. 数据流集成

MedPaperHunter输出的Article格式可以被下游工具直接使用：

```python
# 输出到PRISMA流程图
def generate_prisma_data(screened_articles):
    included = [a for a in screened_articles if a.get("screening") == "included"]
    excluded = [a for a in screened_articles if a.get("screening") == "excluded"]
    
    return {
        "records_screened": len(screened_articles),
        "records_after_dedup": len(set(a["pmid"] for a in screened_articles)),
        "studies_included": len(included),
        "studies_excluded": len(excluded),
        "reasons_for_exclusion": count_reasons(excluded)
    }
```

---

## 后续扩展建议

### 短期扩展
1. 实现arXiv OAI-PMH接口（计算机/物理领域预印本）
2. 添加更多LLM模型支持（Claude、Gemini）
3. 实现检索历史保存和加载

### 中期扩展
1. 添加PRISMA流程图自动生成
2. 实现文献质量评估工具（ROB量表）
3. 数据提取表格生成
4. 引文分析（被引次数、引用网络）

### 长期扩展
1. 与Zotero/Endnote等文献管理工具集成
2. Meta分析自动化
3. 机器学习辅助的偏倚检测
4. 实时文献更新监控

---

## 联系方式

- 项目仓库: https://github.com/Mengtage/MedPaperHunter
- 问题反馈: GitHub Issues
- 技术讨论: GitHub Discussions

---

*本文档由AI助手生成，最后更新于2026年5月*
