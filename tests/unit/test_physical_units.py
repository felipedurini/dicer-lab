"""Recuperación geométrica de celdas completas de la retícula de 21 nt."""

import unittest

from src.dicer_sim.analysis import summarize
from src.dicer_sim.domain import Construct, MoleculeResult, Product, Segment, TerminalRemainder


class PhysicalUnitTests(unittest.TestCase):
    def test_physical_unit_recovery_uses_exact_interval(self):
        construct = Construct(63, (Segment("whole", "gene", 0, 63),))
        products = (
            Product(1, 0, 21, 63),
            Product(2, 21, 42, 42),
            Product(3, 42, 63, 21),
        )
        result = MoleculeResult("left", products, TerminalRemainder(63, 63, "exhausted"))
        summary = summarize((result,), construct)
        self.assertEqual([(unit.start, unit.end) for unit in summary.physical_unit_counts],
                         [(0, 21), (21, 42), (42, 63)])
        self.assertEqual([unit.recovered_molecule_count for unit in summary.physical_unit_counts],
                         [1, 1, 1])
        self.assertTrue(all(unit.n_molecules == 1 for unit in summary.physical_unit_counts))

    def test_unrepresented_partial_grid_unit_is_not_recovered(self):
        construct = Construct(43, (Segment("whole", "gene", 0, 43),))
        result = MoleculeResult(
            "left",
            (Product(1, 0, 21, 43), Product(2, 21, 42, 22)),
            TerminalRemainder(42, 43, "shorter_than_min"),
        )
        summary = summarize((result,), construct)
        self.assertEqual([(unit.start, unit.end) for unit in summary.physical_unit_counts],
                         [(0, 21), (21, 42)])
        self.assertEqual(len(summary.physical_unit_counts), 2)

    def test_origin_offset_defines_full_global_cells(self):
        construct = Construct(
            64, (Segment("whole", "gene", 0, 64),), phase_origin_nt=1
        )
        products = (
            Product(1, 43, 64, 64),
            Product(2, 22, 43, 43),
            Product(3, 1, 22, 22),
        )
        result = MoleculeResult("right", products, TerminalRemainder(0, 1, "shorter_than_min"))
        summary = summarize((result,), construct)
        self.assertEqual([(unit.start, unit.end) for unit in summary.physical_unit_counts],
                         [(1, 22), (22, 43), (43, 64)])
        self.assertEqual([unit.recovered_molecule_count for unit in summary.physical_unit_counts],
                         [1, 1, 1])


if __name__ == "__main__":
    unittest.main()
