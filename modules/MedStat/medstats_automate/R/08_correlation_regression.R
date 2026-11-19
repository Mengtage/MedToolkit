#!/usr/bin/env Rscript
# ============================================
# 相关分析与回归分析模块
# 医学统计分析自动化系统
#
# 功能:
# 1. Pearson相关分析(正态数据)
# 2. Spearman相关分析(非正态/等级数据)
# 3. 线性回归分析
# 4. Logistic回归分析
# 5. Cox回归分析(生存数据)
# 6. 多重共线性诊断
# ============================================

correlation_regression <- function(data,
                                 vars = NULL,
                                 method = "auto",
                                 config = list(),
                                 verbose = TRUE) {
  
  cat("开始相关与回归分析...\n\n")
  
  results <- list()
  
  # ============================================
  # 1. 确定分析变量
  # ============================================
  if (is.null(vars)) {
    vars <- names(data)[sapply(data, is.numeric)]
  }
  
  cat(sprintf("分析变量数: %d\n", length(vars)))
  
  # ============================================
  # 2. 相关分析
  # ============================================
  cat("\n[分析 1/3] 相关分析...\n")
  correlation_results <- correlation_analysis(data, vars, method, config)
  results$correlation <- correlation_results
  
  # ============================================
  # 3. 线性回归分析
  # ============================================
  cat("[分析 2/3] 线性回归分析...\n")
  linear_results <- linear_regression_analysis(data, vars, config)
  results$linear_regression <- linear_results
  
  # ============================================
  # 4. Logistic回归分析
  # ============================================
  cat("[分析 3/3] Logistic回归分析...\n")
  logistic_results <- logistic_regression_analysis(data, config)
  results$logistic_regression <- logistic_results
  
  if (verbose) {
    cat("\n========== 分析完成 ==========\n")
    cat(sprintf("相关分析: %d个变量对\n", nrow(correlation_results$pairs)))
    cat(sprintf("线性回归: %d个模型\n", length(linear_results$models)))
    cat(sprintf("Logistic回归: %d个模型\n", length(logistic_results$models)))
    cat("==============================\n")
  }
  
  return(results)
}

# ============================================
# 相关分析
# ============================================
correlation_analysis <- function(data, vars, method = "auto", config = list()) {
  
  results <- list()
  
  # 选择数值变量
  numeric_data <- data[, vars[vars %in% names(data)][sapply(data[, vars[vars %in% names(data)], drop = FALSE], is.numeric)], drop = FALSE]
  
  if (ncol(numeric_data) < 2) {
    cat("  警告: 数值变量不足2个\n")
    return(list(pairs = data.frame(), matrix = matrix()))
  }
  
  # 自动选择相关方法
  if (method == "auto") {
    method <- "pearson"
  }
  
  # 计算相关矩阵
  if (method == "pearson") {
    cor_matrix <- cor(numeric_data, use = "pairwise.complete.obs", method = "pearson")
  } else {
    cor_matrix <- cor(numeric_data, use = "pairwise.complete.obs", method = "spearman")
  }
  
  # 计算p值矩阵
  n_vars <- ncol(numeric_data)
  p_matrix <- matrix(NA, n_vars, n_vars)
  
  for (i in 1:n_vars) {
    for (j in 1:n_vars) {
      if (i != j) {
        test_result <- cor.test(numeric_data[[i]], numeric_data[[j]], 
                               method = method)
        p_matrix[i, j] <- test_result$p.value
      }
    }
  }
  
  dimnames(p_matrix) <- dimnames(cor_matrix)
  
  # 转换为长格式
  pairs <- list()
  idx <- 1
  for (i in 1:(n_vars - 1)) {
    for (j in (i + 1):n_vars) {
      pairs[[idx]] <- data.frame(
        Var1 = colnames(cor_matrix)[i],
        Var2 = colnames(cor_matrix)[j],
        Correlation = cor_matrix[i, j],
        P_value = p_matrix[i, j],
        Method = method,
        stringsAsFactors = FALSE
      )
      idx <- idx + 1
    }
  }
  
  pairs_df <- do.call(rbind, pairs)
  
  # 多重比较校正
  if (nrow(pairs_df) > 1) {
    pairs_df$P_adjusted <- p.adjust(pairs_df$P_value, method = "BH")
  } else {
    pairs_df$P_adjusted <- pairs_df$P_value
  }
  
  # 添加显著性标记
  pairs_df$Significance <- cut(pairs_df$P_adjusted,
                             breaks = c(-Inf, 0.001, 0.01, 0.05, Inf),
                             labels = c("***", "**", "*", "ns"))
  
  # 排序
  pairs_df <- pairs_df[order(abs(pairs_df$Correlation), decreasing = TRUE), ]
  
  return(list(
    pairs = pairs_df,
    matrix = cor_matrix,
    p_matrix = p_matrix,
    method = method
  ))
}

