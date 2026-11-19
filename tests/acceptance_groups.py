"""Fixed synthetic acceptance checks; never imports/runs the web application."""
from pathlib import Path
import importlib.util,sys,types,json,math,warnings
import numpy as np
import pandas as pd
from scipy import stats

ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/'modules/MedStat/src/analysis'
pkg=types.ModuleType('acceptance_medstat');pkg.__path__=[str(SRC)];sys.modules[pkg.__name__]=pkg

def load(name):
    spec=importlib.util.spec_from_file_location('acceptance_medstat.'+name,SRC/(name+'.py'))
    module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module);return module
C=load('correlation').CorrelationAnalyzer
Cat=load('categorical_tests')
G=load('group_analysis').GroupAnalyzer
T=load('tableone').TableOne
results=[]
def check(name,basis,fn):
    try:
        with warnings.catch_warnings(record=True) as ws:
            warnings.simplefilter('always');passed,observed,expected=fn()
        row={'case':name,'status':'PASS' if passed else 'FAIL','basis':basis,'observed':observed,'expected':expected,'warnings':[str(w.message) for w in ws]}
    except Exception as e:row={'case':name,'status':'FAIL','basis':basis,'observed':type(e).__name__+': '+str(e),'expected':'可处理的结构化结果或明确拒绝'}
    results.append(row)
def close(a,b):return math.isclose(float(a),float(b),rel_tol=1e-10,abs_tol=1e-10)
def corr():
    x=np.array([1.,2,3,4,5]);y=np.array([2.,1,4,3,8]);r=C(pd.DataFrame({'x':x,'y':y}),{'x':'numeric_continuous','y':'numeric_continuous'}).pearson('x','y')
    expected=sum((x-x.mean())*(y-y.mean()))/math.sqrt(sum((x-x.mean())**2)*sum((y-y.mean())**2))
    return close(r['coefficient'],expected),r,{'r':expected,'n':5}
check('Pearson非平凡相关系数','独立中心化乘积公式；不独立验证p值',corr)
def spear():
    r=C(pd.DataFrame({'x':[1,2,3,4,5],'y':[5,3,4,1,2]}),{}).spearman('x','y');expected=1-6*(16+1+1+9+9)/(5*(25-1))
    return close(r['coefficient'],expected),r,expected
check('Spearman无并列秩','独立秩差平方公式',spear)
def missing():
    r=C(pd.DataFrame({'x':[1,2,None,4,5],'y':[2,4,6,None,10]}),{}).pearson('x','y')
    return r['n']==3 and close(r['coefficient'],1),r,{'n':3,'r':1}
check('相关性成对缺失剔除','固定3对完全线性观测',missing)
def constant():
    try:r=C(pd.DataFrame({'x':[1,1,1,1],'y':[1,2,3,4]}),{}).pearson('x','y')
    except ValueError:return True,'明确拒绝','明确拒绝或结构化不可估计'
    return r is None,r,'明确拒绝或结构化不可估计，不能返回NaN数值'
check('相关性常量列','零方差导致相关性未定义',constant)
def invalid_method():
    try:r=C(pd.DataFrame({'x':[1,2,3],'y':[1,4,2]}),{'x':'numeric_continuous','y':'numeric_continuous'}).calculate_all('unsupported')
    except ValueError:return True,'拒绝','拒绝未知方法'
    return False,r,'拒绝未知方法，不能静默运行Spearman'
check('相关性未知方法','输入契约',invalid_method)

def group_df(groups):return pd.DataFrame([(str(i),v) for i,vals in enumerate(groups) for v in vals],columns=['g','v'])
def welch():
    a=np.array([1.,2,3,4]);b=np.array([2.,4,8,10,12]);d=G(group_df([a,b]),{'v':'numeric_continuous'},'g').analyze_numeric('v')
    expected=(a.mean()-b.mean())/math.sqrt(a.var(ddof=1)/len(a)+b.var(ddof=1)/len(b))
    return close(d['tests']['welch_t_test']['statistic'],expected),d['tests'],{'Welch_t':expected}
check('Welch统计量','独立均值、样本方差、标准误公式',welch)
def mwu():
    d=G(group_df([[1,2,3],[4,5,6]]),{'v':'numeric_continuous'},'g').analyze_numeric('v')['tests']['mann_whitney_u']
    return close(d['statistic'],0) and close(d['p_value'],2/math.comb(6,3)),d,{'U':0,'two_sided_exact_p':.1}
