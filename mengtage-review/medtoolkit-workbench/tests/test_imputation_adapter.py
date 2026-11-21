import copy
import json
import math
import statistics
import tempfile
import unittest
from workbench.core import Store


def payload():
    return {'classification':'synthetic','method':'mice_imputation','strategy':'bayesian_ridge',
        'n_imputations':3,'max_iter':5,'pool_means':True,
        'variable_types':{'x':'numeric_continuous','y':'numeric_continuous'},
        'rows':[{'x':x,'y':y} for x,y in [(1,2),(2,5),(3,None),(4,7),(5,11),(6,None),(7,13),(8,17)]]}


class ImputationAdapterTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.store=Store(self.tmp.name);self.pid=self.store.create('Synthetic imputation')
    def tearDown(self):self.tmp.cleanup()
    def run_impute(self,p,pid=None):
        pid=pid or self.pid;jid=self.store.enqueue(pid,'statistics',p);r=self.store.run(jid)
        saved=json.loads(self.store.artifact(pid,r['artifact']).read_text())
        self.assertEqual(saved['datasets'],r['datasets']);return r
    def test_observed_values_and_reproducibility(self):
        p=payload();a=self.run_impute(p);b=self.run_impute(p,self.store.create('Repeat'))
        self.assertEqual(a['datasets'],b['datasets']);self.assertEqual(a['random_seeds'],[42,43,44])
        for dataset in a['datasets']:
            for original,row in zip(p['rows'],dataset):
                for key,value in original.items():
                    if value is not None:self.assertEqual(row[key],value)
                    self.assertTrue(math.isfinite(row[key]))
        self.assertEqual(a['missing_row_indices']['y'],[2,5])
    def test_rubin_variance_and_degrees_from_actual_datasets(self):
        r=self.run_impute(payload());sets=[[row['y'] for row in ds] for ds in r['datasets']]
        estimates=[statistics.mean(ds) for ds in sets];variances=[statistics.variance(ds)/len(ds) for ds in sets]
        u=statistics.mean(variances);b=statistics.variance(estimates);t=u+(1+1/3)*b
        fraction=(1+1/3)*b/t;old=2/fraction**2;observed=(8/10)*7*(1-fraction);df=1/(1/old+1/observed)
        pooled=r['pooled_means'][0]
        self.assertAlmostEqual(pooled['pooled_estimate'],statistics.mean(estimates))
        self.assertAlmostEqual(pooled['total_variance'],t)
        self.assertAlmostEqual(pooled['pooled_standard_error'],math.sqrt(t))
        self.assertAlmostEqual(pooled['degrees_of_freedom'],df)
    def test_deterministic_single_imputation_no_pooling(self):
        p=payload();p.update(strategy='linear',n_imputations=1,pool_means=False)
        r=self.run_impute(p);self.assertEqual(r['actual_imputations'],1);self.assertEqual(r['pooled_means'],[])
    def test_no_missing_returns_one_unchanged_dataset(self):
        p=payload()
        for row in p['rows']:
            if row['y'] is None:row['y']=999
        r=self.run_impute(p);self.assertEqual(r['datasets'],[p['rows']]);self.assertEqual(r['actual_imputations'],1)
        self.assertEqual(r['random_seeds'],[]);self.assertEqual(r['pooled_means'],[])
    def test_invalid_inputs_never_persisted(self):
        cases=[]
        for key,value in [('strategy','linear'),('n_imputations',True),('max_iter',51),('pool_means','yes'),('classification','patient'),('missing_codes',[999])]:
            p=payload();p[key]=value;cases.append(p)
        p=payload();p['variable_types']['y']='categorical';cases.append(p)
        p=payload()
        for row in p['rows']:row['y']=None
        cases.append(p)
        p=payload();p['rows'][0]['x']=True;cases.append(p)
        p=payload();p.update(n_imputations=1,pool_means=True);cases.append(p)
        for p in cases:
            with self.subTest(p=p),self.assertRaises(ValueError):self.store.enqueue(self.pid,'statistics',p)
        self.assertEqual(self.store.jobs(self.pid),[])
