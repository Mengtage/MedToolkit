# MedStats-Automate 高级功能使用指南

## 🎯 新增功能概览

基于 **chart-visualization** 和 **data-analysis** 技能，我们为 MedStats-Automate 添加了以下高级功能：

### 1. 高级数据分析（基于 DuckDB）
- 高性能数据查询
- 详细统计摘要
- 分组统计分析
- 相关矩阵计算
- 数据导出（CSV/JSON）

### 2. 高级可视化（chart-visualization 技能集成）
- 散点图 (Scatter Chart)
- 箱线图 (Boxplot)
- 小提琴图 (Violin Chart)
- 折线图 (Line Chart)
- 直方图 (Histogram)
- 柱状图 (Bar Chart)
- 饼图 (Pie Chart)
- 雷达图 (Radar Chart)
- 相关矩阵热图 (Heatmap)

---

## 🚀 快速开始

### 基本用法

```bash
cd medstats_automate/python
python run_advanced_analysis.py --data dataset.csv --missing 12345 --strata Group
```

### 完整高级分析

```bash
python run_advanced_analysis.py \
  --data dataset.csv \
  --missing 12345 \
  --strata Group \
  --advanced \
  --viz \
  --export
```

---

## 📊 命令行参数详解

| 参数 | 说明 | 示例 |
|------|------|------|
| `--data` | 数据文件路径（必需） | `--data dataset.csv` |
| `--strata` | 分组变量名 | `--strata Group` |
| `--missing` | 缺失值标记 | `--missing 12345` |
| `--vars` | 分析变量列表 | `--vars Age,BMI,BloodPressure` |
| `--advanced` | 启用高级分析（DuckDB） | `--advanced` |
| `--viz` | 启用高级可视化 | `--viz` |
| `--theme` | 可视化主题 | `--theme academy` |
| `--export` | 导出详细结果 | `--export` |
| `--output` | 输出目录 | `--output results` |

---

## 🎨 可视化主题

MedStats-Automate 支持三种可视化主题：

| 主题 | 说明 | 适用场景 |
|------|------|----------|
| `default` | 默认蓝白配色 | 通用场景 |
| `academy` | 学术风格（深蓝、金色） | SCI论文发表 |
| `dark` | 暗色主题 | 演示/深色背景 |

使用示例：
```bash
python run_advanced_analysis.py --data dataset.csv --strata Group --viz --theme academy
```

---

## 📈 使用示例

### 示例 1：基本分析 + 可视化

```bash
python run_advanced_analysis.py \
  --data dataset.csv \
  --missing 12345 \
  --strata Group \
  --viz
```

**输出：**
- `advanced_analysis_tableone.xlsx` - TableOne基线表
- `advanced_analysis_effect_size.xlsx` - 效应量结果
- `visualization_report.html` - 可视化报告（含图表）

---

### 示例 2：高级分析 + 完整统计

```bash
python run_advanced_analysis.py \
  --data dataset.csv \
  --missing 12345 \
  --strata Treatment \
  --advanced \
  --export \
  --output full_analysis
```

**输出：**
- `statistical_summary.csv` - 完整统计摘要
- `group_statistics.csv` - 分组统计详情
- `advanced_analysis_tableone.xlsx`
- `advanced_analysis_effect_size.xlsx`

---

### 示例 3：学术论文风格可视化

```bash
python run_advanced_analysis.py \
  --data dataset.csv \
  --missing 12345 \
  --strata Group \
  --vars Age,BMI,SBP,DBP,HbA1c \
  --viz \
  --theme academy \
  --output academic_output
```

**特点：**
- 图表采用学术风格配色
- 适合 SCI 论文发表
- 包含箱线图、小提琴图、热力图等

---

### 示例 4：自定义变量分析

```bash
python run_advanced_analysis.py \
  --data dataset.csv \
  --missing "12345,-999,NA" \
  --strata Group \
  --vars WBC,RBC,Hb,Plt,ALT,AST,Cr \
  --advanced \
  --viz \
  --export
```

---

## 📁 输出文件说明

### 文件结构

```
output_directory/
├── advanced_analysis_tableone.xlsx      # TableOne基线资料表
├── advanced_analysis_effect_size.xlsx    # 效应量计算结果
│
├── (当启用 --advanced 时)
├── statistical_summary.csv              # 统计摘要
├── group_statistics.csv                # 分组统计
│
├── (当启用 --viz 时)
├── visualization_report.html            # 可视化报告（HTML）
└── charts/                              # 图表文件
    ├── boxplot.png
    ├── violin.png
    ├── heatmap.png
    ├── scatter.png
    └── ...
```

### statistical_summary.csv 示例

```csv
Variable,N,Missing,Mean,SD,Min,Q25,Median,Q75,Max
Age,500,0,45.3,12.5,18,35,45,55,78
BMI,498,2,24.5,3.2,16.8,22.1,24.3,26.8,35.2
SBP,495,5,120.5,15.3,90,110,120,130,180
```

### group_statistics.csv 示例

```csv
Variable,Group,N,Mean,SD,Median,Min,Max
Age,Control,250,44.2,11.8,44,20,75
Age,Treatment,250,46.4,13.1,45,18,78
BMI,Control,248,23.8,2.9,23.5,17.2,32.1
BMI,Treatment,250,25.2,3.4,24.8,16.8,35.2
```

---

## 🔬 高级分析功能详解

### 1. 数据结构检查

使用 `--advanced` 参数时，系统会自动：

1. **识别变量类型**
   - 数值型变量
   - 分类型变量
   - 二分类/多分类

2. **缺失值统计**
   - 每个变量的缺失数量
   - 总缺失率
   - 缺失模式分析

