#!/usr/bin/env Rscript
# ============================================
# 可视化报告模块
# 医学统计分析自动化系统
#
# 图表类型:
# 1. 箱线图 (Boxplot)
# 2. 森林图 (Forest Plot)
# 3. 直方图 (Histogram)
# 4. Q-Q图 (Q-Q Plot)
# 5. 散点图 (Scatter Plot)
# 6. 相关矩阵热图 (Correlation Heatmap)
#
# 引用: ggplot2 (Wickham, 2016)
# ============================================

visualization_report <- function(data,
                               output_dir = "./output",
                               config = list(),
                               vars = NULL,
                               group_var = NULL,
                               effect_vars = NULL,
                               verbose = TRUE) {
  
  cat("开始生成可视化报告...\n\n")
  
  # 创建可视化目录
  plot_dir <- file.path(output_dir, "plots")
  if (!dir.exists(plot_dir)) {
    dir.create(plot_dir, recursive = TRUE)
  }
  
  # 设置ggplot2主题
  theme_set(theme_bw() + 
            theme(text = element_text(family = "sans", size = 11),
                  plot.title = element_text(hjust = 0.5, face = "bold")))
  
  # ============================================
  # 1. 箱线图
  # ============================================
  if (!is.null(group_var) && !is.null(vars)) {
    cat("[可视化 1/6] 箱线图...\n")
    generate_boxplots(data, vars, group_var, plot_dir)
  }
  
  # ============================================
  # 2. 森林图
  # ============================================
  if (!is.null(effect_vars)) {
    cat("[可视化 2/6] 森林图...\n")
    generate_forest_plots(effect_vars, plot_dir, config)
  }
  
  # ============================================
  # 3. 分布图
  # ============================================
  if (!is.null(vars)) {
    cat("[可视化 3/6] 分布图...\n")
    generate_distribution_plots(data, vars, plot_dir)
  }
  
  # ============================================
  # 4. Q-Q图
  # ============================================
  numeric_vars <- names(data)[sapply(data, is.numeric)]
  if (length(numeric_vars) > 0) {
    cat("[可视化 4/6] Q-Q图...\n")
    generate_qq_plots(data, numeric_vars, plot_dir)
  }
  
  # ============================================
  # 5. 相关矩阵热图
  # ============================================
  cat("[可视化 5/6] 相关矩阵热图...\n")
  generate_correlation_heatmap(data, plot_dir, config)
  
  # ============================================
  # 6. 综合面板图
  # ============================================
  cat("[可视化 6/6] 综合面板图...\n")
  generate_summary_panel(data, vars, group_var, plot_dir)
  
  if (verbose) {
    cat("\n========== 可视化完成 ==========\n")
    cat(sprintf("图片保存目录: %s\n", plot_dir))
    cat("================================\n")
  }
  
  return(invisible(list(plot_dir = plot_dir)))
}

# ============================================
# 箱线图生成函数
# ============================================
generate_boxplots <- function(data, vars, group_var, output_dir) {
  
  for (var in vars) {
    if (!is.numeric(data[[var]])) next
    
    p <- ggplot(data, aes_string(x = group_var, y = var, fill = group_var)) +
      geom_boxplot(alpha = 0.7, outlier.shape = 21) +
      geom_jitter(width = 0.2, alpha = 0.4, size = 1) +
      stat_summary(fun = "mean", geom = "point", shape = 23, 
                   size = 3, fill = "white") +
      labs(title = paste("Boxplot of", var, "by", group_var),
           y = var, x = group_var, fill = group_var) +
      theme_minimal() +
      scale_fill_brewer(palette = "Set2")
    
    ggsave(filename = file.path(output_dir, paste0("boxplot_", var, ".png")),
           plot = p, width = 8, height = 6, dpi = 300)
  }
}

