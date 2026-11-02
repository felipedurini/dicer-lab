from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from services.simulator_api.design.thermo import _duplex_delta_g, energy_profile, window_weight


ROOT = Path(__file__).resolve().parents[2]
GO = os.environ.get("DICER_GO") or shutil.which("go")


@unittest.skipUnless(GO, "Go toolchain required for the real dsRNAmax CLI integration")
class DsRNAMaxThermodynamicPrototypeTests(unittest.TestCase):
    def test_three_base_duplex_energy_matches_explicit_nearest_neighbor_sum(self):
        # AUG pairs AT/TG (nearest-neighbor terms AT/TA and CA/GT), with one
        # A/T terminal initiation and the documented 70 mM salt correction.
        self.assertAlmostEqual(_duplex_delta_g("AUG"), 1.1883976215, places=8)

    def test_real_go_discovery_and_lucid_compatible_energy_change_selected_block(self):
        """A real Go discovery result enters the Python energy-weighted selection."""
        with tempfile.TemporaryDirectory(prefix="dicer-design-e1-") as tmp:
            directory = Path(tmp)
            binary = directory / ("dsrnamax.exe" if os.name == "nt" else "dsrnamax")
            subprocess.run(
                [GO, "build", "-o", str(binary), "."],
                cwd=ROOT / "vendor" / "dsrnamax",
                check=True,
                capture_output=True,
                text=True,
                timeout=90,
            )
            fasta = ROOT / "tests" / "fixtures" / "design" / "e1_targets.fasta"
            proc = subprocess.run(
                [str(binary), "discover", "--targets", str(fasta), "--k", "21"],
                check=True,
                capture_output=True,
                text=True,
                timeout=10,
            )
            discovered = json.loads(proc.stdout)
            self.assertEqual(discovered["schema_version"], 1)
            records = discovered["kmers"]
            self.assertGreaterEqual(len(records), 2)
            self.assertEqual([record["occurrences_count"] for record in records], [1, 1])

            # Favor the weaker-terminal candidate so the LUCID delta genuinely
            # changes the decision; lambda=0 is the coverage-only control.
            profiles = {record["sequence_rna"]: energy_profile(record["sequence_rna"]) for record in records}
            weakest = min(profiles, key=lambda sequence: profiles[sequence]["delta"])
            strongest = max(profiles, key=lambda sequence: profiles[sequence]["delta"])
            weights = {sequence: window_weight(profile["delta"], lambda_value=1) for sequence, profile in profiles.items()}
            kmer_file = directory / "kmers.json"
            request_file = directory / "assemble.json"
            kmer_file.write_text(json.dumps(discovered), encoding="utf-8")
            request_file.write_text(json.dumps({
                "schema_version": 1, "lambda": 1,
                "weights": weights,
            }), encoding="utf-8")
            weighted_proc = subprocess.run(
                [str(binary), "assemble", "--kmers", str(kmer_file), "--request", str(request_file)],
                check=True, capture_output=True, text=True, timeout=10,
            )
            weighted = json.loads(weighted_proc.stdout)
            request_file.write_text(json.dumps({
                "schema_version": 1, "lambda": 0,
                "weights": {sequence: 1 for sequence in weights},
            }), encoding="utf-8")
            control_proc = subprocess.run(
                [str(binary), "assemble", "--kmers", str(kmer_file), "--request", str(request_file)],
                check=True, capture_output=True, text=True, timeout=10,
            )
            control = json.loads(control_proc.stdout)
            self.assertNotEqual(weakest, strongest)
            self.assertEqual(window_weight(profiles[weakest]["delta"], lambda_value=0), 1)
            self.assertEqual(weights[strongest], 2)
            self.assertNotEqual(control["selected_sequence_rna"], weighted["selected_sequence_rna"])
            self.assertEqual(weighted["selected_sequence_rna"], strongest)

    def test_energy_profile_has_explicit_lucid_compatibility_conventions(self):
        profile = energy_profile("AUGAUGAUGAUGAUGAUGAUG")
        self.assertEqual(profile["profile_id"], "lucid_end3_v1")
        self.assertEqual(profile["temperature_c"], 22)
        self.assertEqual(profile["salt_correction"], 5)
        self.assertTrue(all(isinstance(profile[key], float) for key in ("duplex_dg", "sense_end_dg", "antisense_end_dg", "delta")))

    def test_invalid_sequence_rejected_instead_of_silently_filtered(self):
        for sequence in ("ATNACGTACGTACGTACGTACG", "AC", "AUGX" * 5 + "A"):
            with self.subTest(sequence=sequence), self.assertRaises(ValueError):
                energy_profile(sequence)


if __name__ == "__main__":
    unittest.main()
