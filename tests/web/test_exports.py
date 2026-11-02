import tempfile
import unittest
from pathlib import Path
from fastapi.testclient import TestClient

from services.simulator_api.app import create_app
from services.simulator_api.settings import Settings
from tests.web.test_job_schema import request_dict


class ExportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.settings = Settings.from_env({"APP_ENV":"test","AUTH_MODE":"local","APP_ORIGIN":"http://127.0.0.1:3000","SIMULATOR_API_URL":"http://127.0.0.1:8000","DATA_DIR":str(Path(self.temp.name)/"data"),"API_HOST":"127.0.0.1"})
        self.app = create_app(self.settings, start_worker=False)
        self.client = TestClient(self.app, base_url="http://127.0.0.1")
        payload = request_dict(); payload["n_molecules"] = 5; payload["compute_exact"] = False
        response = self.client.post("/v1/jobs", json=payload, headers={"origin":self.settings.app_origin,"Idempotency-Key":"d51a328a-3420-47d0-a513-4a36461ce0c4"})
        self.job_id = response.json()["id"]
        store = self.app.state.job_store; store.claim_next("test-engine")
        store.finish(self.job_id, {"label":"safe", "scenarios":[{"id":"baseline", "metrics":[{"key":"length_21","scope":"global","scope_id":None,"numerator":2,"denominator":3,"value":2/3,"basis":"pooled_products","unit":"fraction","source_kind":"monte_carlo"}]}]})

    def tearDown(self):
        self.client.close(); self.app.state.job_store.close(); self.temp.cleanup()

    def test_private_result_json_and_csv_exports_are_owner_scoped(self):
        origin = {"origin":self.settings.app_origin}
        result = self.client.get(f"/v1/jobs/{self.job_id}/results")
        self.assertEqual(result.status_code, 200)
        exported = self.client.get(f"/v1/jobs/{self.job_id}/exports/results.json")
        self.assertEqual(exported.status_code, 200)
        self.assertEqual(exported.json()["label"], "safe")
        csv = self.client.get(f"/v1/jobs/{self.job_id}/exports/metrics.csv")
        self.assertEqual(csv.status_code, 200)
        self.assertIn("numerator,denominator", csv.text)
        self.assertEqual(self.client.get(f"/v1/jobs/{self.job_id}/exports/not-a-file").status_code, 404)

    def test_results_are_unavailable_until_terminal_success(self):
        payload = request_dict(); payload["n_molecules"] = 5; payload["compute_exact"] = False
        response = self.client.post("/v1/jobs", json=payload, headers={"origin":self.settings.app_origin,"Idempotency-Key":"d51a328a-3420-47d0-a513-4a36461ce0c5"})
        self.assertEqual(self.client.get(f"/v1/jobs/{response.json()['id']}/results").status_code, 409)


if __name__ == "__main__":
    unittest.main()
