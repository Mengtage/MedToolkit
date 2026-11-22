"""Unit and HTTP integration tests for Stage 1 (Auto-Pagination, Open Academic APIs, 5-Database Query Translator) and Stage 2 (10-Dimension PICO + 4W + MCID Data Charting)."""
import json
import tempfile
import unittest
from unittest.mock import patch

from workbench.core import Store
from workbench.adapters import search
from workbench.sources import SourceService
from workbench.query_translator import translate_query
from workbench.charting import (
    CHARTING_DIMENSIONS,
    INTERVENTION_4W_KEYS,
    CURATED_PMID_CHARTING,
    validate_charting_entry,
)
from workbench.dedup_jobs import digest
from workbench.screening_http import ScreeningService
from workbench.screening_autopilot import (
    generate_screening_decisions,
    batch_register_fulltext,
    suggest_study_mappings,
)
import test_http_workflow as http_fixture


class SearchPaginationAndQueryTranslatorTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = Store(self.tmp.name)
        self.pid = self.store.create('阶段1自动翻页与多源检索测试')

    def test_pubmed_auto_pagination_fetches_all_pages(self):
        # Simulate 5 total hits across 3 esearch pages of page_size=2, followed by efetch batches
        esearch_p1 = json.dumps({'esearchresult': {'count': '5', 'idlist': ['101', '102']}}).encode()
        esearch_p2 = json.dumps({'esearchresult': {'count': '5', 'idlist': ['103', '104']}}).encode()
        esearch_p3 = json.dumps({'esearchresult': {'count': '5', 'idlist': ['105']}}).encode()

        def make_xml(pmids):
            items = ''.join(
                f'<PubmedArticle><MedlineCitation><PMID>{p}</PMID>'
                f'<Article><ArticleTitle>Postoperative pain AI study {p}</ArticleTitle>'
                f'<Abstract><AbstractText>Enrolled 120 patients with AUROC 0.85.</AbstractText></Abstract>'
                f'</Article></MedlineCitation></PubmedArticle>'
                for p in pmids
            )
            return f'<PubmedArticleSet>{items}</PubmedArticleSet>'.encode()

        responses = [
            esearch_p1,
            esearch_p2,
            esearch_p3,
            make_xml(['101', '102']),
            make_xml(['103', '104']),
            make_xml(['105']),
        ]
        with patch('workbench.adapters.get', side_effect=responses), patch('time.sleep'):
            res = search(self.store, self.pid, {'query': 'postoperative pain AI', 'limit': 5, 'fetch_all': True, 'page_size': 2}, 'j_pub_pag')
        self.assertTrue(res['complete'])
        self.assertEqual(res['total_hits'], 5)
        self.assertEqual(res['retrieved'], 5)
        self.assertEqual(res['pages_fetched'], 3)

    def test_europe_pmc_cursormark_auto_pagination(self):
        epmc_p1 = json.dumps({
            'hitCount': 3,
            'nextCursorMark': 'cursor_page_2',
            'resultList': {'result': [
                {'title': 'EPMC Study 1', 'pmid': '201', 'abstractText': 'Abstract 1'},
                {'title': 'EPMC Study 2', 'pmid': '202', 'abstractText': 'Abstract 2'},
            ]},
        }).encode()
        epmc_p2 = json.dumps({
            'hitCount': 3,
            'nextCursorMark': 'cursor_page_2',
            'resultList': {'result': [
                {'title': 'EPMC Study 3', 'pmid': '203', 'abstractText': 'Abstract 3'},
            ]},
        }).encode()
        with patch('workbench.adapters.get', side_effect=[epmc_p1, epmc_p2]):
            res = search(self.store, self.pid, {'query': 'nociception level', 'database': 'europe_pmc', 'limit': 3, 'fetch_all': True, 'page_size': 2}, 'j_epmc_pag')
        self.assertTrue(res['complete'])
        self.assertEqual(res['total_hits'], 3)
        self.assertEqual(res['retrieved'], 3)
        self.assertEqual(res['pages_fetched'], 2)

    def test_openalex_crossref_and_clinicaltrials_open_apis(self):
        # 1. OpenAlex
        oa_resp = json.dumps({
            'meta': {'count': 1, 'next_cursor': None},
            'results': [{
                'title': 'OpenAlex multimodal pain prediction',
                'doi': 'https://doi.org/10.1000/oa.2025.1',
                'ids': {'pmid': 'https://pubmed.ncbi.nlm.nih.gov/30012345'},
                'publication_date': '2025-05-10',
                'authorships': [{'author': {'display_name': 'Alice Smith'}}],
                'primary_location': {'source': {'display_name': 'NPJ Digital Medicine'}},
                'biblio': {'volume': '8', 'issue': '1', 'first_page': '10', 'last_page': '18'},
                'abstract_inverted_index': {'Postoperative': [0], 'pain': [1], 'prediction': [2], 'model.': [3]},
            }],
        }).encode()
        with patch('workbench.adapters.get', return_value=oa_resp):
            r_oa = search(self.store, self.pid, {'query': 'postoperative pain', 'database': 'openalex', 'limit': 10}, 'j_oa')
        self.assertEqual(r_oa['database'], 'OpenAlex')
        self.assertEqual(r_oa['retrieved'], 1)
        oa_saved = json.loads(self.store.artifact(self.pid, r_oa['artifact']).read_text())
        self.assertEqual(oa_saved['records'][0]['abstract'], 'Postoperative pain prediction model.')
        self.assertEqual(oa_saved['records'][0]['pmid'], '30012345')
        self.assertEqual(oa_saved['records'][0]['pages'], '10-18')

        # 2. Crossref
        cr_resp = json.dumps({
            'message': {
                'total-results': 1,
                'items': [{
                    'title': ['Crossref analgesic closed-loop trial'],
                    'DOI': '10.1000/cr.2025.2',
                    'author': [{'family': 'Lee', 'given': 'Min'}],
                    'container-title': ['British Journal of Anaesthesia'],
                    'published': {'date-parts': [[2025, 4, 1]]},
                    'volume': '134',
                    'issue': '4',
                    'page': '500-508',
                    'abstract': '<jats:p>Closed-loop analgesia evaluation.</jats:p>',
                }],
            },
        }).encode()
        with patch('workbench.adapters.get', return_value=cr_resp):
            r_cr = search(self.store, self.pid, {'query': 'closed-loop analgesia', 'database': 'crossref', 'limit': 10}, 'j_cr')
        self.assertEqual(r_cr['database'], 'Crossref')
        self.assertEqual(r_cr['retrieved'], 1)

        # 3. ClinicalTrials.gov v2 + SourceService register capture
        ct_resp = json.dumps({
            'totalCount': 1,
            'studies': [{
                'protocolSection': {
                    'identificationModule': {'nctId': 'NCT09988776', 'briefTitle': 'NOL-Guided Analgesia Trial'},
                    'descriptionModule': {'briefSummary': 'Randomized trial of NOL-guided opioid dosing.'},
                    'statusModule': {'startDateStruct': {'date': '2025-01-15'}},
                    'designModule': {'enrollmentInfo': {'count': 120}},
                    'sponsorCollaboratorsModule': {'leadSponsor': {'name': 'University Hospital'}},
                },
            }],
        }).encode()
        with patch('workbench.adapters.get', return_value=ct_resp):
            jid = self.store.enqueue(self.pid, 'search', {'query': 'nociception level', 'database': 'clinicaltrials', 'limit': 10})
            r_ct = self.store.run(jid)
        self.assertEqual(r_ct['database'], 'ClinicalTrials.gov')
        cap = SourceService(self.store).capture(self.pid, r_ct['artifact'], True)
        run_data, _ = SourceService(self.store).load(self.pid, cap['id'])
        self.assertEqual(run_data['metadata']['kind'], 'register')
        self.assertIn('NCT09988776', run_data['records'][0]['title'])

    def test_five_database_boolean_query_translator(self):
        q = '("Pain, Postoperative"[Mesh] OR "acute postoperative pain"[tiab]) AND ("Artificial Intelligence"[Mesh] OR "machine learning"[tiab])'
        out = translate_query(q, target='all', date_from='2022', date_to='2026')
        self.assertEqual(set(out['translations']), {'pubmed', 'embase_ovid', 'wos', 'scopus', 'cochrane'})
        self.assertIn('exp pain, postoperative/', out['translations']['embase_ovid']['translated_query'])
        self.assertIn('.ti,ab,kw.', out['translations']['embase_ovid']['translated_query'])
        self.assertTrue(out['translations']['wos']['translated_query'].startswith('TS=('))
        self.assertTrue(out['translations']['scopus']['translated_query'].startswith('TITLE-ABS-KEY('))
        self.assertIn('[mh "Pain, Postoperative"]', out['translations']['cochrane']['translated_query'])


