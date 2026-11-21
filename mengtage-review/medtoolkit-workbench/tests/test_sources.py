import json,tempfile,unittest
from unittest.mock import patch
from workbench.core import Store
from workbench.sources import SourceService,collection_accounting
from workbench.dedup_jobs import digest
from workbench.screening_http import ScreeningService

class SourcesTest(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup);self.store=Store(tmp.name);self.pid=self.store.create('Synthetic source review');self.s=SourceService(self.store)
        self.meta={'database':'Database A','kind':'database','query':'synthetic query','searched_at':'2026-11-21','total_hits':2,'complete':True,'coverage_note':'Synthetic complete import'}
        self.a=[{'title':'Trial one','pmid':'1'},{'title':'Trial two','pmid':'2'}];self.b=[self.a[1],{'title':'Trial three','pmid':'3'}]
    def import_(self,rows=None,**meta):return self.s.import_records(self.pid,{**self.meta,**meta},self.a if rows is None else rows,True)
    def collection(self,ids,parent_id=None):return self.s.create(self.pid,'Synthetic collection',ids,parent_id,'Author selected complete source list',True)
    def run_dedup(self,name):
        raw=json.loads(self.store.artifact(self.pid,name).read_text());jid=self.store.enqueue(self.pid,'deduplicate',{'source_artifact':name,'source_sha256':digest(raw)});return self.store.run(jid)['artifact']
    def test_import_idempotent_and_confirmation(self):
        a=self.import_();b=self.import_();self.assertEqual(a['id'],b['id']);self.assertTrue(b['reused']);self.assertEqual(len(self.s.list(self.pid)['runs']),1)
        with self.assertRaises(ValueError):self.s.import_records(self.pid,self.meta,self.a,False)
    def test_validation_no_unrelated_fields(self):
        for meta in ({'total_hits':1},{'complete':True,'total_hits':None},{'kind':'website'},{'searched_at':'bad'},{'complete':'yes'}):
            with self.assertRaises(ValueError):self.import_(**meta)
        for rows in ([{**self.a[0],'patient_name':'Not allowed'}],[{'title':'','pmid':'1'}],[{'title':'A','doi':'bad'}],[{'title':'A','abstract':'x'*2_000_000}]):
            with self.assertRaises(ValueError):self.import_(rows,total_hits=len(rows))
        self.assertEqual(self.s.list(self.pid)['runs'],[])
    def test_multi_source_dedup_and_origins(self):
        a=self.import_();b=self.import_(self.b,database='Register B',kind='register');c=self.collection([a['id'],b['id']]);data,_=self.s.load(self.pid,c['id'],True)
        self.assertEqual(data['retrieved'],4);self.assertEqual(len(data['record_origins']),4)
        path=self.run_dedup(c['artifact']);dedup=json.loads(self.store.artifact(self.pid,path).read_text());self.assertEqual((dedup['input_count'],dedup['duplicates_removed'],dedup['unique_count']),(4,1,3))
        shared=next(g for g in dedup['groups'] if len(g['source_indices'])==2);ids={data['record_origins'][i-1]['source_id'] for i in shared['source_indices']};self.assertEqual(ids,{a['id'],b['id']})
    def test_incremental_versions_are_full_selections(self):
        a=self.import_();v1=self.collection([a['id']]);original=self.store.artifact(self.pid,v1['artifact']).read_bytes()
        b=self.import_(self.b,database='Database B');v2=self.collection([a['id'],b['id']],v1['id']);data,_=self.s.load(self.pid,v2['id'],True)
        self.assertEqual(data['parent_collection']['id'],v1['id']);self.assertEqual(data['retrieved'],4);self.assertEqual(original,self.store.artifact(self.pid,v1['artifact']).read_bytes())
        replaced=self.collection([b['id']],v2['id']);self.assertEqual(self.s.load(self.pid,replaced['id'],True)[0]['retrieved'],2)
        again=self.collection([b['id'],a['id']],v1['id']);self.assertEqual(again['id'],v2['id'])
    def test_duplicate_and_cross_project_rejected(self):
        a=self.import_()
        with self.assertRaises(ValueError):self.collection([a['id'],a['id']])
        other=self.store.create('Other')
        with self.assertRaises(ValueError):self.s.create(other,'Wrong',[a['id']],None,'Wrong',True)
        with self.assertRaises(ValueError):self.collection([a['id']],parent_id='unknown')
    def test_source_tamper_and_origin_tamper(self):
        a=self.import_();c=self.collection([a['id']]);data,_=self.s.load(self.pid,c['id'],True);data['record_origins'][0]['source_record_index']=2
        with self.assertRaises(ValueError):collection_accounting(self.store,self.pid,data)
        self.store.artifact(self.pid,a['artifact']).write_text('{}')
        with self.assertRaises(ValueError):self.s.load(self.pid,a['id'])
    def test_partial_unknown_and_zero_run(self):
        a=self.import_(total_hits=None,complete=False);z=self.import_([],database='Empty register',kind='register',total_hits=0);c=self.collection([a['id'],z['id']]);data,_=self.s.load(self.pid,c['id'],True);out=collection_accounting(self.store,self.pid,data)
        self.assertIsNone(out['search_total_hits']);self.assertIsNone(out['records_not_downloaded']);self.assertFalse(out['search_complete']);self.assertEqual(len(out['source_breakdown']),2)
    def test_native_capture_requires_completed_search(self):
        def search(store,pid,payload,jid):
            name=store.save(pid,jid+'-search.json',{'query':payload['query'],'records':self.a,'retrieved':2,'total_hits':7,'complete':False})
            return {'artifact':name}
        job=self.store.enqueue(self.pid,'search',{'query':'Synthetic PubMed'})
        with patch('workbench.adapters.search',side_effect=search):name=self.store.run(job)['artifact']
        result=self.s.capture(self.pid,name,True);data,_=self.s.load(self.pid,result['id']);self.assertEqual(data['metadata']['database'],'PubMed');self.assertFalse(data['complete']);self.assertEqual(data['original_sha256'],digest(json.loads(self.store.artifact(self.pid,name).read_text())))
        self.assertEqual(self.s.capture(self.pid,name,True)['id'],result['id'])
        with self.assertRaises(ValueError):self.s.capture(self.pid,result['artifact'],True)
    def test_combined_limit(self):
        rows=[{'title':f'Unique {i}','pmid':str(i+1)} for i in range(501)];a=self.import_(rows,total_hits=501);b=self.import_(rows,database='Other',total_hits=501)
        with self.assertRaises(ValueError):self.collection([a['id'],b['id']])
    def test_collection_to_screening_prisma_lineage(self):
        a=self.import_();b=self.import_(self.b,database='Register B',kind='register');c=self.collection([a['id'],b['id']]);dedup=self.run_dedup(c['artifact'])
        service=ScreeningService(self.store);h=service.access.issue('h','human');m=service.access.issue('m','model')
        protocol={'question':'Synthetic','stage':'title_abstract','inclusion':'Adults','exclusion':'Other','human_reviewer':'h','llm_reviewer':'m','adjudicator':'h'};review=service.prepare(self.pid,dedup,protocol)['review'];service.ledger.approve(review,'h',True)
        rows=[{'record_id':f'r{i:06}','decision':'exclude','reason_code':'population','reason':'Synthetic exclusion','locator':'title'} for i in range(1,4)]
        service.ledger.submit(review,'h',rows,{'type':'human_manual'});service.ledger.submit(review,'m',rows,{'model':'synthetic','parameters':{},'prompt':'Synthetic','raw_response':'Synthetic','run_id':'synthetic'});service.ledger.reveal(review,'h')
        for row in rows:service.ledger.adjudicate(review,'h',**row)
        out=service.prisma.preview(review,'h');self.assertEqual(out['status'],'selected_lineage_complete');self.assertEqual(out['counts']['records_identified'],4);self.assertEqual(out['counts']['duplicates_removed'],1);self.assertEqual(out['counts']['records_screened'],3);self.assertEqual(len(out['source_breakdown']),2)
        origin=out['provenance']['record_source_lineage'];self.assertEqual(sum(len(r['members']) for r in origin),4);self.assertEqual(out['collection']['label'],'Synthetic collection')
