# 数据管理规范

## 1. 数据分类

### 1.1 原始数据 (data/raw/)
- **定义**：未经过任何处理的原始数据文件
- **格式**：CSV、Excel、JSON、XML等
- **命名规则**：`raw_<数据源>_<日期>.csv`
- **示例**：`raw_pubmed_search_20240115.csv`

### 1.2 处理后数据 (data/processed/)
- **定义**：经过清洗、转换、整合后的数据
- **格式**：CSV、Excel、JSON
- **命名规则**：`processed_<数据类型>_<版本>.csv`
- **示例**：`processed_references_v1.csv`

## 2. 文件命名规范

### 2.1 通用规则
- 使用小写字母
- 单词之间用下划线分隔
- 包含日期时使用YYYYMMDD格式
- 包含版本号时使用v1, v2格式

### 2.2 示例
```
# 参考文献
references_pubmed.csv
references_embase.csv
references_all_combined.csv

# 试验数据
trial_data_raw.xlsx
trial_data_cleaned.csv
trial_analysis_results.csv

# 研究方案
study_protocol_v1.docx
study_protocol_final.pdf
```

## 3. 数据版本控制

### 3.1 版本号规则
- 主版本号：重大变更（数据结构改变）
- 次版本号：数据更新（新增/修改记录）
- 修订号：小修改（格式调整等）

### 3.2 版本记录
每个数据集应维护版本记录文件：
```
data/processed/
├── processed_references_v1.csv
├── processed_references_v2.csv
└── version_history.md
```

## 4. 数据文档要求

### 4.1 README文件
每个数据目录应有README文件说明：
- 数据来源
- 数据格式
- 字段说明
- 数据收集时间
- 数据质量说明

### 4.2 数据字典
对于结构化数据，应提供数据字典：
- 字段名称
- 数据类型
- 字段说明
- 取值范围
- 缺失值处理方式

## 5. 数据安全

### 5.1 敏感数据处理
- 患者隐私信息应匿名化
- 禁止存储个人身份信息
- 敏感数据应加密存储

### 5.2 访问控制
- 原始数据应限制访问权限
- 处理后数据可适当开放

## 6. 数据生命周期

```
原始数据收集 → 数据清洗 → 数据分析 → 结果验证 → 论文写作 → 数据归档
     ↓              ↓           ↓            ↓            ↓           ↓
  raw/          processed/    results/     results/     manuscript/   archive/
```

---

**文档版本**: 1.0  
**最后更新**: 2026-05-17
