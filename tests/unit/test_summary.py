"""Conteos agrupados y denominadores de productos emitidos."""

import unittest

from src.dicer_sim.analysis import summarize
from src.dicer_sim.domain import Construct, MoleculeResult, Product, Segment, TerminalRemainder
from src.dicer_sim.models import ConstantEpsilon, EpsilonCutModel
from src.dicer_sim.simulation import simulate_molecule


class ScriptedRandom:
    def __init__(self, value):
        self.value = value

    def random(self):
        return self.value


def whole_construct(length):
    return Construct(length, (Segment("whole", "gene", 0, length),))


def left_result(length, product_lengths, terminal_reason, proposed=None):
    products = []
    consumed = 0
    for index, product_length in enumerate(product_lengths, start=1):
        remaining = length - consumed
        products.append(Product(index, consumed, consumed + product_length, remaining))
        consumed += product_length
    remainder = TerminalRemainder(
        consumed,
        length,
        reason=terminal_reason,
        proposed_length=proposed,
    )
    return MoleculeResult("left", tuple(products), remainder)


class SummaryTests(unittest.TestCase):
    def test_length_counts_sum_to_product_count(self):
        construct = whole_construct(66)
        result = left_result(66, (24, 21, 21), "exhausted")
        summary = summarize((result,), construct)
        self.assertEqual(summary.length_counts, ((21, 2), (22, 0), (24, 1)))
        self.assertEqual(sum(count for _, count in summary.length_counts), summary.n_products)

    def test_contained_plus_crossing_equals_total(self):
        construct = Construct(
            66,
            (Segment("left", "a", 0, 33), Segment("right", "b", 33, 66)),
        )
        summary = summarize((left_result(66, (24, 21, 21), "exhausted"),), construct)
        self.assertEqual(summary.contained_count, 2)
        self.assertEqual(summary.crossing_count, 1)
        self.assertEqual(summary.contained_count + summary.crossing_count, summary.n_products)

    def test_empty_products_have_none_ratios(self):
        construct = whole_construct(20)
        result = left_result(20, (), "shorter_than_min")
        summary = summarize((result,), construct)
        self.assertEqual(summary.n_products, 0)
        self.assertIsNone(summary.proportion21)
        self.assertEqual(summary.proportion_by_length,
                         ((21, 0, 0, None), (22, 0, 0, None), (24, 0, 0, None)))
        self.assertEqual(summary.n_molecules_without_products, 1)

    def test_failed_proposal_and_remainder_are_excluded_from_products(self):
        construct = whole_construct(21)
        result = simulate_molecule(
            construct,
            EpsilonCutModel(ConstantEpsilon(1.0), p22=0.0),
            "left",
            ScriptedRandom(0.3),
        )
        summary = summarize((result,), construct)
        self.assertEqual(summary.n_products, 0)
        self.assertEqual(summary.length_counts, ((21, 0), (22, 0), (24, 0)))
        self.assertEqual(summary.terminal_reason_counts["proposal_exceeds_remaining"], 1)
        self.assertEqual(summary.terminal_length_counts[21], 1)

    def test_pooled_ratio_differs_from_mean_molecule_ratio(self):
        construct = whole_construct(90)
        four_21 = left_result(90, (21, 21, 21, 21), "shorter_than_min")
        three_24 = left_result(90, (24, 24, 24), "shorter_than_min")
        summary = summarize((four_21, three_24), construct)
        self.assertAlmostEqual(summary.proportion21, 4 / 7)
        mean_of_molecule_ratios = (1.0 + 0.0) / 2
        self.assertNotAlmostEqual(summary.proportion21, mean_of_molecule_ratios)
        self.assertEqual((summary.proportion21_numerator, summary.proportion21_denominator),
                         (4, 7))

    def test_length21_terminal_selection_example(self):
        construct = whole_construct(21)
        model = EpsilonCutModel(ConstantEpsilon(0.5), p22=0.5)
        emitted = simulate_molecule(construct, model, "left", ScriptedRandom(0.1))
        stopped = simulate_molecule(construct, model, "left", ScriptedRandom(0.9))
        summary = summarize((emitted, stopped), construct)
        self.assertEqual(summary.n_products, 1)
        self.assertEqual(summary.proportion21, 1.0)
        self.assertEqual(summary.n_molecules_without_products, 1)

    def test_summary_is_single_pass_and_reports_ordinal_denominators(self):
        construct = whole_construct(64)
        result = left_result(64, (21, 21, 21), "shorter_than_min")

        def only_once():
            yield result

        summary = summarize(only_once(), construct)
        self.assertEqual(summary.n_molecules, 1)
        self.assertEqual([item.n_reached for item in summary.ordinal_counts], [1, 1, 1])


if __name__ == "__main__":
    unittest.main()
