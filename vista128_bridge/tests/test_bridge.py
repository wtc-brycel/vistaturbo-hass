import os
import queue
import sys
import tempfile
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))
sys.path.insert(0, os.path.dirname(__file__))

from fake_paho import install_fake_paho  # noqa: E402

install_fake_paho()

from vista_bridge.bridge import VistaBridge  # noqa: E402
from vista_bridge.diagnostics import DiagnosticEvents as DE, DiagnosticJournal  # noqa: E402
from vista_bridge.framing import RawFrame  # noqa: E402
from vista_bridge.bridge import TxItem  # noqa: E402


class FakeMqtt:
    def __init__(self):
        self.published = []
        self.alarm_state_publishes = 0
        self.discovery_publishes = 0
        self.zone_summary_publishes = 0
        self.publish_errors = 0
        self.connected = True

    def publish(self, *args, **kwargs):
        self.published.append((args, kwargs))
        return True

    def publish_json(self, *args, **kwargs):
        self.published.append((args, kwargs))

    def publish_alarm_states(self, state):
        self.alarm_state_publishes += 1

    def publish_discovery(self):
        self.discovery_publishes += 1

    def publish_zone_summaries(self, state):
        self.zone_summary_publishes += 1


class FakeState:
    def __init__(self):
        self.query_snapshots = []

    def begin_query_snapshot(self, query_name):
        self.query_snapshots.append(query_name)


class FakeSynchronizer:
    def __init__(self):
        self.ready_count = 0
        self.recovery_requests = []
        self.transaction_kind = "arming_status"

    def pending_transaction_kind(self):
        return self.transaction_kind

    def mark_ready(self):
        self.ready_count += 1
        return True

    def request_recovery_resync(self, reason):
        self.recovery_requests.append(reason)
        return True


class FakeControl:
    def __init__(self):
        self.infer_count = 0
        self.infer_result = True

    def infer_automation_available(self):
        self.infer_count += 1
        return self.infer_result


class FakeHandler:
    def __init__(self):
        self.calls = []

    def handle(self, *args):
        self.calls.append(args)


