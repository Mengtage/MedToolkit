#!/usr/bin/env Rscript
# ============================================
# ROC曲线分析模块
# 医学统计分析自动化系统
#
# 基于: pROC包 (Robin et al., 2011)
# DOI: 10.1186/1471-2105-12-77
#
# 功能:
# 1. ROC曲线绘制
# 2. AUC计算与95%CI
# 3. 最佳截断值确定
# 4. 敏感性/特异性分析
# 5. 多指标ROC比较(DeLong检验)
# 6. 校准曲线
# ============================================

roc_analysis <- function(data,
                        predictor,
                        outcome,
                        control = NULL,
                        output_dir = "./output",
                        config = list(),
                        verbose = TRUE) {
  
  cat("开始ROC曲线分析...\n\n")
  
  # ============================================
  # 1. 数据准备
  # ============================================
  # 处理预测变量
  if (is.character(predictor)) {
    predictor_data <- data[[predictor]]
  } else {
    predictor_data <- predictor
  }
  
  # 处理结局变量(需要是二分类)
  if (is.character(outcome)) {
    outcome_data <- data[[outcome]]
  } else {
    outcome_data <- outcome
  }
  
  # 确保结局变量是二分类
  if (!is.numeric(outcome_data) && !is.factor(outcome_data)) {
    stop("结局变量必须是数值型或因子型")
  }
  
  # 转换为数值
  if (is.factor(outcome_data)) {
    outcome_numeric <- as.numeric(outcome_data) - 1
    levels_info <- levels(outcome_data)
  } else {
    unique_vals <- sort(unique(outcome_data))
    outcome_numeric <- as.numeric(outcome_data == unique_vals[2])
    levels_info <- c(paste0("非", unique_vals[2]), as.character(unique_vals[2]))
  }
  
  # 检查缺失值
  complete_idx <- complete.cases(predictor_data) & complete.cases(outcome_data)
  predictor_clean <- predictor_data[complete_idx]
  outcome_clean <- outcome_numeric[complete_idx]
  
  n_total <- length(outcome_clean)
  n_positive <- sum(outcome_clean)
  n_negative <- n_total - n_positive
  
  cat(sprintf("样本信息:\n"))
  cat(sprintf("  总样本: %d\n", n_total))
  cat(sprintf("  阳性: %d (%.1f%%)\n", n_positive, n_positive/n_total*100))
  cat(sprintf("  阴性: %d (%.1f%%)\n", n_negative, n_negative/n_total*100))
  
  # ============================================
  # 2. 构建ROC曲线
  # ============================================
  cat("\n构建ROC曲线...\n")
  
  roc_obj <- roc(outcome_clean, predictor_clean,
                 ci = TRUE,
                 boot.n = config$bootstrap_n %||% 2000,
                 percent = FALSE)
  
  # ============================================
  # 3. 计算AUC及95%CI
  # ============================================
  auc_value <- auc(roc_obj)
  ci_auc <- ci(roc_obj)
  
  cat(sprintf("\nAUC = %.4f (95%% CI: %.4f - %.4f)\n", 
              auc_value, ci_auc[1], ci_auc[3]))
  
  # ============================================
  # 4. 最佳截断值
  # ============================================
  # 使用Youden指数
  coords_youden <- coords(roc_obj, "best", ret = "all",
                          best.method = "youden")
  
  # 使用最大约登指数的截断值
  optimal_cutoff <- coords_youden$threshold[1]
  optimal_sensitivity <- coords_youden$sensitivity[1]
  optimal_specificity <- coords_youden$specificity[1]
  
  cat(sprintf("\n最佳截断值 (Youden指数):\n"))
  cat(sprintf("  截断值: %.4f\n", optimal_cutoff))
  cat(sprintf("  敏感性: %.2f%%\n", optimal_sensitivity * 100))
  cat(sprintf("  特异性: %.2f%%\n", optimal_specificity * 100))
  
  # ============================================
  # 5. 多指标ROC比较(如果有control组)
  # ============================================
  if (!is.null(control) && is.character(control)) {
    cat("\n多指标ROC比较...\n")
    control_data <- data[[control]]
    control_clean <- control_data[complete_idx]
    
    roc_control <- roc(outcome_clean, control_clean,
                       ci = TRUE, percent = FALSE)
    
    # DeLong检验
    roc_test <- roc.test(roc_obj, roc_control, method = "delong")
    
    cat(sprintf("\nDeLong检验结果:\n"))
    cat(sprintf("  差异: %.4f\n", roc_test$difference))
    cat(sprintf("  Z统计量: %.4f\n", roc_test$statistic))
    cat(sprintf("  P值: %.4f\n", roc_test$p.value))
  }
  
  # ============================================
  # 6. 绘制ROC曲线
  # ============================================
  cat("\n绘制ROC曲线...\n")
  
  plot_dir <- file.path(output_dir, "plots")
  if (!dir.exists(plot_dir)) {
    dir.create(plot_dir, recursive = TRUE)
  }
  
  # 基本ROC曲线
  p1 <- ggroc(roc_obj, alpha = 0.6, linewidth = 1.5,
              color = "#2171B5", size = 1.5) +
    geom_abline(intercept = 1, slope = 1, linetype = "dashed",
                color = "gray50", linewidth = 1) +
    annotate("text", x = 0.75, y = 0.25, 
             label = sprintf("AUC = %.3f (95%% CI: %.3f-%.3f)",
                             auc_value, ci_auc[1], ci_auc[3]),
             size = 5, fontface = "bold") +
    labs(title = paste("ROC Curve:", predictor, "for", outcome),
         x = "1 - Specificity", y = "Sensitivity") +
    theme_minimal() +
    theme(plot.title = element_text(hjust = 0.5, face = "bold"))
  
  ggsave(filename = file.path(plot_dir, paste0("roc_", predictor, ".png")),
         plot = p1, width = 8, height = 8, dpi = 300)
  
  # 敏感性-特异性曲线
  p2 <- ggplot(data.frame(
    threshold = coords(roc_obj, "threshold")$threshold,
    sensitivity = coords(roc_obj, "sensitivity")$sensitivity,
    specificity = coords(roc_obj, "specificity")$specificity
  ), aes(x = threshold)) +
    geom_line(aes(y = sensitivity, color = "Sensitivity"), linewidth = 1.2) +
    geom_line(aes(y = specificity, color = "Specificity"), linewidth = 1.2) +
    geom_vline(xintercept = optimal_cutoff, linetype = "dashed",
               color = "red", linewidth = 1) +
    labs(title = "Sensitivity and Specificity by Threshold",
         x = "Threshold", y = "Value",
         color = "Measure") +
    theme_minimal()
  
  ggsave(filename = file.path(plot_dir, paste0("roc_sens_spec_", predictor, ".png")),
         plot = p2, width = 10, height = 6, dpi = 300)
  
  # ============================================
  # 7. 校准曲线
  # ============================================
  cat("绘制校准曲线...\n")
  
  # 使用val.prob函数计算校准
  pred_probs <- predict(roc_obj$predictor, roc_obj$predictor)
  
  p3 <- calibration_plot(outcome_clean, predictor_clean, predictor, plot_dir)
  
  # ============================================
  # 8. 返回结果
  # ============================================
  results <- list(
    predictor = predictor,
    outcome = outcome,
    roc_object = roc_obj,
    auc = auc_value,
    ci_auc = ci_auc,
    optimal_cutoff = optimal_cutoff,
    optimal_sensitivity = optimal_sensitivity,
    optimal_specificity = optimal_specificity,
    sample_size = n_total,
    n_positive = n_positive,
    n_negative = n_negative,
    coords = coords_youden,
    comparison = if(!is.null(control)) roc_test else NULL
  )
  
  if (verbose) {
    cat("\n========== ROC分析完成 ==========\n")
    cat(sprintf("预测指标: %s\n", predictor))
    cat(sprintf("诊断标准: %s\n", outcome))
    cat(sprintf("AUC: %.4f (95%% CI: %.4f-%.4f)\n", auc_value, ci_auc[1], ci_auc[3]))
    cat(sprintf("最佳截断值: %.4f\n", optimal_cutoff))
    cat(sprintf("敏感性: %.2f%%, 特异性: %.2f%%\n",
                optimal_sensitivity*100, optimal_specificity*100))
    cat("================================\n")
  }
  
  return(results)
}

