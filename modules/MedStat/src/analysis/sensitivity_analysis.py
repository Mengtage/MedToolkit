"""
敏感性分析模块
实现极端假设分析和Tipping Point分析
"""

import pandas as pd
import numpy as np
from scipy import stats
from scipy.stats import norm


class SensitivityAnalyzer:
    """
    敏感性分析器
    评估缺失数据处理对结果的稳健性
    """
    
    @staticmethod
    def extreme_case_analysis(data, outcome_col, group_col, missing_col=None):
        """
        极端假设敏感性分析 - Worst-case/Best-case
        
        Parameters:
        -----------
        data : pd.DataFrame
            数据集
        outcome_col : str
            结局变量
        group_col : str
            分组变量
        missing_col : str
            缺失指示变量（可选）
            
        Returns:
        --------
        dict
            三种场景的分析结果
        """
        # 识别缺失值
        if missing_col is None:
            missing_mask = data[outcome_col].isnull()
        else:
            missing_mask = data[missing_col] == 1
        
        scenarios = {}
        
        # 1. 观察数据分析
        observed_data = data[~missing_mask].copy()
        scenarios['observed'] = {
            'label': '观察数据',
            'n': int(len(observed_data)),
            'missing_n': int(missing_mask.sum()),
            'missing_rate': float(missing_mask.mean()),
            **SensitivityAnalyzer._perform_group_comparison(observed_data, group_col, outcome_col)
        }
        
        # 2. Worst-case分析（缺失均视为不利结局）
        worst_case = data.copy()
        worst_case.loc[missing_mask, outcome_col] = 0
        scenarios['worst_case'] = {
            'label': '最差情况假设',
            'n': int(len(worst_case)),
            'assumption': '所有缺失值均视为结局=0',
            **SensitivityAnalyzer._perform_group_comparison(worst_case, group_col, outcome_col)
        }
        
        # 3. Best-case分析（缺失均视为有利结局）
        best_case = data.copy()
        best_case.loc[missing_mask, outcome_col] = 1
        scenarios['best_case'] = {
            'label': '最佳情况假设',
            'n': int(len(best_case)),
            'assumption': '所有缺失值均视为结局=1',
            **SensitivityAnalyzer._perform_group_comparison(best_case, group_col, outcome_col)
        }
        
        # 4. Missing-at-random分析（MAR假设下的多重插补）
        scenarios['mar'] = {
            'label': 'MAR假设(MICE)',
            'n': int(len(data)),
            'assumption': '缺失与观测数据相关（MAR）',
            'note': '需要调用MICE插补模块'
        }
        
        return scenarios
    
    @staticmethod
    def _perform_group_comparison(data, group_col, outcome_col):
        """执行组间比较"""
        try:
            # 构建2×2表
            group1 = data[data[group_col] == 1]
            group0 = data[data[group_col] == 0]
            
            a = len(group1[group1[outcome_col] == 1])  # 暴露组阳性
            b = len(group1[group1[outcome_col] == 0])  # 暴露组阴性
            c = len(group0[group0[outcome_col] == 1])  # 非暴露组阳性
            d = len(group0[group0[outcome_col] == 0])  # 非暴露组阴性
            
            # 计算OR
            if b > 0 and c > 0:
                or_val = (a * d) / (b * c)
                se_log_or = np.sqrt(1/a + 1/b + 1/c + 1/d)
                z = norm.ppf(0.975)
                or_ci = [
                    float(np.exp(np.log(or_val) - z * se_log_or)),
                    float(np.exp(np.log(or_val) + z * se_log_or))
                ]
            else:
                or_val = np.nan
                or_ci = [None, None]
            
            # 卡方检验
            observed = np.array([[a, b], [c, d]])
            chi2_stat, p_value, _, _ = stats.chi2_contingency(observed)
            
            return {
                'or': float(or_val) if not np.isnan(or_val) else None,
                'or_ci': or_ci,
                'p_value': float(p_value),
                'chi2_statistic': float(chi2_stat),
                'contingency_table': observed.tolist()
            }
        except Exception as e:
            return {'error': str(e)}
    
    @staticmethod
    def tipping_point_analysis(data, outcome_col, group_col, missing_col=None):
        """
        Tipping Point分析 - 确定结果稳健的临界点
        
        Parameters:
        -----------
        data : pd.DataFrame
            数据集
        outcome_col : str
            结局变量
        group_col : str
            分组变量
        missing_col : str
            缺失指示变量（可选）
            
        Returns:
        --------
        dict
            临界点估计和可视化数据
        """
        # 识别试验组和对照组的缺失
        if missing_col is None:
            missing_mask = data[outcome_col].isnull()
        else:
            missing_mask = data[missing_col] == 1
        
        group_mask = data[group_col] == 1
        
        # 试验组和对照组的缺失数
        tx_missing = int((missing_mask & group_mask).sum())
        ctrl_missing = int((missing_mask & ~group_mask).sum())
        
        # 当前效应量
        observed_data = data[~missing_mask]
        current_or = SensitivityAnalyzer._calculate_or(observed_data, group_col, outcome_col)
        
        # 计算tipping point
        # 在alpha=0.05水平下，OR=1为临界点
        tipping_results = []
        
        for tx_assumed_failure in range(0, tx_missing + 1):
            for ctrl_assumed_success in range(0, ctrl_missing + 1):
                # 假设试验组tx_assumed_failure个缺失为失败
                # 假设对照组ctrl_assumed_success个缺失为成功
                adjusted_or = SensitivityAnalyzer._adjust_or_for_missing(
                    observed_data, group_col, outcome_col,
                    tx_assumed_failure, ctrl_assumed_success
                )
                
                if adjusted_or <= 1:
                    tipping_results.append({
                        'tx_failure_assumption': tx_assumed_failure,
                        'ctrl_success_assumption': ctrl_assumed_success,
                        'adjusted_or': adjusted_or,
                        'tipping_probability': SensitivityAnalyzer._calculate_tipping_probability(
                            tx_assumed_failure, tx_missing,
                            ctrl_assumed_success, ctrl_missing
                        )
                    })
        
        # 找到最小临界点
        min_tipping = None
        if tipping_results:
            min_tipping = min(tipping_results, key=lambda x: x['tipping_probability'])
        
        return {
            'current_or': current_or,
            'tx_missing': tx_missing,
            'ctrl_missing': ctrl_missing,
            'tipping_point': min_tipping,
            'is_robust': bool(min_tipping is None or min_tipping['tipping_probability'] < 0.05),
            'all_tipping_points': tipping_results
        }
    
    @staticmethod
    def _calculate_or(data, group_col, outcome_col):
        """计算OR"""
        group1 = data[data[group_col] == 1]
        group0 = data[data[group_col] == 0]
        
        a = len(group1[group1[outcome_col] == 1])
        b = len(group1[group1[outcome_col] == 0])
        c = len(group0[group0[outcome_col] == 1])
        d = len(group0[group0[outcome_col] == 0])
        
        if b > 0 and c > 0:
            return (a * d) / (b * c)
        return np.nan
    
    @staticmethod
    def _adjust_or_for_missing(observed_data, group_col, outcome_col, 
                                tx_failure, ctrl_success):
        """调整OR以考虑缺失值"""
        group1 = observed_data[observed_data[group_col] == 1]
        group0 = observed_data[observed_data[group_col] == 0]
        
        a = len(group1[group1[outcome_col] == 1]) + (0 - tx_failure)  # 试验组阳性
        b = len(group1[group1[outcome_col] == 0]) + tx_failure       # 试验组阴性
        c = len(group0[group0[outcome_col] == 1]) + ctrl_success      # 对照组阳性
        d = len(group0[group0[outcome_col] == 0]) - ctrl_success     # 对照组阴性
        
        if b > 0 and c > 0:
            return (a * d) / (b * c)
        return np.nan
    
    @staticmethod
    def _calculate_tipping_probability(tx_failure, tx_missing, 
                                       ctrl_success, ctrl_missing):
        """计算临界点概率（简化版）"""
        # 假设缺失值随机分布
        if tx_missing == 0 and ctrl_missing == 0:
            return 0.0
        
        # 使用二项分布计算概率
        from scipy.stats import binom
        
        p_tx = binom.pmf(tx_failure, tx_missing, 0.5) if tx_missing > 0 else 1.0
        p_ctrl = binom.pmf(ctrl_success, ctrl_missing, 0.5) if ctrl_missing > 0 else 1.0
        
        return p_tx * p_ctrl
    
    @staticmethod
    def generate_sensitivity_plot(scenarios):
        """生成敏感性分析图表"""
        data = []
        
        scenario_names = ['observed', 'worst_case', 'best_case']
        scenario_labels = ['观察数据', '最差情况', '最佳情况']
        
        or_values = []
        or_cis = []
        
        for name in scenario_names:
            if name in scenarios:
                or_val = scenarios[name].get('or')
                or_ci = scenarios[name].get('or_ci', [None, None])
                
                if or_val is not None:
                    or_values.append(or_val)
                    or_cis.append(or_ci)
        
        data.append({
            'x': scenario_labels[:len(or_values)],
            'y': or_values,
            'type': 'scatter',
            'mode': 'markers',
            'marker': {'size': 15},
            'error_y': {
                'type': 'data',
                'symmetric': False,
                'array': [ci[1] - or_values[i] if ci[1] else 0 for i, ci in enumerate(or_cis)],
                'arrayminus': [or_values[i] - ci[0] if ci[0] else 0 for i, ci in enumerate(or_cis)]
            },
            'name': 'OR值'
        })
        
        layout = {
            'title': '敏感性分析 - 不同假设下的OR值',
            'xaxis': {'title': '假设场景'},
            'yaxis': {
                'title': '比值比 (OR)',
                'type': 'log'
            },
            'shapes': [{
                'type': 'line',
                'x0': -0.5, 'y0': 1,
                'x1': 2.5, 'y1': 1,
                'line': {'color': '#333', 'dash': 'dash'}
            }],
            'margin': {'l': 80, 'r': 50}
        }
        
        return {'data': data, 'layout': layout}