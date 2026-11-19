"""Fixed synthetic acceptance checks for missing-data and pooling repairs."""
import importlib.util
import json
from pathlib import Path
import warnings
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
def load(name):
    spec=importlib.util.spec_from_file_location(name,ROOT/'modules/MedStat/src/analysis'/f'{name}.py')
    obj=importlib.util.module_from_spec(spec);spec.loader.exec_module(obj);return obj
qc=load('quality_control');mi=load('mice_imputation')
results=[]
def check(name,fn):
    try:
        detail=fn();results.append({'name':name,'status':'PASS','detail':detail})
    except AssertionError as e:results.append({'name':name,'status':'FAIL','detail':str(e)})
    except Exception as e:results.append({'name':name,'status':'BLOCKED','detail':type(e).__name__+': '+str(e)})
def require(condition,detail):
    assert condition,detail
    return detail

def base():
    return pd.DataFrame({'x':[1,2,3,4,5,6,7,8], 'y':[1.,np.nan,5.,4.,np.nan,8.,9.,7.], 'c':['A','B','A','A','B','B','A','B']})
TYPES={'x':'numeric_continuous','y':'numeric_continuous','c':'categorical'}
def imputer(strategy='bayesian_ridge'):
    return mi.MICEImputer(base(),TYPES,n_imputations=3,max_iter=10,strategy=strategy)

check('native_missing_count',lambda:require(qc.MissingDataAnalyzer(pd.DataFrame({'x':[1.,np.nan,3.]})).analyze()[0]['missing_count']==1,'1/3 native missing counted'))
def dtype_placeholders():
    a=qc.MissingDataAnalyzer(pd.DataFrame({'x':pd.Series(['NA','ok'],dtype=object)})).analyze()[0]['missing_count']
    b=qc.MissingDataAnalyzer(pd.DataFrame({'x':pd.Series(['NA','ok'],dtype='str')})).analyze()[0]['missing_count']
    return require(a==b,{'object_missing':a,'string_missing':b,'expected':'same declared placeholder policy across string dtypes'})
check('placeholder_dtype_consistency',dtype_placeholders)
def matrix_consistency():
    a=qc.MissingDataAnalyzer(pd.DataFrame({'x':pd.Series(['NA','ok'],dtype=object)}))
    n=a.analyze()[0]['missing_count'];matrix=int(a.get_missing_matrix().to_numpy().sum())
    return require(n==matrix,{'reported_missing':n,'heatmap_missing':matrix})
check('missing_summary_matrix_consistency',matrix_consistency)
def sentinel():
    count=qc.MissingDataAnalyzer(pd.DataFrame({'measurement':[999.,2.,3.]})).analyze()[0]['missing_count']
    return require(count==0,{'reported_missing':count,'expected':0,'condition':'999 is a valid measured value; no missing-code dictionary supplied'})
check('valid_numeric_value_not_missing_without_dictionary',sentinel)
a=imputer();datasets=a.impute()
def reproducible():
    other=imputer().impute()
    return require(all(x.equals(y) for x,y in zip(datasets,other)),'same seed sequence yields identical completed datasets')
check('fixed_seed_reproducibility',reproducible)
def observed():
    original=base()
    return require(all(all(d.loc[original[c].notna(),c].equals(original.loc[original[c].notna(),c]) if c=='c' else np.array_equal(d.loc[original[c].notna(),c].values,original.loc[original[c].notna(),c].values) for c in original) for d in datasets),'observed values preserved')
check('observed_values_preserved',observed)
check('complete_categorical_values_preserved',lambda:require(all(set(d.c).issubset({'A','B'}) for d in datasets),'all completed categorical values belong to observed categories in this fixture'))
check('posterior_draws_vary',lambda:require(not datasets[0].equals(datasets[1]),'posterior draws produce different imputations'))
def linear_diversity():
    try:imputer('linear').impute()
    except ValueError:return 'linear多次插补被明确拒绝；不再输出重复数据冒充MI'
    return require(False,'unsupported deterministic multiple imputation accepted')
check('linear_multiple_imputation_uncertainty',linear_diversity)
def empty_feature():
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            mi.MICEImputer(pd.DataFrame({'x':[1.,2.,3.],'y':[np.nan]*3}),{'x':'numeric_continuous','y':'numeric_continuous'},n_imputations=3).impute()
    except ValueError:return 'all-missing column rejected with ValueError'
    except Exception as e:return require(False,{'actual_error':type(e).__name__,'expected':'explicit unsupported-column validation, not indexing crash'})
    return require(False,'all-missing column silently accepted')
check('all_missing_column_validation',empty_feature)
def moments():
    obj=mi.MICEImputer(pd.DataFrame({'x':range(20)}),{'x':'numeric_continuous'})
    obj.imputed_datasets=[pd.DataFrame({'estimate':[e],'variance':[v]}) for e,v in [(1.,.25),(2.,.25),(3.,.25)]]
    out=obj.pool_results(lambda d:(d.estimate.iloc[0],d.variance.iloc[0]))
    expected={'pooled_estimate':2.,'within_variance':.25,'between_variance':1.,'total_variance':.25+4/3}
    return require(all(np.isclose(out[k],v) for k,v in expected.items()),{'actual':out,'expected':expected})
