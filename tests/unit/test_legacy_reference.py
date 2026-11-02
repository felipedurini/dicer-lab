"""Caracterización del modelo existente; no recalcula su análisis matemático."""

import unittest

import numpy as np

from src.fase import (
    p_fase_cero,
    rendimiento_dos_extremos,
    rendimiento_un_extremo,
)


class LegacyReferenceTests(unittest.TestCase):
    def test_phase_before_first_cut_is_zero(self):
        for epsilon, p22 in ((0.0, 0.0), (0.2, 0.5), (1.0, 1.0)):
            with self.subTest(epsilon=epsilon, p22=p22):
                self.assertAlmostEqual(p_fase_cero(0, epsilon, p22), 1.0, delta=1e-12)

    def test_zero_epsilon_all_ordinal_products_align(self):
        np.testing.assert_allclose(
            rendimiento_un_extremo(8, 0.0),
            np.ones(8),
            atol=1e-12,
            rtol=0.0,
        )

    def test_mixture_is_weighted_reversed_ordinal_profile(self):
        one_end = rendimiento_un_extremo(9, 0.2, p22=0.35)
        for fraction_left in (0.0, 0.25, 1.0):
            with self.subTest(fraction_left=fraction_left):
                expected = fraction_left * one_end + (1.0 - fraction_left) * one_end[::-1]
                np.testing.assert_allclose(
                    rendimiento_dos_extremos(9, 0.2, p22=0.35, f=fraction_left),
                    expected,
                    atol=1e-12,
                    rtol=0.0,
                )

    def test_first_product_probability_is_one_minus_epsilon(self):
        for epsilon, p22 in ((0.0, 0.0), (0.2, 0.5), (0.7, 1.0), (1.0, 0.25)):
            with self.subTest(epsilon=epsilon, p22=p22):
                observed = rendimiento_un_extremo(3, epsilon, p22=p22)[0]
                self.assertAlmostEqual(observed, 1.0 - epsilon, delta=1e-12)


if __name__ == "__main__":
    unittest.main()
