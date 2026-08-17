import os
import sqlite3
import sys
import tempfile
import unittest

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


if __name__ == "__main__":
    unittest.main()
