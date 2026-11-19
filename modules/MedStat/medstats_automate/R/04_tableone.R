#!/usr/bin/env Rscript
# ============================================
# TableOne基线资料表生成模块
# 医学统计分析自动化系统
#
# 基于: tableone包 (Kazuki Yoshida et al.)
# CRAN版本: v0.13.2
#
# 功能:
# 1. 自动正态性检验与统计方法选择
# 2. 分组描述性统计(均值±SD / 中位数[IQR])
# 3. 组间比较P值计算
# 4. 标准化均数差(SMD)计算
# 5. 支持多组比较与多重比较校正
# ============================================

generate_tableone <- function(data,
                             groups = 2,
                             strata = NULL,
                             factor_vars = NULL,
                             nonnormal_vars = NULL,
                             exact_vars = NULL,
                             config = list(),
                             verbose = TRUE) {
  
  cat("开始生成TableOne基线资料表...\n\n")
  
  # ============================================
  # 1. 确定分析变量
  # ============================================
  all_vars <- names(data)
  
  # 确定分组变量
  if (is.null(strata)) {
    # 如果未指定，默认使用第一个可能是分组的变量
    cat("警告: 未指定分组变量，将生成整体描述性统计表\n")
    has_strata <- FALSE
    strata <- NULL
  } else {
    has_strata <- TRUE
    cat(sprintf("分组变量: %s\n", strata))
  }
  
  # 确定分类变量
  if (is.null(factor_vars)) {
    factor_vars <- names(data)[sapply(data, is.factor) | sapply(data, is.character)]
  }
  
  # 确定连续变量
  cont_vars <- setdiff(all_vars, c(strata, factor_vars))
  
  cat(sprintf("分类变量: %d个\n", length(factor_vars)))
  cat(sprintf("连续变量: %d个\n\n", length(cont_vars)))
  
  # ============================================
  # 2. 正态性检验(为后续统计方法选择提供依据)
  # ============================================
  normality_results <- list()
  auto_nonnormal <- c()
  
  for (var in cont_vars) {
    vals <- data[[var]]
    vals_clean <- vals[!is.na(vals)]
    
    if (length(vals_clean) >= 3) {
      # Shapiro-Wilk检验 (样本量<5000)
      if (length(vals_clean) <= 5000) {
        test <- shapiro.test(vals_clean)
        is_normal <- test$p.value > 0.05
        normality_results[[var]] <- list(
          test = "Shapiro-Wilk",
          W = test$statistic,
          p_value = test$p.value,
          normal = is_normal
        )
      } else {
        # Kolmogorov-Smirnov检验 (大样本)
        test <- ks.test(vals_clean, "pnorm")
        is_normal <- test$p.value > 0.05
        normality_results[[var]] <- list(
          test = "Kolmogorov-Smirnov",
          D = test$statistic,
          p_value = test$p.value,
          normal = is_normal
        )
      }
      
      # 如果指定自动判断非正态
      if (isTRUE(config$auto_detect_nonnormal) && !is_normal) {
        auto_nonnormal <- c(auto_nonnormal, var)
      }
    }
  }
  
  # 合并自动检测的非正态变量
  if (length(auto_nonnormal) > 0) {
    nonnormal_vars <- unique(c(nonnormal_vars, auto_nonnormal))
  }
  
  if (verbose && length(normality_results) > 0) {
    cat("========== 正态性检验结果 ==========\n")
    for (var in names(normality_results)) {
      res <- normality_results[[var]]
      status <- ifelse(res$normal, "正态", "非正态")
      cat(sprintf("  %s: %s检验, p=%.4f [%s]\n",
                  var, res$test, res$p_value, status))
    }
    cat("====================================\n\n")
  }
  
  # ============================================
  # 3. 方差齐性检验
  # ============================================
  variance_homogeneity <- list()
  
  if (has_strata && length(cont_vars) > 0) {
    for (var in cont_vars) {
      groups_data <- split(data[[var]], data[[strata]])
      groups_data <- groups_data[sapply(groups_data, length) >= 2]
      
      if (length(groups_data) >= 2) {
        # Levene检验
        levene_result <- car::leveneTest(data[[var]], data[[strata]],
                                         center = "median")
        variance_homogeneity[[var]] <- list(
          test = "Levene",
          statistic = levene_result$`F(value)`[1],
          p_value = levene_result$`Pr(>F)`[1],
          homogeneous = levene_result$`Pr(>F)`[1] > 0.05
        )
      }
    }
  }
  
  # ============================================
  # 4. 使用tableone包生成基线表
  # ============================================
  cat("生成TableOne表...\n")
  
  # 创建TableOne对象
  tableone_obj <- CreateTableOne(
    vars = all_vars,
    strata = strata,
    data = data,
    factorVars = factor_vars,
    includeNA = FALSE,
    test = has_strata,
    smd = TRUE,
    addOverall = !has_strata
  )
  
  # ============================================
  # 5. 打印结果(指定非正态和精确方法)
  # ============================================
  print_tableone <- print(
    tableone_obj,
    nonnormal = nonnormal_vars,
    exact = exact_vars,
    smd = TRUE,
    formatOptions = list(big.mark = ","),
    showAllLevels = TRUE,
    printToggle = FALSE
  )
  
  # ============================================
  # 6. 组间比较统计检验(详细结果)
  # ============================================
  detailed_results <- calculate_detailed_stats(
    data = data,
    cont_vars = cont_vars,
    factor_vars = factor_vars,
    strata = strata,
    groups = groups,
    normality_results = normality_results,
    variance_homogeneity = variance_homogeneity,
    nonnormal_vars = nonnormal_vars
  )
  
  # ============================================
  # 7. 组间比较P值(格式化保留三位小数)
  # ============================================
  p_values_formatted <- format_p_values(detailed_results$p_values)
  
  # ============================================
  # 8. 输出结果汇总
  # ============================================
  result <- list(
    tableone = print_tableone,
    tableone_object = tableone_obj,
    normality = normality_results,
    variance = variance_homogeneity,
    p_values = p_values_formatted,
    detailed_stats = detailed_results,
    groups = groups,
    strata = strata,
    factor_vars = factor_vars,
    nonnormal_vars = nonnormal_vars
  )
  
  if (verbose) {
    cat("\n========== TableOne生成完成 ==========\n")
    cat(sprintf("分组数量: %d\n", groups))
    cat(sprintf("分组变量: %s\n", ifelse(has_strata, strata, "无")))
    cat(sprintf("变量总数: %d\n", length(all_vars)))
    cat(sprintf("  - 连续变量: %d\n", length(cont_vars)))
    cat(sprintf("  - 分类变量: %d\n", length(factor_vars)))
    cat("=======================================\n")
  }
  
  return(result)
}

