import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))
sys.path.insert(0, os.path.dirname(__file__))

from fake_paho import install_fake_paho  # noqa: E402

install_fake_paho()

from helpers import make_settings  # noqa: E402
from vista_bridge.message_handler import ProtocolMessageHandler  # noqa: E402
from vista_bridge.state import VistaState  # noqa: E402


class FakeMqtt:
    def __init__(self):
        self.events = []

    def publish_partition_discovery(self, partition):
        pass

    def publish_partition_state(self, partition):
        pass

    def publish_zone_discovery(self, zone):
        pass

    def publish_zone_state(self, zone):
        pass

    def publish_event(self, event, **kwargs):
        self.events.append((event, kwargs))


class FakePrinter:
    def __init__(self):
        self.events = []

    def enqueue_event(self, **kwargs):
        self.events.append(kwargs)


class FakeSynchronizer:
    def __init__(self):
        self.descriptor_complete = 0
        self.resync = []
        self.program_mode = False

    def mark_descriptor_complete(self):
        self.descriptor_complete += 1

    def request_full_resync(self, reason):
        self.resync.append(reason)

    def set_program_mode(self, active):
        self.program_mode = active


class MessageHandlerTests(unittest.TestCase):
    def setUp(self):
        self.state = VistaState()
        self.mqtt = FakeMqtt()
        self.printer = FakePrinter()
        self.sync = FakeSynchronizer()
        self.handler = ProtocolMessageHandler(
            make_settings(),
            self.state,
            self.mqtt,
            self.printer,
            self.sync,
        )

    def test_descriptor_event_interleave_updates_state(self):
        self.handler.handle(
            "zone_partition",
            b"49ZP10011110000000000011111111111011011111010111000000000000000000000003E",
            "2026-08-16T01:27:44+00:00",
        )
        self.handler.handle(
            "zone_descriptor",
            b'21zd027"GLASS BREAK KITCHEN "003D',
            "2026-08-16T01:27:49+00:00",
        )
        self.handler.handle(
            "system_event",
            b"1BnqF502700012123150826007B",
            "2026-08-16T01:27:51+00:00",
        )
        self.handler.handle(
            "zone_descriptor",
            b'0Dzd000""007A',
            "2026-08-16T01:28:02+00:00",
        )

        self.assertEqual(self.state.zones[27].descriptor, "GLASS BREAK KITCHEN")
        self.assertTrue(self.state.zones[27].faulted)
        self.assertEqual(len(self.mqtt.events), 1)
        self.assertEqual(len(self.printer.events), 1)
        self.assertEqual(self.sync.descriptor_complete, 1)


if __name__ == "__main__":
    unittest.main()
