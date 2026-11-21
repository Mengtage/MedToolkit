"""Bounded continuous-data imputation with optional scalar mean pooling."""
import hashlib
import math
import warnings
from .core import canonical


def validate(payload):
    if set(payload)-{'classification','method','rows','variable_types','strategy','n_imputations','max_iter','pool_means','_retry_of'}:
        raise ValueError('插补输入包含未允许字段')
    types=payload.get('variable_types');rows=payload.get('rows')
    if not isinstance(types,dict) or not 2<=len(types)<=10:raise ValueError('需显式指定2至10个连续变量')
    if any(not isinstance(k,str) or not k.strip() or len(k)>100 or v!='numeric_continuous' for k,v in types.items()):
        raise ValueError('当前统一入口仅支持连续数值变量')
    if not isinstance(rows,list) or not 3<=len(rows)<=500:raise ValueError('当前验收支持3至500行')
    strategy=payload.get('strategy');m=payload.get('n_imputations');iterations=payload.get('max_iter')
    if strategy not in ('bayesian_ridge','linear','ridge'):raise ValueError('未知插补策略')
    if type(m) is not int or not 1<=m<=20 or type(iterations) is not int or not 1<=iterations<=50:raise ValueError('插补份数1至20，迭代数1至50')
    if m>1 and strategy!='bayesian_ridge':raise ValueError('linear/ridge仅支持单次插补')
    if type(payload.get('pool_means')) is not bool:raise ValueError('需明确是否合并均值')
    if payload['pool_means'] and m<2:raise ValueError('单次插补不提供多重插补推断')
    for row in rows:
        if not isinstance(row,dict) or set(row)!=set(types):raise ValueError('数据列须与类型字典完全一致')
        if any(v is not None and (type(v) not in (int,float) or not math.isfinite(v) or abs(v)>1e50) for v in row.values()):
            raise ValueError('须为有限数值（绝对值不超过1e50）或null；不猜测缺失码')
    for name in types:
        values=[r[name] for r in rows if r[name] is not None]
        if len(values)<2:raise ValueError('每列至少两个已观测值，不支持全缺失列')
        if len(values)<len(rows) and len(set(values))<2:raise ValueError('缺失列已观测值为常量，当前入口不支持')


def analyze(store,pid,payload,jid):
    import pandas as pd
    import scipy
    import sklearn
    from .adapters import module
    validate(payload)
    source='MedStat/src/analysis/mice_imputation.py'
    df=pd.DataFrame(payload['rows'])
    engine=module(source,'medstat_imputation').MICEImputer(df,payload['variable_types'],
        n_imputations=payload['n_imputations'],max_iter=payload['max_iter'],strategy=payload['strategy'])
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        datasets=engine.impute()
        pooled=engine.pooled_means() if payload['pool_means'] else []
    missing={name:[i for i,row in enumerate(payload['rows']) if row[name] is None] for name in payload['variable_types']}
    had_missing=any(missing.values())
    result={'method':'mice_imputation','classification':'synthetic','llm_calls':0,
        'strategy':payload['strategy'],'requested_imputations':payload['n_imputations'],'actual_imputations':len(datasets),
        'max_iter':payload['max_iter'],'random_seeds':[42+i for i in range(len(datasets))] if had_missing else [],
        'missing_row_indices':missing,'row_index_base':0,'input_rows':len(df),'variable_types':payload['variable_types'],
        'datasets':[data.to_dict(orient='records') for data in datasets],
        'comparison':engine.get_comparison(),'pooled_means':pooled,
        'pooling_status':('pooled_means_only' if pooled else 'not_applicable_no_missing' if not had_missing else 'not_requested'),
        'pooling_scope':'scalar_column_means_only; no regression pooling',
        'warnings':[{'category':w.category.__name__,'message':str(w.message)} for w in caught],
        'source':source,'environment':{'pandas':pd.__version__,'scipy':scipy.__version__,'scikit_learn':sklearn.__version__},
        'input_sha256':hashlib.sha256(canonical({k:payload[k] for k in ('rows','variable_types','strategy','n_imputations','max_iter','pool_means')}).encode()).hexdigest()}
    name=store.save(pid,f'{jid}-statistics.json',result)
    return {'artifact':name,**result}
