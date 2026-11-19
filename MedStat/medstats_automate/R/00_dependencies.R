# Medical Statistics Analysis System (MedStats-Automate)
# 基于SCI发表标准设计的医学统计分析自动化工具
# 版本: 1.0.0
# 
# 主要功能:
# 1. 数据导入与质量控制
# 2. 多重插补(MICE)处理缺失值
# 3. TableOne基线资料表生成
# 4. 效应量计算与置信区间
# 5. 相关与回归分析
# 6. ROC曲线分析
# 7. 可视化报告
#
# 引用来源:
# - tableone: Kazuki Yoshida et al., CRAN v0.13.2
# - mice: Van Buuren & Groothuis-Oudshoorn (2011), JSS v045.i03
# - pROC: Robin et al. (2011), BMC Bioinformatics 12:77
# - ggplot2: Wickham (2016), Springer

# 依赖包检查与安装
required_packages <- c(
  "tableone",      # TableOne基线表
  "mice",          # 多重插补
  "pROC",          # ROC分析
  "ggplot2",       # 可视化
  "dplyr",         # 数据处理
  "tidyr",         # 数据整理
  "openxlsx",      # Excel导出
  "car",           # 方差齐性检验
  "psych",         # 描述性统计
  "rstatix",       # 统计检验
  "survival",      # 生存分析(HR计算)
  "ggpubr",        # 高级可视化
  "gridExtra",     # 多图排版
  "metafor"        # 森林图
)

# 检查并安装缺失的包
for (pkg in required_packages) {
  if (!requireNamespace(pkg, quietly = TRUE)) {
    install.packages(pkg, repos = "https://cloud.r-project.org/")
  }
}

# 加载所有包
invisible(lapply(required_packages, library, character.only = TRUE))

cat("===========================================\n")
cat("Medical Statistics Analysis System\n")
cat("MedStats-Automate v1.0.0 (SCI Standard)\n")
cat("===========================================\n")
cat("所有依赖包已成功加载\n")
