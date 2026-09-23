from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
import logging
from pathlib import Path
import queue
import re
import sqlite3
import threading
import time
from typing import Any
import uuid


LOG = logging.getLogger(__name__)

DIAGNOSTIC_SEVERITIES = frozenset({"debug", "info", "warning", "error", "critical"})
DIAGNOSTIC_CATEGORIES = frozenset(
    {
        "system",
        "panel_transport",
        "protocol",
        "synchronization",
        "ha_transport",
        "state_delivery",
        "control",
        "persistence",
        "printer",
        "management",
    }
)
EVENT_TYPE_RE = re.compile(r"^[a-z][a-z0-9_]*(?:\.[a-z0-9_]+)+$")

SENSITIVE_DETAIL_KEYS = frozenset(
    {
        "password",
        "passwd",
        "pin",
        "code",
        "remote_code",
        "installer_code",
        "master_code",
        "credential",
        "credentials",
        "secret",
        "token",
        "access_token",
        "refresh_token",
        "authorization",
        "api_key",
        "private_key",
        "client_key",
        "command_sequence",
        "logical_command_sequence",
        "raw_payload",
        "payload",
    }
)
SENSITIVE_DETAIL_SUFFIXES = (
    "_password",
    "_passwd",
    "_pin",
    "_credential",
    "_credentials",
    "_secret",
    "_token",
    "_private_key",
    "_client_key",
)

MAX_DETAIL_DEPTH = 4
MAX_DETAIL_KEYS = 32
MAX_DETAIL_ITEMS = 32
MAX_DETAIL_STRING = 512
MAX_DETAILS_JSON = 8192
WRITE_QUEUE_MAX = 2048
WRITE_BATCH_MAX = 50


class DiagnosticEvents:
    APP_STARTED = "system.app_started"
    APP_STOPPING = "system.app_stopping"
    APP_STOPPED = "system.app_stopped"
    HEALTH_SNAPSHOT = "system.health_snapshot"
    TASK_FAILED = "system.task_failed"
    QUEUE_SATURATED = "system.queue_saturated"

    PANEL_CONNECTED = "panel_transport.connected"
    PANEL_CONNECT_FAILED = "panel_transport.connect_failed"
    PANEL_CONNECTION_LOST = "panel_transport.connection_lost"
    PANEL_RECONNECT_SCHEDULED = "panel_transport.reconnect_scheduled"

    INVALID_FRAME = "protocol.invalid_frame"

    SYNC_STARTED = "synchronization.started"
    SYNC_COMPLETED = "synchronization.completed"
    SYNC_FAILED = "synchronization.failed"
    SYNC_SESSION_TAINTED = "synchronization.session_tainted"

    HA_CONNECTED = "ha_transport.connected"
    HA_DISCONNECTED = "ha_transport.disconnected"
    HA_CONNECTION_REJECTED = "ha_transport.connection_rejected"
    HA_WATCHDOG_TRIGGERED = "ha_transport.watchdog_triggered"
    HA_RECOVERY_STARTED = "ha_transport.recovery_started"
    HA_CLIENT_REPLACED = "ha_transport.client_replaced"
    HA_RECOVERY_FAILED = "ha_transport.recovery_failed"

    STATE_REPLAY_STARTED = "state_delivery.replay_started"
    STATE_REPLAY_COMPLETED = "state_delivery.replay_completed"
    STATE_REPLAY_FAILED = "state_delivery.replay_failed"

    CONTROL_SAFETY_INTERLOCK_BLOCKED = "control.safety_interlock_blocked"


DIAGNOSTIC_EVENT_TYPES = frozenset(
    value
    for name, value in vars(DiagnosticEvents).items()
    if name.isupper() and isinstance(value, str)
)


@dataclass(frozen=True)
class DiagnosticRecord:
    id: int
    event_id: str
    occurred_at: str
    severity: str
    category: str
    component: str
    event_type: str
    message: str
    boot_id: str
    panel_session_id: str
    transport_session_id: str
    correlation_id: str
    details: dict[str, Any]


@dataclass(frozen=True)
class DiagnosticStats:
    count: int
    oldest_at: str
    newest_at: str
    write_errors: int
    dropped_events: int = 0
    pending_writes: int = 0


