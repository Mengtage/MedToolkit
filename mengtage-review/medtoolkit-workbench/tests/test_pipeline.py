"""End-to-end tests for native multi-database search, RIS/NBIB/CSV file import, de-identified statistics, screening autopilot, SCI auto-drafting, and self-contained pipeline CLI/API."""
import base64
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from docx import Document

from workbench.core import Store
from workbench.importers import parse_ris, parse_nbib, parse_bib_csv, parse_statistics_csv
from workbench.sources import SourceService
from workbench.pipeline import run_pipeline
import test_http_workflow as http_fixture


SAMPLE_RIS = """TY  - JOUR
TI  - Closed-loop analgesia nociception index monitoring in postoperative acute pain: a randomized controlled trial (NCT05511223)
AU  - Zhang, Wei
AU  - Li, Ming
JO  - British Journal of Anaesthesia
PY  - 2025/04/12
VL  - 134
IS  - 4
SP  - 712
EP  - 720
DO  - 10.1016/j.bja.2025.01.015
AN  - 40112233
AB  - Background: We evaluated closed-loop analgesia nociception index (ANI) guided remifentanil and morphine administration in 180 adult surgical patients (NCT05511223). Results: Severe pain incidence decreased significantly (P < 0.001).
ER  - 

TY  - JOUR
TI  - Secondary hemodynamic analysis of the NCT05511223 closed-loop postoperative analgesia trial
AU  - Zhang, Wei
AU  - Chen, Hua
JO  - Anaesthesia
PY  - 2025
VL  - 80
IS  - 8
SP  - 901
EP  - 909
DO  - 10.1111/anae.2025.09
AN  - 40112234
AB  - Methods: Secondary analysis of adult patients enrolled in NCT05511223 receiving closed-loop postoperative pain management.
ER  - 
"""

SAMPLE_NBIB = """PMID- 40223344
TI  - Multimodal wearable biosignals and machine learning for continuous postoperative pain prediction in adult surgical wards
FAU - Wang, Jun
FAU - Zhao, Lin
JT  - Anesthesiology
DP  - 2024 Nov
VI  - 141
IP  - 5
PG  - 880-892
LID - 10.1097/ALN.0000000000005123 [doi]
AB  - We developed and externally validated a multimodal machine learning model combining photoplethysmography and heart rate variability in 420 adult patients for postoperative pain prediction (AUROC 0.84, Brier score 0.14).
"""

SAMPLE_BIB_CSV = """Title,Authors,Journal,Year,Volume,Issue,Pages,PMID,DOI,Abstract
"Preclinical rat model of sciatic nerve injury pain","Kim S; Park J","Pain Research","2024","12","1","10-18","40334455","10.1000/rat.2024","We tested a rat animal model in vitro and in vivo."
"A narrative review of postoperative analgesia","Brown A","Current Pain Reports","2024","28","2","55-62","40334456","10.1000/rev.2024","This narrative review summarizes historical pain protocols."
"""

SAMPLE_STAT_CSV = """group,sample_size,auroc,external_validated
Biosignal_Monitoring,180,0.86,yes
Biosignal_Monitoring,240,0.82,yes
Biosignal_Monitoring,150,0.79,no
Clinical_Risk_Model,420,0.84,yes
Clinical_Risk_Model,310,0.77,no
Clinical_Risk_Model,520,0.81,no
"""


class SelfContainedPipelineTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = Store(self.tmp.name)

    def test_importers_ris_nbib_csv_and_stat_csv(self):
        ris_recs = parse_ris(SAMPLE_RIS)
        self.assertEqual(len(ris_recs), 2)
        self.assertEqual(ris_recs[0]['pmid'], '40112233')
        self.assertEqual(ris_recs[0]['volume'], '134')
        self.assertEqual(ris_recs[0]['issue'], '4')
        self.assertEqual(ris_recs[0]['pages'], '712-720')

        nbib_recs = parse_nbib(SAMPLE_NBIB)
        self.assertEqual(len(nbib_recs), 1)
        self.assertEqual(nbib_recs[0]['pmid'], '40223344')
        self.assertEqual(nbib_recs[0]['doi'], '10.1097/ALN.0000000000005123')
        self.assertEqual(nbib_recs[0]['volume'], '141')
        self.assertEqual(nbib_recs[0]['pages'], '880-892')

        csv_recs = parse_bib_csv(SAMPLE_BIB_CSV)
        self.assertEqual(len(csv_recs), 2)
        self.assertEqual(csv_recs[0]['pmid'], '40334455')

        stat_parsed = parse_statistics_csv(SAMPLE_STAT_CSV)
        self.assertEqual(stat_parsed['row_count'], 6)
        self.assertEqual(stat_parsed['variable_types']['sample_size'], 'numeric_continuous')
        self.assertEqual(stat_parsed['variable_types']['group'], 'categorical')

    def test_europe_pmc_native_search_and_capture(self):
        pid = self.store.create('Europe PMC native search test')
        fake_epmc = {
            'hitCount': 1,
            'resultList': {
                'result': [{
                    'title': 'Europe PMC multimodal postoperative analgesia study',
                    'authorString': 'Liu Y, Sun X.',
                    'journalInfo': {'volume': '15', 'issue': '2', 'journal': {'title': 'Journal of Clinical Anesthesia'}},
                    'firstPublicationDate': '2025-03-01',
                    'pageInfo': '101-109',
                    'pmid': '40998877',
                    'doi': '10.1016/j.jclinane.2025.101',
                    'abstractText': '<p>Adult patients undergoing surgery were monitored continuously.</p>',
                }]
            }
        }
        with patch('workbench.adapters.get', return_value=json.dumps(fake_epmc).encode('utf-8')):
            jid = self.store.enqueue(pid, 'search', {'query': 'postoperative pain AI', 'limit': 25, 'database': 'europe_pmc'})
            res = self.store.run(jid)
        self.assertEqual(res['database'], 'Europe PMC')
        self.assertEqual(res['retrieved'], 1)
        svc = SourceService(self.store)
        cap = svc.capture(pid, res['artifact'], True)
        run_data, _ = svc.load(pid, cap['id'])
        self.assertEqual(run_data['metadata']['database'], 'Europe PMC')
        self.assertEqual(run_data['records'][0]['volume'], '15')
        self.assertEqual(run_data['records'][0]['pages'], '101-109')

    def test_end_to_end_native_pipeline_execution(self):
        stat_parsed = parse_statistics_csv(SAMPLE_STAT_CSV)
        out_dir = Path(self.tmp.name) / 'pipeline_output'
        config = {
            'question': '术后急性疼痛管理中的人工智能连续监测与闭环干预临床证据评价',
            'guideline': 'PRISMA-ScR',
            'classification': 'public',
            'inclusion': 'Adult surgical patients receiving AI or nociception monitoring or machine learning postoperative pain prediction',
            'exclusion': 'Animal rat/mice studies, narrative reviews, protocols without clinical data',
            'imports': [
                {
                    'metadata': {
                        'database': 'PubMed RIS Export',
                        'kind': 'database',
                        'query': 'postoperative pain closed-loop ANI',
                        'searched_at': '2026-11-21',
                        'total_hits': 2,
                        'complete': True,
                        'coverage_note': 'RIS file import',
                    },
                    'filename': 'pubmed_batch.ris',
                    'content': SAMPLE_RIS,
                },
                {
                    'metadata': {
                        'database': 'MEDLINE NBIB Export',
                        'kind': 'database',
                        'query': 'wearable biosignals postoperative pain',
                        'searched_at': '2026-11-21',
                        'total_hits': 1,
                        'complete': True,
                        'coverage_note': 'NBIB file import',
                    },
                    'filename': 'medline.nbib',
                    'content': SAMPLE_NBIB,
                },
                {
                    'metadata': {
                        'database': 'CSV Database Export',
                        'kind': 'database',
                        'query': 'postoperative pain auxiliary records',
                        'searched_at': '2026-11-21',
                        'total_hits': 2,
                        'complete': True,
                        'coverage_note': 'CSV file import with exclusion candidates',
                    },
                    'filename': 'extra.csv',
                    'content': SAMPLE_BIB_CSV,
                },
            ],
            'statistics': [
                {
                    'classification': 'deidentified',
                    'method': 'tableone',
                    'strata': 'group',
                    'variable_types': stat_parsed['variable_types'],
                    'rows': stat_parsed['rows'],
                }
            ],
        }
        result = run_pipeline(self.store, config, output_dir=out_dir)
        # 5 imported records: 2 excluded (1 rat animal study, 1 narrative review), 3 included reports -> 2 unique studies (2 share NCT05511223 + 1 independent)
        counts = result['prisma_counts']
        self.assertEqual(counts['records_identified'], 5)
        self.assertEqual(counts['records_screened'], 5)
        self.assertEqual(counts['records_excluded'], 2)
        self.assertEqual(counts['reports_included'], 3)
        self.assertEqual(counts['studies_included'], 2)
        self.assertEqual(result['checks']['blockers'], [])
        self.assertEqual(result['checks']['warnings'], [])
        self.assertEqual(result['vancouver_reference_count'], 3)

        md_path = Path(result['output_files']['manuscript_md'])
        docx_path = Path(result['output_files']['manuscript_docx'])
        self.assertTrue(md_path.exists())
        self.assertTrue(docx_path.exists())
        md_text = md_path.read_text(encoding='utf-8')
        self.assertIn('## 参考文献 (References)', md_text)
        self.assertIn('134(4):712-720.', md_text)
        self.assertNotIn('[E:', md_text)

        doc = Document(io.BytesIO(docx_path.read_bytes()))
        self.assertGreaterEqual(len(doc.tables), 2)
        # Verify three-line table XML borders
        inside_v = doc.tables[0]._tbl.tblPr.xpath('.//w:tblBorders/w:insideV/@w:val')
        self.assertEqual(inside_v, ['nil'])


