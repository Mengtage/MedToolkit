"""Explicit probability evaluation; no automatic fitting or threshold replacement."""
import hashlib
import math
from .core import canonical


def validate(payload):
    if set(payload)-{'classification','method','rows','threshold','n_bins','evaluation_scope','_retry_of'}:
        raise ValueError('预测评估包含未允许字段')
    if payload.get('evaluation_scope') not in ('training','held_out','external'):
        raise ValueError('需明确training/held_out/external评估来源')
    threshold=payload.get('threshold')
    if type(threshold) not in (int,float) or not math.isfinite(threshold) or not 0<=threshold<=1:
        raise ValueError('需显式指定0至1分类阈值')
    bins=payload.get('n_bins')
    rows=payload.get('rows')
    if not isinstance(rows,list) or not 2<=len(rows)<=10000:raise ValueError('需要2至10000行')
    if type(bins) is not int or not 2<=bins<=min(20,len(rows)):raise ValueError('分箱数需为2至20且不超过样本数')
    labels=set()
    for row in rows:
        if not isinstance(row,dict) or set(row)!={'observed','probability'}:raise ValueError('每行仅允许observed/probability')
        y,p=row['observed'],row['probability']
        if type(y) is not int or y not in (0,1):raise ValueError('结局须为整数0/1')
        if type(p) not in (int,float) or not math.isfinite(p) or not 0<=p<=1:raise ValueError('概率须为0至1有限数值；不自动剔除缺失')
        labels.add(y)
    if labels!={0,1}:raise ValueError('ROC评估需要两类结局')


def analyze(store,pid,payload,jid):
    import sklearn
    import scipy
    from .adapters import module
    validate(payload)
    source='MedStat/src/analysis/model_evaluation.py'
    m=module(source,'medstat_evaluation')
    y=[r['observed'] for r in payload['rows']];p=[r['probability'] for r in payload['rows']]
    evaluator=m.ModelEvaluator(y,p,y_probs=p,threshold=payload['threshold'])
    cm=evaluator.calculate_confusion_matrix();metrics=evaluator.calculate_basic_metrics()
    undefined=[]
    for name,denominator in [('ppv',cm['TP']+cm['FP']),('npv',cm['TN']+cm['FN']),('mcc',(cm['TP']+cm['FP'])*(cm['TP']+cm['FN'])*(cm['TN']+cm['FP'])*(cm['TN']+cm['FN']))]:
        if denominator==0:metrics[name]=None;undefined.append(name)
    calibration=evaluator.calculate_calibration_metrics(payload['n_bins'])
    result={'method':'prediction_evaluation','classification':payload.get('classification','synthetic'),'llm_calls':0,
        'n':len(y),'event_value':1,'threshold':payload['threshold'],'threshold_rule':'probability >= threshold',
        'evaluation_scope':payload['evaluation_scope'],'scope_verification':'user_declared_not_independently_verified',
        'confusion_matrix':cm,'metrics':metrics,'undefined_metrics':undefined,'roc':evaluator.calculate_roc_curve(),
        'brier_score':calibration['brier_score'],'calibration_curve':calibration['calibration_curve'],
        'n_bins':payload['n_bins'],'binning':'equal_width_0_1; last bin includes 1',
        'threshold_selection':'input threshold used; ROC Youden optimum exploratory on this evaluation set',
        'excluded_outputs':['hosmer_lemeshow','isotonic_refit','dca','nri','idi'],
        'source':source,'environment':{'scipy':scipy.__version__,'scikit_learn':sklearn.__version__},
        'input_sha256':hashlib.sha256(canonical({k:payload[k] for k in ('rows','threshold','n_bins','evaluation_scope')}).encode()).hexdigest()}
    name=store.save(pid,f'{jid}-statistics.json',result)
    return {'artifact':name,**result}
