import asyncio
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))

from vista_bridge.config import ControlSettings  # noqa: E402
from vista_bridge.control import VistaControlCoordinator  # noqa: E402
from vista_bridge.state import VistaState  # noqa: E402


class FakeSynchronizer:
    def __init__(self):
        self.lock = asyncio.Lock()
        self.ready_event = asyncio.Event()
        self.keypad_refreshes = []
        self.arming_refreshes = 0
        self.active = False

    def begin_external_transaction(self):
        self.active = True
        self.ready_event.clear()

    def end_external_transaction(self):
        self.active = False

    async def wait_ready(self, timeout_seconds):
        try:
            await asyncio.wait_for(self.ready_event.wait(), timeout=timeout_seconds)
            return True
        except asyncio.TimeoutError:
            return False

    async def run_keypad_refresh(self, partition):
        self.keypad_refreshes.append(partition)
        return True

    async def run_arming_refresh(self):
        self.arming_refreshes += 1
        return True


class ControlCoordinatorTests(unittest.IsolatedAsyncioTestCase):
    def make_control(self, *, enabled=True, keypad=True, alarm=True):
        self.connected = True
        self.sent = []
        self.results = []
        self.state = VistaState()
        self.sync = FakeSynchronizer()

        def send_query(data, source, label):
            self.sent.append((data, source, label))
            asyncio.get_running_loop().call_soon(self.sync.ready_event.set)
            return True, "queued"

        control = VistaControlCoordinator(
            ControlSettings(
                enabled=enabled,
                keypad_enabled=keypad,
                native_alarm_enabled=alarm,
                response_timeout_seconds=1,
                verify_delay_ms=0,
            ),
            self.state,
            self.sync,
            lambda: self.connected,
            send_query,
            self.results.append,
        )
        control.reset_session()
        return control

    async def test_keypad_requires_automation_on_and_never_echoes_key(self):
        control = self.make_control()
        ok, reason = control.enqueue_keypad(1, "1")
        self.assertFalse(ok)
        self.assertEqual(reason, "automation_interface_unavailable")

        control.set_automation_available(True)
        ok, reason = control.enqueue_keypad(1, "1")
        self.assertTrue(ok)
        self.assertEqual(reason, "queued")
        self.assertTrue(await control.process_next())
        self.assertEqual(self.sent[0][0], b"0AKS11002F\r\n")
        self.assertEqual(self.sync.keypad_refreshes, [1])
        self.assertTrue(self.results[-1]["ok"])
        self.assertEqual(self.results[-1]["action"], "keypress")
        self.assertNotIn("key", self.results[-1])

    async def test_function_letter_is_rejected_not_reencoded_as_star(self):
        control = self.make_control()
        control.set_automation_available(True)
        ok, reason = control.enqueue_keypad(1, "A")
        self.assertFalse(ok)
        self.assertIn("unsupported keypad keystroke", reason)
        self.assertEqual(self.sent, [])

    async def test_native_alarm_verifies_partition_mode(self):
        control = self.make_control()
        control.set_automation_available(True)
        self.state.partitions[1].raw_mode = "A"
        ok, _ = control.enqueue_alarm(1, "ARM_AWAY", "1234")
        self.assertTrue(ok)
        await control.process_next()
        self.assertEqual(self.sent[0][0], b"16AA00123410000000000C\r\n")
        self.assertEqual(self.sync.arming_refreshes, 1)
        self.assertTrue(self.results[-1]["ok"])
        self.assertEqual(self.results[-1]["status"], "confirmed")
        self.assertNotIn("code", self.results[-1])

    async def test_native_alarm_reports_verification_mismatch(self):
        control = self.make_control()
        control.set_automation_available(True)
        self.state.partitions[1].raw_mode = "D"
        ok, _ = control.enqueue_alarm(1, "ARM_AWAY", "1234")
        self.assertTrue(ok)
        await control.process_next()
        self.assertFalse(self.results[-1]["ok"])
        self.assertEqual(self.results[-1]["status"], "verification_mismatch")

    async def test_pending_requests_are_discarded_across_session_reset(self):
        control = self.make_control()
        control.set_automation_available(True)
        self.assertTrue(control.enqueue_keypad(1, "2")[0])
        control.reset_session()
        self.assertFalse(await control.process_next())
        self.assertEqual(self.sent, [])
        self.assertEqual(self.results[-1]["status"], "panel_session_reset")

    async def test_global_and_feature_gates(self):
        control = self.make_control(enabled=False)
        control.set_automation_available(True)
        self.assertEqual(control.enqueue_keypad(1, "1"), (False, "control_disabled"))

        control = self.make_control(keypad=False)
        control.set_automation_available(True)
        self.assertEqual(control.enqueue_keypad(1, "1"), (False, "keypad_control_disabled"))

        control = self.make_control(alarm=False)
        control.set_automation_available(True)
        self.assertEqual(
            control.enqueue_alarm(1, "DISARM", "1234"),
            (False, "native_alarm_control_disabled"),
        )


if __name__ == "__main__":
    unittest.main()
