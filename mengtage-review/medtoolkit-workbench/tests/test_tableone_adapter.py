import copy
import json
import math
import tempfile
import unittest
from workbench.core import Store


def payload(strata=True):
    p = {'classification': 'synthetic', 'method': 'tableone',
         'variable_types': {'g': 'categorical', 'v': 'numeric_continuous', 'c': 'categorical'},
         'rows': [{'g': g, 'v': v, 'c': c} for g, vs in [('A', [1, 2, 3]), ('B', [4, 5, 6])] for v, c in zip(vs, ['yes', 'no', None])]}
    if strata:p['strata'] = 'g'
    return p


class TableOneAdapterTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(self.tmp.name)
        self.pid = self.store.create('Synthetic baseline')

    def tearDown(self):self.tmp.cleanup()

    def run_table(self, p):
        jid = self.store.enqueue(self.pid, 'statistics', p)
        result = self.store.run(jid)
        saved = json.loads(self.store.artifact(self.pid, result['artifact']).read_text())
        self.assertEqual(saved['table'], result['table'])
        self.assertEqual(result['llm_calls'], 0)
        return result

    def test_grouped_summary_and_missing_denominator(self):
        r = self.run_table(payload())
        numeric = [row for row in r['table'] if row['variable'] == 'v']
        self.assertEqual([x['mean'] for x in numeric], [2, 5])
        self.assertEqual([x['sd'] for x in numeric], [1, 1])
        yes = [row for row in r['table'] if row['variable'] == 'c' and row['level'] == 'yes']
        self.assertEqual([x['percent'] for x in yes], [50, 50])
        self.assertEqual(r['missingness']['A']['c'], {'n_valid': 2, 'n_missing': 1})
        t = next(x for x in r['p_values'] if x['variable'] == 'v')
        self.assertEqual(t['test'], 'Independent t-test')
        self.assertAlmostEqual(t['statistic'], -3/math.sqrt(2/3))

    def test_overall_and_single_observation_sd(self):
        p = {'classification': 'synthetic', 'method': 'tableone', 'variable_types': {'v': 'numeric_continuous'}, 'rows': [{'v': 7}]}
        r = self.run_table(p)
        self.assertEqual(r['table'][0]['mean'], 7)
        self.assertIsNone(r['table'][0]['sd'])
        self.assertEqual(r['p_values'], [])

    def test_infinite_fisher_or_has_explicit_boundary(self):
        p = {'classification': 'synthetic', 'method': 'tableone', 'strata': 'g', 'variable_types': {'g': 'categorical', 'c': 'categorical'}, 'rows': [{'g': g, 'c': c} for g,c in [('A','no')]*3+[('B','yes')]*3]}
        r = self.run_table(p)
        test = r['p_values'][0]
        self.assertAlmostEqual(test['p_value'], 2/math.comb(6, 3))
        self.assertIsNone(test['statistic'])
        self.assertEqual(r['nonfinite_boundary_fields'], ['p_values.0.statistic'])

    def test_all_types_explicit_and_bad_inputs_not_saved(self):
        cases=[]
        for field, value in [('classification', 'patient'), ('strata','v'), ('variable_types', {'v':'guessed'}), ('extra','marker')]:
            p=payload();p[field]=value;cases.append(p)
        p=payload();p['rows'][0]['g']=None;cases.append(p)
        p=payload();p['rows'][0]['v']=True;cases.append(p)
        p=payload();p['rows'][0]['v']=None;p['rows'][1]['v']=None;cases.append(p)
        p=payload();p['rows'][0]['extra']='marker';cases.append(p)
        p=payload();
        for row in p['rows']:row['v']=1
        cases.append(p)
        for p in cases:
            with self.subTest(p=p), self.assertRaises(ValueError):self.store.enqueue(self.pid,'statistics',p)
        self.assertEqual(self.store.jobs(self.pid),[])

    def test_overall_sd_independent_formula(self):
        r=self.run_table(payload(False))
        row=next(x for x in r['table'] if x['variable']=='v')
        self.assertAlmostEqual(row['sd'], math.sqrt(sum((i-3.5)**2 for i in range(1,7))/5))
        self.assertEqual(r['p_values'],[])
