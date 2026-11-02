"""Contratos del constructo y de sus tramos de coordenadas."""

import unittest

from src.dicer_sim.domain import (
    Construct,
    MoleculeResult,
    Product,
    Segment,
    TerminalRemainder,
)


class DomainTests(unittest.TestCase):
    def test_segments_partition_construct(self):
        segments = (
            Segment("a", "gene-a", 0, 21),
            Segment("b", "gene-b", 21, 43),
        )
        construct = Construct(43, segments)
        self.assertEqual(construct.length_nt, 43)
        self.assertEqual(construct.segments, segments)
        self.assertEqual(construct.phase_origin_nt, 0)

    def test_repeated_gene_ids_are_allowed(self):
        construct = Construct(
            42,
            (Segment("copy-a", "gene", 0, 21), Segment("copy-b", "gene", 21, 42)),
        )
        self.assertEqual([part.gene_id for part in construct.segments], ["gene", "gene"])

    def test_duplicate_segment_ids_are_rejected(self):
        with self.assertRaises(ValueError):
            Construct(42, (Segment("same", "a", 0, 21), Segment("same", "b", 21, 42)))

    def test_gap_overlap_or_empty_segment_is_rejected(self):
        invalid_partitions = (
            (Segment("a", "a", 0, 20), Segment("b", "b", 21, 42)),
            (Segment("a", "a", 0, 22), Segment("b", "b", 21, 42)),
            (Segment("a", "a", 1, 21), Segment("b", "b", 21, 42)),
        )
        for segments in invalid_partitions:
            with self.subTest(segments=segments):
                with self.assertRaises(ValueError):
                    Construct(42, segments)
        with self.assertRaises(ValueError):
            Segment("empty", "gene", 21, 21)

    def test_invalid_construct_lengths_are_rejected(self):
        valid = (Segment("whole", "gene", 0, 21),)
        for length in (0, -1):
            with self.subTest(length=length), self.assertRaises(ValueError):
                Construct(length, valid)
        for length in (True, 21.0, "21"):
            with self.subTest(length=length), self.assertRaises(TypeError):
                Construct(length, valid)

    def test_coordinates_are_half_open(self):
        segment = Segment("whole", "gene", 0, 21)
        self.assertEqual(segment.start, 0)
        self.assertEqual(segment.end, 21)
        self.assertEqual(segment.end - segment.start, 21)

    def test_invalid_segment_fields_are_rejected(self):
        for segment_id, gene_id in (("", "gene"), ("id", ""), (1, "gene"), ("id", None)):
            with self.subTest(segment_id=segment_id, gene_id=gene_id), self.assertRaises(
                (TypeError, ValueError)
            ):
                Segment(segment_id, gene_id, 0, 21)
        for start, end in ((-1, 1), (2, 1), (0, 0), (False, 1), (0, 1.5)):
            with self.subTest(start=start, end=end), self.assertRaises((TypeError, ValueError)):
                Segment("id", "gene", start, end)

    def test_invalid_phase_origin_is_rejected(self):
        segment = (Segment("whole", "gene", 0, 21),)
        for origin in (-1, 21):
            with self.subTest(origin=origin), self.assertRaises(ValueError):
                Construct(21, segment, phase_origin_nt=origin)
        for origin in (True, 1.0):
            with self.subTest(origin=origin), self.assertRaises(TypeError):
                Construct(21, segment, phase_origin_nt=origin)

    def test_records_are_frozen(self):
        segment = Segment("whole", "gene", 0, 21)
        construct = Construct(21, (segment,))
        with self.assertRaises(AttributeError):
            segment.start = 1
        with self.assertRaises(AttributeError):
            construct.length_nt = 42

    def test_product_length_is_coordinate_difference(self):
        product = Product(cut_index=1, start=0, end=22, remaining_before=22)
        self.assertEqual(product.length_nt, 22)

    def test_cut_indices_start_at_one(self):
        with self.assertRaises(ValueError):
            Product(cut_index=0, start=0, end=21, remaining_before=21)
        with self.assertRaises(TypeError):
            Product(cut_index=True, start=0, end=21, remaining_before=21)

    def test_empty_remainder_is_representable(self):
        remainder = TerminalRemainder(21, 21, reason="exhausted")
        result = MoleculeResult("left", (), remainder)
        self.assertEqual(result.remainder.length_nt, 0)
        self.assertEqual(result.products, ())

    def test_overshoot_records_proposed_length(self):
        remainder = TerminalRemainder(
            0, 22, reason="proposal_exceeds_remaining", proposed_length=24
        )
        self.assertEqual(remainder.length_nt, 22)
        self.assertEqual(remainder.proposed_length, 24)
        self.assertFalse(hasattr(remainder, "cut_index"))

    def test_result_preserves_cut_order(self):
        products = (
            Product(cut_index=1, start=22, end=43, remaining_before=43),
            Product(cut_index=2, start=1, end=22, remaining_before=22),
        )
        result = MoleculeResult(
            "right",
            products,
            TerminalRemainder(0, 1, reason="shorter_than_min"),
        )
        self.assertEqual(result.products, products)
        self.assertEqual([product.cut_index for product in result.products], [1, 2])

    def test_product_and_remainder_reject_inconsistent_values(self):
        for start, end in ((0, 0), (-1, 20), (0, 23)):
            with self.subTest(start=start, end=end), self.assertRaises((TypeError, ValueError)):
                Product(1, start, end, max(21, end - start))
        with self.assertRaises(ValueError):
            Product(1, 0, 21, remaining_before=20)
        with self.assertRaises(ValueError):
            TerminalRemainder(0, 21, reason="exhausted")
        with self.assertRaises(ValueError):
            TerminalRemainder(
                0, 22, reason="proposal_exceeds_remaining", proposed_length=22
            )

    def test_result_requires_a_valid_direction_and_immutable_products(self):
        remainder = TerminalRemainder(0, 0, reason="exhausted")
        with self.assertRaises(ValueError):
            MoleculeResult("both", (), remainder)
        with self.assertRaises(TypeError):
            MoleculeResult("left", [], remainder)


if __name__ == "__main__":
    unittest.main()
