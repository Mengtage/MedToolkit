import base64,json,tempfile,unittest
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor
from workbench.core import Store
from workbench.writer import WriterService
class WriterTest(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.store=Store(self.tmp.name);self.pid=self.store.create('Synthetic');self.s=WriterService(self.store)
  self.doc=self.s.document(self.pid,'a.txt',base64.b64encode(b'Synthetic finding 42.\fSecond page.').decode(),'Synthetic DOI','synthetic',True)
  self.item={'id':'e1','document_id':self.doc['id'],'locator':'p:1','excerpt':'Synthetic finding 42.','support_note':'Synthetic only','verified_by':'Author','report_id':'','study_ids':[]};self.package=self.s.evidence(self.pid,'Synthetic',[self.item])
 def save(self,body='Synthetic finding 42. [E:e1]',**kw):return self.s.save(self.pid,'合成稿件',[{'title':'结果','body':body}],self.package['id'],**kw)
 def approve(self,m):return self.s.review(self.pid,m['id'],'approved','Author','Checked source and claims',True)
 def test_lifecycle_review_export_revision(self):
  m=self.save();self.assertIn('未批准草稿',self.s.export(self.pid,m['id'])['markdown']);self.approve(m);out=self.s.export(self.pid,m['id']);self.assertIn('已获作者批准',out['markdown']);self.assertEqual([e['id'] for e in out['references']],['e1'])
  n=self.save(manuscript_id=m['manuscript_id'],expected_version=m['id']);self.assertEqual(self.s.inspect(self.pid,n['id'])['status'],'needs_human_review');self.assertEqual(self.s.inspect(self.pid,m['id'])['status'],'approved')
  with self.assertRaises(ValueError):self.approve(m)
  self.s.review(self.pid,n['id'],'changes_requested','Author','Need changes',True);self.assertEqual(self.s.inspect(self.pid,n['id'])['status'],'changes_requested')
 def test_wrong_page_quote_unknown_duplicate(self):
  for change in [{'locator':'p:2'},{'excerpt':'not present'},{'document_id':'unknown'},{'locator':'p:0'}]:
   with self.subTest(change=change),self.assertRaises(ValueError):self.s.evidence(self.pid,'bad',[{**self.item,**change}])
  with self.assertRaises(ValueError):self.s.evidence(self.pid,'bad',[self.item,self.item])
 def test_cross_project_paths(self):
  p=self.store.create('Other');m=self.save()
  for fn in [lambda:self.s.load(p,self.doc['id']),lambda:self.s.evidence(p,'bad',[self.item]),lambda:self.s.load('../escape',self.doc['id']),lambda:self.s.inspect(p,m['id'])]:
   with self.assertRaises(ValueError):fn()
 def test_source_tampering(self):
  m=self.save();self.store.artifact(self.pid,self.doc['snapshot']['blob']).write_text('changed')
  for fn in [lambda:self.approve(m),lambda:self.s.export(self.pid,m['id'])]:
   with self.assertRaises(ValueError):fn()
 def test_snapshot_tampering(self):
  self.store.save(self.pid,'writer-'+self.package['id']+'.json',{'items':[]})
  with self.assertRaises(ValueError):self.save()
 def test_citation_blockers_warnings(self):
  for body in ['no citation','wrong [E:unknown]','bad [E:e1] [E:bad space]','[待补证据] [E:e1]']:
   m=self.save(body)
   with self.subTest(body=body),self.assertRaises(ValueError):self.approve(m)
  m=self.save('42 without citation\n\nSupported [E:e1]');self.assertTrue(m['checks']['warnings']);self.assertFalse(m['checks']['blockers'])
  m_sub=self.save('### 1.1 Subheading with number\n\nSupported [E:e1]');self.assertFalse(m_sub['checks']['warnings']);self.assertFalse(m_sub['checks']['blockers'])
  m_imrad=self.s.save(self.pid,'SCI稿件',[{'title':'摘要','body':'目的：评估疼痛。\n方法：范围综述。\n结果：纳入36项研究。\n结论：可行。'},{'title':'关键词','body':'术后疼痛；人工智能；范围综述'},{'title':'1. 引言','body':'背景阐述 [E:e1]。'},{'title':'2. 方法','body':'检索2022至2026年文献。'},{'title':'5. 结论','body':'本研究总结了核心证据。'},{'title':'6. 声明','body':'无利益冲突。'}],self.package['id'])
  self.assertFalse(m_imrad['checks']['blockers']);self.assertFalse(m_imrad['checks']['warnings'])
  m_bad_sci=self.s.save(self.pid,'Bad SCI',[{'title':'摘要','body':'摘要误引文献 [E:e1]'},{'title':'结果','body':'在 /sources 中运行 tableone 得到 P = 0.000 [E:e1]'}],self.package['id'])
  self.assertGreaterEqual(len(m_bad_sci['checks']['warnings']),3)
 def test_confirmation_validation(self):
  m=self.save()
  with self.assertRaises(ValueError):self.s.review(self.pid,m['id'],'approved','Author','Checked',False)
  with self.assertRaises(ValueError):self.s.document(self.pid,'x.txt','eA==','source','private',True)
  with self.assertRaises(ValueError):self.s.save(self.pid,'title',[],self.package['id'])
  with self.assertRaises(ValueError):self.s.dispatch('export',{'project':self.pid,'version':m['id'],'actor':'other'})
 def test_concurrent_edit(self):
  m=self.save()
  def update(i):
   try:return self.save(f'Edit {i} [E:e1]',manuscript_id=m['manuscript_id'],expected_version=m['id'])['id']
   except ValueError:return None
  with ThreadPoolExecutor(2) as pool:results=list(pool.map(update,[1,2]))
  self.assertEqual(sum(x is not None for x in results),1)
 def test_package_revision_export_fixed(self):
  m=self.save();out=self.s.export(self.pid,m['id']);new=self.s.evidence(self.pid,'Revised',[{**self.item,'support_note':'Changed'}],self.package['id']);self.assertEqual(new['parent_id'],self.package['id']);self.assertEqual(self.s.load(self.pid,out['id'])['evidence']['id'],self.package['id'])
 def test_review_chain_tampering(self):
  m=self.save();self.approve(m)
  with self.store.db() as db:db.execute('UPDATE writer_reviews SET event=?',(json.dumps({'hash':'bad','previous_hash':''}),))
  with self.assertRaises(ValueError):self.s.export(self.pid,m['id'])
 def test_no_model_calls(self):
  with patch('urllib.request.urlopen',side_effect=AssertionError('No network')):
   m=self.save();self.approve(m);self.assertEqual(self.s.export(self.pid,m['id'])['llm_calls'],0)
