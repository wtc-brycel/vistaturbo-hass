import os
import sys
import unittest
from types import SimpleNamespace

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))
sys.path.insert(0, os.path.dirname(__file__))

from fake_paho import install_fake_paho  # noqa: E402

install_fake_paho()

from vista_bridge.bridge import VistaBridge  # noqa: E402
from vista_bridge.framing import RawFrame  # noqa: E402
from vista_bridge.bridge import TxItem  # noqa: E402


class FakeMqtt:
    def __init__(self):
        self.published = []
        self.alarm_state_publishes = 0

    def publish(self, *args, **kwargs):
        self.published.append((args, kwargs))

    def publish_json(self, *args, **kwargs):
        self.published.append((args, kwargs))

    def publish_alarm_states(self, state):
        self.alarm_state_publishes += 1


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
