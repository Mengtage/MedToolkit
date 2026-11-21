import unittest
from workbench.deduplication import deduplicate
class DedupTests(unittest.TestCase):
    def run_dedup(self,rows,policy='review'):return deduplicate(rows,conflict_policy=policy)
    def test_doi_and_provenance(self):
        rows=[{'title':'One','doi':'https://doi.org/10.1234/ABC'},{'title':'ONE','doi':'doi:10.1234/abc','abstract':'More complete'}]
        o=self.run_dedup(rows);self.assertEqual(o['unique_count'],1);self.assertEqual(o['raw_records'],rows);self.assertEqual(o['groups'][0]['selected_source_index'],2)
    def test_title_fallback_and_empty(self):
        o=self.run_dedup([{'title':'Test: Paper!'},{'title':'test paper'},{},{'title':''}]);self.assertEqual(o['unique_count'],3)
    def test_conflicting_title(self):
        rows=[{'title':'Same','pmid':'1'},{'title':'Same','pmid':'2'}]
        self.assertEqual(deduplicate(rows)['unique_count'],2)
        self.assertEqual(deduplicate(rows)['conflict_policy'],'review')
        self.assertEqual(self.run_dedup(rows,'title_wins')['unique_count'],1)
    def test_id_bridge_conflict(self):
        rows=[{'pmid':'1','doi':'10.1234/a'},{'pmid':'1'},{'pmid':'2','doi':'10.1234/a'}]
        o=self.run_dedup(rows);self.assertEqual(o['unique_count'],2);self.assertTrue(o['review_candidates'])
    def test_same_id_different_title(self):
        o=self.run_dedup([{'pmid':'PMID: 001','title':'Old'},{'pmid':'https://pubmed.ncbi.nlm.nih.gov/1/','title':'New'}]);self.assertEqual(o['unique_count'],1)
    def test_invalid_and_explicit_policy(self):
        with self.assertRaises(ValueError):self.run_dedup([{'doi':'garbage'}])
        with self.assertRaises(ValueError):self.run_dedup([],None)
    def test_order_independent_unidentified_in_conflicted_title_bucket(self):
        a={'title':'Same Title Bucket','pmid':'111'}
        b={'title':'Same Title Bucket'}
        c={'title':'Same Title Bucket','pmid':'222'}
        out1=self.run_dedup([a,b,c])
        out2=self.run_dedup([c,b,a])
        self.assertEqual(out1['unique_count'],3)
        self.assertEqual(out2['unique_count'],3)
        self.assertTrue(any(r['reason']=='title_only_ambiguous_bucket' for r in out1['review_candidates']))
        self.assertTrue(any(r['reason']=='title_only_ambiguous_bucket' for r in out2['review_candidates']))
    def test_cross_database_complementary_ids_auto_merge_and_enrich(self):
        long_title='Randomized controlled trial of perioperative dexmedetomidine for postoperative delirium'
        r1={'title':long_title,'pmid':'123456'}
        r2={'title':long_title,'doi':'10.1000/dex-trial-2026'}
        out=self.run_dedup([r1,r2])
        self.assertEqual(out['unique_count'],1)
        self.assertEqual(out['review_candidates'],[])
        self.assertEqual(out['records'][0]['pmid'],'123456')
        self.assertEqual(out['records'][0]['doi'],'10.1000/dex-trial-2026')
if __name__=='__main__':unittest.main()