class PipelineHTTPTest(unittest.TestCase):
    setUpClass = classmethod(http_fixture.WorkflowTest.setUpClass.__func__)
    tearDownClass = classmethod(http_fixture.WorkflowTest.tearDownClass.__func__)
    request = http_fixture.WorkflowTest.request
    project = http_fixture.WorkflowTest.project

    def test_http_import_file_parse_csv_and_pipeline_run(self):
        pid = self.project()
        imp = self.request('/api/sources/import_file', {
            'project': pid,
            'metadata': {
                'database': 'RIS HTTP Test',
                'kind': 'database',
                'query': 'closed-loop analgesia',
                'searched_at': '2026-11-21',
                'total_hits': 2,
                'complete': True,
                'coverage_note': 'HTTP RIS import',
            },
            'filename': 'test.ris',
            'content': SAMPLE_RIS,
            'confirmed': True,
        }, 201)
        self.assertTrue(imp['artifact'].startswith('source-'))

        parsed_csv = self.request('/api/statistics/parse_csv', {'content': SAMPLE_STAT_CSV}, 200)
        self.assertEqual(parsed_csv['row_count'], 6)

        pipe_out = self.request('/api/pipeline/run', {
            'question': 'HTTP端到端科研流水线验证：术后疼痛闭环监测',
            'imports': [{
                'metadata': {
                    'database': 'HTTP RIS',
                    'kind': 'database',
                    'query': 'closed-loop analgesia',
                    'searched_at': '2026-11-21',
                    'total_hits': 2,
                    'complete': True,
                    'coverage_note': 'Complete',
                },
                'filename': 'batch.ris',
                'content': SAMPLE_RIS,
            }],
        }, 200)
        self.assertEqual(pipe_out['prisma_counts']['reports_included'], 2)
        self.assertEqual(pipe_out['prisma_counts']['studies_included'], 1)
        self.assertEqual(pipe_out['checks']['blockers'], [])


if __name__ == '__main__':
    unittest.main()
