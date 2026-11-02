from __future__ import annotations

import unittest
from unittest.mock import patch

from services.simulator_api.design.pipeline import _candidate_metrics
from services.simulator_api.design.schemas import DesignRequest
from services.simulator_api.design.ranking import pareto_rank


class CandidateMetricTests(unittest.TestCase):
    def test_gene_coverage_uses_only_that_genes_selected_block(self):
        request = DesignRequest.model_validate({
            "design_schema_version": 1, "label": "metric fixture",
            "targets": [
                {"gene_id": "g0", "sequence_rna": "A" * 21},
                {"gene_id": "g1", "sequence_rna": "G" * 21},
            ],
            "blocks": [{"gene_id": "g0", "length_nt": 21}, {"gene_id": "g1", "length_nt": 21}],
            "reference_ids": [], "seed": 1, "lambda": 1,
            "thermo_profile": "lucid_end3_v1", "iterations": 1,
        })
        a21, g21 = "A" * 21, "G" * 21
        blocks = [
            {"gene_id": "g0", "start": 0, "end": 21, "sequence_rna": a21},
            {"gene_id": "g1", "start": 21, "end": 42, "sequence_rna": g21},
        ]
        profile = {
            "profile_id": "fixture", "duplex_dg": -1.0,
            "sense_end_dg": -0.2, "antisense_end_dg": -0.1, "delta": 0.1,
        }
        # g0 also has a matching k-mer in g1's block. The old whole-candidate
        # numerator counted both matches over a one-window denominator (2.0).
        with patch("services.simulator_api.design.pipeline.energy_profile", return_value=profile), \
             patch("services.simulator_api.design.pipeline.window_weight", return_value=1):
            candidate, _ = _candidate_metrics(
                "fixture", a21 + g21, blocks, request, {},
                {"g0": {a21, g21}, "g1": {g21}},
                {"g0": 21, "g1": 21},
            )

        self.assertEqual(candidate["metrics"]["coverage_by_gene"], {"g0": 1.0, "g1": 1.0})
        self.assertLessEqual(candidate["metrics"]["minimum_gene_coverage"], 1.0)


class ParetoMetricTests(unittest.TestCase):
    def test_ranking_uses_corrected_coverage_then_stable_tie_break(self):
        candidates = [
            {"candidate_id": "b", "metrics": {"minimum_gene_coverage": .8,
             "high_stability_window_fraction": .5, "dimer_gap_per_nt": .2}},
            {"candidate_id": "a", "metrics": {"minimum_gene_coverage": 1.0,
             "high_stability_window_fraction": .5, "dimer_gap_per_nt": .2}},
            {"candidate_id": "c", "metrics": {"minimum_gene_coverage": 1.0,
             "high_stability_window_fraction": .5, "dimer_gap_per_nt": .2}},
        ]
        ranked = pareto_rank(candidates)
        self.assertEqual([row["candidate_id"] for row in ranked], ["a", "c", "b"])
        self.assertEqual([row["pareto_front"] for row in ranked], [0, 0, 1])


if __name__ == "__main__":
    unittest.main()
