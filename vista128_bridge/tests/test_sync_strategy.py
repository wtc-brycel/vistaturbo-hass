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
    async def test_periodic_loop_polls_arming_status_only_without_availability_flap(self):
        connected = True
        sent = []
        invalidated = []
        snapshot_checks = []
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
            on_query_start=lambda query: invalidated.append(query.name),
            on_snapshot_check=lambda: snapshot_checks.append(True),
        )

        await sync.periodic_loop()

        self.assertEqual(
            sent,
            [("periodic", "arming_status", b"08as0064\r\n")],
        )
        self.assertNotIn("zone_status", {label for _, label, _ in sent})
        self.assertEqual(invalidated, [])
        self.assertEqual(snapshot_checks, [True])

    async def test_failed_periodic_reconciliation_invalidates_arming_freshness(self):
        connected = True
        invalidated = []
        snapshot_checks = []

        def send_query(data, source, label):
            nonlocal connected
            connected = False
            return False, "tx_queue_full"

        sync = VistaSynchronizer(
            sync_settings(),
            keypad_disabled(),
            False,
            False,
            lambda: connected,
            send_query,
            lambda: None,
            on_query_start=lambda query: invalidated.append(query.name),
            on_snapshot_check=lambda: snapshot_checks.append(True),
        )

        await sync.periodic_loop()

        self.assertEqual(invalidated, ["arming_status"])
        self.assertEqual(snapshot_checks, [True])
        self.assertEqual(sync.failures_consecutive, 1)

    async def test_post_control_arming_verification_rechecks_without_invalidating_snapshot(self):
        invalidated = []
        snapshot_checks = []
        sync = None

        def send_query(data, source, label):
            loop = asyncio.get_running_loop()
            loop.call_soon(sync.mark_protocol_message, label)
            loop.call_soon(sync.mark_ready)
            return True, "queued"

        sync = VistaSynchronizer(
            sync_settings(),
            keypad_disabled(),
            False,
            False,
            lambda: True,
            send_query,
            lambda: None,
            on_query_start=lambda query: invalidated.append(query.name),
            on_snapshot_check=lambda: snapshot_checks.append(True),
        )

        self.assertTrue(await sync.run_arming_refresh())
        self.assertEqual(invalidated, [])
        self.assertEqual(snapshot_checks, [True])

    async def test_full_resync_retains_zone_snapshot_queries_and_rechecks_freshness(self):
        connected = True
        calls = []
        snapshot_checks = []
        sync = VistaSynchronizer(
            sync_settings(),
            keypad_disabled(),
            False,
            False,
            lambda: connected,
            lambda data, source, label: (True, "queued"),
            lambda: None,
            on_snapshot_check=lambda: snapshot_checks.append(True),
        )
        sync._startup_complete = True

        async def capture_run_sync(queries, *, source, description, **kwargs):
            nonlocal connected
            calls.append((tuple(query.name for query in queries), source, description, kwargs))
            connected = False
            return True

        sync.run_sync = capture_run_sync
        sync.request_full_resync("state_loss")
        await sync.resync_loop()

        self.assertEqual(len(calls), 1)
        names, source, description, kwargs = calls[0]
        self.assertEqual(names, tuple(query.name for query in STARTUP_QUERIES))
        self.assertIn("zone_status", names)
        self.assertEqual(source, "resync")
        self.assertIn("state_loss", description)
        self.assertEqual(kwargs, {})
        self.assertEqual(snapshot_checks, [True])

    async def test_recovery_requests_are_debounced_into_one_full_snapshot(self):
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

        async def capture_run_sync(queries, *, source, description, **kwargs):
            nonlocal connected
            calls.append((tuple(query.name for query in queries), source, description))
            connected = False
            return True

        sync.run_sync = capture_run_sync
        self.assertTrue(sync.request_recovery_resync("invalid frame 1"))
        self.assertTrue(sync.request_recovery_resync("invalid frame 2"))
        await sync.resync_loop()

        self.assertEqual(len(calls), 1)
        self.assertIn("invalid frame 2", calls[0][2])

    async def test_recovery_request_during_active_resync_gets_followup_snapshot(self):
        connected = True
        calls = []
        second_requested = False
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

        async def capture_run_sync(queries, *, source, description, **kwargs):
            nonlocal connected, second_requested
            calls.append((tuple(query.name for query in queries), source, description))
            if not second_requested:
                second_requested = True
                self.assertTrue(sync.request_recovery_resync("corruption during recovery"))
            else:
                connected = False
            return True

        sync.run_sync = capture_run_sync
        self.assertTrue(sync.request_recovery_resync("initial corruption"))
        await sync.resync_loop()

        self.assertEqual(len(calls), 2)
        self.assertIn("initial corruption", calls[0][2])
        self.assertIn("corruption during recovery", calls[1][2])

    async def test_failed_recovery_resync_forces_reconnect(self):
        connected = True
        reconnects = []
        sync = VistaSynchronizer(
            sync_settings(),
            keypad_disabled(),
            False,
            False,
            lambda: connected,
            lambda data, source, label: (True, "queued"),
            lambda: reconnects.append(True),
        )
        sync._startup_complete = True

        async def failed_run_sync(queries, *, source, description, **kwargs):
            return False

        sync.run_sync = failed_run_sync
        self.assertTrue(sync.request_recovery_resync("invalid frame"))
        await sync.resync_loop()

        self.assertEqual(reconnects, [True])

    async def test_recovery_during_startup_is_deferred_until_startup_completes(self):
        connected = True
        sync = VistaSynchronizer(
            sync_settings(),
            keypad_disabled(),
            False,
            False,
            lambda: connected,
            lambda data, source, label: (True, "queued"),
            lambda: None,
        )

        async def successful_startup_sync(queries, *, source, description, **kwargs):
            return True

        sync.run_sync = successful_startup_sync
        self.assertTrue(sync.request_recovery_resync("invalid startup frame"))
        self.assertTrue(sync._recovery_resync_pending)
        self.assertFalse(sync._resync_requested.is_set())

        await sync.startup()

        self.assertTrue(sync._startup_complete)
        self.assertFalse(sync._recovery_resync_pending)
        self.assertTrue(sync._resync_requested.is_set())

    def test_recovery_during_programming_waits_for_program_exit(self):
        sync = VistaSynchronizer(
            sync_settings(),
            keypad_disabled(),
            False,
            False,
            lambda: True,
            lambda data, source, label: (True, "queued"),
            lambda: None,
        )
        sync._startup_complete = True
        sync.set_program_mode(True)

        self.assertTrue(sync.request_recovery_resync("invalid programming frame"))
        self.assertTrue(sync._recovery_resync_pending)
        self.assertFalse(sync._resync_requested.is_set())

        sync.set_program_mode(False)

        self.assertFalse(sync._recovery_resync_pending)
        self.assertTrue(sync._resync_requested.is_set())


if __name__ == "__main__":
    unittest.main()