# ============================================
# 线性回归分析
# ============================================
linear_regression_analysis <- function(data, vars, config = list()) {
  
  results <- list()
  
  # 确定因变量(默认第一个变量)
  if (is.null(config$dependent_var)) {
    dep_var <- vars[1]
    indep_vars <- vars[-1]
  } else {
    dep_var <- config$dependent_var
    indep_vars <- setdiff(vars, dep_var)
  }
  
  if (length(indep_vars) == 0) {
    cat("  警告: 自变量不足\n")
    return(list(models = list(), coefficients = data.frame()))
  }
  
  # 单变量线性回归
  univariate_models <- list()
  univariate_coefs <- list()
  
  for (var in indep_vars) {
    formula <- as.formula(paste(dep_var, "~", var))
    model <- lm(formula, data = data)
    summary_model <- summary(model)
    
    univariate_models[[var]] <- model
    
    univariate_coefs[[var]] <- data.frame(
      Predictor = var,
      Dependent = dep_var,
      Coefficient = coef(model)[2],
      Std_Error = summary_model$coefficients[2, 2],
      t_value = summary_model$coefficients[2, 3],
      P_value = summary_model$coefficients[2, 4],
      R_squared = summary_model$r.squared,
      stringsAsFactors = FALSE
    )
  }
  
  results$univariate_models <- univariate_models
  results$univariate_coefficients <- do.call(rbind, univariate_coefs)
  
  # 多变量线性回归
  if (length(indep_vars) > 1) {
    formula <- as.formula(paste(dep_var, "~", paste(indep_vars, collapse = "+")))
    multivariate_model <- lm(formula, data = data)
    summary_mv <- summary(multivariate_model)
    
    results$multivariate_model <- multivariate_model
    
    # 系数表
    coef_df <- data.frame(
      Predictor = rownames(summary_mv$coefficients),
      Coefficient = summary_mv$coefficients[, 1],
      Std_Error = summary_mv$coefficients[, 2],
      t_value = summary_mv$coefficients[, 3],
      P_value = summary_mv$coefficients[, 4]
    )
    rownames(coef_df) <- NULL
    
    # 模型拟合度
    model_fit <- data.frame(
      N = nrow(data),
      R_squared = summary_mv$r.squared,
      Adj_R_squared = summary_mv$adj.r.squared,
      F_statistic = summary_mv$fstatistic[1],
      P_value = pf(summary_mv$fstatistic[1], 
                   summary_mv$fstatistic[2], 
                   summary_mv$fstatistic[3], 
                   lower.tail = FALSE)
    )
    
    results$multivariate_coefficients <- coef_df
    results$model_fit <- model_fit
    
    # 多重共线性诊断
    vif_values <- car::vif(multivariate_model)
    results$vif <- data.frame(
      Variable = names(vif_values),
      VIF = as.numeric(vif_values),
      stringsAsFactors = FALSE
    )
  }
  
  results$models <- c(univariate_models, 
                      list(Multivariate = results$multivariate_model))
  
  return(results)
}

