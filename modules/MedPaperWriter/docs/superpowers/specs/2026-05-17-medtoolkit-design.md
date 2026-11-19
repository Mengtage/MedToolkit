# MedToolkit 医学论文自动化写作系统 - 技术架构设计文档

**文档版本**: 1.0
**编写日期**: 2026-05-17
**作者**: AI Assistant

---

## 1. 项目概览

### 1.1 项目背景

MedToolkit 是一个集成化的医学论文自动化写作系统，旨在帮助医学研究人员快速生成高质量的论文初稿。系统整合了文献检索、统计分析和论文写作三大核心功能，支持两种主要写作模式：综述模式和RCT模式。

### 1.2 核心目标

- 提供智能化的论文写作辅助工具
- 保证学术严谨性和内容质量
- 控制AI使用成本
- 支持中英文双语输出
- 提供灵活的审核机制

### 1.3 技术选型

| 组件 | 技术方案 | 说明 |
|------|----------|------|
| 架构模式 | 模块化单体架构 | 部署简单，便于维护 |
| 后端框架 | FastAPI | 高性能异步API |
| 前端 | HTML + JavaScript | 轻量级，无需构建 |
| LLM服务 | DeepSeek API | deepseek-v4-flash/pro |
| 存储 | localStorage/sessionStorage | 本地会话存储 |
| 文档生成 | python-docx | Word文档生成 |

---

## 2. 系统架构

### 2.1 整体架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                        用户界面层                                  │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────┐  │
│  │  模式选择   │  │  综述模式   │  │  RCT模式    │  │  审核   │  │
│  │   界面     │  │   对话界面  │  │   操作界面  │  │   界面  │  │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────┘  │
├─────────────────────────────────────────────────────────────────┤
│                         API网关层                                  │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │  /api/mode  /api/chat  /api/review  /api/export  /api/rct │ │
│  └─────────────────────────────────────────────────────────────┘ │
├─────────────────────────────────────────────────────────────────┤
│                        核心服务层                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │Conversation │  │  Outlining   │  │      DraftWriter      │  │
│  │  Manager    │  │   Engine     │  │        Engine         │  │
│  └──────────────┘  └──────────────┘  └──────────────────────┘  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │    Review   │  │   Document   │  │       LLMClient       │  │
│  │   Manager   │  │  Generator   │  │   (DeepSeek API)     │  │
│  └──────────────┘  └──────────────┘  └──────────────────────┘  │
├─────────────────────────────────────────────────────────────────┤
│                       存储层                                      │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │        localStorage / sessionStorage                          │ │
│  │  - 会话状态  - 提纲草稿  - 章节内容  - 用户反馈              │ │
│  └─────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 核心组件职责

| 组件 | 英文名 | 职责范围 |
|------|--------|----------|
| 会话管理器 | ConversationManager | 管理多轮对话、上下文、进度恢复 |
| 提纲引擎 | OutliningEngine | 生成3级标题提纲，支持修改 |
| 撰写引擎 | DraftWriter | 根据提纲撰写初稿内容 |
| 审核管理器 | ReviewManager | 管理审核流程、收集反馈、处理修订 |
| 文档生成器 | DocumentGenerator | 生成符合格式的Word文档 |
| LLM客户端 | LLMClient | 调用DeepSeek API，管理token消耗 |

---

## 3. 两种写作模式

### 3.1 综述模式

#### 3.1.1 流程图

```
用户输入标题
     ↓
漏斗式追问交互
（追问专家，temperature=0.8）
     ↓
确定核心学术问题
     ↓
生成论文提纲（3级标题）
（提纲专家，temperature=0.7）
     ↓
用户审核提纲
     ↓
逐段撰写内容
（撰写专家，temperature=0.3）
     ↓
逐段审核（每完成1个3级标题）
     ↓
全部审核通过
     ↓
导出Word文档
```

#### 3.1.2 漏斗式追问设计

追问策略：从宽泛的研究领域开始，根据用户回答逐步缩小范围。

**追问阶段**：

| 阶段 | 追问内容 | 目的 |
|------|----------|------|
| 第一阶段 | 研究领域概述 | 确定研究方向 |
| 第二阶段 | 具体问题挖掘 | 发现研究空白 |
| 第三阶段 | 可行性评估 | 评估研究可行性 |
| 第四阶段 | 创新点确认 | 明确研究价值 |

**系统提示词（追问专家）**：

```
你是一位资深医学研究方法学专家，擅长通过追问来发现有价值的研究问题。

任务：基于用户提供的研究领域，进行漏斗式追问，逐步聚焦到具体的学术问题。

追问原则：
1. 提问要有层次，从广泛到具体
2. 每个问题要说明提问的理由
3. 每次最多提问2个问题
4. 注意挖掘研究空白和创新点
5. 语言用中文，专业且友好

交互规则：
- 根据用户回答调整追问方向
- 如果用户回答模糊，适当追问澄清
- 当研究问题明确时，提示用户确认
```

