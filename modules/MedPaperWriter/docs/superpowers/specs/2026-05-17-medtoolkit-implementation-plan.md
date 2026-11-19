# MedToolkit 医学论文自动化写作系统 - 实现计划

**文档版本**: 1.0
**编写日期**: 2026-05-17
**基于设计文档**: 2026-05-17-medtoolkit-design.md

---

## 1. 实现阶段划分

### 阶段一：基础设施搭建（第1-2天）

| 任务 | 优先级 | 预计工时 | 依赖项 |
|------|--------|----------|--------|
| 1.1 项目目录结构创建 | P0 | 2h | 无 |
| 1.2 依赖包安装 | P0 | 1h | 无 |
| 1.3 LLM客户端实现 | P0 | 4h | 无 |
| 1.4 会话状态管理 | P0 | 4h | 无 |
| 1.5 FastAPI框架搭建 | P0 | 3h | 1.1-1.3 |

### 阶段二：综述模式核心（第3-5天）

| 任务 | 优先级 | 预计工时 | 依赖项 |
|------|--------|----------|--------|
| 2.1 追问专家实现 | P0 | 4h | 1.3 |
| 2.2 提纲专家实现 | P0 | 4h | 1.3 |
| 2.3 逐段审核机制 | P0 | 4h | 1.4 |
| 2.4 综述模式前端界面 | P0 | 6h | 1.5, 2.1-2.3 |
| 2.5 Token监控功能 | P1 | 3h | 1.3 |

### 阶段三：RCT模式核心（第6-8天）

| 任务 | 优先级 | 预计工时 | 依赖项 |
|------|--------|----------|--------|
| 3.1 研究方案解析器 | P0 | 4h | 1.3 |
| 3.2 IMRAD框架生成 | P0 | 4h | 1.3 |
| 3.3 撰写专家实现 | P0 | 4h | 1.3 |
| 3.4 RCT模式前端界面 | P0 | 6h | 1.5, 3.1-3.3 |
| 3.5 线路B接口预留 | P2 | 1h | 3.1 |

### 阶段四：文档生成（第9-10天）

| 任务 | 优先级 | 预计工时 | 依赖项 |
|------|--------|----------|--------|
| 4.1 Word文档生成器 | P0 | 6h | 2.4, 3.4 |
| 4.2 参考文献格式导出 | P0 | 4h | 4.1 |
| 4.3 导出界面优化 | P1 | 2h | 4.1, 4.2 |

### 阶段五：测试与优化（第11-12天）

| 任务 | 优先级 | 预计工时 | 依赖项 |
|------|--------|----------|--------|
| 5.1 功能测试 | P0 | 6h | 阶段一至四 |
| 5.2 前端界面美化 | P1 | 4h | 阶段二、三 |
| 5.3 性能优化 | P1 | 4h | 5.1 |
| 5.4 文档编写 | P1 | 2h | 全部 |

---

## 2. 详细任务清单

### 2.1 阶段一：基础设施搭建

#### 2.1.1 项目目录结构创建

**文件结构**：

```
MedToolkit/
├── MedPaperWriter/
│   ├── app.py                      # FastAPI应用入口
│   ├── main.py                     # CLI入口
│   ├── requirements.txt            # 依赖包
│   ├── .env.example                # 环境变量示例
│   ├── services/                   # 核心服务
│   │   ├── __init__.py
│   │   ├── conversation_manager.py # 会话管理
│   │   ├── outlining_engine.py    # 提纲引擎
│   │   ├── draft_writer.py        # 撰写引擎
│   │   ├── review_manager.py      # 审核管理
│   │   └── document_generator.py  # 文档生成
│   ├── llm/                       # LLM相关
│   │   ├── __init__.py
│   │   ├── client.py              # DeepSeek客户端
│   │   ├── prompts.py             # 专家系统提示词
│   │   └── token_monitor.py       # Token监控
│   ├── routers/                   # API路由
│   │   ├── __init__.py
│   │   ├── mode.py                # 模式选择
│   │   ├── chat.py                # 对话接口
│   │   ├── review.py              # 审核接口
│   │   └── export.py              # 导出接口
│   ├── models/                    # 数据模型
│   │   ├── __init__.py
│   │   ├── session.py             # 会话模型
│   │   ├── outline.py             # 提纲模型
│   │   └── section.py             # 章节模型
│   ├── templates/                  # 前端模板
│   │   ├── index.html             # 主界面
│   │   ├── review.html            # 审核界面
│   │   └── export.html            # 导出界面
│   └── static/                    # 静态文件
│       ├── css/
│       │   └── styles.css         # 样式文件
│       └── js/
│           └── app.js             # 前端逻辑
└── docs/
    └── superpowers/
        └── specs/
            ├── 2026-05-17-medtoolkit-design.md
            └── 2026-05-17-medtoolkit-implementation-plan.md
```

