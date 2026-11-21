"""Source API acceptance, including the larger but bounded import body."""
import unittest
import test_http_workflow as fixture

class SourceHTTPTests(unittest.TestCase):
    setUpClass=classmethod(fixture.WorkflowTest.setUpClass.__func__)
    tearDownClass=classmethod(fixture.WorkflowTest.tearDownClass.__func__)
    request=fixture.WorkflowTest.request
    project=fixture.WorkflowTest.project
    def body(self,pid,abstract='Synthetic'):
        return {'project':pid,'metadata':{'database':'Synthetic database','kind':'database','query':'Synthetic','searched_at':'2026-11-21','total_hits':1,'complete':True,'coverage_note':'Synthetic only'},'records':[{'title':'Synthetic','abstract':abstract}],'confirmed':True}
    def test_large_import_and_content_limit(self):
        pid=self.project();result=self.request('/api/sources/import_records',self.body(pid,'x'*1_100_000),201)
        self.assertTrue(result['artifact'].startswith('source-'))
        self.request('/api/sources/import_records',self.body(pid,'x'*2_000_000),400)
        self.assertEqual(len(self.request('/api/sources?project='+pid)['runs']),1)
    def test_source_list_version_and_fields(self):
        pid=self.project();body=self.body(pid);self.request('/api/sources/import_records',{**body,'actor':'forged'},400)
        run=self.request('/api/sources/import_records',body,201);self.assertTrue(self.request('/api/sources/import_records',body,201)['reused'])
        args={'project':pid,'label':'Version one','source_ids':[run['id']],'parent_id':None,'reason':'Synthetic confirmed selection','confirmed':True}
        collection=self.request('/api/sources/create',args,201)
        listing=self.request('/api/sources?project='+pid);self.assertEqual(listing['collections'][0]['id'],collection['id'])
        self.request('/api/sources/create',{**args,'source_ids':[run['id'],run['id']]},400)
        other=self.project();self.request('/api/sources/create',{**args,'project':other},400)
