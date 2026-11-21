import copy
import json
import math
import tempfile
import unittest
from unittest.mock import patch
from workbench.core import Store


def payload(method='fisher', table=None):
    table = table if table is not None else [[1, 9], [11, 3]]
    return {'classification': 'synthetic', 'method': method, 'table': table,
            'row_labels': [f'group{i}' for i in range(len(table))],
            'column_labels': [f'outcome{i}' for i in range(len(table[0]))]}


class CategoricalAdapterTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(self.tmp.name)
        self.pid = self.store.create('Synthetic contingency tables')

    def tearDown(self):
        self.tmp.cleanup()

    def run_table(self, p):
        jid = self.store.enqueue(self.pid, 'statistics', p)
        with patch('workbench.adapters.gemini') as model:
            result = self.store.run(jid)
            model.assert_not_called()
        saved = json.loads(self.store.artifact(self.pid, result['artifact']).read_text())
        self.assertEqual(saved['table'], p['table'])
        self.assertEqual(saved['row_labels'], p['row_labels'])
        self.assertEqual(saved['llm_calls'], 0)
        return result

    def test_fisher_against_hypergeometric_enumeration(self):
        result = self.run_table(payload())
        probabilities = [math.comb(12, a) * math.comb(12, 10-a) / math.comb(24, 10) for a in range(11)]
        expected = sum(p for p in probabilities if p <= probabilities[1] + 1e-15)
        self.assertAlmostEqual(result['p_value'], expected, places=12)
        self.assertAlmostEqual(result['statistic'], 1/33, places=12)

    def test_pearson_and_yates_against_formula(self):
        for method, correction in [('chi2', 0), ('yates', .5)]:
            with self.subTest(method=method):
                r = self.run_table(payload(method, [[10, 20], [20, 10]]))
                expected = 4 * (5-correction)**2 / 15
                self.assertAlmostEqual(r['statistic'], expected, places=12)

    def test_auto_preserves_existing_selection(self):
        for table, name in [([[1, 2], [3, 4]], 'Fisher'), ([[5, 5], [5, 5]], 'Yates'), ([[10, 20], [20, 10]], 'Pearson')]:
            with self.subTest(name=name):
                self.assertIn(name, self.run_table(payload('categorical_auto', table))['method'])

    def test_monte_carlo_metadata_and_repeatability(self):
        p = payload('fisher', [[1, 0, 1], [0, 1, 1], [1, 1, 0]])
        a = self.run_table(p)
        p['row_labels'][0] = 'renamed-group'
        b = self.run_table(p)
        self.assertTrue(a['p_value_is_approximate'])
        self.assertEqual(a['random_seed'], 20261119)
        self.assertEqual(a['n_resamples'], 19999)
        self.assertEqual(a['p_value'], b['p_value'])
        self.assertNotEqual(a['input_sha256'], b['input_sha256'])

    def test_zero_cell_boundary_serializes(self):
        r = self.run_table(payload('fisher', [[0, 4], [3, 0]]))
        self.assertTrue(r['odds_ratio_boundary'])
        self.assertEqual(r['statistic'], 0)

    def test_invalid_inputs_never_persist(self):
        cases = []
        for table in [[], [[1, 2], [3]], [[True, 2], [3, 4]], [[1.5, 2], [3, 4]], [[-1, 2], [3, 4]], [[0, 0], [3, 4]], [[0, 2], [0, 4]], [[1000000, 1], [1, 1]]]:
            p = payload();p['table'] = table;cases.append(p)
        for key, value in [('classification', 'patient'), ('row_labels', ['same', 'same']), ('column_labels', ['one']), ('method', 'unknown'), ('extra', 'marker')]:
            p = payload();p[key] = value;cases.append(p)
        cases.append(payload('yates', [[1, 2, 3], [4, 5, 6]]))
        for p in cases:
            with self.subTest(p=p), self.assertRaises(ValueError):
                self.store.enqueue(self.pid, 'statistics', p)
        self.assertEqual(self.store.jobs(self.pid), [])
