import asyncio
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))

from vista_bridge.config import KeypadSettings, SyncSettings  # noqa: E402
from vista_bridge.protocol import parse_keypad_display  # noqa: E402
from vista_bridge.synchronizer import VistaSynchronizer  # noqa: E402


CANCEL_SENT_FRAME = bytes.fromhex(
    "32 39 6b 64 a0 43 41 4e 43 45 4c 20 53 45 4e 54 20 54 4f 20 43 45 "
    "4e 54 52 41 4c 20 20 53 54 41 54 49 4f 4e 31 30 30 34 37"
)


class MarkerlessKeypadResponseTests(unittest.IsolatedAsyncioTestCase):
    async def test_observed_cancel_display_completes_pending_p1_transaction(self):
        report = parse_keypad_display(CANCEL_SENT_FRAME)
        self.assertIsNotNone(report)
        self.assertEqual(report.line_1, "CANCEL SENT TO C")
        self.assertEqual(report.line_2, "ENTRAL  STATION")

        sync = None
        reconnects = []

        def send_query(data, source, label):
            self.assertEqual(data, b"09KD10077\r\n")
            self.assertEqual(source, "keypad")
            self.assertEqual(label, "keypad_display_p1")
            loop = asyncio.get_running_loop()
            loop.call_soon(sync.accept_keypad_response, report)
            loop.call_soon(sync.mark_ready)
            return True, "queued"

        sync = VistaSynchronizer(
            SyncSettings(
                startup_enabled=True,
                initial_delay_ms=0,
                command_delay_ms=0,
                response_timeout_seconds=1,
                periodic_enabled=True,
                periodic_interval_seconds=300,
                reconnect_after_failures=3,
            ),
            KeypadSettings(
                enabled=True,
                partitions=(1,),
                poll_interval_seconds=7,
                event_refresh_delay_ms=250,
            ),
            False,
            False,
            lambda: True,
            send_query,
            lambda: reconnects.append(True),
        )

        self.assertTrue(await sync.run_keypad_refresh(1))
        self.assertEqual(reconnects, [])


if __name__ == "__main__":
    unittest.main()
