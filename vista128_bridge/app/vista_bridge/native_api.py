from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import hmac
import json
import logging
from typing import TYPE_CHECKING
from urllib.parse import urlsplit
from uuid import uuid4

from .command_model import CommandValidationError, VistaCommand

if TYPE_CHECKING:
    from .bridge import VistaBridge

LOG = logging.getLogger(__name__)
API_SCHEMA = 1
DEFAULT_PORT = 8098
MAX_REQUEST_BYTES = 8192
MAX_CONTROL_BODY_BYTES = 4096
HEARTBEAT_SECONDS = 20
OBSERVE_INTERVAL_SECONDS = 0.25
ALARM_ACTIONS = frozenset({"disarm", "arm_away", "arm_home", "arm_night"})


class NativeApiServer:
    """Private semantic API for the Home Assistant native integration."""

    def __init__(self, bridge: VistaBridge, token: str, port: int = DEFAULT_PORT) -> None:
        if not token:
            raise ValueError("native API token must not be empty")
        self._bridge = bridge
        self._token = token
        self._port = port
        self._server: asyncio.AbstractServer | None = None
        self._observer_task: asyncio.Task[None] | None = None
        self._subscribers: set[asyncio.Queue[int]] = set()
        self._revision = 0
        self._fingerprint = ""

    @property
    def port(self) -> int:
        if self._server is None or not self._server.sockets:
            return self._port
        return int(self._server.sockets[0].getsockname()[1])

    async def start(self) -> None:
        self._server = await asyncio.start_server(
            self._handle_client,
            host="0.0.0.0",
            port=self._port,
            limit=MAX_REQUEST_BYTES,
        )
        self._fingerprint = self._snapshot_fingerprint()
        self._observer_task = asyncio.create_task(
            self._observe_state(), name="native-api-state-observer"
        )
        LOG.info("Native Home Assistant API listening on internal port %d", self.port)

    async def stop(self) -> None:
        if self._observer_task is not None:
            self._observer_task.cancel()
            await asyncio.gather(self._observer_task, return_exceptions=True)
            self._observer_task = None
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            self._server = None
        self._subscribers.clear()

    async def _observe_state(self) -> None:
        """Turn in-process semantic state changes into a push stream."""
        while True:
            await asyncio.sleep(OBSERVE_INTERVAL_SECONDS)
            fingerprint = self._snapshot_fingerprint()
            if fingerprint == self._fingerprint:
                continue
            self._fingerprint = fingerprint
            self._revision += 1
            for subscriber in tuple(self._subscribers):
                if subscriber.empty():
                    subscriber.put_nowait(self._revision)

    def _snapshot_fingerprint(self) -> str:
        return json.dumps(
            self._snapshot_payload(include_metadata=False),
            sort_keys=True,
            separators=(",", ":"),
        )

    def snapshot(self) -> dict:
        payload = self._snapshot_payload(include_metadata=True)
        payload["revision"] = self._revision
        payload["generated_at"] = datetime.now(timezone.utc).isoformat()
        return payload

    def _snapshot_payload(self, *, include_metadata: bool) -> dict:
        state = self._bridge.state
        panel_connected = self._bridge._is_connected()
        configured_keypads = set(self._bridge.settings.keypad.partitions)
        control_settings = self._bridge.settings.control
        native_alarm_control = bool(
            control_settings.enabled and control_settings.native_alarm_enabled
        )

        partitions = [
            {
                "partition": partition.partition,
                "state": partition.ha_state,
                **partition.attributes(),
            }
            for partition in state.partitions.values()
        ]
        zones = [zone.attributes() for zone in state.zones.values() if zone.partition]

        keypads = []
        for keypad in state.keypads.values():
            if keypad.partition not in configured_keypads:
                continue
            keypads.append(
                {
                    "partition": keypad.partition,
                    "state": keypad.ha_state,
                    "available": bool(panel_connected and keypad.session_fresh),
                    **keypad.attributes(),
                }
            )

        last_event = None
        if state.last_event is not None:
            event = state.last_event
            last_event = {
                "code": event.code,
                "description": event.description,
                "zone": event.zone,
                "user": event.user,
                "partition": event.partition,
                "panel_timestamp": event.panel_timestamp,
            }

        payload = {
            "schema": API_SCHEMA,
            "panel": {
                "connected": panel_connected,
                "state_fresh": bool(state.live_snapshot_complete),
                "alarm_knowledge_complete": bool(state.alarm_knowledge_complete),
                "session_generation": state.session_generation,
            },
            "control": {
                "native_alarm": native_alarm_control,
                "automation_available": bool(
                    native_alarm_control
                    and self._bridge.control.automation_available()
                ),
            },
            "partitions": partitions,
            "zones": zones,
            "keypads": keypads,
            "last_event": last_event,
        }
        if include_metadata:
            payload["api"] = {
                "read_only": not native_alarm_control,
                "alarm_control": native_alarm_control,
            }
        return payload

    async def _handle_client(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        try:
            request = await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), timeout=5)
        except (
            asyncio.IncompleteReadError,
            asyncio.LimitOverrunError,
            asyncio.TimeoutError,
        ):
            writer.close()
            await writer.wait_closed()
            return

        try:
            header_text = request.decode("iso-8859-1")
        except UnicodeDecodeError:
            await self._write_json(writer, 400, {"error": "invalid_request"})
            return

        lines = header_text.split("\r\n")
        request_line = lines[0].split()
        if len(request_line) != 3:
            await self._write_json(writer, 400, {"error": "invalid_request"})
            return
        method, target, _ = request_line
        headers: dict[str, str] = {}
        for line in lines[1:]:
            if not line or ":" not in line:
                continue
            name, value = line.split(":", 1)
            headers[name.strip().lower()] = value.strip()

        if not hmac.compare_digest(
            headers.get("authorization", ""), f"Bearer {self._token}"
        ):
            await self._write_json(writer, 401, {"error": "unauthorized"})
            return

        path = urlsplit(target).path
        if method == "GET":
            if path == "/v1/health":
                await self._write_json(
                    writer,
                    200,
                    {"schema": API_SCHEMA, "status": "ok", "revision": self._revision},
                )
            elif path == "/v1/snapshot":
                await self._write_json(writer, 200, self.snapshot())
            elif path == "/v1/stream":
                await self._stream_events(writer)
            else:
                await self._write_json(writer, 404, {"error": "not_found"})
            return

        if method == "POST" and path == "/v1/control/alarm":
            payload, error = await self._read_control_payload(reader, headers)
            if error is not None:
                status, code = error
                await self._write_json(writer, status, {"error": code})
                return
            assert payload is not None
            await self._handle_alarm_control(writer, payload)
            return

        await self._write_json(writer, 405, {"error": "method_not_allowed"})

    async def _read_control_payload(
        self, reader: asyncio.StreamReader, headers: dict[str, str]
    ) -> tuple[dict | None, tuple[int, str] | None]:
        content_type = headers.get("content-type", "").split(";", 1)[0].strip().lower()
        if content_type != "application/json":
            return None, (415, "content_type_must_be_json")
        try:
            content_length = int(headers.get("content-length", ""))
        except ValueError:
            return None, (400, "invalid_content_length")
        if not 1 <= content_length <= MAX_CONTROL_BODY_BYTES:
            return None, (
                413 if content_length > MAX_CONTROL_BODY_BYTES else 400,
                "control_body_too_large" if content_length > MAX_CONTROL_BODY_BYTES else "empty_control_body",
            )
        try:
            raw = await asyncio.wait_for(reader.readexactly(content_length), timeout=5)
            payload = json.loads(raw.decode("utf-8"))
        except (
            asyncio.IncompleteReadError,
            asyncio.TimeoutError,
            UnicodeDecodeError,
            json.JSONDecodeError,
        ):
            return None, (400, "invalid_json")
        if not isinstance(payload, dict):
            return None, (400, "control_body_must_be_object")
        return payload, None

    async def _handle_alarm_control(
        self, writer: asyncio.StreamWriter, payload: dict
    ) -> None:
        control_settings = self._bridge.settings.control
        if not (control_settings.enabled and control_settings.native_alarm_enabled):
            await self._write_json(
                writer, 403, {"error": "native_alarm_control_disabled"}
            )
            return

        action = payload.get("action")
        code = payload.get("code")
        partition = payload.get("partition")
        if action not in ALARM_ACTIONS:
            await self._write_json(writer, 400, {"error": "unsupported_alarm_action"})
            return
        if isinstance(partition, bool):
            await self._write_json(writer, 400, {"error": "invalid_partition"})
            return
        try:
            partition_number = int(partition)
        except (TypeError, ValueError):
            await self._write_json(writer, 400, {"error": "invalid_partition"})
            return
        if not 1 <= partition_number <= 8:
            await self._write_json(writer, 400, {"error": "invalid_partition"})
            return
        if not isinstance(code, str):
            await self._write_json(writer, 400, {"error": "invalid_code"})
            return

        actor = payload.get("actor") if isinstance(payload.get("actor"), dict) else {}
        actor_id = str(actor.get("user_id", ""))
        actor_name = str(actor.get("name", ""))
        context_id = str(payload.get("context_id", ""))[:96]
        interaction_id = f"ha-{uuid4().hex}"
        started_at = datetime.now(timezone.utc).isoformat()

        try:
            command = VistaCommand(
                command_type=action,
                partition=partition_number,
                code=code,
                source="home_assistant",
                actor_id=actor_id,
                actor_name=actor_name,
                interaction_id=interaction_id,
            )
        except CommandValidationError:
            await self._write_json(writer, 400, {"error": "invalid_code"})
            return

        accepted, detail = self._bridge.enqueue_command_control(
            command,
            {
                "interaction_id": interaction_id,
                "audit_interaction_id": interaction_id,
                "audit_request_id": context_id or interaction_id,
                "started_at": started_at,
                "source": "home_assistant",
                "action": action,
                "actor_id": actor_id,
                "actor_name": actor_name,
            },
        )
        if not accepted:
            unavailable = {
                "panel_offline",
                "automation_interface_unavailable",
                "transaction_unavailable",
            }
            busy = {"control_queue_full", "keypad_interaction_busy"}
            status = 503 if detail in unavailable else 429 if detail in busy else 409
            await self._write_json(writer, status, {"error": detail})
            return

        await self._write_json(
            writer,
            202,
            {
                "ok": True,
                "status": detail,
                "interaction_id": interaction_id,
                "partition": partition_number,
                "action": action,
            },
        )

    async def _write_json(
        self, writer: asyncio.StreamWriter, status: int, payload: dict
    ) -> None:
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        reason = {
            200: "OK",
            202: "Accepted",
            400: "Bad Request",
            401: "Unauthorized",
            403: "Forbidden",
            404: "Not Found",
            405: "Method Not Allowed",
            409: "Conflict",
            413: "Payload Too Large",
            415: "Unsupported Media Type",
            429: "Too Many Requests",
            503: "Service Unavailable",
        }.get(status, "Error")
        writer.write(
            (
                f"HTTP/1.1 {status} {reason}\r\n"
                "Content-Type: application/json\r\n"
                f"Content-Length: {len(body)}\r\n"
                "Cache-Control: no-store\r\n"
                "Connection: close\r\n\r\n"
            ).encode("ascii")
            + body
        )
        try:
            await writer.drain()
        finally:
            writer.close()
            await writer.wait_closed()

    async def _stream_events(self, writer: asyncio.StreamWriter) -> None:
        queue: asyncio.Queue[int] = asyncio.Queue(maxsize=1)
        self._subscribers.add(queue)
        writer.write(
            b"HTTP/1.1 200 OK\r\n"
            b"Content-Type: text/event-stream\r\n"
            b"Cache-Control: no-cache, no-store\r\n"
            b"Connection: keep-alive\r\n\r\n"
        )
        try:
            await self._write_sse_snapshot(writer)
            while True:
                try:
                    await asyncio.wait_for(queue.get(), timeout=HEARTBEAT_SECONDS)
                except asyncio.TimeoutError:
                    writer.write(b": heartbeat\n\n")
                    await writer.drain()
                    continue
                await self._write_sse_snapshot(writer)
        except (ConnectionError, BrokenPipeError, ConnectionResetError, asyncio.CancelledError):
            pass
        finally:
            self._subscribers.discard(queue)
            writer.close()
            try:
                await writer.wait_closed()
            except (ConnectionError, BrokenPipeError, ConnectionResetError):
                pass

    async def _write_sse_snapshot(self, writer: asyncio.StreamWriter) -> None:
        data = json.dumps(self.snapshot(), separators=(",", ":"))
        writer.write(f"event: snapshot\ndata: {data}\n\n".encode("utf-8"))
        await writer.drain()