check('Mann-Whitney完全分离小样本','所有20种秩分配，两端各一种',mwu)
def cohend():
    d=G(group_df([[1,2,3],[4,5,6]]),{'v':'numeric_continuous'},'g').analyze_numeric('v')['tests']['cohens_d']
    return close(d,-3),d,-3
check('Cohen d','两组样本SD均1，均值差-3',cohend)
def anova():
    d=G(group_df([[1,2,3],[4,5,6],[7,8,9]]),{'v':'numeric_continuous'},'g').analyze_numeric('v')['tests']['anova']
    return close(d['statistic'],27),d,{'F':27,'between_SS':54,'within_SS':6,'df':[2,6]}
check('单因素ANOVA','手算组间/组内平方和',anova)
def group_missing_category():
    d=pd.DataFrame({'g':['a','a','b','b'],'v':['yes','no',None,None]})
    r=G(d,{'v':'categorical'},'g').analyze_categorical('v');return 'b' in r['groups'],r,'保留b组并报告0个有效观察/缺失，不应KeyError'
check('分类变量某组全缺失','缺失数据边界',group_missing_category)

def chisquare():
    obs=np.array([[10,20],[20,10]]);r=Cat.CategoricalTestSelector.select_test(obs,'chi2');e=np.outer(obs.sum(1),obs.sum(0))/obs.sum();expected=((obs-e)**2/e).sum()
    return close(r['statistic'],expected),r,{'chi2':expected}
check('Pearson列联表卡方','独立期望频数与平方残差公式',chisquare)
def fisher():
    obs=np.array([[1,9],[11,3]]);r=Cat.CategoricalTestSelector.select_test(obs,'fisher')
    probs={a:math.comb(12,a)*math.comb(12,10-a)/math.comb(24,10) for a in range(0,11)}
    expected=sum(p for p in probs.values() if p<=probs[1]+1e-15)
    return close(r['p_value'],expected),r,{'two_sided_p':expected,'OR':1/33}
check('2×2 Fisher精确P值','独立超几何组合枚举',fisher)
def montecarlo():
    obs=np.array([[1,0,1],[0,1,1],[1,1,0]]);r=Cat.CategoricalTestSelector.select_test(obs)
    # Branch called Fisher/Monte Carlo must not merely return uncorrected Pearson approximation.
    return 'Monte Carlo' not in r['method'],r,{'not_acceptable':'Fisher/Monte Carlo标签实际调用chi2_contingency；此处不提供Fisher基准值'}
check('稀疏RxC方法名称与执行一致','静态调用核对 + 数值返回，不宣称精确P值独立基准',montecarlo)
def df_strata(tables):
    rows=[]
    for k,table in enumerate(tables):
        for i in range(2):
            for j in range(2):rows.extend([{'g':1-i,'y':1-j,'s':k}]*int(table[i][j]))
    return pd.DataFrame(rows)
def mh_null():
    tables=[[[9,81],[1,9]],[[9,1],[81,9]]];r=Cat.MantelHaenszelTest.test(df_strata(tables),'g','y','s')
    return close(r['mh_statistic'],0),r,{'MH_conditional_score':0,'pooled_OR':1,'explanation':'各层a恰等于独立性期望；无连续性修正的条件得分为0'}
check('MH分层检验抵抗混杂','每层独立性构造；层内a-Ea=0',mh_null)
def homogeneous():
    r=Cat.MantelHaenszelTest.test(df_strata([[[20,10],[10,20]],[[20,10],[10,20]]]),'g','y','s')
    return close(r['homogeneity_statistic'],0),r,{'Breslow_Day_statistic':0,'common_OR':4}
check('同质层的同质性检验','完全相同列联表，共同比值比恰与层比值比一致',homogeneous)
def ci_replication():
    one=Cat.MantelHaenszelTest.test(df_strata([[[20,10],[10,20]]]),'g','y','s')
    two=Cat.MantelHaenszelTest.test(df_strata([[[20,10],[10,20]],[[20,10],[10,20]]]),'g','y','s')
    w1=math.log(one['pooled_or_ci'][1]/one['pooled_or_ci'][0]);w2=math.log(two['pooled_or_ci'][1]/two['pooled_or_ci'][0])
    return w2<w1,{'one':one['pooled_or_ci'],'two':two['pooled_or_ci'],'logwidth_ratio':w2/w1},'增加独立同分布层后区间应变窄，而非变宽'
check('MH区间随信息增加','独立复制样本的信息量单调性',ci_replication)
def forest():
    r=Cat.MantelHaenszelTest.generate_forest_plot_data([{'or':4,'stratum':'a'}],4,[2,8])['data'][-1]['error_x']
    return r['array']==[4] and r['arrayminus']==[2],r,{'array':[4],'arrayminus':[2]}
