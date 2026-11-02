"""Contrasta MC finito con la DP usando el presupuesto de Hoeffding predefinido."""

import math
import unittest

import numpy as np

from src.dicer_sim.analysis import classify_product
from src.dicer_sim.domain import Construct, RunConfig, Segment
from src.dicer_sim.exact import expected_summary
from src.dicer_sim.models import ConstantEpsilon, EpsilonCutModel, PiecewiseEpsilon
from src.dicer_sim.simulation import iter_population


N = 50_000
DELTA = math.sqrt(math.log(2 * 128 / 1e-6) / (2 * N))
CONSTRUCT = Construct(84, (Segment("a", "g", 0, 42), Segment("b", "h", 42, 84)))


def check_scenario(test, model, f_left, seed):
    exact = expected_summary(CONSTRUCT, model, f_left)
    results = iter_population(CONSTRUCT, model, RunConfig(N, seed, f_left))
    selected = []
    for result in results:
        test.assertEqual(sum(p.length_nt for p in result.products) + result.remainder.length_nt, 84)
        products = result.products
        annotations = [classify_product(product, CONSTRUCT, result.direction) for product in products]
        selected.append((
            len(products) / 4,
            sum(p.length_nt == 21 for p in products) / 4,
            sum(p.length_nt == 22 for p in products) / 4,
            sum(p.length_nt == 24 for p in products) / 4,
            sum(1 for p in products if p.length_nt == 21 and (p.start % 21 == 0)) / 4,
            result.remainder.length_nt / 84,
            sum(a.contained_segment_id is not None for a in annotations) / 4,
            sum(bool(a.crossed_boundaries) for a in annotations) / 4,
            sum(a.contained_segment_id == "a" for a in annotations) / 4,
            sum(any(a.contained_segment_id == sid for sid in ("a",)) for a in annotations) / 4,
        ))
    observed = [math.fsum(row[i] for row in selected) / N for i in range(6)]
    expected = [
        exact.expected_products / 4,
        exact.expected_length_counts[21] / 4,
        exact.expected_length_counts[22] / 4,
        exact.expected_length_counts[24] / 4,
        exact.expected_metrics.get("aligned21_global_count", 0.0) / 4,
        exact.expected_remainder_nt / 84,
        exact.expected_metrics.get("contained_count", 0.0) / 4,
        exact.expected_metrics.get("crossing_count", 0.0) / 4,
        exact.expected_metrics.get("segment:a:contained_count", 0.0) / 4,
        exact.expected_metrics.get("gene:g:contained_count", 0.0) / 4,
    ]
    for index, (actual, target) in enumerate(zip(observed, expected)):
        with test.subTest(seed=seed, metric=index):
            test.assertLessEqual(abs(actual - target), DELTA)


class FiniteValidationTests(unittest.TestCase):
    def test_finite_constant_matches_exact(self):
        check_scenario(self, EpsilonCutModel(ConstantEpsilon(0.2), 0.4), 1.0, 20261031)

    def test_piecewise_matches_exact(self):
        model = EpsilonCutModel(PiecewiseEpsilon((40, 65), (0.05, 0.25, 0.4)), 0.3)
        check_scenario(self, model, 0.25, 20261032)

    def test_direction_mixture_matches_exact(self):
        model = EpsilonCutModel(ConstantEpsilon(0.35), 0.6)
        check_scenario(self, model, 0.0, 20261033)


if __name__ == "__main__":
    unittest.main()
