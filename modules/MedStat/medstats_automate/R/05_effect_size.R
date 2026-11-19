#!/usr/bin/env Rscript
# ============================================
# 效应量计算模块
# 医学统计分析自动化系统
#
# 功能:
# 1. 连续变量效应量: Cohen's d, Hedges' g, Mean Difference
# 2. 二分类变量效应量: OR, RR, RD, NNT
# 3. 生存数据效应量: HR
# 4. 95%置信区间计算
# 5. 多重比较校正(Bonferroni, BH-FDR)
#
# 参考文献:
# - Cohen, J. (1988). Statistical Power Analysis for the Behavioral Sciences
# - Campbell Collaboration Effect Size Guidelines
# ============================================

calculate_effect_size <- function(data,
                                 vars = NULL,
                                 groups = 2,
                                 strata = NULL,
                                 outcome_var = NULL,
                                 exposure_var = NULL,
                                 time_var = NULL,
                                 status_var = NULL,
                                 config = list(),
                                 verbose = TRUE) {
  
  cat("开始计算效应量...\n\n")
  
  # ============================================
  # 1. 确定需要计算的变量
  # ============================================
  if (is.null(vars)) {
    # 默认计算所有数值变量的效应量
    vars <- names(data)[sapply(data, is.numeric)]
  }
  
  cat(sprintf("效应量计算变量: %d个\n", length(vars)))
  cat(sprintf("分组数量: %d\n\n", groups))
  
  # ============================================
  # 2. 计算效应量
  # ============================================
  effect_sizes <- list()
  
  for (var in vars) {
    if (is.null(strata)) {
      next
    }
    
    # 获取变量值和分组
    x <- data[[var]]
    group <- data[[strata]]
    
    # 判断变量类型
    is_binary <- length(unique(x[!is.na(x)])) == 2
    is_categorical <- is.factor(x) && nlevels(x) <= 2
    
    if (is_binary || is_categorical) {
      # 二分类变量 -> 计算OR, RR, RD
      effect_sizes[[var]] <- calculate_binary_effect_size(
        data = data,
        exposure = var,
        outcome = strata,
        groups = groups
      )
    } else {
      # 连续变量 -> 计算MD, Cohen's d, Hedges' g
      effect_sizes[[var]] <- calculate_continuous_effect_size(
        data = data,
        variable = var,
        group = strata,
        groups = groups
      )
    }
  }
  
  # ============================================
  # 3. 多重比较校正(当变量数>1时)
  # ============================================
  if (length(effect_sizes) > 1) {
    effect_sizes <- adjust_for_multiple_comparison(effect_sizes, config)
  }
  
  # ============================================
  # 4. 格式化结果
  # ============================================
  result_df <- format_effect_size_results(effect_sizes)
  
  if (verbose) {
    cat("\n========== 效应量计算结果 ==========\n")
    print(result_df)
    cat("====================================\n")
  }
  
  return(list(
    effect_sizes = effect_sizes,
    results_table = result_df,
    vars_analyzed = vars
  ))
}

