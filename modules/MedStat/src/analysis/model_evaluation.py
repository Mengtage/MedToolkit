"""
预测模型评估模块

提供完整的预测模型评估功能，包括：
- 分类性能指标（灵敏度、特异度、PPV、NPV等）
- ROC曲线分析（AUC值、最佳截断点）
- 校准度评估（校准曲线、Brier分数）
- 临床实用性评估（DCA、NRI、IDI）
"""

import numpy as np
import pandas as pd
from sklearn.metrics import (
    roc_curve, auc, confusion_matrix,
    accuracy_score, precision_score, recall_score, f1_score,
    matthews_corrcoef
)
from scipy.stats import chi2
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression

class ModelEvaluator:
    """
    预测模型评估器
    
    提供全面的预测模型评估功能，遵循TRIPOD声明和PROBAST标准
    """
    
    def __init__(self, y_true, y_scores, y_probs=None, threshold=0.5):
        """
        初始化评估器
        
        Parameters:
        -----------
        y_true : array-like
            真实标签（0/1）
        y_scores : array-like
            预测分数或概率
        y_probs : array-like, optional
            预测概率（如果y_scores不是概率）
        threshold : float, optional
            默认分类阈值（默认0.5）
        """
        self.y_true = np.array(y_true)
        self.y_scores = np.array(y_scores)
        self.threshold = threshold
        
        # 自动检测输入类型：概率值还是分类结果
        unique_values = np.unique(self.y_scores)
        self.is_probability = len(unique_values) > 2 or (
            len(unique_values) == 2 and 
            not np.all(np.isin(unique_values, [0, 1]))
        )
        
        if self.is_probability:
            # 输入是概率值
            self.y_probs = np.array(y_probs) if y_probs is not None else self.y_scores
            self.y_pred = (self.y_scores >= threshold).astype(int)
        else:
            # 输入是分类结果（0/1）
            self.y_probs = None
            self.y_pred = self.y_scores.astype(int)
        
    def calculate_confusion_matrix(self):
        """
        计算混淆矩阵
        
        Returns:
        --------
        dict
            包含TP, TN, FP, FN
        """
        cm = confusion_matrix(self.y_true, self.y_pred)
        if cm.shape[0] == 1:
            if self.y_true[0] == 0:
                return {'TP': 0, 'TN': cm[0, 0], 'FP': 0, 'FN': 0}
            else:
                return {'TP': cm[0, 0], 'TN': 0, 'FP': 0, 'FN': 0}
        
        TN, FP, FN, TP = cm.ravel()
        return {
            'TP': int(TP),
            'TN': int(TN),
            'FP': int(FP),
            'FN': int(FN),
            'matrix': cm.tolist()
        }
    
    def calculate_basic_metrics(self):
        """
        计算基础分类指标
        
        Returns:
        --------
        dict
            包含灵敏度、特异度、PPV、NPV、准确率、F1、Youden指数、MCC
        """
        cm = self.calculate_confusion_matrix()
        TP, TN, FP, FN = cm['TP'], cm['TN'], cm['FP'], cm['FN']
        
        # 灵敏度（召回率）
        sensitivity = TP / (TP + FN) if (TP + FN) > 0 else 0
        
        # 特异度
        specificity = TN / (TN + FP) if (TN + FP) > 0 else 0
        
        # 阳性预测值（精确率）
        ppv = TP / (TP + FP) if (TP + FP) > 0 else 0
        
        # 阴性预测值
        npv = TN / (TN + FN) if (TN + FN) > 0 else 0
        
        # 准确率
        accuracy = (TP + TN) / (TP + TN + FP + FN) if (TP + TN + FP + FN) > 0 else 0
        
        # F1分数
        f1 = f1_score(self.y_true, self.y_pred)
        
        # Youden指数
        youden = sensitivity + specificity - 1
        
        # MCC
        mcc = matthews_corrcoef(self.y_true, self.y_pred)
        
        return {
            'sensitivity': sensitivity,
            'specificity': specificity,
            'ppv': ppv,
            'npv': npv,
            'accuracy': accuracy,
            'f1_score': f1,
            'youden_index': youden,
            'mcc': mcc
        }
    
    def calculate_roc_curve(self):
        """
        计算ROC曲线数据
        
        Returns:
        --------
        dict
            包含fpr、tpr、thresholds和AUC值
        """
        # 如果输入是分类结果，自动转换为伪概率值
        probs = self.y_probs if self.is_probability else self.y_scores.astype(float)
        
        fpr, tpr, thresholds = roc_curve(self.y_true, probs)
        roc_auc = auc(fpr, tpr)
        
        # 计算最佳截断点（使用Youden指数）
        youden_indices = tpr - fpr
        optimal_idx = np.argmax(youden_indices)
        optimal_threshold = thresholds[optimal_idx]
        
        # 修复：将inf值替换为None，避免JSON序列化失败
        thresholds_clean = [float(t) if np.isfinite(t) else None for t in thresholds]
        fpr_clean = [float(x) for x in fpr]
        tpr_clean = [float(x) for x in tpr]
        
        return {
            'fpr': fpr_clean,
            'tpr': tpr_clean,
            'thresholds': thresholds_clean,
            'auc': float(roc_auc),
            'optimal_threshold': float(optimal_threshold),
            'optimal_tpr': float(tpr[optimal_idx]),
            'optimal_fpr': float(fpr[optimal_idx]),
            'is_probability': self.is_probability
        }
    
    def calculate_calibration_metrics(self, n_bins=10):
        """
        计算校准度指标
        
        Parameters:
        -----------
        n_bins : int
            分箱数量（默认10）
        
        Returns:
        --------
        dict
            包含校准曲线数据、Brier分数、Hosmer-Lemeshow检验结果
        """
        # 如果输入是分类结果，自动转换为伪概率值
        probs = self.y_probs if self.is_probability else self.y_scores.astype(float)
        
        # Brier分数
        brier_score = np.mean((probs - self.y_true) ** 2)
        
        # 校准曲线
        if n_bins > len(self.y_true):
            n_bins = max(2, len(self.y_true) // 2)
        
        # 按预测概率分箱
        bins = np.linspace(0, 1, n_bins + 1)
        bin_indices = np.digitize(probs, bins) - 1
        
        calib_data = []
        hl_expected = []
        hl_observed = []
        
        for i in range(n_bins):
            mask = bin_indices == i
            if np.any(mask):
                bin_probs = probs[mask]
                bin_true = self.y_true[mask]
                mean_prob = np.mean(bin_probs)
                mean_true = np.mean(bin_true)
                n_bin = len(bin_true)
                calib_data.append({
                    'bin': i + 1,
                    'mean_predicted': float(mean_prob),
                    'mean_observed': float(mean_true),
                    'n': int(n_bin)
                })
                hl_expected.append(n_bin * mean_prob)
                hl_observed.append(np.sum(bin_true))
        
        # Hosmer-Lemeshow检验
        hl_stat = 0
        hl_pvalue = 1.0
        if len(hl_expected) >= 2:
            hl_expected = np.array(hl_expected)
            hl_observed = np.array(hl_observed)
            mask = hl_expected > 0
            if np.any(mask):
                hl_stat = np.sum((hl_observed[mask] - hl_expected[mask]) ** 2 / hl_expected[mask])
                df = len(hl_expected[mask]) - 2
                if df > 0:
                    hl_pvalue = 1 - chi2.cdf(hl_stat, df)
        
        # 校准斜率和截距（使用isotonic regression）
        ir = IsotonicRegression(out_of_bounds='clip')
        calib_probs = ir.fit_transform(probs, self.y_true)
        
        return {
            'brier_score': float(brier_score),
            'calibration_curve': calib_data,
            'hosmer_lemeshow': {
                'statistic': float(hl_stat),
                'p_value': float(hl_pvalue),
                'bins': n_bins
            },
            'calibrated_probs': calib_probs.tolist(),
            'is_probability': self.is_probability
        }
    
    def calculate_nri(self, old_probs, new_thresholds=None):
        """
        计算净重分类改善（NRI）
        
        Parameters:
        -----------
        old_probs : array-like
            旧模型的预测概率
        new_thresholds : list, optional
            风险阈值列表，默认[0.1, 0.2, 0.5]
        
        Returns:
        --------
        dict
            包含NRI结果
        """
        # 如果没有概率值，返回错误
        if self.y_probs is None:
            return {'error': 'NRI计算需要概率值输入'}
        
        if new_thresholds is None:
            new_thresholds = [0.1, 0.2, 0.5]
        
        old_probs = np.array(old_probs)
        
        nri_results = {}
        total_events = np.sum(self.y_true == 1)
        total_non_events = np.sum(self.y_true == 0)
        
        for threshold in new_thresholds:
            # 事件组中：旧模型低风险，新模型高风险
            event_up = np.sum((old_probs < threshold) & (self.y_probs >= threshold) & (self.y_true == 1))
            
            # 事件组中：旧模型高风险，新模型低风险
            event_down = np.sum((old_probs >= threshold) & (self.y_probs < threshold) & (self.y_true == 1))
            
            # 非事件组中：旧模型低风险，新模型高风险
            non_event_up = np.sum((old_probs < threshold) & (self.y_probs >= threshold) & (self.y_true == 0))
            
            # 非事件组中：旧模型高风险，新模型低风险
            non_event_down = np.sum((old_probs >= threshold) & (self.y_probs < threshold) & (self.y_true == 0))
            
            # NRI事件组
            nri_event = (event_up - event_down) / total_events if total_events > 0 else 0
            
            # NRI非事件组
            nri_non_event = (non_event_down - non_event_up) / total_non_events if total_non_events > 0 else 0
            
            # 总NRI
            nri_total = nri_event + nri_non_event
            
            nri_results[f'threshold_{threshold}'] = {
                'threshold': threshold,
                'event_up': int(event_up),
                'event_down': int(event_down),
                'non_event_up': int(non_event_up),
                'non_event_down': int(non_event_down),
                'nri_event': float(nri_event),
                'nri_non_event': float(nri_non_event),
                'nri_total': float(nri_total)
            }
        
        return nri_results
    
    def calculate_idi(self, old_probs):
        """
        计算综合判别改善（IDI）
        
        Parameters:
        -----------
        old_probs : array-like
            旧模型的预测概率
        
        Returns:
        --------
        dict
            包含IDI结果
        """
        # 如果没有概率值，返回错误
        if self.y_probs is None:
            return {'error': 'IDI计算需要概率值输入'}
        
        old_probs = np.array(old_probs)
        
        # 事件组概率差异
        mean_prob_event_new = np.mean(self.y_probs[self.y_true == 1])
        mean_prob_event_old = np.mean(old_probs[self.y_true == 1])
        
        # 非事件组概率差异
        mean_prob_non_event_new = np.mean(self.y_probs[self.y_true == 0])
        mean_prob_non_event_old = np.mean(old_probs[self.y_true == 0])
        
        # IDI
        idi = (mean_prob_event_new - mean_prob_event_old) - (mean_prob_non_event_new - mean_prob_non_event_old)
        
        # 方差估计（简化版）
        n_events = np.sum(self.y_true == 1)
        n_non_events = np.sum(self.y_true == 0)
        
        var_event_new = np.var(self.y_probs[self.y_true == 1]) if n_events > 0 else 0
        var_event_old = np.var(old_probs[self.y_true == 1]) if n_events > 0 else 0
        var_non_event_new = np.var(self.y_probs[self.y_true == 0]) if n_non_events > 0 else 0
        var_non_event_old = np.var(old_probs[self.y_true == 0]) if n_non_events > 0 else 0
        
        variance = (var_event_new + var_event_old) / n_events + (var_non_event_new + var_non_event_old) / n_non_events
        se = np.sqrt(variance) if variance > 0 else 0
        z_score = idi / se if se > 0 else 0
        
        return {
            'idi': float(idi),
            'se': float(se),
            'z_score': float(z_score),
            'mean_prob_event_new': float(mean_prob_event_new),
            'mean_prob_event_old': float(mean_prob_event_old),
            'mean_prob_non_event_new': float(mean_prob_non_event_new),
            'mean_prob_non_event_old': float(mean_prob_non_event_old)
        }
    
    def decision_curve_analysis(self, thresholds=None):
        """
        决策曲线分析（DCA）
        
        Parameters:
        -----------
        thresholds : array-like, optional
            阈值概率范围，默认0到1，步长0.01
        
        Returns:
        --------
        dict
            包含DCA曲线数据
        """
        # 如果输入是分类结果，自动转换为伪概率值
        probs = self.y_probs if self.is_probability else self.y_scores.astype(float)
        
        if thresholds is None:
            thresholds = np.linspace(0, 1, 101)
        
        # 计算净获益
        n = len(self.y_true)
        n_events = np.sum(self.y_true == 1)
        n_non_events = n - n_events
        
        net_benefit = []
        net_benefit_all = []  # 全部治疗
        net_benefit_none = []  # 全部不治疗
        
        for p in thresholds:
            # 当前模型的净获益
            pred_high_risk = probs >= p
            tp = np.sum(pred_high_risk & (self.y_true == 1))
            fp = np.sum(pred_high_risk & (self.y_true == 0))
            
            nb = (tp / n) - (fp / n) * (p / (1 - p)) if p < 1 else 0
            net_benefit.append(float(nb))
            
            # 全部治疗的净获益
            nb_all = (n_events / n) - (n_non_events / n) * (p / (1 - p)) if p < 1 else 0
            net_benefit_all.append(float(nb_all))
            
            # 全部不治疗的净获益
            net_benefit_none.append(0.0)
        
        return {
            'thresholds': thresholds.tolist(),
            'net_benefit': net_benefit,
            'net_benefit_all': net_benefit_all,
            'net_benefit_none': net_benefit_none,
            'is_probability': self.is_probability
        }
    
    def evaluate(self):
        """
        执行完整评估
        
        Returns:
        --------
        dict
            包含所有评估指标
        """
        return {
            'confusion_matrix': self.calculate_confusion_matrix(),
            'basic_metrics': self.calculate_basic_metrics(),
            'roc_curve': self.calculate_roc_curve(),
            'calibration': self.calculate_calibration_metrics(),
            'dca': self.decision_curve_analysis()
        }


def evaluate_model(y_true, y_scores, y_probs=None, threshold=0.5):
    """
    便捷函数：评估预测模型
    
    Parameters:
    -----------
    y_true : array-like
        真实标签
    y_scores : array-like
        预测分数
    y_probs : array-like, optional
        预测概率
    threshold : float, optional
        分类阈值
    
    Returns:
    --------
    dict
        评估结果
    """
    evaluator = ModelEvaluator(y_true, y_scores, y_probs, threshold)
    return evaluator.evaluate()


def compare_models(y_true, new_probs, old_probs=None, threshold=0.5):
    """
    比较两个模型的性能
    
    Parameters:
    -----------
    y_true : array-like
        真实标签
    new_probs : array-like
        新模型预测概率
    old_probs : array-like, optional
        旧模型预测概率
    threshold : float, optional
        分类阈值
    
    Returns:
    --------
    dict
        包含两个模型的评估结果和比较指标
    """
    new_eval = evaluate_model(y_true, new_probs, new_probs, threshold)
    
    result = {
        'new_model': new_eval
    }
    
    if old_probs is not None:
        old_eval = evaluate_model(y_true, old_probs, old_probs, threshold)
        result['old_model'] = old_eval
        
        # 计算NRI和IDI
        evaluator = ModelEvaluator(y_true, new_probs, new_probs, threshold)
        result['nri'] = evaluator.calculate_nri(old_probs)
        result['idi'] = evaluator.calculate_idi(old_probs)
    
    return result