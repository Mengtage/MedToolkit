#!/usr/bin/env python3
# ============================================
# ROC曲线分析模块 (Python版本)
# ============================================

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.metrics import roc_curve, auc
import warnings

def roc_analysis(data, predictor, outcome, control=None, output_dir='./output', 
                 config=None, verbose=True):
    """
    ROC曲线分析
    
    Parameters:
    -----------
    data : pd.DataFrame
        输入数据
    predictor : str
        预测变量名（诊断指标）
    outcome : str
        结局变量名（二分类）
    control : str, optional
        对照组变量
    config : dict
        配置参数
    verbose : bool
        是否输出详细信息
        
    Returns:
    --------
    dict : 包含ROC分析结果
    """
    if config is None:
        config = {}
    
    if verbose:
        print("开始ROC曲线分析...\n")
    
    # 获取预测变量和结局变量
    if isinstance(predictor, str):
        x = data[predictor].values
    else:
        x = predictor
    
    if isinstance(outcome, str):
        y = data[outcome].values
    else:
        y = outcome
    
    # 移除缺失值
    valid_idx = ~(np.isnan(x) | np.isnan(y))
    x = x[valid_idx]
    y = y[valid_idx]
    
    # 计算ROC曲线
    fpr, tpr, thresholds = roc_curve(y, x)
    roc_auc = auc(fpr, tpr)
    
    # 计算95%置信区间（Bootstrap方法）
    n_bootstrap = config.get('bootstrap_n', 2000)
    auc_ci = bootstrap_auc_ci(x, y, n_bootstrap=n_bootstrap)
    
    # 寻找最佳截断值（Youden指数）
    youden_index = tpr - fpr
    optimal_idx = np.argmax(youden_index)
    optimal_threshold = thresholds[optimal_idx]
    optimal_sensitivity = tpr[optimal_idx]
    optimal_specificity = 1 - fpr[optimal_idx]
    
    # 计算约登指数
    youden = optimal_sensitivity + optimal_specificity - 1
    
    if verbose:
        print(f"ROC分析结果:")
        print(f"  AUC: {roc_auc:.4f} (95%CI: {auc_ci[0]:.4f}-{auc_ci[1]:.4f})")
        print(f"  最佳截断值: {optimal_threshold:.4f}")
        print(f"  敏感性: {optimal_sensitivity:.4f}")
        print(f"  特异性: {optimal_specificity:.4f}")
        print(f"  约登指数: {youden:.4f}\n")
    
    results = {
        'auc': roc_auc,
        'auc_ci': auc_ci,
        'fpr': fpr,
        'tpr': tpr,
        'thresholds': thresholds,
        'optimal_threshold': optimal_threshold,
        'optimal_sensitivity': optimal_sensitivity,
        'optimal_specificity': optimal_specificity,
        'youden_index': youden,
        'predictor': predictor if isinstance(predictor, str) else 'array',
        'outcome': outcome if isinstance(outcome, str) else 'array'
    }
    
    return results

def bootstrap_auc_ci(x, y, n_bootstrap=2000, ci=0.95):
    """
    使用Bootstrap方法计算AUC的置信区间
    
    Parameters:
    -----------
    x : array
        预测变量
    y : array
        结局变量
    n_bootstrap : int
        Bootstrap重采样次数
    ci : float
        置信水平
        
    Returns:
    --------
    tuple : (lower, upper) 置信区间
    """
    n = len(x)
    aucs = []
    
    np.random.seed(42)
    
    for _ in range(n_bootstrap):
        # 重采样
        idx = np.random.choice(n, size=n, replace=True)
        x_boot = x[idx]
        y_boot = y[idx]
        
        try:
            fpr, tpr, _ = roc_curve(y_boot, x_boot)
            auc_boot = auc(fpr, tpr)
            aucs.append(auc_boot)
        except:
            continue
    
    if len(aucs) == 0:
        return (0.5, 0.5)
    
    # 计算置信区间
    alpha = 1 - ci
    lower = np.percentile(aucs, alpha/2 * 100)
    upper = np.percentile(aucs, (1 - alpha/2) * 100)
    
    return (lower, upper)

