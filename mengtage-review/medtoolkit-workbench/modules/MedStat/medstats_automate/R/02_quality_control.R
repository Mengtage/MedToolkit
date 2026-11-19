#!/usr/bin/env Rscript
# ============================================
# 数据质量控制与清洗模块
# 医学统计分析自动化系统
#
# 功能:
# 1. 缺失值检测与报告
# 2. 分布检测(正态性检验)
# 3. 异常值识别
# 4. 数据清洗建议
# ============================================

quality_control <- function(data, 
                           missing_threshold = 0.5,
                           normality_alpha = 0.05,
                           verbose = TRUE) {
  
  cat("开始数据质量控制...\n\n")
  
  # ============================================
  # 1. 缺失值分析
  # ============================================
  missing_report <- analyze_missing(data)
  
  if (verbose) {
    cat("\n========== 缺失值报告 ==========\n")
    print(missing_report$summary)
    cat("==================================\n")
  }
  
  # ============================================
  # 2. 数值变量分布检测
  # ============================================
  numeric_vars <- names(data)[sapply(data, is.numeric)]
  normality_results <- list()
  
  for (var in numeric_vars) {
    vals <- data[[var]]
    vals_clean <- vals[!is.na(vals)]
    
    if (length(vals_clean) >= 3) {
      # Shapiro-Wilk正态性检验(样本量<5000时推荐)
      if (length(vals_clean) <= 5000) {
        test_result <- shapiro.test(vals_clean)
        normality_results[[var]] <- list(
          test = "Shapiro-Wilk",
          statistic = test_result$statistic,
          p_value = test_result$p.value,
          is_normal = test_result$p.value > normality_alpha
        )
      } else {
        # 大样本使用Kolmogorov-Smirnov检验
        test_result <- ks.test(vals_clean, "pnorm", 
                               mean(vals_clean), sd(vals_clean))
        normality_results[[var]] <- list(
          test = "Kolmogorov-Smirnov",
          statistic = test_result$statistic,
          p_value = test_result$p.value,
          is_normal = test_result$p.value > normality_alpha
        )
      }
    }
  }
  
  if (verbose && length(normality_results) > 0) {
    cat("\n========== 正态性检验结果 ==========\n")
    for (var in names(normality_results)) {
      res <- normality_results[[var]]
      status <- ifelse(res$is_normal, "正态 ✓", "非正态 ✗")
      cat(sprintf("  %s: W=%.4f, p=%.4f [%s]\n",
                  var, res$statistic, res$p_value, status))
    }
    cat("======================================\n")
  }
  
  # ============================================
  # 3. 异常值检测(Tukey方法)
  # ============================================
  outlier_report <- detect_outliers(data, numeric_vars)
  
  if (verbose && length(outlier_report$outliers) > 0) {
    cat("\n========== 异常值检测 ==========\n")
    for (var in names(outlier_report$outliers)) {
      n_outliers <- length(outlier_report$outliers[[var]])
      pct <- n_outliers / nrow(data) * 100
      cat(sprintf("  %s: %d个异常值 (%.1f%%)\n", var, n_outliers, pct))
    }
    cat("=================================\n")
  }
  
  # ============================================
  # 4. 数据质量评分
  # ============================================
  quality_score <- calculate_quality_score(data, missing_report)
  
  if (verbose) {
    cat("\n========== 数据质量评分 ==========\n")
    cat(sprintf("  总体质量评分: %.1f/100\n", quality_score$total))
    cat(sprintf("  完整性评分: %.1f/100\n", quality_score$completeness))
    cat(sprintf("  一致性评分: %.1f/100\n", quality_score$consistency))
    cat("=================================\n")
  }
  
  # ============================================
  # 5. 清洗建议
  # ============================================
  cleaning_suggestions <- generate_cleaning_suggestions(
    data, missing_report, normality_results, outlier_report
  )
  
  if (verbose && length(cleaning_suggestions) > 0) {
    cat("\n========== 清洗建议 ==========\n")
    for (i in seq_along(cleaning_suggestions)) {
      cat(sprintf("  %d. %s\n", i, cleaning_suggestions[[i]]))
    }
    cat("=============================\n")
  }
  
  # 返回完整报告
  return(list(
    summary = list(
      n_rows = nrow(data),
      n_cols = ncol(data),
      n_complete = sum(complete.cases(data)),
      complete_rate = mean(complete.cases(data)) * 100
    ),
    missing = missing_report,
    normality = normality_results,
    outliers = outlier_report$outliers,
    quality_score = quality_score,
    suggestions = cleaning_suggestions,
    vars_to_impute = names(missing_report$by_var)[
      missing_report$by_var$missing_rate > 0 & 
      missing_report$by_var$missing_rate <= missing_threshold
    ]
  ))
}

