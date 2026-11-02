"""Verifica estadística de un núcleo de propuestas fijo."""

import math
import unittest

import numpy as np

from src.dicer_sim.simulation import sample_cut_length


N_SAMPLES = 50_000
M_BUDGET = 128
ALPHA = 1e-6
DELTA = math.sqrt(math.log(2 * M_BUDGET / ALPHA) / (2 * N_SAMPLES))


class FixedKernel:
    def probabilities(self, remaining_nt):
        return (0.7, 0.12, 0.18)


class SamplingStatisticalTests(unittest.TestCase):
    def test_fixed_length_sampling_matches_kernel_probabilities(self):
        rng = np.random.Generator(np.random.PCG64(20261029))
        counts = {21: 0, 22: 0, 24: 0}
        model = FixedKernel()
        for _ in range(N_SAMPLES):
            counts[sample_cut_length(model, 100, rng)] += 1
        for length, expected in ((21, 0.7), (22, 0.12), (24, 0.18)):
            with self.subTest(length=length):
                observed = counts[length] / N_SAMPLES
                self.assertLessEqual(abs(observed - expected), DELTA)


if __name__ == "__main__":
    unittest.main()
