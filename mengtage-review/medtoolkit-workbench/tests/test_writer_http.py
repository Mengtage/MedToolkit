import base64,unittest
import test_http_workflow as fixture
class WriterHTTP(unittest.TestCase):
 setUpClass=classmethod(fixture.WorkflowTest.setUpClass.__func__)
 tearDownClass=classmethod(fixture.WorkflowTest.tearDownClass.__func__)
 request=fixture.WorkflowTest.request
 project=fixture.WorkflowTest.project
 def test_manual_writer_http(self):
  p=self.project()
  def call(op,body,status=200):return self.request('/api/writer/'+op,{'project':p,**body},status)
  d=call('document',{'filename':'a.txt','content_base64':base64.b64encode(b'Example 42.').decode(),'source':'Synthetic','classification':'synthetic','confirmed':True})
  e=call('evidence',{'label':'Example','items':[{'id':'e1','document_id':d['id'],'locator':'p:1','excerpt':'Example 42.','support_note':'Example only','verified_by':'Author','report_id':'','study_ids':[]}],'parent_id':None})
  m=call('save',{'title':'Manuscript','sections':[{'title':'Results','body':'Example 42. [E:e1]'}],'evidence_id':e['id'],'manuscript_id':None,'expected_version':None})
  call('review',{'version':m['id'],'decision':'approved','author':'Author','note':'Checked','confirmed':False},400)
  call('review',{'version':m['id'],'decision':'approved','author':'Author','note':'Checked','confirmed':True});self.assertEqual(call('export',{'version':m['id']})['status'],'approved');self.assertEqual(len(self.request('/api/writer?project='+p)['heads']),1)
  self.request('/api/writer/load',{'project':self.project(),'id':m['id']},400)

  word=call('export_word',{'version':m['id']});self.assertTrue(base64.b64decode(word['content_base64']).startswith(b'PK'));self.assertEqual(word['manifest']['status'],'approved')
