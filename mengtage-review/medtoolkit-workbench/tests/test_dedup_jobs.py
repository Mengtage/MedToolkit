import tempfile,unittest,json
from workbench.core import Store
from workbench.dedup_jobs import digest,resolve

class DedupJobsTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.store=Store(self.tmp.name);self.pid=self.store.create('Synthetic')
        self.source={'records':[{'title':'Same','pmid':'1'},{'title':'Same','pmid':'1','abstract':'More'},{'title':'Same','pmid':'2'}]}
        self.store.save(self.pid,'source.json',self.source)
        self.payload={'source_artifact':'source.json','source_sha256':digest(self.source)}
    def run_dedup(self):
        jid=self.store.enqueue(self.pid,'deduplicate',self.payload);r=self.store.run(jid)
        return r['artifact'],json.loads(self.store.artifact(self.pid,r['artifact']).read_text())
    def test_persisted_idempotency(self):
        j=self.store.enqueue(self.pid,'deduplicate',self.payload);self.assertEqual(j,self.store.enqueue(self.pid,'deduplicate',self.payload));self.store.run(j)
        self.assertEqual(j,self.store.enqueue(self.pid,'deduplicate',self.payload))
    def test_changed_source_rejected(self):
        j=self.store.enqueue(self.pid,'deduplicate',self.payload);self.store.save(self.pid,'source.json',{'records':[]})
        with self.assertRaises(ValueError):self.store.run(j)
    def test_project_scope(self):
        other=self.store.create('Other')
        with self.assertRaises(FileNotFoundError):self.store.enqueue(other,'deduplicate',self.payload)
    def test_review_immutable(self):
        name,original=self.run_dedup();self.assertEqual(original['unique_count'],2)
        for decision,count in [('keep',2),('merge',1)]:
            p={'source_artifact':name,'source_sha256':digest(original),'candidate_index':0,'decision':decision,'reason':'Human review'}
            j=self.store.enqueue(self.pid,'dedup_review',p);r=self.store.run(j);out=json.loads(self.store.artifact(self.pid,r['artifact']).read_text())
            self.assertEqual(out['unique_count'],count);self.assertEqual(out['raw_records'],self.source['records']);self.assertTrue(out['review_events'])
        self.assertEqual(json.loads(self.store.artifact(self.pid,name).read_text()),original)
    def test_keep_constraint_and_repeat(self):
        _,out=self.run_dedup();p={'candidate_index':0,'decision':'keep','reason':'Distinct reports'};out=resolve(out,p)
        with self.assertRaises(ValueError):resolve(out,p)
        # Another candidate with the same two groups cannot override the keep decision.
        if len(out['review_candidates'])>1:
            with self.assertRaises(ValueError):resolve(out,{'candidate_index':1,'decision':'merge','reason':'Would contradict keep'})
    def test_bad_input(self):
        for extra in [{'candidate_index':-1,'decision':'keep','reason':'x'},{'candidate_index':0,'decision':'merge','reason':''}]:
            with self.assertRaises(ValueError):self.store.enqueue(self.pid,'dedup_review',{**self.payload,**extra})
if __name__=='__main__':unittest.main()
