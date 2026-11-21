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
if __name__=='__main__':unittest.main()
