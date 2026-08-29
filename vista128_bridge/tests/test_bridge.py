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
    def publish(self, *args, **kwargs):
        pass

    def publish_json(self, *args, **kwargs):
        pass


class FakeSynchronizer:
    def __init__(self):
        self.ready_count = 0

    def mark_ready(self):
        self.ready_count += 1


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
        bridge.synchronizer = FakeSynchronizer()
        bridge.handler = FakeHandler()
        return bridge

    def test_invalid_ready_packet_does_not_complete_sync(self):
        bridge = self.make_bridge()
        bridge._handle_frame(RawFrame.create(b"08OK009F", "crlf"))
        self.assertEqual(bridge.synchronizer.ready_count, 0)
        self.assertEqual(bridge.invalid_frames, 1)
        self.assertEqual(bridge.handler.calls, [])

    def test_valid_ready_packet_completes_sync(self):
        bridge = self.make_bridge()
        bridge._handle_frame(RawFrame.create(b"08OK009E", "crlf"))
        self.assertEqual(bridge.synchronizer.ready_count, 1)
        self.assertEqual(bridge.invalid_frames, 0)
        self.assertEqual(len(bridge.handler.calls), 1)

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
