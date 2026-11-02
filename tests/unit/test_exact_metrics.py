import unittest

from src.dicer_sim.domain import Construct, Segment
from src.dicer_sim.exact import expected_summary
from src.dicer_sim.models import ConstantEpsilon, EpsilonCutModel


class ExactMetricTests(unittest.TestCase):
    def test_exact_containment_phase_and_physical_units(self):
        construct = Construct(21, (Segment("s", "g", 0, 21),))
        result = expected_summary(construct, EpsilonCutModel(ConstantEpsilon(0.0)))
        metrics = result.expected_metrics
        self.assertEqual(result.expected_products, 1.0)
        self.assertEqual(metrics["contained_count"], 1.0)
        self.assertEqual(metrics["aligned21_local_count"], 1.0)
        self.assertEqual(metrics["segment:s:overlap_nt"], 21.0)
        self.assertEqual(metrics["gene:g:contained_count"], 1.0)
        self.assertEqual(metrics["physical:0:21:recovered_count"], 1.0)

    def test_exact_right_geometry_and_weighted_mixture(self):
        construct = Construct(42, (Segment("s1", "g", 0, 21), Segment("s2", "g", 21, 42)))
        model = EpsilonCutModel(ConstantEpsilon(0.0))
        left = expected_summary(construct, model, 1.0)
        right = expected_summary(construct, model, 0.0)
        mixed = expected_summary(construct, model, 0.25)
        self.assertEqual(left.expected_metrics["segment:s1:contained_count"], 1.0)
        self.assertEqual(right.expected_metrics["segment:s2:contained_count"], 1.0)
        self.assertAlmostEqual(
            mixed.expected_metrics["segment:s1:contained_count"],
            0.25 * left.expected_metrics["segment:s1:contained_count"]
            + 0.75 * right.expected_metrics.get("segment:s1:contained_count", 0.0),
        )
        self.assertEqual(mixed.expected_metrics["gene:g:touching_count"], 2.0)

    def test_repeated_gene_metrics_sum_over_segments(self):
        construct = Construct(42, (Segment("a", "g", 0, 21), Segment("b", "g", 21, 42)))
        result = expected_summary(construct, EpsilonCutModel(ConstantEpsilon(0.0)))
        self.assertEqual(result.expected_metrics["gene:g:overlap_nt"], 42.0)
        self.assertEqual(result.expected_metrics["gene:g:contained_count"], 2.0)

    def test_nan_mixture_is_rejected(self):
        construct = Construct(21, (Segment("s", "g", 0, 21),))
        with self.assertRaises(ValueError):
            expected_summary(construct, EpsilonCutModel(ConstantEpsilon(0.0)), float("nan"))


if __name__ == "__main__":
    unittest.main()
