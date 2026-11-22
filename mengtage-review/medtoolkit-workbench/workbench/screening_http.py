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
        from .charting import DataChartingService
        self.studies=StudyService(self);self.prisma=PrismaService(self);self.charting=DataChartingService(self)
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
        allowed={'writer_candidates':{'review','project'},'writer_capture':{'review','project','record_id','screening_event_hash','mapping_event_hash','classification','confirmed'},'writer_auto_package':{'review','project','confirmed'},'approve':{'review','confirmed'},'ballot':{'review'},'state':{'review'},'submit':{'review','decisions','provenance'},
            'auto_screen':{'review'},'batch_adjudicate':{'review','confirmed'},
            'reveal':{'review'},'adjudicate':{'review','record_id','decision','reason'},'export':{'review'},'export_csv':{'review'},
            'fulltext_status':{'review'},'fulltext_register':{'review','record_id','status','reason'},'fulltext_batch_register':{'review'},
            'fulltext_prepare':{'review','protocol'},'fulltext_file':{'review','record_id'},
            'study_state':{'review'},'study_save':{'review','mappings','screening_event_hash','mapping_event_hash','confirmed'},'study_auto_suggest':{'review'},
            'chart_state':{'review'},'chart_extract':{'review'},'chart_save':{'review','charting','screening_event_hash','mapping_event_hash','confirmed'},
            'prisma_preview':{'review'},'prisma_export':{'review','expected_sha256'}}
        optional={'reason_code','locator','quote'} if operation=='adjudicate' else {'filename','content_base64'} if operation=='fulltext_register' else {'mode','submit'} if operation=='auto_screen' else {'default_for_disagreement'} if operation=='batch_adjudicate' else {'mode','items'} if operation=='fulltext_batch_register' else {'label','classification','include_statistics'} if operation=='writer_auto_package' else {'mode','save'} if operation=='chart_extract' else {'charting_event_hash'} if operation=='chart_save' else set()
        fields=set(body)-optional
        if operation not in allowed or fields!=allowed[operation]:raise ValueError('筛选请求字段无效；身份由令牌决定')
        if not isinstance(body['review'],str):raise ValueError('批次ID无效')
        self.events(body['review'],actor)
        if operation=='writer_auto_package':
            from .writer import WriterService
            from .writer_autopilot import batch_capture_and_freeze_evidence
            return batch_capture_and_freeze_evidence(
                WriterService(self.store),
                self,
                project=body['project'],
                review=body['review'],
                actor=actor,
                label=body.get('label','综述与统计综合证据包'),
                classification=body.get('classification','public'),
                include_statistics=body.get('include_statistics',True),
                confirmed=body['confirmed'],
            )
        if operation=='auto_screen':
            from .screening_autopilot import generate_screening_decisions
            ballot=self.ledger.ballot(body['review'],actor)
            decisions,provenance=generate_screening_decisions(ballot,body.get('mode','auto'))
            if body.get('submit') is True:
                prov=provenance if actor==ballot['protocol']['llm_reviewer'] else {'type':'human_manual'}
                ev_hash=self.ledger.submit(body['review'],actor,decisions,prov)
                return {'event_hash':ev_hash,'decisions':decisions,'provenance':provenance,'submitted':True}
            return {'decisions':decisions,'provenance':provenance,'submitted':False}
        if operation=='batch_adjudicate':
            if body.get('confirmed') is not True:raise ValueError('请确认批量裁决')
            audit=self.ledger.export(body['review'],actor)
            draft=audit['events'][0]['data'];protocol=draft['protocol'];is_full=protocol['stage']=='full_text'
            submissions={e['actor']:{r['record_id']:r for r in e['data']['decisions']} for e in audit['events'] if e['kind']=='submitted'}
            h_map=submissions.get(protocol['human_reviewer'],{});m_map=submissions.get(protocol['llm_reviewer'],{})
            fallback=body.get('default_for_disagreement','human')
            adjudicated=[]
            for item in draft['records']:
                rid=item['record_id'];h_dec=h_map.get(rid,{});m_dec=m_map.get(rid,{})
                if h_dec.get('decision') in ('include','exclude') and h_dec.get('decision')==m_dec.get('decision'):
                    chosen=h_dec;reason=f"双人独立判断一致（{chosen['decision']}）：{chosen.get('reason','')}"
                elif fallback=='human' and h_dec.get('decision') in ('include','exclude'):
                    chosen=h_dec;reason=f"裁决采纳人类评审判断（{chosen['decision']}）：{chosen.get('reason','')}"
                elif fallback=='include_if_any' and 'include' in (h_dec.get('decision'),m_dec.get('decision')):
                    chosen=h_dec if h_dec.get('decision')=='include' else m_dec
                    reason=f"保全式裁决纳入：{chosen.get('reason','')}"
                else:
                    continue
                kw={'review':body['review'],'actor':actor,'record_id':rid,'decision':chosen['decision'],'reason':reason[:2000]}
                if chosen['decision']=='exclude' and chosen.get('reason_code'):kw['reason_code']=chosen['reason_code']
                if is_full:
                    kw['locator']=chosen.get('locator') or 'p:1'
                    kw['quote']=chosen.get('quote') or ''
                ev_hash=self.ledger.adjudicate(**kw)
                adjudicated.append({'record_id':rid,'decision':chosen['decision'],'event_hash':ev_hash})
            return {'adjudicated_count':len(adjudicated),'adjudicated':adjudicated}
        if operation=='fulltext_batch_register':
            from .screening_autopilot import batch_register_fulltext
            return batch_register_fulltext(self.fulltext,body['review'],actor,mode=body.get('mode','auto_snapshot'),items=body.get('items'))
        if operation=='study_auto_suggest':
            from .screening_autopilot import suggest_study_mappings
            return suggest_study_mappings(self.studies,body['review'],actor)
        if operation in ('writer_candidates','writer_capture'):
            from . import writer_hunter
            return getattr(writer_hunter,operation.removeprefix('writer_'))(self,actor=actor,**body)
        if operation=='prisma_preview':
            from .fulltext import json_hash
            report=self.prisma.preview(body['review'],actor);return {'report':report,'sha256':json_hash(report)}
        if operation=='prisma_export':return self.prisma.export(actor=actor,**body)
        if operation.startswith('chart_'):return getattr(self.charting,operation.removeprefix('chart_'))(actor=actor,**body)
        if operation.startswith('study_'):return getattr(self.studies,operation.removeprefix('study_'))(actor=actor,**body)
        if operation.startswith('fulltext_'):return getattr(self.fulltext,operation.removeprefix('fulltext_'))(actor=actor,**body)
        if operation=='state':return self.state(body['review'],actor)
        if operation=='export_csv':
            from .screening_exports import export_csv
            return export_csv(self.ledger.export(body['review'],actor))
        result=getattr(self.ledger,operation)(actor=actor,**body)
        return {'event_hash':result} if isinstance(result,str) else result
