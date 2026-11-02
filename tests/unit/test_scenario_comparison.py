import unittest

from src.dicer_sim.domain import Construct, RunConfig, Segment
from src.dicer_sim.experiments import compare_scenarios, run_scenario
from src.dicer_sim.models import ConstantEpsilon, EpsilonCutModel


def setup_pair(length=42, epsilon=0.0, p22=0.5, f_left=1.0):
    construct = Construct(length, (Segment("s", "g", 0, length),))
    baseline = run_scenario(construct, EpsilonCutModel(ConstantEpsilon(epsilon), p22),
                            RunConfig(20, 101, f_left))
    candidate = run_scenario(construct, EpsilonCutModel(ConstantEpsilon(epsilon), p22),
                             RunConfig(20, 202, f_left))
    return baseline, candidate


class ScenarioComparisonTests(unittest.TestCase):
    def test_comparison_rejects_incompatible_constructs(self):
        baseline, candidate = setup_pair()
        other = run_scenario(Construct(43, (Segment("s", "g", 0, 43),)),
                             EpsilonCutModel(ConstantEpsilon(0.0)), RunConfig(20, 303))
        with self.assertRaises(ValueError):
            compare_scenarios(baseline, other)

    def test_comparison_requires_same_p22_and_direction_mixture(self):
        baseline, _ = setup_pair()
        construct = baseline.construct
        wrong_model = run_scenario(construct, EpsilonCutModel(ConstantEpsilon(0.0), 0.4), RunConfig(20, 202))
        with self.assertRaises(ValueError):
            compare_scenarios(baseline, wrong_model)
        wrong_direction = run_scenario(construct, EpsilonCutModel(ConstantEpsilon(0.0)), RunConfig(20, 202, 0.5))
        with self.assertRaises(ValueError):
            compare_scenarios(baseline, wrong_direction)

    def test_delta_is_candidate_minus_baseline_and_degenerate_is_exact(self):
        baseline, candidate = setup_pair()
        comparison = compare_scenarios(baseline, candidate)
        self.assertEqual(comparison["proportion21"]["delta"], 0.0)
        self.assertEqual(comparison["proportion21"]["delta_interval"], (0.0, 0.0))

    def test_zero_denominator_delta_is_none(self):
        baseline, candidate = setup_pair(length=20)
        self.assertIsNone(compare_scenarios(baseline, candidate)["proportion21"]["delta"])


if __name__ == "__main__":
    unittest.main()
