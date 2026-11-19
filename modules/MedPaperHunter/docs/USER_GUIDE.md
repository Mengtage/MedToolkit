# MedPaperHunter - 用户指南

**版本**: 1.0.0  
**最后更新**: 2026-05-14

## 目录
1. [项目简介](#项目简介)
2. [快速开始](#快速开始)
3. [安装指南](#安装指南)
4. [使用说明](#使用说明)
5. [配置详解](#配置详解)
6. [模块说明](#模块说明)
7. [常见问题](#常见问题)
8. [进阶使用](#进阶使用)

---

## 项目简介

MedPaperHunter 是一个自动化的学术文献检索与整理系统，专为科研人员设计。它可以自动在多个学术平台检索文献、分析内容，并整理成结构化的 Excel 报告。

### 主要功能

- **多平台检索**
  - PubMed（生物医学）
  - Google Scholar（综合学术）
  - arXiv（预印本）
  - 可扩展支持更多平台

- **智能检索**
  - 基于 MeSH 术语推荐检索词
  - 自动生成多平台适配的检索式
  - 支持近7天最新文献检索

- **文献分析**
  - PDF 自动下载与解析
  - 摘要分段提取（背景/方法/结果/结论）
  - AI 全文总结（需配置 API）

- **数据整理**
  - 自动匹配期刊影响因子
  - Excel 格式导出
  - 结构化数据展示

- **定时任务**
  - 每周五晚 20:00 自动执行
  - 灵活的任务配置

---

## 快速开始

### 1. 环境要求

- Python 3.8 或更高版本
- 稳定的网络连接

### 2. 3分钟快速上手

```bash
# 1. 克隆仓库
git clone https://github.com/Mengtage/MedPaperHunter.git
cd MedPaperHunter

# 2. 安装依赖
pip install -r requirements.txt

# 3. 运行测试验证
python test_system.py

# 4. 开始使用
python main.py "你的研究主题"
```

---

## 安装指南

### 标准安装

1. **克隆或下载项目**
   ```bash
   git clone https://github.com/Mengtage/MedPaperHunter.git
   cd MedPaperHunter
   ```

2. **创建虚拟环境（推荐）**
   ```bash
   # 使用 venv
   python -m venv venv
   
   # 激活虚拟环境
   # Linux/Mac:
   source venv/bin/activate
   # Windows:
   venv\Scripts\activate
   ```

3. **安装依赖**
   ```bash
   pip install -r requirements.txt
   ```

4. **验证安装**
   ```bash
   python test_system.py
   ```

### 依赖说明

项目依赖的主要库：

| 库名 | 用途 |
|------|------|
| requests | HTTP 请求 |
| beautifulsoup4 | HTML 解析 |
| lxml | XML/HTML 处理 |
| openpyxl | Excel 文件操作 |
| pandas | 数据处理 |
| pymupdf | PDF 解析 |
| schedule | 定时任务 |

---

## 使用说明

### 基本使用

#### 1. 单次检索

```bash
# 方式1: 命令行参数
python main.py "肿瘤免疫治疗"

# 方式2: 交互式输入
python main.py
# 然后按提示输入研究主题
```

#### 2. 定时任务

```bash
# 启动定时任务（每周五晚20:00执行）
python scheduler.py
```

按 `Ctrl+C` 可停止定时任务。

### 输出说明

检索完成后，结果会保存在 `output/` 目录下，文件名格式为：
```
literature_search_{主题}_{时间戳}.xlsx
```

#### Excel 文件结构

| 列名 | 说明 |
|------|------|
| 发表日期 | 文献发表日期 |
| 期刊名 | 发表期刊名称 |
| 期刊影响因子 | 期刊影响因子（如有） |
| 第一作者名 | 第一作者姓名 |
| 摘要中背景部分 | 摘要背景部分 |
| 摘要中研究方法部分 | 摘要方法部分 |
| 摘要中研究结果部分 | 摘要结果部分 |
| 摘要中结论部分 | 摘要结论部分 |
| AI阅读pdf全文后的总结_关键数据 | AI总结的关键数据 |
| AI阅读pdf全文后的总结_研究优势与局限 | AI总结的优劣势 |
| AI阅读pdf全文后的总结_未来发展方向 | AI总结的研究方向 |

---

## 配置详解

### 环境变量配置

复制 `.env.example` 为 `.env` 并根据需要修改：

```bash
cp .env.example .env
```

### 配置文件 (config.py)

主要配置项：

```python
class Config:
    # 学术平台配置
    PLATFORMS = {
        'pubmed': {
            'url': 'https://pubmed.ncbi.nlm.nih.gov/',
            'name': 'PubMed',
            'carsi_login': True
        },
        # ... 更多平台
    }
    
    # CARSI 机构
    CARSI_INSTITUTION = 'peking university'
    
    # 检索时间范围（天数）
    SEARCH_DAYS = 7
    
    # 输出目录
    OUTPUT_DIR = 'output'
```

### 影响因子数据

编辑 `data/impact_factors.csv` 添加期刊影响因子：

```csv
journal,impact_factor
Nature,69.504
Science,63.714
Cell,66.850
```

---

## 模块说明

### 1. 检索词推荐模块 (search_term_recommender.py)

**功能**：
- 基于主题推荐 MeSH 术语
- 生成 PubMed 检索式
- 转换为其他平台检索式

**使用示例**：
```python
from modules import SearchTermRecommender

recommender = SearchTermRecommender()

# 推荐检索词
terms = recommender.recommend_mesh_terms("cancer immunotherapy")

# 生成检索式
query = recommender.generate_pubmed_query("cancer immunotherapy")
```

### 2. 文献检索模块 (literature_searcher.py)

**功能**：
- 多平台文献检索
- 元数据提取（标题、作者、期刊等）

**使用示例**：
```python
from modules import LiteratureSearcher

searcher = LiteratureSearcher()
articles = searcher.search_pubmed("your query", max_results=20)
```

### 3. PDF 分析模块 (pdf_analyzer.py)

**功能**：
- PDF 下载
- 文本提取
- 摘要分段
- AI 总结（预留接口）

**使用示例**：
```python
from modules import PDFAnalyzer

analyzer = PDFAnalyzer()
analysis = analyzer.analyze_article(article)
```

### 4. Excel 导出模块 (excel_exporter.py)

**功能**：
- 数据整理
- 影响因子匹配
- Excel 导出

**使用示例**：
```python
from modules import ExcelExporter

exporter = ExcelExporter()
output_file = exporter.export_to_excel(articles, analyzed_data, "topic")
```

---

## 常见问题

### Q: 如何添加更多学术平台？

A: 在 `config.py` 的 `PLATFORMS` 字典中添加新平台配置，然后在 `literature_searcher.py` 中实现对应的检索方法。

### Q: 如何配置 AI 总结功能？

A: 在 `.env` 文件中配置相应的 API Key（如 OpenAI 或 Claude），然后修改 `pdf_analyzer.py` 中的 `summarize_pdf` 方法调用真实的 AI API。

### Q: 检索时提示网络错误？

A: 请检查网络连接，部分平台可能需要科学上网或机构网络访问。

### Q: 找不到期刊影响因子？

A: 在 `data/impact_factors.csv` 中添加对应的期刊影响因子数据。

### Q: 如何修改定时任务时间？

A: 编辑 `scheduler.py` 中的 `schedule.every().friday.at("20:00")` 部分。

---

## 进阶使用

### 自定义检索平台

1. 在 `config.py` 添加平台配置
2. 在 `literature_searcher.py` 实现 `search_xxx` 方法
3. 在 `search_term_recommender.py` 实现 `generate_xxx_query` 方法

### 集成 AI API

示例（OpenAI）：
```python
# 在 pdf_analyzer.py 中
import openai
from dotenv import load_dotenv
import os

load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

def summarize_pdf(self, pdf_content):
    text = self.extract_text_from_pdf(pdf_content)
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[
            {"role": "user", "content": f"请总结以下文献...\n\n{text[:4000]}"}
        ]
    )
    # 处理返回结果...
```

### 批量检索多个主题

创建脚本 `batch_search.py`：
```python
from main import main

topics = [
    "cancer immunotherapy",
    "gene editing",
    "machine learning in medicine"
]

for topic in topics:
    main(topic)
```

---

## 技术支持

如有问题，请：
1. 查阅本文档的常见问题部分
2. 查看 GitHub Issues
3. 提交新的 Issue

---

## 许可证

请查看项目根目录的 LICENSE 文件。

---

*祝科研顺利！* 📚✨