**创建目录命令**：

```bash
mkdir -p MedToolkit/MedPaperWriter/{services,llm,routers,models,templates,static/{css,js}}
```

#### 2.1.2 依赖包安装

**requirements.txt**：

```
fastapi==0.104.1
uvicorn==0.24.0
python-docx==1.1.2
openai==1.52.2
pandas==2.2.3
python-dotenv==1.0.1
pydantic==2.5.2
python-multipart==0.0.6
jinja2==3.1.2
```

**安装命令**：

```bash
pip install -r requirements.txt
```

#### 2.1.3 LLM客户端实现

**文件**: `MedPaperWriter/llm/client.py`

**核心功能**：

```python
class LLMClient:
    """DeepSeek API客户端"""

    def __init__(self, api_key: str = None, model: str = "deepseek-chat"):
        self.api_key = api_key or os.getenv("DEEPSEEK_API_KEY")
        self.model = model
        self.client = OpenAI(
            api_key=self.api_key,
            base_url="https://api.deepseek.com"
        )

    def chat(self,
             messages: list,
             temperature: float = 0.7,
             max_tokens: int = 4000) -> tuple[str, dict]:
        """
        发送对话请求

        返回:
            (response_text, usage_info)
            usage_info包含: prompt_tokens, completion_tokens, total_tokens
        """
        pass

    def generate(self,
                prompt: str,
                system_prompt: str = None,
                temperature: float = 0.7,
                max_tokens: int = 4000) -> tuple[str, dict]:
        """简化接口，生成文本"""
        pass
```

#### 2.1.4 会话状态管理

**文件**: `MedPaperWriter/services/conversation_manager.py`

**核心功能**：

```python
class ConversationManager:
    """会话状态管理器"""

    def __init__(self):
        self.sessions = {}

    def create_session(self, mode: str, user_id: str = None) -> str:
        """创建新会话"""
        session_id = str(uuid.uuid4())
        self.sessions[session_id] = {
            "session_id": session_id,
            "mode": mode,  # "review" | "rct"
            "status": "in_progress",
            "outline": {"confirmed": False, "structure": []},
            "sections": [],
            "current_section": None,
            "context": [],
            "token_usage": {"total": 0}
        }
        return session_id

    def save_progress(self, session_id: str, data: dict):
        """保存会话进度到localStorage"""
        pass

    def restore_session(self, session_id: str) -> dict:
        """从localStorage恢复会话"""
        pass

    def add_context(self, session_id: str, role: str, content: str):
        """添加对话上下文"""
        pass

    def get_context(self, session_id: str) -> list:
        """获取对话上下文"""
        pass
```

#### 2.1.5 FastAPI框架搭建

**文件**: `MedPaperWriter/app.py`

**核心代码结构**：

```python
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from routers import mode, chat, review, export

app = FastAPI(title="MedToolkit - 医学论文自动化写作系统")

# 挂载静态文件
app.mount("/static", StaticFiles(directory="static"), name="static")

# 注册路由
app.include_router(mode.router, prefix="/api/mode", tags=["模式"])
app.include_router(chat.router, prefix="/api/chat", tags=["对话"])
app.include_router(review.router, prefix="/api/review", tags=["审核"])
app.include_router(export.router, prefix="/api/export", tags=["导出"])

@app.get("/")
async def home():
    """主界面"""
    return {"message": "MedToolkit API"}

@app.get("/app")
async def app_page():
    """返回前端页面"""
    return FileResponse("templates/index.html")
```