#### 3.1.3 提纲生成规则

**提纲结构**（3级标题）：

```
1. 引言（一级）
   1.1 研究背景（二级）
       1.1.1 疾病概述
       1.1.2 当前治疗现状
   1.2 研究意义（二级）
       1.2.1 临床需求
       1.2.2 科学价值
   1.3 研究问题（二级）
2. 方法（一级）
   2.1 文献检索策略（二级）
   2.2 纳入与排除标准（二级）
   2.3 数据提取（二级）
   2.4 质量评价（二级）
3. 结果（一级）
   4. 讨论（一级）
   5. 结论（一级）
```

#### 3.1.4 逐段审核机制

每完成一个3级标题的内容编写后：

1. 展示生成的内容（中英文对照）
2. 提供审核选项：
   - 确认通过
   - 提出修改意见
   - 跳过此段
3. 根据用户反馈决定下一步：
   - 通过 → 继续下一段
   - 修改 → 根据意见修订后重新展示

### 3.2 RCT模式

#### 3.2.1 模式说明

RCT模式包含两个并行线路：

**线路A：RCT论文手稿生成**（当前开发）

**线路B：RCT研究方案生成**（暂不开发，预留接口）

#### 3.2.2 线路A流程图

```
用户上传研究方案 + 统计报告
     ↓
AI阅读理解材料
     ↓
搭建论文框架
（Introduction / Methods / Results / Discussion / Conclusions）
     ↓
用户审核框架
     ↓
Introduction 撰写 → 审核
     ↓
Methods 撰写 → 审核
     ↓
Results 撰写 → 审核
     ↓
Discussion 撰写 → 审核
     ↓
Conclusions 撰写 → 审核
     ↓
References / Tables 生成
     ↓
导出Word文档
```

#### 3.2.3 线路B接口预留

```python
# 预留接口：RCT研究方案生成
@app.post("/api/rct/protocol/generate")
async def generate_protocol(
    research_topic: str = Form(...),
    research_type: str = Form("RCT")
):
    """
    预留接口：RCT研究方案生成

    未来实现功能：
    - 基于用户研究主题
    - 生成完整研究方案
    - 包含PICO框架、研究设计、样本量计算等

    当前状态：暂不开发
    """
    return {
        "status": "reserved",
        "message": "此功能暂未开放，敬请期待",
        "estimated_release": "TBD"
    }
```

#### 3.2.4 IMRAD章节审核

每个大章节（IMRAD结构）完成后进行审核：

| 章节 | 审核重点 |
|------|----------|
| Introduction | 研究背景逻辑、研究问题明确性 |
| Methods | 方法描述完整性、可重复性 |
| Results | 数据呈现准确性、统计方法恰当性 |
| Discussion | 结果解释合理性、局限性讨论 |
| Conclusions | 结论是否基于结果、创新点总结 |

---

## 4. 三级专家系统

### 4.1 专家配置

| 专家 | temperature | 语言 | 职责 |
|------|-------------|------|------|
| 追问专家 | 0.8 | 中文 | 漏斗式追问，挖掘研究问题 |
| 提纲专家 | 0.7 | 中文 | 生成3级标题提纲 |
| 撰写专家 | 0.3 | 中文/英文 | 按提纲撰写内容 |

### 4.2 temperature设置理由

- **追问专家（0.8）**：需要保持追问的创造性和灵活性，过低可能导致问题过于机械
- **提纲专家（0.7）**：需要平衡结构规范性和创新性
- **撰写专家（0.3）**：需要严格控制幻觉和学术不端风险

### 4.3 撰写专家系统提示词

```
你是一位严谨的医学论文撰写专家，擅长撰写符合SCI标准的论文。

任务：根据提纲撰写各部分内容。

语言模式：
- 根据用户选择的语言输出（中/英文）
- 英文：Times New Roman风格，学术规范
- 中文：宋体小四风格

写作规范：
1. 严禁捏造文献或数据
2. 如需引用但不确定，标注"[待引用-文献主题]"
3. 避免绝对化表述（如"证明"、"确保"等）
4. 使用客观、学术化的语言
5. 每段150-300字（英文200-350词）

格式要求：
- 段落首行缩进2字符
- 1.5倍行距
- 引用格式：[作者, 年份]

质量检查：
- 检查术语一致性
- 检查逻辑连贯性
- 确保数据描述准确性
```

---

## 5. Token消耗控制

### 5.1 监控机制

实时监控token消耗，包括：

- **已消耗token数**：当前会话已使用的token总量
- **预计剩余消耗**：基于当前进度估算的总消耗
- **成本估算**：基于DeepSeek API定价估算费用

