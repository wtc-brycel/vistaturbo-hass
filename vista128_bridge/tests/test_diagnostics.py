from __future__ import annotations

from datetime import datetime, timezone
import os
import sqlite3
import sys
import tempfile
import threading
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))

from vista_bridge.diagnostics import DiagnosticEvents as DE, DiagnosticJournal  # noqa: E402


class DiagnosticJournalTests(unittest.TestCase):
    def make_journal(self, path: str, **kwargs) -> DiagnosticJournal:
        return DiagnosticJournal(path, **kwargs)

    def test_record_derives_category_and_preserves_context(self):
        with tempfile.TemporaryDirectory() as tmp:
            journal = self.make_journal(os.path.join(tmp, "diagnostics.sqlite3"))
            panel_session = journal.new_id("panel")
            transport_session = journal.new_id("ha")
            correlation = journal.new_id("corr")
            journal.set_panel_session(panel_session)
            journal.set_transport_session(transport_session)

            event_id = journal.record(
                DE.HA_WATCHDOG_TRIGGERED,
                severity="error",
                component="mqtt",
                correlation_id=correlation,
                message="Heartbeat acknowledgement timed out",
                details={"last_puback_age_seconds": 61.2},
            )

            self.assertIsNotNone(event_id)
            row = journal.recent(limit=1)[0]
            self.assertEqual(row.category, "ha_transport")
            self.assertEqual(row.severity, "error")
            self.assertEqual(row.component, "mqtt")
            self.assertEqual(row.boot_id, journal.boot_id)
            self.assertEqual(row.panel_session_id, panel_session)
            self.assertEqual(row.transport_session_id, transport_session)
            self.assertEqual(row.correlation_id, correlation)
            self.assertEqual(row.details["last_puback_age_seconds"], 61.2)

    def test_sensitive_details_are_redacted_before_sqlite(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "diagnostics.sqlite3")
            journal = self.make_journal(path)
            secret = "super-secret-value"
            journal.record(
                DE.CONTROL_SAFETY_INTERLOCK_BLOCKED,
                severity="warning",
                details={
                    "pin": "1234",
                    "password": secret,
                    "payload": secret,
                    "nested": {"access_token": secret, "reason_code": 7},
                    "event_code": "B7",
                    "reason_code": 4,
                },
            )

            row = journal.recent(limit=1)[0]
            self.assertEqual(row.details["pin"], "[redacted]")
            self.assertEqual(row.details["password"], "[redacted]")
            self.assertEqual(row.details["payload"], "[redacted]")
            self.assertEqual(row.details["nested"]["access_token"], "[redacted]")
            self.assertEqual(row.details["nested"]["reason_code"], 7)
            self.assertEqual(row.details["event_code"], "B7")
            self.assertEqual(row.details["reason_code"], 4)

            with sqlite3.connect(path) as db:
                stored = db.execute(
                    "SELECT details_json FROM diagnostic_events"
                ).fetchone()[0]
            self.assertNotIn(secret, stored)
            self.assertNotIn("1234", stored)

    def test_recent_filters_and_sorting(self):
        with tempfile.TemporaryDirectory() as tmp:
            journal = self.make_journal(os.path.join(tmp, "diagnostics.sqlite3"))
            journal.record(
                "panel_transport.connected",
                component="tcp",
                occurred_at="2026-09-23T10:00:00+00:00",
            )
            journal.record(
                "ha_transport.disconnected",
                severity="warning",
                component="mqtt",
                correlation_id="corr_1",
                occurred_at="2026-09-23T10:01:00+00:00",
            )
            journal.record(
                "state_delivery.replay_completed",
                component="mqtt",
                correlation_id="corr_1",
                occurred_at="2026-09-23T10:02:00+00:00",
            )

            newest = journal.recent(order="newest")
            self.assertEqual(newest[0].event_type, "state_delivery.replay_completed")
            oldest = journal.recent(order="oldest")
            self.assertEqual(oldest[0].event_type, "panel_transport.connected")
            warning = journal.recent(severity="warning")
            self.assertEqual([item.event_type for item in warning], ["ha_transport.disconnected"])
            correlated = journal.recent(correlation_id="corr_1", order="oldest")
            self.assertEqual(
                [item.event_type for item in correlated],
                ["ha_transport.disconnected", "state_delivery.replay_completed"],
            )
            transport = journal.recent(category="ha_transport")
            self.assertEqual(len(transport), 1)
            window = journal.recent(
                since="2026-09-23T10:00:30+00:00",
                until="2026-09-23T10:01:30+00:00",
            )
            self.assertEqual(
                [item.event_type for item in window],
                [DE.HA_DISCONNECTED],
            )

    def test_cursor_pages_are_stable_and_do_not_duplicate_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            journal = self.make_journal(os.path.join(tmp, "diagnostics.sqlite3"))
            for index in range(5):
                journal.record(
                    DE.HEALTH_SNAPSHOT,
                    occurred_at=f"2026-09-23T10:0{index}:00+00:00",
                    details={"sequence": index},
                )
            self.assertTrue(journal.flush(timeout=2.0))

            first = journal.query_page(limit=2, order="newest")
            second = journal.query_page(
                limit=2,
                order="newest",
                cursor=first["next_cursor"],
            )
            third = journal.query_page(
                limit=2,
                order="newest",
                cursor=second["next_cursor"],
            )

            ids = [
                record.id
                for page in (first, second, third)
                for record in page["records"]
            ]
            self.assertEqual(len(ids), 5)
            self.assertEqual(len(set(ids)), 5)
            self.assertIsNotNone(first["next_cursor"])
            self.assertIsNotNone(second["next_cursor"])
            self.assertIsNone(third["next_cursor"])
            self.assertEqual(
                [record.details["sequence"] for record in first["records"]],
                [4, 3],
            )

    def test_cursor_page_rejects_invalid_cursor(self):
        with tempfile.TemporaryDirectory() as tmp:
            journal = self.make_journal(os.path.join(tmp, "diagnostics.sqlite3"))
            with self.assertRaises(ValueError):
                journal.query_page(cursor={"id": 1})
            with self.assertRaises(ValueError):
                journal.query_page(cursor={"occurred_at": "x", "id": True})

    def test_incident_summary_groups_correlated_sequences(self):
        with tempfile.TemporaryDirectory() as tmp:
            journal = self.make_journal(os.path.join(tmp, "diagnostics.sqlite3"))
            correlation = journal.new_id("ha")
            journal.record(
                DE.HA_WATCHDOG_TRIGGERED,
                severity="error",
                component="mqtt",
                message="Heartbeat acknowledgement timed out",
                correlation_id=correlation,
                occurred_at="2026-09-23T10:00:00+00:00",
            )
            journal.record(
                DE.HA_RECOVERY_STARTED,
                severity="warning",
                component="mqtt",
                correlation_id=correlation,
                occurred_at="2026-09-23T10:00:01+00:00",
            )
            journal.record(
                DE.STATE_REPLAY_COMPLETED,
                component="mqtt",
                correlation_id=correlation,
                occurred_at="2026-09-23T10:00:03+00:00",
            )
            journal.record(
                DE.HEALTH_SNAPSHOT,
                component="bridge",
                occurred_at="2026-09-23T10:05:00+00:00",
            )
            self.assertTrue(journal.flush(timeout=2.0))

            incidents = journal.recent_incidents(limit=10)

            self.assertEqual(len(incidents), 1)
            incident = incidents[0]
            self.assertEqual(incident["correlation_id"], correlation)
            self.assertEqual(incident["event_count"], 3)
            self.assertEqual(incident["severity"], "error")
            self.assertEqual(
                incident["event_types"],
                [
                    DE.HA_WATCHDOG_TRIGGERED,
                    DE.HA_RECOVERY_STARTED,
                    DE.STATE_REPLAY_COMPLETED,
                ],
            )
            self.assertEqual(
                incident["categories"],
                ["ha_transport", "state_delivery"],
            )
            self.assertEqual(incident["components"], ["mqtt"])
            self.assertEqual(
                incident["summary"],
                "Heartbeat acknowledgement timed out",
            )

    def test_prune_enforces_age_and_row_limits(self):
        with tempfile.TemporaryDirectory() as tmp:
            journal = self.make_journal(
                os.path.join(tmp, "diagnostics.sqlite3"),
                max_age_days=3650,
                max_rows=100,
            )
            for index in range(105):
                journal.record(
                    "system.health_snapshot",
                    occurred_at=f"2026-09-23T10:{index % 60:02d}:00+00:00",
                    details={"sequence": index},
                )
            journal.prune(
                now=datetime(2026, 9, 23, 12, 0, tzinfo=timezone.utc),
                max_age_days=3650,
                max_rows=100,
                batch_size=500,
            )
            self.assertEqual(journal.stats().count, 100)

            deleted = journal.prune(
                now=datetime(2026, 9, 25, 12, 0, tzinfo=timezone.utc),
                max_age_days=1,
                max_rows=100,
                batch_size=500,
            )
            self.assertEqual(deleted, 100)
            self.assertEqual(journal.stats().count, 0)

    def test_record_does_not_block_on_slow_sqlite_writer(self):
        with tempfile.TemporaryDirectory() as tmp:
            journal = self.make_journal(os.path.join(tmp, "diagnostics.sqlite3"))
            gate = threading.Event()
            original_persist = journal._persist_batch

            def slow_persist(batch):
                gate.wait(timeout=1.0)
                original_persist(batch)

            journal._persist_batch = slow_persist
            started = time.monotonic()
            event_id = journal.record(
                DE.HA_DISCONNECTED,
                severity="warning",
                component="mqtt",
                details={"reason_code": 7},
            )
            elapsed = time.monotonic() - started

            self.assertIsNotNone(event_id)
            self.assertLess(elapsed, 0.1)
            gate.set()
            self.assertTrue(journal.flush(timeout=2.0))
            journal.close()

    def test_close_flushes_last_queued_event(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "diagnostics.sqlite3")
            journal = self.make_journal(path)
            event_id = journal.record(
                DE.APP_STOPPED,
                component="bridge",
                occurred_at="2026-09-23T19:30:00+00:00",
            )

            self.assertIsNotNone(event_id)
            self.assertTrue(journal.close(timeout=2.0))
            with sqlite3.connect(path) as db:
                row = db.execute(
                    "SELECT event_type FROM diagnostic_events WHERE event_id = ?",
                    (event_id,),
                ).fetchone()
            self.assertEqual(row, (DE.APP_STOPPED,))

    def test_invalid_event_taxonomy_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            journal = self.make_journal(os.path.join(tmp, "diagnostics.sqlite3"))
            with self.assertRaises(ValueError):
                journal.record("mqtt_broke")
            with self.assertRaises(ValueError):
                journal.record("random.failure")
            with self.assertRaises(ValueError):
                journal.record("system.failure", severity="fatal")

    def test_unavailable_journal_fails_open(self):
        journal = DiagnosticJournal("/dev/null/diagnostics.sqlite3")
        self.assertFalse(journal.available)
        self.assertIsNone(journal.record("system.app_started"))
        self.assertEqual(journal.recent(), [])
        self.assertEqual(journal.stats().count, 0)


if __name__ == "__main__":
    unittest.main()
