#!/usr/bin/env Rscript
# ============================================
# 医学统计分析自动化主程序
# MedStats-Automate v1.0.0
# 
# 使用方法:
# Rscript medstats_main.R --data <数据文件> --config <配置文件> --output <输出目录>
#
# 支持的数据格式: .csv, .xlsx, .xls
#
# 作者: MedStats Team
# ============================================

library(argparser)
library(yaml)

# 命令行参数解析
arg <- arg_parser("医学统计分析自动化程序")
arg <- add_argument(arg, "--data", help = "数据文件路径", type = "character")
arg <- add_argument(arg, "--config", help = "配置文件路径", type = "character", default = "config.yaml")
arg <- add_argument(arg, "--output", help = "输出目录", type = "character", default = "./output")
arg <- add_argument(arg, "--groups", help = "实验组数(1/2/3+)", type = "integer", default = 2)
arg <- add_argument(arg, "--strata", help = "分组变量名", type = "character", default = NULL)
arg <- add_argument(arg, "--impute_vars", help = "需要插补的变量(逗号分隔)", type = "character", default = NULL)
arg <- add_argument(arg, "--effect_vars", help = "效应量计算变量(逗号分隔)", type = "character", default = NULL)
arg <- add_argument(arg, "--roc_var_a", help = "ROC分析变量a(诊断指标)", type = "character", default = NULL)
arg <- add_argument(arg, "--roc_var_b", help = "ROC分析变量b(诊断标准)", type = "character", default = NULL)
arg <- add_argument(arg, "--verbose", help = "详细输出", flag = TRUE)

# 解析参数
argv <- parse_args(arg)

# 创建输出目录
if (!dir.exists(argv$output)) {
  dir.create(argv$output, recursive = TRUE)
}

# 加载配置文件
if (file.exists(argv$config)) {
  config <- read_yaml(argv$config)
} else {
  config <- list()
}

# 设置随机种子(保证可重复性)
set.seed(config$seed %||% 42)

# 加载所有模块
source("R/01_data_import.R")
source("R/02_quality_control.R")
source("R/03_mice_imputation.R")
source("R/04_tableone.R")
source("R/05_effect_size.R")
source("R/06_export.R")
source("R/07_visualization.R")
source("R/08_correlation_regression.R")
source("R/09_roc_analysis.R")

# ============================================
# 主程序流程
# ============================================

main <- function() {
  
  cat("\n===========================================\n")
  cat("医学统计分析自动化程序\n")
  cat(paste0("开始时间: ", Sys.time(), "\n"))
  cat("===========================================\n\n")
  
  # Step 1: 数据导入
  cat("[Step 1/9] 数据导入...\n")
  data <- import_data(argv$data)
  
  # Step 2: 数据质量控制
  cat("[Step 2/9] 数据质量控制与清洗...\n")
  qc_report <- quality_control(data)
  
  # Step 3: 多重插补
  if (!is.null(argv$impute_vars) || config$auto_impute) {
    cat("[Step 3/9] 多重插补(MICE)...\n")
    imp_result <- mice_imputation(data, 
                                  vars = if(!is.null(argv$impute_vars)) {
                                    strsplit(argv$impute_vars, ",")[[1]]
                                  } else {
                                    NULL
                                  },
                                  m = config$mice_m %||% 5,
                                  maxit = config$mice_maxit %||% 10)
    data <- imp_result$data
  }
  
  # Step 4: TableOne生成
  cat("[Step 4/9] 生成TableOne基线资料表...\n")
  tableone_result <- generate_tableone(
    data = data,
    groups = argv$groups,
    strata = argv$strata,
    config = config
  )
  
  # Step 5: 效应量计算
  cat("[Step 5/9] 计算效应量与95%CI...\n")
  effect_result <- calculate_effect_size(
    data = data,
    vars = if(!is.null(argv$effect_vars)) {
      strsplit(argv$effect_vars, ",")[[1]]
    } else {
      NULL
    },
    groups = argv$groups,
    strata = argv$strata,
    config = config
  )
  
  # Step 6: 导出结果
  cat("[Step 6/9] 导出Excel结果...\n")
  export_results(
    tableone = tableone_result,
    effect_size = effect_result,
    output_dir = argv$output
  )
  
  # Step 7: 可视化
  cat("[Step 7/9] 生成可视化报告...\n")
  visualization_report(
    data = data,
    output_dir = argv$output,
    config = config
  )
  
  # Step 8: 相关与回归分析
  cat("[Step 8/9] 相关与回归分析...\n")
  reg_result <- correlation_regression(
    data = data,
    config = config
  )
  
  # Step 9: ROC分析
  if (!is.null(argv$roc_var_a) && !is.null(argv$roc_var_b)) {
    cat("[Step 9/9] ROC曲线分析...\n")
    roc_result <- roc_analysis(
      data = data,
      predictor = argv$roc_var_a,
      outcome = argv$roc_var_b,
      output_dir = argv$output
    )
  }
  
  cat("\n===========================================\n")
  cat("分析完成!\n")
  cat(paste0("结束时间: ", Sys.time(), "\n"))
  cat(paste0("输出目录: ", argv$output, "\n"))
  cat("===========================================\n")
  
  return(list(
    tableone = tableone_result,
    effect_size = effect_result,
    qc_report = qc_report,
    regression = reg_result
  ))
}

# 执行主程序
if (!interactive()) {
  result <- main()
}
