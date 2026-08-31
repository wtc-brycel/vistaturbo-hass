from __future__ import annotations

import asyncio
import os
import sys
from types import SimpleNamespace
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))

from vista_bridge.native_api import NativeApiServer  # noqa: E402


class FakeControl:
    def automation_available(self) -> bool:
        return False


class FakeState:
    def __init__(self) -> None:
        self.partitions = {}
        self.zones = {}
        self.keypads = {}
        self.last_event = None
        self.live_snapshot_complete = False
        self.alarm_knowledge_complete = False
        self.session_generation = 1


class FakeBridge:
    def __init__(self) -> None:
        self.state = FakeState()
        self.control = FakeControl()
        self.handler = SimpleNamespace(native_event_callback=None)
        self.settings = SimpleNamespace(
            keypad=SimpleNamespace(partitions=()),
            control=SimpleNamespace(enabled=False, native_alarm_enabled=False),
        )

    def _is_connected(self) -> bool:
        return False


async def _open_stream(port: int, path: str) -> tuple[asyncio.StreamReader, asyncio.StreamWriter]:
    reader, writer = await asyncio.open_connection("127.0.0.1", port)
    writer.write(
        (
            f"GET {path} HTTP/1.1\r\n"
            "Host: 127.0.0.1\r\n"
            "Authorization: Bearer test-machine-token\r\n"
            "Connection: keep-alive\r\n\r\n"
        ).encode("ascii")
    )
    await writer.drain()
    head = await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), timeout=1)
    if b" 200 " not in head:
        raise AssertionError(f"unexpected stream response: {head!r}")
    return reader, writer


class NativeApiShutdownTests(unittest.IsolatedAsyncioTestCase):
    async def test_stop_wakes_state_and_event_streams_without_heartbeat_delay(self) -> None:
        server = NativeApiServer(FakeBridge(), "test-machine-token", 0)
        await server.start()
        state_reader, state_writer = await _open_stream(server.port, "/v1/stream")
        event_reader, event_writer = await _open_stream(server.port, "/v1/events")

        # Both streams are now blocked waiting for the next state/event or the
        # 20-second heartbeat. App shutdown must wake them directly.
        await asyncio.wait_for(server.stop(), timeout=1)

        await asyncio.wait_for(state_reader.read(), timeout=1)
        await asyncio.wait_for(event_reader.read(), timeout=1)
        state_writer.close()
        event_writer.close()
        await state_writer.wait_closed()
        await event_writer.wait_closed()


if __name__ == "__main__":
    unittest.main()
