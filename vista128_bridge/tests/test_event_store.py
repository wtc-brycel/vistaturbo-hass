import os
import sqlite3
import sys
import tempfile
import unittest
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))

from vista_bridge.event_store import EventStore  # noqa: E402
from vista_bridge.protocol import SystemEvent  # noqa: E402


def sample_event() -> SystemEvent:
    return SystemEvent(
        code="B7",
        description="Arm STAY",
        zone=0,
        user=2,
        partition=1,
        minute=21,
        hour=3,
        day=15,
        month=8,
        year=26,
    )


class TrackingEventStore(EventStore):
    def __init__(self, path: str) -> None:
        self.opened_connections = []
        super().__init__(path)

    def _connect(self):
        db = super()._connect()
        self.opened_connections.append(db)
        return db

    def assert_all_closed(self, testcase: unittest.TestCase) -> None:
        for db in self.opened_connections:
            with testcase.assertRaises(sqlite3.ProgrammingError):
                db.execute("SELECT 1")


class EventStoreTests(unittest.TestCase):
    def test_connections_are_closed_after_each_operation(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = TrackingEventStore(os.path.join(tmp, "events.sqlite3"))
            store.assert_all_closed(self)

            event = sample_event()
            store.record(event, source="live", received_at="2026-08-15T03:21:05-04:00")
            store.update_descriptor(0, "SYSTEM")
            store.finish_history_dump(
                completed_at="2026-08-17T10:00:01-04:00",
                seen=1,
                inserted=1,
            )
            store.stats()
            store.recent(20)
            store.assert_all_closed(self)

    def test_live_and_history_observations_dedupe_into_one_journal_row(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = EventStore(os.path.join(tmp, "events.sqlite3"))
            event = sample_event()

            self.assertTrue(
                store.record(
                    event,
                    source="live",
                    received_at="2026-08-15T03:21:05-04:00",
                )
            )
            self.assertFalse(
                store.record(
                    event,
                    source="history",
                    received_at="2026-08-17T10:00:00-04:00",
                    occurrence=1,
                )
            )

            self.assertEqual(store.stats().count, 1)
            recent = store.recent(20)
            self.assertEqual(len(recent), 1)
            self.assertEqual(recent[0]["source"], "both")
            self.assertEqual(recent[0]["event_code"], "B7")
            self.assertEqual(recent[0]["panel_timestamp"], "2026-08-15T03:21")

    def test_repeated_same_minute_events_are_preserved_by_occurrence(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = EventStore(os.path.join(tmp, "events.sqlite3"))
            event = sample_event()
            self.assertTrue(store.record(event, source="history", received_at="2026-08-17T10:00:00-04:00", occurrence=1))
            self.assertTrue(store.record(event, source="history", received_at="2026-08-17T10:00:01-04:00", occurrence=2))
            self.assertFalse(store.record(event, source="history", received_at="2026-08-17T10:01:00-04:00", occurrence=1))
            self.assertEqual(store.stats().count, 2)
            self.assertEqual([row["occurrence"] for row in store.recent(20)], [2, 1])

    def test_descriptor_backfill_updates_existing_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = EventStore(os.path.join(tmp, "events.sqlite3"))
            event = sample_event()
            event = SystemEvent(**{**event.__dict__, "zone": 27})
            store.record(event, source="history", received_at="2026-08-17T10:00:00-04:00", occurrence=1)
            self.assertEqual(store.update_descriptor(27, "FRONT DOOR"), 1)
            self.assertEqual(store.recent(1)[0]["descriptor"], "FRONT DOOR")

    def test_history_dump_metadata_persists(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "events.sqlite3")
            store = EventStore(path)
            store.finish_history_dump(
                completed_at="2026-08-17T10:00:01-04:00",
                seen=512,
                inserted=417,
            )

            reopened = EventStore(path)
            stats = reopened.stats()
            self.assertEqual(stats.last_dump_at, "2026-08-17T10:00:01-04:00")
            self.assertEqual(stats.last_dump_seen, 512)
            self.assertEqual(stats.last_dump_inserted, 417)

    def test_recent_limit_is_bounded(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = EventStore(os.path.join(tmp, "events.sqlite3"))
            event = sample_event()
            store.record(
                event,
                source="history",
                received_at="2026-08-17T10:00:00-04:00",
            )
            self.assertEqual(len(store.recent(1000)), 1)

    def test_pruning_enforces_age_and_row_limits(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = EventStore(os.path.join(tmp, "events.sqlite3"), max_age_days=30, max_rows=2)
            base = sample_event()
            for occurrence in (1, 2, 3):
                store.record(
                    base,
                    source="history",
                    received_at=f"2026-08-2{occurrence}T10:00:00+00:00",
                    occurrence=occurrence,
                )
            self.assertEqual(store.stats().count, 2)
            deleted = store.prune(
                now=datetime(2026, 8, 29, tzinfo=timezone.utc),
                max_age_days=1,
                max_rows=100,
                batch_size=10,
            )
            self.assertEqual(deleted, 2)
            self.assertEqual(store.stats().count, 0)

    def test_keypad_audit_upserts_one_logical_interaction_with_command(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "events.sqlite3")
            store = EventStore(path, max_age_days=30, max_rows=10)
            store.record_keypad_interaction(
                interaction_id="interaction-1",
                observed_at="2026-08-17T10:00:00+00:00",
                started_at="2026-08-17T09:59:59+00:00",
                actor_id="alice-id",
                actor_name="Alice",
                partition=1,
                source="ha_frontend",
                action="keypad_sequence",
                command_sequence="1234#",
                operands={"zone": "7"},
                status="queued",
                ok=False,
            )
            store.record_keypad_interaction(
                interaction_id="interaction-1",
                observed_at="2026-08-17T10:00:01+00:00",
                actor_id="alice-id",
                actor_name="Alice",
                partition=1,
                source="ha_frontend",
                action="keypad_sequence",
                command_sequence="1234#",
                operands={"zone": "007"},
                status="accepted",
                ok=True,
            )
            with sqlite3.connect(path) as db:
                count = db.execute("SELECT COUNT(*) FROM keypad_interactions").fetchone()[0]
                row = db.execute(
                    "SELECT actor_id, actor_name, partition_number, source, action, "
                    "command_sequence, operands_json, status, ok "
                    "FROM keypad_interactions WHERE interaction_id='interaction-1'"
                ).fetchone()
                columns = {
                    column[1] for column in db.execute("PRAGMA table_info(keypad_interactions)")
                }
            self.assertEqual(count, 1)
            self.assertEqual(
                row,
                (
                    "alice-id",
                    "Alice",
                    1,
                    "ha_frontend",
                    "keypad_sequence",
                    "1234#",
                    '{"zone":"007"}',
                    "accepted",
                    1,
                ),
            )
            self.assertNotIn("keys", columns)
            self.assertNotIn("payload", columns)

    def test_keypad_audit_schema_migrates_existing_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "events.sqlite3")
            with sqlite3.connect(path) as db:
                db.execute(
                    "CREATE TABLE keypad_interactions ("
                    "interaction_id TEXT PRIMARY KEY, started_at TEXT NOT NULL, "
                    "last_seen_at TEXT NOT NULL, completed_at TEXT NOT NULL DEFAULT '', "
                    "actor_id TEXT NOT NULL DEFAULT '', actor_name TEXT NOT NULL DEFAULT '', "
                    "partition_number INTEGER NOT NULL, source TEXT NOT NULL, "
                    "action TEXT NOT NULL, status TEXT NOT NULL, ok INTEGER NOT NULL DEFAULT 0)"
                )
            EventStore(path)
            with sqlite3.connect(path) as db:
                columns = {
                    column[1]
                    for column in db.execute("PRAGMA table_info(keypad_interactions)")
                }
            self.assertIn("command_sequence", columns)
            self.assertIn("operands_json", columns)
            self.assertIn("last_request_id", columns)

    def test_keypad_audit_retention_is_bounded(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = EventStore(os.path.join(tmp, "events.sqlite3"), max_age_days=30, max_rows=2)
            for index in range(3):
                store.record_keypad_interaction(
                    interaction_id=f"interaction-{index}",
                    observed_at=f"2026-08-20T10:00:0{index}+00:00",
                    partition=1,
                    source="ha_frontend",
                    action="keypad_sequence",
                    status="accepted",
                    ok=True,
                )
            with sqlite3.connect(store.path) as db:
                self.assertEqual(
                    db.execute("SELECT COUNT(*) FROM keypad_interactions").fetchone()[0],
                    2,
                )
            deleted = store.prune(
                now=datetime(2026, 8, 29, tzinfo=timezone.utc),
                max_age_days=1,
                max_rows=100,
                batch_size=10,
            )
            self.assertEqual(deleted, 2)

    def test_keypad_audit_concatenates_segments_for_one_interaction(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "events.sqlite3")
            store = EventStore(path)
            for sequence, status in (("1", "queued"), ("2", "accepted")):
                store.record_keypad_interaction(
                    interaction_id="interaction-1",
                    observed_at=f"2026-08-20T10:00:0{sequence}+00:00",
                    partition=1,
                    source="ha_frontend",
                    action="keypad_sequence",
                    command_sequence=sequence,
                    status=status,
                    ok=status == "accepted",
                )
            with sqlite3.connect(path) as db:
                row = db.execute(
                    "SELECT command_sequence, status FROM keypad_interactions "
                    "WHERE interaction_id='interaction-1'"
                ).fetchone()
            self.assertEqual(row, ("12", "accepted"))

    def test_keypad_audit_lifecycle_is_idempotent_per_segment(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "events.sqlite3")
            store = EventStore(path)
            for sequence, status, request_id in (
                ("1", "queued", "segment-1"),
                ("1", "accepted", "segment-1"),
                ("2", "queued", "segment-2"),
                ("2", "accepted", "segment-2"),
            ):
                store.record_keypad_interaction(
                    interaction_id="interaction-1",
                    observed_at=f"2026-08-20T10:00:0{len(request_id)}+00:00",
                    partition=1,
                    source="ha_frontend",
                    action="keypad_sequence",
                    command_sequence=sequence,
                    request_id=request_id,
                    status=status,
                    ok=status == "accepted",
                )
            with sqlite3.connect(path) as db:
                row = db.execute(
                    "SELECT command_sequence, status, last_request_id "
                    "FROM keypad_interactions WHERE interaction_id='interaction-1'"
                ).fetchone()
            self.assertEqual(row, ("12", "accepted", "segment-2"))

    def test_keypad_audit_appends_identical_distinct_segments(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = EventStore(os.path.join(tmp, "events.sqlite3"))
            for request_id, status in (
                ("segment-1", "queued"),
                ("segment-1", "accepted"),
                ("segment-2", "queued"),
                ("segment-2", "accepted"),
            ):
                store.record_keypad_interaction(
                    interaction_id="interaction-1",
                    observed_at="2026-08-20T10:00:00+00:00",
                    partition=1,
                    source="ha_frontend",
                    action="keypad_sequence",
                    command_sequence="1",
                    request_id=request_id,
                    status=status,
                    ok=status == "accepted",
                )
            with sqlite3.connect(store.path) as db:
                sequence = db.execute(
                    "SELECT command_sequence FROM keypad_interactions "
                    "WHERE interaction_id='interaction-1'"
                ).fetchone()[0]
            self.assertEqual(sequence, "11")


if __name__ == "__main__":
    unittest.main()
