import tempfile
import unittest
from pathlib import Path

from services.simulator_api.storage import JobStore
from services.simulator_api.worker import execute_request
from tests.web.test_job_schema import request_dict


class WorkerExecutionTests(unittest.TestCase):
    def test_custom_policy_runs_through_worker_and_is_preserved_in_trace(self):
        with tempfile.TemporaryDirectory() as root:
            store = JobStore(Path(root) / "jobs.sqlite3")
            store.initialize()
            request = request_dict()
            request["n_molecules"] = 5
            request["construct"]["length_nt"] = 42
            request["construct"]["segments"] = [{"segment_id": "only", "gene_id": "gene_a", "start": 0, "end": 42}]
            request["scenarios"] = request["scenarios"][:1]
            request["scenarios"][0]["epsilon"] = {"type": "custom", "schema_version": 1,
                "expression": "α + β*(1-L/N)", "parameters": {"α": .1, "β": .2}}
            request["compute_exact"] = True
            job, _ = store.submit("owner", "custom", "custom-hash", request)
            store.claim_next("engine")
            result = execute_request(request, store, job.id)
            policy = result["scenarios"][0]["first_trajectory"]["config"]["model"]["epsilon"]
            self.assertEqual(policy["expression"], "α + β*(1-L/N)")
            self.assertEqual(policy["parameters"], {"α": .1, "β": .2})
            store.close()

    def test_worker_uses_existing_engine_and_returns_observed_dp_and_first_trace(self):
        with tempfile.TemporaryDirectory() as root:
            store = JobStore(Path(root) / "jobs.sqlite3")
            store.initialize()
            request = request_dict()
            request["n_molecules"] = 25
            request["construct"]["length_nt"] = 42
            request["construct"]["segments"] = [{"segment_id": "only", "gene_id": "gene_a", "start": 0, "end": 42}]
            request["scenarios"] = request["scenarios"][:1]
            request["compute_exact"] = True
            request["baseline_id"] = "baseline"
            job, _ = store.submit("owner", "key", "hash", request)
            store.claim_next("engine")
            result = execute_request(request, store, job.id)
            scenario = result["scenarios"][0]
            self.assertEqual(result["web_schema_version"], 1)
            self.assertEqual(scenario["first_trajectory"]["source"]["kind"], "population_first")
            self.assertTrue(any(metric["source_kind"] == "exact_expectation" for metric in scenario["metrics"]))
            self.assertTrue(any(metric["source_kind"] == "monte_carlo" for metric in scenario["metrics"]))
            self.assertEqual(scenario["summary"]["n_molecules"], 25)
            store.close()


if __name__ == "__main__":
    unittest.main()
