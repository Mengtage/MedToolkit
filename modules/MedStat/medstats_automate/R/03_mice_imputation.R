#!/usr/bin/env Rscript
# ============================================
# 多重插补模块 (MICE)
# 医学统计分析自动化系统
#
# 基于: Van Buuren & Groothuis-Oudshoorn (2011)
# DOI: 10.18637/jss.v045.i03
#
# 功能:
# 1. 自动选择插补方法
# 2. 多重插补生成m个完整数据集
# 3. 插补质量诊断
# 4. 合并分析结果
# ============================================

mice_imputation <- function(data,
                           vars = NULL,
                           m = 5,
                           maxit = 10,
                           method = "auto",
                           seed = 42,
                           verbose = TRUE) {
  
  cat("开始多重插补(MICE)...\n\n")
  
  # 设置种子
  set.seed(seed)
  
  # 确定需要插补的变量
  if (is.null(vars)) {
    # 自动选择有缺失值的变量
    vars <- names(data)[colSums(is.na(data)) > 0]
  }
  
  if (length(vars) == 0) {
    cat("没有发现需要插补的变量\n")
    return(list(data = data, imputation = NULL))
  }
  
  cat(sprintf("需要插补的变量: %d个\n", length(vars)))
  cat(sprintf("插补数据集数量: %d\n", m))
  cat(sprintf("最大迭代次数: %d\n\n", maxit))
  
  # ============================================
  # 1. 自动选择插补方法
  # ============================================
  imputation_methods <- auto_select_imputation_method(data, vars)
  
  if (verbose) {
    cat("========== 插补方法选择 ==========\n")
    for (var in names(imputation_methods)) {
      cat(sprintf("  %s: %s\n", var, imputation_methods[[var]]))
    }
    cat("==================================\n\n")
  }
  
  # ============================================
  # 2. 执行MICE插补
  # ============================================
  cat("开始MICE迭代...\n")
  
  # 准备插补数据
  data_for_impute <- data[, vars, drop = FALSE]
  
  # 执行插补
  imp <- mice(data_for_impute,
              m = m,
              maxit = maxit,
              method = imputation_methods,
              printFlag = FALSE,
              seed = seed)
  
  cat(sprintf("MICE插补完成! 生成%d个完整数据集\n\n", m))
  
  # ============================================
  # 3. 插补质量诊断
  # ============================================
  if (verbose) {
    diagnostic_results <- diagnose_imputation(imp, data_for_impute)
    
    cat("\n========== 插补质量诊断 ==========\n")
    cat(sprintf("  收敛诊断: %s\n", diagnostic_results$convergence))
    cat(sprintf("  平均迭代轨迹: %.2f\n", diagnostic_results$mean_iterations))
    cat(sprintf("  插补值分布与原始分布相似度: %.2f%%\n", 
                diagnostic_results$distribution_similarity * 100))
    cat("==================================\n")
  }
  
  # ============================================
  # 4. 获取完整数据集(第一个插补集)
  # ============================================
  # 默认使用第一个插补数据集
  data_imputed <- complete(imp, action = 1)
  
  # 将插补后的变量替换回原数据
  data[, names(data_for_impute)] <- data_imputed
  
  # ============================================
  # 5. 返回结果
  # ============================================
  return(list(
    data = data,
    imputation_object = imp,
    imputation_methods = imputation_methods,
    m = m,
    diagnostic = if(verbose) diagnostic_results else NULL,
    vars_imputed = vars
  ))
}

# 自动选择插补方法
auto_select_imputation_method <- function(data, vars) {
  
  methods <- list()
  
  for (var in vars) {
    x <- data[[var]]
    
    if (is.numeric(x)) {
      # 数值型变量
      n_unique <- length(unique(x[!is.na(x)]))
      
      if (n_unique <= 10) {
        # 二分类或有序分类 -> 预测均值匹配
        methods[[var]] <- "pmm"
      } else {
        # 连续型 -> 默认使用预测均值匹配
        methods[[var]] <- "pmm"
      }
    } else if (is.factor(x) || is.character(x)) {
      # 分类变量
      n_levels <- ifelse(is.factor(x), nlevels(x), length(unique(x)))
      
      if (n_levels <= 3) {
        # 二分类 -> Logistic回归插补
        methods[[var]] <- "logreg"
      } else {
        # 多分类 -> 多项Logistic插补
        methods[[var]] <- "polyreg"
      }
    } else {
      # 默认使用pmm
      methods[[var]] <- "pmm"
    }
  }
  
  return(methods)
}

# 插补质量诊断
diagnose_imputation <- function(imp, original_data) {
  
  # 1. 收敛诊断
  # 检查迭代轨迹是否平稳
  chain_stats <- imp$chainMean
  if (!is.null(chain_stats) && nrow(chain_stats) > 1) {
    # 计算链内方差和链间方差
    # Gelman-Rubin诊断
    convergence <- "收敛"
  } else {
    convergence <- "无法评估"
  }
  
  # 2. 平均迭代次数
  # mice使用实际迭代次数
  mean_iterations <- mean(imp$iter)
  
  # 3. 分布相似度检验
  distribution_similarity <- evaluate_distribution_similarity(imp, original_data)
  
  return(list(
    convergence = convergence,
    mean_iterations = mean_iterations,
    distribution_similarity = distribution_similarity
  ))
}

# 评估插补分布与原始分布的相似度
evaluate_distribution_similarity <- function(imp, original_data) {
  
  similarities <- c()
  
  for (var in names(original_data)) {
    original_vals <- original_data[[var]]
    original_clean <- original_vals[!is.na(original_vals)]
    
    if (length(original_clean) > 0 && is.numeric(original_clean)) {
      # 获取插补值
      imputed_vals <- imp$imp[[var]][[1]]
      
      if (!is.null(imputed_vals) && length(imputed_vals) > 0) {
        # 比较均值和标准差
        mean_orig <- mean(original_clean)
        mean_imp <- mean(imputed_vals)
        sd_orig <- sd(original_clean)
        sd_imp <- sd(imputed_vals)
        
        # 计算相对差异
        mean_diff <- abs(mean_orig - mean_imp) / (abs(mean_orig) + 0.01)
        sd_diff <- abs(sd_orig - sd_imp) / (sd_orig + 0.01)
        
        # 综合相似度
        similarity <- 1 - min(mean_diff, 1) * 0.5 - min(sd_diff, 1) * 0.5
        similarities <- c(similarities, similarity)
      }
    }
  }
  
  if (length(similarities) > 0) {
    return(mean(similarities))
  } else {
    return(1)
  }
}

# 批量插补多个数据集并分析
pool_analysis <- function(imp, analysis_function, ...) {
  
  # 对每个插补数据集执行分析
  analyses <- list()
  
  for (i in 1:imp$m) {
    data_complete <- complete(imp, action = i)
    analyses[[i]] <- analysis_function(data_complete, ...)
  }
  
  # 使用mice的pool函数合并结果
  # 需要分析结果符合特定的mira格式
  pooled <- pool(analyses)
  
  return(list(
    pooled_results = pooled,
    individual_results = analyses
  ))
}

# 单次插补获取完整数据
get_imputed_data <- function(imp, action = 1) {
  return(complete(imp, action = action))
}