3. **分布特征**
   - 正态性检验
   - 偏度和峰度
   - 异常值检测

### 2. 分组统计分析

当指定 `--strata` 时：

1. **组间比较**
   - 各组均值、标准差
   - 中位数、四分位数
   - 最小值、最大值

2. **效应量计算**
   - Cohen's d
   - Hedges' g
   - OR, RR, RD

3. **P值计算**
   - 正态数据：t检验
   - 非正态数据：Mann-Whitney U
   - 分类数据：卡方检验

### 3. 相关矩阵

自动计算数值变量间的：
- Pearson 相关系数
- Spearman 等级相关
- P值和置信区间

---

## 🎨 可视化功能详解

### 1. 箱线图 (Boxplot)

**用途：** 比较不同组的数值分布

**数据格式：**
```json
[
  {"category": "Control", "value": 10.5},
  {"category": "Control", "value": 12.3},
  {"category": "Treatment", "value": 18.7},
  {"category": "Treatment", "value": 20.1}
]
```

**生成方式：**
- 自动识别分组变量
- 显示中位数、四分位、异常值
- 支持多组比较

### 2. 小提琴图 (Violin Plot)

**用途：** 展示数据分布形态

**特点：**
- 结合箱线图和核密度估计
- 适合展示分布的细节
- 适合样本量≥30的数据

### 3. 散点图 (Scatter Plot)

**用途：** 展示两个变量的关系

**数据格式：**
```json
[
  {"x": 10, "y": 20, "group": "A"},
  {"x": 15, "y": 25, "group": "A"},
  {"x": 20, "y": 30, "group": "B"}
]
```

### 4. 热力图 (Heatmap)

**用途：** 展示相关矩阵

**数据格式：**
```json
[
  {"x": "Age", "y": "BMI", "value": 0.45},
  {"x": "Age", "y": "SBP", "value": 0.52},
  {"x": "BMI", "y": "SBP", "value": 0.38}
]
```

### 5. 直方图 (Histogram)

**用途：** 展示单变量分布

**特点：**
- 自动选择最优的分组数
- 显示频数分布
- 适合正态性判断

---

## 📋 完整分析流程

### 推荐的完整分析流程

```bash
# 1. 基础分析
python run_advanced_analysis.py \
  --data dataset.csv \
  --missing 12345 \
  --strata Group

# 2. 添加高级分析
python run_advanced_analysis.py \
  --data dataset.csv \
  --missing 12345 \
  --strata Group \
  --advanced

# 3. 添加可视化
python run_advanced_analysis.py \
  --data dataset.csv \
  --missing 12345 \
  --strata Group \
  --viz

# 4. 完整分析（推荐）
python run_advanced_analysis.py \
  --data dataset.csv \
  --missing 12345 \
  --strata Group \
  --vars Age,BMI,SBP,DBP,HbA1c \
  --advanced \
  --viz \
  --theme academy \
  --export \
  --output complete_analysis
```

---

## 💡 最佳实践

### 1. 数据准备

**推荐：**
- CSV 格式，避免 Excel 的格式问题
- 变量名使用英文字母和下划线
- 分组变量使用 0/1 或字符串编码
- 缺失值统一使用单一标记（如 12345）

**示例 CSV：**
```csv
ID,Age,BMI,Group,Treatment,Outcome
1,45,24.5,0,0,1
2,52,28.3,0,1,0
3,38,22.1,1,1,1
...
```

### 2. 变量选择

**使用 `--vars` 参数指定关键变量：**

```bash
# 指定实验室指标
--vars WBC,RBC,Hb,Plt,ALT,AST,Cr,BUN

# 指定临床指标
--vars Age,BMI,SBP,DBP,HR

# 指定代谢指标
--vars Glu,HbA1c,TC,TG,HDL,LDL
```

### 3. 可视化主题选择

**SCI论文发表：** 使用 `--theme academy`
```bash
--viz --theme academy
```

**通用场景：** 使用默认主题
```bash
--viz --theme default
```

**演示/深色背景：** 使用暗色主题
```bash
--viz --theme dark
```

### 4. 批量分析

对于多个数据集，使用脚本批量处理：

```bash
#!/bin/bash

for dataset in dataset1.csv dataset2.csv dataset3.csv; do
  python run_advanced_analysis.py \
    --data "$dataset" \
    --missing 12345 \
    --strata Group \
    --advanced \
    --viz \
    --output "results_$(basename $dataset .csv)"
done
```

---

## 🐛 常见问题

### Q1: 如何处理中文字符？

指定编码：
```bash
--encoding "GBK"  # 或 "GB2312"
```

### Q2: 图表生成失败？

检查 Node.js 是否安装：
```bash
node --version
```

如未安装，安装 Node.js：
```bash
# Ubuntu/Debian
sudo apt-get install nodejs

# macOS
brew install node

# Windows
# 从 https://nodejs.org 下载安装
```

### Q3: 可视化性能较慢？

减少分析变量数量：
```bash
--vars Age,BMI,SBP,DBP  # 只分析4个变量
```

### Q4: 如何只生成特定图表？

修改代码中的 `create_medical_report` 函数，注释不需要的图表生成部分。

---

## 📞 技术支持

如遇问题，请检查：

1. **Python 版本**：推荐 3.8+
2. **依赖包**：
   ```bash
   pip install pandas numpy scipy scikit-learn matplotlib seaborn openpyxl psutil
   ```
3. **Node.js**：用于图表生成
4. **数据格式**：确认 CSV 编码和格式正确

---

## 🎯 下一步

- 查看生成的 HTML 报告
- 检查导出的 Excel 文件
- 根据需要调整分析参数
- 如需定制化开发，请联系支持团队
