import copy,csv,io,tempfile,unittest
from workbench.core import Store
from workbench.screening import ScreeningLedger
from workbench.screening_exports import export_csv,REASON_CODES,REASON_VERSION,safe_cell
class ScreeningExportTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.store=Store(self.tmp.name);self.pid=self.store.create('Synthetic')
        self.store.save(self.pid,'source.json',{'records':[{'title':'=FORMULA(1)','pmid':'1'},{'title':'中文, "引号"\n换行','pmid':'2'}]})
        self.l=ScreeningLedger(self.store);self.p=dict(question='Synthetic',stage='title_abstract',inclusion='Adult',exclusion='Other',human_reviewer='human',llm_reviewer='model',adjudicator='human',reason_codes=copy.deepcopy(REASON_CODES),reason_codebook_version=REASON_VERSION)
        self.r=self.l.prepare(self.pid,'source.json',self.p,'admin');self.l.approve(self.r,'human',True)
        self.d=[dict(record_id='r000001',decision='exclude',reason_code='population',reason='Child population',locator='abstract'),dict(record_id='r000002',decision='uncertain',reason='No abstract',locator='title')]
    def reveal(self):
        self.l.submit(self.r,'human',self.d,{'type':'human_manual'});self.l.submit(self.r,'model',self.d,dict(model='synthetic',parameters={},prompt='fixture',raw_response='fixture',run_id='fixture'));self.l.reveal(self.r,'human')
    def test_code_required_and_unknown(self):
        for code in ['', 'unknown']:
            rows=copy.deepcopy(self.d);rows[0]['reason_code']=code
            with self.assertRaises(ValueError):self.l.submit(self.r,'human',rows,{'type':'human_manual'})
        rows=copy.deepcopy(self.d);rows[1]['reason_code']='other'
        with self.assertRaises(ValueError):self.l.submit(self.r,'human',rows,{'type':'human_manual'})
    def test_codebook_frozen(self):
        self.p['reason_codes']['population']='Changed later'
        self.assertEqual(self.l.ballot(self.r,'human')['protocol']['reason_codes']['population'],'研究对象不符')
    def test_csv_revisions_pending_and_escaping(self):
        self.reveal();self.l.adjudicate(self.r,'human','r000001','exclude','Child','population')
        self.l.adjudicate(self.r,'human','r000001','include','Corrected after review')
        audit=self.l.export(self.r,'human');out=export_csv(audit)
        self.assertEqual(out['pending_final'],1)
        rows=list(csv.DictReader(io.StringIO(out['files'][0]['content'].lstrip('\ufeff'))))
        self.assertEqual(len(rows),2);self.assertEqual(rows[0]['title'],"'=FORMULA(1)");self.assertEqual(rows[0]['final_reason_code'],'');self.assertEqual(rows[0]['final_decision'],'include');self.assertEqual(rows[1]['final_status'],'pending');self.assertEqual(rows[1]['title'],'中文, "引号"\n换行')
        history=list(csv.DictReader(io.StringIO(out['files'][1]['content'].lstrip('\ufeff'))));self.assertEqual(len(history),6);self.assertEqual([r['reason_code'] for r in history if r['event_kind']=='adjudicated'],['population',''])
        self.assertEqual(audit['events'][0]['data']['records'][0]['record']['title'],'=FORMULA(1)')
    def test_adjudication_code(self):
        self.reveal()
        with self.assertRaises(ValueError):self.l.adjudicate(self.r,'human','r000001','exclude','Reason')
        with self.assertRaises(ValueError):self.l.adjudicate(self.r,'human','r000001','include','Reason','other')
    def test_legacy_free_text(self):
        protocol={k:v for k,v in self.p.items() if k not in ('reason_codes','reason_codebook_version')};r=self.l.prepare(self.pid,'source.json',protocol,'admin');self.l.approve(r,'human',True)
        rows=[{k:v for k,v in row.items() if k!='reason_code'} for row in self.d]
        self.l.submit(r,'human',rows,{'type':'human_manual'});self.l.submit(r,'model',rows,dict(model='fixture',parameters={},prompt='fixture',raw_response='fixture',run_id='fixture'));self.l.reveal(r,'human');self.l.adjudicate(r,'human','r000001','exclude','Legacy free text')
        out=export_csv(self.l.export(r,'human'));self.assertIn('legacy_free_text',out['files'][0]['content'])
    def test_formula_prefixes(self):
        for value in ['=1','+1','-1','@SUM(A1)','  =1','\t1','\r1','\n1']:self.assertTrue(safe_cell(value).startswith("'"))
if __name__=='__main__':unittest.main()
