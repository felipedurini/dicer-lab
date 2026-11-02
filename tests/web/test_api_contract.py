import json
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from services.simulator_api.settings import Settings
from services.simulator_api.app import create_app
from tests.web.test_job_schema import request_dict


class ApiContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.settings = Settings.from_env({
            "APP_ENV": "test",
            "AUTH_MODE": "local",
            "APP_ORIGIN": "http://127.0.0.1:3000",
            "SIMULATOR_API_URL": "http://127.0.0.1:8000",
            "DATA_DIR": str(root / "data"),
            "PORT": "8000",
            "API_HOST": "127.0.0.1",
        })
        self.client = TestClient(create_app(self.settings), base_url="http://127.0.0.1")

    def tearDown(self):
        self.client.close()
        self.client.app.state.job_store.close()
        self.temp.cleanup()

    def test_public_health_is_minimal_and_uncached(self):
        response = self.client.get("/health/live")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})
        self.assertEqual(response.headers["cache-control"], "private, no-store")
        self.assertIn("x-request-id", response.headers)
        self.assertNotIn("version", response.json())

    def test_local_private_routes_reject_remote_and_malformed_host_headers(self):
        # A loopback peer is insufficient: a browser can resolve an attacker
        # hostname to loopback. Host must remain a valid loopback authority.
        for host in ("attacker.example", "127.0.0.1.attacker.example",
                     "localhost/ignored", "localhost?ignored", "localhost#ignored",
                     "localhost@attacker.example", "localhost:invalid",
                     "[::1", "local\thost"):
            with self.subTest(host=host):
                response = self.client.get("/v1/capabilities", headers={"host": host})
                self.assertEqual(response.status_code, 403)

    def test_local_private_routes_accept_valid_loopback_authorities(self):
        for host in ("127.0.0.1", "127.0.0.1:8000", "localhost:8000", "[::1]:8000"):
            with self.subTest(host=host):
                response = self.client.get("/v1/capabilities", headers={"host": host})
                self.assertEqual(response.status_code, 200)

    def test_local_private_routes_reject_duplicate_host_headers(self):
        response = self.client.get("/v1/capabilities", headers=[
            ("host", "localhost"), ("host", "attacker.example"),
        ])
        self.assertEqual(response.status_code, 403)

    def test_capabilities_describe_real_v1_limits_and_worker_readiness(self):
        response = self.client.get("/v1/capabilities")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["web_schema_version"], 1)
        self.assertEqual(data["limits"]["max_construct_length_nt"], 5000)
        self.assertEqual(data["limits"]["max_scenarios"], 4)
        self.assertFalse(data["worker_available"])
        self.assertEqual(data["terminal_rule"], "stop_on_overshoot_v1")

    def test_epsilon_profile_is_evaluated_by_scientific_engine(self):
        payload = {"web_schema_version": 1, "construct": {"length_nt": 315,
            "phase_origin_nt": 0, "segments": [{"segment_id": "all", "gene_id": "g", "start": 0, "end": 315}]},
            "p22": .5, "f_left": .5, "seed": 1,
            "epsilon": {"type": "custom", "schema_version": 1,
                         "expression": "0.05 + 0.15 * sqrt(1 - L/N)", "parameters": {}}}
        response = self.client.post("/v1/epsilon-profile", json=payload,
            headers={"origin": self.settings.app_origin})
        self.assertEqual(response.status_code, 200)
        profile = response.json()
        self.assertEqual(profile["points"][0]["length_nt"], 21)
        self.assertEqual(profile["points"][-1]["length_nt"], 315)
        self.assertAlmostEqual(profile["points"][-1]["epsilon"], .05)
        payload["epsilon"]["expression"] = "1 + L/N"
        rejected = self.client.post("/v1/epsilon-profile", json=payload,
            headers={"origin": self.settings.app_origin})
        self.assertEqual(rejected.status_code, 422)

    def test_invalid_json_contract_uses_shared_error_envelope(self):
        response = self.client.post(
            "/v1/jobs", content=json.dumps({"web_schema_version": 1}),
            headers={"content-type": "application/json", "origin": "http://127.0.0.1:3000"},
        )
        self.assertEqual(response.status_code, 422)
        error = response.json()["error"]
        self.assertTrue(error["code"])
        self.assertTrue(error["message"])
        self.assertTrue(error["request_id"])
        self.assertTrue(error["fields"])
        self.assertEqual(response.headers["x-request-id"], error["request_id"])
        self.assertEqual(response.headers["cache-control"], "private, no-store")

    def test_oversized_json_is_rejected_before_schema_validation(self):
        response = self.client.post(
            "/v1/jobs",
            content=b"{" + b" " * (65 * 1024),
            headers={"content-type": "application/json", "origin": "http://127.0.0.1:3000"},
        )
        self.assertEqual(response.status_code, 413)
        self.assertEqual(response.json()["error"]["code"], "request_too_large")

    def test_reference_endpoint_distinguishes_missing_catalog_from_empty_catalog(self):
        missing = self.client.get("/v1/design/references")
        self.assertEqual(missing.status_code, 200)
        self.assertEqual(missing.json(), {"items": [], "catalog_status": "missing"})
        references = self.settings.data_dir / "references"
        references.mkdir(parents=True)
        (references / "catalog.json").write_text(json.dumps({"schema_version": 1, "references": []}), encoding="utf-8")
        empty = self.client.get("/v1/design/references")
        self.assertEqual(empty.status_code, 200)
        self.assertEqual(empty.json(), {"items": [], "catalog_status": "ready"})

    def test_design_submission_uses_shared_store_and_kind_aware_idempotency(self):
        body = {"design_schema_version":1,"label":"synthetic","targets":[
            {"gene_id":"g1","sequence_rna":"AUGC"*11},
            {"gene_id":"g2","sequence_rna":"CGUA"*11}],
            "blocks":[{"gene_id":"g1","length_nt":21},{"gene_id":"g2","length_nt":21}],
            "reference_ids":[],"seed":12,"lambda":1,"thermo_profile":"lucid_end3_v1","iterations":3}
        headers={"origin":self.settings.app_origin,"idempotency-key":"00000000-0000-0000-0000-000000000012"}
        submitted=self.client.post("/v1/design/jobs",json=body,headers=headers)
        self.assertEqual(submitted.status_code,202,submitted.text)
        self.assertEqual(submitted.json()["kind"],"dsrna_design")
        self.assertEqual(self.client.get("/v1/jobs?kind=dsrna_design").json()["items"][0]["id"],submitted.json()["id"])
        replay=self.client.post("/v1/design/jobs",json=body,headers=headers)
        self.assertEqual(replay.status_code,200)
        self.assertEqual(replay.json()["id"],submitted.json()["id"])

    def test_candidate_transfer_keeps_sequence_snapshot_and_checks_job_ownership(self):
        store=self.client.app.state.job_store
        store.initialize()
        source,_=store.submit("00000000-0000-4000-8000-000000000001","design-source","design-hash",{"label":"design"},kind="dsrna_design")
        store.claim_next("engine")
        candidate={"candidate_id":"b"*64,"sequence_rna":"AUGC"*10+"AU","length_nt":42,
                   "blocks":[{"gene_id":"g1","start":0,"end":21},{"gene_id":"g2","start":21,"end":42}]}
        store.finish(source.id,{"candidates":[candidate]})
        from tests.web.test_job_schema import request_dict
        payload=request_dict(); payload.pop("construct"); payload["label"]="candidate sim"; payload["n_molecules"]=10
        headers={"origin":self.settings.app_origin,"idempotency-key":"00000000-0000-0000-0000-000000000099"}
        response=self.client.post(f"/v1/design/jobs/{source.id}/candidates/{candidate['candidate_id']}/simulate",json=payload,headers=headers)
        self.assertEqual(response.status_code,202,response.text)
        child=store.get_owned("00000000-0000-4000-8000-000000000001",response.json()["id"])
        self.assertEqual(child.kind,"simulation")
        self.assertEqual(child.request["_sequence_source"]["sha256"],__import__("hashlib").sha256(candidate["sequence_rna"].encode()).hexdigest())
        missing=self.client.post(f"/v1/design/jobs/123e4567-e89b-42d3-a456-426614174099/candidates/{candidate['candidate_id']}/simulate",json=payload,headers=headers)
        self.assertEqual(missing.status_code,404)

    def test_openapi_is_versioned_and_never_exposed_as_a_public_route(self):
        app = create_app(self.settings)
        schema = app.openapi()
        self.assertIn("/v1/capabilities", schema["paths"])
        self.assertIn("/v1/jobs", schema["paths"])
        self.assertNotIn("/openapi.json", {route.path for route in app.routes})
        self.assertNotIn("/docs", {route.path for route in app.routes})
        self.assertTrue(schema["info"]["version"].startswith("1."))
        app.state.job_store.close()

    def test_job_submission_is_durable_idempotent_and_owner_scoped(self):
        payload = request_dict()
        payload["n_molecules"] = 3
        payload["compute_exact"] = False
        headers = {"origin": self.settings.app_origin, "Idempotency-Key": "d51a328a-3420-47d0-a513-4a36461ce0c4"}
        first = self.client.post("/v1/jobs", json=payload, headers=headers)
        self.assertEqual(first.status_code, 202)
        self.assertEqual(first.json()["state"], "queued")
        repeat = self.client.post("/v1/jobs", json=payload, headers=headers)
        self.assertEqual(repeat.status_code, 200)
        self.assertEqual(first.json()["id"], repeat.json()["id"])
        payload["label"] = "different payload"
        conflict = self.client.post("/v1/jobs", json=payload, headers=headers)
        self.assertEqual(conflict.status_code, 409)
        self.assertEqual(self.client.get("/v1/jobs").status_code, 200)


if __name__ == "__main__":
    unittest.main()
