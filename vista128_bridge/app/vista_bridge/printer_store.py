from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import sqlite3


@dataclass(frozen=True)
class PrintJob:
    job_id: int
    payload: bytes


class PrintQueueStore:
    def __init__(self, path: str, *, max_terminal_rows: int = 5000) -> None:
        self.max_terminal_rows = max(1, int(max_terminal_rows))
        db_path = Path(path)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(db_path)
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute("PRAGMA synchronous=FULL")
        self._db.execute(
            """
            CREATE TABLE IF NOT EXISTS print_jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                event_code TEXT NOT NULL,
                payload BLOB NOT NULL DEFAULT X'',
                status TEXT NOT NULL DEFAULT 'pending',
                attempts INTEGER NOT NULL DEFAULT 0,
                last_error TEXT NOT NULL DEFAULT '',
                completed_at TEXT NOT NULL DEFAULT ''
            )
            """
        )
        self._db.execute(
            "CREATE INDEX IF NOT EXISTS idx_print_jobs_status_id "
            "ON print_jobs(status, id)"
        )
        self._db.commit()
        self.prune_terminal()

    def close(self) -> None:
        self._db.close()

    def queue_depth(self) -> int:
        row = self._db.execute(
            "SELECT COUNT(*) FROM print_jobs WHERE status='pending'"
        ).fetchone()
        return int(row[0]) if row else 0

    def create(self, created_at: str, event_code: str) -> int:
        cursor = self._db.execute(
            "INSERT INTO print_jobs(created_at, event_code) VALUES (?, ?)",
            (created_at, event_code),
        )
        return int(cursor.lastrowid)

    def set_payload(self, job_id: int, payload: bytes) -> None:
        self._db.execute(
            "UPDATE print_jobs SET payload=? WHERE id=?",
            (payload, job_id),
        )
        self._db.commit()

    def delete(self, job_id: int) -> None:
        self._db.execute("DELETE FROM print_jobs WHERE id=?", (job_id,))
        self._db.commit()

    def next_pending(self) -> PrintJob | None:
        row = self._db.execute(
            "SELECT id, payload FROM print_jobs "
            "WHERE status='pending' ORDER BY id LIMIT 1"
        ).fetchone()
        if row is None:
            return None
        return PrintJob(job_id=int(row[0]), payload=bytes(row[1]))

    def record_attempt_error(self, job_id: int, error: str) -> None:
        self._db.execute(
            "UPDATE print_jobs SET attempts=attempts+1, last_error=? WHERE id=?",
            (error[:500], job_id),
        )
        self._db.commit()

    def mark_complete(self, job_id: int) -> str:
        completed_at = datetime.now(timezone.utc).isoformat()
        self._db.execute(
            "UPDATE print_jobs SET status='complete', attempts=attempts+1, "
            "last_error='', completed_at=? WHERE id=?",
            (completed_at, job_id),
        )
        self._db.commit()
        self.prune_terminal()
        return completed_at

    def mark_uncertain(self, job_id: int, error: str) -> None:
        self._mark(job_id, "uncertain", error)

    def mark_failed(self, job_id: int, error: str) -> None:
        self._mark(job_id, "failed", error)

    def _mark(self, job_id: int, status: str, error: str) -> None:
        self._db.execute(
            "UPDATE print_jobs SET status=?, attempts=attempts+1, last_error=? WHERE id=?",
            (status, error[:500], job_id),
        )
        self._db.commit()
        self.prune_terminal()

    def prune_terminal(self, batch_size: int = 500) -> int:
        """Bound terminal spool history without ever deleting pending work."""
        batch = max(1, min(5000, int(batch_size)))
        row = self._db.execute(
            "SELECT COUNT(*) FROM print_jobs WHERE status IN ('complete','failed','uncertain')"
        ).fetchone()
        excess = int(row[0]) - self.max_terminal_rows if row else 0
        if excess <= 0:
            return 0
        cursor = self._db.execute(
            "DELETE FROM print_jobs WHERE id IN ("
            "SELECT id FROM print_jobs "
            "WHERE status IN ('complete','failed','uncertain') "
            "ORDER BY id LIMIT ?"
            ")",
            (min(excess, batch),),
        )
        self._db.commit()
        return int(cursor.rowcount)
