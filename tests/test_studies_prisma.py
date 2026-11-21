import base64,json,tempfile,unittest
from workbench.core import Store
from workbench.screening_http import ScreeningService
from workbench.deduplication import deduplicate
from workbench.fulltext import json_hash
from workbench.prisma import diagram

class StudyPrismaTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup);self.store=Store(tmp.name);self.s=ScreeningService(self.store);self.pid=self.store.create('Synthetic review')
        self.h=self.s.access.issue('human','human');self.m=self.s.access.issue('model','model');self.x=self.s.access.issue('outside','human')
        self.protocol=dict(question='Synthetic review',stage='title_abstract',inclusion='Adults',exclusion='Children',human_reviewer='human',llm_reviewer='model',adjudicator='human')
        raw=[{'title':'A','pmid':'1'},{'title':'A','pmid':'1'},{'title':'B','pmid':'2'},{'title':'C','pmid':'3'},{'title':'D','pmid':'4'}]
        self.search={'records':raw,'retrieved':5,'total_hits':5,'complete':True};self.store.save(self.pid,'search.json',self.search)
        self.dedup=deduplicate(raw);self.dedup.update(method='deduplication',source_artifact='search.json',source_sha256=json_hash(self.search))
        self.store.save(self.pid,'dedup.json',self.dedup)
        self.parent=self.s.prepare(self.pid,'dedup.json',self.protocol)['review'];self.r=self.parent
        self.provenance={'model':'synthetic','parameters':{},'prompt':'Synthetic','raw_response':'Synthetic','run_id':'synthetic'}
        rows=[dict(record_id=f'r{i:06}',decision='include',reason='Synthetic decision',locator='title') for i in range(1,5)]
        self.finish(rows)
        self.call('adjudicate',record_id='r000004',decision='exclude',reason='Not eligible',reason_code='population')
        for rid in ('r000001','r000002'):
            self.call('fulltext_register',record_id=rid,status='retrieved',reason='Synthetic supplied',filename='fixture.txt',content_base64=base64.b64encode(b'Trial X and Trial Y enrolled adults.').decode())
        self.call('fulltext_register',record_id='r000003',status='not_retrieved',reason='No synthetic report')
        self.r=self.call('fulltext_prepare',protocol=self.protocol)['review']
        self.rows=[dict(record_id=f'r{i:06}',decision='include',reason='Synthetic final',locator='p:1',quote='Trial X and Trial Y enrolled adults.') for i in (1,2)]
        self.finish(self.rows)
    def call(self,op,actor=None,**body):return self.s.dispatch(op,{'review':self.r,**body},actor or self.h)
    def finish(self,rows):
        self.call('approve',confirmed=True);self.call('submit',decisions=rows,provenance={'type':'human_manual'});self.call('submit',self.m,decisions=rows,provenance=self.provenance);self.call('reveal')
        for row in rows:self.call('adjudicate',**row)
    def mapping(self,ids=None):
        return [dict(record_id=row['record_id'],study_ids=(ids or [['trial_x'],['trial_x']])[i],reason='Same trial identifier in source',locator='p:1',quote=row['quote']) for i,row in enumerate(self.rows)]
    def save(self,rows=None,**overrides):
        state=self.call('study_state');args=dict(mappings=rows if rows is not None else self.mapping(),screening_event_hash=state['screening_event_hash'],mapping_event_hash=state['mapping_event_hash'],confirmed=True);args.update(overrides);return self.call('study_save',**args)
    def test_counts_report_vs_study_and_missing(self):
        before=self.call('prisma_preview')['report'];self.assertIsNone(before['counts']['studies_included'])
        self.save();after=self.call('prisma_preview')['report'];c=after['counts']
        self.assertEqual((c['records_identified'],c['duplicates_removed'],c['records_screened'],c['records_excluded']),(5,1,4,1))
        self.assertEqual((c['reports_sought'],c['reports_not_retrieved'],c['reports_assessed'],c['reports_included'],c['studies_included']),(3,1,2,2,1))
        self.assertEqual(after['status'],'selected_lineage_complete')
        self.assertEqual(after['reports_not_retrieved'][0]['reason'],'No synthetic report')
    def test_many_to_many_and_revision_history(self):
        self.save();old=self.call('study_state');self.save(self.mapping([['trial_x','trial_y'],['trial_x']]))
        state=self.call('study_state');self.assertEqual(len(state['history']),2);self.assertEqual(state['history'][1]['previous_hash'],old['mapping_event_hash'])
        self.assertEqual(self.call('prisma_preview')['report']['counts']['studies_included'],2)
    def test_confirmation_invalid_ids_missing_and_quote(self):
        with self.assertRaises(ValueError):self.save(confirmed=False)
        for rows in (self.mapping()[:1],self.mapping([['trial_x','trial_x'],['trial_x']]),self.mapping([['../bad'],['trial_x']])):
            with self.assertRaises(ValueError):self.save(rows)
        rows=self.mapping();rows[0]['quote']='Not in original'
        with self.assertRaises(ValueError):self.save(rows)
        self.assertEqual(self.call('study_state')['history'],[])
    def test_access_isolation(self):
        for op in ('study_state','prisma_preview'):
            with self.assertRaises(ValueError):self.call(op,self.m)
            with self.assertRaises(PermissionError):self.call(op,self.x)
        with self.assertRaises(ValueError):self.s.dispatch('study_state',{'review':self.r,'actor':'human'},self.h)
    def test_optimistic_version_conflict(self):
        state=self.call('study_state');self.save()
        with self.assertRaises(ValueError):self.save(mapping_event_hash=state['mapping_event_hash'])
        self.call('adjudicate',**{**self.rows[0],'reason':'New adjudication'})
        with self.assertRaises(ValueError):self.save(screening_event_hash=state['screening_event_hash'])
        self.assertFalse(self.call('study_state')['mapping_valid']);self.assertIsNone(self.call('prisma_preview')['report']['counts']['studies_included'])
    def test_exclusion_reason_and_zero_included(self):
        for row in self.rows:self.call('adjudicate',**{**row,'decision':'exclude','reason':'Not adult','reason_code':'population'})
        report=self.call('prisma_preview')['report'];self.assertEqual(report['counts']['studies_included'],0);self.assertEqual(report['counts']['reports_included'],0)
        self.assertEqual(report['exclusion_reasons'],[{'code':'population','label':'研究对象不符','count':2}])
    def test_parent_revision_uses_frozen_version(self):
        self.save();self.s.ledger.adjudicate(self.parent,'human','r000001','exclude','Parent correction','population')
        report=self.call('prisma_preview')['report'];self.assertTrue(report['provenance']['parent_changed']);self.assertEqual(report['counts']['reports_sought'],3)
        self.assertEqual(report['status'],'partial_or_historical')
    def test_changed_search_does_not_invent_counts(self):
        self.save();self.store.save(self.pid,'search.json',{**self.search,'total_hits':999})
        report=self.call('prisma_preview')['report'];self.assertIsNone(report['counts']['records_identified']);self.assertIsNone(report['counts']['duplicates_removed']);self.assertEqual(report['status'],'partial_or_historical')
    def test_export_frozen_hash_and_svg_escaping(self):
        self.save();out=self.call('prisma_preview');export=self.call('prisma_export',expected_sha256=out['sha256']);snapshot=json.loads(export['files'][0]['content'])
        self.assertEqual(snapshot['report_sha256'],json_hash(snapshot['report']));self.assertEqual(snapshot['report'],out['report'])
        self.assertEqual(json.loads(self.store.artifact(self.pid,export['artifact']).read_text()),snapshot)
        self.assertTrue(export['files'][1]['content'].startswith('\ufeff'))
        import xml.etree.ElementTree as ET
        ET.fromstring(export['files'][2]['content']);report=out['report'];report['exclusion_reasons']=[{'code':'</text><script>x</script>','count':1}]
        svg=diagram(report);self.assertNotIn('<script>',svg);ET.fromstring(svg)
        self.save(self.mapping([['x'],['y']]))
        with self.assertRaises(ValueError):self.call('prisma_export',expected_sha256=out['sha256'])
    def test_pending_final_is_not_complete(self):
        with self.store.db() as db:db.execute("DELETE FROM screening_events WHERE review=? AND json_extract(event,'$.kind')='adjudicated'",(self.r,))
        report=self.call('prisma_preview')['report'];self.assertEqual(report['counts']['reports_pending'],2);self.assertIsNone(report['counts']['studies_included'])
        with self.assertRaises(ValueError):self.save()
    def test_all_unretrieved_from_parent(self):
        self.r=self.parent
        for rid in ('r000001','r000002'):self.call('fulltext_register',record_id=rid,status='not_retrieved',reason='No longer available in this branch')
        report=self.call('prisma_preview')['report'];self.assertEqual(report['counts']['reports_sought'],3);self.assertEqual(report['counts']['reports_not_retrieved'],3);self.assertEqual(report['counts']['studies_included'],0)
    def test_all_excluded_title_stage(self):
        self.r=self.parent
        for i in range(1,4):self.call('adjudicate',record_id=f'r{i:06}',decision='exclude',reason='Revised',reason_code='population')
        report=self.call('prisma_preview')['report'];self.assertEqual(report['counts']['records_excluded'],4);self.assertEqual(report['counts']['reports_sought'],0)
    def test_partial_search_source_count_function(self):
        from workbench.prisma import source_counts
        with self.store.db() as db:draft=self.s.ledger._events(db,self.parent)[0]['data']
        search={**self.search,'total_hits':20,'complete':False};self.store.save(self.pid,'partial.json',search)
        dedup={**self.dedup,'source_artifact':'partial.json','source_sha256':json_hash(search)};self.store.save(self.pid,'partial-dedup.json',dedup)
        out=source_counts(self.store,self.pid,{**draft,'source_artifact':'partial-dedup.json','source_sha256':json_hash(dedup)})
        self.assertEqual(out['records_identified'],5);self.assertEqual(out['records_not_downloaded'],15);self.assertFalse(out['search_complete']);self.assertTrue(out['issues'])
    def test_mapping_hash_tamper(self):
        self.save()
        with self.store.db() as db:db.execute("UPDATE study_events SET event=replace(event,'Same trial identifier','Changed identifier')")
        with self.assertRaises(ValueError):self.call('study_state')
