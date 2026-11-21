import json,unittest,io,base64
from docx import Document
import test_writer as fixture
from workbench.core import canonical
class WriterStatisticsTest(unittest.TestCase):
 setUp=fixture.WriterTest.setUp
 def job(self):
  jid=self.store.enqueue(self.pid,'statistics',{'classification':'synthetic','method':'pearson','x':'x','y':'y','rows':[{'x':1,'y':2},{'x':2,'y':4},{'x':3,'y':5}]});self.store.run(jid);return jid
 def document(self):return self.s.capture_statistics(self.pid,self.job(),True)
 def manuscript(self):
  d=self.document();item={**self.item,'document_id':d['id'],'excerpt':'"method": "pearson"'};e=self.s.evidence(self.pid,'Stats',[item]);m=self.s.save(self.pid,'Stats',[{'title':'Result','body':'Synthetic correlation [E:e1]'}],e['id']);return d,e,m
 def test_binding_through_review_and_word(self):
  d,e,m=self.manuscript();self.assertEqual(e['items'][0]['native_statistics'],d['native_statistics']);self.s.review(self.pid,m['id'],'approved','Author','Checked synthetic results',True);out=self.s.export_word(self.pid,m['id']);self.assertEqual(out['audit']['references'][0]['native_statistics']['job_id'],d['native_statistics']['job_id']);doc=Document(io.BytesIO(base64.b64decode(out['content_base64'])));self.assertIn(d['native_statistics']['payload_sha256'],'\n'.join(p.text for p in doc.paragraphs))
 def test_changed_artifact_before_and_after_capture(self):
  d,e,m=self.manuscript();binding=d['native_statistics'];path=self.store.artifact(self.pid,binding['artifact']);data=json.loads(path.read_text());data['fake']=99;path.write_text(canonical(data))
  for fn in [lambda:self.s.capture_statistics(self.pid,binding['job_id'],True),lambda:self.s.export(self.pid,m['id']),lambda:self.s.review(self.pid,m['id'],'approved','Author','Checked',True)]:
   with self.assertRaises(ValueError):fn()
 def test_input_change_old_hash_and_cross_project(self):
  jid=self.job();other=self.store.create('Other')
  with self.assertRaises(ValueError):self.s.capture_statistics(other,jid,True)
  with self.assertRaises(ValueError):self.s.capture_statistics(self.pid,jid,False)
  with self.store.db() as db:
   row=db.execute('SELECT payload,result FROM jobs WHERE id=?',(jid,)).fetchone();payload=json.loads(row[0]);payload['rows'][0]['x']=9;db.execute('UPDATE jobs SET payload=? WHERE id=?',(canonical(payload),jid))
  with self.assertRaises(ValueError):self.s.capture_statistics(self.pid,jid,True)
  with self.store.db() as db:
   result=json.loads(row[1]);result.pop('artifact_sha256');db.execute('UPDATE jobs SET payload=?,result=? WHERE id=?',(row[0],canonical(result),jid))
  with self.assertRaisesRegex(ValueError,'旧任务'):self.s.capture_statistics(self.pid,jid,True)
 def test_pending_and_manual_documents_do_not_gain_native_identity(self):
  jid=self.store.enqueue(self.pid,'statistics',{'classification':'synthetic','method':'pearson','x':'x','y':'y','rows':[{'x':1,'y':2},{'x':2,'y':4},{'x':3,'y':5}]})
  with self.assertRaises(ValueError):self.s.capture_statistics(self.pid,jid,True)
  self.assertNotIn('native_statistics',self.package['items'][0])
 def test_capture_categorical_auto_uses_requested_method(self):
  jid=self.store.enqueue(self.pid,'statistics',{'classification':'synthetic','method':'categorical_auto','table':[[10,20],[20,10]],'row_labels':['g0','g1'],'column_labels':['o0','o1']});self.store.run(jid)
  doc=self.s.capture_statistics(self.pid,jid,True)
  self.assertEqual(doc['native_statistics']['method'],'categorical_auto')
