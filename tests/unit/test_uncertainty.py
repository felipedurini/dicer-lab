import unittest

from src.dicer_sim.experiments import difference_interval, ratio_interval_from_bounded_counts


class UncertaintyTests(unittest.TestCase):
    def test_ratio_interval_from_bounded_counts(self):
        low, high = ratio_interval_from_bounded_counts(0.4, 0.8, 0.1)
        self.assertAlmostEqual(low, 0.3 / 0.9)
        self.assertAlmostEqual(high, 0.5 / 0.7)
        self.assertEqual(ratio_interval_from_bounded_counts(0.1, 0.15, 0.2), (0.0, 1.0))
        self.assertEqual(ratio_interval_from_bounded_counts(0.0, 0.0, 0.0), (0.0, 1.0))

    def test_zero_denominator_delta_is_none(self):
        self.assertIsNone(ratio_interval_from_bounded_counts(0.0, 0.0, 0.0, estimate=True))

    def test_difference_interval_endpoints(self):
        low, high = difference_interval((0.2, 0.4), (0.1, 0.3))
        self.assertAlmostEqual(low, -0.1)
        self.assertAlmostEqual(high, 0.3)


if __name__ == "__main__":
    unittest.main()
