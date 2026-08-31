import os
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))

from vista_bridge.event_store import EventStore  # noqa: E402


class EventStoreCommandIntegrityTests(unittest.TestCase):
    def test_acknowledged_unverified_completes_audit_interaction(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "events.sqlite3")
            store = EventStore(path)
            observed_at = "2026-08-30T20:00:00-04:00"
            store.record_keypad_interaction(
                interaction_id="subtype-unverified",
                observed_at=observed_at,
                partition=1,
                source="mqtt",
                action="arm_home",
                command_type="arm_home",
                execution_mechanism="keypad",
                verification="acknowledged_unverified",
                status="acknowledged_unverified",
                ok=True,
            )

            with sqlite3.connect(path) as db:
                row = db.execute(
                    "SELECT completed_at, status, verification, ok "
                    "FROM keypad_interactions "
                    "WHERE interaction_id = 'subtype-unverified'"
                ).fetchone()

            self.assertEqual(
                row,
                (
                    observed_at,
                    "acknowledged_unverified",
                    "acknowledged_unverified",
                    1,
                ),
            )


if __name__ == "__main__":
    unittest.main()