---

### 2.2 阶段二：综述模式核心

#### 2.2.1 追问专家实现

**文件**: `MedPaperWriter/llm/prompts.py`

**追问专家系统提示词**：

```python
QA_EXPERT_PROMPT = """你是一位资深医学研究方法学专家，擅长通过追问来发现有价值的研究问题。

任务：基于用户提供的研究领域，进行漏斗式追问，逐步聚焦到具体的学术问题。

追问原则：
1. 提问要有层次，从广泛到具体
2. 每个问题要说明提问的理由
3. 每次最多提问2个问题
4. 注意挖掘研究空白和创新点
5. 语言用中文，专业且友好
6. 禁止编造不存在的文献或数据

交互规则：
- 根据用户回答调整追问方向
- 如果用户回答模糊，适当追问澄清
- 当研究问题明确时，提示用户确认并总结

当前进度：[{progress}]
已收集信息：{collected_info}

请开始追问或总结研究问题。
"""
```

**温度设置**: `temperature = 0.8`

#### 2.2.2 提纲专家实现

**提纲专家系统提示词**：

```python
OUTLINE_EXPERT_PROMPT = """你是一位SCI论文结构专家，擅长为综述和研究论文设计提纲。

任务：基于研究问题，生成3级标题的详细论文提纲。

提纲结构规范：
1. 使用数字编号（一级1. 二级1.1 三级1.1.1）
2. 每级标题要精准、学术化
3. 综述提纲通常包含：引言、方法、结果、讨论、结论
4. 根据研究问题特点调整结构

研究问题：{research_question}
研究类型：{study_type}  # 综述/系统评价/Meta分析

请生成详细的3级标题提纲。
"""
```

**温度设置**: `temperature = 0.7`

#### 2.2.3 逐段审核机制

**文件**: `MedPaperWriter/services/review_manager.py`

**核心功能**：

```python
class ReviewManager:
    """审核流程管理器"""

    def __init__(self):
        self.review_queue = []

    def submit_for_review(self, section_id: str, content: dict):
        """提交章节供审核"""
        self.review_queue.append({
            "section_id": section_id,
            "content": content,
            "status": "pending",
            "submitted_at": datetime.now()
        })

    def approve_section(self, section_id: str):
        """审核通过"""
        pass

    def request_revision(self, section_id: str, feedback: str):
        """请求修订"""
        pass

    def get_pending_reviews(self) -> list:
        """获取待审核列表"""
        pass
```

#### 2.2.4 综述模式前端界面

**文件**: `MedPaperWriter/templates/index.html`

**界面布局**：

```
┌─────────────────────────────────────────────────────────────┐
│  综述模式                                                    │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  研究领域输入                                                │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ 请输入您的研究领域...                                 │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                              │
│  AI追问区域                                                  │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ Q1: 您研究的疾病领域是什么？                          │    │
│  │ 理由：了解具体疾病类型有助于聚焦研究范围              │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ [用户输入框]                                         │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                              │
│  [发送]  [清除上下文]                                        │
│                                                              │
│  Token消耗：已使用 1,234  预计剩余 5,000                    │
│  [暂停]  [终止]                                             │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

### 2.3 阶段三：RCT模式核心

#### 2.3.1 研究方案解析器

**核心功能**：

```python
class ProtocolParser:
    """研究方案解析器"""

    def parse(self, protocol_text: str) -> dict:
        """解析研究方案文本"""
        return {
            "study_type": "RCT",
            "population": "...",      # 研究对象
            "intervention": "...",     # 干预措施
            "control": "...",          # 对照
            "outcome": "...",          # 结局指标
            "sample_size": 300,
            "statistical_methods": []
        }
