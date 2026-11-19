"""Fixed synthetic acceptance checks; never modifies the legacy implementation."""
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
    return pd.DataFrame({'x':[1,2,3,4,5,6,7,8], 'y':[1.,np.nan,5.,4.,np.nan,8.,9.,7.], 'c':['A','B',None,'A','B',None,'A','B']})
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
check('categorical_support',lambda:require(all(set(d.c).issubset({'A','B'}) for d in datasets),'all completed categorical values belong to observed categories in this fixture'))
check('posterior_draws_vary',lambda:require(not datasets[0].equals(datasets[1]),'posterior draws produce different imputations'))
def linear_diversity():
    ds=imputer('linear').impute();return require(not all(ds[0].equals(x) for x in ds[1:]),{'identical_datasets':all(ds[0].equals(x) for x in ds[1:]),'m':len(ds)})
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
def ui_pool():
    row=a.get_comparison()['y'];n=len(base());m=3
    ui={'Q':row['imputed_mean'],'U':row['imputed_std']**2/n,'B':(row['imputed_std']-row['original_std'])**2/m}
    q=np.array([d.y.mean() for d in datasets]);u=np.array([d.y.var(ddof=1)/n for d in datasets]);ref={'Q':float(q.mean()),'U':float(u.mean()),'B':float(q.var(ddof=1))}
    return require(all(np.isclose(ui[k],ref[k],rtol=1e-6,atol=1e-6) for k in ref),{'app_formula':ui,'dataset_level_pooling':ref})
check('app_rubin_matches_dataset_level_estimates',ui_pool)
output={'scope':'legacy missing-data and MICE acceptance; synthetic inputs only','pandas':pd.__version__,'numpy':np.__version__,'results':results,'counts':{s:sum(r['status']==s for r in results) for s in ['PASS','FAIL','BLOCKED']}}
(ROOT/'reports/acceptance-missing.json').write_text(json.dumps(output,ensure_ascii=False,indent=2))
print(json.dumps(output,ensure_ascii=False,indent=2))

raise SystemExit(1 if any(row['status'] != 'PASS' for row in results) else 0)
