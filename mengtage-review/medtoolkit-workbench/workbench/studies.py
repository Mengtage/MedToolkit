"""Human-confirmed many-to-many report/study mapping; revisions never overwrite."""
import json
import re
import uuid
from .core import canonical,now
from .fulltext import json_hash,validate_evidence

class StudyService:
    def __init__(self,service):
        self.service=service;self.store=service.store
        with self.store.db() as db:db.execute('CREATE TABLE IF NOT EXISTS study_events(sequence INTEGER PRIMARY KEY AUTOINCREMENT, review TEXT NOT NULL, event TEXT NOT NULL)')
    def audit(self,review,actor):
        audit=self.service.ledger.export(review,actor)
        if audit['events'][0]['data']['protocol']['stage']!='full_text':raise ValueError('研究映射须选择全文批次')
        return audit
    def events(self,review,db=None):
        if db is None:
            with self.store.db() as db:return self.events(review,db)
        events=[json.loads(r[0]) for r in db.execute('SELECT event FROM study_events WHERE review=? ORDER BY sequence',(review,))];previous=''
        for event in events:
            if event['previous_hash']!=previous or json_hash({k:v for k,v in event.items() if k!='event_hash'})!=event['event_hash']:raise ValueError('研究映射审计链损坏')
            previous=event['event_hash']
        return events
    def state(self,review,actor):
        audit=self.audit(review,actor);events=self.events(review);last=events[-1] if events else None
        valid=bool(last and last['screening_event_hash']==audit['events'][-1]['event_hash'])
        included={r['record_id'] for r in audit['final_decisions'] if r['decision']=='include'}
        rows=[{'record_id':r['record_id'],'report_id':r['record']['report_id'],'title':r['record'].get('title',''),'record':r['record']} for r in audit['events'][0]['data']['records'] if r['record_id'] in included]
        return {'review':review,'pending_final':audit['pending_final'],'screening_event_hash':audit['events'][-1]['event_hash'],
            'mapping_event_hash':last['event_hash'] if last else '', 'mapping_valid':valid,'records':rows,'mappings':last['mappings'] if valid else [],'history':events}
    def save(self,review,actor,mappings,screening_event_hash,mapping_event_hash,confirmed):
        if confirmed is not True:raise ValueError('请人工确认报告与研究的关联')
        audit=self.audit(review,actor)
        if audit['pending_final']:raise ValueError('请先完成全部全文裁决')
        if not isinstance(mappings,list):raise ValueError('需要报告研究映射列表')
        included={r['record_id'] for r in audit['final_decisions'] if r['decision']=='include'}
        records={r['record_id']:r['record'] for r in audit['events'][0]['data']['records']};seen=set()
        for row in mappings:
            if not isinstance(row,dict) or set(row)!={'record_id','study_ids','reason','locator','quote'}:raise ValueError('研究映射字段无效')
            rid=row['record_id']
            if not isinstance(rid,str) or rid not in included or rid in seen:raise ValueError('映射须覆盖每篇最终纳入报告且不可重复')
            seen.add(rid);ids=row['study_ids']
            if not isinstance(ids,list) or not 1<=len(ids)<=100 or any(not isinstance(v,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,80}',v) for v in ids) or len(set(ids))!=len(ids):raise ValueError('研究ID须唯一且为1至80位字母、数字、横线或下划线')
            if not isinstance(row['reason'],str) or not 1<=len(row['reason'].strip())<=2000:raise ValueError('需说明关联依据或修订理由')
            validate_evidence(records[rid],row['locator'],row['quote'])
        if seen!=included:raise ValueError('不能遗漏最终纳入报告的研究归属')
        with self.store.db() as db:
            db.execute('BEGIN IMMEDIATE');current=self.service.ledger._events(db,review);events=self.events(review,db)
            if current[-1]['event_hash']!=screening_event_hash or audit['events'][-1]['event_hash']!=screening_event_hash:raise ValueError('全文裁决已变化，请刷新后重新核对')
            if (events[-1]['event_hash'] if events else '')!=mapping_event_hash:raise ValueError('映射已有新版本，请刷新后再修订')
            event={'event_id':uuid.uuid4().hex,'review_id':review,'actor':actor,'timestamp':now(),'screening_event_hash':screening_event_hash,
                'mappings':mappings,'previous_hash':mapping_event_hash,'scope':'study_ids_local_to_selected_review'}
            event['event_hash']=json_hash(event);db.execute('INSERT INTO study_events(review,event) VALUES(?,?)',(review,canonical(event)))
        return {'event_hash':event['event_hash']}
