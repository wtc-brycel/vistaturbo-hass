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

    def publish(self, topic, payload, **kwargs):
        self.published.append((topic, payload, kwargs))


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
            VistaState(),
            mqtt,
            FakePrinter(),
            sync,
            control=control,
        )
        return sync, mqtt, control, handler, reconnects

    async def test_communication_off_completes_inflight_control_without_reconnect(self):
        sync, mqtt, control, handler, reconnects = self.make_handler()
        transaction = sync._begin_transaction("control")
        waiter = asyncio.create_task(sync.wait_ready(1))
        await asyncio.sleep(0)

        handler.handle(
            "communication_off",
            b"08XF009A",
            "2026-09-10T22:12:24-04:00",
        )

        self.assertTrue(await waiter)
        self.assertTrue(sync._program_mode)
        self.assertTrue(transaction.ready_event.is_set())
        self.assertEqual(reconnects, [])
        self.assertIn(
            ("panel/automation_available", "OFF", {"retain": True, "qos": 1}),
            mqtt.published,
        )
        self.assertEqual(control.availability[-1], (False, "explicit"))
        sync._finish_transaction(transaction)

    async def test_communication_on_leaves_program_mode_and_requests_resync(self):
        sync, mqtt, control, handler, reconnects = self.make_handler()
        sync._startup_complete = True
        sync.set_program_mode(True)

        handler.handle(
            "communication_on",
            b"08XN00A2",
            "2026-09-10T22:14:00-04:00",
        )

        self.assertFalse(sync._program_mode)
        self.assertTrue(sync._resync_requested.is_set())
        self.assertEqual(reconnects, [])
        self.assertIn(
            ("panel/automation_available", "ON", {"retain": True, "qos": 1}),
            mqtt.published,
        )
        self.assertEqual(control.availability[-1], (True, "explicit"))


if __name__ == "__main__":
    unittest.main()
