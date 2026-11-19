# MedStats-Automate 使用指南

## 📋 概述

MedStats-Automate 是一个基于 Python 的医学统计分析自动化工具，支持：
- 数据导入与质量控制
- MICE多重插补处理缺失值
- TableOne基线资料表生成
- 效应量计算
- ROC曲线分析
- 可视化报告

## 🚀 快速开始

### 1. 安装依赖

```bash
pip install pandas numpy scipy scikit-learn matplotlib seaborn openpyxl psutil
```

### 2. 基本用法

使用您的数据集进行分析：

```bash
cd medstats_automate/python
python run_analysis.py --data dataset.csv --strata Group --missing 12345
```

## 📝 命令行参数

| 参数 | 说明 | 示例 |
|------|------|------|
| `--data` | 数据文件路径（必需） | `--data dataset.csv` |
| `--strata` | 分组变量名 | `--strata Group` |
| `--missing` | 缺失值标记（多个用逗号分隔） | `--missing 12345` 或 `--missing 12345,-999` |
| `--output` | 输出目录 | `--output results` |
| `--encoding` | 文件编码 | `--encoding UTF-8` |
| `--impute` | 执行MICE插补 | `--impute` |
| `--impute_m` | 插补数据集数量 | `--impute_m 5` |
| `--effect_vars` | 效应量计算变量 | `--effect_vars Age,Weight,Height` |
| `--roc_predictor` | ROC预测变量 | `--roc_predictor Age` |
| `--roc_outcome` | ROC结局变量 | `--roc_outcome Outcome` |
| `--visualize` | 生成可视化报告 | `--visualize` |

## 💡 使用示例

### 示例 1：基本分析（识别 12345 为缺失值）

```bash
python run_analysis.py \
  --data dataset.csv \
  --strata Group \
  --missing 12345
```

### 示例 2：完整分析（含插补和可视化）

```bash
python run_analysis.py \
  --data dataset.csv \
  --strata Treatment \
  --missing 12345 \
  --impute \
  --visualize \
  --output my_results
```

### 示例 3：多缺失值标记 + ROC分析

```bash
python run_analysis.py \
  --data dataset.csv \
  --strata Group \
  --missing "12345,-999,NA" \
  --roc_predictor Age \
  --roc_outcome Outcome \
  --output roc_results
```

### 示例 4：指定特定变量进行分析

```bash
python run_analysis.py \
  --data dataset.csv \
  --strata Group \
  --missing 12345 \
  --effect_vars Age,BMI,BloodPressure \
  --impute \
  --visualize
```

## 📊 输出文件

运行后会在指定输出目录生成以下文件：

```
output_directory/
├── analysis_result_tableone.xlsx      # TableOne基线资料表
├── analysis_result_effect_size.xlsx   # 效应量计算结果
├── plots/                             # 可视化图表（如果启用）
│   ├── boxplots.png                   # 箱线图
│   ├── violinplots.png                 # 小提琴图
│   ├── histograms.png                 # 直方图
│   ├── qqplots.png                    # Q-Q图
│   ├── forest_plot.png                # 森林图
│   └── correlation_heatmap.png        # 相关矩阵热图
```

## 🔧 缺失值处理

MedStats-Automate 支持多种缺失值标记：

### 单一缺失值

```bash
--missing 12345
```

### 多个缺失值

```bash
--missing "12345,-999,-888"
```

### 常见缺失值类型

| 类型 | 示例 |
|------|------|
| 数值型 | `--missing 12345` |
| 负数型 | `--missing -999` |
| 混合型 | `--missing "12345,-999,NA"` |

## 📈 分析流程

完整分析包含以下步骤：

```
1. 数据导入
   └─ 读取CSV/Excel文件，识别12345等为缺失值

2. 数据质量控制
   ├─ 缺失值分析
   ├─ 正态性检验
   └─ 异常值检测

3. MICE多重插补（可选）
   └─ 自动选择插补方法

4. TableOne基线资料表
   ├─ 分组描述性统计
   ├─ P值计算
   └─ 标准化均数差(SMD)

5. 效应量计算
   ├─ Cohen's d
   ├─ OR/RR/RD
   └─ 95%置信区间

6. ROC分析（可选）
   ├─ AUC计算
   └─ 最佳截断值

7. 可视化报告（可选）
   └─ 多种统计图表
```

## ⚙️ 配置说明

### 数据要求

- 支持格式：CSV, Excel (.xlsx, .xls)
- 第一行应为变量名
- 分组变量应为分类变量（如 0/1 或 Control/Treatment）

### 分组变量说明

`--strata` 参数指定分组变量，用于：
- TableOne分组统计
- 组间P值计算
- 效应量计算

### 变量选择

使用 `--effect_vars` 指定要分析的变量：
```bash
--effect_vars Age,BMI,SBP,DBP
```

如果不指定，将自动选择所有数值变量。

## 🐛 常见问题

### Q1: 数据文件路径包含空格怎么办？

使用引号包裹路径：
```bash
--data "C:\My Documents\dataset.csv"
```

### Q2: 如何处理中文字符编码问题？

指定编码：
```bash
--encoding "GBK"  # 或 "GB2312"
```

### Q3: 缺失值很多应该怎么办？

使用MICE插补：
```bash
--impute --impute_m 10
```

### Q4: 如何查看所有参数？

```bash
python run_analysis.py --help
```

## 📄 技术支持

如遇问题，请检查：
1. Python版本（推荐 3.8+）
2. 依赖包是否完整安装
3. 数据文件路径是否正确
4. 缺失值标记是否正确设置

## 📋 分析报告示例

运行成功后会输出类似以下信息：

```
======================================================================
MedStats-Automate 医学统计分析自动化系统
======================================================================
分析时间: 2024-01-15 10:30:00
数据文件: dataset.csv
分组变量: Group
缺失值标记: 12345
======================================================================

[步骤 1/7] 数据导入
✓ 数据导入成功! 耗时: 0.52秒
  数据维度: 500 行 × 30 列

[步骤 2/7] 数据质量控制
✓ 质量控制完成! 耗时: 0.15秒
  总缺失值: 150 (1.00%)

[步骤 3/7] MICE多重插补
✓ MICE插补完成! 耗时: 2.35秒

[步骤 4/7] TableOne基线资料表生成
✓ TableOne生成完成! 耗时: 0.89秒

[步骤 5/7] 效应量计算
✓ 效应量计算完成! 耗时: 0.45秒

[步骤 6/7] ROC曲线分析
✓ ROC分析完成! 耗时: 1.25秒
  AUC: 0.8234 (95%CI: 0.7856-0.8612)

[步骤 7/7] 可视化报告生成
✓ 可视化报告完成! 耗时: 3.21秒

======================================================================
分析完成!
总耗时: 8.82秒
输出目录: ./analysis_output
======================================================================
```