@dataclass(frozen=True)
class _PendingDiagnostic:
    event_id: str
    occurred_at: str
    severity: str
    category: str
    component: str
    event_type: str
    message: str
    boot_id: str
    panel_session_id: str
    transport_session_id: str
    correlation_id: str
    details_json: str


class DiagnosticJournal:
    """Bounded operational diagnostic journal.

    This is intentionally not a second general-purpose logging pipeline.
    Callers record lifecycle transitions, failures, recoveries, and sparse
    health snapshots. Routine protocol traffic and successful state updates
    remain in the normal application log.
    """

    def __init__(
        self,
        path: str,
        *,
        max_age_days: int = 30,
        max_rows: int = 25000,
    ) -> None:
        self.path = path
        self.max_age_days = max(1, int(max_age_days))
        self.max_rows = max(100, int(max_rows))
        self.boot_id = self.new_id("boot")
        self.available = True
        self.write_errors = 0
        self.dropped_events = 0
        self._context_lock = threading.RLock()
        self._counter_lock = threading.Lock()
        self._panel_session_id = ""
        self._transport_session_id = ""
        self._write_queue: queue.Queue[_PendingDiagnostic] = queue.Queue(
            maxsize=WRITE_QUEUE_MAX
        )
        self._writer_stop = threading.Event()
        self._writer_thread: threading.Thread | None = None

        try:
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            self._initialize()
            self.prune()
            self._writer_thread = threading.Thread(
                target=self._writer_loop,
                name="diagnostic-journal-writer",
                daemon=True,
            )
            self._writer_thread.start()
        except Exception:
            self.available = False
            LOG.exception("Diagnostic journal unavailable; continuing without persistence")

    @staticmethod
    def new_id(prefix: str) -> str:
        normalized = re.sub(r"[^a-z0-9_]", "", str(prefix).lower())[:16] or "id"
        return f"{normalized}_{uuid.uuid4().hex[:16]}"

    @property
    def panel_session_id(self) -> str:
        with self._context_lock:
            return self._panel_session_id

    @property
    def transport_session_id(self) -> str:
        with self._context_lock:
            return self._transport_session_id

    def set_panel_session(self, session_id: str) -> None:
        with self._context_lock:
            self._panel_session_id = self._clean_text(session_id, 64)

    def clear_panel_session(self) -> None:
        self.set_panel_session("")

    def set_transport_session(self, session_id: str) -> None:
        with self._context_lock:
            self._transport_session_id = self._clean_text(session_id, 64)

    def clear_transport_session(self) -> None:
        self.set_transport_session("")

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
                CREATE TABLE IF NOT EXISTS diagnostic_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id TEXT NOT NULL UNIQUE,
                    occurred_at TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    category TEXT NOT NULL,
                    component TEXT NOT NULL DEFAULT '',
                    event_type TEXT NOT NULL,
                    message TEXT NOT NULL DEFAULT '',
                    boot_id TEXT NOT NULL,
                    panel_session_id TEXT NOT NULL DEFAULT '',
                    transport_session_id TEXT NOT NULL DEFAULT '',
                    correlation_id TEXT NOT NULL DEFAULT '',
                    details_json TEXT NOT NULL DEFAULT '{}'
                );

                CREATE INDEX IF NOT EXISTS idx_diagnostic_events_time
                    ON diagnostic_events(occurred_at DESC, id DESC);
                CREATE INDEX IF NOT EXISTS idx_diagnostic_events_category
                    ON diagnostic_events(category, occurred_at DESC, id DESC);
                CREATE INDEX IF NOT EXISTS idx_diagnostic_events_severity
                    ON diagnostic_events(severity, occurred_at DESC, id DESC);
                CREATE INDEX IF NOT EXISTS idx_diagnostic_events_type
                    ON diagnostic_events(event_type, occurred_at DESC, id DESC);
                CREATE INDEX IF NOT EXISTS idx_diagnostic_events_correlation
                    ON diagnostic_events(correlation_id, occurred_at DESC, id DESC);
                CREATE INDEX IF NOT EXISTS idx_diagnostic_events_boot
                    ON diagnostic_events(boot_id, occurred_at DESC, id DESC);
                CREATE INDEX IF NOT EXISTS idx_diagnostic_events_panel_session
                    ON diagnostic_events(panel_session_id, occurred_at DESC, id DESC);
                CREATE INDEX IF NOT EXISTS idx_diagnostic_events_transport_session
                    ON diagnostic_events(transport_session_id, occurred_at DESC, id DESC);
                """
            )
            db.execute("PRAGMA user_version=1")

    def record(
        self,
        event_type: str,
        *,
        severity: str = "info",
        component: str = "",
        message: str = "",
        details: dict[str, Any] | None = None,
        correlation_id: str = "",
        occurred_at: str | None = None,
        panel_session_id: str | None = None,
        transport_session_id: str | None = None,
    ) -> str | None:
        severity = str(severity).lower().strip()
        event_type = str(event_type).lower().strip()
        if severity not in DIAGNOSTIC_SEVERITIES:
            raise ValueError(f"unsupported diagnostic severity: {severity}")
        if not EVENT_TYPE_RE.fullmatch(event_type):
            raise ValueError(f"invalid diagnostic event type: {event_type}")
        if event_type not in DIAGNOSTIC_EVENT_TYPES:
            raise ValueError(f"unsupported diagnostic event type: {event_type}")
        category = event_type.split(".", 1)[0]
        if category not in DIAGNOSTIC_CATEGORIES:
            raise ValueError(f"unsupported diagnostic category: {category}")

        event_id = self.new_id("diag")
        when = occurred_at or datetime.now(timezone.utc).isoformat()
        with self._context_lock:
            panel_context = (
                self._panel_session_id
                if panel_session_id is None
                else self._clean_text(panel_session_id, 64)
            )
            transport_context = (
                self._transport_session_id
                if transport_session_id is None
                else self._clean_text(transport_session_id, 64)
            )

        if not self.available or self._writer_stop.is_set():
            return None

        pending = _PendingDiagnostic(
            event_id=event_id,
            occurred_at=self._clean_text(when, 64),
            severity=severity,
            category=category,
            component=self._clean_text(component, 64),
            event_type=event_type,
            message=self._clean_text(message, 512),
            boot_id=self.boot_id,
            panel_session_id=panel_context,
            transport_session_id=transport_context,
            correlation_id=self._clean_text(correlation_id, 96),
            details_json=self._encode_details(details),
        )
        try:
            self._write_queue.put_nowait(pending)
            return event_id
        except queue.Full:
            with self._counter_lock:
                self.dropped_events += 1
                dropped = self.dropped_events
            if dropped == 1 or dropped % 100 == 0:
                LOG.warning(
                    "Diagnostic journal write queue full; dropped %d event(s)",
                    dropped,
                )
            return None

    def recent(
        self,
        *,
        limit: int = 200,
        severity: str | None = None,
        category: str | None = None,
        component: str | None = None,
        event_type: str | None = None,
        correlation_id: str | None = None,
        boot_id: str | None = None,
        since: str | None = None,
        until: str | None = None,
        order: str = "newest",
    ) -> list[DiagnosticRecord]:
        if not self.available:
            return []
        limit = max(1, min(1000, int(limit)))
        if severity is not None:
            severity = severity.lower().strip()
            if severity not in DIAGNOSTIC_SEVERITIES:
                raise ValueError("invalid diagnostic severity filter")
        if category is not None:
            category = category.lower().strip()
            if category not in DIAGNOSTIC_CATEGORIES:
                raise ValueError("invalid diagnostic category filter")
        if event_type is not None:
            event_type = event_type.lower().strip()
            if (
                not EVENT_TYPE_RE.fullmatch(event_type)
                or event_type not in DIAGNOSTIC_EVENT_TYPES
            ):
                raise ValueError("invalid diagnostic event type filter")
        if order not in {"newest", "oldest"}:
            raise ValueError("diagnostic order must be newest or oldest")

        clauses: list[str] = []
        values: list[Any] = []
        for column, value in (
            ("severity", severity),
            ("category", category),
            ("component", component),
            ("event_type", event_type),
            ("correlation_id", correlation_id),
            ("boot_id", boot_id),
        ):
            if value is None:
                continue
            clauses.append(f"{column} = ?")
            values.append(self._clean_text(value, 96))
        if since:
            clauses.append("occurred_at >= ?")
            values.append(self._clean_text(since, 64))
        if until:
            clauses.append("occurred_at <= ?")
            values.append(self._clean_text(until, 64))

        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        direction = "DESC" if order == "newest" else "ASC"
        query = (
            "SELECT * FROM diagnostic_events "
            f"{where} ORDER BY occurred_at {direction}, id {direction} LIMIT ?"
        )
        values.append(limit)

        try:
            with closing(self._connect()) as db:
                rows = db.execute(query, values).fetchall()
        except sqlite3.Error:
            LOG.exception("Could not read diagnostic journal")
            return []
        return [self._record_from_row(row) for row in rows]

    def stats(self) -> DiagnosticStats:
        if not self.available:
            return DiagnosticStats(
                0,
                "",
                "",
                self.write_errors,
                self.dropped_events,
                self._write_queue.qsize(),
            )
        try:
            with closing(self._connect()) as db:
                row = db.execute(
                    "SELECT COUNT(*), MIN(occurred_at), MAX(occurred_at) "
                    "FROM diagnostic_events"
                ).fetchone()
            return DiagnosticStats(
                count=int(row[0]) if row else 0,
                oldest_at=str(row[1] or "") if row else "",
                newest_at=str(row[2] or "") if row else "",
                write_errors=self.write_errors,
                dropped_events=self.dropped_events,
                pending_writes=self._write_queue.qsize(),
            )
        except sqlite3.Error:
            LOG.exception("Could not read diagnostic journal stats")
            return DiagnosticStats(
                0,
                "",
                "",
                self.write_errors,
                self.dropped_events,
                self._write_queue.qsize(),
            )

    def flush(self, timeout: float = 2.0) -> bool:
        """Wait briefly for already-queued diagnostic writes to reach SQLite."""
        if not self.available:
            return False
        deadline = time.monotonic() + max(0.0, float(timeout))
        while self._write_queue.unfinished_tasks:
            if time.monotonic() >= deadline:
                return False
            time.sleep(0.01)
        return True

    def close(self, timeout: float = 2.0) -> bool:
        """Flush queued events and stop the writer without blocking transport threads."""
        if self._writer_stop.is_set():
            return self._write_queue.unfinished_tasks == 0
        self._writer_stop.set()
        flushed = self.flush(timeout=timeout)
        thread = self._writer_thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=max(0.0, float(timeout)))
        return flushed and (thread is None or not thread.is_alive())

    def _writer_loop(self) -> None:
        while not self._writer_stop.is_set() or not self._write_queue.empty():
            try:
                first = self._write_queue.get(timeout=0.1)
            except queue.Empty:
                continue

            batch = [first]
            while len(batch) < WRITE_BATCH_MAX:
                try:
                    batch.append(self._write_queue.get_nowait())
                except queue.Empty:
                    break

            try:
                self._persist_batch(batch)
            except sqlite3.Error:
                with self._counter_lock:
                    self.write_errors += len(batch)
                LOG.exception(
                    "Could not persist diagnostic batch containing %d event(s)",
                    len(batch),
                )
            finally:
                for _ in batch:
                    self._write_queue.task_done()

    def _persist_batch(self, batch: list[_PendingDiagnostic]) -> None:
        if not batch:
            return
        with closing(self._connect()) as db, db:
            db.executemany(
                """
                INSERT INTO diagnostic_events (
                    event_id, occurred_at, severity, category, component,
                    event_type, message, boot_id, panel_session_id,
                    transport_session_id, correlation_id, details_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        item.event_id,
                        item.occurred_at,
                        item.severity,
                        item.category,
                        item.component,
                        item.event_type,
                        item.message,
                        item.boot_id,
                        item.panel_session_id,
                        item.transport_session_id,
                        item.correlation_id,
                        item.details_json,
                    )
                    for item in batch
                ],
            )
        self.prune()

    def prune(
        self,
        *,
        now: datetime | None = None,
        max_age_days: int | None = None,
        max_rows: int | None = None,
        batch_size: int = 500,
    ) -> int:
        if not self.available:
            return 0
        age_days = (
            self.max_age_days if max_age_days is None else max(1, int(max_age_days))
        )
        row_limit = self.max_rows if max_rows is None else max(100, int(max_rows))
        batch = max(1, min(5000, int(batch_size)))
        reference = now or datetime.now(timezone.utc)
        cutoff = (reference - timedelta(days=age_days)).isoformat()

        try:
            with closing(self._connect()) as db, db:
                deleted = 0
                expired = db.execute(
                    "SELECT id FROM diagnostic_events WHERE occurred_at < ? "
                    "ORDER BY id LIMIT ?",
                    (cutoff, batch),
                ).fetchall()
                if expired:
                    ids = [int(row[0]) for row in expired]
                    placeholders = ",".join("?" for _ in ids)
                    cursor = db.execute(
                        f"DELETE FROM diagnostic_events WHERE id IN ({placeholders})",
                        ids,
                    )
                    deleted += int(cursor.rowcount)

                remaining = db.execute(
                    "SELECT COUNT(*) FROM diagnostic_events"
                ).fetchone()
                count = int(remaining[0]) if remaining else 0
                excess = count - row_limit
                if excess > 0 and deleted < batch:
                    limit = min(excess, batch - deleted)
                    cursor = db.execute(
                        "DELETE FROM diagnostic_events WHERE id IN ("
                        "SELECT id FROM diagnostic_events ORDER BY id LIMIT ?"
                        ")",
                        (limit,),
                    )
                    deleted += int(cursor.rowcount)
                return deleted
        except sqlite3.Error:
            LOG.exception("Could not prune diagnostic journal")
            return 0

    @classmethod
    def _record_from_row(cls, row: sqlite3.Row) -> DiagnosticRecord:
        try:
            details = json.loads(row["details_json"])
        except (TypeError, ValueError, json.JSONDecodeError):
            details = {}
        if not isinstance(details, dict):
            details = {}
        return DiagnosticRecord(
            id=int(row["id"]),
            event_id=str(row["event_id"]),
            occurred_at=str(row["occurred_at"]),
            severity=str(row["severity"]),
            category=str(row["category"]),
            component=str(row["component"]),
            event_type=str(row["event_type"]),
            message=str(row["message"]),
            boot_id=str(row["boot_id"]),
            panel_session_id=str(row["panel_session_id"]),
            transport_session_id=str(row["transport_session_id"]),
            correlation_id=str(row["correlation_id"]),
            details=details,
        )

    @classmethod
    def _encode_details(cls, details: dict[str, Any] | None) -> str:
        sanitized = cls._sanitize_value(details or {}, depth=0)
        if not isinstance(sanitized, dict):
            sanitized = {}
        encoded = json.dumps(
            sanitized,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        )
        if len(encoded) <= MAX_DETAILS_JSON:
            return encoded
        return json.dumps(
            {
                "details_truncated": True,
                "encoded_size": len(encoded),
            },
            separators=(",", ":"),
            sort_keys=True,
        )

    @classmethod
    def _sanitize_value(cls, value: Any, *, depth: int) -> Any:
        if depth >= MAX_DETAIL_DEPTH:
            return "[max-depth]"
        if value is None or isinstance(value, (bool, int, float)):
            return value
        if isinstance(value, str):
            return cls._clean_text(value, MAX_DETAIL_STRING)
        if isinstance(value, dict):
            result: dict[str, Any] = {}
            for index, (raw_key, item) in enumerate(value.items()):
                if index >= MAX_DETAIL_KEYS:
                    result["details_truncated"] = True
                    break
                key = cls._clean_text(raw_key, 64)
                if not key:
                    continue
                normalized = key.lower()
                if cls._sensitive_key(normalized):
                    result[key] = "[redacted]"
                else:
                    result[key] = cls._sanitize_value(item, depth=depth + 1)
            return result
        if isinstance(value, (list, tuple, set, frozenset)):
            items = list(value)[:MAX_DETAIL_ITEMS]
            result = [cls._sanitize_value(item, depth=depth + 1) for item in items]
            if len(value) > MAX_DETAIL_ITEMS:
                result.append("[truncated]")
            return result
        return cls._clean_text(repr(value), MAX_DETAIL_STRING)

    @staticmethod
    def _sensitive_key(key: str) -> bool:
        if key in SENSITIVE_DETAIL_KEYS:
            return True
        return any(key.endswith(suffix) for suffix in SENSITIVE_DETAIL_SUFFIXES)

    @staticmethod
    def _clean_text(value: Any, limit: int) -> str:
        return "".join(
            character for character in str(value) if character.isprintable()
        )[:limit]
