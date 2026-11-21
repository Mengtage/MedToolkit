"""Review audit ledger. HTTP callers use scoped credentials; local CLI is trusted.

No LLM calls. Draft -> explicit approval -> independent submissions -> reveal -> adjudicate.
HTTP permissions are enforced in screening_http; administrator/disk access remains trusted.
"""
import hashlib
import json
import sqlite3
import uuid
from .core import canonical, now

class ScreeningLedger:
    def __init__(self, store):
        self.store = store
        with store.db() as db:
            db.execute('CREATE TABLE IF NOT EXISTS screening_events (sequence INTEGER PRIMARY KEY AUTOINCREMENT, review TEXT NOT NULL, project TEXT NOT NULL, event TEXT NOT NULL)')

    def _events(self, db, review):
        rows=db.execute('SELECT event FROM screening_events WHERE review=? ORDER BY sequence',(review,)).fetchall()
        if not rows:raise ValueError('筛选批次不存在')
        events=[json.loads(r[0]) for r in rows]
        previous=''
        for e in events:
            content={k:v for k,v in e.items() if k!='event_hash'}
            if e['previous_hash']!=previous or self._hash(content)!=e['event_hash']:
                raise ValueError('审计链校验失败')
            previous=e['event_hash']
        return events

    @staticmethod
    def _hash(value):return hashlib.sha256(canonical(value).encode()).hexdigest()

    def _append(self, db, project, review, kind, actor, data, previous=''):
        if not isinstance(actor,str) or not actor.strip():raise ValueError('需要记录操作者')
        event={'review_id':review,'project_id':project,'event_id':uuid.uuid4().hex,'kind':kind,
               'actor':actor,'timestamp':now(),'data':data,'previous_hash':previous}
        event['event_hash']=self._hash(event)
        db.execute('INSERT INTO screening_events(review,project,event) VALUES(?,?,?)',(review,project,canonical(event)))
        return event['event_hash']

    def prepare(self, project, source_artifact, protocol, actor, identity_assurance="caller_declared_local_only"):
        self.store.project(project)
        if not isinstance(protocol,dict):raise ValueError('需要筛选方案')
        required={'question','stage','inclusion','exclusion','human_reviewer','llm_reviewer','adjudicator'}
        if set(protocol)-{'reason_codes','reason_codebook_version'}!=required:raise ValueError('方案字段不完整或含额外字段')
        if 'reason_codes' in protocol:
            codes=protocol['reason_codes']
            if not isinstance(codes,dict) or not 1<=len(codes)<=40 or any(not isinstance(k,str) or not k or not isinstance(v,str) or not v.strip() for k,v in codes.items()):raise ValueError('原因词表须为非空代码与说明映射（最多40项）')
            if not isinstance(protocol.get('reason_codebook_version'),str) or not protocol['reason_codebook_version'].strip():raise ValueError('需记录原因词表版本')
        elif 'reason_codebook_version' in protocol:raise ValueError('缺少原因词表')
        if protocol['stage'] not in ('title_abstract','full_text'):raise ValueError('筛选阶段无效')
        if any(not isinstance(protocol[k],str) or not protocol[k].strip() for k in required):raise ValueError('方案字段不得为空')
        if len({protocol['human_reviewer'],protocol['llm_reviewer'],protocol['adjudicator']})<2 or protocol['human_reviewer']==protocol['llm_reviewer']:
            raise ValueError('人类和LLM必须为不同评审者')
        source=json.loads(self.store.artifact(project,source_artifact).read_text())
        records=source.get('records')
        if not isinstance(records,list) or not records or any(not isinstance(r,dict) for r in records):raise ValueError('需要非空文献记录')
        if protocol['stage']=='full_text':
            from .fulltext import validate_snapshot
            if source.get('method')!='fulltext_manifest' or not isinstance(source.get('lineage'),dict):raise ValueError('全文需使用已登记的固定快照')
            for record in records:
                validate_snapshot(record.get('fulltext'))
                if not all(record.get(k) for k in ('parent_review_id','parent_record_id','report_id')):raise ValueError('缺少跨阶段来源关联')
        # Freeze material and numbering; do not edit the source artifact or infer dedup approval.
        snapshot=[{'record_id':f'r{i+1:06d}','record':record,'record_sha256':self._hash(record)} for i,record in enumerate(records)]
        data={'source_artifact':source_artifact,'source_sha256':self._hash(source),'protocol':protocol,
              'protocol_sha256':self._hash(protocol),'records':snapshot,'identity_assurance':identity_assurance}
        review=uuid.uuid4().hex
        with self.store.db() as db:
            db.execute('BEGIN IMMEDIATE')
            if protocol['stage']=='full_text':
                lineage=source['lineage'];parent=self._events(db,lineage['parent_review_id'])
                if parent[0]['project_id']!=project or parent[-1]['event_hash']!=lineage['parent_event_hash']:raise ValueError('父批次已变化，请刷新后重新准备')
                retrieval=db.execute('SELECT event FROM fulltext_events WHERE parent_review=? ORDER BY sequence DESC LIMIT 1',(lineage['parent_review_id'],)).fetchone()
                if not retrieval or json.loads(retrieval[0])['event_hash']!=lineage['retrieval_events'][-1]['event_hash']:raise ValueError('全文取得登记已变化，请重新准备')
                data['lineage']=lineage
            self._append(db,project,review,'prepared',actor,data)
        return review

    def approve(self, review, actor, confirmed=False):
        with self.store.db() as db:
            db.execute('BEGIN IMMEDIATE');ev=self._events(db,review);draft=ev[0]['data']
            if confirmed is not True or actor!=draft['protocol']['human_reviewer']:raise ValueError('需要指定人类作者明确批准')
            if len(ev)!=1:raise ValueError('批次已批准或已开始')
            return self._append(db,ev[0]['project_id'],review,'approved',actor,
                {'protocol_sha256':draft['protocol_sha256'],'source_sha256':draft['source_sha256']},ev[-1]['event_hash'])

    def ballot(self, review, actor):
        with self.store.db() as db:ev=self._events(db,review)
        d=ev[0]['data'];p=d['protocol']
        if not any(e['kind']=='approved' for e in ev):raise ValueError('人工checkpoint尚未批准')
        if actor not in (p['human_reviewer'],p['llm_reviewer']):raise ValueError('不在评审者名单')
        # Never include other decisions or rationale in a reviewer's ballot/prompt.
        return {'review_id':review,'protocol':p,'protocol_sha256':d['protocol_sha256'],'records':[{'record_id':r['record_id'],'record_sha256':r['record_sha256'],'record':{k:v for k,v in r['record'].items() if k in ('title','abstract','pmid','doi','authors','journal','pub_date','fulltext','parent_review_id','parent_record_id','report_id')}} for r in d['records']]}

    def submit(self, review, actor, decisions, provenance):
        with self.store.db() as db:
            db.execute('BEGIN IMMEDIATE');ev=self._events(db,review);d=ev[0]['data'];p=d['protocol']
            if not any(e['kind']=='approved' for e in ev):raise ValueError('人工checkpoint尚未批准')
            if actor not in (p['human_reviewer'],p['llm_reviewer']):raise ValueError('不在评审者名单')
            if any(e['kind']=='submitted' and e['actor']==actor for e in ev):raise ValueError('已锁定提交；修改须新批次，不覆盖原判断')
            expected={r['record_id'] for r in d['records']}
            if not isinstance(decisions,list) or len(decisions)!=len(expected):raise ValueError('必须逐条完成，缺项不能默认为排除')
            ids=[]
            for row in decisions:
                if not isinstance(row,dict) or set(row)-{'reason_code','quote'}!={'record_id','decision','reason','locator'}:raise ValueError('判断字段无效')
                if row['decision'] not in ('include','exclude','uncertain'):raise ValueError('判断无效')
                if any(not isinstance(row[k],str) or not row[k].strip() for k in ('record_id','decision','reason','locator')):raise ValueError('理由/证据位置等字段不可为空')
                from .screening_exports import validate_reason
                validate_reason(row['decision'],row.get('reason_code',''),p)
                if p['stage']=='full_text':
                    from .fulltext import validate_evidence
                    item=next((r for r in d['records'] if r['record_id']==row['record_id']),None)
                    if item is None:raise ValueError('文献ID无效')
                    validate_evidence(item['record'],row['locator'],row.get('quote'))
                ids.append(row['record_id'])
            if len(set(ids))!=len(ids) or set(ids)!=expected:raise ValueError('文献ID重复或不属于此批次')
            if not isinstance(provenance,dict):raise ValueError('需要来源记录')
            if actor==p['llm_reviewer']:
                fields={'model','parameters','prompt','raw_response','run_id'}
                if set(provenance)!=fields or any(not provenance[k] for k in ('model','prompt','raw_response','run_id')):raise ValueError('模型来源需完整记录型号、参数、实际提示、原始响应与运行ID')
                if not isinstance(provenance['parameters'],dict):raise ValueError('模型参数须为对象')
            elif provenance!={'type':'human_manual'}:raise ValueError('人工判断须标记human_manual')
            return self._append(db,ev[0]['project_id'],review,'submitted',actor,
                {'decisions':decisions,'provenance':provenance,'protocol_sha256':d['protocol_sha256']},ev[-1]['event_hash'])

    def reveal(self, review, actor):
        with self.store.db() as db:
            db.execute('BEGIN IMMEDIATE');ev=self._events(db,review);p=ev[0]['data']['protocol']
            if actor!=p['adjudicator']:raise ValueError('需要指定裁决者')
            submissions=[e for e in ev if e['kind']=='submitted']
            if len(submissions)!=2:raise ValueError('双方完整提交锁定后才能揭盲')
            if not any(e['kind']=='revealed' for e in ev):
                self._append(db,ev[0]['project_id'],review,'revealed',actor,{},ev[-1]['event_hash'])
            return {e['actor']:e['data']['decisions'] for e in submissions}

    def adjudicate(self, review, actor, record_id, decision, reason, reason_code="", locator="", quote=""):
        with self.store.db() as db:
            db.execute('BEGIN IMMEDIATE');ev=self._events(db,review);d=ev[0]['data']
            if actor!=d['protocol']['adjudicator'] or not any(e['kind']=='revealed' for e in ev):raise ValueError('须揭盲后由裁决者确认')
            if record_id not in {r['record_id'] for r in d['records']}:raise ValueError('文献ID无效')
            if decision not in ('include','exclude') or not isinstance(reason,str) or not reason.strip():raise ValueError('需最终判断及理由')
            from .screening_exports import validate_reason
            validate_reason(decision,reason_code,d['protocol'])
            if d['protocol']['stage']=='full_text':
                from .fulltext import validate_evidence
                record=next(r['record'] for r in d['records'] if r['record_id']==record_id)
                validate_evidence(record,locator,quote)
            # Revisions append another event; original decisions remain immutable through this API.
            return self._append(db,ev[0]['project_id'],review,'adjudicated',actor,
                {'record_id':record_id,'decision':decision,'reason':reason,**({'locator':locator,'quote':quote} if d['protocol']['stage']=='full_text' else {}),**({'reason_code':reason_code} if reason_code else {})},ev[-1]['event_hash'])

    def export(self, review, actor):
        with self.store.db() as db:ev=self._events(db,review)
        if actor!=ev[0]['data']['protocol']['adjudicator'] or not any(e['kind']=='revealed' for e in ev):raise ValueError('审计导出须揭盲后由裁决者执行')
        final={e['data']['record_id']:e['data'] for e in ev if e['kind']=='adjudicated'}
        return {'review_id':review,'events':ev,'final_decisions':list(final.values()),
                'pending_final':len(ev[0]['data']['records'])-len(final),
                'integrity':'hash_chain_verified; no_external_anchor; administrator_and_disk_access_trusted'}
