#!/usr/bin/env Rscript
# ============================================
# 数据导入模块
# 医学统计分析自动化系统
# 
# 支持格式:
# - CSV (.csv)
# - Excel (.xlsx, .xls)
# - SPSS (.sav) via haven
# - STATA (.dta) via haven
#
# 功能:
# 1. 自动检测数据格式
# 2. 数据类型识别(数值/字符/因子)
# 3. 自动识别变量类型
# 4. 缺失值标记处理
# ============================================

import_data <- function(file_path, encoding = "UTF-8") {
  
  cat("开始数据导入...\n")
  
  # 检查文件是否存在
  if (!file.exists(file_path)) {
    stop("错误: 文件不存在 - ", file_path)
  }
  
  # 获取文件扩展名
  ext <- tools::file_ext(file_path)
  
  # 根据扩展名选择导入方法
  data <- switch(ext,
    "csv" = {
      read.csv(file_path, header = TRUE, sep = ",",
               encoding = encoding, stringsAsFactors = FALSE)
    },
    "txt" = {
      read.table(file_path, header = TRUE, sep = "\t",
                 encoding = encoding, stringsAsFactors = FALSE)
    },
    "xlsx" = {
      openxlsx::read.xlsx(file_path)
    },
    "xls" = {
      gdata::read.xls(file_path)
    },
    "sav" = {
      haven::read_sav(file_path)
    },
    "dta" = {
      haven::read_dta(file_path)
    },
    {
      stop("不支持的文件格式: ", ext)
    }
  )
  
  # 数据基本信息
  cat("\n========== 数据导入报告 ==========\n")
  cat("文件路径:", file_path, "\n")
  cat("数据维度:", nrow(data), "行 x", ncol(data), "列\n")
  cat("内存占用:", format(object.size(data), units = "auto"), "\n")
  cat("===================================\n\n")
  
  # 自动识别变量类型
  data <- auto_detect_types(data)
  
  return(data)
}

# 自动检测变量类型
auto_detect_types <- function(data) {
  
  cat("开始自动识别变量类型...\n")
  
  for (col in names(data)) {
    # 检查是否为数值型
    if (is.numeric(data[[col]])) {
      next
    }
    
    # 检查唯一值数量
    unique_vals <- unique(data[[col]])
    n_unique <- length(unique_vals)
    n_total <- length(data[[col]])
    
    # 分类判断
    if (n_unique <= 2) {
      # 二分类变量
      data[[col]] <- as.factor(data[[col]])
      cat(sprintf("  %s -> 二分类因子 (levels: %s)\n", 
                  col, paste(levels(data[[col]]), collapse = ", ")))
      
    } else if (n_unique <= 10 && is.character(data[[col]])) {
      # 多分类变量(字符型)
      data[[col]] <- as.factor(data[[col]])
      cat(sprintf("  %s -> 多分类因子 (%d levels)\n", col, n_unique))
      
    } else if (is.character(data[[col]])) {
      # 尝试转换为数值
      suppressWarnings(num_check <- as.numeric(data[[col]]))
      if (sum(!is.na(num_check)) > length(data[[col]]) * 0.5) {
        data[[col]] <- num_check
        cat(sprintf("  %s -> 数值型 (自动转换)\n", col))
      } else {
        data[[col]] <- as.factor(data[[col]])
        cat(sprintf("  %s -> 分类因子 (%d levels)\n", col, n_unique))
      }
    }
  }
  
  return(data)
}

# 数据预览
preview_data <- function(data, n = 10) {
  cat("\n========== 数据预览 ==========\n")
  cat("前", n, "行数据:\n")
  print(head(data, n))
  cat("\n数据类型:\n")
  print(sapply(data, class))
  cat("\n================================\n")
}
