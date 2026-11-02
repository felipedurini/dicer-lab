"""Muestreo inverso de la distribución con una fuente aleatoria inyectable."""

import unittest

from src.dicer_sim.simulation import sample_cut_length


class FixedKernel:
    def __init__(self, probabilities):
        self.kernel = probabilities
        self.seen_lengths = []

    def probabilities(self, remaining_nt):
        self.seen_lengths.append(remaining_nt)
        return self.kernel


class ScriptedRandom:
    def __init__(self, values):
        self.values = iter(values)
        self.calls = 0

    def random(self):
        self.calls += 1
        return next(self.values)


class SamplingTests(unittest.TestCase):
    def test_inverse_cdf_boundaries(self):
        model = FixedKernel((0.5, 0.25, 0.25))
        rng = ScriptedRandom((0.0, 0.499, 0.5, 0.749, 0.75, 0.999))
        observed = [sample_cut_length(model, 100, rng) for _ in range(6)]
        self.assertEqual(observed, [21, 21, 22, 22, 24, 24])
        self.assertEqual(rng.calls, 6)

    def test_zero_probability_bins_are_never_selected(self):
        cases = (
            ((0.0, 1.0, 0.0), 22),
            ((1.0, 0.0, 0.0), 21),
            ((0.0, 0.0, 1.0), 24),
        )
        for probabilities, expected in cases:
            with self.subTest(probabilities=probabilities):
                rng = ScriptedRandom((0.0, 0.5, 0.999999))
                observed = [sample_cut_length(FixedKernel(probabilities), 100, rng)
                            for _ in range(3)]
                self.assertEqual(observed, [expected] * 3)
                self.assertEqual(rng.calls, 3)

    def test_one_uniform_is_consumed_per_proposal(self):
        rng = ScriptedRandom((0.25,))
        self.assertEqual(sample_cut_length(FixedKernel((0.0, 1.0, 0.0)), 80, rng), 22)
        self.assertEqual(rng.calls, 1)

    def test_invalid_kernel_is_rejected_before_rng_draw(self):
        rng = ScriptedRandom((0.2,))
        with self.assertRaises(ValueError):
            sample_cut_length(FixedKernel((0.6, 0.2, 0.1)), 80, rng)
        self.assertEqual(rng.calls, 0)

    def test_invalid_uniform_is_rejected(self):
        for value in (-0.1, 1.0, float("nan"), float("inf")):
            with self.subTest(value=value):
                rng = ScriptedRandom((value,))
                with self.assertRaises((TypeError, ValueError)):
                    sample_cut_length(FixedKernel((0.5, 0.25, 0.25)), 80, rng)
                self.assertEqual(rng.calls, 1)


if __name__ == "__main__":
    unittest.main()