```

#### 2.3.2 IMRAD框架生成

**IMRAD章节定义**：

```python
IMRAD_STRUCTURE = {
    "introduction": {
        "chinese": "引言",
        "sections": ["研究背景", "研究目的", "研究假设"]
    },
    "methods": {
        "chinese": "方法",
        "sections": ["研究设计", "研究对象", "干预措施", "观察指标", "统计分析"]
    },
    "results": {
        "chinese": "结果",
        "sections": ["研究流程", "基线特征", "主要结局", "次要结局", "安全性分析"]
    },
    "discussion": {
        "chinese": "讨论",
        "sections": ["主要发现", "与既往研究对比", "机制探讨", "局限性", "临床意义"]
    },
    "conclusions": {
        "chinese": "结论",
        "sections": ["主要结论", "研究意义"]
    }
}
```

#### 2.3.3 撰写专家实现

**撰写专家系统提示词**：

```python
WRITER_EXPERT_PROMPT = """你是一位严谨的医学论文撰写专家，擅长撰写符合SCI标准的论文。

任务：根据提纲撰写{chapter_name}部分内容。

语言模式：{language}  # 中文/English
研究背景：{background}
提纲：{outline}

写作规范：
1. 严禁捏造文献或数据
2. 如需引用但不确定，标注"[待引用-文献主题]"
3. 避免绝对化表述（如"证明"、"确保"等）
4. 使用客观、学术化的语言
5. 每段150-300字（英文200-350词）

格式要求（中文）：
- 字体：宋体，小四
- 行距：1.5倍
- 首行缩进2字符

格式要求（英文）：
- 字体：Times New Roman，12号
- 行距：1.5倍

请撰写内容。
"""

# 温度设置
WRITER_TEMPERATURE = 0.3
```

#### 2.3.4 RCT模式前端界面

**界面布局**：

```
┌─────────────────────────────────────────────────────────────┐
│  RCT模式                                                    │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ 上传研究方案 (.txt, .docx)                          │    │
│  │ [选择文件]  未选择文件                               │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ 上传统计分析报告 (.txt, .xlsx)                       │    │
│  │ [选择文件]  未选择文件                               │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                              │
│  论文框架预览                                                │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ [√] Introduction                                    │    │
│  │ [√] Methods                                        │    │
│  │ [√] Results                                        │    │
│  │ [√] Discussion                                     │    │
│  │ [√] Conclusions                                    │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                              │
│  [确认框架，开始撰写]                                         │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

### 2.4 阶段四：文档生成

#### 2.4.1 Word文档生成器

**文件**: `MedPaperWriter/services/document_generator.py`

**核心功能**：

```python
from docx import Document
from docx.shared import Pt, Inches
from docx.oxml.ns import qn

class DocumentGenerator:
    """Word文档生成器"""

    def __init__(self):
        self.doc = Document()

    def set_styles(self, language: str = "zh"):
        """设置文档样式"""
        style = self.doc.styles['Normal']
        if language == "zh":
            style.font.name = '宋体'
            style._element.rPr.rFonts.set(qn('w:eastAsia'), '宋体')
            style.font.size = Pt(12)  # 小四
        else:
            style.font.name = 'Times New Roman'
            style.font.size = Pt(12)
        style.paragraph_format.line_spacing = 1.5
        style.paragraph_format.first_line_indent = Inches(0.3)

    def add_heading(self, text: str, level: int = 1):
        """添加标题"""
        heading = self.doc.add_heading(text, level=level)
        heading.alignment = 1  # 居中

    def add_paragraph(self, text: str):
        """添加段落"""
        para = self.doc.add_paragraph(text)
        para.paragraph_format.first_line_indent = Inches(0.3)
        return para

    def add_section(self, title: str, content_zh: str, content_en: str = None):
        """添加中英文对照章节"""
        self.add_heading(title, level=1)
        self.add_paragraph(content_zh)
        if content_en:
            self.add_paragraph(content_en)

    def save(self, output_path: str):
        """保存文档"""
        self.doc.save(output_path)
```

#### 2.4.2 参考文献格式导出

**文件**: `MedPaperWriter/services/reference_formatter.py`

**支持的格式**：