check('rubin_point_and_variance_hand_calculation',moments)
def route(name, frame, settings):
    import ast, os, tempfile, traceback
    from types import SimpleNamespace
    tree=ast.parse((ROOT/'modules/MedStat/app.py').read_text())
    function=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name==name)
    function.decorator_list=[]
    saved={}
    with tempfile.TemporaryDirectory() as tmp:
        env={'session':{'id':'synthetic'},'request':SimpleNamespace(get_json=lambda **k:settings),
             'load_data':lambda _: (frame,TYPES), 'load_result':lambda *a:None,
             'jsonify':lambda x:x,'save_result':lambda sid,k,v:saved.update({k:v}),
             'get_session_dir':lambda _:tmp,'MissingDataAnalyzer':qc.MissingDataAnalyzer,
             'MICEImputer':mi.MICEImputer,'os':os,'np':np,'pd':pd,'traceback':traceback}
        exec(compile(ast.Module(body=[function],type_ignores=[]),'app_route','exec'),env)
        return env[name](),saved

def ui_pool():
    response,_=route('mice_impute',base(),{'n_imputations':3})
    require(isinstance(response,dict) and response.get('success'),response)
    ui=next(r for r in response['rubin_stats'] if r['variable']=='y')
    q=np.array([d.y.mean() for d in datasets]);u=np.array([d.y.var(ddof=1)/len(base()) for d in datasets])
    ref={'q_bar':float(q.mean()),'u_bar':float(u.mean()),'b':float(q.var(ddof=1))}
    return require(all(np.isclose(ui[k],ref[k],rtol=1e-10) for k in ref),{'actual_web_function':ui,'independent_moments':ref})
check('app_rubin_matches_dataset_level_estimates',ui_pool)
def web_mask():
    response,_=route('missing_analysis',pd.DataFrame({'value':['NA','ok',None]}),{})
    stats=response['results']['stats'][0]
    count=sum(sum(row) for row in response['results']['heatmap']['data'][0]['z'])
    return require(stats['missing_count']==count==2,{'summary':stats['missing_count'],'matrix':count})
check('actual_web_missing_summary_and_heatmap',web_mask)
def declared_code():
    analyzer=qc.MissingDataAnalyzer(pd.DataFrame({'v':[999.,2.,3.]}),{'v':[999]})
    return require(analyzer.analyze()[0]['missing_count']==1 and analyzer.normalized_data().v.isna().sum()==1,'explicit numeric dictionary applied')
check('explicit_numeric_missing_code',declared_code)
def categorical_rejection():
    data=base();data.loc[[2,5],'c']=None  # Exact original missing-category fixture
    try:mi.MICEImputer(data,TYPES,n_imputations=3).impute()
    except ValueError:return 'categorical missing outcome rejected pending dedicated categorical MI model'
    return require(False,'categorical regression rounding still enabled')
check('unsupported_categorical_missing_rejected',categorical_rejection)
def failed_fit():
    obj=imputer();obj.imputed_datasets=[pd.DataFrame({'x':[1]}),pd.DataFrame({'x':[2]})]
    def fit(d):
        if d.x.iloc[0]==2:raise ValueError('synthetic failure')
        return 1.,.2
    try:obj.pool_results(fit)
    except ValueError:return 'one failed analysis aborts pool; no silent deletion'
    return require(False,'partial pooling silently accepted')
check('failed_imputation_analysis_not_omitted',failed_fit)
def br_df():
    obj=imputer();obj.imputed_datasets=[pd.DataFrame({'estimate':[e],'variance':[v]}) for e,v in [(1.,.25),(2.,.25),(3.,.25)]]
    out=obj.pool_results(lambda d:(d.estimate.iloc[0],d.variance.iloc[0]),df_complete=19)
    lam=(4/3)/(.25+4/3);old=2/lam**2;observed=20/22*19*(1-lam)
    df=old*observed/(old+observed)
    return require(np.isclose(out['degrees_of_freedom'],df),{'actual_df':out['degrees_of_freedom'],'Barnard_Rubin_hand_formula':df})
check('barnard_rubin_degrees_of_freedom',br_df)
def no_missing():
    response,_=route('mice_impute',base().fillna({'y':2.}),{'n_imputations':3})
    require(response['success'],response)
    return require(response['rubin_stats']==[] and response['inference_status']=='single_completed_dataset_no_mi_inference',response['inference_status'])
check('no_missing_data_not_claimed_multiple_imputation',no_missing)
check('strict_json_outputs',lambda:require(bool(json.dumps(a.pooled_means(),allow_nan=False)),'finite JSON mean pooling'))
def web_unsupported_status():
    response,_=route('mice_impute',base(),{'strategy':'linear','n_imputations':3})
    return require(isinstance(response,tuple) and response[1]==400 and 'linear/ridge' in response[0]['error'],response)
check('web_unsupported_multiple_imputation_status_400',web_unsupported_status)
def web_all_missing_status():
    data=base();data['y']=np.nan
    response,_=route('mice_impute',data,{'n_imputations':3})
    return require(isinstance(response,tuple) and response[1]==400 and '全缺失' in response[0]['error'],response)
check('web_all_missing_status_400',web_all_missing_status)
output={'scope':'repaired missing-data and numeric-only MI; actual app function extracted with mocked session/storage; synthetic inputs only','pandas':pd.__version__,'numpy':np.__version__,'results':results,'counts':{s:sum(r['status']==s for r in results) for s in ['PASS','FAIL','BLOCKED']}}
(ROOT/'reports/acceptance-missing.json').write_text(json.dumps(output,ensure_ascii=False,indent=2))
print(json.dumps(output,ensure_ascii=False,indent=2))

raise SystemExit(1 if any(row['status'] != 'PASS' for row in results) else 0)