class BridgeFrameTests(unittest.TestCase):
    def make_bridge(self):
        bridge = VistaBridge.__new__(VistaBridge)
        bridge.rx_frames = 0
        bridge.invalid_frames = 0
        bridge.settings = SimpleNamespace(raw_logging=False, raw_mqtt_enabled=False)
        bridge.mqtt = FakeMqtt()
        bridge.state = FakeState()
        bridge.synchronizer = FakeSynchronizer()
        bridge.control = FakeControl()
        bridge.handler = FakeHandler()
        return bridge

    def test_invalid_ready_packet_does_not_complete_sync_and_requests_recovery(self):
        bridge = self.make_bridge()
        bridge._handle_frame(RawFrame.create(b"08OK009F", "crlf"))
        self.assertEqual(bridge.synchronizer.ready_count, 0)
        self.assertEqual(bridge.control.infer_count, 0)
        self.assertEqual(bridge.invalid_frames, 1)
        self.assertEqual(bridge.handler.calls, [])
        self.assertEqual(bridge.state.query_snapshots, ["zone_status"])
        self.assertEqual(bridge.synchronizer.recovery_requests, ["invalid panel frame"])
        self.assertEqual(bridge.mqtt.alarm_state_publishes, 1)
        self.assertIn(
            (("panel/state_fresh", "OFF"), {"retain": True, "qos": 1}),
            bridge.mqtt.published,
        )

    def test_invalid_frame_diagnostics_are_coalesced_during_corruption_burst(self):
        bridge = self.make_bridge()
        events = []
        bridge._diagnostic_record = lambda event_type, **kwargs: events.append(
            (event_type, kwargs)
        )

        with patch("vista_bridge.bridge.time.monotonic", side_effect=[100.0, 110.0]):
            bridge._handle_frame(RawFrame.create(b"08OK009F", "crlf"))
            bridge._handle_frame(RawFrame.create(b"08OK009F", "crlf"))

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0][0], DE.INVALID_FRAME)
        self.assertEqual(
            events[0][1]["details"]["occurrences_since_last_report"],
            1,
        )
        self.assertEqual(bridge.invalid_frames, 2)
        self.assertEqual(bridge._invalid_frames_since_report, 1)

    def test_valid_ready_packet_completes_sync_without_recovery(self):
        bridge = self.make_bridge()
        bridge.control.infer_result = False
        bridge._handle_frame(RawFrame.create(b"08OK009E", "crlf"))
        self.assertEqual(bridge.synchronizer.ready_count, 1)
        self.assertEqual(bridge.invalid_frames, 0)
        self.assertEqual(len(bridge.handler.calls), 1)
        self.assertEqual(bridge.state.query_snapshots, [])
        self.assertEqual(bridge.synchronizer.recovery_requests, [])

    def test_successful_read_transaction_infers_automation_available(self):
        bridge = self.make_bridge()
        bridge.synchronizer.transaction_kind = "arming_status"

        bridge._handle_frame(RawFrame.create(b"08OK009E", "crlf"))

        self.assertEqual(bridge.control.infer_count, 1)
        self.assertIn(
            (("panel/automation_available", "ON"), {"retain": True, "qos": 1}),
            bridge.mqtt.published,
        )
        self.assertIn(
            (
                ("panel/automation_availability_source", "inferred"),
                {"retain": True, "qos": 1},
            ),
            bridge.mqtt.published,
        )

    def test_unowned_ready_does_not_infer_automation_available(self):
        bridge = self.make_bridge()
        bridge.synchronizer.transaction_kind = None

        bridge._handle_frame(RawFrame.create(b"08OK009E", "crlf"))

        self.assertEqual(bridge.control.infer_count, 0)

    def test_mqtt_recovery_replays_discovery_and_current_state(self):
        bridge = VistaBridge.__new__(VistaBridge)
        bridge.mqtt = FakeMqtt()
        bridge.state = SimpleNamespace(live_snapshot_complete=True)
        bridge.control = SimpleNamespace(
            automation_available=lambda: True,
            automation_availability_source=lambda: "inferred",
        )
        metrics_calls = []
        dynamic_calls = []
        bridge._publish_metrics = lambda: metrics_calls.append(True)
        bridge._publish_dynamic_state = (
            lambda *, include_discovery=False: dynamic_calls.append(include_discovery)
        )

        self.assertTrue(bridge._publish_mqtt_recovery_snapshot())

        self.assertEqual(bridge.mqtt.discovery_publishes, 1)
        self.assertEqual(bridge.mqtt.zone_summary_publishes, 1)
        self.assertEqual(bridge.mqtt.alarm_state_publishes, 1)
        self.assertEqual(metrics_calls, [True])
        self.assertEqual(dynamic_calls, [True])
        self.assertIn(
            (("panel/state_fresh", "ON"), {"retain": True, "qos": 1}),
            bridge.mqtt.published,
        )
        self.assertIn(
            (("panel/automation_available", "ON"), {"retain": True, "qos": 1}),
            bridge.mqtt.published,
        )
        self.assertIn(
            (
                ("panel/automation_availability_source", "inferred"),
                {"retain": True, "qos": 1},
            ),
            bridge.mqtt.published,
        )
        self.assertEqual(
            bridge.mqtt.published[-1],
            (("bridge/availability", "online"), {"retain": True, "qos": 1}),
        )

    def test_mqtt_recovery_does_not_mark_online_after_publish_error(self):
        bridge = VistaBridge.__new__(VistaBridge)
        bridge.mqtt = FakeMqtt()
        bridge.state = SimpleNamespace(live_snapshot_complete=True)
        bridge.control = SimpleNamespace(
            automation_available=lambda: True,
            automation_availability_source=lambda: "inferred",
        )
        bridge._publish_metrics = lambda: setattr(
            bridge.mqtt, "publish_errors", bridge.mqtt.publish_errors + 1
        )
        bridge._publish_dynamic_state = lambda **kwargs: None

        self.assertFalse(bridge._publish_mqtt_recovery_snapshot())
        self.assertNotIn(
            (("bridge/availability", "online"), {"retain": True, "qos": 1}),
            bridge.mqtt.published,
        )

    def test_health_snapshot_is_bounded_and_contains_both_health_planes(self):
        with tempfile.TemporaryDirectory() as tmp:
            bridge = VistaBridge.__new__(VistaBridge)
            bridge.settings = SimpleNamespace(
                diagnostics=SimpleNamespace(health_snapshot_interval_seconds=900)
            )
            bridge.diagnostics = DiagnosticJournal(
                os.path.join(tmp, "diagnostics.sqlite3")
            )
            bridge._started_monotonic = 100.0
            bridge._last_health_snapshot_monotonic = 0.0
            bridge._panel_connected = threading.Event()
            bridge._panel_connected.set()
            bridge.state = SimpleNamespace(
                live_snapshot_complete=True,
                session_generation=4,
            )
            bridge.mqtt = SimpleNamespace(
                diagnostic_state=lambda now: {
                    "connected": True,
                    "transport_generation": 3,
                    "last_puback_age_seconds": 1.5,
                }
            )
            bridge.synchronizer = SimpleNamespace(
                last_success_at="2026-09-23T18:00:00+00:00",
                failures_consecutive=0,
            )
            bridge.rx_frames = 100
            bridge.rx_bytes = 2000
            bridge.tx_frames = 25
            bridge.tx_bytes = 500
            bridge.invalid_frames = 1
            bridge._tx_queue = queue.Queue()
            bridge._raw_tx_queue = queue.Queue()
            bridge.printer = SimpleNamespace(
                metrics=SimpleNamespace(status="idle", queue_depth=0)
            )

            bridge._maybe_record_health_snapshot(now=1000.0)
            bridge._maybe_record_health_snapshot(now=1100.0)

            records = bridge.diagnostics.recent(
                event_type=DE.HEALTH_SNAPSHOT,
                order="oldest",
            )
            self.assertEqual(len(records), 1)
            details = records[0].details
            self.assertTrue(details["panel_connected"])
            self.assertTrue(details["panel_state_fresh"])
            self.assertEqual(details["state_session_generation"], 4)
            self.assertTrue(details["ha_transport"]["connected"])
            self.assertEqual(details["ha_transport"]["transport_generation"], 3)
            self.assertEqual(details["tx_queue_depth"], 0)

    def test_control_and_raw_tx_logs_redact_payloads(self):
        bridge = self.make_bridge()
        bridge.settings = SimpleNamespace(raw_logging=True, raw_mqtt_enabled=False)
        with self.assertLogs("vista_bridge.bridge", level="INFO") as logs:
            bridge._log_tx(TxItem("control", "keypad_p1", b"1234"))
            bridge._log_tx(TxItem("debug", "raw", b"1234"))
        output = "\n".join(logs.output)
        self.assertNotIn("1234", output)
        self.assertIn("payload redacted", output)


if __name__ == "__main__":
    unittest.main()
