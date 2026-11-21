"""Immutable, source-pinned deduplication and human review jobs."""
import copy
import hashlib
import json
import re
from .core import canonical, now
from .deduplication import deduplicate

def digest(value):return hashlib.sha256(canonical(value).encode()).hexdigest()

def validate(kind, payload):
    fields={'source_artifact','source_sha256','_retry_of'}
    if kind=='dedup_review':fields|={'candidate_index','decision','reason'}
    if set(payload)-fields:raise ValueError('去重任务含未知字段')
    name=payload.get('source_artifact')
    if not isinstance(name,str) or not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_.-]*',name):raise ValueError('来源产物名无效')
    if not re.fullmatch('[a-f0-9]{64}',payload.get('source_sha256','')):raise ValueError('需要来源快照哈希')
    if kind=='dedup_review':
        if type(payload.get('candidate_index')) is not int or payload['candidate_index']<0:raise ValueError('候选编号无效')
        if payload.get('decision') not in ('keep','merge'):raise ValueError('需选择保留或合并')
        if not isinstance(payload.get('reason'),str) or not 1<=len(payload['reason'].strip())<=2000:raise ValueError('需填写处理理由（最多2000字）')

def load_source(store,pid,payload):
    source=json.loads(store.artifact(pid,payload['source_artifact']).read_text())
    if digest(source)!=payload['source_sha256']:raise ValueError('来源已变化，请重新选择产物')
    return source

def resolve(source,payload):
    out=copy.deepcopy(source)
    if out.get('method')!='deduplication':raise ValueError('不是去重产物')
    index=payload['candidate_index'];candidates=out['review_candidates']
    if index>=len(candidates):raise ValueError('候选编号不存在')
    candidate=candidates[index]
    if candidate.get('resolution'):raise ValueError('此候选已处理，请勿覆盖旧意见')
    left,right=candidate['left'],candidate['right']
    groups=out['groups']
    a=next(g for g in groups if left in g['source_indices']);b=next(g for g in groups if right in g['source_indices'])
    if payload['decision']=='merge' and a is not b:
        merged=set(a['source_indices']+b['source_indices'])
        for c in candidates:
            if c.get('resolution')=='keep' and c['left'] in merged and c['right'] in merged:raise ValueError('合并会违反已有保留决定，请新建复核分支')
        a['source_indices']=sorted(merged)
        # Preserve an existing representative; all source metadata remains available.
        groups.remove(b)
    candidate['resolution']=payload['decision']
    out.setdefault('review_events',[]).append({'candidate_index':index,'left':left,'right':right,'decision':payload['decision'],'reason':payload['reason'].strip(),'actor':'local_owner','identity_assurance':'single_owner_access_token','timestamp':now()})
    for c in candidates:
        if not c.get('resolution') and any(c['left'] in g['source_indices'] and c['right'] in g['source_indices'] for g in groups):c['resolution']='same_group_after_review'
    out['records']=[out['raw_records'][g['selected_source_index']-1] for g in groups]
    out['unique_count']=len(groups);out['duplicates_removed']=out['input_count']-len(groups)
    out['pending_review_count']=sum(not c.get('resolution') for c in candidates)
    return out

def run(store,pid,payload,jid,kind):
    validate(kind,payload);source=load_source(store,pid,payload)
    if kind=='deduplicate':
        out=deduplicate(source['records']);out['method']='deduplication';out['review_events']=[]
        out['pending_review_count']=len(out['review_candidates'])
    else:out=resolve(source,payload)
    out['source_artifact']=payload['source_artifact'];out['source_sha256']=payload['source_sha256']
    name=store.save(pid,f'{jid}-dedup.json',out)
    return {'artifact':name,'unique_count':out['unique_count'],'pending_review_count':out['pending_review_count']}
