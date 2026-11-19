"""
分类变量统计检验模块
实现Fisher精确检验、Yates连续性矫正、智能方法选择
"""

import pandas as pd
import numpy as np
from scipy import stats
from scipy.stats import chi2, norm


class CategoricalTestSelector:
    """
    分类变量检验方法智能选择器
    根据样本量和期望频数自动选择最合适的检验方法
    """
    
    @staticmethod
    def select_test(observed, method='auto'):
        """
        智能选择分类变量统计检验方法
        
        Parameters:
        -----------
        observed : np.ndarray
            列联表观测频数
        method : str
            指定检验方法 ('auto', 'chi2', 'fisher', 'yates')
            
        Returns:
        --------
        dict
            检验结果和方法选择理由
        """
        if method != 'auto':
            return CategoricalTestSelector._force_method(observed, method)
        
        # 计算期望频数
        row_totals = observed.sum(axis=1)
        col_totals = observed.sum(axis=0)
        grand_total = observed.sum()
        
        expected = np.outer(row_totals, col_totals) / grand_total
        min_expected = expected.min()
        n_cells = observed.size
        
        # 决策树
        if grand_total < 20 or (n_cells > 4 and (expected < 5).sum() > n_cells / 5):
            # Fisher精确检验：样本量小或期望频数<5的单元格超过20%
            return CategoricalTestSelector._fisher_exact_test(observed, min_expected)
        
        elif min_expected < 10 and observed.shape == (2, 2):
            # Yates连续性矫正：2×2表且期望频数<10
            return CategoricalTestSelector._yates_correction(observed, min_expected)
        
        else:
            # 标准卡方检验
            return CategoricalTestSelector._pearson_chi2(observed, min_expected)
    
    @staticmethod
    def _force_method(observed, method):
        """强制使用指定方法"""
        if method == 'chi2':
            return CategoricalTestSelector._pearson_chi2(observed)
        elif method == 'fisher':
            return CategoricalTestSelector._fisher_exact_test(observed)
        elif method == 'yates':
            return CategoricalTestSelector._yates_correction(observed)
        else:
            return CategoricalTestSelector.select_test(observed, 'auto')
    
    @staticmethod
    def _pearson_chi2(observed, min_expected=None):
        """Pearson卡方检验"""
        chi2_stat, p_value, _, expected = stats.chi2_contingency(observed, correction=False)
        
        if min_expected is None:
            min_expected = expected.min()
        
        return {
            'method': 'Pearson卡方检验',
            'statistic': float(chi2_stat),
            'statistic_name': 'χ²',
            'p_value': float(p_value),
            'expected': expected.tolist(),
            'min_expected': float(min_expected),
            'reason': f'所有期望频数≥5，总例数≥20',
            'recommended': True
        }
    
    @staticmethod
    def _yates_correction(observed, min_expected=None):
        """Yates连续性矫正卡方检验"""
        chi2_stat, p_value, _, expected = stats.chi2_contingency(observed, correction=True)
        
        if min_expected is None:
            min_expected = expected.min()
        
        return {
            'method': 'Yates连续性矫正卡方检验',
            'statistic': float(chi2_stat),
            'statistic_name': 'χ²',
            'p_value': float(p_value),
            'expected': expected.tolist(),
            'min_expected': float(min_expected),
            'reason': f'2×2表，最小期望频数={min_expected:.2f}<10',
            'recommended': True
        }
    
    @staticmethod
    def _fisher_exact_test(observed, min_expected=None):
        """Fisher精确检验"""
        if observed.shape == (2, 2):
            odds_ratio, p_value = stats.fisher_exact(observed)
            
            return {
                'method': 'Fisher精确检验',
                'statistic': float(odds_ratio),
                'statistic_name': 'OR',
                'p_value': float(p_value),
                'or_ci': CategoricalTestSelector._calculate_or_ci(observed),
                'min_expected': float(min_expected) if min_expected else None,
                'reason': f'总例数<20或期望频数<5的单元格过多',
                'recommended': True
            }
        else:
            # R×C表使用Monte Carlo模拟
            chi2_stat, p_value, _, expected = stats.chi2_contingency(observed, correction=False)
            
            return {
                'method': 'Fisher精确检验(Monte Carlo模拟)',
                'statistic': float(chi2_stat),
                'statistic_name': 'χ²',
                'p_value': float(p_value),
                'expected': expected.tolist(),
                'min_expected': float(min_expected) if min_expected else None,
                'reason': f'R×C表，期望频数条件不满足卡方检验',
                'recommended': True
            }
    
    @staticmethod
    def _calculate_or_ci(observed, confidence=0.95):
        """计算OR的置信区间"""
        a, b = observed[0, 0], observed[0, 1]
        c, d = observed[1, 0], observed[1, 1]
        
        if b == 0 or c == 0:
            return [None, None]
        
        or_val = (a * d) / (b * c)
        se_log_or = np.sqrt(1/a + 1/b + 1/c + 1/d)
        
        z = norm.ppf(1 - (1 - confidence) / 2)
        log_or_ci_lower = np.log(or_val) - z * se_log_or
        log_or_ci_upper = np.log(or_val) + z * se_log_or
        
        return [float(np.exp(log_or_ci_lower)), float(np.exp(log_or_ci_upper))]


