from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import hmac
import json
import logging
from typing import TYPE_CHECKING
from urllib.parse import urlsplit

if TYPE_CHECKING:
    from .bridge import VistaBridge

LOG = logging.getLogger(__name__)
API_SCHEMA = 1
DEFAULT_PORT = 8098
MAX_REQUEST_BYTES = 8192
HEARTBEAT_SECONDS = 20
OBSERVE_INTERVAL_SECONDS = 0.25


class NativeApiServer:
    """Read-only private API for the Home Assistant native integration."""

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
            "partitions": partitions,
            "zones": zones,
            "keypads": keypads,
            "last_event": last_event,
        }
        if include_metadata:
            payload["api"] = {"read_only": True}
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

        if method != "GET":
            await self._write_json(writer, 405, {"error": "method_not_allowed"})
            return
        if not hmac.compare_digest(
            headers.get("authorization", ""), f"Bearer {self._token}"
        ):
            await self._write_json(writer, 401, {"error": "unauthorized"})
            return

        path = urlsplit(target).path
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

    async def _write_json(
        self, writer: asyncio.StreamWriter, status: int, payload: dict
    ) -> None:
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        reason = {
            200: "OK",
            400: "Bad Request",
            401: "Unauthorized",
            404: "Not Found",
            405: "Method Not Allowed",
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
