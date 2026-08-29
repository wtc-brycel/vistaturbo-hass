import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))
sys.path.insert(0, os.path.dirname(__file__))

from fake_paho import install_fake_paho  # noqa: E402

install_fake_paho()

from helpers import make_settings  # noqa: E402
from vista_bridge.synchronizer import VistaSynchronizer  # noqa: E402
from vista_bridge.message_handler import ProtocolMessageHandler  # noqa: E402
from vista_bridge.state import VistaState  # noqa: E402


class FakeMqtt:
    def __init__(self):
        self.events = []
        self.summary_calls = 0
        self.keypad_discovery = []
        self.keypad_states = []

    def publish_partition_discovery(self, partition):
        pass

    def publish_partition_state(self, partition):
        pass

    def publish_keypad_discovery(self, partition):
        self.keypad_discovery.append(partition)

    def publish_keypad_state(self, keypad):
        self.keypad_states.append(keypad)

    def publish_alarm_states(self, state):
        pass

    def publish_zone_discovery(self, zone):
        pass

    def publish_zone_state(self, zone):
        pass

    def publish_zone_summaries(self, state):
        self.summary_calls += 1

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
        self.keypad_response = 0
        self.keypad_partition = None
        self.keypad_refreshes = []
        self.resync = []
        self.program_mode = False

    def mark_descriptor_complete(self):
        self.descriptor_complete += 1

    def mark_keypad_response(self):
        self.keypad_response += 1

    def active_keypad_partition(self):
        return self.keypad_partition

    def request_keypad_refresh(self, partition):
        self.keypad_refreshes.append(partition)

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

    def test_captured_keypad_display_updates_partition_keypad(self):
        self.sync.keypad_partition = 1
        self.handler.handle(
            "keypad_display",
            b"29kd\xd01   DISARMED   BYPAS-RDY TO ARM100CD",
            "2026-08-16T13:22:28-04:00",
        )

        keypad = self.state.keypads[1]
        self.assertTrue(keypad.initialized)
        self.assertEqual(keypad.line_1, "P1   DISARMED   ")
        self.assertEqual(keypad.line_2, "BYPAS-RDY TO ARM")
        self.assertTrue(keypad.ready_led)
        self.assertTrue(keypad.backlight)
        self.assertEqual(self.sync.keypad_response, 1)
        self.assertEqual(self.mqtt.keypad_discovery, [1])
        self.assertEqual(len(self.mqtt.keypad_states), 1)

    def test_delayed_keypad_response_cannot_update_another_partition(self):
        settings = make_settings()
        sync = VistaSynchronizer(
            settings.sync,
            settings.keypad,
            False,
            False,
            lambda: True,
            lambda data, source, label: (True, "queued"),
            lambda: None,
        )
        transaction = sync._begin_transaction(
            "keypad", partition=1, expected_message="keypad_display"
        )
        handler = ProtocolMessageHandler(
            settings,
            self.state,
            self.mqtt,
            self.printer,
            sync,
        )
        def packet(partition: int) -> bytes:
            line_1 = f"{partition}   DISARMED   ".encode("ascii")
            line_2 = b"READY TO ARM    "
            return b"29kd\xd0" + line_1 + line_2 + b"100CD"

        handler.handle("keypad_display", packet(2), "2026-08-16T13:22:28-04:00")
        self.assertFalse(self.state.keypads[1].initialized)
        self.assertFalse(transaction.response_event.is_set())

        handler.handle("keypad_display", packet(1), "2026-08-16T13:22:29-04:00")
        self.assertTrue(self.state.keypads[1].initialized)
        self.assertEqual(self.state.keypads[1].line_1[:2], "P1")
        sync._finish_transaction(transaction)

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
        self.assertGreaterEqual(self.mqtt.summary_calls, 2)
        self.assertEqual(len(self.printer.events), 1)
        self.assertEqual(self.sync.descriptor_complete, 1)
        self.assertIn(1, self.sync.keypad_refreshes)

    def test_configured_fault_zone_increments_keypad_chime_sequence(self):
        handler = ProtocolMessageHandler(
            make_settings(chime_zones=(27,)),
            self.state,
            self.mqtt,
            self.printer,
            self.sync,
        )
        self.sync.keypad_partition = 1
        handler.handle(
            "keypad_display",
            b"29kd\xd01   DISARMED   BYPAS-RDY TO ARM100CD",
            "2026-08-16T13:22:28-04:00",
        )
        self.state.zones[27].partition = 1
        self.state.zones[27].descriptor = "GLASS BREAK KITCHEN"
        self.state.arming_initialized = True
        self.state.partitions[1].raw_mode = "D"
        before = len(self.mqtt.keypad_states)
        handler.handle(
            "system_event",
            b"1BnqF502700012123150826007B",
            "2026-08-16T13:23:00-04:00",
        )
        keypad = self.state.keypads[1]
        self.assertEqual(keypad.chime_sequence, 1)
        self.assertEqual(keypad.chime_zone, 27)
        self.assertEqual(keypad.chime_descriptor, "GLASS BREAK KITCHEN")
        self.assertGreater(len(self.mqtt.keypad_states), before)

    def test_duplicate_fault_event_does_not_chime_twice(self):
        handler = ProtocolMessageHandler(
            make_settings(chime_zones=(27,)), self.state, self.mqtt, self.printer, self.sync
        )
        self.state.zones[27].partition = 1
        self.state.arming_initialized = True
        self.state.partitions[1].raw_mode = "D"
        packet = b"1BnqF502700012123150826007B"
        handler.handle("system_event", packet, "2026-08-16T13:23:00-04:00")
        handler.handle("system_event", packet, "2026-08-16T13:23:01-04:00")
        self.assertEqual(self.state.keypads[1].chime_sequence, 1)

    def test_configured_fault_does_not_chime_while_armed(self):
        handler = ProtocolMessageHandler(
            make_settings(chime_zones=(27,)), self.state, self.mqtt, self.printer, self.sync
        )
        self.state.zones[27].partition = 1
        self.state.arming_initialized = True
        self.state.partitions[1].raw_mode = "A"
        handler.handle(
            "system_event",
            b"1BnqF502700012123150826007B",
            "2026-08-16T13:23:00-04:00",
        )
        self.assertEqual(self.state.keypads[1].chime_sequence, 0)

    def test_configured_fault_waits_for_authoritative_arming_state(self):
        handler = ProtocolMessageHandler(
            make_settings(chime_zones=(27,)), self.state, self.mqtt, self.printer, self.sync
        )
        self.state.zones[27].partition = 1
        handler.handle(
            "system_event",
            b"1BnqF502700012123150826007B",
            "2026-08-16T13:23:00-04:00",
        )
        self.assertEqual(self.state.keypads[1].chime_sequence, 0)

    def test_unlisted_fault_zone_does_not_chime(self):
        handler = ProtocolMessageHandler(
            make_settings(chime_zones=(28,)),
            self.state,
            self.mqtt,
            self.printer,
            self.sync,
        )
        handler.handle(
            "system_event",
            b"1BnqF502700012123150826007B",
            "2026-08-16T13:23:00-04:00",
        )
        self.assertEqual(self.state.keypads[1].chime_sequence, 0)

    def test_captured_bypass_event_refreshes_zone_summaries(self):
        self.handler.handle(
            "zone_partition",
            b"49ZP10011110000000000011111111111011011111010111000000000000000000000003E",
            "2026-08-16T01:27:44+00:00",
        )
        before = self.mqtt.summary_calls
        self.handler.handle(
            "system_event",
            b"1Bnq0503400214423150826008C",
            "2026-08-16T01:50:02+00:00",
        )
        self.assertTrue(self.state.zones[34].bypassed)
        self.assertEqual(self.mqtt.summary_calls, before + 1)
        self.assertEqual(self.sync.keypad_refreshes[-1], 1)


if __name__ == "__main__":
    unittest.main()
