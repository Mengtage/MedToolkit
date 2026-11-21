"""Auditable PRISMA-style accounting for one explicitly selected local lineage.

Not an assertion that this lineage covers an entire systematic review.
"""
from collections import Counter
import html
import json
import uuid
from .core import canonical,now
from .fulltext import json_hash
from .screening_exports import csv_text

REFERENCE='https://www.prisma-statement.org/prisma-2020-flow-diagram'

def final(events):return {e['data']['record_id']:e['data'] for e in events if e['kind']=='adjudicated'}

def source_counts(store,project,draft):
    """Fail closed: no invented zero for absent, changed or inconsistent sources."""
    name=draft['source_artifact'];expected=draft['source_sha256'];sources=[];visited=set();selected=None;raw=None
    try:
        for _ in range(256):
            if name in visited:raise ValueError('来源链循环')
            visited.add(name);source=json.loads(store.artifact(project,name).read_text())
            if json_hash(source)!=expected:raise ValueError('来源产物哈希变化')
            sources.append({'artifact':name,'sha256':expected,'kind':source.get('method','search')})
            if source.get('method')=='deduplication':
                if selected is None:
                    selected=source;raw=source['raw_records'];groups=source['groups']
                    if source['records']!=[r['record'] for r in draft['records']]:raise ValueError('去重产物与筛选快照不一致')
                    indices=[i for group in groups for i in group['source_indices']]
                    if sorted(indices)!=list(range(1,len(raw)+1)):raise ValueError('去重来源分组不守恒')
                    if len(groups)!=len(source['records']) or any(g['selected_source_index'] not in g['source_indices'] for g in groups):raise ValueError('去重代表记录无效')
                    if source['records']!=[raw[g['selected_source_index']-1] for g in groups]:raise ValueError('去重代表记录不匹配')
                    if source['input_count']!=len(raw) or source['unique_count']!=len(groups) or source['duplicates_removed']!=len(raw)-len(groups):raise ValueError('去重计数不守恒')
                    if any(not c.get('resolution') for c in source['review_candidates']):raise ValueError('去重冲突未处理')
                elif source['raw_records']!=raw:raise ValueError('复核分支原始记录不一致')
                name=source['source_artifact'];expected=source['source_sha256'];continue
            if selected is None or source['records']!=raw:raise ValueError('缺少检索到去重的完整来源链')
            if source.get('method')=='source_collection':
                from .sources import collection_accounting
                account=collection_accounting(store,project,source)
                account['record_source_lineage']=[{'screening_record_id':draft['records'][i]['record_id'],'canonical_record_id':g['canonical_record_id'],'members':[source['record_origins'][j-1] for j in g['source_indices']]} for i,g in enumerate(selected['groups'])]
                return {'records_identified':len(raw),'duplicates_removed':len(raw)-len(draft['records']),'sources':sources,**account}
            retrieved=source['retrieved'];hits=source['total_hits']
            if type(retrieved) is not int or type(hits) is not int or retrieved!=len(raw) or hits<retrieved:raise ValueError('检索数量不一致')
            complete=source.get('complete') is True and hits==retrieved
            return {'records_identified':len(raw),'duplicates_removed':len(raw)-len(draft['records']),
                'search_total_hits':hits,'records_not_downloaded':hits-retrieved,'search_complete':complete,
                'sources':sources,'issues':[] if complete else ['检索结果未取全；仅统计已导入的局部记录，不能作为完整检索流程。']}
        raise ValueError('来源链超过256个版本')
    except (KeyError,IndexError,TypeError,ValueError,OSError) as error:
        return {'records_identified':None,'duplicates_removed':None,'search_total_hits':None,'records_not_downloaded':None,'search_complete':False,'sources':sources,'issues':['检索/去重来源链缺失、变化或不一致；前段计数未知。']}