# ============================================
# 森林图生成函数
# ============================================
generate_forest_plots <- function(effect_sizes, output_dir, config) {
  
  if (length(effect_sizes) == 0) return()
  
  # 准备数据
  plot_data <- do.call(rbind, lapply(effect_sizes, function(x) {
    if (is.null(x$cohens_d)) return(NULL)
    
    data.frame(
      variable = x$variable,
      estimate = x$cohens_d,
      lower = x$ci_95_lower,
      upper = x$ci_95_upper,
      stringsAsFactors = FALSE
    )
  }))
  
  if (is.null(plot_data) || nrow(plot_data) == 0) return()
  
  # 森林图
  p <- ggplot(plot_data, aes(x = estimate, y = reorder(variable, estimate))) +
    geom_vline(xintercept = 0, linetype = "dashed", color = "gray50") +
    geom_point(size = 3, color = "#2171B5") +
    geom_errorbarh(aes(xmin = lower, xmax = upper), height = 0.3) +
    labs(title = "Forest Plot of Effect Sizes (Cohen's d)",
         x = "Cohen's d (95% CI)", y = "") +
    xlim(min(plot_data$lower) - 0.5, max(plot_data$upper) + 0.5) +
    theme_minimal()
  
  ggsave(filename = file.path(output_dir, "forest_plot_effects.png"),
         plot = p, width = 10, height = max(6, nrow(plot_data) * 0.5 + 2), dpi = 300)
  
  # OR森林图(如果适用)
  or_data <- do.call(rbind, lapply(effect_sizes, function(x) {
    if (is.null(x$odds_ratio)) return(NULL)
    
    data.frame(
      variable = x$variable,
      estimate = log(x$odds_ratio),
      lower = log(x$or_ci_lower),
      upper = log(x$or_ci_upper),
      stringsAsFactors = FALSE
    )
  }))
  
  if (!is.null(or_data) && nrow(or_data) > 0) {
    p_or <- ggplot(or_data, aes(x = estimate, y = reorder(variable, estimate))) +
      geom_vline(xintercept = 0, linetype = "dashed", color = "gray50") +
      geom_point(size = 3, color = "#CB181D") +
      geom_errorbarh(aes(xmin = lower, xmax = upper), height = 0.3) +
      labs(title = "Forest Plot of Odds Ratios (log scale)",
           x = "Log Odds Ratio (95% CI)", y = "") +
      theme_minimal()
    
    ggsave(filename = file.path(output_dir, "forest_plot_or.png"),
           plot = p_or, width = 10, height = max(6, nrow(or_data) * 0.5 + 2), dpi = 300)
  }
}

# ============================================
# 分布图生成函数
# ============================================
generate_distribution_plots <- function(data, vars, output_dir) {
  
  for (var in vars) {
    if (!is.numeric(data[[var]])) next
    
    # 直方图+密度曲线
    p1 <- ggplot(data, aes_string(x = var)) +
      geom_histogram(aes(y = after_stat(density)), bins = 30, 
                     fill = "#4292C6", alpha = 0.7) +
      geom_density(color = "#CB181D", linewidth = 1) +
      labs(title = paste("Distribution of", var),
           x = var, y = "Density") +
      theme_minimal()
    
    ggsave(filename = file.path(output_dir, paste0("histogram_", var, ".png")),
           plot = p1, width = 8, height = 6, dpi = 300)
  }
}

# ============================================
# Q-Q图生成函数
# ============================================
generate_qq_plots <- function(data, vars, output_dir, n_plots = 6) {
  
  vars_to_plot <- head(vars, n_plots)
  
  plots <- lapply(vars_to_plot, function(var) {
    ggplot(data, aes_string(sample = var)) +
      stat_qq() +
      stat_qq_line(color = "#CB181D") +
      labs(title = paste("Q-Q Plot:", var)) +
      theme_minimal()
  })
  
  # 合并多图
  combined <- grid.arrange(grobs = plots, ncol = 2,
                           top = "Normal Q-Q Plots")
  
  ggsave(filename = file.path(output_dir, "qq_plots_combined.png"),
         plot = combined, width = 12, height = 8, dpi = 300)
}