### 5.2 用户控制功能

| 功能 | 说明 |
|------|------|
| 暂停 | 暂停当前AI生成，保留上下文 |
| 终止 | 立即终止当前会话，保存已生成内容 |
| 继续 | 从暂停点恢复生成 |

### 5.3 界面设计

**Token监控区域**（无图标，纯文字）：

```
会话状态：进行中
已消耗Token：12,345
预计总消耗：约 45,000（基于当前进度）
预估费用：约 ¥3.45
[暂停]  [终止]
```

### 5.4 实现方案

```python
class TokenMonitor:
    def __init__(self):
        self.total_tokens = 0
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.cost_per_token = 0.0001  # DeepSeek定价

    def record_usage(self, prompt_tokens: int, completion_tokens: int):
        self.prompt_tokens += prompt_tokens
        self.completion_tokens += completion_tokens
        self.total_tokens = self.prompt_tokens + self.completion_tokens

    def estimate_remaining(self, sections_completed: int, total_sections: int) -> int:
        avg_per_section = self.total_tokens / max(sections_completed, 1)
        return int(avg_per_section * (total_sections - sections_completed))

    def get_cost(self) -> float:
        return self.total_tokens * self.cost_per_token
```

---

## 6. 参考文献格式导出

### 6.1 支持的格式

| 格式 | 适用场景 | 示例期刊 |
|------|----------|----------|
| Vancouver | 医学期刊 | NEJM, Lancet, JAMA |
| APA 7th | 心理学、社会科学 | APA系列期刊 |
| MLA | 人文学科 | MLA系列期刊 |
| Chicago | 历史学等 | Chicago Manual |
| GB/T 7714 | 中文学术期刊 | 中国知网收录期刊 |

### 6.2 导出功能设计

```python
class ReferenceFormatter:
    def __init__(self, style: str = "vancouver"):
        self.style = style

    def format_reference(self, article: dict) -> str:
        """将文献信息格式化为指定格式"""
        if self.style == "vancouver":
            return self._vancouver_format(article)
        elif self.style == "apa":
            return self._apa_format(article)
        elif self.style == "gb7714":
            return self._gb7714_format(article)
        # ... 其他格式

    def export_to_docx(self, references: list, style: str):
        """导出参考文献到Word文档"""
        formatted_refs = [self.format_reference(ref) for ref in references]
        # 使用python-docx生成带编号的参考文献列表
```

### 6.3 界面设计

导出选项（与Word导出同一界面）：

```
导出设置
━━━━━━━━━━━━━━━
参考文献格式：
  ○ Vancouver（医学期刊）
  ○ APA 7th（心理学/社会科学）
  ○ MLA（人文学科）
  ○ Chicago（历史学）
  ○ GB/T 7714（中文学术期刊）

[取消]  [确认导出]
```

---

## 7. 会话状态管理

### 7.1 存储结构

```javascript
// localStorage 存储结构
{
  "medtoolkit_session": {
    "session_id": "uuid-xxx",
    "mode": "review | rct",
    "status": "in_progress | paused | completed",
    "created_at": "2026-05-17T10:00:00Z",
    "updated_at": "2026-05-17T10:30:00Z",
    "outline": {
      "confirmed": true,
      "structure": [...]
    },
    "sections": [
      {
        "id": "1.1.1",
        "title": "疾病概述",
        "content_zh": "...",
        "content_en": "...",
        "status": "approved | pending | revision"
      }
    ],
    "user_feedback": [
      {
        "section_id": "1.1.1",
        "feedback": "需要补充更多流行病学数据",
        "timestamp": "2026-05-17T10:25:00Z"
      }
    ],
    "token_usage": {
      "total": 12345,
      "estimated_total": 45000
    }
  }
}
```

### 7.2 进度恢复

用户关闭浏览器后再次访问时：

1. 检测localStorage中的会话状态
2. 提示用户恢复或新建会话
3. 恢复后跳转到上次编辑位置

---

## 8. 前端界面设计

### 8.1 配色规范

沿用MedPaperHunter的设计系统：

```css
:root {
  /* 主色系 */
  --primary-color: #0066CC;
  --primary-hover: #0052A3;
  --primary-light: #E3F2FD;

  /* 深色系 */
  --secondary-color: #1B2A4A;
  --secondary-light: #2C3E50;

  /* 功能色 */
  --success-color: #4CAF50;
  --warning-color: #FF9800;
  --danger-color: #F44336;
  --info-color: #2196F3;

  /* 中性色 */
  --background-light: #F5F7FA;
  --background-white: #FFFFFF;
  --border-color: #E0E0E0;
  --text-primary: #333333;
  --text-secondary: #666666;
  --text-muted: #999999;
}
```

### 8.2 界面组件规范