class PrismaService:
    def __init__(self,service):self.service=service;self.store=service.store
    def preview(self,review,actor):
        audit=self.service.ledger.export(review,actor);events=audit['events'];draft=events[0]['data'];project=events[0]['project_id'];stage=draft['protocol']['stage'];issues=[]
        mapping=None;retrieval=[];child_final=final(events);parent_changed=False
        if stage=='full_text':
            lineage=draft['lineage'];parent_id=lineage['parent_review_id']
            with self.store.db() as db:all_parent=self.service.ledger._events(db,parent_id)
            position=next((i for i,e in enumerate(all_parent) if e['event_hash']==lineage['parent_event_hash']),None)
            if position is None or all_parent[0]['project_id']!=project:raise ValueError('父阶段版本无法核验')
            parent=all_parent[:position+1];parent_changed=position!=len(all_parent)-1
            retrieval=lineage['retrieval_events'];missing=lineage['reports_not_retrieved']
            mapping=self.service.studies.state(review,actor)
            if mapping['screening_event_hash']!=events[-1]['event_hash']:raise ValueError('全文裁决正在变化，请刷新')
            included=[r for r in child_final.values() if r['decision']=='include'];excluded=[r for r in child_final.values() if r['decision']=='exclude']
            reports_assessed=len(draft['records']);reports_included=len(included);reports_excluded=len(excluded);pending=audit['pending_final']
            study_count=len({sid for row in mapping['mappings'] for sid in row['study_ids']}) if mapping['mapping_valid'] and not pending else 0 if not reports_included and not pending else None
            if study_count is None:issues.append('全文裁决或人工研究映射尚未完成，研究数未知。')
            if parent_changed:issues.append('父批次已有后续修订；本图使用子批次冻结的历史父版本。')
        elif stage=='title_abstract':
            parent=events;parent_id=review
            if audit['pending_final']:raise ValueError('请先完成题名摘要裁决')
            status=self.service.fulltext.status(review,actor);retrieval=status['events']
            if status['parent_event_hash']!=events[-1]['event_hash']:raise ValueError('父阶段正在变化，请刷新')
            if any(row['status']=='retrieved' for row in status['records']):raise ValueError('已有取得全文，请选择其全文筛选批次生成流程')
            if any(row['status']=='pending' for row in status['records']):raise ValueError('请先逐条登记全文取得状态')
            missing=[{'parent_record_id':r['record_id'],'reason':r['event']['reason'],'retrieval_event_hash':r['event']['event_hash']} for r in status['records']]
            included=[];excluded=[];reports_assessed=reports_included=reports_excluded=pending=study_count=0
        else:raise ValueError('不支持此筛选阶段')
        parent_draft=parent[0]['data'];parent_final=final(parent);n=len(parent_draft['records']);sought=sum(r['decision']=='include' for r in parent_final.values());ta_excluded=sum(r['decision']=='exclude' for r in parent_final.values())
        if len(parent_final)!=n or sought+ta_excluded!=n:raise ValueError('父阶段裁决不完整')
        if sought!=reports_assessed+len(missing) or reports_assessed!=reports_excluded+reports_included+pending:raise ValueError('跨阶段数量不守恒')
        source=source_counts(self.store,project,parent_draft);issues+=source['issues']
        reasons=Counter(r.get('reason_code') or 'legacy_uncoded' for r in excluded)
        labels=draft['protocol'].get('reason_codes',{})
        counts={k:source[k] for k in ('records_identified','duplicates_removed','search_total_hits','records_not_downloaded')}
        counts.update(records_screened=n,records_excluded=ta_excluded,reports_sought=sought,reports_not_retrieved=len(missing),reports_assessed=reports_assessed,reports_excluded=reports_excluded,reports_pending=pending,reports_included=reports_included,studies_included=study_count)
        if pending:issues.append('全文裁决仍有待完成项；不得当成最终流程图。')
        status='selected_lineage_complete' if not issues else 'partial_or_historical'
        return {'schema':'medhunter-prisma-v1','review_id':review,'scope':'selected_frozen_source_collection_and_screening_lineage; not_whole_review_attestation' if source.get('source_breakdown') else 'single_selected_search_and_screening_lineage; not_whole_review_attestation',
            'source_breakdown':source.get('source_breakdown',[]),'collection':source.get('collection'),
            'status':status,'counts':counts,'issues':issues,'reference':REFERENCE,
            'exclusion_reasons':[{'code':code,'label':labels.get(code,'旧批次未编码'),'count':count} for code,count in sorted(reasons.items())],
            'reports_not_retrieved':missing,'mapping':mapping,'retrieval_history':retrieval,
            'provenance':{'project_id':project,'parent_review_id':parent_id,'parent_event_hash':parent[-1]['event_hash'],
                'selected_event_hash':events[-1]['event_hash'],'source_artifacts':source['sources'],'record_source_lineage':source.get('record_source_lineage',[]),'parent_changed':parent_changed,
                'parent_final_decisions':[{k:r.get(k,'') for k in ('record_id','decision','reason_code')} for r in parent_final.values()],'fulltext_final_decisions':list(child_final.values()) if stage=='full_text' else []}}
    def export(self,review,actor,expected_sha256):
        report=self.preview(review,actor)
        if json_hash(report)!=expected_sha256:raise ValueError('流程或映射已变化，请重新预览后导出')
        snapshot={'snapshot_id':uuid.uuid4().hex,'actor':actor,'created':now(),'report':report,'report_sha256':json_hash(report)}
        snapshot['snapshot_sha256']=json_hash(snapshot)
        name=self.store.save(report['provenance']['project_id'],snapshot['snapshot_id']+'-prisma.json',snapshot)
        rows=[{'metric':key,'count':value,'status':'unknown' if value is None else 'known'} for key,value in report['counts'].items()]
        rows += [{'metric':'fulltext_exclusion:'+row['code'],'count':row['count'],'status':'known'} for row in report['exclusion_reasons']]
        for source in report['source_breakdown']:
            for metric in ('retrieved','total_hits'):
                value=source[metric];rows.append({'metric':source['source_id']+':'+metric,'count':value,'status':'unknown' if value is None else 'known'})
        for row in rows:row.update(snapshot_id=snapshot['snapshot_id'],report_sha256=snapshot['report_sha256'])
        return {'snapshot_id':snapshot['snapshot_id'],'artifact':name,'files':[
            {'filename':'prisma-audit.json','content':json.dumps(snapshot,ensure_ascii=False,indent=2)},
            {'filename':'prisma-counts.csv','content':csv_text(['metric','count','status','snapshot_id','report_sha256'],rows)},
            {'filename':'prisma-flow.svg','content':diagram(report,snapshot['snapshot_id'])}]}

