from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from pydantic import ValidationError

from services.simulator_api.design.references import ReferenceCatalog, ReferenceError
from services.simulator_api.design.schemas import DesignRequest
from services.simulator_api.design.dsrnamax import DsRNAMaxAdapter
from services.simulator_api.design.pipeline import DesignPipeline, DesignPipelineError


ROOT = Path(__file__).resolve().parents[2]
GO = os.environ.get("DICER_GO") or shutil.which("go")


def design_request() -> dict:
    return {
        "design_schema_version": 1,
        "label": "fixture",
        "targets": [
            {"gene_id": "g0", "sequence_rna": "UGGUAGGGCAAGAACCGAUCU"},
            {"gene_id": "g1", "sequence_rna": "AUGUUUACAUAAAAUUCGCGC"},
        ],
        "blocks": [
            {"gene_id": "g0", "length_nt": 21},
            {"gene_id": "g1", "length_nt": 21},
        ],
        "reference_ids": [], "seed": 17, "lambda": 1,
        "thermo_profile": "lucid_end3_v1", "iterations": 10,
    }


class DesignRequestContractTests(unittest.TestCase):
    def test_normalizes_and_checks_complete_unique_gene_blocks(self):
        request = DesignRequest.model_validate(design_request())
        self.assertEqual(request.targets[0].sequence_dna, "TGGTAGGGCAAGAACCGATCT")
        self.assertEqual(request.total_construct_length, 42)

    def test_rejects_ambiguity_duplicate_ids_and_incomplete_block_assignment(self):
        for mutate in (
            lambda data: data["targets"][0].update(sequence_rna="N" + data["targets"][0]["sequence_rna"][1:]),
            lambda data: data["targets"][1].update(gene_id="g0"),
            lambda data: data["blocks"].pop(),
            lambda data: data["blocks"][0].update(length_nt=20),
            lambda data: data.update(seed=2**31),
        ):
            value = design_request()
            mutate(value)
            with self.subTest(value=value), self.assertRaises(ValidationError):
                DesignRequest.model_validate(value)


class DsRNAMaxProcessTests(unittest.TestCase):
    def test_execute_drains_large_stdout_and_stderr_while_process_runs(self):
        import sys
        adapter = DsRNAMaxAdapter()
        code = "import sys; sys.stdout.write('o' * 200000); sys.stdout.flush(); sys.stderr.write('e' * 200000); sys.stderr.flush()"
        completed = adapter._execute([sys.executable, "-c", code])
        self.assertEqual(completed.returncode, 0)
        self.assertEqual(len(completed.stdout), 200000)
        self.assertEqual(len(completed.stderr), 200000)

    def test_execute_waits_for_a_slow_child_without_an_execution_deadline(self):
        import sys
        import time
        started = time.monotonic()
        completed = DsRNAMaxAdapter()._execute([sys.executable, "-c", "import time; time.sleep(1.1); print('done')"])
        self.assertEqual(completed.stdout.strip(), "done")
        self.assertGreaterEqual(time.monotonic() - started, 1.0)

    def test_execute_cancels_a_running_child(self):
        import sys
        import time
        started = time.monotonic()
        adapter = DsRNAMaxAdapter(cancel_check=lambda: time.monotonic() - started > 0.15)
        with self.assertRaises(Exception) as context:
            adapter._execute([sys.executable, "-c", "import time; time.sleep(10)"])
        self.assertEqual(getattr(context.exception, "code", None), "job_cancelled")


class ReferenceCatalogTests(unittest.TestCase):
    def test_reference_checksum_and_identity_are_verified(self):
        with tempfile.TemporaryDirectory(prefix="dicer-reference-") as tmp:
            root = Path(tmp) / "references"
            fasta = root / "toy.fa"
            root.mkdir()
            fasta.write_text(">toy_v1|tx\nACGTACGT\n", encoding="ascii")
            from hashlib import sha256
            checksum = sha256(fasta.read_bytes()).hexdigest()
            catalog = root / "catalog.json"
            catalog.write_text(json.dumps({"schema_version": 1, "references": [{
                "id": "toy_v1", "organism": "toy", "version": "v1",
                "source_uri": "https://example.invalid/toy", "license": "CC0",
                "relative_path": "toy.fa", "sha256": checksum,
                "length_nt": 8, "record_count": 1,
            }]}), encoding="utf-8")
            resolved = ReferenceCatalog(root).resolve(["toy_v1"])
            self.assertEqual(resolved[0].path, fasta.resolve())
            fasta.write_text(">r1|tx\nACGTACGA\n", encoding="ascii")
            with self.assertRaises(ReferenceError):
                ReferenceCatalog(root).resolve(["toy_v1"])

    def test_reference_path_escape_is_rejected(self):
        with tempfile.TemporaryDirectory(prefix="dicer-reference-") as tmp:
            root = Path(tmp) / "references"
            root.mkdir()
            catalog = root / "catalog.json"
            catalog.write_text(json.dumps({"schema_version": 1, "references": [{
                "id": "escape", "organism": "toy", "version": "v1",
                "source_uri": "local", "license": "CC0",
                "relative_path": "../outside.fa", "sha256": "0" * 64,
                "length_nt": 1, "record_count": 1,
            }]}), encoding="utf-8")
            with self.assertRaises(ReferenceError):
                ReferenceCatalog(root).resolve(["escape"])


