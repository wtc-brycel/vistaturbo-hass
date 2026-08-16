import asyncio
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))

from vista_bridge.config import SyncSettings  # noqa: E402
from vista_bridge.protocol import STARTUP_QUERIES  # noqa: E402
from vista_bridge.synchronizer import VistaSynchronizer  # noqa: E402


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
            SyncSettings(
                startup_enabled=True,
                initial_delay_ms=0,
                command_delay_ms=0,
                response_timeout_seconds=1,
                periodic_enabled=True,
                periodic_interval_seconds=300,
                reconnect_after_failures=3,
            ),
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


if __name__ == "__main__":
    unittest.main()