# ============================================
# 校准曲线绘制
# ============================================
calibration_plot <- function(outcome, predictor, var_name, output_dir) {
  
  # 分箱计算
  n_bins <- 10
  bins <- cut(predictor, breaks = n_bins, labels = FALSE)
  
  calibration_data <- data.frame(
    bin = bins,
    outcome = outcome,
    pred = predictor
  )
  
  # 计算每个箱的预测概率和实际阳性率
  cal_summary <- calibration_data %>%
    group_by(bin) %>%
    summarise(
      mean_pred = mean(pred, na.rm = TRUE),
      n = sum(!is.na(bin)),
      obs_rate = mean(outcome, na.rm = TRUE)
    ) %>%
    filter(n >= 5)
  
  # 校准曲线
  p <- ggplot(cal_summary, aes(x = mean_pred, y = obs_rate)) +
    geom_point(size = 4, color = "#2171B5") +
    geom_line(linewidth = 1, color = "#2171B5") +
    geom_abline(intercept = 0, slope = 1, linetype = "dashed",
               color = "gray50", linewidth = 1) +
    labs(title = paste("Calibration Plot:", var_name),
         x = "Predicted Probability",
         y = "Observed Probability") +
    xlim(0, 1) + ylim(0, 1) +
    theme_minimal()
  
  ggsave(filename = file.path(output_dir, paste0("calibration_", var_name, ".png")),
         plot = p, width = 8, height = 6, dpi = 300)
  
  return(p)
}

