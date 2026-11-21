import json
import math
import tempfile
import unittest
from unittest.mock import patch
from workbench.core import Store


def payload(groups):
    return {'classification': 'synthetic', 'method': 'group_numeric', 'group': 'g', 'value': 'v',
            'rows': [{'g': str(i), 'v': v} for i, values in enumerate(groups) for v in values]}


class GroupAdapterTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(self.tmp.name)
        self.pid = self.store.create('Synthetic independent groups')

    def tearDown(self):
        self.tmp.cleanup()

    def run_groups(self, groups):
        p = payload(groups)
        jid = self.store.enqueue(self.pid, 'statistics', p)
        with patch('workbench.adapters.gemini') as model:
            result = self.store.run(jid)
            model.assert_not_called()
        saved = json.loads(self.store.artifact(self.pid, result['artifact']).read_text())
        self.assertEqual(saved['tests'], result['tests'])
        self.assertEqual(result['llm_calls'], 0)
        return result

    def test_two_groups_independent_formulas(self):
        r = self.run_groups([[1, 2, 3], [4, 5, 6]])
        self.assertAlmostEqual(r['tests']['welch_t_test']['statistic'], -3/math.sqrt(2/3))
        self.assertAlmostEqual(r['tests']['cohens_d'], -3)
        self.assertEqual(r['tests']['mann_whitney_u']['statistic'], 0)
        self.assertAlmostEqual(r['tests']['mann_whitney_u']['p_value'], 2/math.comb(6, 3))

    def test_three_groups_independent_sums_of_squares(self):
        r = self.run_groups([[1, 2, 3], [4, 5, 6], [7, 8, 9]])
        self.assertAlmostEqual(r['tests']['anova']['statistic'], (54/2)/(6/6))
        # Rank sums 6, 15, 24; no ties.
        expected = 12/(9*10)*sum(s*s/3 for s in (6, 15, 24))-3*10
        self.assertAlmostEqual(r['tests']['kruskal_wallis']['statistic'], expected)
        self.assertEqual(r['group_order'], ['0', '1', '2'])

    def test_missing_counts_and_group_order(self):
        r = self.run_groups([[4, 5, None, 6], [1, None, 2, 3]])
        self.assertEqual(r['input_rows'], 8)
        self.assertEqual(r['complete_rows'], 6)
        self.assertEqual(r['missing_by_group'], {'0': 1, '1': 1})
        self.assertAlmostEqual(r['tests']['cohens_d'], 3)

    def test_one_constant_group_supported(self):
        r = self.run_groups([[1, 1, 1], [2, 3, 4]])
        self.assertAlmostEqual(r['tests']['welch_t_test']['statistic'], -2/math.sqrt(1/3))

    def test_invalid_input_never_persisted(self):
        cases = [payload(g) for g in [[[1, 2], [3]], [[1, 2], [None, None]], [[1, 1], [2, 2]], [[1, 2, 3, 4]], [[1, 2], [True, 3]], [[1, 2], [float('inf'), 3]], [[1, 2], [1e101, 3]]]]
        p = payload([[1, 2], [3, 4]]);p['rows'][0]['g'] = None;cases.append(p)
        p = payload([[1, 2], [3, 4]]);p['classification'] = 'patient';cases.append(p)
        p = payload([[1, 2], [3, 4]]);p['rows'][0]['extra'] = 'marker';cases.append(p)
        for p in cases:
            with self.subTest(p=p), self.assertRaises(ValueError):
                self.store.enqueue(self.pid, 'statistics', p)
        self.assertEqual(self.store.jobs(self.pid), [])

    def test_nonfinite_computation_fails_without_artifact(self):
        jid = self.store.enqueue(self.pid, 'statistics', payload([[1, 2], [3, 4]]))
        with patch('workbench.groups.load_analyzer') as loader:
            loader.return_value.return_value.analyze_numeric.return_value = {'tests': {'statistic': float('nan')}}
            with self.assertRaises(ValueError):self.store.run(jid)
        self.assertEqual(self.store.jobs(self.pid)[0]['state'], 'failed')
        self.assertFalse(list((self.store.root/self.pid).glob('*statistics.json')))
