# MedPaperHunter - 医学文献智能检索系统

简单易用的医学文献检索工具，通过 Web 界面操作，无需编程背景！

---

## 📖 新手用户必读

无需编程基础，按以下简单步骤即可使用！

### 🚀 快速开始（3步）

#### 第一步：获取 DeepSeek API Key

1. 访问 [DeepSeek 平台](https://platform.deepseek.com/)
2. 注册账号并获取 API Key
3. 保存好您的 API Key（类似于 `sk-xxxxx...`）

#### 第二步：启动系统

根据您的操作系统选择对应的启动方式：

**Windows 用户：**
- 🖱️ 双击 `启动系统.bat` 文件

**macOS 用户：**
- 🖱️ 右键点击 `启动系统.command` → 选择“打开”
- ⚠️ 如提示安全警告，请查看 `docs/macOS_安全设置说明.md`

**Linux 用户：**
- 🖥️ 在终端运行：`python3 start_web_app.py`

#### 第三步：配置并使用

1. 首次运行会自动创建 `.env` 文件
2. 打开 `.env` 文件，填入您的 DeepSeek API Key
3. 保存文件并**重新运行启动脚本**
4. 系统会自动在浏览器中打开 http://localhost:8000
5. 在网页中输入研究主题，开始检索！

---

## ✨ 功能特性

- 🌐 **Web 图形界面** - 美观易用，无需命令行
- 🧠 **智能检索式生成** - 基于 MeSH 术语，自动生成专业检索式
- 🔍 **PubMed 直接检索** - 支持直接通过 API 检索 PubMed
- 📊 **其他平台支持** - 生成 Web of Science/Scopus/arXiv 检索式，支持 CSV 导入
- 🔄 **多平台合并去重** - 智能识别重复文献
- 🤖 **AI 智能筛选** - 自动筛选相关文献并给出原因
- 📄 **Excel 导出** - 支持导出带影响因子的完整文献表
- 📋 **PRISMA 流程图** - 自动生成系统评价筛选流程图

---

## 📁 项目结构（简洁清晰）

```
MedPaperHunter/
├── 📂 backend/              # 后端代码（开发者看）
│   ├── app.py              # Web 服务器主程序
│   ├── dedup.py            # 文献去重和筛选
│   ├── exporter.py         # 导出功能
│   ├── llm_medical_search.py   # LLM 检索策略生成
│   ├── medical_search_strategy_builder.py  # 检索式构建
│   ├── prisma_generator.py # PRISMA 流程图生成
│   └── pubmed_fetcher.py   # PubMed 检索
├── 📂 frontend/            # 前端页面
│   └── index.html          # Web 界面
├── 📂 data/                # 数据文件
│   ├── impact_factors.csv  # 影响因子数据
│   └── update_impact_factors.py  # 影响因子更新脚本
├── 📂 docs/                # 详细文档
├── 📄 start_web_app.py     # Python 启动脚本
├── 📄 启动系统.bat         # Windows 一键启动
├── 📄 启动系统.command     # macOS 一键启动
├── 📄 .env.example         # 配置模板
└── 📄 requirements.txt     # 依赖列表
```

---

## 📂 文档导航（需要时查看）

| 文档 | 说明 |
|------|------|
| [docs/USER_GUIDE.md](docs/USER_GUIDE.md) | 📖 用户使用指南（详细） |
| [docs/START_GUIDE.md](docs/START_GUIDE.md) | 🏁 启动说明 |
| [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) | ❓ 常见问题排查 |
| [docs/macOS_安全设置说明.md](docs/macOS_安全设置说明.md) | 🍎 macOS 安全设置 |

---

## 🔧 开发者手动启动（进阶用户）

如果需要手动启动：

```bash
# 1. 创建虚拟环境（可选）
python -m venv venv
source venv/bin/activate  # macOS/Linux
venv\Scripts\activate     # Windows

# 2. 安装依赖
pip install -r requirements.txt

# 3. 复制并编辑配置
cp .env.example .env
# 编辑 .env，填入您的 API Key

# 4. 启动服务器
cd backend
python -m uvicorn app:app --host 0.0.0.0 --port 8000

# 5. 访问 http://localhost:8000
```

---

## ⚠️ 注意事项

- 请遵守各学术平台的使用条款
- 首次使用需要配置 DeepSeek API Key
- 检索结果会保存在 `output/` 目录（自动创建）

---

## ❓ 常见问题速查

**Q: 提示缺少模块？**
A: 运行 `pip install -r requirements.txt` 安装所有依赖

**Q: API Key 在哪里获取？**
A: 访问 https://platform.deepseek.com/ 注册获取

**Q: 如何停止服务器？**
A: 在运行窗口按 `Ctrl+C`

**Q: 其他问题？**
A: 查看 `docs/` 目录下的详细文档！

---

## 📢 状态说明

✅ **PubMed 模块已完成，无需修改！**

---

## 🌟 祝您使用愉快！

如有问题，请查看 `docs/` 目录下的文档！