# ============================================
# 相关矩阵热图
# ============================================
generate_correlation_heatmap <- function(data, output_dir, config) {
  
  # 选择数值变量
  numeric_data <- data[, sapply(data, is.numeric), drop = FALSE]
  
  if (ncol(numeric_data) < 2) {
    cat("  警告: 数值变量不足2个，跳过相关矩阵热图\n")
    return()
  }
  
  # 限制变量数量
  max_vars <- config$max_correlation_vars %||% 15
  if (ncol(numeric_data) > max_vars) {
    numeric_data <- numeric_data[, 1:max_vars]
    cat(sprintf("  限制相关矩阵为前%d个变量\n", max_vars))
  }
  
  # 计算相关矩阵
  cor_matrix <- cor(numeric_data, use = "pairwise.complete.obs")
  
  # 转换为长格式
  cor_long <- reshape2::melt(cor_matrix)
  names(cor_long) <- c("Var1", "Var2", "Correlation")
  
  # 热图
  p <- ggplot(cor_long, aes(x = Var1, y = Var2, fill = Correlation)) +
    geom_tile() +
    scale_fill_gradient2(low = "#2166AC", mid = "white", high = "#B2182B",
                         limit = c(-1, 1), name = "Correlation") +
    geom_text(aes(label = sprintf("%.2f", Correlation)), size = 3) +
    labs(title = "Correlation Matrix Heatmap") +
    theme_minimal() +
    theme(axis.text.x = element_text(angle = 45, hjust = 1))
  
  ggsave(filename = file.path(output_dir, "correlation_heatmap.png"),
         plot = p, width = max(10, ncol(cor_matrix) * 0.8), 
         height = max(8, ncol(cor_matrix) * 0.7), dpi = 300)
}

# ============================================
# 综合面板图
# ============================================
generate_summary_panel <- function(data, vars, group_var, output_dir) {
  
  if (is.null(vars) || length(vars) == 0) {
    vars <- head(names(data)[sapply(data, is.numeric)], 4)
  }
  
  vars_to_plot <- head(vars, 4)
  n <- length(vars_to_plot)
  
  plots <- list()
  
  for (var in vars_to_plot) {
    if (is.numeric(data[[var]])) {
      if (!is.null(group_var)) {
        p <- ggplot(data, aes_string(x = group_var, y = var, fill = group_var)) +
          geom_boxplot(alpha = 0.7) +
          labs(title = var, y = var) +
          theme_minimal() +
          theme(legend.position = "none",
                axis.text.x = element_text(angle = 45, hjust = 1))
      } else {
        p <- ggplot(data, aes_string(x = var)) +
          geom_histogram(bins = 30, fill = "#4292C6", alpha = 0.7) +
          labs(title = var, y = "Count") +
          theme_minimal()
      }
      plots[[var]] <- p
    }
  }
  
  if (length(plots) > 0) {
    ncol <- min(2, length(plots))
    nrow <- ceiling(length(plots) / ncol)
    
    combined <- do.call(grid.arrange, c(plots, ncol = ncol, nrow = nrow,
                                         top = "Summary Visualization Panel"))
    
    ggsave(filename = file.path(output_dir, "summary_panel.png"),
           plot = combined, width = 10, height = 5 * nrow, dpi = 300)
  }
}

# ============================================
# ROC曲线图
# ============================================
plot_roc_curve <- function(roc_obj, output_dir, name = "roc_curve") {
  
  p <- ggroc(roc_obj, alpha = 0.5, linewidth = 1.5) +
    geom_abline(intercept = 1, slope = 1, linetype = "dashed", color = "gray50") +
    labs(title = paste("ROC Curve -", name),
         subtitle = sprintf("AUC = %.3f (95%% CI: %.3f-%.3f)",
                           auc(roc_obj),
                           ci(roc_obj)[1], ci(roc_obj)[3])) +
    theme_minimal()
  
  ggsave(filename = file.path(output_dir, paste0(name, "_roc.png")),
         plot = p, width = 8, height = 6, dpi = 300)
  
  return(p)
}
