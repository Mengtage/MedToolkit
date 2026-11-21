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
        self.y_true = np.asarray(y_true, dtype=float)
        self.y_scores = np.asarray(y_scores, dtype=float)
        self.threshold = float(threshold)
        if (self.y_true.ndim != 1 or self.y_scores.ndim != 1 or
                len(self.y_true) == 0 or len(self.y_true) != len(self.y_scores)):
            raise ValueError('真实标签与预测分数必须是等长非空一维数组')
        if (not np.all(np.isfinite(self.y_true)) or
                not np.all(np.isin(self.y_true, [0, 1])) or
                not np.all(np.isfinite(self.y_scores)) or not np.isfinite(self.threshold)):
            raise ValueError('需要有限预测分数、有限阈值及二元0/1标签')
        self.y_true = self.y_true.astype(int)
        # Only actual 0/1 values are class labels; one unique fractional value
        # is still a probability/score and must be thresholded.
        self.is_probability = not np.all(np.isin(self.y_scores, [0, 1]))
        self.y_probs = None
        if y_probs is not None:
            self.y_probs = np.asarray(y_probs, dtype=float)
            if (self.y_probs.ndim != 1 or len(self.y_probs) != len(self.y_true) or
                    not np.all(np.isfinite(self.y_probs)) or
                    np.any((self.y_probs < 0) | (self.y_probs > 1))):
                raise ValueError('预测概率必须与标签等长且处于[0,1]')
            self.is_probability = True
        elif self.is_probability:
            self.y_probs = self.y_scores
        self.y_pred = ((self.y_scores >= self.threshold).astype(int)
                       if self.is_probability else self.y_scores.astype(int))

    def calculate_confusion_matrix(self):
        """
        计算混淆矩阵
        
        Returns:
        --------
        dict
            包含TP, TN, FP, FN
        """
        cm = confusion_matrix(self.y_true, self.y_pred, labels=[0, 1])
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
        
        if len(np.unique(self.y_true)) != 2:
            raise ValueError('ROC需要两类真实结局')
        fpr, tpr, thresholds = roc_curve(self.y_true, probs)
        roc_auc = auc(fpr, tpr)
        
        # 计算最佳截断点（使用Youden指数）
        youden_indices = tpr - fpr
        finite_indices = np.flatnonzero(np.isfinite(thresholds))
        if len(finite_indices) == 0:
            raise ValueError('ROC没有有限的可用阈值')
        optimal_idx = finite_indices[np.argmax(youden_indices[finite_indices])]
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
        
        if type(n_bins) is not int or n_bins < 1:
            raise ValueError('分箱数量必须是正整数')
        if np.any((probs < 0) | (probs > 1)):
            raise ValueError('校准分析需要[0,1]概率，不能使用未校准的分数')

        # Brier分数
        brier_score = np.mean((probs - self.y_true) ** 2)
        
        # 校准曲线
        if n_bins > len(self.y_true):
            n_bins = max(2, len(self.y_true) // 2)
        
        # 按预测概率分箱
        bins = np.linspace(0, 1, n_bins + 1)
        bin_indices = np.minimum(np.digitize(probs, bins) - 1, n_bins - 1)
        
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
        
        # Keep the legacy equal-width bins; include BOTH outcome cells.
        # Quantile-based HL grouping is a separate policy decision.
        expected = np.asarray(hl_expected, dtype=float)
        observed = np.asarray(hl_observed, dtype=float)
        sizes = np.asarray([row['n'] for row in calib_data], dtype=float)
        df = len(expected) - 2
        degenerate = bool(np.any((expected <= 0) | (expected >= sizes)))
        hl_stat = None if degenerate else float(np.sum(
            (observed - expected) ** 2 / expected +
            (observed - expected) ** 2 / (sizes - expected)))
        hl_pvalue = float(chi2.sf(hl_stat, df)) if hl_stat is not None and df > 0 else None
        hl_status = ('zero_expected_cell' if degenerate else
                     'insufficient_groups' if df <= 0 else 'approximate')

        # 校准斜率和截距（使用isotonic regression）
        ir = IsotonicRegression(out_of_bounds='clip')
        calib_probs = ir.fit_transform(probs, self.y_true)
        
        return {
            'brier_score': float(brier_score),
            'calibration_curve': calib_data,
            'hosmer_lemeshow': {
                'statistic': hl_stat,
                'p_value': hl_pvalue,
                'bins': n_bins,
                'occupied_bins': len(expected),
                'df': df,
                'status': hl_status,
                'binning': 'legacy_equal_width',
                'expected_events': expected.tolist(),
                'observed_events': observed.tolist(),
                'group_sizes': sizes.astype(int).tolist(),
                'small_expected_cells': bool(np.any((expected < 5) | (sizes - expected < 5)))
            },
            'calibrated_probs': calib_probs.tolist(),
            'is_probability': self.is_probability
        }
    
    def _paired_probabilities(self, old_probs):
        old = np.asarray(old_probs, dtype=float)
        new = np.asarray(self.y_probs, dtype=float)
        if (old.ndim != 1 or old.shape != self.y_true.shape or
                not np.all(np.isfinite(old)) or np.any((old < 0) | (old > 1)) or
                not np.all(np.isfinite(new)) or np.any((new < 0) | (new > 1))):
            raise ValueError('新旧概率必须等长、有限且处于[0,1]，按同一受试者顺序配对')
        if len(np.unique(self.y_true)) != 2:
            raise ValueError('NRI/IDI需要同时存在事件与非事件')
        return old

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
        
        old_probs = self._paired_probabilities(old_probs)
        
        new_thresholds = np.asarray(new_thresholds, dtype=float)
        if (new_thresholds.ndim != 1 or not len(new_thresholds) or
                not np.all(np.isfinite(new_thresholds)) or
                np.any((new_thresholds <= 0) | (new_thresholds >= 1))):
            raise ValueError('NRI阈值必须为0至1之间的有限一维数组（不含端点）')
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
                'threshold': float(threshold),
                'method': 'binary_category_nri_at_each_threshold',
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
        
        old_probs = self._paired_probabilities(old_probs)
        
        # 事件组概率差异
        mean_prob_event_new = np.mean(self.y_probs[self.y_true == 1])
        mean_prob_event_old = np.mean(old_probs[self.y_true == 1])
        
        # 非事件组概率差异
        mean_prob_non_event_new = np.mean(self.y_probs[self.y_true == 0])
        mean_prob_non_event_old = np.mean(old_probs[self.y_true == 0])
        
        # IDI
        idi = (mean_prob_event_new - mean_prob_event_old) - (mean_prob_non_event_new - mean_prob_non_event_old)
        
        # Fixed paired predictions: sample variance of within-person differences.
        # This does not account for model refitting uncertainty.
        differences = self.y_probs - old_probs
        event_diff = differences[self.y_true == 1]
        non_event_diff = differences[self.y_true == 0]
        enough = len(event_diff) >= 2 and len(non_event_diff) >= 2
        variance = (np.var(event_diff, ddof=1) / len(event_diff) +
                    np.var(non_event_diff, ddof=1) / len(non_event_diff)) if enough else None
        se = float(np.sqrt(variance)) if variance is not None else None
        z_score = float(idi / se) if se is not None and se > 0 else None

        return {
            'idi': float(idi),
            'se': se,
            'z_score': z_score,
            'variance_method': 'paired_differences_sample_variance_fixed_predictions',
            'inference_status': 'insufficient_group_size' if not enough else 'zero_variance' if se == 0 else 'approximate_fixed_predictions',
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
        
        thresholds = np.asarray(thresholds, dtype=float)
        if (thresholds.ndim != 1 or not len(thresholds) or
                not np.all(np.isfinite(thresholds)) or np.any((thresholds < 0) | (thresholds > 1))):
            raise ValueError('DCA阈值必须为[0,1]有限一维数组')
        if not np.all(np.isfinite(probs)) or np.any((probs < 0) | (probs > 1)):
            raise ValueError('DCA需要[0,1]概率')
        # 计算净获益
        n = len(self.y_true)
        n_events = np.sum(self.y_true == 1)
        n_non_events = n - n_events
        
        net_benefit = []
        net_benefit_all = []  # 全部治疗
        net_benefit_none = []  # 全部不治疗
        
        for p in thresholds:
            if p == 1:
                net_benefit.append(None)
                net_benefit_all.append(None)
                net_benefit_none.append(0.0)
                continue
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
            'undefined_thresholds': [1.0] if np.any(thresholds == 1) else [],
            'threshold_rule': 'probability >= threshold',
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