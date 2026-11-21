import unittest,json,base64,io
from docx import Document
import test_studies_prisma as fixture
from workbench.writer import WriterService
class WriterHunterTest(unittest.TestCase):
 setUp=fixture.StudyPrismaTests.setUp
 call=fixture.StudyPrismaTests.call
 finish=fixture.StudyPrismaTests.finish
 mapping=fixture.StudyPrismaTests.mapping
 save=fixture.StudyPrismaTests.save
 def capture(self,actor=None,**overrides):
  view=self.call('writer_candidates',project=self.pid)
  args=dict(project=self.pid,record_id='r000001',screening_event_hash=view['screening_event_hash'],mapping_event_hash=view['mapping_event_hash'],classification='synthetic',confirmed=True);args.update(overrides)
  return self.call('writer_capture',actor,**args)
 def manuscript(self):
  self.save();doc=self.capture();w=WriterService(self.store);e=w.evidence(self.pid,'Hunter',[dict(id='e1',document_id=doc['id'],locator='p:1',excerpt='Trial X and Trial Y enrolled adults.',support_note='Synthetic only',verified_by='Author',report_id='',study_ids=[])]);m=w.save(self.pid,'Hunter draft',[dict(title='Results',body='Synthetic [E:e1]')],e['id']);return w,doc,e,m
 def test_native_lineage_review_word(self):
  w,doc,e,m=self.manuscript();self.assertEqual(e['items'][0]['study_ids'],['trial_x']);self.assertEqual(e['items'][0]['report_id'],doc['native_hunter']['report_id']);w.review(self.pid,m['id'],'approved','Author','Checked',True);out=w.export_word(self.pid,m['id']);text='\n'.join(p.text for p in Document(io.BytesIO(base64.b64decode(out['content_base64']))).paragraphs);self.assertIn(doc['native_hunter']['mapping_event_hash'],text);self.assertEqual(out['audit']['references'][0]['captured_by'],'human')
 def test_role_project_and_confirmation(self):
  self.save()
  for actor in [self.m,self.x]:
   with self.assertRaises((PermissionError,ValueError)):self.capture(actor)
  with self.assertRaises(ValueError):self.capture(confirmed=False)
  with self.assertRaises(ValueError):self.capture(project=self.store.create('Other'))
  with self.assertRaises(ValueError):self.capture(record_id='unknown')
 def test_requires_mapping_and_complete_revealed_fulltext(self):
  with self.assertRaises(ValueError):self.call('writer_candidates',project=self.pid)
  self.save();self.s.ledger.adjudicate(self.r,'human','r000001','exclude','Changed','population','p:1','Trial X and Trial Y enrolled adults.')
  with self.assertRaises(ValueError):self.call('writer_candidates',project=self.pid)
  self.r=self.parent
  with self.assertRaises(ValueError):self.call('writer_candidates',project=self.pid)
 def test_mapping_revision_blocks_old_evidence(self):
  w,doc,e,m=self.manuscript();old=self.call('writer_candidates',project=self.pid);self.save(self.mapping([['trial_x'],['other_trial_updated']]))
  self.assertEqual(w.export(self.pid,m['id'])['manuscript']['id'],m['id'])
  self.save(self.mapping([['new_trial'],['other_trial_updated']]))
  with self.assertRaises(ValueError):self.capture(mapping_event_hash=old['mapping_event_hash'])
  with self.assertRaises(ValueError):w.export(self.pid,m['id'])
  fresh=self.capture();self.assertEqual(fresh['native_hunter']['study_ids'],['new_trial'])
 def test_source_and_file_replacement(self):
  w,doc,e,m=self.manuscript();p=self.store.artifact(self.pid,doc['snapshot']['blob']);raw=p.read_bytes();p.write_bytes(b'changed')
  with self.assertRaises(ValueError):w.export_word(self.pid,m['id'])
  p.write_bytes(raw);self.store.save(self.pid,doc['native_hunter']['source_artifact'],{'records':[]})
  with self.assertRaises(ValueError):w.export(self.pid,m['id'])
 def test_parent_history_and_conflicting_manual_id(self):
  w,doc,e,m=self.manuscript();self.s.ledger.adjudicate(self.parent,'human','r000001','exclude','Parent changed','population');self.assertTrue(self.call('writer_candidates',project=self.pid)['parent_changed']);w.export(self.pid,m['id'])
  item={k:e['items'][0][k] for k in ['id','document_id','locator','excerpt','support_note','verified_by','report_id','study_ids']};item['study_ids']=['forged']
  with self.assertRaises(ValueError):w.evidence(self.pid,'Bad',[item])
