from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sqlite3
from typing import Any

from .protocol import SystemEvent


@dataclass(frozen=True)
class EventJournalStats:
    count: int
    last_dump_at: str
    last_dump_seen: int
    last_dump_inserted: int


class EventStore:
    """Persistent VISTA event journal backed by SQLite.

    The panel event payload only has minute resolution. Identical payloads can
    legitimately occur more than once inside a minute, so rows are keyed by a
    deterministic fingerprint plus an occurrence number. Historical LD dumps
    assign stable occurrences in dump order; live notifications append the next
    occurrence for that fingerprint.
    """

    def __init__(self, path: str) -> None:
        self.path = path
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=5)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("PRAGMA synchronous=NORMAL")
        return db

    def _initialize(self) -> None:
        with self._connect() as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    fingerprint TEXT NOT NULL,
                    occurrence INTEGER NOT NULL,
                    event_code TEXT NOT NULL,
                    description TEXT NOT NULL,
                    zone INTEGER NOT NULL,
                    user_number INTEGER NOT NULL,
                    partition_number INTEGER NOT NULL,
                    panel_timestamp TEXT,
                    panel_year INTEGER NOT NULL,
                    panel_month INTEGER NOT NULL,
                    panel_day INTEGER NOT NULL,
                    panel_hour INTEGER NOT NULL,
                    panel_minute INTEGER NOT NULL,
                    descriptor TEXT NOT NULL DEFAULT '',
                    seen_live INTEGER NOT NULL DEFAULT 0,
                    seen_history INTEGER NOT NULL DEFAULT 0,
                    first_received_at TEXT NOT NULL,
                    last_received_at TEXT NOT NULL,
                    UNIQUE(fingerprint, occurrence)
                );
                CREATE INDEX IF NOT EXISTS idx_events_panel_timestamp
                    ON events(panel_timestamp DESC, id DESC);
                CREATE INDEX IF NOT EXISTS idx_events_partition
                    ON events(partition_number, panel_timestamp DESC, id DESC);
                CREATE INDEX IF NOT EXISTS idx_events_code
                    ON events(event_code, panel_timestamp DESC, id DESC);
                CREATE INDEX IF NOT EXISTS idx_events_fingerprint
                    ON events(fingerprint, occurrence);

                CREATE TABLE IF NOT EXISTS metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                """
            )
            db.execute("PRAGMA user_version=1")

    @staticmethod
    def fingerprint(event: SystemEvent) -> str:
        return "|".join(
            (
                event.code,
                f"{event.zone:03d}",
                f"{event.user:03d}",
                str(event.partition),
                f"{event.year:02d}",
                f"{event.month:02d}",
                f"{event.day:02d}",
                f"{event.hour:02d}",
                f"{event.minute:02d}",
            )
        )

    def record(
        self,
        event: SystemEvent,
        *,
        source: str,
        received_at: str,
        descriptor: str = "",
        occurrence: int | None = None,
    ) -> bool:
        if source not in {"live", "history"}:
            raise ValueError("event source must be live or history")
        if occurrence is not None and occurrence < 1:
            raise ValueError("event occurrence must be >= 1")

        fingerprint = self.fingerprint(event)
        with self._connect() as db:
            if occurrence is None:
                row = db.execute(
                    "SELECT COALESCE(MAX(occurrence), 0) + 1 FROM events WHERE fingerprint = ?",
                    (fingerprint,),
                ).fetchone()
                occurrence = int(row[0])

            existed = db.execute(
                "SELECT 1 FROM events WHERE fingerprint = ? AND occurrence = ?",
                (fingerprint, occurrence),
            ).fetchone() is not None
            db.execute(
                """
                INSERT INTO events (
                    fingerprint, occurrence, event_code, description, zone,
                    user_number, partition_number, panel_timestamp, panel_year,
                    panel_month, panel_day, panel_hour, panel_minute, descriptor,
                    seen_live, seen_history, first_received_at, last_received_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(fingerprint, occurrence) DO UPDATE SET
                    description = excluded.description,
                    descriptor = CASE
                        WHEN excluded.descriptor <> '' THEN excluded.descriptor
                        ELSE events.descriptor
                    END,
                    seen_live = MAX(events.seen_live, excluded.seen_live),
                    seen_history = MAX(events.seen_history, excluded.seen_history),
                    last_received_at = excluded.last_received_at
                """,
                (
                    fingerprint,
                    occurrence,
                    event.code,
                    event.description,
                    event.zone,
                    event.user,
                    event.partition,
                    event.panel_timestamp,
                    2000 + event.year,
                    event.month,
                    event.day,
                    event.hour,
                    event.minute,
                    descriptor,
                    1 if source == "live" else 0,
                    1 if source == "history" else 0,
                    received_at,
                    received_at,
                ),
            )
            return not existed

    def update_descriptor(self, zone: int, descriptor: str) -> int:
        if not descriptor:
            return 0
        with self._connect() as db:
            cursor = db.execute(
                "UPDATE events SET descriptor = ? WHERE zone = ? AND descriptor <> ?",
                (descriptor, zone, descriptor),
            )
            return int(cursor.rowcount)

    def finish_history_dump(
        self,
        *,
        completed_at: str,
        seen: int,
        inserted: int,
    ) -> None:
        with self._connect() as db:
            for key, value in (
                ("last_dump_at", completed_at),
                ("last_dump_seen", str(seen)),
                ("last_dump_inserted", str(inserted)),
            ):
                db.execute(
                    "INSERT INTO metadata(key, value) VALUES(?, ?) "
                    "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                    (key, value),
                )

    def stats(self) -> EventJournalStats:
        with self._connect() as db:
            count = int(db.execute("SELECT COUNT(*) FROM events").fetchone()[0])
            metadata = {
                row["key"]: row["value"]
                for row in db.execute(
                    "SELECT key, value FROM metadata WHERE key IN "
                    "('last_dump_at','last_dump_seen','last_dump_inserted')"
                )
            }
        return EventJournalStats(
            count=count,
            last_dump_at=metadata.get("last_dump_at", ""),
            last_dump_seen=int(metadata.get("last_dump_seen", "0") or 0),
            last_dump_inserted=int(metadata.get("last_dump_inserted", "0") or 0),
        )

    def recent(self, limit: int = 20) -> list[dict[str, Any]]:
        limit = max(1, min(100, int(limit)))
        with self._connect() as db:
            rows = db.execute(
                """
                SELECT id, occurrence, event_code, description, zone,
                       user_number, partition_number, panel_timestamp, descriptor,
                       seen_live, seen_history, last_received_at
                FROM events
                ORDER BY COALESCE(panel_timestamp, last_received_at) DESC, id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

        events: list[dict[str, Any]] = []
        for row in rows:
            seen_live = bool(row["seen_live"])
            seen_history = bool(row["seen_history"])
            source = "both" if seen_live and seen_history else "live" if seen_live else "history"
            events.append(
                {
                    "id": row["id"],
                    "occurrence": row["occurrence"],
                    "event_code": row["event_code"],
                    "description": row["description"],
                    "zone": row["zone"],
                    "user": row["user_number"],
                    "partition": row["partition_number"],
                    "panel_timestamp": row["panel_timestamp"],
                    "descriptor": row["descriptor"],
                    "source": source,
                    "received_at": row["last_received_at"],
                }
            )
        return events
