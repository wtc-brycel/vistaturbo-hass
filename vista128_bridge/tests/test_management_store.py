from __future__ import annotations

from contextlib import closing
from pathlib import Path
import sqlite3
import tempfile
import unittest

from vista_bridge.management_store import ManagementStore


def _db(path: str) -> sqlite3.Connection:
    db = sqlite3.connect(path)
    db.row_factory = sqlite3.Row
    return db


def _initialize(path: str) -> None:
    with closing(_db(path)) as db, db:
        db.executescript(
            """
            CREATE TABLE metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL);
            CREATE TABLE events(
                id INTEGER PRIMARY KEY, occurrence INTEGER NOT NULL DEFAULT 1,
                event_code TEXT NOT NULL, description TEXT NOT NULL,
                zone INTEGER NOT NULL, user_number INTEGER NOT NULL,
                partition_number INTEGER NOT NULL, panel_timestamp TEXT,
                descriptor TEXT NOT NULL DEFAULT '', seen_live INTEGER NOT NULL DEFAULT 0,
                seen_history INTEGER NOT NULL DEFAULT 0,
                last_received_at TEXT NOT NULL
            );
            CREATE TABLE keypad_interactions(
                interaction_id TEXT PRIMARY KEY, started_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL, completed_at TEXT NOT NULL DEFAULT '',
                actor_id TEXT NOT NULL DEFAULT '', actor_name TEXT NOT NULL DEFAULT '',
                partition_number INTEGER NOT NULL, source TEXT NOT NULL,
                action TEXT NOT NULL, command_sequence TEXT NOT NULL DEFAULT '',
                operands_json TEXT NOT NULL DEFAULT '{}', last_request_id TEXT NOT NULL DEFAULT '',
                command_type TEXT NOT NULL DEFAULT '', code TEXT NOT NULL DEFAULT '',
                execution_mechanism TEXT NOT NULL DEFAULT '', confidence TEXT NOT NULL DEFAULT '',
                verification TEXT NOT NULL DEFAULT '', status TEXT NOT NULL, ok INTEGER NOT NULL DEFAULT 0
            );
            """
        )
        db.execute(
            "INSERT INTO events VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
            (1, 1, "F5", "Fault", 27, 0, 1, "2026-08-30T20:10:00-04:00", "FRONT DOOR", 1, 0, "2026-08-30T20:10:02-04:00"),
        )
        db.execute(
            "INSERT INTO events VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
            (2, 1, "B7", "Arm STAY", 0, 2, 2, "2026-08-30T19:45:00-04:00", "", 0, 1, "2026-08-30T20:00:00-04:00"),
        )
        db.execute(
            "INSERT INTO keypad_interactions VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                "audit-1", "2026-08-30T20:20:00-04:00", "2026-08-30T20:20:02-04:00",
                "2026-08-30T20:20:02-04:00", "ha-user-1", "Bryce", 1, "ha_frontend",
                "disarm", "24681", '{"partition":1}', "request-1", "disarm", "2468",
                "native", "high", "confirmed", "confirmed", 1,
            ),
        )


class ManagementStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = str(Path(self.temp.name) / "events.sqlite3")
        _initialize(self.path)
        self.store = ManagementStore(self.path)

    def tearDown(self):
        self.temp.cleanup()

    def test_admin_secret_is_one_way_and_verifiable(self):
        self.store.configure_admin_unlock("correct horse battery staple")
        self.assertTrue(self.store.admin_unlock_configured())
        self.assertTrue(self.store.verify_admin_unlock("correct horse battery staple"))
        self.assertFalse(self.store.verify_admin_unlock("incorrect secret"))
        with closing(_db(self.path)) as db:
            values = [row[0] for row in db.execute("SELECT value FROM metadata")]
        self.assertNotIn("correct horse battery staple", values)

    def test_unified_log_query_filters_sorts_searches_and_pages(self):
        self.store.ensure_indexes()
        page = self.store.query_logs(search="front door", page_size=25)
        self.assertEqual(page.total, 1)
        self.assertEqual(page.records[0]["record_type"], "panel")
        self.assertEqual(page.records[0]["zone"], 27)

        audit = self.store.query_logs(record_type="audit", actor="bryce", status="confirmed")
        self.assertEqual(audit.total, 1)
        self.assertEqual(audit.records[0]["event_action"], "disarm")
        self.assertEqual(audit.records[0]["subject"], "Bryce")

        partition = self.store.query_logs(partition=2, direction="asc")
        self.assertEqual(partition.total, 1)
        self.assertEqual(partition.records[0]["user_number"], 2)

        all_rows = self.store.query_logs(page=1, page_size=2, sort="time", direction="desc")
        self.assertEqual(all_rows.total, 3)
        self.assertEqual(len(all_rows.records), 2)
        self.assertEqual(all_rows.records[0]["record_type"], "audit")
        second = self.store.query_logs(page=2, page_size=2, sort="time", direction="desc")
        self.assertEqual(len(second.records), 1)

    def test_sensitive_audit_detail_is_explicitly_gated(self):
        safe = self.store.audit_detail("audit-1", include_sensitive=False)
        self.assertIsNotNone(safe)
        self.assertNotIn("command_sequence", safe)
        self.assertNotIn("code", safe)
        self.assertNotIn("operands", safe)

        sensitive = self.store.audit_detail("audit-1", include_sensitive=True)
        self.assertIsNotNone(sensitive)
        self.assertEqual(sensitive["command_sequence"], "24681")
        self.assertEqual(sensitive["code"], "2468")
        self.assertEqual(sensitive["operands"], {"partition": 1})


if __name__ == "__main__":
    unittest.main()
