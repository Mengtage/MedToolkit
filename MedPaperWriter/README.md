# MedToolkit - 医学论文自动化写作系统

基于AI的医学论文初稿自动化生成工具，支持综述模式和RCT模式。

## 功能特点

### 综述模式
- 漏斗式追问确定研究问题
- AI生成3级标题提纲
- 逐段撰写与审核
- 支持手动修改提纲

### RCT模式
- 上传研究方案和统计报告
- IMRAD框架搭建
- 章节撰写与审核（IMRAD）
- 多格式参考文献导出

## 技术栈

- 后端：FastAPI + Python
- LLM：DeepSeek API (deepseek-chat)
- 前端：HTML + CSS + JavaScript
- 文档生成：python-docx

## 安装

1. 克隆项目
```bash
cd MedToolkit/MedPaperWriter
```

2. 安装依赖
```bash
pip install -r requirements.txt
```

3. 配置API密钥
```bash
cp .env.example .env
# 编辑.env文件，填入您的DeepSeek API密钥
DEEPSEEK_API_KEY=your_api_key_here
```

## 运行

```bash
python app.py
```

访问 http://localhost:8001

## 使用流程

### 综述模式
1. 选择"综述模式"
2. 输入研究主题
3. 与AI进行漏斗式追问
4. 确认研究问题
5. 审核提纲（或手动修改）
6. 逐段撰写正文
7. 审核每一段内容
8. 导出Word文档

### RCT模式
1. 选择"RCT模式"
2. 上传研究方案
3. 上传统计分析报告
4. 确认IMRAD框架
5. 按章节撰写和审核
6. 导出Word文档

## 项目结构

```
MedPaperWriter/
├── app.py                    # FastAPI应用入口
├── requirements.txt          # 依赖包
├── .env.example             # 环境变量示例
├── services/                # 核心服务
│   ├── session_manager.py   # 会话管理
│   ├── document_generator.py # 文档生成
│   └── reference_formatter.py # 参考文献格式化
├── llm/                     # LLM相关
│   └── client.py            # DeepSeek API客户端
├── routers/                 # API路由
│   ├── mode.py              # 模式选择
│   ├── chat.py              # 对话交互
│   ├── review.py             # 审核流程
│   └── export.py            # 导出
├── models/                  # 数据模型
├── templates/               # 前端模板
│   └── index.html          # 主界面
└── static/                 # 静态文件
    └── css/styles.css      # 样式文件
```

## 参考文献格式

支持以下参考文献格式：
- Vancouver（医学期刊）
- APA（心理学/社会科学）
- MLA（人文学科）
- Chicago（历史学）
- GB/T 7714（中文学术）

## 注意事项

1. 使用前请确保配置有效的DeepSeek API密钥
2. 建议使用Chrome或Firefox浏览器
3. 撰写内容请自行审核，确保学术准确性
4. Token使用量会实时显示，请注意控制成本

## 许可证

MIT License