#### 按钮样式

```css
.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 10px 24px;
  border: none;
  border-radius: 4px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s ease;
}

.btn-primary {
  background: var(--primary-color);
  color: white;
}

.btn-secondary {
  background: var(--background-white);
  color: var(--text-primary);
  border: 1px solid var(--border-color);
}
```

#### 卡片/面板

```css
.workflow-step {
  background: var(--background-white);
  border-radius: 8px;
  padding: 20px;
  margin-bottom: 12px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}
```

#### 消息提示

```css
.success-msg {
  padding: 12px;
  background: #E8F5E9;
  color: #2E7D32;
  border-left: 3px solid var(--success-color);
  border-radius: 4px;
  font-size: 13px;
}

.error-msg {
  padding: 12px;
  background: #FFEBEE;
  color: #C62828;
  border-left: 3px solid var(--danger-color);
  border-radius: 4px;
  font-size: 13px;
}
```

### 8.3 主界面布局

```
┌─────────────────────────────────────────────────────────────┐
│  MedToolkit - 医学论文自动化写作系统                          │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌───────────────────────┐  ┌───────────────────────┐        │
│  │                       │  │                       │        │
│  │    综述模式            │  │    RCT模式            │        │
│  │                       │  │                       │        │
│  │  输入标题，AI协助      │  │  基于研究方案和       │        │
│  │  挖掘研究问题          │  │  统计分析生成论文     │        │
│  │                       │  │                       │        │
│  └───────────────────────┘  └───────────────────────┘        │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## 9. API接口设计

### 9.1 核心接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/mode/select` | POST | 选择写作模式 |
| `/api/chat` | POST | 发送对话消息 |
| `/api/outline/generate` | POST | 生成提纲 |
| `/api/outline/confirm` | POST | 确认提纲 |
| `/api/section/write` | POST | 撰写章节 |
| `/api/section/review` | POST | 审核章节 |
| `/api/export/docx` | POST | 导出Word文档 |
| `/api/session/status` | GET | 获取会话状态 |
| `/api/session/pause` | POST | 暂停会话 |
| `/api/session/resume` | POST | 恢复会话 |
| `/api/session/terminate` | POST | 终止会话 |

### 9.2 接口响应格式

```json
{
  "success": true,
  "data": { ... },
  "token_usage": {
    "prompt_tokens": 1000,
    "completion_tokens": 500,
    "total": 1500
  },
  "message": "操作成功"
}
```

---

## 10. 质量控制

### 10.1 学术严谨性保障

| 机制 | 说明 |
|------|------|
| 用户审核把关 | 每段内容用户确认后生效 |
| 低temperature | 撰写专家使用低temperature减少幻觉 |
| 引用标注 | 无法确认的引用标记"[待引用]" |
| 术语一致性 | 系统检查全文术语使用 |

### 10.2 错误处理

| 错误类型 | 处理方式 |
|----------|----------|
| API调用失败 | 重试3次，失败后提示用户 |
| Token超限 | 暂停生成，提示用户 |
| 会话过期 | 提示用户恢复或新建 |

---

## 11. 未来扩展

### 11.1 待开发功能

- RCT研究方案生成模块（线路B）
- EndNote/Zotero文献管理工具集成
- 多语言支持（日语、韩语）
- 图表自动生成

### 11.2 性能优化

- 引入缓存机制减少重复调用
- 支持流式输出提升用户体验
- 批量处理减少API调用次数

---

## 12. 附录

### 12.1 文件结构

```
MedToolkit/
├── docs/
│   └── superpowers/
│       └── specs/
│           └── 2026-05-17-medtoolkit-design.md
├── data/
├── scripts/
├── notebooks/
├── figures/
├── tables/
├── results/
├── manuscript/
├── tasks/
├── MedPaperHunter/
├── MedPaperWriter/
│   ├── app.py                 # FastAPI应用
│   ├── main.py                # 主程序入口
│   ├── services/
│   │   ├── conversation_manager.py
│   │   ├── outlining_engine.py
│   │   ├── draft_writer.py
│   │   ├── review_manager.py
│   │   └── document_generator.py
│   ├── llm/
│   │   ├── client.py          # DeepSeek API客户端
│   │   └── prompts.py         # 专家系统提示词
│   ├── templates/
│   │   ├── index.html         # 主界面
│   │   ├── review.html        # 审核界面
│   │   └── export.html        # 导出界面
│   └── static/
│       └── styles.css         # 样式文件
└── MedStat/
```

### 12.2 依赖包

```
fastapi==0.104.1
uvicorn==0.24.0
python-docx==1.1.2
openai==1.52.2
pandas==2.2.3
python-dotenv==1.0.1
```

---

**文档结束**

*本设计文档为MedToolkit项目的技术架构设计，如有问题请及时沟通。*
