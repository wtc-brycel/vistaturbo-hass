from __future__ import annotations

import asyncio
import json
import os
import sys
from types import SimpleNamespace
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))

from vista_bridge.native_api import NativeApiServer  # noqa: E402


class FakePartition:
    def __init__(self, partition: int, state: str = "disarmed") -> None:
        self.partition = partition
        self.ha_state = state

    def attributes(self) -> dict:
        return {
            "partition": self.partition,
            "vista_mode": "away" if self.ha_state == "armed_away" else "disarmed",
            "ready": True,
        }


class FakeZone:
    def __init__(self, zone: int) -> None:
        self.zone = zone
        self.partition = 0
        self.descriptor = ""
        self.faulted = False

    def attributes(self) -> dict:
        return {
            "zone": self.zone,
            "partition": self.partition,
            "descriptor": self.descriptor,
            "faulted": self.faulted,
            "trouble": False,
            "alarm": False,
            "bypassed": False,
            "low_battery": False,
            "tamper": False,
            "raw_status": "0",
        }


class FakeKeypad:
    def __init__(self, partition: int) -> None:
        self.partition = partition
        self.session_fresh = False
        self.line_1 = ""
        self.line_2 = ""

    @property
    def ha_state(self) -> str:
        return f"{self.line_1.rstrip()} | {self.line_2.rstrip()}"

    def attributes(self) -> dict:
        return {
            "partition": self.partition,
            "line_1": self.line_1,
            "line_2": self.line_2,
            "ready": True,
            "trouble": False,
            "armed": True,
            "session_fresh": self.session_fresh,
        }


class FakeState:
    def __init__(self) -> None:
        self.partitions = {i: FakePartition(i) for i in range(1, 9)}
        self.zones = {i: FakeZone(i) for i in range(1, 129)}
        self.keypads = {i: FakeKeypad(i) for i in range(1, 9)}
        self.last_event = None
        self.live_snapshot_complete = True
        self.alarm_knowledge_complete = True
        self.session_generation = 1


class FakeBridge:
    def __init__(self) -> None:
        self.state = FakeState()
        self.settings = SimpleNamespace(
            keypad=SimpleNamespace(partitions=(1,)),
        )
        self.connected = True

    def _is_connected(self) -> bool:
        return self.connected


async def _request(
    port: int,
    path: str,
    *,
    token: str | None = None,
    method: str = "GET",
) -> tuple[int, dict]:
    reader, writer = await asyncio.open_connection("127.0.0.1", port)
    headers = [
        f"{method} {path} HTTP/1.1",
        "Host: 127.0.0.1",
        "Connection: close",
    ]
    if token is not None:
        headers.append(f"Authorization: Bearer {token}")
    writer.write(("\r\n".join(headers) + "\r\n\r\n").encode("ascii"))
    await writer.drain()
    raw = await reader.read()
    writer.close()
    await writer.wait_closed()
    head, body = raw.split(b"\r\n\r\n", 1)
    status = int(head.split(b" ", 2)[1])
    return status, json.loads(body)


class NativeApiTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.bridge = FakeBridge()
        state = self.bridge.state
        state.partitions[1].ha_state = "armed_away"
        state.zones[1].partition = 1
        state.zones[1].descriptor = "FRONT DOOR"
        keypad = state.keypads[1]
        keypad.session_fresh = True
        keypad.line_1 = "P1   ARMED AWAY "
        keypad.line_2 = "ALL SECURE      "

        self.server = NativeApiServer(self.bridge, "test-machine-token", 0)
        await self.server.start()

    async def asyncTearDown(self) -> None:
        await self.server.stop()

    async def test_snapshot_exposes_semantic_state_without_credentials(self) -> None:
        status, payload = await _request(
            self.server.port,
            "/v1/snapshot",
            token="test-machine-token",
        )
        self.assertEqual(status, 200)
        self.assertEqual(payload["schema"], 1)
        self.assertTrue(payload["api"]["read_only"])
        self.assertEqual(payload["partitions"][0]["state"], "armed_away")
        self.assertEqual(payload["zones"][0]["descriptor"], "FRONT DOOR")
        self.assertEqual(payload["keypads"][0]["line_1"], "P1   ARMED AWAY ")
        self.assertNotIn("test-machine-token", json.dumps(payload))

    async def test_api_requires_discovered_bearer_token(self) -> None:
        status, payload = await _request(self.server.port, "/v1/snapshot")
        self.assertEqual(status, 401)
        self.assertEqual(payload, {"error": "unauthorized"})

        status, payload = await _request(
            self.server.port,
            "/v1/snapshot",
            token="wrong-token",
        )
        self.assertEqual(status, 401)
        self.assertEqual(payload, {"error": "unauthorized"})

    async def test_ha0_api_is_read_only(self) -> None:
        status, payload = await _request(
            self.server.port,
            "/v1/snapshot",
            token="test-machine-token",
            method="POST",
        )
        self.assertEqual(status, 405)
        self.assertEqual(payload, {"error": "method_not_allowed"})

    async def test_state_changes_increment_push_revision(self) -> None:
        status, before = await _request(
            self.server.port,
            "/v1/snapshot",
            token="test-machine-token",
        )
        self.assertEqual(status, 200)

        self.bridge.state.zones[1].faulted = True
        await asyncio.sleep(0.4)

        status, after = await _request(
            self.server.port,
            "/v1/snapshot",
            token="test-machine-token",
        )
        self.assertEqual(status, 200)
        self.assertGreater(after["revision"], before["revision"])
        self.assertTrue(after["zones"][0]["faulted"])


if __name__ == "__main__":
    unittest.main()
