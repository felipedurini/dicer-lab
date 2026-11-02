import unittest

from services.simulator_api.metrics import metric_rows
from src.dicer_sim.analysis import summarize
from src.dicer_sim.domain import Construct, MoleculeResult, Product, Segment, TerminalRemainder
from src.dicer_sim.exact import expected_summary
from src.dicer_sim.models import ConstantEpsilon, EpsilonCutModel


class MetricProjectionTests(unittest.TestCase):
    def construct(self, genes):
        ends = (10, 30) if len(genes) == 2 else (10, 20, 30)
        starts = (0,) + ends[:-1]
        return Construct(
            30,
            tuple(
                Segment(f"s{i}", gene, start, end)
                for i, (gene, start, end) in enumerate(zip(genes, starts, ends))
            ),
        )

    def result(self):
        return MoleculeResult(
            "left",
            (Product(1, 0, 21, 30),),
            TerminalRemainder(21, 30, "shorter_than_min"),
        )

    def indexed(self, rows):
        return {(row["key"], row["scope_id"], row["source_kind"]): row for row in rows}

    def test_same_gene_segment_crossing_is_interior_of_gene_only(self):
        construct = self.construct(("gene_a", "gene_a"))
        summary = summarize((self.result(),), construct)
        rows = self.indexed(metric_rows(summary))
        self.assertEqual(rows[("segment_crossing", None, "monte_carlo")]["value"], 1.0)
        self.assertEqual(rows[("gene_crossing", None, "monte_carlo")]["value"], 0.0)
        self.assertEqual(rows[("gene_interior", "gene_a", "monte_carlo")]["numerator"], 1)
        self.assertEqual(rows[("gene_interior", "gene_a", "monte_carlo")]["denominator"], 1)
        self.assertEqual(rows[("gene_interior", "gene_a", "monte_carlo")]["value"], 1.0)
        self.assertEqual(rows[("gene_segment_interior", "gene_a", "monte_carlo")]["value"], 0.0)

    def test_a_b_a_crossing_is_not_gene_interior_and_counts_each_gene_once(self):
        construct = self.construct(("gene_a", "gene_b", "gene_a"))
        summary = summarize((self.result(),), construct)
        exact = expected_summary(construct, EpsilonCutModel(ConstantEpsilon(0.0)))
        rows = self.indexed(metric_rows(summary, exact=exact, construct=construct))
        self.assertEqual(rows[("gene_crossing", None, "monte_carlo")]["numerator"], 1)
        self.assertEqual(rows[("gene_interior", "gene_a", "monte_carlo")]["value"], 0.0)
        self.assertEqual(rows[("gene_interior", "gene_b", "monte_carlo")]["value"], 0.0)
        self.assertEqual(rows[("gene_crossing_touching", "gene_a", "monte_carlo")]["numerator"], 1)
        self.assertEqual(rows[("gene_crossing_touching", "gene_b", "monte_carlo")]["numerator"], 1)
        self.assertEqual(rows[("gene_interior", "gene_a", "exact_expectation")]["value"], 0.0)

    def test_zero_denominators_are_null_and_exact_rows_are_expectations(self):
        no_product_construct = Construct(20, (Segment("s", "g", 0, 20),))
        summary = summarize(
            (MoleculeResult("left", (), TerminalRemainder(0, 20, "shorter_than_min")),),
            no_product_construct,
        )
        rows = self.indexed(metric_rows(summary))
        self.assertIsNone(rows[("length_21", None, "monte_carlo")]["value"])
        self.assertEqual(rows[("length_21", None, "monte_carlo")]["denominator"], 0)
        exact = expected_summary(
            no_product_construct,
            EpsilonCutModel(ConstantEpsilon(0.0)),
        )
        exact_rows = self.indexed(metric_rows(summary, exact=exact, construct=no_product_construct))
        exact_gene = exact_rows[("gene_interior", "g", "exact_expectation")]
        self.assertEqual(exact_gene["source_kind"], "exact_expectation")
        self.assertEqual(exact_gene["basis"], "pooled_products")
        self.assertIsNone(exact_gene["value"])


if __name__ == "__main__":
    unittest.main()
