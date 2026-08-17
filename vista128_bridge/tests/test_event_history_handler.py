import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))
sys.path.insert(0, os.path.dirname(__file__))

from fake_paho import install_fake_paho  # noqa: E402

install_fake_paho()

from helpers import make_settings  # noqa: E402
from vista_bridge.event_store import EventStore  # noqa: E402
from vista_bridge.message_handler import ProtocolMessageHandler  # noqa: E402
from vista_bridge.state import VistaState  # noqa: E402


def make_packet(body_without_length_and_checksum: str) -> bytes:
    total_length = 2 + len(body_without_length_and_checksum) + 2
    prefix = f"{total_length:02X}" + body_without_length_and_checksum
    checksum = (-sum(prefix.encode("ascii"))) & 0xFF
    return (prefix + f"{checksum:02X}").encode("ascii")


class FakeMqtt:
    def __init__(self):
        self.live_events = []
        self.history = []
        self.keypad_refresh_side_effects = 0

    def publish_event(self, event, **kwargs):
        self.live_events.append(event)

    def publish_event_history(self, **kwargs):
        self.history.append(kwargs)

    def publish_keypad_state(self, keypad):
        pass

    def publish_partition_state(self, partition):
        pass

    def publish_zone_state(self, zone):
        pass

    def publish_zone_discovery(self, zone):
        pass

    def publish_zone_summaries(self, state):
        pass


class FakePrinter:
    def __init__(self):
        self.events = []

    def enqueue_event(self, **kwargs):
        self.events.append(kwargs)


class FakeSynchronizer:
    def __init__(self):
        self.log_complete = 0
        self.keypad_refreshes = []

    def mark_event_log_complete(self):
        self.log_complete += 1

    def request_keypad_refresh(self, partition):
        self.keypad_refreshes.append(partition)

    def request_full_resync(self, reason):
        pass

    def set_program_mode(self, active):
        pass


class EventHistoryHandlerTests(unittest.TestCase):
    def test_historical_entries_are_persisted_without_live_side_effects(self):
        with tempfile.TemporaryDirectory() as tmp:
            settings = make_settings(spool_path=os.path.join(tmp, "printer.sqlite3"))
            store = EventStore(os.path.join(tmp, "events.sqlite3"))
            state = VistaState()
            mqtt = FakeMqtt()
            printer = FakePrinter()
            sync = FakeSynchronizer()
            handler = ProtocolMessageHandler(settings, state, mqtt, printer, sync, store)

            packet = make_packet("ldF50270001212315082600")
            handler.handle("event_log_entry", packet, "2026-08-17T10:05:00-04:00")

            self.assertEqual(store.stats().count, 1)
            self.assertEqual(mqtt.live_events, [])
            self.assertEqual(printer.events, [])
            self.assertEqual(sync.keypad_refreshes, [])
            self.assertFalse(state.zones[27].faulted)

            handler.handle("event_log_complete", b"08lc0069", "2026-08-17T10:05:02-04:00")
            self.assertEqual(sync.log_complete, 1)
            self.assertEqual(len(mqtt.history), 1)
            self.assertEqual(mqtt.history[0]["count"], 1)
            self.assertEqual(mqtt.history[0]["last_dump_seen"], 1)
            self.assertEqual(mqtt.history[0]["last_dump_inserted"], 1)


if __name__ == "__main__":
    unittest.main()
