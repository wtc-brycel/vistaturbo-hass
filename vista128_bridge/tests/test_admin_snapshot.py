from __future__ import annotations

import json
from queue import Queue
from types import SimpleNamespace
import sys
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

from vista_bridge.admin_snapshot import AdminSnapshotBuilder  # noqa: E402
from vista_bridge.event_store import EventJournalStats  # noqa: E402
from vista_bridge.state import VistaState  # noqa: E402


class _FakeEventStore:
    def stats(self):
        return EventJournalStats(
            count=17,
            last_dump_at="2026-09-21T20:00:00+00:00",
            last_dump_seen=12,
            last_dump_inserted=3,
        )


class _FakeMqttClient:
    def is_connected(self):
        return True


class _FakeSynchronizer:
    failures_total = 2
    failures_consecutive = 0
    last_success_at = "2026-09-21T22:00:00+00:00"

    def is_active(self):
        return False

    def pending_transaction_kind(self):
        return None


class _FakeControl:
    def automation_available(self):
        return True

    def automation_availability_source(self):
        return "explicit"


class AdminSnapshotTests(unittest.TestCase):
    def _bridge(self):
        state = VistaState()
        state.arming_initialized = True
        state.zone_status_blocks_seen = {1, 2}
        state.zone_partition_blocks_seen = {1, 2}
        state.keypads[1].initialized = True
        state.keypads[1].session_fresh = True
        state.keypads[1].line_1 = "DISARMED        "
        state.keypads[1].line_2 = "READY TO ARM    "

        settings = SimpleNamespace(
            panel=SimpleNamespace(
                host="10.2.2.141",
                port=10001,
                timezone="America/New_York",
            ),
            keypad=SimpleNamespace(partitions=(1,)),
            control=SimpleNamespace(
                enabled=True,
                keypad_enabled=True,
                native_alarm_enabled=False,
            ),
            event_history=SimpleNamespace(
                max_age_days=90,
                max_rows=10000,
            ),
            mqtt=SimpleNamespace(
                tls_enabled=True,
                password="must-not-leak",
                tls_client_key="/secret/private-key.pem",
            ),
            diagnostics=SimpleNamespace(
                max_age_days=30,
                max_rows=25000,
            ),
        )
        metrics = SimpleNamespace(
            status="idle",
            queue_depth=0,
            completed=4,
            uncertain=0,
            failed=0,
            dropped=0,
            last_error="",
            last_completed_at="",
        )
        bridge = SimpleNamespace(
            state=state,
            settings=settings,
            event_store=_FakeEventStore(),
            control=_FakeControl(),
            synchronizer=_FakeSynchronizer(),
            printer=SimpleNamespace(enabled=False, metrics=metrics),
            mqtt=SimpleNamespace(
                connected=True,
                publish_errors=1,
            ),
            diagnostics=SimpleNamespace(
                runtime_state=lambda: {
                    "available": True,
                    "write_errors": 0,
                    "dropped_events": 0,
                    "pending_writes": 0,
                    "writer_alive": True,
                }
            ),
            rx_frames=10,
            rx_bytes=100,
            tx_frames=5,
            tx_bytes=50,
            invalid_frames=1,
            _tx_queue=Queue(),
            _raw_tx_queue=Queue(),
            _telnet=SimpleNamespace(active=True),
            _is_connected=lambda: True,
        )
        return bridge

    def test_snapshot_contains_operational_state(self):
        snapshot = AdminSnapshotBuilder(self._bridge()).build(
            {"id": "ha-user", "display_name": "Administrator"}
        )
        self.assertTrue(snapshot["panel"]["connected"])
        self.assertTrue(snapshot["control"]["keypad_available"])
        self.assertEqual(snapshot["journal"]["count"], 17)
        self.assertTrue(snapshot["keypads"]["1"]["available"])
        self.assertEqual(
            snapshot["keypads"]["1"]["command_topic"],
            "vista/ingress/keypad/1/command",
        )
        self.assertEqual(snapshot["user"]["id"], "ha-user")

    def test_zone_evidence_is_distinct_from_current_conditions(self):
        bridge = self._bridge()
        zone = bridge.state.zones[65]
        zone.partition = 2
        zone.bypassed = True
        zone.bypass_source = "event_05"
        zone.bypass_reported_at = "2026-10-07T12:00:00+00:00"
        builder = AdminSnapshotBuilder(bridge)
        row = builder.build()["zones"][0]
        self.assertEqual(row["zone"], 65)
        self.assertTrue(row["current"])
        self.assertTrue(row["conditions"]["bypassed"])
        bridge.state.reset_connection_derived_annunciators()
        row = builder.build()["zones"][0]
        self.assertFalse(row["current"])
        self.assertTrue(all(value is None for value in row["conditions"].values()))
        self.assertTrue(row["bypass_evidence"]["value"])
        self.assertEqual(row["bypass_evidence"]["source"], "event_05")

    def test_offline_and_automation_suspension_mask_zone_conditions(self):
        bridge = self._bridge()
        bridge.state.zones[1].partition = 1
        builder = AdminSnapshotBuilder(bridge)
        bridge._is_connected = lambda: False
        self.assertFalse(builder.build()["zones"][0]["current"])
        bridge._is_connected = lambda: True
        bridge.control = SimpleNamespace(automation_available=lambda: False,
                                         automation_availability_source=lambda: "communication_off")
        self.assertIsNone(builder.build()["zones"][0]["conditions"]["bypassed"])

    def test_zone_snapshot_reports_completeness_without_exposing_unassigned_zones(self):
        bridge = self._bridge()
        self.assertEqual(AdminSnapshotBuilder(bridge).build()["zones"], [])
        bridge.state.zones[128].partition = 1
        bridge.state.zone_status_blocks_seen = {1}
        snapshot = AdminSnapshotBuilder(bridge).build()
        self.assertEqual(snapshot["synchronizer"]["zone_status_blocks"], [1])
        self.assertIsNone(snapshot["zones"][0]["conditions"]["bypassed"])
        self.assertIsNone(snapshot["zones"][0]["bypass_evidence"]["value"])

    def test_snapshot_includes_bounded_mqtt_watchdog_health(self):
        bridge = self._bridge()
        bridge.mqtt.diagnostic_state = lambda: {
            "transport_generation": 3, "watchdog_restarts": 1,
            "last_puback_age_seconds": 2.5, "heartbeat_pending_seconds": None,
            "transport_session_id": "not-part-of-the-ui-contract",
        }
        snapshot = AdminSnapshotBuilder(bridge).build()
        self.assertEqual(snapshot["mqtt"]["watchdog_restarts"], 1)
        self.assertEqual(snapshot["mqtt"]["last_puback_age_seconds"], 2.5)
        self.assertNotIn("transport_session_id", snapshot["mqtt"])

    def test_snapshot_excludes_credentials(self):
        encoded = json.dumps(AdminSnapshotBuilder(self._bridge()).build())
        self.assertNotIn("must-not-leak", encoded)
        self.assertNotIn("private-key.pem", encoded)


if __name__ == "__main__":
    unittest.main()
