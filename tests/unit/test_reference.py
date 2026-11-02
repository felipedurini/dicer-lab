"""Adaptación semántica a las probabilidades Fourier existentes."""

import unittest
from unittest.mock import patch

from src.dicer_sim.models import ConstantEpsilon, PiecewiseEpsilon
from src.dicer_sim.reference import stationary_prefix_reference
from src.fase import p_fase_cero, rendimiento_un_extremo


class ReferenceTests(unittest.TestCase):
    def test_reference_delegates_to_existing_functions(self):
        with (
            patch("src.dicer_sim.reference.p_fase_cero", wraps=p_fase_cero) as phase,
            patch("src.dicer_sim.reference.rendimiento_un_extremo",
                  wraps=rendimiento_un_extremo) as yield_by_index,
        ):
            result = stationary_prefix_reference(3, 0.2, p22=0.35, length_nt=72)
        self.assertEqual(phase.call_count, 3)
        self.assertEqual(yield_by_index.call_count, 1)
        self.assertEqual(result["phase_zero_after"], tuple(p_fase_cero(k, 0.2, 0.35)
                                                         for k in (1, 2, 3)))
        self.assertEqual(result["aligned21_relative"], tuple(
            rendimiento_un_extremo(3, 0.2, 0.35)
        ))

    def test_prefix_requires_length_at_least_24k(self):
        with self.assertRaises(ValueError):
            stationary_prefix_reference(2, 0.1, length_nt=47)
        result = stationary_prefix_reference(2, 0.1, length_nt=48)
        self.assertEqual(result["guaranteed_length_nt"], 48)
        with self.assertRaises(ValueError):
            stationary_prefix_reference(0, 0.1, length_nt=48)
        with self.assertRaises(TypeError):
            stationary_prefix_reference(True, 0.1, length_nt=48)

    def test_reference_requires_constant_epsilon(self):
        with self.assertRaises(TypeError):
            stationary_prefix_reference(1, PiecewiseEpsilon((), (0.1,)), length_nt=24)
        with self.assertRaises(TypeError):
            stationary_prefix_reference(1, ConstantEpsilon(0.1), length_nt=24)

    def test_prefix_denominator_is_every_molecule(self):
        reference = stationary_prefix_reference(4, 0.2, length_nt=96)
        self.assertEqual(reference["denominator"], "all_molecules")
        self.assertEqual(reference["n_guaranteed_cuts"], 4)

    def test_right_prefix_uses_phase_relative_to_initiating_end(self):
        result = stationary_prefix_reference(2, 0.1, p22=0.4, length_nt=48)
        self.assertEqual(result["phase_origin"], "initiating_end")
        self.assertEqual(len(result["phase_zero_after"]), 2)
        self.assertEqual(len(result["aligned21_relative"]), 2)


if __name__ == "__main__":
    unittest.main()