# ============================================
# 多指标ROC曲线比较
# ============================================
compare_multiple_roc <- function(data, predictors, outcome, output_dir) {
  
  results <- list()
  
  # 构建各指标的ROC曲线
  roc_list <- list()
  for (pred in predictors) {
    pred_data <- data[[pred]]
    outcome_data <- data[[outcome]]
    
    roc_list[[pred]] <- roc(outcome_data, pred_data, ci = TRUE)
  }
  
  # 绘制比较图
  roc_df <- data.frame(
    FPR = 1 - roc_list[[1]]$specificities,
    TPR = roc_list[[1]]$sensitivities,
    Predictor = names(roc_list)[1]
  )
  
  for (i in 2:length(roc_list)) {
    roc_df <- rbind(roc_df, data.frame(
      FPR = 1 - roc_list[[i]]$specificities,
      TPR = roc_list[[i]]$sensitivities,
      Predictor = names(roc_list)[i]
    ))
  }
  
  # 比较图
  p <- ggplot(roc_df, aes(x = FPR, y = TPR, color = Predictor)) +
    geom_line(linewidth = 1.2) +
    geom_abline(intercept = 0, slope = 1, linetype = "dashed",
               color = "gray50", linewidth = 1) +
    labs(title = "ROC Curve Comparison",
         x = "1 - Specificity", y = "Sensitivity") +
    theme_minimal() +
    scale_color_brewer(palette = "Set1")
  
  # 添加AUC标注
  auc_labels <- sapply(roc_list, function(r) sprintf("AUC = %.3f", auc(r)))
  
  ggsave(filename = file.path(output_dir, "roc_comparison.png"),
         plot = p, width = 10, height = 8, dpi = 300)
  
  # 两两比较(DeLong检验)
  comparison_results <- list()
  predictors_list <- names(roc_list)
  
  for (i in 1:(length(predictors_list) - 1)) {
    for (j in (i + 1):length(predictors_list)) {
      test_result <- roc.test(roc_list[[predictors_list[i]]],
                              roc_list[[predictors_list[j]]],
                              method = "delong")
      
      comparison_results[[paste(predictors_list[i], "vs", predictors_list[j])]] <- 
        data.frame(
          Predictor1 = predictors_list[i],
          Predictor2 = predictors_list[j],
          AUC1 = auc(roc_list[[predictors_list[i]]]),
          AUC2 = auc(roc_list[[predictors_list[j]]]),
          Z = test_result$statistic,
          P_value = test_result$p.value
        )
    }
  }
  
  return(list(
    roc_curves = roc_list,
    comparison = comparison_results
  ))
}

# ============================================
# 计算ROC曲线的各种指标
# ============================================
calculate_roc_metrics <- function(roc_obj, threshold = NULL) {
  
  # 获取坐标
  coords_df <- coords(roc_obj, "all", ret = "all")
  
  # 计算各种指标
  metrics <- list(
    auc = auc(roc_obj),
    ci_auc_95 = ci(roc_obj),
    sensitivity = coords_df$sensitivity,
    specificity = coords_df$specificity,
    ppv = coords_df$ppv,
    npv = coords_df$npv,
    threshold = coords_df$threshold
  )
  
  # 最佳截断值(Youden指数)
  youden_idx <- which.max(metrics$sensitivity + metrics$specificity - 1)
  optimal <- list(
    threshold = metrics$threshold[youden_idx],
    sensitivity = metrics$sensitivity[youden_idx],
    specificity = metrics$specificity[youden_idx],
    ppv = metrics$ppv[youden_idx],
    npv = metrics$npv[youden_idx],
    youden_index = metrics$sensitivity[youden_idx] + metrics$specificity[youden_idx] - 1
  )
  
  # 特定截断值的指标
  if (!is.null(threshold)) {
    coords_thresh <- coords(roc_obj, x = threshold, input = "threshold",
                           ret = c("sensitivity", "specificity", "ppv", "npv"))
    optimal$at_threshold <- coords_thresh
  }
  
  return(list(
    metrics = metrics,
    optimal = optimal
  ))
}
