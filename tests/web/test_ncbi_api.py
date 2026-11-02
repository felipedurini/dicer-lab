import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from services.simulator_api.app import create_app
from services.simulator_api.settings import Settings


class FakeNCBI:
    async def search(self, **_kwargs):
        return [{"accession": "TEST000001.1", "organism": "Example organism", "description": "gene transcript",
                 "length_nt": 30, "molecule_type": "mRNA", "source_uri": "https://www.ncbi.nlm.nih.gov/nuccore/TEST000001.1"}]

    async def fetch_records(self, accessions, *, max_total_nt=5_000_000):
        self.max_total_nt = max_total_nt
        if accessions != ["TEST000001.1"]:
            raise ValueError("unexpected accession")
        return [{"accession": "TEST000001.1", "organism": "Example organism", "description": "gene transcript",
                 "length_nt": 30, "molecule_type": "mRNA", "source_uri": "https://www.ncbi.nlm.nih.gov/nuccore/TEST000001.1",
                 "sequence_rna": "ACGU" * 7 + "AC", "sequence_dna": "ACGT" * 7 + "AC"}]

    def persist_references(self, records):
        return [{"id": "ncbi_TEST000001.1", "organism": records[0]["organism"], "version": records[0]["accession"],
                 "source_uri": records[0]["source_uri"], "license": "NCBI record", "sha256": "a" * 64,
                 "length_nt": records[0]["length_nt"], "record_count": 1, "scope": "partial_reference"}]


class NCBIAPITests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.settings = Settings.from_env({
            "APP_ENV": "test", "AUTH_MODE": "local", "APP_ORIGIN": "http://127.0.0.1:3000",
            "SIMULATOR_API_URL": "http://127.0.0.1:8000", "DATA_DIR": str(Path(self.temp.name) / "data"),
            "PORT": "8000", "API_HOST": "127.0.0.1",
        })
        self.app = create_app(self.settings, start_worker=False)
        self.client = TestClient(self.app, base_url="http://127.0.0.1")
        self.app.state.ncbi = FakeNCBI()

    def tearDown(self):
        self.client.close()
        self.app.state.job_store.close()
        self.temp.cleanup()

    def test_search_import_target_and_reference_routes(self):
        search = self.client.get("/v1/ncbi/search", params={"organism": "Example organism", "query": "gene"})
        self.assertEqual(search.status_code, 200)
        self.assertEqual(search.json()["items"][0]["length_nt"], 30)
        self.assertNotIn("sequence_rna", search.json()["items"][0])

        headers = {"origin": self.settings.app_origin}
        sequences = self.client.post("/v1/ncbi/sequences", json={"accessions": ["TEST000001.1"]}, headers=headers)
        self.assertEqual(sequences.status_code, 200)
        self.assertEqual(sequences.json()["items"][0]["sequence_rna"], "ACGU" * 7 + "AC")
        self.assertEqual(self.app.state.ncbi.max_total_nt, 20_000)

        references = self.client.post("/v1/ncbi/references", json={"accessions": ["TEST000001.1"]}, headers=headers)
        self.assertEqual(references.status_code, 200)
        self.assertEqual(references.json()["items"][0]["scope"], "partial_reference")
