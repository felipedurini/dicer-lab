"""Métricas de fase local y alineación con la retícula global."""

import unittest

from src.dicer_sim.analysis import classify_product
from src.dicer_sim.domain import Construct, Product, Segment


def construct(length=63, phase_origin_nt=0):
    return Construct(
        length,
        (Segment("whole", "target", 0, length),),
        phase_origin_nt=phase_origin_nt,
    )


class PhaseMetricTests(unittest.TestCase):
    def test_relative_phase_uses_actual_consumed_length(self):
        product = Product(cut_index=2, start=24, end=45, remaining_before=46)
        annotation = classify_product(product, construct(70), direction="left")
        self.assertEqual(annotation.relative_phase_before, 24 % 21)
        self.assertEqual(annotation.relative_phase_after, (24 + 21) % 21)

    def test_right_local_phase_and_global_phase_differ_for_nonmultiple_length(self):
        product = Product(cut_index=1, start=43, end=64, remaining_before=64)
        annotation = classify_product(product, construct(64), direction="right")
        self.assertEqual(annotation.relative_phase_before, 0)
        self.assertEqual(annotation.global_phase_before, 64 % 21)
        self.assertTrue(annotation.aligned21_local)
        self.assertFalse(annotation.aligned21_global)

    def test_length21_does_not_imply_global_alignment(self):
        product = Product(cut_index=1, start=22, end=43, remaining_before=41)
        annotation = classify_product(product, construct(63), direction="left")
        self.assertEqual(product.length_nt, 21)
        self.assertEqual(annotation.global_phase_before, 1)
        self.assertFalse(annotation.aligned21_local)
        self.assertFalse(annotation.aligned21_global)

    def test_nonzero_phase_origin_changes_global_alignment_only(self):
        product = Product(cut_index=1, start=1, end=22, remaining_before=62)
        annotation = classify_product(
            product, construct(63, phase_origin_nt=1), direction="left"
        )
        self.assertEqual(annotation.relative_phase_before, 1)
        self.assertEqual(annotation.global_phase_before, 0)
        self.assertFalse(annotation.aligned21_local)
        self.assertTrue(annotation.aligned21_global)

    def test_product_coordinates_must_match_construct_and_direction(self):
        with self.assertRaises(ValueError):
            classify_product(Product(1, 1, 22, 63), construct(63), direction="left")
        with self.assertRaises(ValueError):
            classify_product(Product(1, 0, 21, 63), construct(63), direction="right")
        with self.assertRaises(ValueError):
            classify_product(Product(1, 42, 63, 63), construct(63), direction="left")


if __name__ == "__main__":
    unittest.main()
