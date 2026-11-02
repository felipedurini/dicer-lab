"""Programación dinámica exacta para terminación y conteos por longitud."""

import unittest

from src.dicer_sim.domain import Construct, Segment
from src.dicer_sim.exact import expected_summary
from src.dicer_sim.models import ConstantEpsilon, EpsilonCutModel


def construct(length):
    return Construct(length, (Segment("whole", "gene", 0, length),))


class ExactTests(unittest.TestCase):
    def test_exact_short_and_degenerate_substrates(self):
        short = expected_summary(construct(20), EpsilonCutModel(ConstantEpsilon(0.2)))
        self.assertEqual(short.expected_products, 0.0)
        self.assertEqual(short.terminal_probabilities[20], 1.0)
        self.assertEqual(short.terminal_reason_probabilities["shorter_than_min"], 1.0)

        exact = expected_summary(construct(63), EpsilonCutModel(ConstantEpsilon(0.0)))
        self.assertAlmostEqual(exact.expected_products, 3.0)
        self.assertEqual(dict(exact.length_counts), {21: 3.0, 22: 0.0, 24: 0.0})
        self.assertEqual(exact.terminal_probabilities[0], 1.0)

    def test_exact_length21_hand_enumeration(self):
        result = expected_summary(
            construct(21), EpsilonCutModel(ConstantEpsilon(0.5), p22=0.5)
        )
        self.assertAlmostEqual(result.expected_length_counts[21], 0.5)
        self.assertAlmostEqual(result.expected_products, 0.5)
        self.assertAlmostEqual(result.terminal_probabilities[0], 0.5)
        self.assertAlmostEqual(result.terminal_probabilities[21], 0.5)
        self.assertAlmostEqual(result.expected_remainder_nt, 10.5)

    def test_exact_length42_hand_enumeration(self):
        result = expected_summary(
            construct(42), EpsilonCutModel(ConstantEpsilon(0.5), p22=0.5)
        )
        self.assertAlmostEqual(result.expected_length_counts[21], 0.75)
        self.assertAlmostEqual(result.expected_length_counts[22], 0.25)
        self.assertAlmostEqual(result.expected_length_counts[24], 0.25)
        self.assertAlmostEqual(result.expected_products, 1.25)
        self.assertAlmostEqual(result.terminal_probabilities[0], 0.25)
        self.assertAlmostEqual(result.terminal_probabilities[18], 0.25)
        self.assertAlmostEqual(result.terminal_probabilities[20], 0.25)
        self.assertAlmostEqual(result.terminal_probabilities[21], 0.25)
        self.assertAlmostEqual(result.expected_remainder_nt, 14.75)

    def test_terminal_probabilities_sum_to_one(self):
        for length in (1, 20, 21, 22, 23, 24, 42, 84):
            with self.subTest(length=length):
                result = expected_summary(
                    construct(length), EpsilonCutModel(ConstantEpsilon(0.37), p22=0.23)
                )
                self.assertAlmostEqual(sum(result.terminal_probabilities.values()), 1.0, delta=1e-12)

    def test_expected_mass_conservation(self):
        for length in (21, 22, 42, 64, 84):
            with self.subTest(length=length):
                result = expected_summary(
                    construct(length), EpsilonCutModel(ConstantEpsilon(0.2), p22=0.5)
                )
                emitted_nt = sum(size * count for size, count in result.expected_length_counts.items())
                self.assertAlmostEqual(emitted_nt + result.expected_remainder_nt, length, delta=1e-10)


if __name__ == "__main__":
    unittest.main()
