import asyncio
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))

from vista_bridge.config import ControlSettings  # noqa: E402
from vista_bridge.control import VistaControlCoordinator  # noqa: E402
from vista_bridge.protocol import build_keypad_stroke_command  # noqa: E402
from vista_bridge.state import VistaState  # noqa: E402


class FakeSynchronizer:
    def __init__(self):
        self.lock = asyncio.Lock()
        self.ready_event = asyncio.Event()
        self.keypad_refresh_requests = []

    def begin_external_transaction(self):
        self.ready_event.clear()

    def end_external_transaction(self):
        pass

    async def wait_ready(self, timeout_seconds):
        try:
            await asyncio.wait_for(self.ready_event.wait(), timeout=timeout_seconds)
            return True
        except asyncio.TimeoutError:
            return False

    def request_keypad_refresh(self, partition):
        self.keypad_refresh_requests.append(partition)


class RapidKeypadTests(unittest.IsolatedAsyncioTestCase):
    def make_control(self):
        self.sent = []
        self.results = []
        self.sync = FakeSynchronizer()

        def send_query(data, source, label):
            self.sent.append((data, source, label))
            asyncio.get_running_loop().call_soon(self.sync.ready_event.set)
            return True, "queued"

        control = VistaControlCoordinator(
            ControlSettings(
                enabled=True,
                keypad_enabled=True,
                native_alarm_enabled=True,
                response_timeout_seconds=1,
                verify_delay_ms=0,
            ),
            VistaState(),
            self.sync,
            lambda: True,
            send_query,
            self.results.append,
        )
        control.reset_session()
        control.set_automation_available(True)
        return control

    async def test_rapid_completed_keypresses_queue_in_arrival_order(self):
        control = self.make_control()
        keys = "12341"

        for index, key in enumerate(keys):
            self.assertEqual(
                control.enqueue_keypad(
                    1,
                    key,
                    {
                        "interaction_id": f"keypress-{index}",
                        "audit_interaction_id": "code-off-session",
                        "interaction_complete": True,
                        "source": "ha_frontend",
                    },
                ),
                (True, "queued"),
            )

        for _ in keys:
            self.assertTrue(await control.process_next())

        self.assertEqual(
            [frame for frame, _, _ in self.sent],
            [build_keypad_stroke_command(1, key) for key in keys],
        )
        self.assertTrue(all(result["ok"] for result in self.results))

    async def test_open_interaction_still_blocks_other_keypad_callers(self):
        control = self.make_control()
        self.assertEqual(
            control.enqueue_keypad(
                1,
                "12",
                {
                    "interaction_id": "open-a",
                    "interaction_complete": False,
                },
            ),
            (True, "queued"),
        )
        self.assertEqual(
            control.enqueue_keypad(
                1,
                "3",
                {
                    "interaction_id": "standalone-b",
                    "interaction_complete": True,
                },
            ),
            (False, "keypad_interaction_busy"),
        )
        self.assertEqual(
            control.enqueue_keypad(
                1,
                "34",
                {
                    "interaction_id": "open-a",
                    "interaction_complete": True,
                },
            ),
            (True, "queued"),
        )