def compare_roc_curves(results_list, verbose=True):
    """
    比较多条ROC曲线（DeLong检验）
    
    Parameters:
    -----------
    results_list : list
        多个roc_analysis结果
    verbose : bool
        是否输出详细信息
        
    Returns:
    --------
    dict : 比较结果
    """
    if verbose:
        print("ROC曲线比较分析...\n")
    
    n_curves = len(results_list)
    comparison = []
    
    for i in range(n_curves):
        for j in range(i+1, n_curves):
            res1 = results_list[i]
            res2 = results_list[j]
            
            # 使用AUC差异的Z检验（简化版DeLong检验）
            z_stat, p_value = delong_z_test(
                res1['fpr'], res1['tpr'],
                res2['fpr'], res2['tpr'],
                res1['auc'], res2['auc']
            )
            
            comparison.append({
                'curve1': res1.get('predictor', f'Curve_{i}'),
                'curve2': res2.get('predictor', f'Curve_{j}'),
                'auc1': res1['auc'],
                'auc2': res2['auc'],
                'auc_diff': res1['auc'] - res2['auc'],
                'z_statistic': z_stat,
                'p_value': p_value
            })
            
            if verbose:
                print(f"{res1['predictor']} vs {res2['predictor']}:")
                print(f"  AUC差异: {res1['auc'] - res2['auc']:.4f}")
                print(f"  Z统计量: {z_stat:.4f}")
                print(f"  P值: {p_value:.4f}")
                if p_value < 0.05:
                    print(f"  结论: 两条ROC曲线存在显著差异")
                else:
                    print(f"  结论: 两条ROC曲线无显著差异")
                print()
    
    return {'comparisons': comparison}

def delong_z_test(fpr1, tpr1, fpr2, tpr2, auc1, auc2):
    """
    DeLong检验的Z统计量（简化版）
    
    Note: 完整的DeLong检验需要计算协方差矩阵，
    这里使用简化的Z检验方法
    """
    n1 = len(fpr1)
    n2 = len(fpr2)
    
    # 简化的方差估计
    var1 = auc1 * (1 - auc1) / n1
    var2 = auc2 * (1 - auc2) / n2
    
    # Z统计量
    diff = auc1 - auc2
    se = np.sqrt(var1 + var2)
    
    if se == 0:
        return 0, 1
    
    z_stat = diff / se
    p_value = 2 * (1 - stats.norm.cdf(abs(z_stat)))
    
    return z_stat, p_value

def calculate_predictive_values(y_true, y_pred, threshold):
    """
    计算预测值指标
    
    Parameters:
    -----------
    y_true : array
        真实结局
    y_pred : array
        预测概率
    threshold : float
        截断值
        
    Returns:
    --------
    dict : 预测值指标
    """
    y_binary = (y_pred >= threshold).astype(int)
    
    # 计算混淆矩阵
    tp = np.sum((y_binary == 1) & (y_true == 1))
    tn = np.sum((y_binary == 0) & (y_true == 0))
    fp = np.sum((y_binary == 1) & (y_true == 0))
    fn = np.sum((y_binary == 0) & (y_true == 1))
    
    # 计算指标
    sensitivity = tp / (tp + fn) if (tp + fn) > 0 else 0
    specificity = tn / (tn + fp) if (tn + fp) > 0 else 0
    ppv = tp / (tp + fp) if (tp + fp) > 0 else 0
    npv = tn / (tn + fn) if (tn + fn) > 0 else 0
    
    return {
        'sensitivity': sensitivity,
        'specificity': specificity,
        'ppv': ppv,
        'npv': npv,
        'tp': tp,
        'tn': tn,
        'fp': fp,
        'fn': fn
    }
