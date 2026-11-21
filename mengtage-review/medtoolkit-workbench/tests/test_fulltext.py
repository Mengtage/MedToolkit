import base64,json,tempfile,unittest
from copy import deepcopy
from workbench.core import Store
from workbench.screening_http import ScreeningService
from workbench.fulltext import snapshot,validate_snapshot


def synthetic_pdf():
    stream=b'BT /F1 12 Tf 72 720 Td (Synthetic adult randomized trial.) Tj ET'
    objects=[b'<< /Type /Catalog /Pages 2 0 R >>',b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>',b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>',b'<< /Length '+str(len(stream)).encode()+b' >>\nstream\n'+stream+b'\nendstream']
    raw=b'%PDF-1.4\n';offsets=[0]
    for i,obj in enumerate(objects,1):offsets.append(len(raw));raw+=str(i).encode()+b' 0 obj\n'+obj+b'\nendobj\n'
    start=len(raw);raw+=b'xref\n0 6\n0000000000 65535 f \n'
    raw+=b''.join(f'{offset:010d} 00000 n \n'.encode() for offset in offsets[1:])
    return raw+b'trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n'+str(start).encode()+b'\n%%EOF\n'

class FulltextTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup);self.store=Store(tmp.name);self.s=ScreeningService(self.store);self.pid=self.store.create('Synthetic')
        self.h=self.s.access.issue('human','human');self.m=self.s.access.issue('model','model');self.x=self.s.access.issue('other','human')
        self.protocol=dict(question='Synthetic',stage='title_abstract',inclusion='Adults',exclusion='Children',human_reviewer='human',llm_reviewer='model',adjudicator='human')
        self.store.save(self.pid,'dedup.json',{'method':'deduplication','records':[{'title':'A'},{'title':'B'}],'review_candidates':[]})
        self.parent=self.s.prepare(self.pid,'dedup.json',self.protocol)['review'];self.r=self.parent
        self.provenance={'model':'synthetic','parameters':{},'prompt':'Synthetic','raw_response':'Synthetic','run_id':'synthetic'}
        self.call('approve',confirmed=True)
        rows=[{'record_id':rid,'decision':'include','reason':'PARENT_SECRET','locator':'title'} for rid in ('r000001','r000002')]
        self.call('submit',decisions=rows,provenance={'type':'human_manual'});self.call('submit',self.m,decisions=rows,provenance=self.provenance);self.call('reveal')
        for row in rows:self.call('adjudicate',record_id=row['record_id'],decision='include',reason='PARENT_SECRET')
    def call(self,op,actor=None,**body):return self.s.dispatch(op,{'review':self.r,**body},actor or self.h)
    def register(self):
        self.call('fulltext_register',record_id='r000001',status='retrieved',reason='Supplied synthetic PDF',filename='fixture.pdf',content_base64=base64.b64encode(synthetic_pdf()).decode())
        self.call('fulltext_register',record_id='r000002',status='not_retrieved',reason='Synthetic unavailable report')
    def child(self):
        self.register();self.r=self.call('fulltext_prepare',protocol=self.protocol)['review'];return self.r
    def test_pdf_and_text_snapshot_integrity(self):
        doc=snapshot(self.store,self.pid,'fixture.pdf',base64.b64encode(synthetic_pdf()).decode());validate_snapshot(doc)
        self.assertIn('Synthetic adult randomized trial.',doc['pages'][0]['text']);self.assertEqual(doc['extraction']['page_numbering'],'physical_pdf_pages_1_based')
        text=snapshot(self.store,self.pid,'中文.txt',base64.b64encode('第一页\f第二页'.encode()).decode());self.assertEqual(len(text['pages']),2)
        self.assertEqual(text['extraction']['page_numbering'],'form_feed_segments_not_original_pdf_pages')
        text['pages'][0]['text']='tamper'
        with self.assertRaises(ValueError):validate_snapshot(text)
    def test_retrieval_permission_and_required_status(self):
        with self.assertRaises(ValueError):self.call('fulltext_status',self.m)
        with self.assertRaises(PermissionError):self.call('fulltext_status',self.x)
        with self.assertRaises(ValueError):self.call('fulltext_prepare',protocol=self.protocol)
        with self.assertRaises(ValueError):self.call('fulltext_register',record_id='unknown',status='not_retrieved',reason='No report')
        self.assertTrue(all(r['status']=='pending' for r in self.call('fulltext_status')['records']))
    def test_file_validation_and_unretrieved(self):
        for name,raw in [('x.pdf',b'not pdf'),('x.txt',b'  '),('x.exe',b'x'),('../x.txt',b'x'),('x.txt',b'\xff')]:
            with self.subTest(name=name),self.assertRaises(ValueError):snapshot(self.store,self.pid,name,base64.b64encode(raw).decode())
        for rid in ('r000001','r000002'):self.call('fulltext_register',record_id=rid,status='not_retrieved',reason='Unavailable')
        with self.assertRaises(ValueError):self.call('fulltext_prepare',protocol=self.protocol)
        self.assertEqual(len(self.call('fulltext_status')['events']),2)
    def test_checkpoint_and_private_parent_rationale(self):
        self.child()
        with self.assertRaises(ValueError):self.call('ballot',self.m)
        with self.assertRaises(ValueError):self.call('fulltext_file',self.m,record_id='r000001')
        self.assertEqual(len(self.call('state')['checkpoint_records']),1)
        self.assertEqual(self.call('state',self.m)['checkpoint_records'],[])
        file=self.call('fulltext_file',record_id='r000001');self.assertEqual(base64.b64decode(file['content_base64']),synthetic_pdf())
        self.call('approve',confirmed=True)
        ballot=self.call('ballot',self.m);self.assertNotIn('PARENT_SECRET',json.dumps(ballot));self.assertNotIn('retrieval_events',json.dumps(ballot))
        self.assertEqual(ballot['records'][0]['record']['parent_review_id'],self.parent)
    def test_quote_validation_and_cross_stage_audit(self):
        self.child();self.call('approve',confirmed=True)
        row=dict(record_id='r000001',decision='include',reason='Adult trial',locator='p:1',quote='Synthetic adult randomized trial.')
        for changes in ({'locator':'p:2'},{'quote':'Invented text'},{'locator':'abstract'},{'record_id':'unknown'}):
            with self.assertRaises(ValueError):self.call('submit',decisions=[{**row,**changes}],provenance={'type':'human_manual'})
        self.call('submit',decisions=[row],provenance={'type':'human_manual'})
        with self.assertRaises(ValueError):self.call('reveal')
        self.call('submit',self.m,decisions=[{**row,'decision':'uncertain'}],provenance=self.provenance);self.call('reveal')
        with self.assertRaises(ValueError):self.call('adjudicate',record_id=row['record_id'],decision='include',reason='No evidence')
        self.call('adjudicate',**row);audit=self.call('export');lineage=audit['events'][0]['data']['lineage']
        self.assertEqual((lineage['reports_sought'],lineage['reports_retrieved'],len(lineage['reports_not_retrieved'])),(2,1,1))
        self.assertEqual(audit['pending_final'],0);self.assertEqual(audit['final_decisions'][0]['quote'],row['quote'])
        csv=self.call('export_csv')['files'];self.assertIn('file_sha256',csv[0]['content']);self.assertIn(row['quote'],csv[0]['content']);self.assertIn(row['quote'],csv[1]['content'])
    def test_parent_revision_invalidates_registration(self):
        self.register();self.call('adjudicate',record_id='r000001',decision='include',reason='Reconfirmed updated reasoning')
        status=self.call('fulltext_status');self.assertEqual(status['records'][0]['status'],'pending')
        with self.assertRaises(ValueError):self.call('fulltext_prepare',protocol=self.protocol)
        self.assertEqual(len(status['events']),2)
        for rid in ('r000001','r000002'):self.call('adjudicate',record_id=rid,decision='exclude',reason='Revised final exclusion',reason_code='population')
        status=self.call('fulltext_status');self.assertEqual(status['records'],[]);self.assertEqual(len(status['events']),2)
    def test_original_tamper_and_retrieval_tamper(self):
        self.child();event=self.s.fulltext.events(self.parent)[0];self.store.artifact(self.pid,event['document']['blob']).write_bytes(b'tampered')
        with self.assertRaises(ValueError):self.call('fulltext_file',record_id='r000001')
        with self.store.db() as db:db.execute("UPDATE fulltext_events SET event=replace(event,'Supplied synthetic PDF','Altered reason')")
        with self.assertRaises(ValueError):self.s.fulltext.events(self.parent)

    def test_child_frozen_after_parent_revision_and_warning(self):
        child=self.child();before=self.call('state')
        self.assertFalse(before['parent_changed'])
        self.s.ledger.adjudicate(self.parent,'human','r000001','exclude','Revised parent','population')
        after=self.call('state');self.assertTrue(after['parent_changed'])
        self.assertEqual(before['source_sha256'],after['source_sha256'])
        self.assertEqual(after['record_count'],1)
    def test_original_tamper_rejected_before_prepare(self):
        self.register();doc=self.s.fulltext.events(self.parent)[0]['document']
        self.store.artifact(self.pid,doc['blob']).write_bytes(b'changed')
        with self.assertRaises(ValueError):self.call('fulltext_prepare',protocol=self.protocol)
