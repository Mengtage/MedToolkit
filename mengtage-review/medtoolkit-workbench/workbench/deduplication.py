"""Deterministic title/PMID/DOI dedup with retained originals and merge evidence.

Default review policy preserves identifier conflicts for human review; no LLM.
"""
import copy
import hashlib
import re
import unicodedata
from .core import canonical

def normalize(record):
    def value(key):
        v=record.get(key)
        if v is None:return ''
        if not isinstance(v,(str,int)):raise ValueError('文献标题和标识须为文本')
        return unicodedata.normalize('NFKC',str(v)).strip()
    pmid=value('pmid')
    pmid=re.sub(r'^https?://pubmed\.ncbi\.nlm\.nih\.gov/','',pmid,flags=re.I).strip('/')
    pmid=re.sub(r'^pmid\s*:\s*','',pmid,flags=re.I)
    if pmid and not re.fullmatch(r'[0-9]+',pmid):raise ValueError('PMID格式无效')
    if pmid:pmid=str(int(pmid))
    doi=re.sub(r'^(?:https?://(?:dx\.)?doi\.org/|doi\s*:\s*)','',value('doi'),flags=re.I).casefold()
    if doi and not re.fullmatch(r'10\.\d{4,9}/\S+',doi):raise ValueError('DOI格式无效')
    title=''.join(' ' if unicodedata.category(c).startswith('P') else c for c in value('title').casefold())
    title=' '.join(title.split())
    return {'pmid':pmid,'doi':doi,'title':title}

def merged_representative(raw_records, source_indices):
    ids=[i-1 for i in source_indices]
    chosen=max(ids,key=lambda i:(sum(v not in (None,'',[],{}) for v in raw_records[i].values()),-i))
    record=copy.deepcopy(raw_records[chosen])
    for key in ('pmid','doi'):
        if record.get(key) in (None,''):
            values=[raw_records[i].get(key) for i in ids if raw_records[i].get(key) not in (None,'')]
            norms={normalize({key:v})[key] for v in values}
            if len(norms)==1:record[key]=values[0]
    return record,chosen+1

def deduplicate(records, *, conflict_policy="review"):
    if conflict_policy not in ('review','title_wins'):raise ValueError('须显式选择review或title_wins冲突策略')
    if not isinstance(records,list) or len(records)>1000 or any(not isinstance(r,dict) for r in records):raise ValueError('最多1000条文献对象')
    normalized=[normalize(r) for r in records]
    parent=list(range(len(records)));events=[];conflicts=[]
    def find(i):
        while parent[i]!=i:i=parent[i]
        return i
    def members(i):return [k for k in range(len(records)) if find(k)==i]
    indexes={k:{} for k in ('pmid','doi','title')}
    candidates={}
    for i,record in enumerate(normalized):
        for key,val in record.items():
            if not val:continue
            for j in indexes[key].get(val,[]):
                candidates.setdefault((j,i),[]).append(key)
                if len(candidates)>20000:raise ValueError('候选重复对超过20000，请拆分输入并人工核对跨批次重复')
            indexes[key].setdefault(val,[]).append(i)
    conflicted_titles={t for t,idxs in indexes['title'].items() if any(len({normalized[i][k] for i in idxs if normalized[i][k]})>1 for k in ('pmid','doi'))}
    # IDs before title, then source order; guard conflicts across whole connected components.
    for (left,right),keys in sorted(candidates.items(),key=lambda kv:(not bool(set(kv[1])&{'pmid','doi'}),kv[0])):
        a,b=find(left),find(right)
        if a==b:continue
        group=members(a)+members(b)
        inconsistent={k:sorted({normalized[i][k] for i in group if normalized[i][k]}) for k in ('pmid','doi')}
        inconsistent={k:v for k,v in inconsistent.items() if len(v)>1}
        has_identifier=bool(set(keys)&{'pmid','doi'})
        # With review policy a title-only match is automatic only when one side has no ID, or cross-DB long title (>=30 chars) has complementary PMID/DOI with no conflict.
        both_identified=all(any(normalized[i][k] for i in members(c) for k in ('pmid','doi')) for c in (a,b))
        title_val=normalized[left]['title'] if 'title' in keys else ''
        title_bucket_conflict=bool(not has_identifier and title_val in conflicted_titles)
        cross_db_complementary=bool(not has_identifier and both_identified and not inconsistent and not title_bucket_conflict and len(title_val)>=30)
        reason='identifier_conflict' if inconsistent else 'title_only_ambiguous_bucket' if title_bucket_conflict else 'title_only_both_identified' if not has_identifier and both_identified and not cross_db_complementary else None
        detail={'left':left+1,'right':right+1,'matched_fields':keys,'identifier_conflicts':inconsistent}
        if reason and not(conflict_policy=='title_wins' and 'title' in keys):
            conflicts.append({**detail,'reason':reason,'action':'retain_for_review'});continue
        parent[b]=a;events.append({**detail,'action':'merge','override':bool(reason)})
    output=[];groups=[]
    for representative in sorted({find(i) for i in range(len(records))}):
        ids=[i+1 for i in members(representative)]
        record,chosen=merged_representative(records,ids)
        output.append(record)
        groups.append({'canonical_record_id':f'd{len(groups)+1:06d}','source_indices':ids,'selected_source_index':chosen})
    return {'records':output,'raw_records':copy.deepcopy(records),'normalized_keys':normalized,'groups':groups,
            'merge_events':events,'review_candidates':conflicts,'input_count':len(records),'unique_count':len(output),
            'duplicates_removed':len(records)-len(output),'llm_calls':0,'rule_version':'title-pmid-doi-v1',
            'conflict_policy':conflict_policy,'input_sha256':hashlib.sha256(canonical(records).encode()).hexdigest()}
