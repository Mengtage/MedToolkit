import math
import tempfile
import unittest
from workbench.core import Store


def payload(method='poisson_regression'):
    return {'classification':'synthetic','method':method,'outcome':'y','predictors':['x'],
            'rows':[{'x':x,'y':y} for x,ys in [(0,[1,2,3,2]),(1,[2,4,6,4])] for y in ys]}


class GLMAdapterTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.store=Store(self.tmp.name);self.pid=self.store.create('Synthetic GLM')
    def tearDown(self):self.tmp.cleanup()
    def run_model(self,p):
        jid=self.store.enqueue(self.pid,'statistics',p);return self.store.run(jid)
    def test_poisson_group_mean_solution(self):
        r=self.run_model(payload())
        self.assertAlmostEqual(r['coefficients']['Intercept'],math.log(2))
        self.assertAlmostEqual(r['coefficients']['x'],math.log(2))
        self.assertAlmostEqual(r['std_errors']['x'],math.sqrt(1/8+1/16),places=5)
        self.assertAlmostEqual(r['mean_ratios']['x'],2)
        for a,b in zip(r['fitted_means'],[2]*4+[4]*4):self.assertAlmostEqual(a,b)
        self.assertEqual(r['link'],'log')
    def test_gamma_inverse_group_mean_solution(self):
        r=self.run_model(payload('gamma_regression'))
        self.assertAlmostEqual(r['coefficients']['Intercept'],.5)
        self.assertAlmostEqual(r['coefficients']['x'],-.25)
        for a,b in zip(r['fitted_means'],[2]*4+[4]*4):self.assertAlmostEqual(a,b)
        self.assertEqual(r['coefficient_ci_scale'],'inverse_mean')
        self.assertNotIn('mean_ratios',r)
        self.assertEqual(r['link'],'inverse')
    def test_complete_case_indices(self):
        p=payload();p['rows'].append({'x':None,'y':2});r=self.run_model(p)
        self.assertEqual(r['complete_rows'],8);self.assertEqual(r['excluded_missing_rows'],1)
        self.assertEqual(r['included_row_indices'],list(range(8)))
    def test_outcome_domains_and_extra_parameters_rejected(self):
        cases=[]
        for method,y in [('poisson_regression',-1),('poisson_regression',1.5),('gamma_regression',0),('gamma_regression',-1)]:
            p=payload(method);p['rows'][0]['y']=y;cases.append(p)
        p=payload();p['exposure']=[1]*8;cases.append(p)
        p=payload();p['classification']='patient';cases.append(p)
        for p in cases:
            with self.subTest(p=p),self.assertRaises(ValueError):self.store.enqueue(self.pid,'statistics',p)
        self.assertEqual(self.store.jobs(self.pid),[])