```python
class ReferenceFormatter:
    """参考文献格式化器"""

    SUPPORTED_STYLES = {
        "vancouver": "温哥华格式（医学期刊）",
        "apa": "APA格式（心理学/社会科学）",
        "mla": "MLA格式（人文学科）",
        "chicago": "芝加哥格式（历史学）",
        "gb7714": "GB/T 7714（中文学术）"
    }

    def format_vancouver(self, article: dict) -> str:
        """温哥华格式"""
        authors = article.get("authors", [])
        if isinstance(authors, list):
            authors_str = ", ".join(authors[:3]) + " et al." if len(authors) > 3 else ", ".join(authors)
        else:
            authors_str = authors

        return f"{authors_str}. {article['title']}. {article['journal']}. {article['year']};{article.get('volume', '')}:{article.get('pages', '')}."

    def format_apa(self, article: dict) -> str:
        """APA格式"""
        authors = article.get("authors", [])
        if isinstance(authors, list):
            authors_str = f"{authors[0]} et al." if len(authors) > 2 else " & ".join(authors)
        else:
            authors_str = authors

        return f"{authors_str} ({article['year']}). {article['title']}. {article['journal']}, {article.get('volume', '')}, {article.get('pages', '')}."

    def format_gb7714(self, article: dict) -> str:
        """GB/T 7714格式"""
        authors = article.get("authors", [])
        if isinstance(authors, list):
            authors_str = ", ".join(authors)
        else:
            authors_str = authors

        return f"{authors_str}. {article['title']}[J]. {article['journal']}, {article['year']}, {article.get('volume', '')}({article.get('issue', '')}): {article.get('pages', '')}."
```

---

### 2.5 阶段五：测试与优化

#### 2.5.1 功能测试清单

| 测试项 | 测试内容 | 预期结果 |
|--------|----------|----------|
| T1 | 综述模式 - 追问流程 | AI能够进行漏斗式追问 |
| T2 | 综述模式 - 提纲生成 | 生成3级标题提纲 |
| T3 | 综述模式 - 逐段撰写 | 每段内容符合要求 |
| T4 | 综述模式 - 审核流程 | 支持通过/修订操作 |
| T5 | RCT模式 - 框架生成 | 正确生成IMRAD结构 |
| T6 | RCT模式 - 章节撰写 | 各章节内容完整 |
| T7 | Word导出 - 格式正确 | 符合中/英文格式要求 |
| T8 | 参考文献 - 格式选择 | 各格式正确生成 |
| T9 | Token监控 - 实时显示 | 准确显示消耗 |
| T10 | 会话恢复 - 进度保存 | 刷新后可恢复 |

---

## 3. 里程碑

| 里程碑 | 目标日期 | 完成标志 |
|--------|----------|----------|
| M1 - 基础框架 | 第2天 | API可运行，LLM调用正常 |
| M2 - 综述模式 | 第5天 | 完整流程可使用 |
| M3 - RCT模式 | 第8天 | 完整流程可使用 |
| M4 - 文档导出 | 第10天 | Word导出正常 |
| M5 - 测试通过 | 第12天 | 所有测试项通过 |

---

## 4. 风险与对策

| 风险 | 概率 | 影响 | 对策 |
|------|------|------|------|
| DeepSeek API不稳定 | 中 | 高 | 实现重试机制，添加备用API |
| Token消耗超预期 | 高 | 中 | 严格监控，设置上限提醒 |
| 前端交互复杂 | 中 | 中 | 分阶段开发，及时测试 |
| 学术内容质量不足 | 中 | 高 | 强调用户审核把关 |

---

## 5. 资源需求

| 资源 | 数量 | 说明 |
|------|------|------|
| 开发人员 | 1人 | 全栈开发 |
| API调用额度 | 足够 | DeepSeek API |
| 开发时间 | 12个工作日 | 可根据优先级调整 |

---

## 6. 后续规划

| 功能 | 优先级 | 预计工期 |
|------|--------|----------|
| RCT研究方案生成（线路B） | P1 | 5天 |
| 图表自动生成 | P2 | 7天 |
| EndNote集成 | P2 | 10天 |
| 多语言支持 | P3 | 5天 |

---

**计划结束**

*本计划基于2026-05-17-medtoolkit-design.md设计文档编写，如有调整请及时更新。*