# ============================================
# Logistic回归分析
# ============================================
logistic_regression_analysis <- function(data, config = list()) {
  
  results <- list()
  
  # 确定因变量
  outcome_var <- config$outcome_var
  if (is.null(outcome_var)) {
    # 自动寻找二分类变量作为因变量
    binary_vars <- names(data)[sapply(data, function(x) {
      if (is.factor(x)) return(nlevels(x) == 2)
      if (is.numeric(x)) return(length(unique(x)) == 2)
      return(FALSE)
    })]
    
    if (length(binary_vars) > 0) {
      outcome_var <- binary_vars[1]
    } else {
      cat("  警告: 未找到二分类因变量\n")
      return(list(models = list(), coefficients = data.frame()))
    }
  }
  
  # 确定自变量
  indep_vars <- setdiff(names(data), outcome_var)
  indep_vars <- indep_vars[sapply(data[, indep_vars, drop = FALSE], is.numeric)]
  
  if (length(indep_vars) == 0) {
    cat("  警告: 自变量不足\n")
    return(list(models = list(), coefficients = data.frame()))
  }
  
  # 单变量Logistic回归
  univariate_models <- list()
  univariate_coefs <- list()
  
  for (var in indep_vars) {
    formula <- as.formula(paste(outcome_var, "~", var))
    model <- glm(formula, data = data, family = binomial)
    summary_model <- summary(model)
    
    univariate_models[[var]] <- model
    
    # 计算OR和CI
    coef_val <- coef(model)[2]
    se_val <- summary_model$coefficients[2, 2]
    or_val <- exp(coef_val)
    ci_lower <- exp(coef_val - 1.96 * se_val)
    ci_upper <- exp(coef_val + 1.96 * se_val)
    
    univariate_coefs[[var]] <- data.frame(
      Predictor = var,
      Dependent = outcome_var,
      Coefficient = coef_val,
      Std_Error = se_val,
      Z_value = summary_model$coefficients[2, 3],
      P_value = summary_model$coefficients[2, 4],
      OR = or_val,
      OR_CI_lower = ci_lower,
      OR_CI_upper = ci_upper,
      stringsAsFactors = FALSE
    )
  }
  
  results$univariate_models <- univariate_models
  results$univariate_coefficients <- do.call(rbind, univariate_coefs)
  
  # 多变量Logistic回归
  if (length(indep_vars) > 1) {
    formula <- as.formula(paste(outcome_var, "~", paste(indep_vars, collapse = "+")))
    multivariate_model <- glm(formula, data = data, family = binomial)
    summary_mv <- summary(multivariate_model)
    
    results$multivariate_model <- multivariate_model
    
    # 系数表
    n_coefs <- length(coef(multivariate_model))
    coef_df <- data.frame(
      Predictor = rownames(summary_mv$coefficients),
      Coefficient = summary_mv$coefficients[, 1],
      Std_Error = summary_mv$coefficients[, 2],
      Z_value = summary_mv$coefficients[, 3],
      P_value = summary_mv$coefficients[, 4]
    )
    
    # 添加OR和CI
    if (nrow(coef_df) > 1) {
      coef_df$OR <- exp(coef_df$Coefficient)
      coef_df$OR_CI_lower <- exp(coef_df$Coefficient - 1.96 * coef_df$Std_Error)
      coef_df$OR_CI_upper <- exp(coef_df$Coefficient + 1.96 * coef_df$Std_Error)
    }
    
    rownames(coef_df) <- NULL
    results$multivariate_coefficients <- coef_df
    
    # 模型评价
    results$model_evaluation <- data.frame(
      N = nrow(data),
      Null_Deviance = multivariate_model$null.deviance,
      Deviance = multivariate_model$deviance,
      Pseudo_R2 = 1 - (multivariate_model$deviance / multivariate_model$null.deviance),
      AIC = AIC(multivariate_model),
      BIC = BIC(multivariate_model)
    )
  }
  
  results$models <- c(univariate_models, 
                      list(Multivariate = results$multivariate_model))
  
  return(results)
}

# ============================================
# Cox回归分析
# ============================================
cox_regression_analysis <- function(data, time_var, status_var, vars, config = list()) {
  
  results <- list()
  
  # 单变量Cox回归
  univariate_models <- list()
  univariate_coefs <- list()
  
  for (var in vars) {
    formula <- as.formula(paste("Surv(", time_var, ",", status_var, ") ~", var))
    model <- coxph(formula, data = data)
    summary_model <- summary(model)
    
    univariate_models[[var]] <- model
    
    univariate_coefs[[var]] <- data.frame(
      Predictor = var,
      HR = summary_model$coefficients[1],
      HR_CI_lower = summary_model$conf.int[1, 3],
      HR_CI_upper = summary_model$conf.int[1, 4],
      P_value = summary_model$coefficients[5],
      stringsAsFactors = FALSE
    )
  }
  
  results$univariate_models <- univariate_models
  results$univariate_coefficients <- do.call(rbind, univariate_coefs)
  
  return(results)
}
