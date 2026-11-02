"""Contención y cruces de fronteras entre tramos contiguos."""

import unittest

from src.dicer_sim.analysis import classify_product, summarize
from src.dicer_sim.domain import Construct, MoleculeResult, Product, Segment, TerminalRemainder


class SegmentMetricTests(unittest.TestCase):
    def test_boundary_touch_is_not_crossing(self):
        construct = Construct(
            42,
            (Segment("left", "a", 0, 21), Segment("right", "b", 21, 42)),
        )
        first = classify_product(Product(1, 0, 21, 42), construct, "left")
        second = classify_product(Product(1, 21, 42, 21), construct, "left")
        self.assertEqual(first.crossed_boundaries, ())
        self.assertEqual(second.crossed_boundaries, ())
        self.assertEqual(first.contained_segment_id, "left")
        self.assertEqual(second.contained_segment_id, "right")

    def test_product_crosses_one_junction_once_and_reports_overlaps(self):
        construct = Construct(
            42,
            (Segment("left", "a", 0, 21), Segment("right", "b", 21, 42)),
        )
        annotation = classify_product(Product(1, 20, 41, 22), construct, "left")
        self.assertIsNone(annotation.contained_segment_id)
        self.assertEqual(annotation.touching_segment_ids, ("left", "right"))
        self.assertEqual(annotation.crossed_boundaries, (21,))
        self.assertEqual(annotation.overlap_nt_by_segment, (("left", 1), ("right", 20)))
        self.assertEqual(sum(overlap for _, overlap in annotation.overlap_nt_by_segment), 21)

    def test_product_crossing_multiple_junctions_is_one_product_annotation(self):
        construct = Construct(
            30,
            (
                Segment("a1", "gene-a", 0, 10),
                Segment("a2", "gene-a", 10, 20),
                Segment("b", "gene-b", 20, 30),
            ),
        )
        annotation = classify_product(Product(1, 0, 24, 30), construct, "left")
        self.assertIsNone(annotation.contained_segment_id)
        self.assertEqual(annotation.crossed_boundaries, (10, 20))
        self.assertEqual(annotation.touching_segment_ids, ("a1", "a2", "b"))
        self.assertEqual(annotation.overlap_nt_by_segment, (("a1", 10), ("a2", 10), ("b", 4)))

    def test_contained_product_can_be_desynchronized(self):
        construct = Construct(63, (Segment("whole", "gene", 0, 63),))
        annotation = classify_product(Product(1, 22, 43, 41), construct, "left")
        self.assertEqual(annotation.contained_segment_id, "whole")
        self.assertFalse(annotation.aligned21_global)

    def test_products_touch_only_segments_with_positive_overlap(self):
        construct = Construct(
            63,
            (
                Segment("a", "gene-a", 0, 21),
                Segment("b", "gene-b", 21, 42),
                Segment("c", "gene-c", 42, 63),
            ),
        )
        annotation = classify_product(Product(1, 0, 21, 63), construct, "left")
        self.assertEqual(annotation.touching_segment_ids, ("a",))
        self.assertEqual(annotation.overlap_nt_by_segment, (("a", 21),))

    def test_per_segment_contained_and_touching_counts(self):
        construct = Construct(
            42,
            (Segment("a", "gene-a", 0, 21), Segment("b", "gene-b", 21, 42)),
        )
        products = (Product(1, 0, 21, 42), Product(2, 21, 42, 21))
        result = MoleculeResult("left", products, TerminalRemainder(42, 42, "exhausted"))
        summary = summarize((result,), construct)
        by_id = {item.segment_id: item for item in summary.segment_counts}
        self.assertEqual(by_id["a"].contained_count, 1)
        self.assertEqual(by_id["a"].touching_count, 1)
        self.assertEqual(by_id["b"].contained_count, 1)
        self.assertEqual(by_id["b"].touching_count, 1)
        self.assertEqual(by_id["a"].overlap_nt, 21)
        self.assertEqual(by_id["b"].overlap_nt, 21)

    def test_overlap_nt_conserves_emitted_length(self):
        construct = Construct(
            66,
            (Segment("a", "gene-a", 0, 33), Segment("b", "gene-b", 33, 66)),
        )
        products = (
            Product(1, 0, 24, 66),
            Product(2, 24, 45, 42),
            Product(3, 45, 66, 21),
        )
        result = MoleculeResult("left", products, TerminalRemainder(66, 66, "exhausted"))
        summary = summarize((result,), construct)
        self.assertEqual(sum(item.overlap_nt for item in summary.segment_counts), 66)

    def test_repeated_gene_deduplicates_touched_products(self):
        construct = Construct(
            30,
            (
                Segment("a1", "gene-a", 0, 10),
                Segment("a2", "gene-a", 10, 20),
                Segment("b", "gene-b", 20, 30),
            ),
        )
        result = MoleculeResult(
            "left",
            (Product(1, 0, 24, 30),),
            TerminalRemainder(24, 30, "shorter_than_min"),
        )
        summary = summarize((result,), construct)
        by_gene = {item.gene_id: item for item in summary.gene_counts}
        self.assertEqual(by_gene["gene-a"].touching_count, 1)
        self.assertEqual(by_gene["gene-a"].crossing_touching_count, 1)
        self.assertEqual(by_gene["gene-a"].overlap_nt, 20)
        self.assertEqual(by_gene["gene-b"].touching_count, 1)

    def test_same_gene_segment_boundary_remains_a_junction(self):
        construct = Construct(
            30,
            (Segment("first", "gene", 0, 10), Segment("second", "gene", 10, 30)),
        )
        result = MoleculeResult(
            "left",
            (Product(1, 0, 24, 30),),
            TerminalRemainder(24, 30, "shorter_than_min"),
        )
        summary = summarize((result,), construct)
        self.assertEqual(summary.crossing_count, 1)
        gene = summary.gene_counts[0]
        self.assertEqual(gene.contained_count, 0)
        self.assertEqual(gene.touching_count, 1)
        self.assertEqual(gene.crossing_touching_count, 1)


if __name__ == "__main__":
    unittest.main()
