import asyncio
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))

from vista_bridge.config import KeypadSettings, SyncSettings  # noqa: E402
from vista_bridge.protocol import STARTUP_QUERIES  # noqa: E402
from vista_bridge.synchronizer import VistaSynchronizer  # noqa: E402


def sync_settings(*, periodic_interval_seconds: int = 0) -> SyncSettings:
    return SyncSettings(
        startup_enabled=True,
        initial_delay_ms=0,
        command_delay_ms=0,
        response_timeout_seconds=1,
        periodic_enabled=True,
        periodic_interval_seconds=periodic_interval_seconds,
        reconnect_after_failures=3,
    )


def keypad_disabled() -> KeypadSettings:
    return KeypadSettings(
        enabled=False,
        partitions=(),
        poll_interval_seconds=7,
        event_refresh_delay_ms=250,
    )


class SyncStrategyTests(unittest.IsolatedAsyncioTestCase):
    async def test_periodic_loop_polls_arming_status_only(self):
        connected = True
        sent = []
        sync = None

        def is_connected():
            return connected

        def send_query(data, source, label):
            nonlocal connected
            sent.append((source, label, data))
            loop = asyncio.get_running_loop()
            loop.call_soon(sync.mark_protocol_message, label)
            loop.call_soon(sync.mark_ready)
            connected = False
            return True, "queued"

        sync = VistaSynchronizer(
            sync_settings(),
            keypad_disabled(),
            False,
            False,
            is_connected,
            send_query,
            lambda: None,
        )

        await sync.periodic_loop()

        self.assertEqual(
            sent,
            [("periodic", "arming_status", b"08as0064\r\n")],
        )
        self.assertNotIn("zone_status", {label for _, label, _ in sent})

    async def test_full_resync_retains_zone_snapshot_queries(self):
        connected = True
        calls = []
        sync = VistaSynchronizer(
            sync_settings(),
            keypad_disabled(),
            False,
            False,
            lambda: connected,
            lambda data, source, label: (True, "queued"),
            lambda: None,
        )
        sync._startup_complete = True

        async def capture_run_sync(queries, *, source, description):
            nonlocal connected
            calls.append((tuple(query.name for query in queries), source, description))
            connected = False
            return True

        sync.run_sync = capture_run_sync
        sync.request_full_resync("state_loss")
        await sync.resync_loop()

        self.assertEqual(len(calls), 1)
        names, source, description = calls[0]
        self.assertEqual(names, tuple(query.name for query in STARTUP_QUERIES))
        self.assertIn("zone_status", names)
        self.assertEqual(source, "resync")
        self.assertIn("state_loss", description)


if __name__ == "__main__":
    unittest.main()