# 计算连续变量的效应量
calculate_continuous_effect_size <- function(data, variable, group, groups) {
  
  # 获取分组数据
  group_levels <- levels(data[[group]])
  
  if (groups == 2) {
    # 两组比较
    group1 <- data[[variable]][data[[group]] == group_levels[1]]
    group2 <- data[[variable]][data[[group]] == group_levels[2]]
    
    group1_clean <- group1[!is.na(group1) & !is.na(group2)]
    group2_clean <- group2[!is.na(group1) & !is.na(group2)]
    
    n1 <- length(group1_clean)
    n2 <- length(group2_clean)
    
    mean1 <- mean(group1_clean)
    mean2 <- mean(group2_clean)
    sd1 <- sd(group1_clean)
    sd2 <- sd(group2_clean)
    
    # 均值差
    md <- mean1 - mean2
    
    # Cohen's d
    pooled_sd <- sqrt(((n1 - 1) * sd1^2 + (n2 - 1) * sd2^2) / (n1 + n2 - 2))
    cohens_d <- md / pooled_sd
    
    # Hedges' g (小样本校正)
    correction <- 1 - (3 / (4 * (n1 + n2) - 9))
    hedges_g <- cohens_d * correction
    
    # 95% CI for Cohen's d
    se_d <- sqrt((n1 + n2) / (n1 * n2) + (cohens_d^2) / (2 * (n1 + n2)))
    ci_lower_d <- cohens_d - 1.96 * se_d
    ci_upper_d <- cohens_d + 1.96 * se_d
    
    # 组别信息
    group_info <- paste0(group_levels[1], " vs ", group_levels[2])
    
    result <- list(
      variable = variable,
      type = "continuous",
      comparison = group_info,
      n1 = n1,
      n2 = n2,
      mean1 = mean1,
      mean2 = mean2,
      sd1 = sd1,
      sd2 = sd2,
      mean_diff = md,
      cohens_d = cohens_d,
      hedges_g = hedges_g,
      ci_95_lower = ci_lower_d,
      ci_95_upper = ci_upper_d,
      se = se_d
    )
  } else {
    # 多组比较 -> 计算ANOVA的eta-squared和omega-squared
    all_groups <- split(data[[variable]], data[[group]])
    all_groups <- all_groups[sapply(all_groups, length) >= 2]
    
    if (length(all_groups) >= 2) {
      # 单因素ANOVA
      formula <- as.formula(paste(variable, "~", group))
      anova_result <- oneway.test(formula, data = data)
      
      # 计算效应量
      k <- length(all_groups)
      n <- sum(sapply(all_groups, length))
      group_means <- sapply(all_groups, mean)
      grand_mean <- mean(unlist(all_groups))
      
      # SSB (组间平方和)
      ssb <- sum(sapply(all_groups, function(x) length(x) * (mean(x) - grand_mean)^2))
      
      # SST (总平方和)
      all_vals <- unlist(all_groups)
      sst <- sum((all_vals - grand_mean)^2)
      
      # SSW (组内平方和)
      ssw <- sst - ssb
      
      # eta-squared
      eta_squared <- ssb / sst
      
      # omega-squared (更无偏)
      omega_squared <- (ssb - (k - 1) * (ssw / (n - k))) / (sst + (k - 1) * (ssw / (n - k)) + (n - k))
      
      result <- list(
        variable = variable,
        type = "continuous_multigroup",
        comparison = paste(group_levels, collapse = " vs "),
        n_total = n,
        n_groups = k,
        eta_squared = eta_squared,
        omega_squared = omega_squared,
        f_statistic = anova_result$statistic,
        p_value = anova_result$p.value,
        ci_95_lower = NA,
        ci_95_upper = NA
      )
    } else {
      result <- NULL
    }
  }
  
  return(result)
}

# 计算二分类变量的效应量
calculate_binary_effect_size <- function(data, exposure, outcome, groups) {
  
  # 创建列联表
  if (groups == 2) {
    tab <- table(data[[exposure]], data[[outcome]])
    
    # 确保是2x2表
    if (nrow(tab) == 2 && ncol(tab) == 2) {
      # 提取四格表
      a <- tab[1, 1]  # 暴露阳性,结局阳性
      b <- tab[1, 2]  # 暴露阳性,结局阴性
      c <- tab[2, 1]  # 暴露阴性,结局阳性
      d <- tab[2, 2]  # 暴露阴性,结局阴性
      
      n1 <- a + b  # 总暴露人数
      n2 <- c + d  # 总非暴露人数
      
      # 事件发生率
      p1 <- a / n1  # 暴露组事件率
      p2 <- c / n2  # 非暴露组事件率
      
      # 比值比 (Odds Ratio)
      or <- (a * d) / (b * c)
      
      # 相对危险度 (Risk Ratio)
      rr <- p1 / p2
      
      # 风险差 (Risk Difference)
      rd <- p1 - p2
      
      # 需要治疗人数 (NNT)
      nnt <- ifelse(rd > 0, 1 / rd, -1 / rd)
      
      # 95% CI for OR (Woolf方法)
      log_or <- log(or)
      se_log_or <- sqrt(1/a + 1/b + 1/c + 1/d)
      ci_lower_or <- exp(log_or - 1.96 * se_log_or)
      ci_upper_or <- exp(log_or + 1.96 * se_log_or)
      
      # 95% CI for RR
      log_rr <- log(rr)
      se_log_rr <- sqrt((1 - p1) / (a) + (1 - p2) / (c))
      ci_lower_rr <- exp(log_rr - 1.96 * se_log_rr)
      ci_upper_rr <- exp(log_rr + 1.96 * se_log_rr)
      
      # 95% CI for RD
      se_rd <- sqrt((p1 * (1 - p1) / n1) + (p2 * (1 - p2) / n2))
      ci_lower_rd <- rd - 1.96 * se_rd
      ci_upper_rd <- rd + 1.96 * se_rd
      
      result <- list(
        variable = exposure,
        type = "binary",
        contingency_table = tab,
        n_exposed = n1,
        n_unexposed = n2,
        event_exposed = a,
        event_unexposed = c,
        rate_exposed = p1,
        rate_unexposed = p2,
        odds_ratio = or,
        risk_ratio = rr,
        risk_difference = rd,
        nnt = nnt,
        or_ci_lower = ci_lower_or,
        or_ci_upper = ci_upper_or,
        rr_ci_lower = ci_lower_rr,
        rr_ci_upper = ci_upper_rr,
        rd_ci_lower = ci_lower_rd,
        rd_ci_upper = ci_upper_rd
      )
    } else {
      result <- NULL
    }
  } else {
    result <- NULL
  }
  
  return(result)
}

