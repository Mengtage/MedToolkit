"""Independent arithmetic, symmetry and boundary checks for the unified adapter."""
import copy,json,math,tempfile,unittest
from pathlib import Path
from fractions import Fraction
from workbench.core import Store
from workbench.evaluation_extended import validate

def payload():return json.loads((Path(__file__).resolve().parents[1]/'examples/evaluation_extended.json').read_text())

class ExtendedAdapterTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.store=Store(self.tmp.name);self.pid=self.store.create('Synthetic extended evaluation')
    def run_eval(self,p):
        jid=self.store.enqueue(self.pid,'statistics',p);r=self.store.run(jid)
        self.assertEqual(json.loads(self.store.artifact(self.pid,r['artifact']).read_text())['input_sha256'],r['input_sha256']);self.assertEqual(r['llm_calls'],0)
        json.dumps(r,allow_nan=False);return r
    def test_hl_two_cells_and_actual_nonempty_groups(self):
        p=payload();p['n_bins']=8;r=self.run_eval(p);hl=r['hosmer_lemeshow']
        # Exact rational Pearson table statistic for groups (O1,O0)=(1,1).
        expected=Fraction(496,63)
        self.assertAlmostEqual(hl['statistic'],float(expected));self.assertEqual(hl['df'],2);self.assertEqual(hl['occupied_bins'],4)
        self.assertAlmostEqual(hl['p_value'],math.exp(-float(expected)/2))
        self.assertEqual(hl['binning'],'legacy_equal_width');self.assertTrue(hl['small_expected_cells'])
    def test_dca_independent_weighted_outcome_sum(self):
        p=payload();r=self.run_eval(p);d=r['dca'];old=r['comparison']['old_model_dca']
        for i,t in enumerate(p['dca_thresholds']):
            if t==1:self.assertIsNone(d['net_benefit'][i]);self.assertIsNone(old['net_benefit'][i]);continue
            odds=Fraction(str(t))/(1-Fraction(str(t)))
            for key,result in [('probability',d),('old_probability',old)]:
                utility=sum((Fraction(row['observed'])-(1-row['observed'])*odds) if row[key]>=t else 0 for row in p['rows'])/len(p['rows'])
                self.assertAlmostEqual(result['net_benefit'][i],float(utility))
            self.assertEqual(d['net_benefit_none'][i],0)
        self.assertEqual(d['undefined_thresholds'],[1.0])
    def test_idi_paired_estimate_and_variance(self):
        p=payload();p['rows']=[{'observed':y,'probability':n,'old_probability':o} for y,n,o in [(1,.3,.2),(1,.7,.4),(0,.3,.4),(0,.7,.6)]];p['n_bins']=4
        r=self.run_eval(p)['comparison']['idi'];self.assertAlmostEqual(r['idi'],.2);self.assertAlmostEqual(r['se'],math.sqrt(.02));self.assertAlmostEqual(r['z_score'],math.sqrt(2))
        self.assertEqual(r['inference_status'],'approximate_fixed_predictions')
    def test_model_swap_reverses_nri_idi_not_standard_error(self):
        p=payload();a=self.run_eval(p)['comparison'];q=copy.deepcopy(p)
        for row in q['rows']:row['probability'],row['old_probability']=row['old_probability'],row['probability']
        b=self.run_eval(q)['comparison'];self.assertAlmostEqual(a['idi']['idi'],-b['idi']['idi']);self.assertAlmostEqual(a['idi']['se'],b['idi']['se'])
        for key in a['nri']:self.assertAlmostEqual(a['nri'][key]['nri_total'],-b['nri'][key]['nri_total'])
    def test_pair_order_invariance_and_identical_models(self):
        p=payload();a=self.run_eval(p);p['rows'].reverse();b=self.run_eval(p)
        self.assertEqual(a['comparison']['nri'],b['comparison']['nri']);self.assertAlmostEqual(a['comparison']['idi']['se'],b['comparison']['idi']['se'])
        for row in p['rows']:row['old_probability']=row['probability']
        r=self.run_eval(p);self.assertEqual(r['comparison']['idi']['idi'],0);self.assertIsNone(r['comparison']['idi']['z_score'])
        self.assertTrue(all(v['nri_total']==0 for v in r['comparison']['nri'].values()))
    def test_endpoints_small_groups_and_null_json(self):
        p=payload();p['rows']=[{'observed':0,'probability':0,'old_probability':.1},{'observed':1,'probability':1,'old_probability':.9}];p['n_bins']=2
        r=self.run_eval(p);self.assertIsNone(r['hosmer_lemeshow']['statistic']);self.assertIsNone(r['hosmer_lemeshow']['p_value']);self.assertIsNone(r['comparison']['idi']['se'])
        self.assertEqual(r['comparison']['idi']['inference_status'],'insufficient_group_size')
    def test_single_model_and_threshold_ties(self):
        p=payload();del p['paired_confirmed'];del p['nri_thresholds']
        for row in p['rows']:del row['old_probability'];row['probability']=.5
        r=self.run_eval(p);self.assertIsNone(r['comparison']);self.assertIsNone(r['hosmer_lemeshow']['p_value'])
        self.assertEqual(r['dca']['net_benefit'][2],0);self.assertEqual(r['dca']['net_benefit'][3],0)
    def test_invalid_inputs_rejected_before_persistence(self):
        cases=[]
        for key,value in [('paired_confirmed',False),('nri_thresholds',[0,.5]),('dca_thresholds',[.5,.5]),('dca_thresholds',[1,.5]),('dca_thresholds',[True]),('dca_thresholds',[float('nan')]),('dca_thresholds',[.1]*202),('classification','patient')]:
            p=payload();p[key]=value;cases.append(p)
        p=payload();del p['rows'][0]['old_probability'];cases.append(p)
        for bad in [None,True,-.1,float('inf')]:
            p=payload();p['rows'][0]['old_probability']=bad;cases.append(p)
        for p in cases:
            with self.assertRaises(ValueError):self.store.enqueue(self.pid,'statistics',p)
        self.assertEqual(self.store.jobs(self.pid),[])
