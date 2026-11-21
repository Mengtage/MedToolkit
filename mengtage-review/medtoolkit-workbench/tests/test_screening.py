import tempfile
import unittest
from workbench.core import Store
from workbench.screening import ScreeningLedger

class ScreeningTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.store=Store(self.tmp.name);self.pid=self.store.create('Synthetic review')
        self.store.save(self.pid,'search.json',{'records':[{'title':'Synthetic paper','pmid':'123','screening_reason':'prior opinion must not leak'}]})
        self.l=ScreeningLedger(self.store)
        self.protocol=dict(question='Synthetic review',stage='title_abstract',inclusion='Synthetic condition',exclusion='Wrong population',human_reviewer='author',llm_reviewer='model',adjudicator='author')
        self.review=self.l.prepare(self.pid,'search.json',self.protocol,'author')
        self.decisions=[dict(record_id='r000001',decision='include',reason='Synthetic criterion met',locator='title')]
    def approve(self):self.l.approve(self.review,'author',True)
    def both(self):
        self.approve();self.l.submit(self.review,'author',self.decisions,{'type':'human_manual'})
        self.l.submit(self.review,'model',self.decisions,{'model':'synthetic-test-only','parameters':{},'prompt':'synthetic prompt','raw_response':'synthetic response','run_id':'test-no-model-call'})
    def test_checkpoint(self):
        with self.assertRaises(ValueError):self.l.ballot(self.review,'author')
        with self.assertRaises(ValueError):self.l.approve(self.review,'model',True)
        with self.assertRaises(ValueError):self.l.approve(self.review,'author',False)
        self.approve();self.assertEqual(len(self.l.ballot(self.review,'model')['records']),1)
    def test_blinded_ballot_and_lock(self):
        self.approve();self.l.submit(self.review,'author',self.decisions,{'type':'human_manual'})
        b=self.l.ballot(self.review,'model')
        self.assertNotIn('screening_reason',b['records'][0]['record']);self.assertNotIn('decisions',b)
        with self.assertRaises(ValueError):self.l.reveal(self.review,'author')
        with self.assertRaises(ValueError):self.l.export(self.review,'author')
        with self.assertRaises(ValueError):self.l.submit(self.review,'author',self.decisions,{'type':'human_manual'})
    def test_missing_not_excluded(self):
        self.approve()
        with self.assertRaises(ValueError):self.l.submit(self.review,'author',[],{'type':'human_manual'})
        with self.assertRaises(ValueError):self.l.submit(self.review,'model',self.decisions,{})
    def test_reveal_adjudicate_revise(self):
        self.both();self.assertEqual(len(self.l.reveal(self.review,'author')),2)
        self.l.adjudicate(self.review,'author','r000001','exclude','Correction with rationale')
        self.l.adjudicate(self.review,'author','r000001','include','Second correction with rationale')
        out=self.l.export(self.review,'author');self.assertEqual(out['pending_final'],0)
        self.assertEqual(len([e for e in out['events'] if e['kind']=='adjudicated']),2)
        self.assertEqual(out['final_decisions'][0]['decision'],'include')
    def test_frozen_snapshot_and_tamper(self):
        self.store.save(self.pid,'search.json',{'records':[]});self.approve()
        self.assertEqual(len(self.l.ballot(self.review,'author')['records']),1)
        with self.store.db() as db:db.execute("UPDATE screening_events SET event=replace(event,'Synthetic paper','Changed paper') WHERE review=?",(self.review,))
        with self.assertRaises(ValueError):self.l.ballot(self.review,'author')
    def test_fulltext_rejected(self):
        self.protocol['stage']='full_text'
        with self.assertRaises(ValueError):self.l.prepare(self.pid,'search.json',self.protocol,'author')
if __name__=='__main__':unittest.main()