# 计算生存数据的风险比(HR)
calculate_survival_effect_size <- function(data, time_var, status_var, group_var) {
  
  # 使用Cox比例风险模型
  formula <- as.formula(paste("Surv(", time_var, ",", status_var, ") ~", group_var))
  cox_model <- coxph(formula, data = data)
  
  # 提取HR和CI
  summary_cox <- summary(cox_model)
  
  result <- list(
    type = "survival",
    hr = summary_cox$coefficients[, 2],
    ci_95_lower = summary_cox$conf.int[, 3],
    ci_95_upper = summary_cox$conf.int[, 4],
    p_value = summary_cox$coefficients[, 5],
    concordance = summary_cox$concordance[1]
  )
  
  return(result)
}

# 多重比较校正
adjust_for_multiple_comparison <- function(effect_sizes, config) {
  
  n_tests <- length(effect_sizes)
  method <- config$correction_method %||% "BH"
  
  # 提取原始p值
  p_values <- sapply(effect_sizes, function(x) {
    if (is.null(x$p_value)) {
      return(NA)
    }
    return(x$p_value)
  })
  
  # Bonferroni校正
  p_bonferroni <- p.adjust(p_values, method = "bonferroni")
  
  # Benjamini-Hochberg FDR校正
  p_bh <- p.adjust(p_values, method = "BH")
  
  # 更新结果
  for (i in seq_along(effect_sizes)) {
    effect_sizes[[i]]$p_adjusted_bonferroni <- p_bonferroni[i]
    effect_sizes[[i]]$p_adjusted_bh <- p_bh[i]
  }
  
  return(effect_sizes)
}

# 格式化效应量结果
format_effect_size_results <- function(effect_sizes) {
  
  results <- lapply(effect_sizes, function(x) {
    if (is.null(x)) return(NULL)
    
    if (x$type == "continuous") {
      data.frame(
        Variable = x$variable,
        Type = "连续变量",
        Comparison = x$comparison,
        Mean_Group1 = sprintf("%.2f ± %.2f", x$mean1, x$sd1),
        Mean_Group2 = sprintf("%.2f ± %.2f", x$mean2, x$sd2),
        Mean_Diff = sprintf("%.3f", x$mean_diff),
        Cohens_d = sprintf("%.3f", x$cohens_d),
        Hedges_g = sprintf("%.3f", x$hedges_g),
        CI_95 = sprintf("(%.3f, %.3f)", x$ci_95_lower, x$ci_95_upper),
        stringsAsFactors = FALSE
      )
    } else if (x$type == "binary") {
      data.frame(
        Variable = x$variable,
        Type = "二分类变量",
        Comparison = "暴露 vs 非暴露",
        Event_Rate_1 = sprintf("%.1f%%", x$rate_exposed * 100),
        Event_Rate_2 = sprintf("%.1f%%", x$rate_unexposed * 100),
        OR = sprintf("%.2f", x$odds_ratio),
        OR_CI_95 = sprintf("(%.2f, %.2f)", x$or_ci_lower, x$or_ci_upper),
        RR = sprintf("%.2f", x$risk_ratio),
        RR_CI_95 = sprintf("(%.2f, %.2f)", x$rr_ci_lower, x$rr_ci_upper),
        stringsAsFactors = FALSE
      )
    } else if (x$type == "continuous_multigroup") {
      data.frame(
        Variable = x$variable,
        Type = "连续变量(多组)",
        Comparison = x$comparison,
        Eta_squared = sprintf("%.3f", x$eta_squared),
        Omega_squared = sprintf("%.3f", x$omega_squared),
        F_statistic = sprintf("%.2f", x$f_statistic),
        P_value = sprintf("%.3f", x$p_value),
        stringsAsFactors = FALSE
      )
    }
  })
  
  results <- results[!sapply(results, is.null)]
  
  if (length(results) > 0) {
    return(do.call(rbind, results))
  } else {
    return(data.frame())
  }
}
