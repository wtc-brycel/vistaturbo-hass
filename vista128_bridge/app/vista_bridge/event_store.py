from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sqlite3
from typing import Any

from .protocol import SystemEvent


AUDIT_TERMINAL_STATUSES = frozenset(
    {
        "accepted",
        "confirmed",
        "failed",
        "no_ready_ack",
        "verification_mismatch",
        "stale_session",
        "connection_lost_after_send",
        "request_expired",
        "transaction_unavailable",
        "control_queue_full",
        "control_queue_requeue_failed",
        "automation_interface_unavailable",
        "control_disabled",
        "command_control_disabled",
        "keypad_control_disabled",
        "native_alarm_control_disabled",
        "panel_offline",
        "panel_session_reset",
        "keypad_sequence_too_long",
        "timeout",
        "unknown",
        "unverified",
        "rejected",
    }
)


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

    def __init__(
        self,
        path: str,
        *,
        max_age_days: int = 90,
        max_rows: int = 10000,
    ) -> None:
        self.path = path
        self.max_age_days = max(1, int(max_age_days))
        self.max_rows = max(1, int(max_rows))
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._initialize()
        # Enforce new limits against an existing database without making the
        # first live event pay for all historical cleanup at once.
        self.prune()

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=5)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("PRAGMA synchronous=NORMAL")
        return db

    def _initialize(self) -> None:
        with closing(self._connect()) as db, db:
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

                CREATE TABLE IF NOT EXISTS keypad_interactions (
                    interaction_id TEXT PRIMARY KEY,
                    started_at TEXT NOT NULL,
                    last_seen_at TEXT NOT NULL,
                    completed_at TEXT NOT NULL DEFAULT '',
                    actor_id TEXT NOT NULL DEFAULT '',
                    actor_name TEXT NOT NULL DEFAULT '',
                    partition_number INTEGER NOT NULL,
                    source TEXT NOT NULL,
                    action TEXT NOT NULL,
                    command_sequence TEXT NOT NULL DEFAULT '',
                    operands_json TEXT NOT NULL DEFAULT '{}',
                    last_request_id TEXT NOT NULL DEFAULT '',
                    command_type TEXT NOT NULL DEFAULT '',
                    code TEXT NOT NULL DEFAULT '',
                    execution_mechanism TEXT NOT NULL DEFAULT '',
                    confidence TEXT NOT NULL DEFAULT '',
                    verification TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL,
                    ok INTEGER NOT NULL DEFAULT 0
                );
                CREATE INDEX IF NOT EXISTS idx_keypad_interactions_last_seen
                    ON keypad_interactions(last_seen_at DESC);

                CREATE TABLE IF NOT EXISTS metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                """
            )
            columns = {
                row[1]
                for row in db.execute("PRAGMA table_info(keypad_interactions)")
            }
            if "command_sequence" not in columns:
                db.execute(
                    "ALTER TABLE keypad_interactions ADD COLUMN "
                    "command_sequence TEXT NOT NULL DEFAULT ''"
                )
            if "operands_json" not in columns:
                db.execute(
                    "ALTER TABLE keypad_interactions ADD COLUMN "
                    "operands_json TEXT NOT NULL DEFAULT '{}'"
                )
            if "last_request_id" not in columns:
                db.execute(
                    "ALTER TABLE keypad_interactions ADD COLUMN "
                    "last_request_id TEXT NOT NULL DEFAULT ''"
                )
            for name, definition in (
                ("command_type", "TEXT NOT NULL DEFAULT ''"),
                ("code", "TEXT NOT NULL DEFAULT ''"),
                ("execution_mechanism", "TEXT NOT NULL DEFAULT ''"),
                ("confidence", "TEXT NOT NULL DEFAULT ''"),
                ("verification", "TEXT NOT NULL DEFAULT ''"),
            ):
                if name not in columns:
                    db.execute(
                        f"ALTER TABLE keypad_interactions ADD COLUMN {name} {definition}"
                    )
            db.execute("PRAGMA user_version=3")

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
        with closing(self._connect()) as db, db:
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
            inserted = not existed

        # Keep pruning bounded. A single event must never require deleting an
        # unbounded amount of history while the panel event path is active.
        self.prune()
        return inserted

    def prune(
        self,
        *,
        now: datetime | None = None,
        max_age_days: int | None = None,
        max_rows: int | None = None,
        batch_size: int = 500,
    ) -> int:
        """Delete at most one bounded batch of expired/oldest rows."""
        age_days = self.max_age_days if max_age_days is None else max(1, int(max_age_days))
        row_limit = self.max_rows if max_rows is None else max(1, int(max_rows))
        batch = max(1, min(5000, int(batch_size)))
        reference = now or datetime.now(timezone.utc)
        cutoff = (reference - timedelta(days=age_days)).isoformat()

        with closing(self._connect()) as db, db:
            deleted = 0
            expired = db.execute(
                "SELECT id FROM events WHERE last_received_at < ? "
                "ORDER BY id LIMIT ?",
                (cutoff, batch),
            ).fetchall()
            if expired:
                ids = [int(row[0]) for row in expired]
                placeholders = ",".join("?" for _ in ids)
                cursor = db.execute(
                    f"DELETE FROM events WHERE id IN ({placeholders})", ids
                )
                deleted += int(cursor.rowcount)

            remaining = db.execute("SELECT COUNT(*) FROM events").fetchone()
            count = int(remaining[0]) if remaining else 0
            excess = count - row_limit
            if excess > 0 and deleted < batch:
                limit = min(excess, batch - deleted)
                cursor = db.execute(
                    "DELETE FROM events WHERE id IN ("
                    "SELECT id FROM events ORDER BY id LIMIT ?"
                    ")",
                    (limit,),
                )
                deleted += int(cursor.rowcount)

            audit_expired = db.execute(
                "SELECT interaction_id FROM keypad_interactions "
                "WHERE last_seen_at < ? ORDER BY last_seen_at LIMIT ?",
                (cutoff, batch),
            ).fetchall()
            if audit_expired:
                ids = [str(row[0]) for row in audit_expired]
                placeholders = ",".join("?" for _ in ids)
                cursor = db.execute(
                    "DELETE FROM keypad_interactions "
                    f"WHERE interaction_id IN ({placeholders})",
                    ids,
                )
                deleted += int(cursor.rowcount)

            audit_count = db.execute(
                "SELECT COUNT(*) FROM keypad_interactions"
            ).fetchone()
            audit_excess = int(audit_count[0]) - row_limit if audit_count else 0
            if audit_excess > 0:
                cursor = db.execute(
                    "DELETE FROM keypad_interactions WHERE interaction_id IN ("
                    "SELECT interaction_id FROM keypad_interactions "
                    "ORDER BY last_seen_at LIMIT ?"
                    ")",
                    (min(audit_excess, batch),),
                )
                deleted += int(cursor.rowcount)
            return deleted

    def record_keypad_interaction(
        self,
        *,
        interaction_id: str,
        observed_at: str,
        started_at: str | None = None,
        actor_id: str = "",
        actor_name: str = "",
        partition: int,
        source: str,
        action: str,
        command_sequence: str = "",
        operands: dict[str, Any] | None = None,
        status: str,
        ok: bool,
        request_id: str | int = "",
        command_type: str = "",
        code: str = "",
        execution_mechanism: str = "",
        confidence: str = "",
        verification: str = "",
        logical_command_sequence: str = "",
    ) -> None:
        """Upsert one bounded audit row for one logical interaction.

        The sequence is intentionally stored for the configured administrator:
        panel PINs and keypad commands are part of this local audit record.
        MQTT envelopes and individual keypresses are not stored.
        """
        interaction_id = self._audit_text(interaction_id, 96)
        if not interaction_id:
            return
        observed_at = self._audit_text(observed_at, 64)
        started_at = self._audit_text(started_at or observed_at, 64) or observed_at
        actor_id = self._audit_text(actor_id, 128)
        actor_name = self._audit_text(actor_name, 128)
        source = self._audit_text(source, 32) or "mqtt"
        action = self._audit_text(action, 64) or "keypad_sequence"
        command_sequence = self._audit_text(command_sequence, 256)
        logical_command_sequence = self._audit_text(logical_command_sequence, 256)
        if logical_command_sequence:
            command_sequence = logical_command_sequence
        operands_json = self._audit_operands(operands)
        request_id = self._audit_text(request_id, 96)
        command_type = self._audit_text(command_type, 64)
        code = self._audit_text(code, 4)
        if code and (len(code) != 4 or not code.isdigit()):
            code = ""
        execution_mechanism = self._audit_text(execution_mechanism, 32)
        confidence = self._audit_text(confidence, 16)
        verification = self._audit_text(verification, 64)
        status = self._audit_text(status, 64) or "unknown"
        partition = max(0, min(8, int(partition)))
        with closing(self._connect()) as db, db:
            existing = db.execute(
                "SELECT command_sequence, action, last_request_id, command_type, "
                "code, execution_mechanism, confidence, verification "
                "FROM keypad_interactions "
                "WHERE interaction_id = ?",
                (interaction_id,),
            ).fetchone()
            same_request = bool(
                existing is not None and request_id and existing[2] == request_id
            )
            if same_request and existing[0] and not logical_command_sequence:
                # A queued -> terminal update for the same segment must keep
                # the already accumulated logical sequence intact.
                command_sequence = existing[0]
            if (
                existing is not None
                and existing[0]
                and command_sequence
                and existing[1] == action == "keypad_sequence"
                and not same_request
                and (request_id or existing[0] != command_sequence)
            ):
                # The card may flush a sequence in short logical segments
                # while retaining one interaction ID. Preserve those segments
                # in one row, while an identical terminal update remains an
                # idempotent upsert.
                combined = f"{existing[0]}{command_sequence}"
                command_sequence = combined[:256]
            db.execute(
                """
                INSERT INTO keypad_interactions (
                    interaction_id, started_at, last_seen_at, completed_at,
                    actor_id, actor_name, partition_number, source, action,
                    command_sequence, operands_json, last_request_id,
                    command_type, code, execution_mechanism, confidence,
                    verification, status, ok
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(interaction_id) DO UPDATE SET
                    last_seen_at = excluded.last_seen_at,
                    started_at = CASE
                        WHEN keypad_interactions.started_at = ''
                        THEN excluded.started_at
                        ELSE keypad_interactions.started_at
                    END,
                    completed_at = CASE
                        WHEN excluded.status IN (
                            'accepted','confirmed','failed','no_ready_ack',
                            'verification_mismatch','stale_session',
                            'connection_lost_after_send','request_expired',
                            'transaction_unavailable','control_queue_full',
                            'control_queue_requeue_failed',
                            'automation_interface_unavailable','control_disabled',
                            'command_control_disabled','keypad_control_disabled',
                            'native_alarm_control_disabled','panel_offline',
                            'panel_session_reset','keypad_sequence_too_long',
                            'timeout','unknown','unverified',
                            'rejected'
                        )
                        THEN excluded.last_seen_at
                        ELSE keypad_interactions.completed_at
                    END,
                    actor_id = CASE
                        WHEN excluded.actor_id <> '' THEN excluded.actor_id
                        ELSE keypad_interactions.actor_id
                    END,
                    actor_name = CASE
                        WHEN excluded.actor_name <> '' THEN excluded.actor_name
                        ELSE keypad_interactions.actor_name
                    END,
                    partition_number = excluded.partition_number,
                    source = excluded.source,
                    action = excluded.action,
                    command_sequence = CASE
                        WHEN excluded.command_sequence <> ''
                        THEN excluded.command_sequence
                        ELSE keypad_interactions.command_sequence
                    END,
                    operands_json = CASE
                        WHEN excluded.operands_json <> '{}'
                        THEN excluded.operands_json
                        ELSE keypad_interactions.operands_json
                    END,
                    last_request_id = CASE
                        WHEN excluded.last_request_id <> ''
                        THEN excluded.last_request_id
                        ELSE keypad_interactions.last_request_id
                    END,
                    command_type = CASE
                        WHEN excluded.command_type <> '' THEN excluded.command_type
                        ELSE keypad_interactions.command_type
                    END,
                    code = CASE
                        WHEN excluded.code <> '' THEN excluded.code
                        ELSE keypad_interactions.code
                    END,
                    execution_mechanism = CASE
                        WHEN excluded.execution_mechanism <> ''
                        THEN excluded.execution_mechanism
                        ELSE keypad_interactions.execution_mechanism
                    END,
                    confidence = CASE
                        WHEN excluded.confidence <> '' THEN excluded.confidence
                        ELSE keypad_interactions.confidence
                    END,
                    verification = CASE
                        WHEN excluded.verification <> '' THEN excluded.verification
                        ELSE keypad_interactions.verification
                    END,
                    status = excluded.status,
                    ok = excluded.ok
                """,
                (
                    interaction_id,
                    started_at,
                    observed_at,
                    observed_at if status in AUDIT_TERMINAL_STATUSES else "",
                    actor_id,
                    actor_name,
                    partition,
                    source,
                    action,
                    command_sequence,
                    operands_json,
                    request_id,
                    command_type,
                    code,
                    execution_mechanism,
                    confidence,
                    verification,
                    status,
                    1 if ok else 0,
                ),
            )
        self.prune()

    @staticmethod
    def _audit_text(value: str, limit: int) -> str:
        return "".join(character for character in str(value) if character.isprintable())[:limit]

    @classmethod
    def _audit_operands(cls, operands: dict[str, Any] | None) -> str:
        if not isinstance(operands, dict):
            return "{}"
        normalized = dict(operands)
        if "zone" in normalized:
            zone = normalized["zone"]
            if isinstance(zone, int) and 0 <= zone <= 999:
                normalized["zone"] = f"{zone:03d}"
            elif isinstance(zone, str) and zone.isdigit() and len(zone) <= 3:
                normalized["zone"] = f"{int(zone):03d}"
            else:
                normalized.pop("zone")
        if "zones" in normalized:
            zones = normalized["zones"]
            if isinstance(zones, (list, tuple)) and zones:
                normalized_zones = []
                for zone in zones:
                    if isinstance(zone, bool):
                        normalized_zones = []
                        break
                    if isinstance(zone, int) and 1 <= zone <= 999:
                        normalized_zones.append(f"{zone:03d}")
                    elif isinstance(zone, str) and zone.isdigit() and len(zone) == 3 and int(zone) > 0:
                        normalized_zones.append(zone)
                    else:
                        normalized_zones = []
                        break
                if normalized_zones and len(set(normalized_zones)) == len(normalized_zones):
                    normalized["zones"] = normalized_zones
                else:
                    normalized.pop("zones")
        try:
            encoded = json.dumps(
                normalized,
                ensure_ascii=True,
                separators=(",", ":"),
                sort_keys=True,
            )
        except (TypeError, ValueError):
            return "{}"
        return encoded if len(encoded) <= 512 else "{}"

    def update_descriptor(self, zone: int, descriptor: str) -> int:
        if not descriptor:
            return 0
        with closing(self._connect()) as db, db:
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
        with closing(self._connect()) as db, db:
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
        with closing(self._connect()) as db, db:
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
        with closing(self._connect()) as db, db:
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
