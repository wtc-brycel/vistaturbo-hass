from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

from vista_bridge.event_store import EventStore  # noqa: E402
from vista_bridge.protocol import SystemEvent  # noqa: E402


def _event(
    code: str,
    description: str,
    *,
    zone: int,
    user: int,
    partition: int,
    minute: int,
) -> SystemEvent:
    return SystemEvent(
        code=code,
        description=description,
        zone=zone,
        user=user,
        partition=partition,
        minute=minute,
        hour=20,
        day=21,
        month=9,
        year=26,
    )


class EventStoreAdminQueryTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.store = EventStore(
            str(Path(self.tempdir.name) / "events.sqlite3"),
            max_age_days=3650,
            max_rows=10000,
        )
        received = "2026-09-21T20:30:00+00:00"
        self.fire = _event(
            "01",
            "Fire alarm",
            zone=1,
            user=0,
            partition=1,
            minute=1,
        )
        self.burg = _event(
            "07",
            "Burglary alarm",
            zone=27,
            user=12,
            partition=2,
            minute=2,
        )
        self.restore = _event(
            "02",
            "Fire restore",
            zone=1,
            user=0,
            partition=1,
            minute=3,
        )

        self.store.record(
            self.fire,
            source="history",
            received_at=received,
            descriptor="Front Smoke",
            occurrence=1,
        )
        self.store.record(
            self.fire,
            source="live",
            received_at=received,
            descriptor="Front Smoke",
            occurrence=1,
        )
        self.store.record(
            self.burg,
            source="live",
            received_at=received,
            descriptor="Rear Door",
            occurrence=1,
        )
        self.store.record(
            self.restore,
            source="history",
            received_at=received,
            descriptor="Front Smoke",
            occurrence=1,
        )

    def tearDown(self):
        self.tempdir.cleanup()

    def test_partition_and_source_filters(self):
        partition = self.store.query_page(partition=1)
        self.assertEqual(len(partition["events"]), 2)
        both = self.store.query_page(source="both")
        self.assertEqual(len(both["events"]), 1)
        self.assertEqual(both["events"][0]["event_code"], "01")

    def test_search_matches_descriptor(self):
        page = self.store.query_page(search="Front Smoke")
        self.assertEqual(len(page["events"]), 2)
        self.assertTrue(all(row["zone"] == 1 for row in page["events"]))

    def test_cursor_pages_without_duplicate(self):
        first = self.store.query_page(limit=1)
        self.assertIsNotNone(first["next_cursor"])
        second = self.store.query_page(
            limit=1,
            cursor=first["next_cursor"],
        )
        self.assertEqual(len(second["events"]), 1)
        self.assertNotEqual(
            first["events"][0]["id"],
            second["events"][0]["id"],
        )


if __name__ == "__main__":
    unittest.main()
