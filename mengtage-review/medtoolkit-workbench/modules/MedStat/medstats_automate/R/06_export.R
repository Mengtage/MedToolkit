#!/usr/bin/env Rscript
# ============================================
# 结果导出模块
# 医学统计分析自动化系统
#
# 输出格式:
# 1. TableOne结果 (Excel格式)
# 2. 效应量结果 (Excel格式)
#
# Excel格式规范:
# - 第一列: 变量名
# - 中间列: 分组统计
# - 最后一列: P值
# - P值保留三位小数
# - 二分类变量只保留"1"/"yes"/"female"水平
# ============================================

export_results <- function(tableone = NULL,
                          effect_size = NULL,
                          correlation = NULL,
                          regression = NULL,
                          roc = NULL,
                          output_dir = "./output",
                          filename_prefix = "medstats_result",
                          format = "xlsx",
                          verbose = TRUE) {
  
  cat("开始导出结果...\n\n")
  
  # 确保输出目录存在
  if (!dir.exists(output_dir)) {
    dir.create(output_dir, recursive = TRUE)
  }
  
  exported_files <- list()
  
  # ============================================
  # 1. 导出TableOne结果
  # ============================================
  if (!is.null(tableone)) {
    cat("[导出 1/2] TableOne基线资料表...\n")
    
    tableone_file <- export_tableone_to_excel(
      tableone = tableone,
      output_dir = output_dir,
      filename = paste0(filename_prefix, "_tableone.xlsx")
    )
    exported_files$tableone <- tableone_file
  }
  
  # ============================================
  # 2. 导出效应量结果
  # ============================================
  if (!is.null(effect_size)) {
    cat("[导出 2/2] 效应量计算结果...\n")
    
    effect_file <- export_effect_size_to_excel(
      effect_size = effect_size,
      output_dir = output_dir,
      filename = paste0(filename_prefix, "_effect_size.xlsx")
    )
    exported_files$effect_size <- effect_file
  }
  
  # ============================================
  # 3. 导出相关性分析结果
  # ============================================
  if (!is.null(correlation)) {
    cat("[导出 3/4] 相关性分析结果...\n")
    
    corr_file <- export_correlation_to_excel(
      correlation = correlation,
      output_dir = output_dir,
      filename = paste0(filename_prefix, "_correlation.xlsx")
    )
    exported_files$correlation <- corr_file
  }
  
  # ============================================
  # 4. 导出回归分析结果
  # ============================================
  if (!is.null(regression)) {
    cat("[导出 4/4] 回归分析结果...\n")
    
    reg_file <- export_regression_to_excel(
      regression = regression,
      output_dir = output_dir,
      filename = paste0(filename_prefix, "_regression.xlsx")
    )
    exported_files$regression <- reg_file
  }
  
  # ============================================
  # 5. 生成分析报告摘要
  # ============================================
  report_file <- generate_analysis_report(
    tableone = tableone,
    effect_size = effect_size,
    correlation = correlation,
    regression = regression,
    roc = roc,
    output_dir = output_dir,
    filename = paste0(filename_prefix, "_report.txt")
  )
  exported_files$report <- report_file
  
  if (verbose) {
    cat("\n========== 导出完成 ==========\n")
    for (name in names(exported_files)) {
      cat(sprintf("  %s: %s\n", name, exported_files[[name]]))
    }
    cat("==============================\n")
  }
  
  return(invisible(exported_files))
}

