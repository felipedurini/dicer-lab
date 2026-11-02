"""Small SQLite job store for the single local simulator worker."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from typing import Any
from uuid import uuid4


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class StoredJob:
    id: str
    owner_id: str
    kind: str
    state: str
    request: dict[str, Any]
    progress: dict[str, Any]
    result: dict[str, Any] | None
    error: dict[str, Any] | None
    attempts: int
    created_at: str
    updated_at: str
    finished_at: str | None


class JobStore:
    def __init__(self, path: Path | str):
        self.path = Path(path)
        self._connection: sqlite3.Connection | None = None

    def _db(self) -> sqlite3.Connection:
        if self._connection is None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._connection = sqlite3.connect(self.path, timeout=10, isolation_level=None, check_same_thread=False)
            self._connection.row_factory = sqlite3.Row
            self._connection.execute("PRAGMA journal_mode=WAL")
            self._connection.execute("PRAGMA foreign_keys=ON")
        return self._connection

    def initialize(self) -> None:
        self._db().executescript("""
          CREATE TABLE IF NOT EXISTS jobs(
            id TEXT PRIMARY KEY, owner_id TEXT NOT NULL, idempotency_key TEXT NOT NULL,
            request_hash TEXT NOT NULL, request_json TEXT NOT NULL, state TEXT NOT NULL,
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0,
            progress_json TEXT NOT NULL DEFAULT '{}', result_json TEXT, error_json TEXT,
            UNIQUE(owner_id,idempotency_key));
          CREATE INDEX IF NOT EXISTS jobs_owner_created ON jobs(owner_id,created_at DESC);
        """)
        columns = {row[1] for row in self._db().execute("PRAGMA table_info(jobs)")}
        if "kind" not in columns:
            self._db().execute("ALTER TABLE jobs ADD COLUMN kind TEXT NOT NULL DEFAULT 'simulation'")
        if "finished_at" not in columns:
            self._db().execute("ALTER TABLE jobs ADD COLUMN finished_at TEXT")
        self._db().execute("CREATE TABLE IF NOT EXISTS job_artifacts(job_id TEXT NOT NULL REFERENCES jobs(id),name TEXT NOT NULL,relative_path TEXT NOT NULL,sha256 TEXT NOT NULL,bytes INTEGER NOT NULL,PRIMARY KEY(job_id,name))")

    def close(self) -> None:
        if self._connection is not None:
            self._connection.close()
            self._connection = None

    @staticmethod
    def _job(row: sqlite3.Row | None) -> StoredJob | None:
        if row is None:
            return None
        return StoredJob(row["id"], row["owner_id"], row["kind"], row["state"], json.loads(row["request_json"]),
                         json.loads(row["progress_json"]), json.loads(row["result_json"]) if row["result_json"] else None,
                         json.loads(row["error_json"]) if row["error_json"] else None, row["attempts"],
                         row["created_at"], row["updated_at"], row["finished_at"])

    def submit(self, owner_id: str, key: str, request_hash: str, request: dict[str, Any], kind: str = "simulation") -> tuple[StoredJob, bool]:
        db = self._db()
        encoded = json.dumps(request, sort_keys=True, separators=(",", ":"), allow_nan=False)
        db.execute("BEGIN IMMEDIATE")
        try:
            existing = db.execute("SELECT * FROM jobs WHERE owner_id=? AND idempotency_key=?", (owner_id, key)).fetchone()
            if existing:
                if existing["request_hash"] != request_hash:
                    raise ValueError("idempotency_conflict")
                db.execute("COMMIT")
                return self._job(existing), False
            active = db.execute("SELECT count(*) FROM jobs WHERE state IN ('queued','running','cancel_requested')").fetchone()[0]
            owned = db.execute("SELECT count(*) FROM jobs WHERE owner_id=? AND state IN ('queued','running','cancel_requested')", (owner_id,)).fetchone()[0]
            if active >= 9 or owned >= 3:
                raise RuntimeError("queue_full")
            job_id = str(uuid4())
            now = _now()
            total = request.get("n_molecules", 0) * len(request.get("scenarios", []))
            design = kind == "dsrna_design"
            progress = ({"stage": "queued", "operation": "Esperando que el worker tome el trabajo"} if design else
                        {"stage": "queued", "scenario_id": None, "completed": 0, "total": total,
                        "completed_molecules": 0, "total_molecules": total,
                        "completed_scenarios": 0, "total_scenarios": len(request.get("scenarios", [])),
                        "completed_units": 0, "total_units": total})
            db.execute("INSERT INTO jobs(id,owner_id,idempotency_key,request_hash,request_json,state,created_at,updated_at,progress_json,kind) VALUES(?,?,?,?,?,'queued',?,?,?,?)",
                       (job_id, owner_id, key, request_hash, encoded, now, now, json.dumps(progress), kind))
            row = db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
            db.execute("COMMIT")
            return self._job(row), True
        except BaseException:
            if db.in_transaction:
                db.execute("ROLLBACK")
            raise

    def claim_next(self, engine_version: str) -> StoredJob | None:
        db = self._db()
        db.execute("BEGIN IMMEDIATE")
        try:
            row = db.execute("SELECT * FROM jobs WHERE state='queued' ORDER BY created_at,id LIMIT 1").fetchone()
            if row is None:
                db.execute("COMMIT")
                return None
            prior_progress = json.loads(row["progress_json"])
            now = _now()
            if row["kind"] == "dsrna_design":
                progress = {"stage": "starting", "operation": "Preparando el entorno de análisis", "engine_version": engine_version}
            else:
                progress = {"stage": "starting", "scenario_id": None, "completed": 0,
                            "total": prior_progress.get("total", 0), "completed_molecules": 0,
                            "total_molecules": prior_progress.get("total_molecules", 0),
                            "completed_scenarios": 0, "total_scenarios": prior_progress.get("total_scenarios", 0),
                            "completed_units": 0, "total_units": prior_progress.get("total_units", 0),
                            "engine_version": engine_version}
            db.execute("UPDATE jobs SET state='running',attempts=attempts+1,updated_at=?,progress_json=? WHERE id=? AND state='queued'",
                       (now, json.dumps(progress), row["id"]))
            claimed = db.execute("SELECT * FROM jobs WHERE id=?", (row["id"],)).fetchone()
            db.execute("COMMIT")
            return self._job(claimed)
        except BaseException:
            if db.in_transaction:
                db.execute("ROLLBACK")
            raise

    def set_progress(self, job_id: str, completed: int, total: int, stage: str,
                     scenario_id: str | None = None, completed_scenarios: int = 0,
                     total_scenarios: int = 0) -> None:
        row = self._db().execute("SELECT progress_json,state FROM jobs WHERE id=?", (job_id,)).fetchone()
        if row is None or row["state"] != "running":
            raise ValueError("job_not_running")
        previous = json.loads(row["progress_json"]).get("completed", 0)
        if completed < previous or completed > total or total < 0:
            raise ValueError("progress_not_monotonic")
        self._db().execute("UPDATE jobs SET progress_json=?,updated_at=? WHERE id=? AND state='running'",
            (json.dumps({"stage": stage, "scenario_id": scenario_id, "completed": completed, "total": total,
                         "completed_molecules": completed, "total_molecules": total,
                         "completed_scenarios": completed_scenarios, "total_scenarios": total_scenarios,
                         "completed_units": completed, "total_units": total}), _now(), job_id))

    def set_design_progress(self, job_id: str, progress: dict[str, Any]) -> None:
        row = self._db().execute("SELECT progress_json,state,kind FROM jobs WHERE id=?", (job_id,)).fetchone()
        if row is None or row["kind"] != "dsrna_design":
            raise ValueError("design_job_not_found")
        if row["state"] != "running":
            return
        previous = json.loads(row["progress_json"])
        if progress.get("stage") == "folding":
            completed = progress.get("completed_candidates", 0)
            total = progress.get("total_candidates", 0)
            prior_completed = previous.get("completed_candidates", 0) if previous.get("stage") == "folding" else 0
            if not isinstance(completed, int) or not isinstance(total, int) or completed < prior_completed or completed > total:
                raise ValueError("progress_not_monotonic")
        self._db().execute("UPDATE jobs SET progress_json=?,updated_at=? WHERE id=? AND state='running'",
                           (json.dumps(progress, allow_nan=False), _now(), job_id))

    def finish(self, job_id: str, result: dict[str, Any]) -> None:
        current = self._db().execute("SELECT progress_json FROM jobs WHERE id=? AND state='running'", (job_id,)).fetchone()
        if current is None:
            raise ValueError("job_not_running")
        previous = json.loads(current[0])
        previous["stage"] = "complete"
        previous["completed"] = previous.get("total", 0)
        previous["completed_molecules"] = previous.get("total_molecules", 0)
        previous["completed_scenarios"] = previous.get("total_scenarios", 0)
        finished_at = _now()
        changed = self._db().execute("UPDATE jobs SET state='succeeded',result_json=?,progress_json=?,updated_at=?,finished_at=? WHERE id=? AND state='running'",
            (json.dumps(result, sort_keys=True, separators=(",", ":"), allow_nan=False), json.dumps(previous), finished_at, finished_at, job_id)).rowcount
        if not changed:
            raise ValueError("job_not_running")

    def register_artifacts(self, job_id: str, records: list[dict[str, Any]]) -> None:
        db = self._db(); db.execute("BEGIN IMMEDIATE")
        try:
            db.execute("DELETE FROM job_artifacts WHERE job_id=?", (job_id,))
            db.executemany("INSERT INTO job_artifacts(job_id,name,relative_path,sha256,bytes) VALUES(?,?,?,?,?)",
                [(job_id, r["name"], r["relative_path"], r["sha256"], r["bytes"]) for r in records])
            db.execute("COMMIT")
        except BaseException:
            if db.in_transaction: db.execute("ROLLBACK")
            raise

    def get_artifact(self, job_id: str, name: str):
        return self._db().execute("SELECT name,relative_path,sha256,bytes FROM job_artifacts WHERE job_id=? AND name=?", (job_id, name)).fetchone()

    def fail(self, job_id: str, code: str, message: str, retryable: bool = False) -> None:
        finished_at = _now()
        changed = self._db().execute("UPDATE jobs SET state='failed',error_json=?,updated_at=?,finished_at=? WHERE id=? AND state='running'",
            (json.dumps({"code": code, "message": message, "retryable": retryable}), finished_at, finished_at, job_id)).rowcount
        if not changed:
            raise ValueError("job_not_running")

    def cancel(self, owner_id: str, job_id: str) -> bool:
        now = _now()
        changed = self._db().execute("UPDATE jobs SET state='cancelled',updated_at=?,finished_at=? WHERE id=? AND owner_id=? AND state='queued'", (now, now, job_id, owner_id)).rowcount
        if changed:
            return True
        return self._db().execute("UPDATE jobs SET state='cancel_requested',updated_at=? WHERE id=? AND owner_id=? AND state='running'", (_now(), job_id, owner_id)).rowcount > 0

    def is_cancel_requested(self, job_id: str) -> bool:
        row = self._db().execute("SELECT state FROM jobs WHERE id=?", (job_id,)).fetchone()
        return row is None or row["state"] in {"cancelled", "cancel_requested"}

    def mark_cancelled(self, job_id: str) -> None:
        now = _now()
        self._db().execute("UPDATE jobs SET state='cancelled',result_json=NULL,updated_at=?,finished_at=? WHERE id=? AND state='cancel_requested'", (now, now, job_id))

    def get_owned(self, owner_id: str, job_id: str) -> StoredJob | None:
        return self._job(self._db().execute("SELECT * FROM jobs WHERE id=? AND owner_id=?", (job_id, owner_id)).fetchone())

    def delete_owned(self, owner_id: str, job_id: str) -> bool:
        """Delete terminal result data while retaining the idempotency tombstone."""
        changed = self._db().execute(
            "UPDATE jobs SET state='deleted',result_json=NULL,error_json=NULL,updated_at=? "
            "WHERE id=? AND owner_id=? AND state IN ('succeeded','failed','cancelled')",
            (_now(), job_id, owner_id),
        ).rowcount
        if changed:
            self._db().execute("DELETE FROM job_artifacts WHERE job_id=?", (job_id,))
        return changed > 0

    def list_owned(self, owner_id: str, limit: int = 20, before: str | None = None, kind: str | None = None) -> list[StoredJob]:
        if not 1 <= limit <= 50:
            raise ValueError("invalid_limit")
        clauses, params = ["owner_id=?"], [owner_id]
        if before:
            clauses.append("created_at<?"); params.append(before)
        if kind:
            clauses.append("kind=?"); params.append(kind)
        params.append(limit)
        rows = self._db().execute(f"SELECT * FROM jobs WHERE {' AND '.join(clauses)} ORDER BY created_at DESC LIMIT ?", params).fetchall()
        return [self._job(row) for row in rows]

    def recover_running(self, engine_version: str) -> None:
        db = self._db()
        rows = db.execute("SELECT id,state,attempts,progress_json FROM jobs WHERE state IN ('running','cancel_requested')").fetchall()
        for row in rows:
            if row["state"] == "cancel_requested":
                self.mark_cancelled(row["id"])
            elif row["attempts"] >= 2 or json.loads(row["progress_json"]).get("engine_version") != engine_version:
                self.fail(row["id"], "worker_interrupted", "El proceso terminó durante la simulación", True)
            else:
                progress = {**json.loads(row["progress_json"]), "stage": "requeued", "completed": 0}
                db.execute("UPDATE jobs SET state='queued',progress_json=?,updated_at=? WHERE id=?", (json.dumps(progress), _now(), row["id"]))
