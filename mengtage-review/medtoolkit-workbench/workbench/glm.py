"""Poisson/log and Gamma/inverse GLM, preserving the legacy family defaults."""
import hashlib
import math
import warnings
from .core import canonical

METHODS=('poisson_regression','gamma_regression')


def validate(payload):
    from .regression import validate as numeric_validate
    complete,indices=numeric_validate(payload)
    if 'const' in payload['predictors']:raise ValueError('const保留给GLM截距')
    for row in payload['rows']:
        y=row[payload['outcome']]
        if y is None:continue
        if payload['method']=='poisson_regression' and (y<0 or y!=int(y)):
            raise ValueError('Poisson结果须为非负整数计数')
        if payload['method']=='gamma_regression' and y<=0:
            raise ValueError('Gamma结果必须严格大于零')
    return complete,indices


def analyze(store,pid,payload,jid):
    import pandas as pd
    import scipy
    import statsmodels
    from .adapters import module
    complete,indices=validate(payload)
    source='MedStat/src/analysis/regression.py'
    model=module(source,'medstat_glm').GLMAnalyzer(pd.DataFrame(complete))
    poisson=payload['method']=='poisson_regression'
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        result=(model.fit_poisson if poisson else model.fit_gamma)(y_var=payload['outcome'],X_vars=payload['predictors'])
    warning_names=[w.category.__name__ for w in caught]
    if not result.get('success') or not getattr(model.results,'converged',False) or any(x in warning_names for x in ('PerfectSeparationWarning','ConvergenceWarning')):
        raise ValueError('GLM拟合失败、未收敛或参数不可估计')
    names=['Intercept']+payload['predictors']
    keys=['const']+payload['predictors']
    for field in ('coefficients','std_errors','t_values','p_values'):
        result[field]={name:result[field][key] for name,key in zip(names,keys)}
    intervals=model.results.conf_int().to_numpy()
    result['conf_int_lower']={name:float(intervals[i,0]) for i,name in enumerate(names)}
    result['conf_int_upper']={name:float(intervals[i,1]) for i,name in enumerate(names)}
    means=model.results.predict().tolist()
    if any(not math.isfinite(v) or v<=0 for v in means):raise ValueError('GLM预测均值超出正值定义域')
    result.update({'fitted_means':means,'dispersion_scale':float(model.results.scale),'df_resid':int(model.results.df_resid),
        'family':'Poisson' if poisson else 'Gamma','link':'log' if poisson else 'inverse',
        'coefficient_ci_scale':'log_mean' if poisson else 'inverse_mean','parameter_order':names})
    if poisson:
        result['mean_ratios']={k:math.exp(v) for k,v in result['coefficients'].items()}
    def finite(value):
        if isinstance(value,float) and not math.isfinite(value):raise ValueError('GLM结果包含非有限估计')
        if isinstance(value,dict):
            for v in value.values():finite(v)
        elif isinstance(value,list):
            for v in value:finite(v)
    finite(result)
    result.update({'method':payload['method'],'outcome':payload['outcome'],'predictors':payload['predictors'],
        'input_rows':len(payload['rows']),'complete_rows':len(complete),'excluded_missing_rows':len(payload['rows'])-len(complete),
        'included_row_indices':indices,'row_index_base':0,'missing_policy':'complete_case_selected_variables',
        'classification':'synthetic','llm_calls':0,'source':source,'warnings':warning_names,
        'prediction_scope':'in_sample_fitted_means_not_external_validation','offset':'none','exposure':'none',
        'environment':{'pandas':pd.__version__,'scipy':scipy.__version__,'statsmodels':statsmodels.__version__},
        'input_sha256':hashlib.sha256(canonical({k:payload[k] for k in ('rows','outcome','predictors')}).encode()).hexdigest()})
    name=store.save(pid,f'{jid}-statistics.json',result)
    return {'artifact':name,**result}
