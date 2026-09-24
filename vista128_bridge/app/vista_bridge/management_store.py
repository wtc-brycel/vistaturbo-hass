from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
import base64
import hashlib
import hmac
import json
import sqlite3
import secrets
from typing import Any


_ALLOWED_SORTS = {
    "time": "sort_time",
    "type": "record_type",
    "event": "event_action",
    "partition": "partition_number",
    "subject": "subject",
    "source": "source_result",
}


@dataclass(frozen=True)
class ManagementLogPage:
    records: list[dict[str, Any]]
    total: int
    page: int
    page_size: int


class ManagementStore:
    """Read/query and local step-up-auth helpers over the event database.

    This class deliberately does not own panel state or execute panel writes.
    It only exposes retained event/audit records and an administrator-unlock
    verifier stored as a salted one-way scrypt hash in SQLite metadata.
    """

    _SALT_KEY = "management_admin_salt_v1"
    _HASH_KEY = "management_admin_hash_v1"

    def __init__(self, path: str) -> None:
        self.path = path

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=5)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("PRAGMA synchronous=NORMAL")
        return db

    def ensure_indexes(self) -> None:
        with closing(self._connect()) as db, db:
            db.executescript(
                """
                CREATE INDEX IF NOT EXISTS idx_events_zone_time
                    ON events(zone, panel_timestamp DESC, id DESC);
                CREATE INDEX IF NOT EXISTS idx_events_user_time
                    ON events(user_number, panel_timestamp DESC, id DESC);
                CREATE INDEX IF NOT EXISTS idx_audit_partition_time
                    ON keypad_interactions(partition_number, last_seen_at DESC);
                CREATE INDEX IF NOT EXISTS idx_audit_actor_time
                    ON keypad_interactions(actor_name, last_seen_at DESC);
                CREATE INDEX IF NOT EXISTS idx_audit_status_time
                    ON keypad_interactions(status, last_seen_at DESC);
                """
            )

    @staticmethod
    def _secret_hash(secret: str, salt: bytes) -> bytes:
        return hashlib.scrypt(
            secret.encode("utf-8"),
            salt=salt,
            n=2**14,
            r=8,
            p=1,
            dklen=32,
        )

    def admin_unlock_configured(self) -> bool:
        with closing(self._connect()) as db:
            keys = {
                row[0]
                for row in db.execute(
                    "SELECT key FROM metadata WHERE key IN (?, ?)",
                    (self._SALT_KEY, self._HASH_KEY),
                )
            }
        return {self._SALT_KEY, self._HASH_KEY} <= keys

    def configure_admin_unlock(self, secret: str, *, replace: bool = False) -> None:
        if not isinstance(secret, str) or not 12 <= len(secret) <= 128:
            raise ValueError("administrator unlock secret must be 12..128 characters")
        if self.admin_unlock_configured() and not replace:
            raise RuntimeError("administrator unlock is already configured")
        salt = secrets.token_bytes(16)
        digest = self._secret_hash(secret, salt)
        values = {
            self._SALT_KEY: base64.b64encode(salt).decode("ascii"),
            self._HASH_KEY: base64.b64encode(digest).decode("ascii"),
        }
        with closing(self._connect()) as db, db:
            for key, value in values.items():
                db.execute(
                    "INSERT INTO metadata(key,value) VALUES(?,?) "
                    "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                    (key, value),
                )

    def verify_admin_unlock(self, secret: str) -> bool:
        if not isinstance(secret, str):
            return False
        with closing(self._connect()) as db:
            values = {
                row["key"]: row["value"]
                for row in db.execute(
                    "SELECT key,value FROM metadata WHERE key IN (?, ?)",
                    (self._SALT_KEY, self._HASH_KEY),
                )
            }
        try:
            salt = base64.b64decode(values[self._SALT_KEY], validate=True)
            expected = base64.b64decode(values[self._HASH_KEY], validate=True)
        except (KeyError, ValueError):
            return False
        actual = self._secret_hash(secret, salt)
        return hmac.compare_digest(actual, expected)

    def query_logs(
        self,
        *,
        search: str = "",
        record_type: str = "all",
        partition: int | None = None,
        source_result: str = "",
        zone: int | None = None,
        user_number: int | None = None,
        actor: str = "",
        status: str = "",
        start_at: str = "",
        end_at: str = "",
        sort: str = "time",
        direction: str = "desc",
        page: int = 1,
        page_size: int = 50,
    ) -> ManagementLogPage:
        page = max(1, int(page))
        page_size = max(1, min(100, int(page_size)))
        record_type = record_type if record_type in {"all", "panel", "audit"} else "all"
        sort_column = _ALLOWED_SORTS.get(sort, "sort_time")
        order = "ASC" if direction.lower() == "asc" else "DESC"
        clauses: list[str] = []
        params: list[Any] = []
        if record_type != "all":
            clauses.append("record_type = ?")
            params.append(record_type)
        if partition is not None:
            clauses.append("partition_number = ?")
            params.append(max(0, min(8, int(partition))))
        if source_result:
            clauses.append("LOWER(source_result) = LOWER(?)")
            params.append(source_result[:64])
        if zone is not None:
            clauses.append("zone = ?")
            params.append(max(0, min(999, int(zone))))
        if user_number is not None:
            clauses.append("user_number = ?")
            params.append(max(0, min(999, int(user_number))))
        if actor:
            clauses.append("LOWER(actor_name || ' ' || actor_id) LIKE ?")
            params.append(f"%{actor.lower()[:128]}%")
        if status:
            clauses.append("LOWER(status) = LOWER(?)")
            params.append(status[:64])
        if start_at:
            clauses.append("sort_time >= ?")
            params.append(start_at[:64])
        if end_at:
            clauses.append("sort_time <= ?")
            params.append(end_at[:64])
        if search:
            token = f"%{search.lower()[:160]}%"
            clauses.append(
                "LOWER(event_action || ' ' || subject || ' ' || source_result || ' ' || "
                "event_code || ' ' || CAST(zone AS TEXT) || ' ' || CAST(user_number AS TEXT) || ' ' || "
                "actor_name || ' ' || actor_id || ' ' || command_type || ' ' || verification || ' ' || status) LIKE ?"
            )
            params.append(token)
        where = "WHERE " + " AND ".join(clauses) if clauses else ""
        union = self._unified_log_sql()
        count_sql = f"SELECT COUNT(*) FROM ({union}) records {where}"
        query_sql = (
            f"SELECT * FROM ({union}) records {where} "
            f"ORDER BY {sort_column} {order}, record_id {order} LIMIT ? OFFSET ?"
        )
        offset = (page - 1) * page_size
        with closing(self._connect()) as db:
            total = int(db.execute(count_sql, params).fetchone()[0])
            rows = db.execute(query_sql, [*params, page_size, offset]).fetchall()
        records = [self._row_to_log_record(row) for row in rows]
        return ManagementLogPage(records=records, total=total, page=page, page_size=page_size)

    @staticmethod
    def _unified_log_sql() -> str:
        return """
            SELECT
                'panel' AS record_type,
                CAST(id AS TEXT) AS record_id,
                COALESCE(panel_timestamp, last_received_at) AS sort_time,
                description AS event_action,
                partition_number,
                CASE
                    WHEN zone > 0 THEN 'Z' || printf('%03d', zone) || CASE WHEN descriptor <> '' THEN ' · ' || descriptor ELSE '' END
                    WHEN user_number > 0 THEN 'User ' || printf('%03d', user_number)
                    ELSE CASE WHEN descriptor <> '' THEN descriptor ELSE '-' END
                END AS subject,
                CASE WHEN seen_live = 1 AND seen_history = 1 THEN 'both' WHEN seen_live = 1 THEN 'live' ELSE 'history' END AS source_result,
                zone,
                user_number,
                '' AS actor_name,
                '' AS actor_id,
                event_code,
                '' AS command_type,
                '' AS verification,
                '' AS status
            FROM events
            UNION ALL
            SELECT
                'audit' AS record_type,
                interaction_id AS record_id,
                CASE WHEN completed_at <> '' THEN completed_at ELSE last_seen_at END AS sort_time,
                CASE WHEN action <> '' THEN action ELSE command_type END AS event_action,
                partition_number,
                CASE WHEN actor_name <> '' THEN actor_name WHEN actor_id <> '' THEN actor_id ELSE 'Home Assistant' END AS subject,
                CASE WHEN status <> '' THEN status ELSE source END AS source_result,
                0 AS zone,
                0 AS user_number,
                actor_name,
                actor_id,
                '' AS event_code,
                command_type,
                verification,
                status
            FROM keypad_interactions
        """

    @staticmethod
    def _row_to_log_record(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "record_type": row["record_type"],
            "id": row["record_id"],
            "time": row["sort_time"],
            "event_action": row["event_action"],
            "partition": row["partition_number"],
            "subject": row["subject"],
            "source_result": row["source_result"],
            "zone": row["zone"],
            "user_number": row["user_number"],
            "actor_name": row["actor_name"],
            "actor_id": row["actor_id"],
            "event_code": row["event_code"],
            "command_type": row["command_type"],
            "verification": row["verification"],
            "status": row["status"],
        }

    def audit_detail(self, interaction_id: str, *, include_sensitive: bool = False) -> dict[str, Any] | None:
        with closing(self._connect()) as db:
            row = db.execute(
                "SELECT interaction_id,started_at,last_seen_at,completed_at,actor_id,actor_name,"
                "partition_number,source,action,operands_json,last_request_id,command_type,"
                "execution_mechanism,confidence,verification,status,ok,command_sequence,code "
                "FROM keypad_interactions WHERE interaction_id = ?",
                (str(interaction_id)[:96],),
            ).fetchone()
        if row is None:
            return None
        result = {
            "interaction_id": row["interaction_id"],
            "started_at": row["started_at"],
            "last_seen_at": row["last_seen_at"],
            "completed_at": row["completed_at"],
            "actor_id": row["actor_id"],
            "actor_name": row["actor_name"],
            "partition": row["partition_number"],
            "source": row["source"],
            "action": row["action"],
            "request_id": row["last_request_id"],
            "command_type": row["command_type"],
            "execution_mechanism": row["execution_mechanism"],
            "confidence": row["confidence"],
            "verification": row["verification"],
            "status": row["status"],
            "ok": bool(row["ok"]),
        }
        if include_sensitive:
            try:
                result["operands"] = json.loads(row["operands_json"] or "{}")
            except json.JSONDecodeError:
                result["operands"] = {}
            result["command_sequence"] = row["command_sequence"]
            result["code"] = row["code"]
        return result