# 计算详细的统计结果
calculate_detailed_stats <- function(data,
                                      cont_vars,
                                      factor_vars,
                                      strata,
                                      groups,
                                      normality_results,
                                      variance_homogeneity,
                                      nonnormal_vars) {
  
  results <- list()
  p_values <- data.frame(variable = character(), p_value = numeric(),
                        method = character(), stringsAsFactors = FALSE)
  
  # ============================================
  # 连续变量组间比较
  # ============================================
  for (var in cont_vars) {
    vals <- data[[var]]
    
    if (is.null(strata)) {
      # 无分组: 整体描述
      results[[var]] <- describe_continuous(vals)
      p_values <- rbind(p_values, data.frame(
        variable = var,
        p_value = NA,
        method = "无分组比较",
        stringsAsFactors = FALSE
      ))
    } else {
      # 有分组: 组间比较
      group_vals <- split(vals, data[[strata]])
      group_n <- length(group_vals)
      
      # 判断正态性
      is_normal <- isTRUE(normality_results[[var]]$normal)
      is_nonnormal <- var %in% nonnormal_vars
      
      # 判断方差齐性
      is_homogeneous <- TRUE
      if (!is.null(variance_homogeneity[[var]])) {
        is_homogeneous <- variance_homogeneity[[var]]$homogeneous
      }
      
      # 选择统计方法
      if (group_n == 2) {
        # 两组比较
        if (is_nonnormal || (!is_normal && !is_homogeneous)) {
          # 非参数Mann-Whitney U检验
          test_result <- wilcox.test(vals ~ data[[strata]])
          method <- "Mann-Whitney U检验"
        } else {
          # 参数t检验(独立样本)
          if (is_homogeneous) {
            test_result <- t.test(vals ~ data[[strata]], var.equal = TRUE)
            method <- "独立样本t检验"
          } else {
            test_result <- t.test(vals ~ data[[strata]], var.equal = FALSE)
            method <- "Welch t检验"
          }
        }
      } else {
        # 多组比较
        if (is_nonnormal || !is_normal) {
          # 非参数Kruskal-Wallis检验
          test_result <- kruskal.test(vals ~ data[[strata]])
          method <- "Kruskal-Wallis检验"
        } else {
          # 单因素方差分析
          test_result <- oneway.test(vals ~ data[[strata]])
          method <- "单因素ANOVA"
        }
      }
      
      results[[var]] <- list(
        description = describe_continuous(vals, data[[strata]]),
        test = method,
        statistic = test_result$statistic,
        p_value = test_result$p.value
      )
      
      p_values <- rbind(p_values, data.frame(
        variable = var,
        p_value = test_result$p.value,
        method = method,
        stringsAsFactors = FALSE
      ))
    }
  }
  
  # ============================================
  # 分类变量组间比较
  # ============================================
  for (var in factor_vars) {
    vals <- data[[var]]
    
    if (is.null(strata)) {
      # 无分组: 整体描述
      results[[var]] <- describe_categorical(vals)
      p_values <- rbind(p_values, data.frame(
        variable = var,
        p_value = NA,
        method = "无分组比较",
        stringsAsFactors = FALSE
      ))
    } else {
      # 有分组: 组间比较
      tab <- table(vals, data[[strata]])
      
      # 判断最小期望频数
      chi_result <- suppressWarnings(chisq.test(tab))
      min_expected <- min(chi_result$expected)
      
      if (min_expected < 5 || any(tab < 5)) {
        # Fisher精确检验
        test_result <- fisher.test(tab)
        method <- "Fisher精确检验"
      } else {
        # 卡方检验
        test_result <- chi_result
        method <- "卡方检验"
      }
      
      results[[var]] <- list(
        description = describe_categorical(vals, data[[strata]]),
        contingency_table = tab,
        test = method,
        p_value = test_result$p.value
      )
      
      p_values <- rbind(p_values, data.frame(
        variable = var,
        p_value = test_result$p.value,
        method = method,
        stringsAsFactors = FALSE
      ))
    }
  }
  
  # ============================================
  # 多重比较校正(当组数>2时)
  # ============================================
  if (groups > 2 && nrow(p_values) > 0) {
    # Benjamini-Hochberg FDR校正
    p_values$p_adjusted <- p.adjust(p_values$p_value, method = "BH")
  } else {
    p_values$p_adjusted <- p_values$p_value
  }
  
  return(list(
    results = results,
    p_values = p_values
  ))
}

