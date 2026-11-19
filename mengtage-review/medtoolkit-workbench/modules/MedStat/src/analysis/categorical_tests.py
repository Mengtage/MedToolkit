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
        observed = np.asarray(observed)
        if observed.ndim != 2 or min(observed.shape) < 2 or not np.isfinite(observed).all() or np.any(observed < 0) or np.any(observed != np.floor(observed)):
            raise ValueError('列联表须为至少2×2的非负整数频数')
        if np.any(observed.sum(axis=0) == 0) or np.any(observed.sum(axis=1) == 0):
            raise ValueError('列联表存在零边际，检验不可估计')
        observed = observed.astype(np.int64)
        if method not in ('auto', 'chi2', 'fisher', 'yates'):
            raise ValueError('未知分类检验方法')
        if method == 'yates' and observed.shape != (2, 2):
            raise ValueError('Yates矫正仅支持2×2表')
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
            'reason': f'Pearson渐近卡方；最小期望频数={min_expected:.2f}，请核对适用条件',
            'recommended': bool(min_expected >= 1 and np.mean(expected < 5) <= .2)
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
                'statistic': float(odds_ratio) if np.isfinite(odds_ratio) else None,
                'odds_ratio_boundary': bool(not np.isfinite(odds_ratio) or odds_ratio == 0),
                'statistic_name': 'OR',
                'p_value': float(p_value),
                'or_ci': CategoricalTestSelector._calculate_or_ci(observed),
                'min_expected': float(min_expected) if min_expected else None,
                'reason': f'总例数<20或期望频数<5的单元格过多',
                'recommended': True
            }
        else:
            # Fixed-margin conditional Monte Carlo; statistic is table probability, not chi-square.
            n_resamples, seed = 19999, 20261119
            if not hasattr(stats, 'MonteCarloMethod'):
                raise ValueError('RxC条件Monte Carlo检验需要SciPy>=1.15')
            method = stats.MonteCarloMethod(n_resamples=n_resamples, rng=np.random.default_rng(seed))
            result = stats.fisher_exact(observed, method=method)
            expected = np.outer(observed.sum(axis=1), observed.sum(axis=0)) / observed.sum()
            return {
                'method': 'Fisher条件Monte Carlo检验',
                'statistic': float(np.asarray(result.statistic).item()),
                'statistic_name': '条件表概率',
                'p_value': float(np.asarray(result.pvalue).item()),
                'expected': expected.tolist(),
                'min_expected': float(expected.min()),
                'reason': 'RxC稀疏表；在固定边际下按表概率比较极端性，P值为模拟估计',
                'recommended': True, 'n_resamples': n_resamples, 'random_seed': seed,
                'p_value_is_approximate': True
            }
    
    @staticmethod
    def _calculate_or_ci(observed, confidence=0.95):
        """计算OR的置信区间"""
        a, b = observed[0, 0], observed[0, 1]
        c, d = observed[1, 0], observed[1, 1]
        
        if min(a, b, c, d) == 0:
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
        from statsmodels.stats.contingency_tables import StratifiedTable
        used = data[[group_col, outcome_col, strata_col]].dropna()
        if used.empty or not used[group_col].isin([0, 1]).all() or not used[outcome_col].isin([0, 1]).all():
            raise ValueError('MH分析需要0/1分组与结局及非缺失分层')
        tables, strata_results = [], []
        for label, frame in used.groupby(strata_col, sort=False):
            table = pd.crosstab(frame[group_col], frame[outcome_col]).reindex(index=[1,0], columns=[1,0], fill_value=0).to_numpy()
            if np.any(table.sum(0) == 0) or np.any(table.sum(1) == 0):
                raise ValueError('分层存在零边际，MH分析不可估计')
            a,b,c,d = table.ravel()
            odds = float(a*d/(b*c)) if b*c else None
            if odds is not None and not np.isfinite(odds): odds = None
            strata_results.append({'stratum': label.item() if isinstance(label,np.generic) else label,
                'a':int(a),'b':int(b),'c':int(c),'d':int(d),'or':odds,
                'or_ci':CategoricalTestSelector._calculate_or_ci(table), 'total':int(table.sum())})
            tables.append(table)
        model = StratifiedTable(tables, shift_zeros=False)
        test = model.test_null_odds(correction=False)
        pooled = float(model.oddsratio_pooled)
        if not np.isfinite(pooled) or pooled <= 0:
            raise ValueError('合并OR位于边界，常规对数区间不可估计')
        interval = [float(v) for v in model.oddsratio_pooled_confint()]
        bd_stat = homogeneity_p = None
        if len(tables) > 1:
            # Stable form of the Breslow-Day quadratic, including common OR=1.
            components = []
            for table in tables:
                a,b,c,d = table.ravel().astype(float)
                row, col, n = a+b, a+c, table.sum()
                qa = 1-pooled
                qb = pooled*(row+col) + d-a
                qc = -pooled*row*col
                expected = -qc/qb if abs(qa) < 1e-12 else 2*qc/(-qb-np.sqrt(qb*qb-4*qa*qc))
                cells = np.array([expected,row-expected,col-expected,n-row-col+expected])
                if np.any(cells <= 0):
                    raise ValueError('Breslow-Day期望频数位于边界，检验不可估计')
                variance = 1/np.sum(1/cells)
                components.append((a-expected)**2/variance)
            bd_stat = float(sum(components))
            homogeneity_p = float(chi2.sf(bd_stat,len(tables)-1))
        return {'method':'Mantel-Haenszel分层分析','strata':strata_results,
            'pooled_or':pooled,'pooled_or_ci':interval,
            'mh_statistic':float(test.statistic),'mh_p_value':float(test.pvalue),
            'homogeneity_statistic':bd_stat,'homogeneity_p':homogeneity_p,
            'has_heterogeneity':bool(homogeneity_p < .05) if homogeneity_p is not None else None,
            'n_strata':len(tables),'input_rows':len(data),'complete_rows':len(used),
            'excluded_missing_rows':len(data)-len(used),'continuity_correction':False,
            'ci_method':'Robins-Breslow-Greenland log-OR variance',
            'homogeneity_method':'Breslow-Day (unadjusted)' if len(tables)>1 else 'not_applicable_single_stratum'}
    
    @staticmethod
    def _calculate_mh_or_ci(strata_results, mh_or):
        from statsmodels.stats.contingency_tables import StratifiedTable
        if mh_or is None or not np.isfinite(mh_or) or mh_or <= 0: return [None,None]
        tables = [np.array([[s['a'],s['b']],[s['c'],s['d']]]) for s in strata_results]
        return [float(v) for v in StratifiedTable(tables,shift_zeros=False).oddsratio_pooled_confint()]

    @staticmethod
    def generate_forest_plot_data(strata_results, pooled_or, pooled_ci):
        """生成森林图数据"""
        data = []
        
        # 分层效应量
        for i, result in enumerate(strata_results):
            interval = result.get('or_ci', [None, None])
            if result['or'] is not None and interval[0] is not None and interval[1] is not None:
                or_lower, or_upper = interval
                
                data.append({
                    'x': [result['or']],
                    'y': [f"分层 {result['stratum']}"],
                    'type': 'scatter',
                    'mode': 'markers',
                    'marker': {'size': 10, 'color': '#1f77b4'},
                    'error_x': {
                        'type': 'data',
                        'symmetric': False,
                        'array': [or_upper - result['or']],
                        'arrayminus': [result['or'] - or_lower]
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
                    'array': [pooled_ci[1] - pooled_or],
                    'arrayminus': [pooled_or - pooled_ci[0]]
                },
                'name': 'MH汇总OR'
            })
        
        layout = {
            'title': '分层分析森林图',
            'xaxis': {
                'title': '比值比 (OR)',
                'type': 'log',
                'autorange': True,
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