def diagram(report,snapshot_id=""):
    reasons='；'.join(f"{r['code']}: {r['count']}" for r in report['exclusion_reasons']) or '无已裁决的全文排除'
    source_lines=[]
    for row in report.get('source_breakdown',[]):
        line=f"{row['database']} [{row['kind']}] {row['searched_at']}：导入 {row['retrieved']} / 命中 {row['total_hits'] if row['total_hits'] is not None else '未知'}"
        source_lines.extend(line[i:i+55] for i in range(0,len(line),55))
    reason_lines=(len(reasons)+54)//55
    height=max(1060,980+24*(reason_lines+len(source_lines)));c=report['counts'];parts=[f'<svg xmlns="http://www.w3.org/2000/svg" width="1100" height="{height}" viewBox="0 0 1100 {height}">', f'<rect width="1100" height="{height}" fill="white"/>','<style>text{font-family:Arial,"Noto Sans CJK SC",sans-serif;fill:#183b43;font-size:18px}.box{fill:#f1f8f7;stroke:#126b64;stroke-width:2}</style>']
    parts.append('<metadata>'+html.escape(json.dumps({'snapshot_id':snapshot_id,'report_sha256':json_hash(report),'review_id':report['review_id']}))+'</metadata>')
    def txt(x,y,value,size=18):parts.append(f'<text x="{x}" y="{y}" style="font-size:{size}px">{html.escape(str(value))}</text>')
    def box(x,y,lines):
        parts.append(f'<rect class="box" x="{x}" y="{y}" width="470" height="110" rx="8"/>')
        for i,line in enumerate(lines):txt(x+15,y+30+28*i,line)
    def count(key):return '未知' if c[key] is None else str(c[key])
    txt(35,38,'PRISMA 2020 计数视图 · 选定来源集合' if report.get('source_breakdown') else 'PRISMA 2020 计数视图 · 单一选定来源链',25)
    txt(35,70,'来源链已完成（不代表整个综述检索完整）' if report['status']=='selected_lineage_complete' else '部分完成 / 历史版本：请核对审计JSON中的限制')
    box(35,100,['已导入检索记录 records：'+count('records_identified'),('命中（各次求和）：' if report.get('source_breakdown') else '检索命中：')+count('search_total_hits'),'尚未下载：'+count('records_not_downloaded')])
    box(580,100,['筛选前移除的重复记录：'+count('duplicates_removed'),'此视图仅支持确定性去重链'])
    box(35,250,['题名摘要筛选 records：'+count('records_screened')]);box(580,250,['题名摘要排除 records：'+count('records_excluded')])
    box(35,400,['拟取得全文 reports：'+count('reports_sought')]);box(580,400,['未取得全文 reports：'+count('reports_not_retrieved')])
    box(35,550,['全文评估 reports：'+count('reports_assessed'),'待最终裁决：'+count('reports_pending')]);box(580,550,['全文排除 reports：'+count('reports_excluded'),'逐原因数量见下方及审计JSON'])
    box(35,700,['纳入报告 reports：'+count('reports_included'),'人工确认研究 studies：'+count('studies_included')])
    for y in (210,360,510,660):parts.append(f'<path d="M270 {y} v30 l-5 -7 m5 7 l5 -7" stroke="#126b64" fill="none"/>')
    for y in (155,305,455,605):parts.append(f'<path d="M505 {y} h60 l-7 -5 m7 5 l-7 5" stroke="#126b64" fill="none"/>')
    reasons='；'.join(f"{r['code']}: {r['count']}" for r in report['exclusion_reasons']) or '无已裁决的全文排除'
    # Wrap escaped text into bounded lines; no injected markup or foreign resources.
    for i in range(0,len(reasons),55):txt(35,850+(i//55)*24,reasons[i:i+55],15)
    for i,line in enumerate(source_lines):txt(35,880+24*reason_lines+24*i,line,15)
    txt(35,height-70,'计数规范来源：PRISMA 2020 · '+REFERENCE,13)
    txt(35,height-45,'本图统计选定集合的新筛选流程；既有筛选分支未相加，未知数量不填零。',14)
    txt(35,height-20,'报告指纹：'+json_hash(report),12)
    parts.append('</svg>');return ''.join(parts)
