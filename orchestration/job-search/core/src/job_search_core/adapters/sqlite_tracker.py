"""SQLite tracker — the system of record for jobs and their status history."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from ..domain import (
    Job,
    Status,
    StatusChange,
    StatusSource,
    check_transition,
    now,
)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    data TEXT NOT NULL,          -- full Job as JSON
    status TEXT NOT NULL,        -- duplicated for querying
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS status_history (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT NOT NULL REFERENCES jobs(id),
    from_status TEXT,
    to_status TEXT NOT NULL,
    source TEXT NOT NULL,
    note TEXT,
    at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_jobs_status ON jobs(status);
"""


class SqliteTracker:
    def __init__(self, path: str | Path = ":memory:"):
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(str(path), check_same_thread=False)
        self._db.executescript(_SCHEMA)

    # -- reads -------------------------------------------------------------------------
    def get(self, job_id: str) -> Job:
        row = self._db.execute("SELECT data FROM jobs WHERE id = ?", (job_id,)).fetchone()
        if row is None:
            raise KeyError(job_id)
        return Job.model_validate_json(row[0])

    def list(self, statuses: set[Status] | None = None) -> list[Job]:
        rows = self._db.execute("SELECT data, status FROM jobs ORDER BY id").fetchall()
        return [Job.model_validate_json(d) for d, s in rows if not statuses or s in statuses]

    def history(self, job_id: str) -> list[StatusChange]:
        rows = self._db.execute(
            "SELECT from_status, to_status, source, note, at FROM status_history "
            "WHERE job_id = ? ORDER BY seq",
            (job_id,),
        ).fetchall()
        return [
            StatusChange(
                job_id=job_id,
                from_status=Status(f) if f else None,
                to_status=Status(t),
                source=src,
                note=note,
                at=at,
            )
            for f, t, src, note, at in rows
        ]

    # -- writes ------------------------------------------------------------------------
    def add(self, job: Job) -> Job:
        with self._db:
            self._db.execute(
                "INSERT INTO jobs (id, data, status, updated_at) VALUES (?, ?, ?, ?)",
                (job.id, job.model_dump_json(), job.status.value, job.updated_at.isoformat()),
            )
            self._record(job.id, None, job.status, "pipeline", "created")
        return job

    def save(self, job: Job) -> Job:
        stored = self.get(job.id)
        if job.status != stored.status:
            raise ValueError("status changes must go through transition()")
        job.updated_at = now()
        with self._db:
            self._write(job)
        return job

    def transition(
        self, job_id: str, to: Status, source: StatusSource, note: str | None = None
    ) -> Job:
        job = self.get(job_id)
        check_transition(job_id, job.status, to)
        previous = job.status
        job.status = to
        job.updated_at = now()
        with self._db:
            self._write(job)
            self._record(job_id, previous, to, source, note)
        return job

    def next_id(self, prefix: str = "LG") -> str:
        (count,) = self._db.execute("SELECT COUNT(*) FROM jobs").fetchone()
        return f"{prefix}-{count + 1:04d}"

    # -- internals ---------------------------------------------------------------------
    def _write(self, job: Job) -> None:
        self._db.execute(
            "UPDATE jobs SET data = ?, status = ?, updated_at = ? WHERE id = ?",
            (job.model_dump_json(), job.status.value, job.updated_at.isoformat(), job.id),
        )

    def _record(self, job_id, from_status, to_status, source, note) -> None:
        self._db.execute(
            "INSERT INTO status_history (job_id, from_status, to_status, source, note, at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                job_id,
                from_status.value if from_status else None,
                to_status.value,
                source,
                note,
                now().isoformat(),
            ),
        )
