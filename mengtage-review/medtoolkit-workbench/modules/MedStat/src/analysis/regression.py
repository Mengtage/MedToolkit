"""
回归分析模块
基于statsmodels设计的统计分析功能
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Union, Tuple
import traceback

try:
    import statsmodels.api as sm
    import statsmodels.formula.api as smf
    from statsmodels.discrete.discrete_model import Logit, Probit, MNLogit
    from statsmodels.stats.diagnostic import (
        het_breuschpagan, het_white, lilliefors, acorr_ljungbox,
        normal_ad, breaks_hansen, recursive_olsresiduals
    )
    from scipy import stats as scipy_stats
    from scipy.stats import shapiro, kstest, normaltest
    STATSMODELS_AVAILABLE = True
except ImportError:
    STATSMODELS_AVAILABLE = False


class FormulaParser:
    """R风格公式解析器（简化版）"""

    @staticmethod
    def parse_formula(formula: str, df: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray, List[str]]:
        """
        解析R风格公式

        参数:
            formula: 如 'y ~ x1 + x2 + C(group)'
            df: DataFrame

        返回:
            (y, X, var_names)
        """
        import re

        if '~' not in formula:
            raise ValueError("公式必须包含 ~ 分隔符")

        parts = formula.split('~')
        if len(parts) != 2:
            raise ValueError("公式格式错误，应为 'y ~ x1 + x2'")

        y_var = parts[0].strip()
        x_part = parts[1].strip()

        if y_var not in df.columns:
            raise ValueError(f"结果变量 '{y_var}' 不在数据中")

        # This helper returns a predictor matrix without an intercept.
        # Build derived columns explicitly rather than looking them up in df.
        columns = {}

        def numeric(name):
            if name not in df.columns:
                raise ValueError(f"变量 '{name}' 不在数据中")
            values = pd.to_numeric(df[name], errors='raise').to_numpy(dtype=float)
            if not np.all(np.isfinite(values)):
                raise ValueError('简化公式解析器要求完整有限数值；须先明确缺失处理规则')
            return values

        def add(name, values):
            if name not in columns:
                columns[name] = np.asarray(values, dtype=float)

        for term in x_part.split('+'):
            term = term.strip()
            if not term:
                raise ValueError('公式包含空项')
            category = re.fullmatch(r'C\(([^()]+)\)', term)
            power = re.fullmatch(r'I\(([^()]+?)\s*\*\*\s*(\d+)\)', term)
            if category:
                name = category.group(1).strip()
                if name not in df.columns:
                    raise ValueError(f"变量 '{name}' 不在数据中")
                if df[name].isna().any():
                    raise ValueError('分类变量含缺失值，须先明确缺失处理规则')
                dummies = pd.get_dummies(df[name], prefix=name, drop_first=True, dtype=float)
                for col in dummies.columns:
                    if col in df.columns:
                        raise ValueError('分类编码列名与原始变量冲突')
                    add(col, dummies[col])
            elif power:
                name, exponent = power.group(1).strip(), int(power.group(2))
                if exponent > 10:
                    raise ValueError('简化解析器仅支持0至10的整数幂')
                with np.errstate(over='ignore', invalid='ignore'):
                    values = numeric(name) ** exponent
                if not np.all(np.isfinite(values)):
                    raise ValueError('幂运算得到非有限数值')
                add(f'{name}**{exponent}', values)
            elif '*' in term or ':' in term:
                separator = '*' if '*' in term else ':'
                parts = [v.strip() for v in term.split(separator)]
                if len(parts) != 2 or any(not v for v in parts):
                    raise ValueError('简化解析器仅支持两个原始数值变量的交互')
                left, right = parts
                a, b = numeric(left), numeric(right)
                if separator == '*':
                    add(left, a)
                    add(right, b)
                product = a * b
                if not np.all(np.isfinite(product)):
                    raise ValueError('交互项得到非有限数值')
                add(f'{left}:{right}', product)
            else:
                add(term, numeric(term))

        y = numeric(y_var)
        X_vars = list(columns)
        X = np.column_stack(list(columns.values())) if columns else np.empty((len(df), 0))
        return y, X, X_vars

    @staticmethod
    def create_formula_from_vars(dependent: str, independents: List[str],
                                  interaction: Optional[str] = None) -> str:
        """
        根据变量列表创建公式

        参数:
            dependent: 因变量
            independents: 自变量列表
            interaction: 交互项变量对，如 'x1:x2'

        返回:
            R风格公式字符串
        """
        formula = f"{dependent} ~ {' + '.join(independents)}"
        if interaction:
            formula += f" + {interaction}"
        return formula


class LinearRegressionAnalyzer:
    """OLS线性回归分析器"""

    def __init__(self, df: pd.DataFrame, var_types: Dict[str, str] = None):
        self.df = df
        self.var_types = var_types or {}
        self.model = None
        self.results = None

    def fit_ols(self, formula: str = None, y_var: str = None, X_vars: List[str] = None,
                add_constant: bool = True) -> Dict:
        """
        拟合OLS线性回归模型

        参数:
            formula: R风格公式，如 'y ~ x1 + x2 + C(group)'
            y_var: 因变量名（如果不用formula）
            X_vars: 自变量列表（如果不用formula）
            add_constant: 是否添加常数项

        返回:
            包含回归结果的字典
        """
        if not STATSMODELS_AVAILABLE:
            return {'error': 'statsmodels未安装，请运行: pip install statsmodels'}

        try:
            if formula:
                self.model = smf.ols(formula, data=self.df)
                self.results = self.model.fit()
            elif y_var and X_vars:
                y = self.df[y_var].values
                X = self.df[X_vars].values
                if add_constant:
                    X = sm.add_constant(X)
                self.model = sm.OLS(y, X)
                self.results = self.model.fit()
            else:
                return {'error': '需要提供formula或(y_var, X_vars)'}

            return self._format_results()

        except Exception as e:
            traceback.print_exc()
            return {'error': str(e)}

    def _format_results(self) -> Dict:
        """格式化回归结果"""
        if self.results is None:
            return {'error': '模型未拟合'}

        result = {
            'success': True,
            'coefficients': {},
            'std_errors': {},
            't_values': {},
            'p_values': {},
            'conf_int_lower': {},
            'conf_int_upper': {},
            'rsquared': float(self.results.rsquared),
            'rsquared_adj': float(self.results.rsquared_adj),
            'fvalue': float(self.results.fvalue),
            'f_pvalue': float(self.results.f_pvalue),
            'aic': float(self.results.aic),
            'bic': float(self.results.bic),
            'log_likelihood': float(self.results.llf),
            'df_resid': int(self.results.df_resid),
            'df_model': int(self.results.df_model),
            'n_obs': int(self.results.nobs),
            'residuals': self.results.resid.tolist(),
            'fittedvalues': self.results.fittedvalues.tolist(),
        }

        params = self.results.params
        if isinstance(params, np.ndarray):
            var_names = [f'x{i}' for i in range(len(params))]
        else:
            var_names = params.index.tolist()

        conf_int = self.results.conf_int()
        for i, name in enumerate(var_names):
            if isinstance(params, np.ndarray):
                result['coefficients'][name] = float(params[i])
                result['std_errors'][name] = float(self.results.bse[i])
                result['t_values'][name] = float(self.results.tvalues[i])
                result['p_values'][name] = float(self.results.pvalues[i])
                result['conf_int_lower'][name] = float(conf_int[i, 0])
                result['conf_int_upper'][name] = float(conf_int[i, 1])
            else:
                result['coefficients'][name] = float(params.iloc[i])
                result['std_errors'][name] = float(self.results.bse.iloc[i])
                result['t_values'][name] = float(self.results.tvalues.iloc[i])
                result['p_values'][name] = float(self.results.pvalues.iloc[i])
                result['conf_int_lower'][name] = float(conf_int.iloc[i, 0])
                result['conf_int_upper'][name] = float(conf_int.iloc[i, 1])

        return result

    def predict(self, X_new: pd.DataFrame = None, formula: str = None) -> np.ndarray:
        """预测新数据"""
        if self.results is None:
            raise ValueError("模型未拟合")

        if formula and X_new is not None:
            return self.results.predict(X_new)
        elif X_new is not None:
            return self.results.predict(sm.add_constant(X_new))
        else:
            return self.results.fittedvalues


class LogisticRegressionAnalyzer:
    """Logistic回归分析器"""

    def __init__(self, df: pd.DataFrame, var_types: Dict[str, str] = None):
        self.df = df
        self.var_types = var_types or {}
        self.model = None
        self.results = None

    def fit_logit(self, formula: str = None, y_var: str = None, X_vars: List[str] = None,
                  add_constant: bool = True) -> Dict:
        """
        拟合Logistic回归模型

        参数:
            formula: R风格公式
            y_var: 因变量名
            X_vars: 自变量列表
            add_constant: 是否添加常数项

        返回:
            包含回归结果的字典
        """
        if not STATSMODELS_AVAILABLE:
            return {'error': 'statsmodels未安装，请运行: pip install statsmodels'}

        try:
            if formula:
                self.model = smf.logit(formula, data=self.df)
                self.results = self.model.fit(disp=0)
            elif y_var and X_vars:
                y = self.df[y_var].values
                X = self.df[X_vars].values
                if add_constant:
                    X = sm.add_constant(X)
                self.model = Logit(y, X)
                self.results = self.model.fit(disp=0)
            else:
                return {'error': '需要提供formula或(y_var, X_vars)'}

            return self._format_results()

        except Exception as e:
            traceback.print_exc()
            return {'error': str(e)}

    def _format_results(self) -> Dict:
        """格式化Logistic回归结果"""
        if self.results is None:
            return {'error': '模型未拟合'}

        params = self.results.params
        odds_ratios = np.exp(params)

        result = {
            'success': True,
            'coefficients': {},
            'odds_ratios': {},
            'std_errors': {},
            'z_values': {},
            'p_values': {},
            'conf_int_lower': {},
            'conf_int_upper': {},
            'aic': float(self.results.aic),
            'bic': float(self.results.bic),
            'log_likelihood': float(self.results.llf),
            'pseudo_r2': float(self.results.prsquared),
            'n_obs': int(self.results.nobs),
            'df_model': int(self.results.df_model),
            'residuals': self.results.resid.tolist() if hasattr(self.results, 'resid') else [],
        }

        if isinstance(params, np.ndarray):
            var_names = [f'x{i}' for i in range(len(params))]
        else:
            var_names = params.index.tolist()

        conf_int = self.results.conf_int()
        for i, name in enumerate(var_names):
            if isinstance(params, np.ndarray):
                result['coefficients'][name] = float(params[i])
                result['odds_ratios'][name] = float(odds_ratios[i])
                result['std_errors'][name] = float(self.results.bse[i])
                result['z_values'][name] = float(self.results.tvalues[i])
                result['p_values'][name] = float(self.results.pvalues[i])
                result['conf_int_lower'][name] = float(conf_int[i, 0])
                result['conf_int_upper'][name] = float(conf_int[i, 1])
            else:
                result['coefficients'][name] = float(params.iloc[i])
                result['odds_ratios'][name] = float(odds_ratios.iloc[i])
                result['std_errors'][name] = float(self.results.bse.iloc[i])
                result['z_values'][name] = float(self.results.tvalues.iloc[i])
                result['p_values'][name] = float(self.results.pvalues.iloc[i])
                result['conf_int_lower'][name] = float(conf_int.iloc[i, 0])
                result['conf_int_upper'][name] = float(conf_int.iloc[i, 1])

        return result

    def marginal_effects(self) -> Dict:
        """计算边际效应"""
        if self.results is None:
            return {'error': '模型未拟合'}

        try:
            marginal = self.results.get_margeff()
            return {
                'success': True,
                'margeff': marginal.params.to_dict(),
                'margeff_se': marginal.bse.to_dict(),
                'margeff_pvalues': marginal.pvalues.to_dict(),
                'margeff_conf_int': marginal.conf_int().to_dict() if hasattr(marginal, 'conf_int') else {}
            }
        except Exception as e:
            return {'error': str(e)}

    def predict_proba(self, X_new: pd.DataFrame = None) -> np.ndarray:
        """预测新数据的概率"""
        if self.results is None:
            raise ValueError("模型未拟合")

        if X_new is not None:
            return self.results.predict(X_new)
        return self.results.fittedvalues


class GLMAnalyzer:
    """广义线性模型分析器"""

    def __init__(self, df: pd.DataFrame, var_types: Dict[str, str] = None):
        self.df = df
        self.var_types = var_types or {}
        self.model = None
        self.results = None

    def _prepare_xy(self, y_var: str, X_vars: List[str]):
        """构造带列名的 y/X，保证 GLM 结果可按变量名序列化。

        非数值预测变量自动做哑变量编码（参照组为排序后的第一个水平，
        与 patsy 的 C() 默认处理一致）。
        """
        columns = [y_var] + list(X_vars)
        missing = [c for c in columns if c not in self.df.columns]
        if missing:
            raise ValueError(f"数据中缺少列: {', '.join(missing)}")
        data = self.df[columns].dropna()
        if data.empty:
            raise ValueError('剔除缺失值后没有可用样本')
        try:
            y = data[y_var].astype(float)
        except (TypeError, ValueError) as error:
            raise ValueError(f'因变量 {y_var} 必须是数值型: {error}')

        X_df = data[list(X_vars)]
        non_numeric = [c for c in X_vars
                       if not pd.api.types.is_numeric_dtype(X_df[c])]
        if non_numeric:
            X_df = pd.get_dummies(
                X_df, columns=non_numeric, drop_first=True, dtype=float)
        try:
            X_df = X_df.astype(float)
        except (TypeError, ValueError) as error:
            raise ValueError(f'预测变量必须可转换为数值型: {error}')
        X = sm.add_constant(X_df, has_constant='add')
        return y, X

    def fit_poisson(self, formula: str = None, y_var: str = None, X_vars: List[str] = None) -> Dict:
        """拟合Poisson回归（计数数据）"""
        if not STATSMODELS_AVAILABLE:
            return {'error': 'statsmodels未安装'}

        try:
            if formula:
                self.model = smf.poisson(formula, data=self.df)
            elif y_var and X_vars:
                y, X = self._prepare_xy(y_var, X_vars)
                self.model = sm.GLM(y, X, family=sm.families.Poisson())
            else:
                return {'error': '需要提供formula或(y_var, X_vars)'}

            self.results = self.model.fit()
            return self._format_glm_results()

        except Exception as e:
            return {'error': str(e)}

    def fit_gamma(self, formula: str = None, y_var: str = None, X_vars: List[str] = None) -> Dict:
        """拟合Gamma回归（正偏连续数据）"""
        if not STATSMODELS_AVAILABLE:
            return {'error': 'statsmodels未安装'}

        try:
            if formula:
                self.model = smf.glm(formula, data=self.df, family=sm.families.Gamma())
            elif y_var and X_vars:
                y, X = self._prepare_xy(y_var, X_vars)
                self.model = sm.GLM(y, X, family=sm.families.Gamma())
            else:
                return {'error': '需要提供formula或(y_var, X_vars)'}

            self.results = self.model.fit()
            return self._format_glm_results()

        except Exception as e:
            return {'error': str(e)}

    @staticmethod
    def _as_named_dict(values, names: List[str]) -> Dict[str, float]:
        """兼容 Series 与 ndarray 的参数序列化。"""
        if hasattr(values, 'to_dict'):
            return {str(k): float(v) for k, v in values.to_dict().items()}
        array = np.asarray(values, dtype=float).ravel()
        if len(names) != len(array):
            names = [f'x{i}' for i in range(len(array))]
        return {str(name): float(value) for name, value in zip(names, array)}

    def _format_glm_results(self) -> Dict:
        """格式化GLM结果"""
        if self.results is None:
            return {'error': '模型未拟合'}

        names = list(getattr(self.model, 'exog_names', []) or [])
        # statsmodels 的 .bic 基于 deviance 并触发 FutureWarning；
        # 发表级惯例使用对数似然版本的 BIC。
        bic_attr = getattr(self.results, 'bic_llf', None)
        bic = float(bic_attr) if bic_attr is not None else float(self.results.bic)
        result = {
            'success': True,
            'coefficients': self._as_named_dict(self.results.params, names),
            'std_errors': self._as_named_dict(self.results.bse, names),
            't_values': self._as_named_dict(self.results.tvalues, names),
            'p_values': self._as_named_dict(self.results.pvalues, names),
            'aic': float(self.results.aic),
            'bic': bic,
            'bic_method': 'log_likelihood',
            'log_likelihood': float(self.results.llf),
            'deviance': float(self.results.deviance),
            'pearson_chi2': float(self.results.pearson_chi2),
            'n_obs': int(self.results.nobs),
        }

        return result


class RegressionDiagnostics:
    """回归诊断工具"""

    def __init__(self, residuals: np.ndarray, fitted_values: np.ndarray,
                 X: np.ndarray = None, var_names: List[str] = None):
        self.residuals = np.array(residuals)
        self.fitted_values = np.array(fitted_values)
        self.X = X
        self.var_names = var_names or [f'x{i}' for i in range(X.shape[1])] if X is not None else []

    def normality_tests(self) -> Dict:
        """正态性检验"""
        results = {}

        if len(self.residuals) < 5000:
            stat, p_shapiro = shapiro(self.residuals)
            results['shapiro_wilk'] = {'statistic': float(stat), 'p_value': float(p_shapiro)}
        else:
            stat, p_kstest = kstest(self.residuals, 'norm')
            results['kolmogorov_smirnov'] = {'statistic': float(stat), 'p_value': float(p_kstest)}

        stat, p_jb = normal_ad(self.residuals)
        results['anderson_darling'] = {'statistic': float(stat), 'p_value': float(p_jb)}

        stat, p_lillie = lilliefors(self.residuals)
        results['lilliefors'] = {'statistic': float(stat), 'p_value': float(p_lillie)}

        return results

    def heteroskedasticity_tests(self) -> Dict:
        """异方差性检验"""
        results = {}

        if self.X is not None:
            bp_stat, bp_pvalue, f_stat, fpvalue = het_breuschpagan(self.residuals, self.X)
            results['breusch_pagan'] = {
                'lm_statistic': float(bp_stat),
                'lm_pvalue': float(bp_pvalue),
                'f_statistic': float(f_stat),
                'f_pvalue': float(fpvalue)
            }

            white_stat, white_pvalue, _, _ = het_white(self.residuals, self.X)
            results['white'] = {
                'statistic': float(white_stat),
                'p_value': float(white_pvalue)
            }

        return results

    def autocorrelation_tests(self, lags: int = 10) -> Dict:
        """自相关检验"""
        lb_result = acorr_ljungbox(self.residuals, lags=lags, return_df=True)

        results = {'ljung_box': {}}
        for lag in range(1, lags + 1):
            results['ljung_box'][f'lag_{lag}'] = {
                'statistic': float(lb_result['lb_stat'].iloc[lag-1]),
                'p_value': float(lb_result['lb_pvalue'].iloc[lag-1])
            }

        from statsmodels.stats.stattools import durbin_watson
        dw = durbin_watson(self.residuals)
        results['durbin_watson'] = float(dw)

        return results

    def influence_statistics(self) -> Dict:
        """影响统计量（杠杆值、Cook距离等）"""
        if self.X is None:
            return {'error': '需要提供X矩阵以计算影响统计量'}

        try:
            influence = self.results.get_influence() if hasattr(self, 'results') else None

            if influence is None:
                from statsmodels.stats.outliers_influence import OLSInfluence
                model = sm.OLS(np.zeros(len(self.residuals)), sm.add_constant(np.ones(len(self.residuals))))
                infl = OLSInfluence(model)
                infl.resid = self.residuals
                infl.fittedvalues = self.fitted_values
            else:
                infl = influence

            results = {
                'leverage': infl.hat_matrix_diag.tolist() if hasattr(infl, 'hat_matrix_diag') else [],
                'cooks_distance': infl.cooks_distance[0].tolist() if hasattr(infl, 'cooks_distance') else [],
                'studentized_residuals': infl.studentized_resid.tolist() if hasattr(infl, 'studentized_resid') else [],
                'dffits': infl.dffits[0].tolist() if hasattr(infl, 'dffits') else [],
            }

            return results

        except Exception as e:
            return {'error': str(e)}

    def residual_plots(self) -> Dict:
        """生成残差图的配置数据"""
        return {
            'fitted_vs_residuals': {
                'data': [{
                    'x': self.fitted_values.tolist(),
                    'y': self.residuals.tolist(),
                    'mode': 'markers',
                    'type': 'scatter',
                    'name': '残差'
                }, {
                    'x': [min(self.fitted_values), max(self.fitted_values)],
                    'y': [0, 0],
                    'mode': 'lines',
                    'line': {'color': 'red', 'dash': 'dash'},
                    'name': '零线'
                }],
                'layout': {
                    'title': '拟合值 vs 残差',
                    'xaxis': {'title': '拟合值'},
                    'yaxis': {'title': '残差'}
                }
            },
            'qq_plot': {
                'data': [{
                    'x': (np.sort(self.residuals) / np.std(self.residuals)).tolist(),
                    'y': (scipy_stats.t.ppf(np.linspace(0.01, 0.99, len(self.residuals)),
                                            df=len(self.residuals)-1)).tolist(),
                    'mode': 'markers',
                    'type': 'scatter',
                    'name': 'Q-Q点'
                }],
                'layout': {
                    'title': 'Q-Q图（正态性检验）',
                    'xaxis': {'title': '理论分位数'},
                    'yaxis': {'title': '样本分位数'}
                }
            }
        }


def compare_models(models: Dict[str, Dict]) -> Dict:
    """
    比较多个回归模型

    参数:
        models: 字典，键为模型名，值为模型结果字典

    返回:
        模型比较表
    """
    comparison = {
        'models': list(models.keys()),
        'rsquared': [],
        'rsquared_adj': [],
        'aic': [],
        'bic': [],
        'log_likelihood': []
    }

    for name, result in models.items():
        if isinstance(result, dict) and result.get('success'):
            comparison['rsquared'].append(result.get('rsquared') or result.get('pseudo_r2'))
            comparison['rsquared_adj'].append(result.get('rsquared_adj', None))
            comparison['aic'].append(result.get('aic'))
            comparison['bic'].append(result.get('bic'))
            comparison['log_likelihood'].append(result.get('log_likelihood'))

    df_comparison = pd.DataFrame(comparison)
    df_comparison['best_aic'] = df_comparison['aic'] == df_comparison['aic'].min()
    df_comparison['best_bic'] = df_comparison['bic'] == df_comparison['bic'].min()

    return df_comparison.to_dict()
