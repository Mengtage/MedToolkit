"""Numeric OLS/logistic adapters; no user-supplied executable formulas."""
import contextlib
import hashlib
import io
import math
import warnings
from .core import canonical

METHODS = ('linear_regression', 'logistic_regression')


def validate(payload):
    import numpy as np
    if set(payload)-{'classification','method','outcome','predictors','rows','_retry_of'}:
        raise ValueError('回归输入包含未允许字段')
    outcome, predictors = payload.get('outcome'), payload.get('predictors')
    if not isinstance(outcome,str) or not outcome.strip() or len(outcome)>100:
        raise ValueError('需指定结果变量')
    if not isinstance(predictors,list) or not 1<=len(predictors)<=20:
        raise ValueError('需要1至20个数值预测变量')
    if any(not isinstance(v,str) or not v.strip() or len(v)>100 or v=='Intercept' for v in predictors):
        raise ValueError('预测变量名称无效，Intercept保留给截距')
    if len(set(predictors))!=len(predictors) or outcome in predictors:
        raise ValueError('预测变量不得重复或包含结果变量')
    rows=payload.get('rows'); columns=[outcome]+predictors
    if not isinstance(rows,list) or not 4<=len(rows)<=10000:raise ValueError('需要4至10000行')
    complete=[]; indices=[]
    for i,row in enumerate(rows):
        if not isinstance(row,dict) or set(row)!=set(columns):raise ValueError('仅允许所选回归变量')
        for name,value in row.items():
            if value is not None and (type(value) not in (int,float) or not math.isfinite(value) or abs(value)>1e50):
                raise ValueError('回归数值须有限且绝对值不超过1e50')
            if name==outcome and payload['method']=='logistic_regression' and value is not None and value not in (0,1):
                raise ValueError('Logistic结果必须编码为0/1')
        if all(row[c] is not None for c in columns):complete.append(row);indices.append(i)
    if len(complete)<=len(predictors)+1:raise ValueError('完整样本不足以保留正的残差自由度')
    if len({r[outcome] for r in complete})<2:raise ValueError('完整样本中的结果变量必须有变异')
    x=np.array([[r[c] for c in predictors] for r in complete],dtype=float)
    scales=np.std(x,axis=0)
    if np.any(scales==0):raise ValueError('预测变量为常量')
    normalized=(x-x.mean(axis=0))/scales
    if np.linalg.matrix_rank(np.column_stack([np.ones(len(x)),normalized]))!=len(predictors)+1:
        raise ValueError('设计矩阵不满秩，不能唯一估计系数')
    return complete,indices


def analyze(store,pid,payload,jid):
    import pandas as pd
    import scipy
    import statsmodels
    from .adapters import module
    complete,indices=validate(payload)
    path='MedStat/src/analysis/regression.py'
    original=module(path,'medstat_regression')
    logistic=payload['method']=='logistic_regression'
    analyzer=(original.LogisticRegressionAnalyzer if logistic else original.LinearRegressionAnalyzer)(pd.DataFrame(complete))
    with warnings.catch_warnings(record=True) as caught, contextlib.redirect_stderr(io.StringIO()):
        warnings.simplefilter('always')
        fit=analyzer.fit_logit if logistic else analyzer.fit_ols
        result=fit(y_var=payload['outcome'],X_vars=payload['predictors'],add_constant=True)
    if not result.get('success'):raise ValueError('回归拟合失败')
    warning_names=[w.category.__name__ for w in caught]
    if logistic and (not analyzer.results.mle_retvals.get('converged',False) or any(n in warning_names for n in ('PerfectSeparationWarning','ConvergenceWarning'))):
        raise ValueError('Logistic未收敛或存在分离，结果不可接受')
    def finite(v):
        if isinstance(v,float) and not math.isfinite(v):raise ValueError('回归结果包含非有限估计')
        if isinstance(v,dict):
            for item in v.values():finite(item)
        elif isinstance(v,list):
            for item in v:finite(item)
    names=['Intercept']+payload['predictors']
    for field in ('coefficients','std_errors','t_values','z_values','p_values','conf_int_lower','conf_int_upper','odds_ratios'):
        if field in result:result[field]={name:result[field][f'x{i}'] for i,name in enumerate(names)}
    if logistic:
        result['fitted_probabilities']=analyzer.predict_proba().tolist()
        result['odds_ratio_ci_lower']={k:math.exp(v) for k,v in result['conf_int_lower'].items()}
        result['odds_ratio_ci_upper']={k:math.exp(v) for k,v in result['conf_int_upper'].items()}
        result['event_value']=1
    finite(result)
    result.update({'method':payload['method'],'outcome':payload['outcome'],'predictors':payload['predictors'],
        'parameter_order':names,'coefficient_ci_scale':'log_odds' if logistic else 'coefficient',
        'input_rows':len(payload['rows']),'complete_rows':len(complete),'excluded_missing_rows':len(payload['rows'])-len(complete),
        'included_row_indices':indices,'row_index_base':0,'missing_policy':'complete_case_selected_variables',
        'classification':payload.get('classification','synthetic'),'llm_calls':0,'source':path,'warnings':warning_names,
        'prediction_scope':'in_sample_fitted_values_not_external_validation',
        'environment':{'pandas':pd.__version__,'scipy':scipy.__version__,'statsmodels':statsmodels.__version__},
        'input_sha256':hashlib.sha256(canonical({k:payload[k] for k in ('rows','outcome','predictors')}).encode()).hexdigest()})
    name=store.save(pid,f'{jid}-statistics.json',result)
    return {'artifact':name,**result}
