import copy,unittest
import test_http_workflow as fixture
from test_evaluation_extended_adapter import payload

class ExtendedEvaluationHTTP(unittest.TestCase):
    setUpClass=classmethod(fixture.WorkflowTest.setUpClass.__func__)
    tearDownClass=classmethod(fixture.WorkflowTest.tearDownClass.__func__)
    request=fixture.WorkflowTest.request
    project=fixture.WorkflowTest.project
    finish=fixture.WorkflowTest.finish
    def test_extended_http_persistence_and_refusal(self):
        pid=self.project();p=payload();bad=copy.deepcopy(p);bad['paired_confirmed']=False
        self.request('/api/jobs',{'project':pid,'kind':'statistics','payload':bad},400)
        self.assertEqual(self.request('/api/jobs?project='+pid),[])
        jid=self.request('/api/jobs',{'project':pid,'kind':'statistics','payload':p},201)['id'];job=self.finish(pid,jid);self.assertEqual(job['state'],'completed')
        import json
        result=json.loads(job['result']);saved=self.request('/api/artifact?project='+pid+'&name='+result['artifact'])
        self.assertEqual(saved['method'],'prediction_evaluation_extended');self.assertIsNone(saved['dca']['net_benefit'][-1]);self.assertEqual(saved['n'],8)
        self.assertIn('prediction_evaluation_extended',self.request('/api/capabilities')['statistical_methods'])
