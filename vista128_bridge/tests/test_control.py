import asyncio
import os
import sys
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))

from vista_bridge.config import ControlSettings  # noqa: E402
from vista_bridge.command_model import (  # noqa: E402
    command_from_request,
    compile_keypad_segments,
)
from vista_bridge.control import VistaControlCoordinator  # noqa: E402
from vista_bridge.state import VistaState  # noqa: E402


class FakeSynchronizer:
    def __init__(self):
        self.lock = asyncio.Lock()
        self.ready_event = asyncio.Event()
        self.keypad_refresh_requests = []
        self.direct_keypad_refreshes = []
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

    def request_keypad_refresh(self, partition):
        self.keypad_refresh_requests.append(partition)

    async def run_keypad_refresh(self, partition):
        self.direct_keypad_refreshes.append(partition)
        return True

    async def run_arming_refresh(self):
        self.arming_refreshes += 1
        return True


class ControlCoordinatorTests(unittest.IsolatedAsyncioTestCase):
    def make_control(self, *, enabled=True, keypad=True, alarm=True):
        self.connected = True
        self.sent = []
        self.results = []
        self.audit = []
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
            self.audit.append,
        )
        control.reset_session()
        return control

    async def test_successful_transaction_can_infer_availability_but_xf_latches_blocked(self):
        control = self.make_control()
        self.assertEqual(control.automation_availability_source(), "unknown")
        self.assertTrue(control.infer_automation_available())
        self.assertTrue(control.automation_available())
        self.assertEqual(control.automation_availability_source(), "inferred")

        control.set_automation_available(False)
        self.assertFalse(control.automation_available())
        self.assertEqual(control.automation_availability_source(), "communication_off")
        self.assertFalse(control.infer_automation_available())
        self.assertFalse(control.automation_available())

        control.set_automation_available(True, source="explicit")
        self.assertTrue(control.automation_available())
        self.assertEqual(control.automation_availability_source(), "explicit")

        control.reset_session()
        self.assertFalse(control.automation_available())
        self.assertEqual(control.automation_availability_source(), "unknown")
        self.assertTrue(control.infer_automation_available())

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
        self.assertEqual(self.sync.keypad_refresh_requests, [1])
        self.assertEqual(self.sync.direct_keypad_refreshes, [])
        self.assertTrue(self.results[-1]["ok"])
        self.assertEqual(self.results[-1]["action"], "keypress")
        self.assertNotIn("key", self.results[-1])

    async def test_keypad_audit_keeps_one_exact_logical_sequence_and_operands(self):
        control = self.make_control()
        control.set_automation_available(True)
        ok, reason = control.enqueue_keypad(
            1,
            "1234#",
            {
                "interaction_id": "interaction-1",
                "started_at": "2026-08-17T09:59:59+00:00",
                "actor_id": "alice-id",
                "actor_name": "Alice",
                "source": "ha_frontend",
                "action": "keypad_sequence",
                "command_sequence": "1234#",
                "operands": {"zone": "7"},
            },
        )
        self.assertEqual((ok, reason), (True, "queued"))
        await control.process_next()
        self.assertEqual(
            {key: value for key, value in self.audit[-1].items() if key != "request_id"},
            {
                "interaction_id": "interaction-1",
                "actor_id": "alice-id",
                "actor_name": "Alice",
                "partition": 1,
                "source": "ha_frontend",
                "started_at": "2026-08-17T09:59:59+00:00",
                "action": "keypad_sequence",
                "command_sequence": "1234#",
                "operands": {"zone": "7"},
                "status": "accepted",
                "ok": True,
            },
        )
        self.assertNotIn("1234", self.results[-1])

    async def test_semantic_arm_prefers_native_command_and_audits_semantics(self):
        control = self.make_control(keypad=True, alarm=True)
        control.set_automation_available(True)
        self.state.partitions[1].raw_mode = "A"
        command = command_from_request(
            {
                "action": "arm",
                "mode": "away",
                "partition": 1,
                "code": "1234",
            },
            source="ha_frontend",
            actor_id="alice-id",
            actor_name="Alice",
            interaction_id="interaction-native",
        )
        self.assertEqual(control.enqueue_command(command), (True, "queued"))
        await control.process_next()
        self.assertTrue(self.sent[0][0].endswith(b"\r\n"))
        self.assertIn(b"AA00123410000000", self.sent[0][0])
        self.assertEqual(self.results[-1]["execution_mechanism"], "native")
        self.assertEqual(self.audit[-1]["command_type"], "arm_away")
        self.assertEqual(self.audit[-1]["code"], "1234")

    async def test_semantic_keypad_fallback_keeps_one_transaction_for_all_segments(self):
        control = self.make_control(keypad=True, alarm=False)
        control.set_automation_available(True)
        command = command_from_request(
            {
                "action": "bypass_zones",
                "partition": 1,
                "code": "1234",
                "zones": [1, 27, 104],
            },
            interaction_id="interaction-keypad",
        )
        self.assertEqual(control.enqueue_command(command), (True, "queued"))
        await control.process_next()
        self.assertEqual(len(self.sent), len(compile_keypad_segments(command)))
        self.assertEqual(self.results[-1]["execution_mechanism"], "keypad")
        self.assertEqual(self.audit[-1]["command_sequence"], "12346001027104**")
        self.assertEqual(self.audit[-1]["command_type"], "zone_bypass")

    async def test_keypad_reservation_rejects_interleaved_interaction_until_complete(self):
        control = self.make_control()
        control.set_automation_available(True)
        self.assertEqual(
            control.enqueue_keypad(
                1,
                "12",
                {
                    "interaction_id": "interaction-a",
                    "interaction_complete": False,
                    "request_id": "segment-a-1",
                },
            ),
            (True, "queued"),
        )
        self.assertEqual(
            control.enqueue_keypad(
                1,
                "34",
                {
                    "interaction_id": "interaction-b",
                    "interaction_complete": False,
                    "request_id": "segment-b-1",
                },
            ),
            (False, "keypad_interaction_busy"),
        )
        self.assertEqual(
            control.enqueue_keypad(
                1,
                "34",
                {
                    "interaction_id": "interaction-a",
                    "interaction_complete": True,
                    "request_id": "segment-a-2",
                },
            ),
            (True, "queued"),
        )
        await control.process_next()
        await control.process_next()
        self.assertEqual(
            [item[0] for item in self.sent],
            [b"0BKS11200FC\r\n", b"0BKS13400F8\r\n"],
        )
        self.assertEqual(
            control.enqueue_keypad(
                1,
                "56",
                {"interaction_id": "interaction-b", "interaction_complete": True},
            ),
            (True, "queued"),
        )

    async def test_keypad_reservation_survives_pause_beyond_legacy_timeout(self):
        control = self.make_control()
        control.set_automation_available(True)
        self.assertEqual(
            control.enqueue_keypad(
                1,
                "12345",
                {"interaction_id": "interaction-a", "interaction_complete": False},
            ),
            (True, "queued"),
        )
        paused_time = time.monotonic() + 7.0
        with patch("vista_bridge.control.time.monotonic", return_value=paused_time):
            self.assertEqual(
                control.enqueue_keypad(
                    1,
                    "6",
                    {"interaction_id": "interaction-b", "interaction_complete": False},
                ),
                (False, "keypad_interaction_busy"),
            )

    async def test_unrelated_native_control_waits_for_open_keypad_interaction(self):
        control = self.make_control(keypad=True, alarm=True)
        control.set_automation_available(True)
        self.assertEqual(
            control.enqueue_keypad(
                1,
                "12",
                {"interaction_id": "interaction-a", "interaction_complete": False},
            ),
            (True, "queued"),
        )
        self.assertEqual(control.enqueue_alarm(1, "ARM_AWAY", "1234"), (True, "queued"))
        self.assertEqual(
            control.enqueue_keypad(
                1,
                "34",
                {"interaction_id": "interaction-a", "interaction_complete": True},
            ),
            (True, "queued"),
        )
        await control.process_next()
        await control.process_next()
        self.assertIn(b"KS", self.sent[0][0])
        self.assertIn(b"KS", self.sent[1][0])
        await control.process_next()
        self.assertIn(b"AA", self.sent[2][0])

    async def test_function_and_panic_tokens_are_not_exposed_by_normal_keypad_control(self):
        control = self.make_control()
        control.set_automation_available(True)
        for key in ("A", "D", "PANIC_A"):
            ok, reason = control.enqueue_keypad(1, key)
            self.assertFalse(ok)
            self.assertEqual(reason, "unsupported_keypad_key")
        self.assertTrue(control.enqueue_keypad(1, "1234")[0])
        self.assertEqual(self.sent, [])

    async def test_rapid_code_digits_are_not_blocked_by_direct_kd_round_trips(self):
        control = self.make_control()
        control.set_automation_available(True)
        self.assertTrue(control.enqueue_keypad(1, "1234")[0])
        self.assertTrue(await control.process_next())
        self.assertEqual(len(self.sent), 1)
        self.assertEqual(self.sent[0][0], b"0DKS112340093\r\n")
        self.assertEqual(self.sync.direct_keypad_refreshes, [])
        self.assertEqual(self.sync.keypad_refresh_requests, [1])
        self.assertTrue(self.results[-1]["ok"])

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
