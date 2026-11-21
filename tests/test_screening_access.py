import tempfile,unittest,json
from workbench.core import Store
from workbench.screening_http import ScreeningService

class ScreeningAccessTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.store=Store(self.tmp.name);self.pid=self.store.create('Synthetic review');self.s=ScreeningService(self.store)
        self.h=self.s.access.issue('author','human');self.m=self.s.access.issue('model','model');self.other=self.s.access.issue('other','human')
        self.source={'method':'deduplication','records':[{'title':'Synthetic','abstract':'Example','screening_reason':'must not leak'}],'review_candidates':[]}
        self.store.save(self.pid,'dedup.json',self.source)
        self.protocol=dict(question='Synthetic',stage='title_abstract',inclusion='Adults',exclusion='Wrong population',human_reviewer='author',llm_reviewer='model',adjudicator='author')
        self.r=self.s.prepare(self.pid,'dedup.json',self.protocol)['review']
        self.d=[dict(record_id='r000001',decision='include',reason='meets criteria',locator='abstract')]
    def call(self,op,principal=None,**data):return self.s.dispatch(op,{'review':self.r,**data},principal or self.h)
    def test_hash_credentials_revoke(self):
        self.assertEqual(self.s.access.authenticate(self.h['token'])['actor'],'author')
        self.assertIsNone(self.s.access.authenticate('wrong'))
        with self.store.db() as db:self.assertNotIn(self.h['token'],str(db.execute('SELECT * FROM review_principals').fetchall()))
        self.s.access.revoke('author');self.assertIsNone(self.s.access.authenticate(self.h['token']))
        with self.assertRaises(ValueError):self.s.access.issue('author','human')
    def test_actor_injection_and_cross_batch(self):
        with self.assertRaises(ValueError):self.call('approve',self.m,confirmed=True,actor='author')
        with self.assertRaises(PermissionError):self.call('state',self.other)
        self.assertEqual(self.s.list('other'),[])
    def test_protocol_roles_and_pending_source(self):
        self.protocol['human_reviewer']='model'
        with self.assertRaises(ValueError):self.s.prepare(self.pid,'dedup.json',self.protocol)
        self.protocol['human_reviewer']='author';self.source['review_candidates']=[{'left':1,'right':2}];self.store.save(self.pid,'dedup.json',self.source)
        with self.assertRaises(ValueError):self.s.prepare(self.pid,'dedup.json',self.protocol)
    def test_checkpoint_and_blinding(self):
        with self.assertRaises(ValueError):self.call('ballot')
        with self.assertRaises(ValueError):self.call('approve',self.m,confirmed=True)
        self.call('approve',confirmed=True);self.call('submit',decisions=self.d,provenance={'type':'human_manual'})
        state=self.call('state',self.m);self.assertNotIn('decisions',state);self.assertNotIn(self.d[0]['reason'],json.dumps(state));self.assertNotIn('provenance',state)
        b=self.call('ballot',self.m);self.assertNotIn('screening_reason',b['records'][0]['record'])
        with self.assertRaises(ValueError):self.call('reveal')
        with self.assertRaises(ValueError):self.call('export')
        with self.assertRaises(ValueError):self.call('export_csv')
    def test_lock_reveal_adjudication(self):
        self.call('approve',confirmed=True);self.call('submit',decisions=self.d,provenance={'type':'human_manual'})
        with self.assertRaises(ValueError):self.call('submit',decisions=self.d,provenance={'type':'human_manual'})
        model=[{**self.d[0],'decision':'uncertain','reason':'Synthetic model uncertainty'}]
        self.call('submit',self.m,decisions=model,provenance={'model':'synthetic','parameters':{},'prompt':'synthetic','raw_response':'synthetic','run_id':'synthetic'})
        with self.assertRaises(ValueError):self.call('reveal',self.m)
        with self.assertRaises(ValueError):self.call('export_csv',self.m)
        pair=self.call('reveal');self.assertEqual(pair['model'][0]['decision'],'uncertain')
        self.call('adjudicate',record_id='r000001',decision='include',reason='Human final confirmation')
        out=self.call('export');self.assertEqual(out['pending_final'],0);self.assertEqual(len([e for e in out['events'] if e['kind']=='submitted']),2)
if __name__=='__main__':unittest.main()