check('森林图上下误差方向','已给定中心4、区间[2,8]的绘图代数',forest)

def sd():
    r=T(pd.DataFrame({'v':[1.,2,3]}),{'v':'numeric_continuous'}).generate()['table'].iloc[0].to_dict()
    return close(r['sd'],1),r,{'sample_sd':1,'population_sd':math.sqrt(2/3)}
check('TableOne样本SD','[1,2,3]样本方差=1；GroupAnalyzer同变量采用ddof=1',sd)
def denominator():
    df=pd.DataFrame({'g':['a']*4,'v':['yes','yes','no',None]})
    overall=T(df,{'v':'categorical'}).generate()['table'];grouped=T(df,{'v':'categorical'},'g').generate()['table']
    op=float(overall[overall.level=='yes'].iloc[0].percent);gp=float(grouped[grouped.level=='yes'].iloc[0].percent)
    return op==gp,{'unstratified_yes_pct':op,'single_group_yes_pct':gp},'同一份数据仅增加单一分层，不应静默切换分母；两种口径须显式说明'
check('TableOne分类百分比分母一致性','单层/无分层不变性',denominator)
def plain(value):
    if isinstance(value,np.generic):return plain(value.item())
    if isinstance(value,float) and not math.isfinite(value):return str(value)
    if isinstance(value,dict):return {str(k):plain(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)):return [plain(v) for v in value]
    return value
results=plain(results)
summary={x:sum(r['status']==x for r in results) for x in ['PASS','FAIL','BLOCKED']}
(ROOT/'reports').mkdir(exist_ok=True)
(ROOT/'reports/acceptance-groups.json').write_text(json.dumps({'scope':'correlation,group_analysis,categorical_tests,tableone','summary':summary,'results':results},ensure_ascii=False,indent=2,allow_nan=True))
lines=['# 相关性、组间比较、分类检验与TableOne验收','',f"固定合成数据共 {len(results)} 项：PASS {summary['PASS']}，FAIL {summary['FAIL']}，BLOCKED {summary['BLOCKED']}。未修改原模块；所有发现待决定后修复。",'', '独立性说明：相关系数、Welch统计量、ANOVA、Cohen d、2×2 Fisher采用直接公式/组合枚举；MH使用条件独立与同质性构造反例。未把调用同一SciPy函数视为独立验证。未做临床数据验证；PASS只覆盖所列样例。','', '| 检查 | 结果 | 基准/判据 |','|---|---|---|']
for r in results:lines.append(f"| {r['case']} | {r['status']} | {r['basis']} |")
lines+=['','## 未通过项具体证据','']
for r in results:
    if r['status']=='FAIL':lines += ['### '+r['case'],'','预期：'+str(r['expected']),'','实际：```'+json.dumps(r['observed'],ensure_ascii=False)+'```','']
lines+=['## 判断与待确认项','','- 正常有限输入下基础Pearson/Spearman、Welch统计量、Mann–Whitney小样本、Cohen d、ANOVA及2×2 Fisher所列样例通过。不能由此推出全部统计模块验收通过。','- 分类RxC“Fisher/Monte Carlo”分支实际返回Pearson近似P值，方法标签与执行不符，应阻止作为精确检验报告。','- MH检验使用合并总频数而非分层条件得分；同质性检验以OR=1独立性期望代替共同OR期望；区间对层方差直接求和，更多独立层反而变宽；森林图误差方向颠倒且单层区间被固定设为OR×0.5/2。','- TableOne的SD采用总体分母，与同项目GroupAnalyzer的样本SD不一致；分类缺失值分母无分层/分层不一致。','- GroupAnalyzer数值两组同时返回Welch和Mann–Whitney，TableOne依总体正态性结果自动选检验且t检验默认等方差。这些是方法选择与分析计划兼容性事项，尚不自动更改。','- TableOne缺少完整效应量/置信区间及显式缺失汇总；这些为验收范围外的缺项，不应称为已满足完整科研报告要求。','','执行：`.venv/bin/python tests/acceptance_groups.py`。JSON记录包含全部输入构造对应的实际返回值；失败案例不会被计作通过。']
lines += ['', '存在FAIL或BLOCKED时脚本以退出码1结束；生成报告不等同于验收通过。']
(ROOT/'reports/acceptance-groups.md').write_text('\n'.join(lines)+'\n')
print(json.dumps(summary));print('reports/acceptance-groups.md')

raise SystemExit(1 if summary["FAIL"] or summary["BLOCKED"] else 0)
