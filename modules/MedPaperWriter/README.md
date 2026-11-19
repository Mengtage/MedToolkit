# 📝 MedPaperWriter

> 医学论文自动化写作系统 - 基于大语言模型的智能论文辅助工具

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green.svg)](https://fastapi.tiangolo.com/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## 🎯 功能特点

### 🔬 综述模式 (Review Mode)
- 智能文献分析与整理
- 自动生成综述论文大纲
- 文献引用格式自动格式化

### 📊 RCT模式 (RCT Mode)
- 支持随机对照试验论文写作
- 标准化论文结构生成
- 中英文双语支持

### ✨ 核心特性
- 🚀 **智能写作**: 基于大语言模型的自动内容生成
- 🌐 **多语言支持**: 支持中文和英文论文输出
- 📄 **格式导出**: 支持导出为 Word 文档 (.docx)
- 🔄 **实时进度**: 导出过程实时进度提示
- 💾 **会话管理**: 自动保存和恢复写作进度
- 🛡️ **安全可靠**: 内置速率限制和安全防护

---

## 🚀 快速开始

### 环境要求

- Python 3.10+
- pip 20.0+

### 安装步骤

```bash
# 克隆项目
git clone <repository-url>
cd MedPaperWriter

# 创建虚拟环境
python3 -m venv venvwriter
source venvwriter/bin/activate

# 安装依赖
pip install -r requirements.txt
```

### 配置 API 密钥

1. 复制 `.env.example` 为 `.env`
2. 在 `.env` 文件中配置您的 LLM API 密钥：

```env
# 使用 DeepSeek (推荐)
LLM_API_KEY=your-api-key-here
LLM_BASE_URL=https://api.deepseek.com/v1
LLM_MODEL=deepseek-v4-pro

# 或使用 OpenAI
# LLM_API_KEY=sk-your-openai-key
# LLM_BASE_URL=https://api.openai.com/v1
# LLM_MODEL=gpt-4o-mini
```

### 启动服务

```bash
python3 app.py
```

服务启动后访问: http://localhost:8001

---

## 📖 使用指南

### 综述模式使用流程

1. **选择模式**: 在首页选择「综述模式」
2. **输入主题**: 输入研究主题或研究问题
3. **生成提纲**: 系统自动生成论文大纲
4. **撰写章节**: 依次撰写各章节内容
5. **审核修订**: 查看并修订生成的内容
6. **导出文档**: 选择语言和格式导出论文

### RCT模式使用流程

1. **选择模式**: 在首页选择「RCT模式」
2. **输入标题**: 输入研究论文标题
3. **撰写章节**: 按顺序撰写各章节（Introduction、Methods、Results等）
4. **审核修订**: 查看并修订内容
5. **导出文档**: 支持中文或英文导出

---

## 🏗️ 项目结构

```
MedPaperWriter/
├── api/                 # API 路由模块
│   ├── routes_chat.py   # 对话交互路由
│   ├── routes_export.py # 文档导出路由
│   ├── routes_mode.py   # 模式选择路由
│   └── routes_review.py # 审核流程路由
├── config/              # 配置模块
│   ├── security.py      # 安全配置
│   └── settings.py      # 应用设置
├── core/                # 核心业务逻辑
│   ├── document_generator.py  # 文档生成器
│   ├── expert_factory.py      # 专家工厂
│   ├── llm_client.py          # LLM 客户端
│   └── translator.py          # 翻译模块
├── services/            # 服务层
│   ├── logger.py        # 日志服务
│   ├── session_manager.py     # 会话管理
│   └── security.py      # 安全服务
├── templates/           # 前端模板
│   └── index.html       # 主页面
├── static/              # 静态资源
│   └── css/             # 样式文件
├── data/                # 数据存储
│   └── sessions/        # 会话数据
├── tests/               # 测试模块
├── app.py               # 应用入口
└── requirements.txt     # 依赖列表
```

---

## 🔌 API 接口

### 模式选择

| 方法 | 端点 | 描述 |
|------|------|------|
| POST | `/api/mode/select` | 选择写作模式 |

### 对话交互

| 方法 | 端点 | 描述 |
|------|------|------|
| POST | `/api/chat/rct/write` | 撰写RCT章节 |
| POST | `/api/chat/review/write` | 撰写综述章节 |

### 文档导出

| 方法 | 端点 | 描述 |
|------|------|------|
| POST | `/api/export/docx` | 导出Word文档 |
| GET | `/api/export/download/{session_id}` | 下载生成的文档 |
| GET | `/api/export/download/progress/{session_id}` | 带进度的文档导出 |

---

## 🔒 安全注意事项

1. **API密钥管理**: 切勿将 `.env` 文件提交到版本控制系统
2. **会话安全**: 使用 UUID4 生成不可预测的会话ID
3. **输入验证**: 所有用户输入均经过验证和清理
4. **速率限制**: 内置请求速率限制防止恶意攻击
5. **日志脱敏**: 敏感信息在日志中进行脱敏处理

---

## 📝 更新日志

### v1.0.0
- ✅ 综述模式完整实现
- ✅ RCT模式完整实现
- ✅ 中英文双语支持
- ✅ Word文档导出
- ✅ 实时进度提示
- ✅ 会话管理系统

---

## 📄 许可证

MIT License - 详见 [LICENSE](LICENSE) 文件

---

## 🤝 贡献指南

欢迎提交 Issue 和 Pull Request！

---

**开发团队** | 医学人工智能实验室
