import os
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


class EventStoreTests(unittest.TestCase):
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
                )
            )

            self.assertEqual(store.stats().count, 1)
            recent = store.recent(20)
            self.assertEqual(len(recent), 1)
            self.assertEqual(recent[0]["source"], "both")
            self.assertEqual(recent[0]["event_code"], "B7")
            self.assertEqual(recent[0]["panel_timestamp"], "2026-08-15T03:21")

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