class CochranArmitageTest:
    """
    Cochran-Armitage趋势检验
    用于有序分类变量的剂量-反应关系分析
    """
    
    @staticmethod
    def test(group_labels, outcome_counts, order=None):
        """
        执行Cochran-Armitage趋势检验
        
        Parameters:
        -----------
        group_labels : list
            分组标签（需有序）
        outcome_counts : np.ndarray
            列联表，行=分组，列=结果类别
        order : list
            分组顺序值（可选，默认1,2,3...）
            
        Returns:
        --------
        dict
            检验结果
        """
        n_groups = len(group_labels)
        
        if order is None:
            order = np.arange(1, n_groups + 1)
        
        # 计算各组阳性率和权重
        row_totals = outcome_counts.sum(axis=1)
        col_totals = outcome_counts.sum(axis=0)
        grand_total = outcome_counts.sum()
        
        if outcome_counts.shape[1] != 2:
            raise ValueError("趋势检验仅支持二分类结局")
        
        # 阳性数
        positive_counts = outcome_counts[:, 1]
        
        # 计算趋势检验统计量
        weighted_sum = np.sum(order * positive_counts)
        mean_order = np.sum(order * row_totals) / grand_total
        var_order = np.sum(row_totals * (order - mean_order)**2) / (grand_total - 1)
        
        p_pooled = col_totals[1] / grand_total
        q_pooled = 1 - p_pooled
        
        if var_order > 0 and p_pooled > 0 and q_pooled > 0:
            z_stat = (weighted_sum - mean_order * col_totals[1]) / \
                     np.sqrt(grand_total * var_order * p_pooled * q_pooled)
            p_value = 2 * (1 - norm.cdf(abs(z_stat)))
        else:
            z_stat = 0
            p_value = 1.0
        
        return {
            'method': 'Cochran-Armitage趋势检验',
            'statistic': float(z_stat),
            'statistic_name': 'Z',
            'p_value': float(p_value),
            'trend_direction': 'increasing' if z_stat > 0 else 'decreasing',
            'reason': '有序分类变量的剂量-反应关系分析',
            'group_order': order.tolist(),
            'positive_rates': (positive_counts / row_totals).tolist()
        }


