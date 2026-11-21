import copy
import json
import tempfile
import unittest
from workbench.core import Store


def payload():
    return {'classification':'synthetic','method':'prediction_evaluation','threshold':.5,'n_bins':4,'evaluation_scope':'held_out',
            'rows':[{'observed':y,'probability':p} for y,p in zip([0,0,1,1],[.1,.4,.35,.8])]}


class EvaluationAdapterTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.store=Store(self.tmp.name);self.pid=self.store.create('Synthetic evaluation')
    def tearDown(self):self.tmp.cleanup()
    def run_eval(self,p):
        jid=self.store.enqueue(self.pid,'statistics',p);r=self.store.run(jid)
        saved=json.loads(self.store.artifact(self.pid,r['artifact']).read_text())
        self.assertEqual(saved['roc'],r['roc']);self.assertEqual(r['llm_calls'],0)
        return r
    def test_auc_pairwise_and_brier_formula(self):
        p=payload();r=self.run_eval(p)
        positives=[x['probability'] for x in p['rows'] if x['observed']==1]
        negatives=[x['probability'] for x in p['rows'] if x['observed']==0]
        expected=sum((a>b)+.5*(a==b) for a in positives for b in negatives)/(len(positives)*len(negatives))
        self.assertAlmostEqual(r['roc']['auc'],expected)
        self.assertAlmostEqual(r['brier_score'],sum((x['probability']-x['observed'])**2 for x in p['rows'])/4)
        self.assertEqual(r['confusion_matrix']['matrix'],[[2,0],[1,1]])
        self.assertEqual(r['metrics']['sensitivity'],.5)
    def test_probability_endpoints_and_threshold_inclusive(self):
        p=payload();p['rows']=[{'observed':y,'probability':v} for y,v in [(0,0),(0,.5),(1,.5),(1,1)]]
        r=self.run_eval(p)
        self.assertEqual(r['confusion_matrix']['matrix'],[[1,1],[0,2]])
        self.assertEqual(sum(x['n'] for x in r['calibration_curve']),4)
        final=next(x for x in r['calibration_curve'] if x['bin']==4)
        self.assertEqual(final['mean_predicted'],1)
    def test_constant_probability_and_undefined_metrics(self):
        p=payload()
        for row in p['rows']:row['probability']=.2
        r=self.run_eval(p)
        self.assertEqual(r['roc']['auc'],.5)
        self.assertIsNone(r['metrics']['ppv']);self.assertIsNone(r['metrics']['mcc'])
        self.assertEqual(r['calibration_curve'][0]['n'],4)
    def test_bin_means_independent(self):
        r=self.run_eval(payload());middle=next(x for x in r['calibration_curve'] if x['bin']==2)
        self.assertAlmostEqual(middle['mean_predicted'],(.4+.35)/2)
        self.assertEqual(middle['mean_observed'],.5)
        self.assertNotIn('hosmer_lemeshow',r)
        self.assertEqual(r['threshold'],.5)
    def test_invalid_inputs_not_saved(self):
        cases=[]
        for k,v in [('classification','patient'),('threshold',True),('threshold',1.1),('n_bins',5),('evaluation_scope','unknown'),('extra',42)]:
            p=payload();p[k]=v;cases.append(p)
        for value in [None,True,float('nan'),-.1]:
            p=payload();p['rows'][0]['probability']=value;cases.append(p)
        p=payload()
        for row in p['rows']:row['observed']=1
        cases.append(p)
        for p in cases:
            with self.subTest(p=p),self.assertRaises(ValueError):self.store.enqueue(self.pid,'statistics',p)
        self.assertEqual(self.store.jobs(self.pid),[])
