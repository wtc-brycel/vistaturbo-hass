import asyncio
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))

from vista_bridge.config import KeypadSettings, SyncSettings  # noqa: E402
from vista_bridge.protocol import STARTUP_QUERIES  # noqa: E402
from vista_bridge.synchronizer import VistaSynchronizer  # noqa: E402


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
            callback = (
                sync.mark_descriptor_complete
                if label == "zone_descriptor"
                else sync.mark_ready
            )
            asyncio.get_running_loop().call_soon(callback)
            return True, "queued"

        sync = VistaSynchronizer(
            sync_settings(),
            keypad_settings(),
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

    def test_event_refresh_only_queues_configured_partitions(self):
        sync = VistaSynchronizer(
            sync_settings(),
            keypad_settings(),
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
