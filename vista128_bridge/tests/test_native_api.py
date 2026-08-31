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


class FakeControl:
    def __init__(self) -> None:
        self.available = True

    def automation_available(self) -> bool:
        return self.available


class FakeBridge:
    def __init__(self) -> None:
        self.state = FakeState()
        self.settings = SimpleNamespace(
            keypad=SimpleNamespace(partitions=(1,)),
            control=SimpleNamespace(enabled=True, native_alarm_enabled=True),
        )
        self.control = FakeControl()
        self.connected = True
        self.commands = []
        self.enqueue_result = (True, "queued")

    def _is_connected(self) -> bool:
        return self.connected

    def enqueue_command_control(self, command, metadata=None):
        self.commands.append((command, metadata or {}))
        return self.enqueue_result


async def _request(
    port: int,
    path: str,
    *,
    token: str | None = None,
    method: str = "GET",
    payload: dict | None = None,
) -> tuple[int, dict]:
    reader, writer = await asyncio.open_connection("127.0.0.1", port)
    headers = [
        f"{method} {path} HTTP/1.1",
        "Host: 127.0.0.1",
        "Connection: close",
    ]
    if token is not None:
        headers.append(f"Authorization: Bearer {token}")
    body = b""
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers.extend(
            [
                "Content-Type: application/json",
                f"Content-Length: {len(body)}",
            ]
        )
    writer.write(("\r\n".join(headers) + "\r\n\r\n").encode("ascii") + body)
    await writer.drain()
    raw = await reader.read()
    writer.close()
    await writer.wait_closed()
    head, response_body = raw.split(b"\r\n\r\n", 1)
    status = int(head.split(b" ", 2)[1])
    return status, json.loads(response_body)


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

    async def test_snapshot_exposes_semantic_state_and_control_capability(self) -> None:
        status, payload = await _request(
            self.server.port,
            "/v1/snapshot",
            token="test-machine-token",
        )
        self.assertEqual(status, 200)
        self.assertEqual(payload["schema"], 1)
        self.assertFalse(payload["api"]["read_only"])
        self.assertTrue(payload["api"]["alarm_control"])
        self.assertTrue(payload["control"]["native_alarm"])
        self.assertTrue(payload["control"]["automation_available"])
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

    async def test_only_semantic_alarm_post_is_accepted(self) -> None:
        status, payload = await _request(
            self.server.port,
            "/v1/snapshot",
            token="test-machine-token",
            method="POST",
            payload={"anything": True},
        )
        self.assertEqual(status, 405)
        self.assertEqual(payload, {"error": "method_not_allowed"})

    async def test_alarm_control_enqueues_canonical_command_with_ha_identity(self) -> None:
        status, payload = await _request(
            self.server.port,
            "/v1/control/alarm",
            token="test-machine-token",
            method="POST",
            payload={
                "partition": 2,
                "action": "arm_home",
                "code": "1234",
                "actor": {"user_id": "ha-user-42", "name": ""},
                "context_id": "ha-context-7",
            },
        )
        self.assertEqual(status, 202)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["partition"], 2)
        self.assertEqual(payload["action"], "arm_home")
        self.assertNotIn("code", payload)

        self.assertEqual(len(self.bridge.commands), 1)
        command, metadata = self.bridge.commands[0]
        self.assertEqual(command.command_type, "arm_home")
        self.assertEqual(command.partition, 2)
        self.assertEqual(command.code, "1234")
        self.assertEqual(command.source, "home_assistant")
        self.assertEqual(command.actor_id, "ha-user-42")
        self.assertEqual(command.raw_sequence, "")
        self.assertTrue(command.interaction_id.startswith("ha-"))
        self.assertEqual(metadata["audit_request_id"], "ha-context-7")
        self.assertEqual(metadata["source"], "home_assistant")

    async def test_alarm_control_rejects_nonsemantic_or_invalid_input(self) -> None:
        for request_payload, expected_error in (
            (
                {"partition": 1, "action": "keypad", "code": "1234"},
                "unsupported_alarm_action",
            ),
            (
                {"partition": 1, "action": "arm_away", "code": "12"},
                "invalid_code",
            ),
            (
                {"partition": 9, "action": "arm_away", "code": "1234"},
                "invalid_partition",
            ),
        ):
            with self.subTest(payload=request_payload):
                status, payload = await _request(
                    self.server.port,
                    "/v1/control/alarm",
                    token="test-machine-token",
                    method="POST",
                    payload=request_payload,
                )
                self.assertEqual(status, 400)
                self.assertEqual(payload, {"error": expected_error})
        self.assertEqual(self.bridge.commands, [])

    async def test_alarm_control_respects_existing_preflight_result(self) -> None:
        self.bridge.enqueue_result = (False, "automation_interface_unavailable")
        status, payload = await _request(
            self.server.port,
            "/v1/control/alarm",
            token="test-machine-token",
            method="POST",
            payload={"partition": 1, "action": "disarm", "code": "1234"},
        )
        self.assertEqual(status, 503)
        self.assertEqual(payload, {"error": "automation_interface_unavailable"})

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
