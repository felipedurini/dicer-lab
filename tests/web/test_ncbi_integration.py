import asyncio
import tempfile
import unittest
from pathlib import Path

import httpx

from services.simulator_api.design.ncbi import NCBIClient, NCBIError
from services.simulator_api.design.references import ReferenceCatalog


GENBANK = """LOCUS       TEST000001               30 bp    mRNA    linear   INV 01-JAN-2025
DEFINITION  Example organism test transcript.
ACCESSION   TEST000001
VERSION     TEST000001.1
SOURCE      Example organism
  ORGANISM  Example organism
FEATURES             Location/Qualifiers
     source          1..30
        1 acgtacgtac gtacgtacgt acgtacgtac
//
"""


class NCBIIntegrationTests(unittest.TestCase):
    def test_gene_search_uses_eutils_metadata_without_downloading_search_sequences(self):
        async def scenario():
            async def handler(request: httpx.Request):
                if request.url.path.endswith("esearch.fcgi"):
                    self.assertIn("Dalbulus maidis", request.url.params["term"])
                    self.assertIn("eth", request.url.params["term"])
                    return httpx.Response(200, json={"esearchresult": {"idlist": ["123"]}})
                if request.url.path.endswith("esummary.fcgi"):
                    return httpx.Response(200, json={"result": {"123": {
                        "accessionversion": "PZ371507.1", "organism": "Dalbulus maidis",
                        "title": "eth mRNA", "slen": "615", "moltype": "rna",
                    }}})
                self.fail("A metadata search must not fetch sequence content")

            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                ncbi = NCBIClient(client, Path("unused"))
                rows = await ncbi.search(organism="Dalbulus maidis", query="eth", accession=None)
                self.assertEqual(rows[0]["accession"], "PZ371507.1")
                self.assertEqual(rows[0]["length_nt"], 615)
                self.assertNotIn("sequence_dna", rows[0])

        asyncio.run(scenario())

    def test_accession_metadata_fallback_is_bounded_and_reports_the_full_record_length(self):
        async def scenario():
            async def handler(request: httpx.Request):
                if request.url.path.endswith("esearch.fcgi"):
                    return httpx.Response(200, json={"esearchresult": {"idlist": []}})
                if request.url.path.endswith("efetch.fcgi"):
                    self.assertNotIn("seq_start", request.url.params)
                    return httpx.Response(200, text=GENBANK)
                self.fail(f"Unexpected E-utilities request: {request.url}")

            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                rows = await NCBIClient(client, Path("unused")).search(
                    organism=None, query=None, accession="TEST000001.1")
                self.assertEqual(rows[0]["length_nt"], 30)
                self.assertEqual(rows[0]["sequence_dna"], "ACGTACGTACGTACGTACGTACGTACGTAC")

        asyncio.run(scenario())

    def test_oversized_fetch_is_stopped_at_the_local_download_budget(self):
        async def scenario():
            async def handler(_request: httpx.Request):
                return httpx.Response(200, content=b"X" * 70_000)

            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                with self.assertRaisesRegex(NCBIError, "límite de tamaño"):
                    await NCBIClient(client, Path("unused")).fetch_records(
                        ["TEST000001.1"], max_total_nt=1)

        asyncio.run(scenario())

    def test_imported_accession_is_checksum_verified_persistent_partial_reference(self):
        async def scenario(root: Path):
            async def handler(request: httpx.Request):
                self.assertEqual(request.url.host, "eutils.ncbi.nlm.nih.gov")
                self.assertEqual(request.url.params["rettype"], "gb")
                return httpx.Response(200, text=GENBANK)

            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                ncbi = NCBIClient(client, root / "references")
                record = (await ncbi.fetch_records(["TEST000001.1"]))[0]
                self.assertEqual(record["sequence_rna"], "ACGUACGUACGUACGUACGUACGUACGUAC")
                imported = ncbi.persist_references([record])[0]
                self.assertEqual(imported["scope"], "partial_reference")
                self.assertEqual(imported["version"], "TEST000001.1")
                resolved = ReferenceCatalog(root / "references").resolve([imported["id"]])[0]
                self.assertEqual(resolved.length_nt, 30)
                self.assertEqual(resolved.scope, "partial_reference")
                return imported

        with tempfile.TemporaryDirectory() as temporary:
            first = asyncio.run(scenario(Path(temporary)))
            second = ReferenceCatalog(Path(temporary) / "references").list_public()[0]
            self.assertEqual(first["sha256"], second["sha256"])

    def test_rejects_non_accession_and_wrong_genbank_version(self):
        async def scenario():
            async def handler(_request: httpx.Request):
                return httpx.Response(200, text=GENBANK)

            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                ncbi = NCBIClient(client, Path("unused"))
                with self.assertRaises(NCBIError):
                    await ncbi.fetch_records(["https://invalid.example/sequence"])
                with self.assertRaises(NCBIError):
                    await ncbi.fetch_records(["TEST000001.2"])

        asyncio.run(scenario())