@unittest.skipUnless(GO, "Go toolchain required for real pipeline integration")
class DesignPipelineIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.adapter = DsRNAMaxAdapter()

    def test_two_nonoverlapping_target_genes_form_reproducible_chimera(self):
        request = DesignRequest.model_validate(design_request())
        with tempfile.TemporaryDirectory(prefix="dicer-pipeline-") as tmp:
            progress = []
            result = DesignPipeline(self.adapter, ReferenceCatalog(Path(tmp) / "references")).run(
                request, work_dir=Path(tmp) / "work", progress=progress.append
            )
            self.assertEqual(len(result["candidates"]), 1)
            candidate = result["candidates"][0]
            expected = request.targets[0].sequence_rna + request.targets[1].sequence_rna
            self.assertEqual(candidate["sequence_rna"], expected)
            self.assertEqual([item["gene_id"] for item in candidate["blocks"]], ["g0", "g1"])
            self.assertLessEqual(candidate["metrics"]["minimum_gene_coverage"], 1.0)
            self.assertEqual(result["off_target_screen"], {
                "performed": False,
                "status": "not_run_no_references_selected",
                "method": None,
                "reference_ids": [],
                "candidate_count": 0,
                "candidate_hit_count": 0,
                "window_hit_count": 0,
                "reference_windows_skipped": 0,
            })
            folding_updates = [item for item in progress if item["stage"] == "folding"]
            self.assertEqual(folding_updates[0]["completed_candidates"], 0)
            self.assertEqual(folding_updates[-1]["completed_candidates"], 1)
            self.assertEqual(folding_updates[-1]["total_candidates"], 1)
            self.assertEqual(folding_updates[-1]["estimated_remaining_seconds"], None)
            repeated = DesignPipeline(self.adapter, ReferenceCatalog(Path(tmp) / "references")).run(
                request, work_dir=Path(tmp) / "second"
            )
            self.assertEqual([item["candidate_id"] for item in result["candidates"]],
                             [item["candidate_id"] for item in repeated["candidates"]])

    def test_selected_reference_screen_is_explicit_in_successful_result(self):
        request_data = design_request()
        request_data["reference_ids"] = ["toy_ref"]
        request = DesignRequest.model_validate(request_data)
        with tempfile.TemporaryDirectory(prefix="dicer-screen-summary-") as tmp:
            root = Path(tmp) / "references"
            root.mkdir()
            fasta = root / "toy.fa"
            fasta.write_text(">toy_ref|tx\n" + "C" * 100 + "\n", encoding="ascii")
            from hashlib import sha256
            (root / "catalog.json").write_text(json.dumps({"schema_version": 1, "references": [{
                "id": "toy_ref", "organism": "fixture", "version": "v1",
                "source_uri": "fixture", "license": "CC0", "relative_path": "toy.fa",
                "sha256": sha256(fasta.read_bytes()).hexdigest(), "length_nt": 100, "record_count": 1,
            }]}), encoding="utf-8")
            folding = {"dimer": {"gap_per_nt": 0.0}}
            with patch("services.simulator_api.design.pipeline.fold_candidate", return_value=folding):
                result = DesignPipeline(DsRNAMaxAdapter(), ReferenceCatalog(root)).run(
                    request, work_dir=Path(tmp) / "work"
                )
            summary = result["off_target_screen"]
            self.assertTrue(summary["performed"])
            self.assertEqual(summary["status"], "completed")
            self.assertEqual(summary["method"], "exact_21nt_forward_or_reverse_complement")
            self.assertEqual(summary["reference_ids"], ["toy_ref"])
            self.assertEqual(summary["candidate_count"], 1)
            self.assertEqual(summary["candidate_hit_count"], 0)

    def test_candidate_with_off_target_only_at_gene_junction_is_rejected(self):
        request_data = design_request()
        complete = request_data["targets"][0]["sequence_rna"] + request_data["targets"][1]["sequence_rna"]
        junction = complete[11:32]
        reference_id = "junction_ref"
        with tempfile.TemporaryDirectory(prefix="dicer-pipeline-junction-") as tmp:
            reference_dir = Path(tmp) / "references"
            reference_dir.mkdir()
            fasta = reference_dir / "junction.fa"
            rc = junction.translate(str.maketrans("ACGU", "TGCA"))[::-1]
            fasta.write_text(f">{reference_id}|tx\n{rc}\n", encoding="ascii")
            from hashlib import sha256
            catalog = {"schema_version": 1, "references": [{
                "id": reference_id, "organism": "fixture", "version": "v1",
                "source_uri": "fixture", "license": "CC0", "relative_path": "junction.fa",
                "sha256": sha256(fasta.read_bytes()).hexdigest(), "length_nt": 21, "record_count": 1,
            }]}
            (reference_dir / "catalog.json").write_text(json.dumps(catalog), encoding="utf-8")
            request_data["reference_ids"] = [reference_id]
            request = DesignRequest.model_validate(request_data)
            with self.assertRaises(DesignPipelineError) as context:
                DesignPipeline(DsRNAMaxAdapter(), ReferenceCatalog(reference_dir)).run(
                    request, work_dir=Path(tmp) / "work"
                )
            self.assertEqual(context.exception.code, "no_feasible_candidate")


