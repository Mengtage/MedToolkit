"""Writer capture of adjudicated fulltext reports using a real reviewer credential."""
import json
from .screening import ScreeningLedger
from .fulltext import json_hash,validate_snapshot,sha


def material(store,project,review):
    store.project(project);ledger=ScreeningLedger(store)
    with store.db() as db:
        events=ledger._events(db,review)
        mapping_rows=db.execute('SELECT event FROM study_events WHERE review=? ORDER BY sequence',(review,)).fetchall()
    draft=events[0]['data']
    if events[0]['project_id']!=project:raise ValueError('全文批次不属于所选项目')
    if draft['protocol']['stage']!='full_text' or not any(e['kind']=='revealed' for e in events):raise ValueError('须选择已揭盲的全文批次')
    final={e['data']['record_id']:e for e in events if e['kind']=='adjudicated'}
    if set(final)!={r['record_id'] for r in draft['records']}:raise ValueError('请先完成全部全文裁决')
    mappings=[];previous=''
    for row in mapping_rows:
        event=json.loads(row[0])
        if event['previous_hash']!=previous or json_hash({k:v for k,v in event.items() if k!='event_hash'})!=event['event_hash']:raise ValueError('研究映射审计链损坏')
        mappings.append(event);previous=event['event_hash']
    if not mappings or mappings[-1]['screening_event_hash']!=events[-1]['event_hash']:raise ValueError('请先确认与当前全文裁决一致的研究映射')
    source=json.loads(store.artifact(project,draft['source_artifact']).read_text())
    if json_hash(source)!=draft['source_sha256']:raise ValueError('全文来源清单已变化')
    lineage=draft['lineage']
    with store.db() as db:parent=ledger._events(db,lineage['parent_review_id'])
    if parent[0]['project_id']!=project or not any(e['event_hash']==lineage['parent_event_hash'] for e in parent):raise ValueError('父筛选版本不存在')
    mapped={m['record_id']:m for m in mappings[-1]['mappings']};records=[]
    for row in draft['records']:
        rid=row['record_id']
        if final[rid]['data']['decision']!='include':continue
        if rid not in mapped:raise ValueError('缺少纳入报告的研究映射')
        record=row['record']
        if json_hash(record)!=row['record_sha256']:raise ValueError('报告快照哈希错误')
        doc=record['fulltext'];validate_snapshot(doc)
        if sha(store.artifact(project,doc['blob']).read_bytes())!=doc['file_sha256']:raise ValueError('全文原件已变化')
        binding={'review_id':review,'record_id':rid,'report_id':record['report_id'],'study_ids':mapped[rid]['study_ids'],'study_scope':'selected_review_only','screening_event_hash':events[-1]['event_hash'],'decision_event_hash':final[rid]['event_hash'],'mapping_event_hash':mappings[-1]['event_hash'],'source_artifact':draft['source_artifact'],'source_sha256':draft['source_sha256'],'record_sha256':row['record_sha256'],'protocol_sha256':draft['protocol_sha256'],'parent_review_id':lineage['parent_review_id'],'parent_event_hash':lineage['parent_event_hash'],'retrieval_event_hash':record['retrieval_event_hash']}
        records.append({'record_id':rid,'title':record.get('title',''),'record':record,'binding':binding})
    return {'records':records,'screening_event_hash':events[-1]['event_hash'],'mapping_event_hash':mappings[-1]['event_hash'],'parent_changed':parent[-1]['event_hash']!=lineage['parent_event_hash']}


def candidates(service,project,review,actor):
    service.ledger.export(review,actor)  # Caller must be the actual adjudicator, after reveal.
    view=material(service.store,project,review)
    return {**view,'records':[{'record_id':r['record_id'],'title':r['title'],'report_id':r['binding']['report_id'],'study_ids':r['binding']['study_ids']} for r in view['records']]}


def capture(service,project,review,record_id,screening_event_hash,mapping_event_hash,classification,confirmed,actor):
    if confirmed is not True or classification not in ('public','synthetic'):raise ValueError('请确认选中的是可用于写作的公开或合成材料')
    service.ledger.export(review,actor)
    view=material(service.store,project,review)
    if view['screening_event_hash']!=screening_event_hash or view['mapping_event_hash']!=mapping_event_hash:raise ValueError('裁决或映射已更新，请重新加载报告')
    row=next((r for r in view['records'] if r['record_id']==record_id),None)
    if row is None:raise ValueError('只能选择本批次最终纳入的全文报告')
    from .writer import WriterService
    record=row['record'];source=record.get('title','')+' · '+(record.get('doi') or record.get('pmid') or record['report_id'])
    return WriterService(service.store).persist(project,'document',{'source':source,'classification':classification,'classification_assurance':'adjudicator_declared','snapshot':record['fulltext'],'origin':'native_hunter','native_hunter':row['binding'],'captured_by':actor,'screening_inclusion':'included_in_selected_fulltext_version','parent_changed_at_capture':view['parent_changed']})


def verify(store,project,obj):
    binding=obj['native_hunter'];view=material(store,project,binding['review_id'])
    row=next((r for r in view['records'] if r['record_id']==binding['record_id']),None)
    if row is None or row['binding']!=binding:raise ValueError('全文裁决或研究映射已变化，请重新捕获证据并审核新稿')
