"""Restricted HTTP-facing operations; actor always comes from a credential."""
import json
from .screening import ScreeningLedger
from .review_access import ReviewAccess

class ScreeningService:
    def __init__(self,store):
        self.store=store;self.ledger=ScreeningLedger(store);self.access=ReviewAccess(store)
        from .fulltext import FulltextService
        self.fulltext=FulltextService(self)
        from .studies import StudyService
        from .prisma import PrismaService
        self.studies=StudyService(self);self.prisma=PrismaService(self)
    def prepare(self,project,source_artifact,protocol):
        if not isinstance(protocol,dict):raise ValueError('需要筛选方案')
        from .screening_exports import REASON_CODES,REASON_VERSION
        protocol=dict(protocol)
        if 'reason_codes' not in protocol:
            protocol['reason_codes']=dict(REASON_CODES);protocol['reason_codebook_version']=REASON_VERSION
        if protocol.get('stage')!='title_abstract':raise ValueError('全文批次须从已完成的题名摘要批次准备')
        self.access.validate_protocol(protocol)
        source=json.loads(self.store.artifact(project,source_artifact).read_text())
        if (not isinstance(source,dict) or source.get('method')!='deduplication' or
                not isinstance(source.get('review_candidates'),list) or
                any(not isinstance(c,dict) or not c.get('resolution') for c in source['review_candidates'])):
            raise ValueError('请选择已完成冲突处理的去重产物')
        return {'review':self.ledger.prepare(project,source_artifact,protocol,'administrator',identity_assurance='scoped_reviewer_token')}
    def events(self,review,actor):
        with self.store.db() as db:events=self.ledger._events(db,review)
        protocol=events[0]['data']['protocol']
        if actor not in [protocol[k] for k in ('human_reviewer','llm_reviewer','adjudicator')]:raise PermissionError('不属于此筛选批次')
        return events
    def list(self,actor):
        with self.store.db() as db:ids=[r[0] for r in db.execute('SELECT DISTINCT review FROM screening_events')]
        result=[]
        for review in ids:
            try:events=self.events(review,actor)
            except PermissionError:continue
            result.append({'review':review,'question':events[0]['data']['protocol']['question']})
        return result
    def state(self,review,actor):
        events=self.events(review,actor);draft=events[0]['data'];protocol=draft['protocol']
        parent_changed=False
        if draft.get('lineage'):
            with self.store.db() as db:parent=self.ledger._events(db,draft['lineage']['parent_review_id'])
            parent_changed=parent[-1]['event_hash']!=draft['lineage']['parent_event_hash']
        # Return no decision, rationale, raw response or submitter timing before reveal.
        return {'review':review,'parent_changed':parent_changed,'protocol':protocol,'protocol_sha256':draft['protocol_sha256'],
            'lineage':{k:v for k,v in draft.get('lineage',{}).items() if k in ('parent_review_id','parent_event_hash','reports_sought','reports_retrieved')},
            'source_artifact':draft['source_artifact'],'source_sha256':draft['source_sha256'],
            'checkpoint_records':draft['records'] if protocol['stage']=='full_text' and actor==protocol['human_reviewer'] else [],
            'record_count':len(draft['records']),'material_titles':[{'record_id':r['record_id'],'title':r['record'].get('title','')} for r in draft['records']],'approved':any(e['kind']=='approved' for e in events),
            'own_submitted':any(e['kind']=='submitted' and e['actor']==actor for e in events),
            'ready_to_reveal':sum(e['kind']=='submitted' for e in events)==2,
            'revealed':any(e['kind']=='revealed' for e in events)}
    def dispatch(self,operation,body,principal):
        actor=principal['actor']
        allowed={'writer_candidates':{'review','project'},'writer_capture':{'review','project','record_id','screening_event_hash','mapping_event_hash','classification','confirmed'},'approve':{'review','confirmed'},'ballot':{'review'},'state':{'review'},'submit':{'review','decisions','provenance'},
            'reveal':{'review'},'adjudicate':{'review','record_id','decision','reason'},'export':{'review'},'export_csv':{'review'},
            'fulltext_status':{'review'},'fulltext_register':{'review','record_id','status','reason'},
            'fulltext_prepare':{'review','protocol'},'fulltext_file':{'review','record_id'},
            'study_state':{'review'},'study_save':{'review','mappings','screening_event_hash','mapping_event_hash','confirmed'},
            'prisma_preview':{'review'},'prisma_export':{'review','expected_sha256'}}
        fields=set(body)-({'reason_code','locator','quote'} if operation=='adjudicate' else {'filename','content_base64'} if operation=='fulltext_register' else set())
        if operation not in allowed or fields!=allowed[operation]:raise ValueError('筛选请求字段无效；身份由令牌决定')
        if not isinstance(body['review'],str):raise ValueError('批次ID无效')
        self.events(body['review'],actor)
        if operation in ('writer_candidates','writer_capture'):
            from . import writer_hunter
            return getattr(writer_hunter,operation.removeprefix('writer_'))(self,actor=actor,**body)
        if operation=='prisma_preview':
            from .fulltext import json_hash
            report=self.prisma.preview(body['review'],actor);return {'report':report,'sha256':json_hash(report)}
        if operation=='prisma_export':return self.prisma.export(actor=actor,**body)
        if operation.startswith('study_'):return getattr(self.studies,operation.removeprefix('study_'))(actor=actor,**body)
        if operation.startswith('fulltext_'):return getattr(self.fulltext,operation.removeprefix('fulltext_'))(actor=actor,**body)
        if operation=='state':return self.state(body['review'],actor)
        if operation=='export_csv':
            from .screening_exports import export_csv
            return export_csv(self.ledger.export(body['review'],actor))
        result=getattr(self.ledger,operation)(actor=actor,**body)
        return {'event_hash':result} if isinstance(result,str) else result
