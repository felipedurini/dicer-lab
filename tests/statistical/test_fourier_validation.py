"""Contraste Monte Carlo–Fourier en un prefijo completo y sin censura."""

import math
import unittest

import numpy as np

from src.dicer_sim.domain import Construct, Segment
from src.dicer_sim.models import ConstantEpsilon, EpsilonCutModel
from src.dicer_sim.simulation import simulate_molecule
from src.fase import p_fase_cero, rendimiento_un_extremo


N_MOLECULES = 50_000
K = 8
LENGTH_NT = 24 * K
M_BUDGET = 128
ALPHA = 1e-6
DELTA = math.sqrt(math.log(2 * M_BUDGET / ALPHA) / (2 * N_MOLECULES))


class FourierStatisticalTests(unittest.TestCase):
    def test_constant_prefix_matches_fourier(self):
        construct = Construct(LENGTH_NT, (Segment("whole", "target", 0, LENGTH_NT),))
        for scenario, epsilon in enumerate((0.1, 0.2)):
            with self.subTest(epsilon=epsilon):
                rng = np.random.Generator(np.random.PCG64(20261028 + scenario))
                model = EpsilonCutModel(ConstantEpsilon(epsilon), p22=0.5)
                phase_hits = np.zeros(K, dtype=np.int64)
                aligned_hits = np.zeros(K, dtype=np.int64)

                for _ in range(N_MOLECULES):
                    result = simulate_molecule(construct, model, "left", rng)
                    self.assertGreaterEqual(len(result.products), K)
                    for index, product in enumerate(result.products[:K]):
                        consumed_before = LENGTH_NT - product.remaining_before
                        phase_hits[index] += (consumed_before + product.length_nt) % 21 == 0
                        aligned_hits[index] += (
                            consumed_before % 21 == 0 and product.length_nt == 21
                        )

                observed_phase = phase_hits / N_MOLECULES
                observed_aligned = aligned_hits / N_MOLECULES
                expected_phase = np.array(
                    [p_fase_cero(k, epsilon, 0.5) for k in range(1, K + 1)]
                )
                expected_aligned = rendimiento_un_extremo(K, epsilon, 0.5)
                np.testing.assert_array_less(
                    np.abs(observed_phase - expected_phase), DELTA
                )
                np.testing.assert_array_less(
                    np.abs(observed_aligned - expected_aligned), DELTA
                )


if __name__ == "__main__":
    unittest.main()
