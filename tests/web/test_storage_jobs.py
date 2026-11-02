"""Durable job storage contracts, independent from the scientific engine."""
import tempfile
import unittest
from pathlib import Path

from services.simulator_api.storage import JobStore


class JobStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = JobStore(Path(self.temp.name) / "jobs.sqlite3")
        self.store.initialize()

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def test_idempotency_returns_same_job_only_for_same_request(self):
        first, created = self.store.submit("owner", "key", "hash-a", {"x": 1})
        again, created_again = self.store.submit("owner", "key", "hash-a", {"x": 1})
        self.assertTrue(created)
        self.assertFalse(created_again)
        self.assertEqual(first.id, again.id)
        with self.assertRaises(ValueError):
            self.store.submit("owner", "key", "hash-b", {"x": 2})

    def test_idempotency_scope_includes_owner(self):
        alice, _ = self.store.submit("alice", "key", "hash-a", {"x": 1})
        bob, created = self.store.submit("bob", "key", "hash-a", {"x": 1})
        self.assertTrue(created)
        self.assertNotEqual(alice.id, bob.id)

    def test_claim_is_single_and_progress_monotonic(self):
        job, _ = self.store.submit("owner", "key", "hash-a", {"x": 1})
        claimed = self.store.claim_next("engine-v1")
        self.assertEqual(claimed.id, job.id)
        self.assertIsNone(self.store.claim_next("engine-v1"))
        self.store.set_progress(job.id, 4, 10, "sampling")
        with self.assertRaises(ValueError):
            self.store.set_progress(job.id, 3, 10, "sampling")

    def test_cancel_queued_and_terminal_success(self):
        job, _ = self.store.submit("owner", "key", "hash-a", {"x": 1})
        self.assertTrue(self.store.cancel("owner", job.id))
        self.assertEqual(self.store.get_owned("owner", job.id).state, "cancelled")
        job2, _ = self.store.submit("owner", "key2", "hash-b", {"x": 2})
        self.store.claim_next("engine-v1")
        self.store.finish(job2.id, {"ok": True})
        self.assertEqual(self.store.get_owned("owner", job2.id).result, {"ok": True})

    def test_kind_migration_filter_and_artifact_registry(self):
        old = self.store.submit("owner", "legacy", "old", {"x": 1})[0]
        design, _ = self.store.submit("owner", "design", "new", {"x": 2}, kind="dsrna_design")
        self.assertEqual(old.kind, "simulation")
        self.assertEqual(design.kind, "dsrna_design")
        self.assertEqual([j.id for j in self.store.list_owned("owner", kind="dsrna_design")], [design.id])
        row = {"name":"ranking.csv", "relative_path":"artifacts/a/ranking.csv", "sha256":"a"*64, "bytes":4}
        self.store.register_artifacts(design.id, [row])
        self.assertEqual(self.store.get_artifact(design.id, "ranking.csv")["sha256"], "a"*64)
        self.assertIsNone(self.store.get_artifact(old.id, "ranking.csv"))

    def test_design_progress_uses_folded_candidate_counts_and_persists_terminal_time(self):
        job, _ = self.store.submit("owner", "design-progress", "new", {"x": 2}, kind="dsrna_design")
        self.assertNotIn("total", job.progress)
        claimed = self.store.claim_next("engine-v1")
        self.assertEqual(claimed.created_at, job.created_at)
        self.store.set_design_progress(job.id, {"stage": "folding", "operation": "ViennaRNA",
                                                "completed_candidates": 0, "total_candidates": 5,
                                                "fold_samples": 0, "estimated_remaining_seconds": None})
        self.store.set_design_progress(job.id, {"stage": "folding", "operation": "ViennaRNA",
                                                "completed_candidates": 3, "total_candidates": 5,
                                                "fold_samples": 3, "estimated_remaining_seconds": 2.5})
        self.assertEqual(self.store.get_owned("owner", job.id).progress["completed_candidates"], 3)
        with self.assertRaises(ValueError):
            self.store.set_design_progress(job.id, {"stage": "folding", "completed_candidates": 2,
                                                     "total_candidates": 5})
        self.store.finish(job.id, {"ok": True})
        done = self.store.get_owned("owner", job.id)
        self.assertIsNotNone(done.finished_at)
        self.assertEqual(done.progress["stage"], "complete")

    def test_queued_cancel_persists_terminal_timestamp(self):
        job, _ = self.store.submit("owner", "queued-cancel", "new", {"x": 2}, kind="dsrna_design")
        self.assertTrue(self.store.cancel("owner", job.id))
        cancelled = self.store.get_owned("owner", job.id)
        self.assertEqual(cancelled.state, "cancelled")
        self.assertIsNotNone(cancelled.finished_at)

    def test_owner_scoped_lookup_and_recovery(self):
        job, _ = self.store.submit("owner", "key", "hash-a", {"x": 1})
        self.store.close()
        self.store = JobStore(Path(self.temp.name) / "jobs.sqlite3")
        self.store.initialize()
        self.assertIsNone(self.store.get_owned("other", job.id))
        self.assertEqual(self.store.get_owned("owner", job.id).state, "queued")


if __name__ == "__main__":
    unittest.main()
