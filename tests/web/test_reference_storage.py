from __future__ import annotations

import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest

from services.simulator_api.design.reference_data import bootstrap_references
from services.simulator_api.design.dsrnamax import DsRNAMaxAdapter
from services.simulator_api.design.references import ReferenceCatalog, read_sequences


class ReferenceStorageTests(unittest.TestCase):
    def test_bundled_apis_transcriptome_matches_versioned_manifest(self):
        assets = Path(__file__).resolve().parents[2] / "services" / "simulator_api" / "reference_data"
        with tempfile.TemporaryDirectory() as temporary:
            references_dir = Path(temporary) / "references"
            installed = bootstrap_references(references_dir, assets_dir=assets)
            self.assertEqual(installed, ["apis_mellifera_amel_hav3_1_ar104"])
            reference = ReferenceCatalog(references_dir).resolve(installed)[0]
            self.assertEqual(reference.record_count, 27_887)
            self.assertEqual(reference.length_nt, 98_645_700)
            self.assertEqual(reference.scope, "complete_transcriptome")
            self.assertEqual(reference.assembly_accession, "GCF_003254395.2")
            self.assertEqual(reference.annotation_release, 104)
            self.assertEqual(reference.sha256, "124a2d9c0b0d395b6350b37a4a0980725f8b69fbbb25bf6079d1f65211a6c28e")

    @unittest.skipUnless(os.environ.get("DICER_GO") or shutil.which("go"), "Go toolchain required for full transcriptome screen")
    def test_real_go_screen_finds_window_in_bundled_apis_transcriptome(self):
        assets = Path(__file__).resolve().parents[2] / "services" / "simulator_api" / "reference_data"
        with tempfile.TemporaryDirectory() as temporary:
            references_dir = Path(temporary) / "references"
            bootstrap_references(references_dir, assets_dir=assets)
            reference = ReferenceCatalog(references_dir).resolve(["apis_mellifera_amel_hav3_1_ar104"])[0]
            first_sequence = next(
                sequence for _, sequence in read_sequences(reference)
                if len(sequence) >= 21 and set(sequence[:21]) <= set("ACGU")
            )
            candidate = first_sequence[:21].replace("U", "T")
            work_dir = Path(temporary) / "screen"
            work_dir.mkdir()
            result = DsRNAMaxAdapter().screen(
                work_dir,
                [{"id": "probe", "sequence_dna": candidate}],
                [reference.path],
            )
            self.assertTrue(any(hit["candidate_id"] == "probe" for hit in result["hits"]))

    def test_reference_budget_supports_full_transcriptomes_over_five_megabases(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fasta = root / "large.fa"
            record = "ACGT" * 1_500_001
            fasta.write_text(">large_v1|transcript\n" + record + "\n", encoding="ascii")
            entry = {
                "id": "large_v1", "organism": "Example species", "version": "v1",
                "source_uri": "https://example.invalid/assembly/v1", "license": "test",
                "relative_path": "large.fa", "sha256": hashlib.sha256(fasta.read_bytes()).hexdigest(),
                "length_nt": len(record), "record_count": 1,
                "scope": "complete_transcriptome", "completeness": "complete_annotated_transcript_set",
            }
            (root / "catalog.json").write_text(json.dumps({"schema_version": 1, "references": [entry]}), encoding="utf-8")
            reference = ReferenceCatalog(root).resolve(["large_v1"])[0]
            self.assertEqual(reference.length_nt, 6_000_004)

    def test_bootstrap_installs_versioned_reference_and_merges_dynamic_catalog(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            assets = root / "assets"
            data = root / "persistent" / "references"
            assets.mkdir()
            archive = assets / "source.fa.gz"
            source = b">NM_TEST.1 transcript one\nACGTACGTACGTACGTACGTACGTACGT\n>XR_TEST.1 transcript two\nTTTTCCCCAAAAGGGGTTTTCCCCAAAA\n"
            with gzip.open(archive, "wb") as output:
                output.write(source)
            dynamic = data / "ncbi" / "ncbi_TEST000001.1.fa"
            dynamic.parent.mkdir(parents=True)
            dynamic.write_text(">ncbi_TEST000001.1|TEST000001.1 individual transcript\nACGTACGTACGTACGTACGTACGTACGT\n", encoding="ascii")
            dynamic_entry = {
                "id": "ncbi_TEST000001.1", "organism": "Example", "version": "TEST000001.1",
                "source_uri": "https://example.invalid/record", "license": "NCBI",
                "relative_path": "ncbi/ncbi_TEST000001.1.fa",
                "sha256": hashlib.sha256(dynamic.read_bytes()).hexdigest(), "length_nt": 28,
                "record_count": 1, "scope": "partial_reference",
            }
            (data / "catalog.json").write_text(json.dumps({"schema_version": 1, "references": [dynamic_entry]}), encoding="utf-8")
            fasta = b">apis_mellifera_amel_hav3_1_ar104|NM_TEST.1 transcript one\nACGTACGTACGTACGTACGTACGTACGT\n>apis_mellifera_amel_hav3_1_ar104|XR_TEST.1 transcript two\nTTTTCCCCAAAAGGGGTTTTCCCCAAAA\n"
            static_entry = {
                "id": "apis_mellifera_amel_hav3_1_ar104", "organism": "Apis mellifera", "version": "GCF_003254395.2; Annotation Release 104",
                "source_uri": "https://ftp.ncbi.nlm.nih.gov/genomes/all/annotation_releases/example/rna.fna.gz",
                "license": "NCBI RefSeq public sequence data", "relative_path": "builtin/apis_mellifera.fa",
                "sha256": hashlib.sha256(fasta).hexdigest(), "length_nt": 56, "record_count": 2,
                "scope": "complete_transcriptome", "completeness": "complete_annotated_transcript_set",
                "molecule_type": "mixed RNA transcripts", "provenance": "NCBI RefSeq Annotation Release 104",
                "asset_relative_path": "source.fa.gz", "asset_sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
            }
            (assets / "catalog.json").write_text(json.dumps({"schema_version": 1, "references": [static_entry]}), encoding="utf-8")

            result = bootstrap_references(data, assets_dir=assets)

            self.assertEqual(result, ["apis_mellifera_amel_hav3_1_ar104"])
            public = {item["id"]: item for item in ReferenceCatalog(data).list_public()}
            self.assertEqual(set(public), {"ncbi_TEST000001.1", "apis_mellifera_amel_hav3_1_ar104"})
            self.assertEqual(public["apis_mellifera_amel_hav3_1_ar104"]["record_count"], 2)
            self.assertEqual(public["apis_mellifera_amel_hav3_1_ar104"]["scope"], "complete_transcriptome")
            self.assertTrue((data / "builtin" / "apis_mellifera.fa").is_file())

    def test_metadata_listing_does_not_scan_fasta_but_selection_verifies_it(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fasta = root / "ref.fa"
            fasta.write_text(">ref|tx\nAAAAAAAAAAAAAAAAAAAAA\n", encoding="ascii")
            entry = {
                "id": "ref", "organism": "Example", "version": "v1",
                "source_uri": "https://example.invalid/v1", "license": "test",
                "relative_path": "ref.fa", "sha256": "0" * 64,
                "length_nt": 21, "record_count": 1,
            }
            (root / "catalog.json").write_text(json.dumps({"schema_version": 1, "references": [entry]}), encoding="utf-8")
            self.assertEqual(ReferenceCatalog(root).list_public()[0]["id"], "ref")
            with self.assertRaises(ValueError):
                ReferenceCatalog(root).resolve(["ref"])

    def test_bootstrap_rejects_corrupt_existing_asset(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            assets, data = root / "assets", root / "references"
            assets.mkdir()
            archive = assets / "source.gz"
            with gzip.open(archive, "wb") as output:
                output.write(b">tx\nACGTACGTACGTACGTACGTACGTACGT\n")
            fasta_path = data / "builtin" / "ref.fa"
            fasta_path.parent.mkdir(parents=True)
            fasta_path.write_text(">ref|tx\nAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA\n", encoding="ascii")
            entry = {
                "id": "ref", "organism": "Example", "version": "v1", "source_uri": "https://example.invalid",
                "license": "test", "relative_path": "builtin/ref.fa", "sha256": "0" * 64,
                "length_nt": 30, "record_count": 1, "asset_relative_path": "source.gz",
                "asset_sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
            }
            (assets / "catalog.json").write_text(json.dumps({"schema_version": 1, "references": [entry]}), encoding="utf-8")
            with self.assertRaises(ValueError):
                bootstrap_references(data, assets_dir=assets)


if __name__ == "__main__":
    unittest.main()
