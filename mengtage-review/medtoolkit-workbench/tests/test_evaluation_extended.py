"""Hand-calculated counterexamples for legacy evaluation, no clinical data."""
import importlib.util
from pathlib import Path
import unittest
import json
import math
from scipy.stats import chi2
P=Path(__file__).resolve().parents[1]/'modules/MedStat/src/analysis/model_evaluation.py'
s=importlib.util.spec_from_file_location('evaluation_extended',P);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class ExtendedEvaluation(unittest.TestCase):
    def evaluator(self,y,p):return m.ModelEvaluator(y,p,y_probs=p)
    def test_hl_both_cells(self):
        # Four groups each n=2, O=1, E=.2,.6,1.4,1.8.
        o=self.evaluator([0,1]*4,[.1,.1,.3,.3,.7,.7,.9,.9]).calculate_calibration_metrics(4)['hosmer_lemeshow']
        expected=2*(.64/.2+.64/1.8)+2*(.16/.6+.16/1.4)
        self.assertAlmostEqual(o['statistic'],expected)
        self.assertAlmostEqual(o['p_value'],chi2.sf(expected,2))
        self.assertEqual(o['occupied_bins'],4)
    def test_hl_insufficient_groups(self):
        o=self.evaluator([0,1],[.4,.4]).calculate_calibration_metrics(2)['hosmer_lemeshow']
        self.assertIsNone(o['p_value']);self.assertEqual(o['status'],'insufficient_groups')
    def test_hl_zero_expected(self):
        o=self.evaluator([0,1],[0,1]).calculate_calibration_metrics(2)
        self.assertIsNone(o['hosmer_lemeshow']['statistic']);json.dumps(o,allow_nan=False)
    def test_idi_paired_variance(self):
        # Event changes .1,.3, non-event changes -.1,.1: IDI=.2; variance=.01+.01.
        o=self.evaluator([1,1,0,0],[.3,.7,.3,.7]).calculate_idi([.2,.4,.4,.6])
        self.assertAlmostEqual(o['idi'],.2);self.assertAlmostEqual(o['se'],math.sqrt(.02))
    def test_identical_models(self):
        p=[.2,.7,.3,.8];o=self.evaluator([1,1,0,0],p).calculate_idi(p)
        self.assertEqual(o['idi'],0);self.assertEqual(o['se'],0);self.assertIsNone(o['z_score'])
    def test_idi_small_groups(self):
        o=self.evaluator([0,1],[.2,.8]).calculate_idi([.3,.7]);self.assertIsNone(o['se'])
    def test_nri_binary_counts(self):
        o=self.evaluator([1,1,0,0],[.8,.7,.2,.6]).calculate_nri([.2,.8,.8,.7],[.5])['threshold_0.5']
        self.assertEqual(o['nri_total'],1);self.assertEqual(o['event_up'],1);self.assertEqual(o['non_event_down'],1)
    def test_pair_validation(self):
        a=self.evaluator([0,1],[.2,.8])
        for p in [[.2],[float('nan'),.8],[-.1,.2],[[.2],[.8]]]:
            for fn in [a.calculate_idi,a.calculate_nri]:
                with self.assertRaises(ValueError):fn(p)
    def test_single_class(self):
        a=self.evaluator([1,1],[.2,.8])
        for fn in [a.calculate_idi,a.calculate_nri]:
            with self.assertRaises(ValueError):fn([.3,.7])
    def test_dca_arithmetic_and_list(self):
        o=self.evaluator([0,0,1,1],[.1,.8,.6,.2]).decision_curve_analysis([0,.5,.75,1])
        self.assertEqual(o['net_benefit'],[.5,0,-.75,None])
        self.assertEqual(o['net_benefit_all'],[.5,0,-1,None]);json.dumps(o,allow_nan=False)
    def test_invalid_thresholds(self):
        a=self.evaluator([0,1],[.2,.8])
        for t in [[],[-.1],[1.1],[float('nan')],[[.5]]]:
            with self.assertRaises(ValueError):a.decision_curve_analysis(t)
            with self.assertRaises(ValueError):a.calculate_nri([.3,.7],t)
    def test_dca_reject_raw_scores(self):
        with self.assertRaises(ValueError):m.ModelEvaluator([0,1],[-1,2]).decision_curve_analysis()
if __name__=='__main__':unittest.main()