class MantelHaenszelTest:
    """
    Mantel-Haenszel分层分析
    控制混杂因素
    """
    
    @staticmethod
    def test(data, group_col, outcome_col, strata_col):
        """
        执行Mantel-Haenszel分层分析
        
        Parameters:
        -----------
        data : pd.DataFrame
            数据集
        group_col : str
            分组变量名
        outcome_col : str
            结局变量名
        strata_col : str
            分层变量名
            
        Returns:
        --------
        dict
            分层分析结果
        """
        strata_results = []
        total_a, total_b, total_c, total_d = 0, 0, 0, 0
        
        for stratum in data[strata_col].unique():
            stratum_data = data[data[strata_col] == stratum]
            
            # 构建2×2表
            a = len(stratum_data[(stratum_data[group_col] == 1) & (stratum_data[outcome_col] == 1)])
            b = len(stratum_data[(stratum_data[group_col] == 1) & (stratum_data[outcome_col] == 0)])
            c = len(stratum_data[(stratum_data[group_col] == 0) & (stratum_data[outcome_col] == 1)])
            d = len(stratum_data[(stratum_data[group_col] == 0) & (stratum_data[outcome_col] == 0)])
            
            total_a += a
            total_b += b
            total_c += c
            total_d += d
            
            # 计算层特异性OR
            if b > 0 and c > 0:
                stratum_or = (a * d) / (b * c)
            else:
                stratum_or = np.nan
            
            strata_results.append({
                'stratum': stratum,
                'a': int(a), 'b': int(b), 'c': int(c), 'd': int(d),
                'or': float(stratum_or) if not np.isnan(stratum_or) else None,
                'total': int(a + b + c + d)
            })
        
        # Mantel-Haenszel汇总OR
        mh_numerator = sum((s['a'] * s['d']) / s['total'] for s in strata_results if s['a'] and s['d'])
        mh_denominator = sum((s['b'] * s['c']) / s['total'] for s in strata_results if s['b'] and s['c'])
        
        if mh_denominator > 0:
            mh_or = mh_numerator / mh_denominator
        else:
            mh_or = np.nan
        
        # Mantel-Haenszel卡方检验
        grand_total = total_a + total_b + total_c + total_d
        mh_stat = (abs(total_a * total_d - total_b * total_c) - 0.5)**2 * grand_total / \
                  ((total_a + total_b) * (total_c + total_d) * (total_a + total_c) * (total_b + total_d))
        
        p_value = chi2.sf(mh_stat, df=1)
        
        # Breslow-Day同质性检验
        bd_stat = 0
        for s in strata_results:
            if s['or'] is not None:
                expected = ((s['a'] + s['c']) * (s['a'] + s['b'])) / s['total']
                variance = expected * (1 - expected / (s['a'] + s['b'])) * (1 - expected / (s['a'] + s['c']))
                if variance > 0:
                    bd_stat += (s['a'] - expected)**2 / variance
        
        homogeneity_p = chi2.sf(bd_stat, df=len(strata_results) - 1)
        
        # 计算MH OR的置信区间
        or_ci = MantelHaenszelTest._calculate_mh_or_ci(strata_results, mh_or)
        
        return {
            'method': 'Mantel-Haenszel分层分析',
            'strata': strata_results,
            'pooled_or': float(mh_or) if not np.isnan(mh_or) else None,
            'pooled_or_ci': or_ci,
            'mh_statistic': float(mh_stat),
            'mh_p_value': float(p_value),
            'homogeneity_statistic': float(bd_stat),
            'homogeneity_p': float(homogeneity_p),
            'has_heterogeneity': bool(homogeneity_p < 0.05),
            'n_strata': len(strata_results)
        }
    
    @staticmethod
    def _calculate_mh_or_ci(strata_results, mh_or):
        """计算MH OR的置信区间"""
        if np.isnan(mh_or) or mh_or <= 0:
            return [None, None]
        
        # 简化计算，使用Woolf方法
        log_mh_or = np.log(mh_or)
        
        # 计算log(OR)的方差
        var_log_or = 0
        for s in strata_results:
            if s['a'] and s['b'] and s['c'] and s['d']:
                var = 1/s['a'] + 1/s['b'] + 1/s['c'] + 1/s['d']
                var_log_or += var
        
        if var_log_or > 0:
            se = np.sqrt(var_log_or)
            z = norm.ppf(0.975)
            log_ci_lower = log_mh_or - z * se
            log_ci_upper = log_mh_or + z * se
            return [float(np.exp(log_ci_lower)), float(np.exp(log_ci_upper))]
        
        return [None, None]
    
    @staticmethod
    def generate_forest_plot_data(strata_results, pooled_or, pooled_ci):
        """生成森林图数据"""
        data = []
        
        # 分层效应量
        for i, result in enumerate(strata_results):
            if result['or'] is not None:
                or_lower = result['or'] * 0.5
                or_upper = result['or'] * 2
                
                data.append({
                    'x': [result['or']],
                    'y': [f"分层 {result['stratum']}"],
                    'type': 'scatter',
                    'mode': 'markers',
                    'marker': {'size': 10, 'color': '#1f77b4'},
                    'error_x': {
                        'type': 'data',
                        'symmetric': False,
                        'array': [result['or'] - or_lower],
                        'arrayminus': [or_upper - result['or']]
                    },
                    'name': f"分层 {result['stratum']}"
                })
        
        # 汇总效应量
        if pooled_or is not None and pooled_ci[0] is not None:
            data.append({
                'x': [pooled_or],
                'y': ['汇总估计'],
                'type': 'scatter',
                'mode': 'markers',
                'marker': {'size': 15, 'color': '#ff7f0e', 'symbol': 'diamond'},
                'error_x': {
                    'type': 'data',
                    'symmetric': False,
                    'array': [pooled_or - pooled_ci[0]],
                    'arrayminus': [pooled_ci[1] - pooled_or]
                },
                'name': 'MH汇总OR'
            })
        
        layout = {
            'title': '分层分析森林图',
            'xaxis': {
                'title': '比值比 (OR)',
                'type': 'log',
                'range': [np.log10(0.1), np.log10(10)],
                'zeroline': False
            },
            'yaxis': {'title': '分层'},
            'shapes': [{
                'type': 'line',
                'x0': 1, 'y0': -0.5,
                'x1': 1, 'y1': len(strata_results) + 0.5,
                'line': {'color': '#333', 'dash': 'dash'}
            }],
            'margin': {'l': 100, 'r': 50},
            'showlegend': True
        }
        
        return {'data': data, 'layout': layout}