# 导出TableOne到Excel
export_tableone_to_excel <- function(tableone, output_dir, filename) {
  
  filepath <- file.path(output_dir, filename)
  
  # 创建工作簿
  wb <- createWorkbook()
  
  # ============================================
  # Sheet 1: TableOne主表
  # ============================================
  addWorksheet(wb, "TableOne")
  
  # 获取tableone数据
  tableone_data <- tableone$tableone
  
  # 添加标题
  writeData(wb, "TableOne", "TableOne 基线资料表", 
            startCol = 1, startRow = 1)
  writeData(wb, "TableOne", paste("生成时间:", Sys.time()), 
            startCol = 1, startRow = 2)
  
  # 添加分组信息
  if (!is.null(tableone$strata)) {
    writeData(wb, "TableOne", 
              paste("分组变量:", tableone$strata),
              startCol = 1, startRow = 3)
    writeData(wb, "TableOne", 
              paste("组数:", tableone$groups),
              startCol = 1, startRow = 4)
  }
  
  # 写入TableOne数据
  start_row <- 6
  writeData(wb, "Sheet1", tableone_data, startRow = start_row)
  
  # 添加样式
  headerStyle <- createStyle(textDecoration = "Bold", border = "Bottom")
  addStyle(wb, "TableOne", headerStyle, rows = start_row, cols = 1:ncol(tableone_data))
  
  # ============================================
  # Sheet 2: P值详情
  # ============================================
  addWorksheet(wb, "P_values")
  writeData(wb, "P_values", "组间比较P值详情", startCol = 1, startRow = 1)
  
  if (!is.null(tableone$detailed_stats$p_values)) {
    p_df <- tableone$detailed_stats$p_values
    writeData(wb, "P_values", p_df, startRow = 3)
  }
  
  # ============================================
  # Sheet 3: 正态性检验结果
  # ============================================
  addWorksheet(wb, "Normality_Test")
  writeData(wb, "Normality_Test", "正态性检验结果", startCol = 1, startRow = 1)
  
  if (!is.null(tableone$normality)) {
    norm_df <- do.call(rbind, lapply(names(tableone$normality), function(var) {
      res <- tableone$normality[[var]]
      data.frame(
        Variable = var,
        Test = res$test,
        Statistic = ifelse(is.null(res$W), res$D, res$W),
        P_value = res$p_value,
        Normal = res$normal,
        stringsAsFactors = FALSE
      )
    }))
    writeData(wb, "Normality_Test", norm_df, startRow = 3)
  }
  
  # 保存文件
  saveWorkbook(wb, filepath, overwrite = TRUE)
  
  return(filepath)
}

# 导出效应量到Excel
export_effect_size_to_excel <- function(effect_size, output_dir, filename) {
  
  filepath <- file.path(output_dir, filename)
  
  # 创建工作簿
  wb <- createWorkbook()
  
  # ============================================
  # Sheet 1: 连续变量效应量
  # ============================================
  addWorksheet(wb, "Continuous_Effects")
  writeData(wb, "Continuous_Effects", "连续变量效应量", startCol = 1, startRow = 1)
  writeData(wb, "Continuous_Effects", paste("生成时间:", Sys.time()), 
            startCol = 1, startRow = 2)
  
  # 筛选连续变量结果
  cont_effects <- effect_size$effect_sizes[sapply(effect_size$effect_sizes, 
                                                  function(x) x$type == "continuous")]
  
  if (length(cont_effects) > 0) {
    cont_df <- do.call(rbind, lapply(cont_effects, function(x) {
      data.frame(
        Variable = x$variable,
        Comparison = x$comparison,
        Mean1_SD1 = sprintf("%.2f ± %.2f", x$mean1, x$sd1),
        Mean2_SD2 = sprintf("%.2f ± %.2f", x$mean2, x$sd2),
        Mean_Diff = sprintf("%.3f", x$mean_diff),
        Cohens_d = sprintf("%.3f", x$cohens_d),
        Hedges_g = sprintf("%.3f", x$hedges_g),
        CI_95 = sprintf("(%.3f, %.3f)", x$ci_95_lower, x$ci_95_upper),
        stringsAsFactors = FALSE
      )
    }))
    writeData(wb, "Continuous_Effects", cont_df, startRow = 4)
  }
  
  # ============================================
  # Sheet 2: 二分类变量效应量
  # ============================================
  addWorksheet(wb, "Binary_Effects")
  writeData(wb, "Binary_Effects", "二分类变量效应量", startCol = 1, startRow = 1)
  
  bin_effects <- effect_size$effect_sizes[sapply(effect_size$effect_sizes, 
                                                  function(x) x$type == "binary")]
  
  if (length(bin_effects) > 0) {
    bin_df <- do.call(rbind, lapply(bin_effects, function(x) {
      data.frame(
        Variable = x$variable,
        Event_Rate_Exp = sprintf("%.1f%%", x$rate_exposed * 100),
        Event_Rate_Unexp = sprintf("%.1f%%", x$rate_unexposed * 100),
        OR = sprintf("%.2f", x$odds_ratio),
        OR_CI = sprintf("(%.2f, %.2f)", x$or_ci_lower, x$or_ci_upper),
        RR = sprintf("%.2f", x$risk_ratio),
        RR_CI = sprintf("(%.2f, %.2f)", x$rr_ci_lower, x$rr_ci_upper),
        NNT = sprintf("%.1f", x$nnt),
        stringsAsFactors = FALSE
      )
    }))
    writeData(wb, "Binary_Effects", bin_df, startRow = 3)
  }
  
  # ============================================
  # Sheet 3: 多组比较效应量
  # ============================================
  addWorksheet(wb, "MultiGroup_Effects")
  writeData(wb, "MultiGroup_Effects", "多组比较效应量", startCol = 1, startRow = 1)
  
  multi_effects <- effect_size$effect_sizes[sapply(effect_size$effect_sizes, 
                                                    function(x) x$type == "continuous_multigroup")]
  
  if (length(multi_effects) > 0) {
    multi_df <- do.call(rbind, lapply(multi_effects, function(x) {
      data.frame(
        Variable = x$variable,
        Comparison = x$comparison,
        N_Groups = x$n_groups,
        Eta_squared = sprintf("%.3f", x$eta_squared),
        Omega_squared = sprintf("%.3f", x$omega_squared),
        F_statistic = sprintf("%.2f", x$f_statistic),
        P_value = sprintf("%.3f", round(x$p_value, 3)),
        stringsAsFactors = FALSE
      )
    }))
    writeData(wb, "MultiGroup_Effects", multi_df, startRow = 3)
  }
  
  # 保存文件
  saveWorkbook(wb, filepath, overwrite = TRUE)
  
  return(filepath)
}

