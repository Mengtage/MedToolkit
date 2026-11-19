"""
交互作用分析模块
实现交互效应检验和可视化
"""

import pandas as pd
import numpy as np
from scipy import stats
from scipy.stats import chi2


class InteractionAnalyzer:
    """
    交互作用分析器
    评估变量间的交互效应
    """
    
    @staticmethod
    def analyze(data, var1, var2, outcome, model_type='logistic'):
        """
        交互作用分析
        
        Parameters:
        -----------
        data : pd.DataFrame
            数据集
        var1 : str
            主变量（如：处理组）
        var2 : str
            调节变量（如：年龄组）
        outcome : str
            结局变量
        model_type : str
            模型类型('logistic', 'linear')
            
        Returns:
        --------
        dict
            交互效应检验结果
        """
        try:
            import statsmodels.api as sm
            import statsmodels.formula.api as smf
        except ImportError:
            return {'error': '需要安装statsmodels库'}
        
        # 创建交互项
        data = data.dropna(subset=[var1, var2, outcome]).copy()
        data['interaction'] = data[var1] * data[var2]
        
        # 主效应模型
        main_formula = f"{outcome} ~ {var1} + {var2}"
        interaction_formula = f"{outcome} ~ {var1} + {var2} + interaction"
        
        if model_type == 'logistic':
            main_model = smf.glm(main_formula, data=data, family=sm.families.Binomial()).fit()
            interaction_model = smf.glm(interaction_formula, data=data, family=sm.families.Binomial()).fit()
        elif model_type == 'linear':
            main_model = smf.ols(main_formula, data=data).fit()
            interaction_model = smf.ols(interaction_formula, data=data).fit()
        else:
            return {'error': f'不支持的模型类型: {model_type}'}
        
        # 似然比检验
        lr_statistic = -2 * (main_model.llf - interaction_model.llf)
        df_diff = 1  # 交互项自由度
        lr_p_value = chi2.sf(lr_statistic, df=df_diff)
        
        # 获取交互项系数
        interaction_coef = interaction_model.params.get('interaction', 0)
        interaction_se = interaction_model.bse.get('interaction', 1)
        
        # 计算交互效应的OR/RR
        if model_type == 'logistic':
            interaction_or = np.exp(interaction_coef)
            interaction_or_ci = np.exp([interaction_coef - 1.96 * interaction_se,
                                         interaction_coef + 1.96 * interaction_se])
        else:
            interaction_or = None
            interaction_or_ci = None
        
        return {
            'method': '交互作用分析（似然比检验）',
            'var1': var1,
            'var2': var2,
            'outcome': outcome,
            'model_type': model_type,
            'lr_statistic': float(lr_statistic),
            'lr_p_value': float(lr_p_value),
            'has_interaction': bool(lr_p_value < 0.05),
            'interaction_coef': float(interaction_coef),
            'interaction_se': float(interaction_se),
            'interaction_p': float(interaction_model.pvalues.get('interaction', 1)),
            'interaction_or': float(interaction_or) if interaction_or else None,
            'interaction_or_ci': [float(x) for x in interaction_or_ci] if interaction_or_ci is not None else None,
            'main_model_llf': float(main_model.llf),
            'interaction_model_llf': float(interaction_model.llf),
            'main_model_aic': float(main_model.aic),
            'interaction_model_aic': float(interaction_model.aic)
        }
    
    @staticmethod
    def generate_interaction_plot(data, var1, var2, outcome):
        """
        生成交互作用图
        
        Parameters:
        -----------
        data : pd.DataFrame
            数据集
        var1 : str
            主变量
        var2 : str
            调节变量
        outcome : str
            结局变量
            
        Returns:
        --------
        dict
            Plotly图表配置
        """
        # 计算各组均值/比例
        grouped = data.groupby([var1, var2])[outcome].agg(['mean', 'count']).reset_index()
        
        # 获取唯一值
        var1_values = sorted(data[var1].unique())
        var2_values = sorted(data[var2].unique())
        
        data_traces = []
        for v1 in var1_values:
            subset = grouped[grouped[var1] == v1]
            data_traces.append({
                'x': subset[var2].tolist(),
                'y': subset['mean'].tolist(),
                'type': 'scatter',
                'mode': 'lines+markers',
                'name': f"{var1}={v1}",
                'error_y': {
                    'array': [InteractionAnalyzer._calculate_binomial_se(p, n) 
                             for p, n in zip(subset['mean'], subset['count'])],
                    'visible': True
                }
            })
        
        layout = {
            'title': f'{var1}与{var2}的交互作用',
            'xaxis': {'title': var2},
            'yaxis': {'title': f'{outcome} 比例', 'range': [0, 1]},
            'legend': {'title': var1},
            'annotations': [{
                'x': 0.5, 'y': -0.15,
                'xanchor': 'center', 'yanchor': 'top',
                'text': '平行线表示无交互作用，交叉线表示存在交互作用',
                'showarrow': False,
                'font': {'size': 10}
            }]
        }
        
        return {'data': data_traces, 'layout': layout}
    
    @staticmethod
    def _calculate_binomial_se(p, n):
        """计算二项比例的标准误"""
        if n == 0:
            return 0
        return np.sqrt(p * (1 - p) / n)
    
    @staticmethod
    def stratified_analysis(data, var1, var2, outcome):
        """
        分层交互作用分析
        按var2分层，分析var1对outcome的效应
        
        Parameters:
        -----------
        data : pd.DataFrame
            数据集
        var1 : str
            主变量
        var2 : str
            分层变量
        outcome : str
            结局变量
            
        Returns:
        --------
        dict
            分层分析结果
        """
        strata_results = []
        
        for stratum in data[var2].unique():
            stratum_data = data[data[var2] == stratum]
            
            # 构建2×2表
            group1 = stratum_data[stratum_data[var1] == 1]
            group0 = stratum_data[stratum_data[var1] == 0]
            
            a = len(group1[group1[outcome] == 1])
            b = len(group1[group1[outcome] == 0])
            c = len(group0[group0[outcome] == 1])
            d = len(group0[group0[outcome] == 0])
            
            # 计算OR
            if b > 0 and c > 0:
                or_val = (a * d) / (b * c)
                se_log_or = np.sqrt(1/a + 1/b + 1/c + 1/d)
                from scipy.stats import norm
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
            
            strata_results.append({
                'stratum': stratum,
                'a': int(a), 'b': int(b), 'c': int(c), 'd': int(d),
                'or': float(or_val) if not np.isnan(or_val) else None,
                'or_ci': or_ci,
                'p_value': float(p_value),
                'chi2_statistic': float(chi2_stat)
            })
        
        return {
            'strata': strata_results,
            'n_strata': len(strata_results)
        }