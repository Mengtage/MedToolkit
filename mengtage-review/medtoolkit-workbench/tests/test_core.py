import json
import tempfile
import unittest
from unittest.mock import patch
from workbench.core import Store
from workbench.adapters import evidence,write,statistics,search

class CoreTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.store=Store(self.tmp.name);self.pid=self.store.create('合成示例')
    def tearDown(self):self.tmp.cleanup()
    def test_isolation(self):
        with self.assertRaises(ValueError):self.store.artifact('../escape','x.json')
        with self.assertRaises(ValueError):self.store.artifact(self.pid,'../x.json')
        with self.assertRaises(ValueError):self.store.enqueue('f'*32,'search',{})
    def test_idempotent_job(self):
        j=self.store.enqueue(self.pid,'search',{'query':'pain'})
        self.assertEqual(j,self.store.enqueue(self.pid,'search',{'query':'pain'}))
        self.assertEqual(len(self.store.jobs(self.pid)),1)
    def test_no_repeat_completed(self):
        j=self.store.enqueue(self.pid,'search',{'query':'pain'})
        with patch('workbench.adapters.search',return_value={'retrieved':1}):self.store.run(j)
        with self.assertRaises(ValueError):self.store.run(j)
    def test_recovery_requires_review(self):
        j=self.store.enqueue(self.pid,'search',{'query':'recovery'})
        with self.store.db() as db:db.execute("UPDATE jobs SET state='running' WHERE id=?",(j,))
        self.assertEqual(Store(self.tmp.name).recover(),1)
        self.assertEqual(self.store.jobs(self.pid)[0]['state'],'needs_review')
    def test_reject_private_evidence(self):
        with self.assertRaises(ValueError):evidence({'external_processing_approved':True,'evidence':[{'classification':'patient'}]})
    def test_citation_gate(self):
        p={'section':'背景','external_processing_approved':True,'evidence':[{'id':'e1','source':'doi:test','locator':'p1','excerpt':'公开测试','classification':'public','verified':True}]}
        with patch('workbench.adapters.gemini',return_value=('虚构引用[E:bad]',{'totalTokenCount':20})):
            r=write(self.store,self.pid,p,'test')
        self.assertFalse(r['citation_check_passed']);self.assertEqual(r['state'],'needs_human_review')
    def test_failure_logs_no_data(self):
        j=self.store.enqueue(self.pid,'search',{'query':'test'})
        with patch('workbench.adapters.search',side_effect=ValueError('private sensitive text')):
            with self.assertRaises(ValueError):self.store.run(j)
        self.assertEqual(self.store.jobs(self.pid)[0]['error'],'ValueError')
    def test_patient_data_rejected_before_llm(self):
        with patch('workbench.adapters.gemini') as model:
            with self.assertRaises(ValueError):statistics(self.store,self.pid,{'classification':'patient'},'t')
            model.assert_not_called()
    def test_no_patient_input_persisted(self):
        with self.assertRaises(ValueError):self.store.enqueue(self.pid,'statistics',{'classification':'patient','rows':[{'name':'sensitive-marker'}]})
        self.assertEqual(self.store.jobs(self.pid),[])
        self.assertNotIn(b'sensitive-marker',(self.store.root/'state.sqlite').read_bytes())
    def test_extra_fields_not_saved(self):
        with self.assertRaises(ValueError):self.store.enqueue(self.pid,'search',{'query':'pain','patient_details':'AUDIT_MARKER'})
        payload={'classification':'synthetic','method':'pearson','x':'x','y':'y','rows':[{'x':1,'y':2}]*3,'patient_details':'AUDIT_MARKER'}
        with self.assertRaises(ValueError):self.store.enqueue(self.pid,'statistics',payload)
        self.assertEqual(self.store.jobs(self.pid),[])
        self.assertNotIn(b'AUDIT_MARKER',(self.store.root/'state.sqlite').read_bytes())

    def test_retry_and_lock(self):
        jid=self.store.enqueue(self.pid,'search',{'query':'retry'})
        with self.store.db() as db:db.execute("UPDATE jobs SET state='failed' WHERE id=?",(jid,))
        with self.assertRaises(ValueError):self.store.retry(jid)
        new=self.store.retry(jid,True)
        self.assertNotEqual(jid,new);self.assertEqual(new,self.store.retry(jid,True))
        with self.store.worker_lock():
            with self.assertRaises(ValueError):self.store.recover()
    def test_ris_injection(self):
        from workbench.exports import ris
        output=ris([{'title':'Title\nER  - injected','authors':['A'], 'pmid':'123'}])
        self.assertEqual(output.count('\nER  - '),1)

    def test_statistics_known_result(self):
        p={'classification':'synthetic','method':'pearson','x':'x','y':'y','rows':[{'x':1,'y':2},{'x':2,'y':4},{'x':3,'y':6},{'x':4,'y':8}]}
        with patch('workbench.adapters.gemini') as model:
            r=statistics(self.store,self.pid,p,'t')
        self.assertAlmostEqual(r['coefficient'],1.0);self.assertEqual(r['n'],4);model.assert_not_called()
    def test_search_truncation(self):
        with patch('workbench.adapters.get',return_value=json.dumps({'esearchresult':{'count':'12','idlist':[]}}).encode()):
            r=search(self.store,self.pid,{'query':'test','limit':5},'t')
        self.assertFalse(r['complete']);self.assertEqual(r['total_hits'],12)

    def test_pubmed_xml_inline_tags_doi_and_book_article(self):
        xml = (
            b'<PubmedArticleSet>'
            b'<PubmedArticle><MedlineCitation><PMID>1001</PMID>'
            b'<Article><ArticleTitle><i>In vitro</i> efficacy of <i>Staphylococcus aureus</i> CO<sub>2</sub></ArticleTitle>'
            b'<Abstract><AbstractText Label="METHODS">Tested <i>in vivo</i> &amp; <sup>14</sup>C.</AbstractText></Abstract>'
            b'<AuthorList><Author><LastName>Smith</LastName><ForeName>John</ForeName></Author></AuthorList>'
            b'<ELocationID EIdType="doi">10.1000/main-eloc</ELocationID>'
            b'</Article></MedlineCitation>'
            b'<PubmedData><ReferenceList><Reference><ArticleIdList><ArticleId IdType="doi">10.9999/ref-doi</ArticleId></ArticleIdList></Reference></ReferenceList></PubmedData>'
            b'</PubmedArticle>'
            b'<PubmedBookArticle><BookDocument><PMID>1002</PMID>'
            b'<ArticleTitle><i>StatPearls</i> Airway Management</ArticleTitle>'
            b'<Abstract><AbstractText>Book chapter <b>summary</b>.</AbstractText></Abstract>'
            b'</BookDocument></PubmedBookArticle>'
            b'</PubmedArticleSet>'
        )
        responses = [json.dumps({'esearchresult': {'count': '2', 'idlist': ['1001', '1002']}}).encode(), xml]
        with patch('workbench.adapters.get', side_effect=responses), patch('time.sleep'):
            r = search(self.store, self.pid, {'query': 'staph', 'limit': 10}, 'j1')
        self.assertTrue(r['complete'])
        self.assertEqual(r['retrieved'], 2)
        saved = json.loads(self.store.artifact(self.pid, r['artifact']).read_text())
        rec1, rec2 = saved['records']
        self.assertEqual(rec1['title'], 'In vitro efficacy of Staphylococcus aureus CO2')
        self.assertEqual(rec1['abstract'], 'METHODS: Tested in vivo & 14C.')
        self.assertEqual(rec1['doi'], '10.1000/main-eloc')
        self.assertEqual(rec2['pmid'], '1002')
        self.assertEqual(rec2['title'], 'StatPearls Airway Management')

    def test_correlation_preflight_rejects_insufficient_pairs_and_constants(self):
        bad_cases = [
            [{'x': 1, 'y': None}, {'x': 2, 'y': 4}, {'x': 3, 'y': 6}, {'x': None, 'y': 8}],
            [{'x': 1, 'y': 2}, {'x': 1, 'y': 4}, {'x': 1, 'y': 6}],
            [{'x': 1e101, 'y': 2}, {'x': 2, 'y': 4}, {'x': 3, 'y': 6}],
        ]
        for rows in bad_cases:
            with self.assertRaises(ValueError):
                self.store.enqueue(self.pid, 'statistics', {'classification': 'synthetic', 'method': 'pearson', 'x': 'x', 'y': 'y', 'rows': rows})

if __name__=='__main__':unittest.main()