# 导出相关性分析结果
export_correlation_to_excel <- function(correlation, output_dir, filename) {
  
  filepath <- file.path(output_dir, filename)
  
  wb <- createWorkbook()
  addWorksheet(wb, "Correlation")
  writeData(wb, "Correlation", "相关性分析结果", startCol = 1, startRow = 1)
  
  if (!is.null(correlation$results)) {
    writeData(wb, "Correlation", correlation$results, startRow = 3)
  }
  
  saveWorkbook(wb, filepath, overwrite = TRUE)
  return(filepath)
}

# 导出回归分析结果
export_regression_to_excel <- function(regression, output_dir, filename) {
  
  filepath <- file.path(output_dir, filename)
  
  wb <- createWorkbook()
  addWorksheet(wb, "Regression")
  writeData(wb, "Regression", "回归分析结果", startCol = 1, startRow = 1)
  
  if (!is.null(regression$coefficients)) {
    writeData(wb, "Regression", regression$coefficients, startRow = 3)
  }
  
  saveWorkbook(wb, filepath, overwrite = TRUE)
  return(filepath)
}

# 生成分析报告摘要
generate_analysis_report <- function(tableone, effect_size, correlation, 
                                     regression, roc, output_dir, filename) {
  
  filepath <- file.path(output_dir, filename)
  
  # 构建报告内容
  report_lines <- c(
    "==========================================",
    "医学统计分析报告摘要",
    "MedStats-Automate v1.0.0",
    paste("生成时间:", Sys.time()),
    "==========================================",
    "",
    "【1. 数据概览】",
    paste("  样本量:", if(!is.null(tableone$tableone_object$data$nrow)) 
      tableone$tableone_object$data$nrow else "N/A"),
    paste("  变量数:", if(!is.null(tableone$tableone_object$data$ncol)) 
      tableone$tableone_object$data$ncol else "N/A"),
    "",
    "【2. TableOne分析】",
    paste("  分组变量:", ifelse(is.null(tableone$strata), "无", tableone$strata)),
    paste("  组数:", ifelse(is.null(tableone$groups), "N/A", tableone$groups)),
    paste("  连续变量数:", length(tableone$factor_vars)),
    paste("  分类变量数:", length(tableone$factor_vars)),
    "",
    "【3. 效应量分析】",
    paste("  计算变量数:", length(effect_size$vars_analyzed)),
    "",
    "==========================================",
    "报告结束",
    "=========================================="
  )
  
  writeLines(report_lines, filepath)
  
  return(filepath)
}
