import copy
import json
import math
import tempfile
import unittest
from workbench.core import Store


def linear():
    return {'classification':'synthetic','method':'linear_regression','outcome':'y','predictors':['x'],
            'rows':[{'x':x,'y':y} for x,y in zip([0,1,2,3,4],[1,2,2,4,6])]}


def logistic():
    return {'classification':'synthetic','method':'logistic_regression','outcome':'y','predictors':['x'],
            'rows':[{'x':x,'y':y} for x,ys in [(0,[0]*6+[1]*2),(1,[0]*2+[1]*6)] for y in ys]}


class RegressionAdapterTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.store=Store(self.tmp.name);self.pid=self.store.create('Synthetic regression')
    def tearDown(self):self.tmp.cleanup()
    def run_model(self,p):
        jid=self.store.enqueue(self.pid,'statistics',p);r=self.store.run(jid)
        saved=json.loads(self.store.artifact(self.pid,r['artifact']).read_text())
        self.assertEqual(saved['coefficients'],r['coefficients']);self.assertEqual(r['llm_calls'],0)
        return r
    def test_ols_against_independent_normal_equations(self):
        p=linear();r=self.run_model(p)
        xs=[a['x'] for a in p['rows']];ys=[a['y'] for a in p['rows']]
        xm=sum(xs)/5;ym=sum(ys)/5;sxx=sum((x-xm)**2 for x in xs)
        slope=sum((x-xm)*(y-ym) for x,y in zip(xs,ys))/sxx;intercept=ym-slope*xm
        mse=sum((y-intercept-slope*x)**2 for x,y in zip(xs,ys))/3
        self.assertAlmostEqual(r['coefficients']['x'],slope)
        self.assertAlmostEqual(r['coefficients']['Intercept'],intercept)
        self.assertAlmostEqual(r['std_errors']['x'],math.sqrt(mse/sxx))
        self.assertEqual(r['df_resid'],3)
    def test_logistic_against_grouped_binomial_solution(self):
        r=self.run_model(logistic())
        self.assertAlmostEqual(r['coefficients']['Intercept'],math.log(1/3))
        self.assertAlmostEqual(r['coefficients']['x'],math.log(9))
        self.assertAlmostEqual(r['odds_ratios']['x'],9)
        se=math.sqrt(1/6+1/2+1/2+1/6)
        self.assertAlmostEqual(r['std_errors']['x'],se)
        self.assertAlmostEqual(r['odds_ratio_ci_lower']['x'],math.exp(math.log(9)-1.959963984540054*se))
        for observed,expected in zip(r['fitted_probabilities'],[.25]*8+[.75]*8):self.assertAlmostEqual(observed,expected)
        self.assertEqual(r['coefficient_ci_scale'],'log_odds')
    def test_missing_rows_and_names_preserved(self):
        p=linear();p['rows'].insert(1,{'x':None,'y':8});r=self.run_model(p)
        self.assertEqual(r['included_row_indices'],[0,2,3,4,5]);self.assertEqual(r['excluded_missing_rows'],1)
        self.assertEqual(r['parameter_order'],['Intercept','x'])
    def test_bad_inputs_and_rank_rejected_before_storage(self):
        cases=[]
        p=linear();p['predictors']=['x','x'];cases.append(p)
        p=linear();p['predictors']=['x','y'];cases.append(p)
        p=linear();p['classification']='patient';cases.append(p)
        p=linear();p['rows'][0]['x']=True;cases.append(p)
        p=linear();p['predictors']=['x','z'];p['rows']=[{**r,'z':r['x']*2} for r in p['rows']];cases.append(p)
        p=linear();p['rows']=[{'x':1,'y':r['y']} for r in p['rows']];cases.append(p)
        p=logistic();p['rows'][0]['y']=2;cases.append(p)
        p=logistic();p['rows']=[{**r,'y':1} for r in p['rows']];cases.append(p)
        p=linear();p['formula']='unsafe';cases.append(p)
        for p in cases:
            with self.subTest(p=p), self.assertRaises(ValueError):self.store.enqueue(self.pid,'statistics',p)
        self.assertEqual(self.store.jobs(self.pid),[])
    def test_separation_fails_without_statistics_artifact(self):
        p=logistic();p['rows']=[{'x':i,'y':int(i>=4)} for i in range(8)]
        jid=self.store.enqueue(self.pid,'statistics',p)
        with self.assertRaises(ValueError):self.store.run(jid)
        self.assertEqual(self.store.jobs(self.pid)[0]['state'],'failed')
        self.assertFalse(list((self.store.root/self.pid).glob('*statistics.json')))