# 描述连续变量
describe_continuous <- function(x, group = NULL) {
  x_clean <- x[!is.na(x)]
  
  result <- list(
    n = length(x_clean),
    mean = mean(x_clean),
    sd = sd(x_clean),
    median = median(x_clean),
    q25 = quantile(x_clean, 0.25),
    q75 = quantile(x_clean, 0.75),
    min = min(x_clean),
    max = max(x_clean)
  )
  
  if (!is.null(group)) {
    result$by_group <- lapply(split(x, group), describe_continuous)
  }
  
  return(result)
}

# 描述分类变量
describe_categorical <- function(x, group = NULL) {
  x_clean <- x[!is.na(x)]
  freq_table <- table(x_clean)
  prop_table <- prop.table(freq_table) * 100
  
  result <- list(
    levels = names(freq_table),
    counts = as.numeric(freq_table),
    proportions = as.numeric(prop_table)
  )
  
  if (!is.null(group)) {
    result$by_group <- lapply(split(x, group), describe_categorical)
  }
  
  return(result)
}

# 格式化P值
format_p_values <- function(p_df) {
  if (nrow(p_df) == 0) return(p_df)
  
  p_df$p_formatted <- sapply(p_df$p_value, function(p) {
    if (is.na(p)) {
      return("NA")
    } else if (p < 0.001) {
      return("<0.001")
    } else {
      return(sprintf("%.3f", round(p, 3)))
    }
  })
  
  p_df$p_adjusted_formatted <- sapply(p_df$p_adjusted, function(p) {
    if (is.na(p)) {
      return("NA")
    } else if (p < 0.001) {
      return("<0.001")
    } else {
      return(sprintf("%.3f", round(p, 3)))
    }
  })
  
  return(p_df)
}
