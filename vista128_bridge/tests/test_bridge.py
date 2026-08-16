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
        bridge.settings = SimpleNamespace(raw_logging=False)
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


if __name__ == "__main__":
    unittest.main()