# 缺失值分析
analyze_missing <- function(data) {
  
  # 按变量统计缺失
  by_var <- data.frame(
    variable = names(data),
    n_total = nrow(data),
    n_missing = sapply(data, function(x) sum(is.na(x))),
    stringsAsFactors = FALSE
  )
  by_var$missing_rate <- by_var$n_missing / by_var$n_total * 100
  
  # 缺失模式矩阵
  missing_pattern <- md.pattern(data, plot = FALSE)
  
  return(list(
    by_var = by_var,
    pattern = missing_pattern,
    total_missing = sum(is.na(data)),
    total_missing_rate = sum(is.na(data)) / (nrow(data) * ncol(data)) * 100
  ))
}

# 异常值检测
detect_outliers <- function(data, numeric_vars, iqr_multiplier = 1.5) {
  
  outliers <- list()
  outlier_summary <- data.frame(
    variable = numeric_vars,
    n_outliers = NA,
    lower_bound = NA,
    upper_bound = NA,
    stringsAsFactors = FALSE
  )
  
  for (var in numeric_vars) {
    vals <- data[[var]]
    vals_clean <- vals[!is.na(vals)]
    
    if (length(vals_clean) >= 4) {
      Q1 <- quantile(vals_clean, 0.25)
      Q3 <- quantile(vals_clean, 0.75)
      IQR <- Q3 - Q1
      
      lower_bound <- Q1 - iqr_multiplier * IQR
      upper_bound <- Q3 + iqr_multiplier * IQR
      
      is_outlier <- vals < lower_bound | vals > upper_bound
      outlier_idx <- which(is_outlier)
      
      if (length(outlier_idx) > 0) {
        outliers[[var]] <- data.frame(
          row = outlier_idx,
          value = vals[outlier_idx],
          bound = ifelse(vals[outlier_idx] < lower_bound, "low", "high")
        )
      }
      
      outlier_summary$n_outliers[outlier_summary$variable == var] <- sum(is_outlier)
      outlier_summary$lower_bound[outlier_summary$variable == var] <- lower_bound
      outlier_summary$upper_bound[outlier_summary$variable == var] <- upper_bound
    }
  }
  
  return(list(
    outliers = outliers,
    summary = outlier_summary
  ))
}

# 数据质量评分
calculate_quality_score <- function(data, missing_report) {
  
  # 完整性评分(基于缺失率)
  completeness <- 100 - missing_report$total_missing_rate
  
  # 一致性评分(基于异常值)
  numeric_vars <- names(data)[sapply(data, is.numeric)]
  if (length(numeric_vars) > 0) {
    outlier_count <- 0
    for (var in numeric_vars) {
      outlier_count <- outlier_count + sum(is_outlier(data[[var]]))
    }
    consistency <- max(0, 100 - outlier_count / (nrow(data) * length(numeric_vars)) * 100)
  } else {
    consistency <- 100
  }
  
  # 总体评分
  total <- (completeness * 0.6 + consistency * 0.4)
  
  return(list(
    completeness = completeness,
    consistency = consistency,
    total = total
  ))
}

# 生成清洗建议
generate_cleaning_suggestions <- function(data, missing_report, 
                                          normality_results, outlier_report) {
  
  suggestions <- list()
  
  # 缺失值建议
  high_missing_vars <- missing_report$by_var$variable[
    missing_report$by_var$missing_rate > 50
  ]
  if (length(high_missing_vars) > 0) {
    suggestions <- c(suggestions, 
      sprintf("变量 %s 缺失率>50%%, 建议考虑剔除或与专家确认",
              paste(high_missing_vars, collapse = ", "))
    )
  }
  
  # 非正态变量建议
  non_normal_vars <- names(normality_results)[
    !sapply(normality_results, function(x) x$is_normal)
  ]
  if (length(non_normal_vars) > 0) {
    suggestions <- c(suggestions,
      sprintf("变量 %s 不服从正态分布, 描述统计建议使用中位数(IQR)",
              paste(non_normal_vars, collapse = ", "))
    )
  }
  
  return(suggestions)
}

# 辅助函数:判断异常值
is_outlier <- function(x) {
  Q1 <- quantile(x, 0.25, na.rm = TRUE)
  Q3 <- quantile(x, 0.75, na.rm = TRUE)
  IQR <- Q3 - Q1
  x < (Q1 - 1.5 * IQR) | x > (Q3 + 1.5 * IQR)
}
