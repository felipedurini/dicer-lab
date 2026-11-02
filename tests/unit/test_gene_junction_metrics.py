import unittest

from src.dicer_sim.analysis import classify_product, merge_summaries, summarize
from src.dicer_sim.domain import Construct, MoleculeResult, Product, RunConfig, Segment, TerminalRemainder
from src.dicer_sim.exact import expected_summary
from src.dicer_sim.models import ConstantEpsilon, EpsilonCutModel
from src.dicer_sim.simulation import iter_population


class GeneJunctionMetricTests(unittest.TestCase):
    def test_annotation_distinguishes_segment_and_gene_boundaries(self):
        construct = Construct(30, (
            Segment("a1", "gene_a", 0, 10),
            Segment("a2", "gene_a", 10, 20),
            Segment("b", "gene_b", 20, 30),
        ))
        annotation = classify_product(Product(1, 0, 24, 30), construct, "left")
        self.assertEqual(annotation.crossed_boundaries, (10, 20))
        self.assertEqual(annotation.crossed_segment_boundaries, (10, 20))
        self.assertEqual(annotation.crossed_gene_boundaries, (20,))

    def test_same_gene_segment_crossing_is_not_gene_junction_crossing(self):
        construct = Construct(30, (
            Segment("a1", "gene_a", 0, 10),
            Segment("a2", "gene_a", 10, 30),
        ))
        result = MoleculeResult(
            "left", (Product(1, 0, 21, 30),),
            TerminalRemainder(21, 30, "shorter_than_min"),
        )
        summary = summarize((result,), construct)
        self.assertEqual(summary.crossing_count, 1)  # Compatibilidad: cruce de segmento.
        self.assertEqual(summary.gene_crossing_count, 0)
        gene = summary.gene_counts[0]
        self.assertEqual(gene.crossing_touching_count, 1)
        self.assertEqual(gene.gene_crossing_touching_count, 0)
        self.assertEqual(gene.gene_crossing_fraction, 0.0)

    def test_gene_junction_crossing_counts_both_adjacent_genes_once(self):
        construct = Construct(30, (
            Segment("a1", "gene_a", 0, 10),
            Segment("a2", "gene_a", 10, 20),
            Segment("b", "gene_b", 20, 30),
        ))
        result = MoleculeResult(
            "left", (Product(1, 0, 24, 30),),
            TerminalRemainder(24, 30, "shorter_than_min"),
        )
        summary = summarize((result,), construct)
        self.assertEqual(summary.crossing_count, 1)
        self.assertEqual(summary.gene_crossing_count, 1)
        self.assertLessEqual(summary.gene_crossing_count, summary.crossing_count)
        self.assertEqual(summary.gene_crossing_fraction, 1.0)
        by_gene = {item.gene_id: item for item in summary.gene_counts}
        self.assertEqual(by_gene["gene_a"].gene_crossing_touching_count, 1)
        self.assertEqual(by_gene["gene_b"].gene_crossing_touching_count, 1)
        self.assertEqual(summary.direction_summaries[0].gene_crossing_count, 1)
        self.assertEqual(summary.segment_crossing_count, summary.crossing_count)

    def test_directional_merge_and_exact_dp_preserve_both_crossing_metrics(self):
        same_gene = Construct(30, (
            Segment("a1", "gene_a", 0, 10), Segment("a2", "gene_a", 10, 30),
        ))
        distinct_genes = Construct(30, (
            Segment("a", "gene_a", 0, 20), Segment("b", "gene_b", 20, 30),
        ))
        model = EpsilonCutModel(ConstantEpsilon(0.0))
        same_expected = expected_summary(same_gene, model)
        self.assertEqual(same_expected.expected_metrics["crossing_count"], 1.0)
        self.assertEqual(same_expected.expected_metrics.get("gene_crossing_count", 0.0), 0.0)

        left = summarize(iter_population(distinct_genes, model, RunConfig(12, 71, 1.0)), distinct_genes)
        right = summarize(iter_population(distinct_genes, model, RunConfig(12, 72, 0.0)), distinct_genes)
        merged = merge_summaries((left, right))
        exact = expected_summary(distinct_genes, model, 0.5)
        self.assertEqual(merged.crossing_count, 2 * left.crossing_count)
        self.assertEqual(merged.gene_crossing_count, 2 * left.gene_crossing_count)
        self.assertEqual(exact.expected_metrics["crossing_count"], 1.0)
        self.assertEqual(exact.expected_metrics["gene_crossing_count"], 1.0)
        self.assertLessEqual(
            exact.expected_metrics["gene_crossing_count"],
            exact.expected_metrics["crossing_count"],
        )


if __name__ == "__main__":
    unittest.main()
