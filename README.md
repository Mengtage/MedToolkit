# MedToolkit - 医学论文自动化写作工具

一个集成化的医学论文写作工具套件，包含文献检索、统计分析和论文自动生成功能。

## 📁 项目结构

```
MedToolkit/
├── data/                      # 数据目录
│   ├── raw/                   # 原始数据
│   └── processed/             # 处理后数据
├── scripts/                   # 分析脚本
├── notebooks/                 # Jupyter notebooks
├── figures/                   # 图表文件
├── tables/                    # 表格文件
├── results/                   # 分析结果
├── manuscript/                # 论文草稿
│   ├── 01_data_preparation.md
│   ├── 02_analysis.md
│   └── 03_manuscript_draft.md
├── tasks/                     # 任务管理
├── MedPaperHunter/            # 文献检索模块
│   ├── output/                # 输出目录
│   └── requirements.txt
├── MedPaperWriter/            # 论文写作模块
│   ├── app.py                 # Web应用入口
│   ├── main.py                # 命令行入口
│   ├── deepseek_client.py     # DeepSeek API客户端
│   ├── reference_processor.py # 参考文献处理
│   ├── paper_writer.py        # 论文内容生成
│   ├── word_generator.py      # Word文档生成
│   ├── templates/             # HTML模板
│   ├── uploads/               # 上传文件
│   ├── output/                # 输出文件
│   └── requirements.txt
└── MedStat/                   # 统计分析模块
    ├── output/                # 输出目录
    └── requirements.txt
```

## 🎯 核心功能

### 1. MedPaperHunter - 文献检索与筛选
- 基于PICO/PEO框架的智能检索策略
- 多数据库检索（PubMed、Embase、Cochrane）
- AI驱动的文献筛选
- 支持Excel/CSV导出

### 2. MedStat - 统计分析
- 数据预处理与清洗
- 描述性统计分析
- 推论统计分析
- 图表生成

### 3. MedPaperWriter - 论文自动生成
- 中英文双语对照
- 符合SCI期刊格式要求
- 自动引用参考文献
- 一键生成Word文档

## 🚀 快速开始

### 安装依赖

```bash
# 安装MedPaperWriter依赖
cd MedPaperWriter
pip install -r requirements.txt
```

### 配置API密钥

```bash
cp .env.example .env
# 编辑.env文件，填入您的DeepSeek API密钥
```

### 运行Web应用

```bash
python app.py
```

访问 http://localhost:8001 即可使用论文写作工具。

## 📝 使用流程

### 流程1：数据准备
参考文档：[manuscript/01_data_preparation.md](manuscript/01_data_preparation.md)
1. 收集参考文献（支持Excel/CSV导入）
2. 准备研究方案文档
3. 整理试验数据

### 流程2：统计分析
参考文档：[manuscript/02_analysis.md](manuscript/02_analysis.md)
1. 数据预处理
2. 描述性统计分析
3. 推论统计分析
4. 生成分析报告

### 流程3：论文写作
参考文档：[manuscript/03_manuscript_draft.md](manuscript/03_manuscript_draft.md)
1. 填写论文信息（标题、期刊、研究目的）
2. 上传参考资料
3. 一键生成论文初稿

## 📄 输出格式

生成的Word文档格式：
- **中文**：宋体，小四号字
- **英文**：Times New Roman，12号字
- **行距**：1.5倍
- **首行缩进**：2字符

## 🔗 与MedPaperHunter衔接

MedPaperWriter支持直接从MedPaperHunter导入筛选后的文献：
1. 在MedPaperHunter导出页面点击"开始写论文"
2. 或通过API接口 `/api/bridge/from-hunter` 传入数据

## 🛠 技术栈

| 组件 | 技术 | 版本 |
|------|------|------|
| 后端框架 | FastAPI | 0.104+ |
| 文档生成 | python-docx | 1.1+ |
| 数据处理 | pandas | 2.2+ |
| LLM服务 | DeepSeek API | - |
| 前端 | HTML/CSS/JavaScript | - |

## 📋 质量控制

本项目遵循以下规范：
- 代码版本控制（Git）
- 数据分析可重复性验证
- 论文格式标准化
- 参考文献引用规范

## 📄 许可证

MIT License

---

**文档版本**: 1.0  
**最后更新**: 2026-05-17
