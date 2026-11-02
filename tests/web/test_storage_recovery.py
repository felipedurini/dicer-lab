import tempfile
import unittest
from pathlib import Path

from services.simulator_api.storage import JobStore


class RecoveryTests(unittest.TestCase):
    def test_interrupted_job_requeues_once_then_fails_at_attempt_limit(self):
        with tempfile.TemporaryDirectory() as root:
            store = JobStore(Path(root) / "jobs.sqlite3")
            store.initialize()
            job, _ = store.submit("u", "k", "h", {})
            store.claim_next("engine")
            store.close()
            store = JobStore(Path(root) / "jobs.sqlite3")
            store.initialize()
            store.recover_running("engine")
            self.assertEqual(store.get_owned("u", job.id).state, "queued")
            store.claim_next("engine")
            store.close()
            store = JobStore(Path(root) / "jobs.sqlite3")
            store.initialize()
            store.recover_running("engine")
            self.assertEqual(store.get_owned("u", job.id).state, "failed")
            store.close()


if __name__ == "__main__":
    unittest.main()
