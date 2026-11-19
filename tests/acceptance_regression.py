"""Synthetic acceptance probes; records failures without changing upstream code."""
import importlib.util,json,math
from pathlib import Path
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
def load(name):
 p=ROOT/'modules/MedStat/src/analysis'/f'{name}.py';s=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
r=load('regression');e=load('model_evaluation');rows=[]
def check(name,fn,dependency=False):
 if dependency and not r.STATSMODELS_AVAILABLE:rows.append({'case':name,'status':'BLOCKED','detail':'statsmodels unavailable'});return
 try:
  detail=fn();rows.append({'case':name,'status':'PASS','detail':str(detail)})
 except Exception as exc:rows.append({'case':name,'status':'FAIL','detail':f'{type(exc).__name__}: {exc}'})
def close(a,b):assert np.allclose(a,b,rtol=1e-7,atol=1e-7),(a,b)
def ols():
 x=np.arange(1.,9.);y=2+3*x+np.array([1,-1,-1,1,1,-1,-1,1]);df=pd.DataFrame({'x':x,'y':y});o=r.LinearRegressionAnalyzer(df).fit_ols(formula='y ~ x');assert o.get('success'),o;close(list(o['coefficients'].values()),np.linalg.lstsq(np.column_stack([np.ones(8),x]),y,rcond=None)[0]);assert o['n_obs']==8;return o['coefficients']
def logistic():
 # Two binary-x strata with empirical rates 1/4 and 3/4: analytic MLE alpha=-log(3), beta=2log(3).
 df=pd.DataFrame({'x':[0]*8+[1]*8,'y':[1,1,0,0,0,0,0,0,1,1,1,1,1,1,0,0]});o=r.LogisticRegressionAnalyzer(df).fit_logit(formula='y ~ x');assert o.get('success'),o;close(o['coefficients']['Intercept'],-math.log(3));close(o['coefficients']['x'],2*math.log(3));close(o['odds_ratios']['x'],9);assert o['n_obs']==16;return o['coefficients']
def missing():
 df=pd.DataFrame({'x':[0,1,2,3,4,5.],'y':[1,2,np.nan,4,6,5.]});o=r.LinearRegressionAnalyzer(df).fit_ols(formula='y ~ x');assert o.get('success'),o;assert o['n_obs']==5;return 'n_obs=5'
def bad_input():
 o=r.LogisticRegressionAnalyzer(pd.DataFrame({'x':[0,1,2,3],'y':[0,1,2,1]})).fit_logit(formula='y ~ x');assert 'error' in o;return 'invalid binary outcome rejected'
def constant():
 m=e.ModelEvaluator([0,1,0,1],[.8]*4);cm=m.calculate_confusion_matrix();assert cm['TP']==2 and cm['FP']==2,cm;return cm
def counts():
 m=e.ModelEvaluator([0,0,1,1],[.1,.8,.6,.2]);cm=m.calculate_confusion_matrix();assert [cm[k] for k in ['TN','FP','FN','TP']]==[1]*4;close(m.calculate_basic_metrics()['accuracy'],.5);return cm
def auc():
 a=e.ModelEvaluator([0,0,1,1],[.1,.4,.35,.8]).calculate_roc_curve();close(a['auc'],.75);return a['auc']
def calibration_count():
 a=e.ModelEvaluator([0,0,1,1],[0,.2,.8,1]).calculate_calibration_metrics(n_bins=2);assert sum(v['n'] for v in a['calibration_curve'])==4,a['calibration_curve'];return 'all observations retained'
def constant_json():
 a=e.ModelEvaluator([0,1,0,1],[.5]*4).calculate_roc_curve();json.dumps(a,allow_nan=False);return 'strict JSON'
def parser():
 df=pd.DataFrame({'y':[1,2,3,4],'g':['a','b','a','b']});y,X,n=r.FormulaParser.parse_formula('y ~ C(g)',df);assert X.shape==(4,1);return n
for name,fn,dep in [('OLS independent least-squares',ols,True),('Logit analytic two-stratum MLE',logistic,True),('OLS missing-row count',missing,True),('Logit invalid outcomes',bad_input,True),('Confusion matrix arithmetic',counts,False),('AUC pairwise known 0.75',auc,False),('Constant probability threshold',constant,False),('Calibration boundary count',calibration_count,False),('ROC strict JSON constant scores',constant_json,False),('FormulaParser categorical',parser,False)]:check(name,fn,dep)
(ROOT/'reports/acceptance-regression.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2));print(json.dumps(rows,ensure_ascii=False,indent=2))

raise SystemExit(1 if any(row['status'] != 'PASS' for row in rows) else 0)
