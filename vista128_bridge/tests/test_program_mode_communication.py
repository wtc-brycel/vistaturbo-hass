import asyncio
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
from vista_bridge.synchronizer import VistaSynchronizer  # noqa: E402


class FakeMqtt:
    def __init__(self):
        self.published = []
        self.alarm_publish_calls = 0

    def publish(self, topic, payload, **kwargs):
        self.published.append((topic, payload, kwargs))

    def publish_alarm_states(self, state):
        self.alarm_publish_calls += 1


class FakePrinter:
    pass


class FakeControl:
    def __init__(self):
        self.availability = []

    def set_automation_available(self, available, *, source="explicit"):
        self.availability.append((available, source))
        return True


class ProgramModeCommunicationTests(unittest.IsolatedAsyncioTestCase):
    def make_handler(self):
        settings = make_settings()
        reconnects = []
        state = VistaState()
        state.arming_initialized = True
        state.zone_status_initialized = True
        state.zone_partition_initialized = True
        state.zone_status_blocks_seen.update({1, 2})
        state.zone_partition_blocks_seen.update({1, 2})
        sync = VistaSynchronizer(
            settings.sync,
            settings.keypad,
            False,
            False,
            lambda: True,
            lambda data, source, label: (True, "queued"),
            lambda: reconnects.append(True),
        )
        mqtt = FakeMqtt()
        control = FakeControl()
        handler = ProtocolMessageHandler(
            settings,
            state,
            mqtt,
            FakePrinter(),
            sync,
            control=control,
        )
        return state, sync, mqtt, control, handler, reconnects

    async def test_communication_off_completes_inflight_control_without_reconnect(self):
        state, sync, mqtt, control, handler, reconnects = self.make_handler()
        transaction = sync._begin_transaction("control")
        waiter = asyncio.create_task(sync.wait_ready(1))
        await asyncio.sleep(0)

        handler.handle(
            "communication_off",
            b"08XF009A",
            "2026-09-10T22:12:24-04:00",
        )

        self.assertTrue(await waiter)
        # set_program_mode remains the synchronizer's quiesce gate for now, but
        # XF itself is not treated as proof of installer programming.
        self.assertTrue(sync._program_mode)
        self.assertFalse(handler._programming_active)
        self.assertTrue(transaction.ready_event.is_set())
        self.assertEqual(reconnects, [])
        self.assertFalse(state.live_snapshot_complete)
        self.assertGreaterEqual(mqtt.alarm_publish_calls, 1)
        self.assertIn(
            ("panel/state_fresh", "OFF", {"retain": True, "qos": 1}),
            mqtt.published,
        )
        self.assertIn(
            ("panel/automation_available", "OFF", {"retain": True, "qos": 1}),
            mqtt.published,
        )
        self.assertIn(
            (
                "panel/automation_availability_source",
                "communication_off",
                {"retain": True, "qos": 1},
            ),
            mqtt.published,
        )
        self.assertEqual(control.availability[-1], (False, "explicit"))
        sync._finish_transaction(transaction)

    async def test_explicit_program_event_labels_following_xf_as_programming(self):
        state, sync, mqtt, control, handler, reconnects = self.make_handler()
        handler._handle_system_event_side_effects("AD")

        handler.handle(
            "communication_off",
            b"08XF009A",
            "2026-09-10T22:12:24-04:00",
        )

        self.assertTrue(handler._programming_active)
        self.assertTrue(sync._program_mode)
        self.assertIn(
            (
                "panel/automation_availability_source",
                "programming",
                {"retain": True, "qos": 1},
            ),
            mqtt.published,
        )
        self.assertEqual(reconnects, [])

    async def test_communication_on_leaves_quiesced_mode_and_requests_resync(self):
        state, sync, mqtt, control, handler, reconnects = self.make_handler()
        sync._startup_complete = True
        handler._programming_active = True
        sync.set_program_mode(True)

        handler.handle(
            "communication_on",
            b"08XN00A2",
            "2026-09-10T22:14:00-04:00",
        )

        self.assertFalse(handler._programming_active)
        self.assertFalse(sync._program_mode)
        self.assertTrue(sync._resync_requested.is_set())
        self.assertFalse(state.live_snapshot_complete)
        self.assertEqual(reconnects, [])
        self.assertIn(
            ("panel/automation_available", "ON", {"retain": True, "qos": 1}),
            mqtt.published,
        )
        self.assertEqual(control.availability[-1], (True, "explicit"))


if __name__ == "__main__":
    unittest.main()
