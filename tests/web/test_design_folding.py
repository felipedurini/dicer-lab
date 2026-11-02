from __future__ import annotations
import math
import unittest
from services.simulator_api.design.folding import fold_candidate, FoldingError
from services.simulator_api.design.ranking import pareto_rank

class FoldingTests(unittest.TestCase):
    def test_real_vienna_monomers_and_dimer(self):
        seq = "AUGCUAGCUAGCUAGCUAGCU"
        result = fold_candidate(seq)
        self.assertEqual(result["profile"]["viennarna_version"], "2.7.2")
        self.assertEqual(len(result["monomers"]["sense"]["paired_probability_by_position"]), len(seq))
        self.assertAlmostEqual(result["dimer"]["perfect_duplex_kcal_mol"], result["dimer"]["mfe_kcal_mol"], places=4)
        self.assertGreaterEqual(result["dimer"]["gap_per_nt"], 0)
        expected_gap = (result["dimer"]["perfect_duplex_kcal_mol"] -
                        result["dimer"]["mfe_kcal_mol"])
        self.assertAlmostEqual(result["dimer"]["gap_kcal_mol"], expected_gap, places=10)
        self.assertTrue(result["dimer"]["perfect_duplex_is_mfe"])
        self.assertAlmostEqual(result["dimer"]["gap_per_nt"], expected_gap / len(seq), places=10)
        self.assertIn("&", result["dimer"]["sequence_order"])

    def test_rejects_ambiguous_input(self):
        with self.assertRaises(FoldingError):
            fold_candidate("A" * 20 + "N")

    def test_pareto_fronts_and_nonfinite_values(self):
        rows = [
            {"candidate_id":"a", "metrics":{"minimum_gene_coverage":1.,"high_stability_window_fraction":.5,"dimer_gap_per_nt":.2}},
            {"candidate_id":"b", "metrics":{"minimum_gene_coverage":.8,"high_stability_window_fraction":.4,"dimer_gap_per_nt":.3}},
            {"candidate_id":"c", "metrics":{"minimum_gene_coverage":.9,"high_stability_window_fraction":.6,"dimer_gap_per_nt":.1}},
        ]
        ranked=pareto_rank(rows)
        self.assertEqual([x["pareto_front"] for x in ranked],[0,0,1])
        rows[0]["metrics"]["dimer_gap_per_nt"] = math.nan
        with self.assertRaises(ValueError):
            pareto_rank(rows)

if __name__ == "__main__": unittest.main()
