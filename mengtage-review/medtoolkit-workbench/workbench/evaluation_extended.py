"""Explicit legacy-compatible HL/DCA and optional paired NRI/IDI evaluation."""
import math
from .core import canonical
import hashlib

def json_hash(value):return hashlib.sha256(canonical(value).encode()).hexdigest()
from .evaluation import validate as validate_basic

METHOD='prediction_evaluation_extended'

def validate(payload):
    allowed={'classification','method','rows','threshold','n_bins','evaluation_scope','dca_thresholds','nri_thresholds','paired_confirmed','_retry_of'}
    if set(payload)-allowed:raise ValueError('扩展预测评估含未知字段')
    rows=payload.get('rows')
    if not isinstance(rows,list) or not rows or any(not isinstance(r,dict) for r in rows):raise ValueError('需要逐行预测数据')
    paired=any('old_probability' in r for r in rows)
    expected={'observed','probability'}|({'old_probability'} if paired else set())
    if any(set(r)!=expected for r in rows):raise ValueError('比较模型时每行必须同时有新旧概率，不自动剔除或对齐')
    base={k:v for k,v in payload.items() if k not in ('dca_thresholds','nri_thresholds','paired_confirmed')}
    base['rows']=[{k:r[k] for k in ('observed','probability')} for r in rows]
    validate_basic(base)
    if payload.get('classification') not in ('synthetic','public','deidentified'):raise ValueError('仅允许合成数据、公开文献数据或已脱敏研究数据')
    thresholds=payload.get('dca_thresholds')
    _thresholds(thresholds,'DCA',True,201)
    if paired:
        if payload.get('paired_confirmed') is not True:raise ValueError('请确认每行新旧概率来自同一受试者、同一结局时间点')
        for row in rows:
            p=row['old_probability']
            if type(p) not in (int,float) or not math.isfinite(p) or not 0<=p<=1:raise ValueError('旧概率须为0至1有限数值')
        _thresholds(payload.get('nri_thresholds'),'NRI',False,50)
    elif 'nri_thresholds' in payload or 'paired_confirmed' in payload:raise ValueError('无旧概率时不接受配对声明或NRI阈值')
    return paired

def _thresholds(values,name,endpoints,limit):
    if not isinstance(values,list) or not 1<=len(values)<=limit:raise ValueError(f'{name}需显式提供1至{limit}个阈值')
    for value in values:
        if type(value) not in (int,float) or not math.isfinite(value) or not (0<=value<=1 if endpoints else 0<value<1):raise ValueError(f'{name}阈值范围无效')
    if any(a>=b for a,b in zip(values,values[1:])):raise ValueError(f'{name}阈值须严格递增且不重复')

def analyze(store,pid,payload,jid):
    paired=validate(payload)
    from .adapters import module
    import scipy,sklearn
    evaluator_type=module('MedStat/src/analysis/model_evaluation.py','medstat_extended').ModelEvaluator
    y=[r['observed'] for r in payload['rows']];p=[r['probability'] for r in payload['rows']]
    evaluator=evaluator_type(y,p,y_probs=p,threshold=payload['threshold'])
    calibration=evaluator.calculate_calibration_metrics(payload['n_bins'])
    hl=calibration['hosmer_lemeshow'];warnings=[]
    if hl['status']!='approximate':warnings.append('HL不可完成近似检验：'+hl['status'])
    if hl['small_expected_cells']:warnings.append('HL存在期望频数小于5的单元格；卡方近似可能不可靠。')
    if 1 in payload['dca_thresholds']:warnings.append('DCA阈值1的权重无定义；模型及全部治疗净获益返回null。')
    result={'method':METHOD,'classification':payload.get('classification','synthetic'),'llm_calls':0,'n':len(y),'events':sum(y),'non_events':len(y)-sum(y),
        'evaluation_scope':payload['evaluation_scope'],'scope_verification':'user_declared_not_independently_verified',
        'input_sha256':json_hash({k:v for k,v in payload.items() if k!='_retry_of'}),'threshold':payload['threshold'],
        'threshold_rule':'probability >= threshold','n_bins':payload['n_bins'],'binning':'legacy_equal_width',
        'brier_score':calibration['brier_score'],'calibration_curve':calibration['calibration_curve'],'hosmer_lemeshow':hl,
        'dca':evaluator.decision_curve_analysis(payload['dca_thresholds']),
        'comparison':None,'warnings':warnings,'source':'MedStat/src/analysis/model_evaluation.py',
        'environment':{'scipy':scipy.__version__,'scikit_learn':sklearn.__version__},
        'limitations':['HL沿用等宽分箱及非空组数减2自由度；p值为近似诊断，不代表已证明校准良好。',
            'DCA仅为提供概率在指定阈值下的净获益计算，不选择或推荐临床阈值。']}
    if paired:
        old=[r['old_probability'] for r in payload['rows']]
        old_evaluator=evaluator_type(y,old,y_probs=old,threshold=payload['threshold'])
        result['comparison']={'paired_by':'same_input_row','pairing_assurance':'user_confirmed_not_independently_verified',
            'nri_method':'binary_category_nri_at_each_threshold','nri':evaluator.calculate_nri(old,payload['nri_thresholds']),
            'idi':evaluator.calculate_idi(old),'old_model_dca':old_evaluator.decision_curve_analysis(payload['dca_thresholds'])}
        result['limitations']+=['NRI是每个阈值分别定义的二分类结果，不是多类别或连续NRI。',
            'IDI标准误与Z仅基于固定配对预测；不包括模型重新拟合不确定性，不提供显著性结论。']
    canonical(result)  # Reject NaN/Infinity before persisting any output.
    name=store.save(pid,f'{jid}-statistics.json',result)
    return {'artifact':name,**result}