class DataCharting10DTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = Store(self.tmp.name)
        self.pid = self.store.create('阶段2十维临床证据提取测试')

    def test_curated_37_study_profiles_all_satisfy_10d_schema_and_pure_chinese(self):
        self.assertGreaterEqual(len(CURATED_PMID_CHARTING), 28)
        for pmid, prof in CURATED_PMID_CHARTING.items():
            entry = {
                'record_id': f'r_{pmid}',
                'study_ids': [f'study_pmid_{pmid}'],
                'locator': 'p:1',
                'quote': 'verbatim quote',
                **prof,
            }
            validate_charting_entry(entry, record=None)
            for dim in CHARTING_DIMENSIONS:
                val = prof[dim]
                text_val = ' '.join(val.values()) if isinstance(val, dict) else val
                self.assertNotIn('详见正文', text_val)
                self.assertNotIn('...', text_val)

    def test_charting_service_lifecycle_and_hash_chain_tamper_detection(self):
        sources_svc = SourceService(self.store)
        screening_svc = ScreeningService(self.store)
        meta = {
            'database': 'PubMed',
            'kind': 'database',
            'query': 'postoperative pain AI',
            'searched_at': '2026-11-22',
            'total_hits': 2,
            'complete': True,
            'coverage_note': 'Unit test',
        }
        records = [
            {
                'title': 'The impact of regional block presence on large language model-based postoperative analgesia recommendations',
                'pmid': '41957712',
                'authors': ['Uslu Bayhan B', 'Gazioğlu Kişi T'],
                'journal': 'BMC Anesthesiol',
                'pub_date': '2026',
                'abstract': 'Prospective postoperative pain study of 144 adult patients undergoing elective abdominal surgery evaluated by LLM systems ChatGPT, Gemini, and Copilot.',
            },
            {
                'title': 'Reduced postoperative pain in patients receiving nociception monitor guided analgesia: a randomized controlled trial (NCT03970291)',
                'pmid': '35976578',
                'authors': ['Fuica R', 'Gozal Y'],
                'journal': 'J Clin Monit Comput',
                'pub_date': '2023',
                'abstract': '75 ASA 1-3 adult patients randomized to NOL-guided fentanyl dosing or standard care (NCT03970291). Median pain scores 3.0 vs 5.0 (difference 1.5).',
            },
        ]
        src = sources_svc.import_records(self.pid, meta, records, True)
        col = sources_svc.create(self.pid, 'Test col', [src['id']], None, 'Test', True)
        col_data = json.loads(self.store.artifact(self.pid, col['artifact']).read_text())
        d_jid = self.store.enqueue(self.pid, 'deduplicate', {'source_artifact': col['artifact'], 'source_sha256': digest(col_data)})
        d_art = self.store.run(d_jid)['artifact']

        screening_svc.access.issue('h_rev', 'human')
        screening_svc.access.issue('m_rev', 'model')
        prot = {
            'question': '术后急性疼痛人工智能管理',
            'stage': 'title_abstract',
            'inclusion': 'Postoperative pain AI NOL LLM',
            'exclusion': 'Animal studies',
            'human_reviewer': 'h_rev',
            'llm_reviewer': 'm_rev',
            'adjudicator': 'h_rev',
        }
        ta_rev = screening_svc.prepare(self.pid, d_art, prot)['review']
        screening_svc.ledger.approve(ta_rev, 'h_rev', True)
        bh = screening_svc.ledger.ballot(ta_rev, 'h_rev')
        dh, _ = generate_screening_decisions(bh)
        screening_svc.ledger.submit(ta_rev, 'h_rev', dh, {'type': 'human_manual'})
        bm = screening_svc.ledger.ballot(ta_rev, 'm_rev')
        dm, pm = generate_screening_decisions(bm)
        screening_svc.ledger.submit(ta_rev, 'm_rev', dm, pm)
        screening_svc.ledger.reveal(ta_rev, 'h_rev')
        screening_svc.dispatch('batch_adjudicate', {'review': ta_rev, 'confirmed': True}, {'actor': 'h_rev', 'role': 'human'})

        batch_register_fulltext(screening_svc.fulltext, ta_rev, 'h_rev')
        ft_rev = screening_svc.fulltext.prepare(ta_rev, 'h_rev', {**prot, 'stage': 'full_text'})['review']
        screening_svc.ledger.approve(ft_rev, 'h_rev', True)
        fbh = screening_svc.ledger.ballot(ft_rev, 'h_rev')
        fdh, _ = generate_screening_decisions(fbh)
        screening_svc.ledger.submit(ft_rev, 'h_rev', fdh, {'type': 'human_manual'})
        fbm = screening_svc.ledger.ballot(ft_rev, 'm_rev')
        fdm, fpm = generate_screening_decisions(fbm)
        screening_svc.ledger.submit(ft_rev, 'm_rev', fdm, fpm)
        screening_svc.ledger.reveal(ft_rev, 'h_rev')
        screening_svc.dispatch('batch_adjudicate', {'review': ft_rev, 'confirmed': True}, {'actor': 'h_rev', 'role': 'human'})

        sug = suggest_study_mappings(screening_svc.studies, ft_rev, 'h_rev')
        screening_svc.studies.save(ft_rev, 'h_rev', sug['suggestions'], sug['screening_event_hash'], sug['mapping_event_hash'], True)

        # Extract and save 10D Data Charting via ScreeningService.dispatch
        extracted = screening_svc.dispatch('chart_extract', {'review': ft_rev, 'mode': 'structured', 'save': True}, {'actor': 'h_rev', 'role': 'human'})
        self.assertTrue(extracted['saved'])
        self.assertEqual(extracted['charted_count'], 2)

        state = screening_svc.dispatch('chart_state', {'review': ft_rev}, {'actor': 'h_rev', 'role': 'human'})
        self.assertTrue(state['charting_valid'])
        self.assertEqual(len(state['charting']), 2)
        self.assertEqual(set(state['charting'][0]['intervention']), set(INTERVENTION_4W_KEYS))
        self.assertIn('MCID', state['charting'][1]['effect_size_and_mcid'])

        # Tamper detection on charting_events table
        with self.store.db() as db:
            db.execute("UPDATE charting_events SET event=?", (json.dumps({'previous_hash': 'tampered', 'event_hash': 'bad'}),))
        with self.assertRaises(ValueError):
            screening_svc.charting.state(ft_rev, 'h_rev')


class ChartingAndTranslatorHTTPTest(unittest.TestCase):
    setUpClass = classmethod(http_fixture.WorkflowTest.setUpClass.__func__)
    tearDownClass = classmethod(http_fixture.WorkflowTest.tearDownClass.__func__)
    request = http_fixture.WorkflowTest.request

    def test_http_translate_query_endpoint(self):
        res = self.request('/api/sources/translate_query', {
            'query': '"Pain, Postoperative"[Mesh] AND "Machine Learning"[tiab]',
            'target': 'all',
            'date_from': '2022',
            'date_to': '2026',
        }, 200)
        self.assertIn('embase_ovid', res['translations'])
        self.assertIn('wos', res['translations'])
        self.assertIn('scopus', res['translations'])
        self.assertIn('cochrane', res['translations'])


if __name__ == '__main__':
    unittest.main()
