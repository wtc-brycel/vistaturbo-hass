import asyncio
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))

from vista_bridge.config import KeypadSettings, SyncSettings  # noqa: E402
from vista_bridge.protocol import KeypadDisplayReport, STARTUP_QUERIES  # noqa: E402
from vista_bridge.synchronizer import VistaSynchronizer  # noqa: E402


def keypad_report(line_1="P1   DISARMED   "):
    return KeypadDisplayReport(
        line_1=line_1,
        line_2="READY TO ARM    ",
        backlight=True,
        ready_led=True,
        trouble_led=False,
        armed_led=False,
        led_status=1,
        raw_display=(line_1 + "READY TO ARM    ").encode("ascii"),
    )


def sync_settings() -> SyncSettings:
    return SyncSettings(
        startup_enabled=True,
        initial_delay_ms=0,
        command_delay_ms=0,
        response_timeout_seconds=1,
        periodic_enabled=True,
        periodic_interval_seconds=300,
        reconnect_after_failures=3,
    )


def keypad_settings() -> KeypadSettings:
    return KeypadSettings(
        enabled=True,
        partitions=(1,),
        poll_interval_seconds=7,
        event_refresh_delay_ms=250,
    )


class SynchronizerTests(unittest.IsolatedAsyncioTestCase):
    async def test_startup_queries_use_query_specific_completion(self):
        sent = []
        sync = None

        def send_query(data, source, label):
            sent.append((source, label, data))
            loop = asyncio.get_running_loop()
            if label == "zone_descriptor":
                loop.call_soon(sync.mark_descriptor_complete)
            else:
                loop.call_soon(sync.mark_protocol_message, label)
                loop.call_soon(sync.mark_ready)
            return True, "queued"

        sync = VistaSynchronizer(
            sync_settings(),
            keypad_settings(),
            False,
            False,
            lambda: True,
            send_query,
            lambda: None,
        )

        ok = await sync.run_sync(
            STARTUP_QUERIES,
            source="test",
            description="test sync",
        )

        self.assertTrue(ok)
        self.assertEqual([label for _, label, _ in sent], [q.name for q in STARTUP_QUERIES])
        self.assertEqual(sync.failures_consecutive, 0)
        self.assertTrue(sync.last_success_at)

    async def test_keypad_refresh_uses_captured_query_and_requires_display(self):
        sent = []
        sync = None

        def send_query(data, source, label):
            sent.append((source, label, data))
            loop = asyncio.get_running_loop()
            loop.call_soon(sync.mark_keypad_response)
            loop.call_soon(sync.mark_ready)
            return True, "queued"

        sync = VistaSynchronizer(
            sync_settings(),
            keypad_settings(),
            False,
            False,
            lambda: True,
            send_query,
            lambda: None,
        )

        ok = await sync.run_keypad_refresh(1)

        self.assertTrue(ok)
        self.assertEqual(sent, [("keypad", "keypad_display_p1", b"09KD10077\r\n")])
        self.assertEqual(sync.failures_total, 0)
        self.assertEqual(sync.failures_consecutive, 0)
        self.assertEqual(sync.last_success_at, "")
        self.assertIsNone(sync.active_keypad_partition())

    async def test_unrelated_ready_cannot_complete_a_new_transaction(self):
        sync = VistaSynchronizer(
            sync_settings(), keypad_settings(), False, False, lambda: True,
            lambda data, source, label: (True, "queued"), lambda: None,
        )
        first = sync._begin_transaction("arming_status", expected_message="arming_status")
        self.assertFalse(sync.mark_ready())
        sync.mark_protocol_message("arming_status")
        self.assertTrue(sync.mark_ready())
        sync._finish_transaction(first)

        second = sync._begin_transaction("zone_status", expected_message="zone_status")
        # This is a delayed ACK from the completed first operation.
        self.assertFalse(sync.mark_ready())
        sync.mark_protocol_message("zone_status")
        self.assertTrue(sync.mark_ready())
        sync._finish_transaction(second)

    async def test_keypad_response_partition_is_checked_against_transaction(self):
        sync = VistaSynchronizer(
            sync_settings(), keypad_settings(), False, False, lambda: True,
            lambda data, source, label: (True, "queued"), lambda: None,
        )
        transaction = sync._begin_transaction(
            "keypad", partition=1, expected_message="keypad_display"
        )
        self.assertIsNone(sync.accept_keypad_response(keypad_report("P2   DISARMED   ")))
        self.assertFalse(transaction.response_event.is_set())
        self.assertEqual(sync.accept_keypad_response(keypad_report()), 1)
        sync.mark_ready()
        sync._finish_transaction(transaction)

    async def test_keypad_response_without_a_partition_marker_is_rejected(self):
        sync = VistaSynchronizer(
            sync_settings(), keypad_settings(), False, False, lambda: True,
            lambda data, source, label: (True, "queued"), lambda: None,
        )
        transaction = sync._begin_transaction(
            "keypad", partition=1, expected_message="keypad_display"
        )
        self.assertIsNone(sync.accept_keypad_response(keypad_report("READY           ")))
        self.assertFalse(transaction.response_event.is_set())
        sync._finish_transaction(transaction)

    async def test_simultaneous_keypad_refreshes_are_serialized(self):
        sent = []
        sync = None

        def send_query(data, source, label):
            sent.append(label)
            partition = int(label.rsplit("p", 1)[-1])
            loop = asyncio.get_running_loop()
            loop.call_soon(sync.accept_keypad_response, keypad_report(f"P{partition}   DISARMED   "))
            loop.call_soon(sync.mark_ready)
            return True, "queued"

        sync = VistaSynchronizer(
            sync_settings(), keypad_settings(), False, False, lambda: True,
            send_query, lambda: None,
        )
        self.assertEqual(await asyncio.gather(sync.run_keypad_refresh(1), sync.run_keypad_refresh(2)), [True, True])
        self.assertEqual(sent, ["keypad_display_p1", "keypad_display_p2"])

    def test_event_refresh_only_queues_configured_partitions(self):
        sync = VistaSynchronizer(
            sync_settings(),
            keypad_settings(),
            False,
            False,
            lambda: True,
            lambda data, source, label: (True, "queued"),
            lambda: None,
        )
        sync.request_keypad_refresh(2)
        self.assertFalse(sync._keypad_refresh_requested.is_set())
        sync.request_keypad_refresh(1)
        self.assertTrue(sync._keypad_refresh_requested.is_set())
        self.assertEqual(sync._keypad_refresh_partitions, {1})


if __name__ == "__main__":
    unittest.main()