@unittest.skipUnless(GO, "Go toolchain required for real multi-gene dsRNAmax integration")
class DsRNAMaxBlockIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory(prefix="dicer-dsrnamax-e2-")
        cls.binary = Path(cls._tmp.name) / ("dsrnamax.exe" if os.name == "nt" else "dsrnamax")
        subprocess.run([GO, "build", "-o", str(cls.binary), "."],
                       cwd=ROOT / "vendor" / "dsrnamax", check=True,
                       capture_output=True, text=True, timeout=90)

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def _call(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run([str(self.binary), *args], check=True, capture_output=True,
                              text=True, timeout=10)

    def test_reverse_complement_off_target_removes_target_kmer_with_reference_provenance(self):
        with tempfile.TemporaryDirectory(prefix="dicer-offtarget-") as tmp:
            root = Path(tmp)
            target = root / "targets.fa"
            reference = root / "reference.fa"
            target.write_text(">g0\nTGGTAGGGCAAGAACCGATCT\n", encoding="ascii")
            reference.write_text(">refA|tx1\nAGATCGGTTCTTGCCCTACCA\n", encoding="ascii")
            proc = self._call("discover", "--targets", str(target), "--k", "21",
                              "--offtargets", str(reference))
            result = json.loads(proc.stdout)
            self.assertEqual(result["kmers"], [])
            self.assertEqual(result["filtered_kmers"][0]["excluded_reference_ids"], ["refA"])

    def test_ambiguous_reference_base_breaks_windows_instead_of_joining_flanks(self):
        with tempfile.TemporaryDirectory(prefix="dicer-ambiguous-reference-") as tmp:
            root = Path(tmp)
            target = root / "targets.fa"
            reference = root / "reference.fa"
            target.write_text(">g0\nTGGTAGGGCAAGAACCGATCT\n", encoding="ascii")
            reference.write_text(">refA|tx1\nAAAAAAAAAAANAAAAAAAAAAA\n", encoding="ascii")
            result = json.loads(self._call("discover", "--targets", str(target), "--k", "21",
                                           "--offtargets", str(reference)).stdout)
            self.assertEqual(result["kmers"][0]["excluded_reference_ids"], [])
            self.assertEqual(result["reference_windows_skipped"], 3)

    def test_thermodynamic_window_weights_choose_block_during_assembly(self):
        with tempfile.TemporaryDirectory(prefix="dicer-weighted-block-") as tmp:
            request = Path(tmp) / "blocks.json"
            request.write_text(json.dumps({
                "schema_version": 1,
                "targets": [{"gene_id": "g0", "sequence_dna": "AAAAAAAAAAAAAAAAAAAAAC"}],
                "block_lengths": [{"gene_id": "g0", "length_nt": 21}],
                "weights": {"A" * 21: 1, "A" * 20 + "C": 2},
                "max_blocks_per_gene": 5,
            }), encoding="ascii")
            result = json.loads(self._call("blocks", "--request", str(request)).stdout)
            self.assertEqual(result["blocks"][0]["blocks"][0]["sequence_rna"], "A" * 20 + "C")
            self.assertEqual(result["blocks"][0]["blocks"][0]["score"], 2)

    def test_full_candidate_screen_finds_off_target_created_only_at_chimera_junction(self):
        first = "TGGTAGGGCAAGAACCGATCT"
        second = "ATGTTTACATAAAATTCGCGC"
        candidate = first + second
        junction = candidate[11:32]
        complement = junction.translate(str.maketrans("ACGT", "TGCA"))[::-1]
        with tempfile.TemporaryDirectory(prefix="dicer-junction-screen-") as tmp:
            root = Path(tmp)
            request = root / "candidates.json"
            reference = root / "offtargets.fa"
            request.write_text(json.dumps({"schema_version": 1, "candidates": [
                {"id": "chimera", "sequence_dna": candidate},
            ]}), encoding="ascii")
            reference.write_text(f">ref1|junction\n{complement}\n", encoding="ascii")
            result = json.loads(self._call("screen", "--request", str(request),
                                           "--offtargets", str(reference)).stdout)
            self.assertEqual([(item["start"], item["end"]) for item in result["hits"]], [(11, 32)])
            self.assertEqual(result["hits"][0]["reference_ids"], ["ref1"])


if __name__ == "__main__":
    unittest.main()
