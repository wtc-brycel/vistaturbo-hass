from __future__ import annotations

import asyncio
import base64
from datetime import datetime, timezone
import ipaddress
import json
import logging
from pathlib import Path
from typing import Any

from aiohttp import WSMsgType, web

from .admin_snapshot import AdminSnapshotBuilder


LOG = logging.getLogger(__name__)
DEFAULT_INGRESS_PORT = 8099
DEFAULT_INGRESS_PROXY = "172.30.32.2"
STATIC_ROOT = Path(__file__).with_name("admin_frontend")


def _bounded_header(value: str | None, limit: int) -> str:
    if not value:
        return ""
    return "".join(character for character in value if character.isprintable())[:limit]


def _encode_cursor(cursor: dict[str, Any] | None) -> str:
    if not cursor:
        return ""
    raw = json.dumps(cursor, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _decode_cursor(value: str) -> dict[str, Any] | None:
    value = value.strip()
    if not value:
        return None
    if len(value) > 512:
        raise ValueError("cursor_too_long")
    padding = "=" * (-len(value) % 4)
    try:
        decoded = base64.urlsafe_b64decode((value + padding).encode("ascii"))
        payload = json.loads(decoded.decode("utf-8"))
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("invalid_cursor") from exc
    if not isinstance(payload, dict):
        raise ValueError("invalid_cursor")
    sort_at = str(payload.get("sort_at", ""))
    row_id = int(payload.get("id", 0) or 0)
    if not sort_at or row_id < 1:
        raise ValueError("invalid_cursor")
    return {"sort_at": sort_at[:64], "id": row_id}


class AdminServer:
    """Supervisor-ingress-only administrative web application."""

    def __init__(
        self,
        bridge,
        *,
        port: int = DEFAULT_INGRESS_PORT,
        trusted_proxy_ips: set[str] | None = None,
    ) -> None:
        self.bridge = bridge
        self.port = int(port)
        self.trusted_proxy_ips = {
            str(ipaddress.ip_address(value))
            for value in (trusted_proxy_ips or {DEFAULT_INGRESS_PROXY})
        }
        self.snapshot_builder = AdminSnapshotBuilder(bridge)
        self._runner: web.AppRunner | None = None

        @web.middleware
        async def ingress_middleware(request: web.Request, handler):
            remote = request.remote or ""
            try:
                normalized_remote = str(ipaddress.ip_address(remote))
            except ValueError:
                normalized_remote = ""
            if normalized_remote not in self.trusted_proxy_ips:
                raise web.HTTPForbidden(text="Ingress proxy required")

            user_id = _bounded_header(
                request.headers.get("X-Remote-User-Id"), 128
            )
            if not user_id:
                raise web.HTTPUnauthorized(text="Ingress identity required")
            request["ingress_user"] = {
                "id": user_id,
                "name": _bounded_header(
                    request.headers.get("X-Remote-User-Name"), 128
                ),
                "display_name": _bounded_header(
                    request.headers.get("X-Remote-User-Display-Name"), 128
                ),
            }

            response = await handler(request)
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["Referrer-Policy"] = "no-referrer"
            response.headers["Permissions-Policy"] = (
                "camera=(), microphone=(), geolocation=()"
            )
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; "
                "script-src 'self'; "
                "style-src 'self'; "
                "img-src 'self' data:; "
                "font-src 'self'; "
                "connect-src 'self' ws: wss:; "
                "object-src 'none'; "
                "base-uri 'self'; "
                "form-action 'self'"
            )
            return response

        self.app = web.Application(
            middlewares=[ingress_middleware],
            client_max_size=16 * 1024,
        )
        self.app.add_routes(
            [
                web.get("/", self._index),
                web.get("/index.html", self._index),
                web.get("/admin.css", self._static),
                web.get("/admin.js", self._static),
                web.get("/vista-keypad-card.js", self._static),
                web.get("/api/snapshot", self._snapshot),
                web.get("/api/events", self._events),
                web.post("/api/keypad", self._keypad),
                web.get("/ws", self._websocket),
            ]
        )

    async def start(self) -> None:
        if self._runner is not None:
            return
        runner = web.AppRunner(self.app, access_log=None)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", self.port)
        await site.start()
        self._runner = runner
        LOG.info(
            "Admin ingress service listening on port %d for Supervisor proxy %s",
            self.port,
            ",".join(sorted(self.trusted_proxy_ips)),
        )

    async def stop(self) -> None:
        runner, self._runner = self._runner, None
        if runner is not None:
            await runner.cleanup()

    async def _index(self, request: web.Request) -> web.StreamResponse:
        response = web.FileResponse(STATIC_ROOT / "index.html")
        response.headers["Cache-Control"] = "no-store"
        return response

    async def _static(self, request: web.Request) -> web.StreamResponse:
        filename = request.path.rsplit("/", 1)[-1]
        if filename not in {
            "admin.css",
            "admin.js",
            "vista-keypad-card.js",
        }:
            raise web.HTTPNotFound()
        response = web.FileResponse(STATIC_ROOT / filename)
        response.headers["Cache-Control"] = "no-cache"
        return response

    async def _snapshot(self, request: web.Request) -> web.Response:
        response = web.json_response(
            self.snapshot_builder.build(request["ingress_user"])
        )
        response.headers["Cache-Control"] = "no-store"
        return response

    async def _events(self, request: web.Request) -> web.Response:
        store = self.bridge.event_store
        if store is None:
            return web.json_response(
                {"events": [], "next_cursor": "", "enabled": False}
            )

        try:
            limit = max(1, min(100, int(request.query.get("limit", "50"))))
            partition = max(
                0, min(8, int(request.query.get("partition", "0") or 0))
            )
            zone = max(0, int(request.query.get("zone", "0") or 0))
            user = max(0, int(request.query.get("user", "0") or 0))
            cursor = _decode_cursor(request.query.get("cursor", ""))
        except (ValueError, TypeError) as exc:
            raise web.HTTPBadRequest(text="Invalid event query") from exc

        event_code = request.query.get("event_code", "").strip().upper()[:8]
        source = request.query.get("source", "").strip().lower()[:16]
        if source not in {"", "live", "history", "both"}:
            raise web.HTTPBadRequest(text="Invalid event source")
        search = request.query.get("q", "").strip()[:80]

        page = store.query_page(
            limit=limit,
            partition=partition,
            zone=zone,
            user=user,
            event_code=event_code,
            source=source,
            search=search,
            cursor=cursor,
        )
        response = web.json_response(
            {
                "events": page["events"],
                "next_cursor": _encode_cursor(page["next_cursor"]),
                "enabled": True,
            }
        )
        response.headers["Cache-Control"] = "no-store"
        return response

    async def _keypad(self, request: web.Request) -> web.Response:
        try:
            payload = await request.json()
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise web.HTTPBadRequest(text="Invalid JSON") from exc
        if not isinstance(payload, dict):
            raise web.HTTPBadRequest(text="Invalid keypad request")

        key = str(payload.get("key", ""))
        try:
            partition = int(payload.get("partition", 0))
        except (TypeError, ValueError) as exc:
            raise web.HTTPBadRequest(text="Invalid partition") from exc
        if partition not in self.bridge.settings.keypad.partitions:
            raise web.HTTPBadRequest(text="Partition is not configured")
        if len(key) != 1 or key not in "0123456789*#":
            raise web.HTTPBadRequest(text="Unsupported keypad key")

        user = request["ingress_user"]
        interaction_id = _bounded_header(
            str(payload.get("transaction_id", "")), 96
        )
        audit_interaction_id = _bounded_header(
            str(payload.get("audit_interaction_id", "")), 96
        )
        if not interaction_id:
            raise web.HTTPBadRequest(text="Missing transaction identifier")
        if not audit_interaction_id:
            audit_interaction_id = interaction_id

        accepted, status = self.bridge.enqueue_keypad_control(
            partition,
            key,
            {
                "interaction_id": interaction_id,
                "audit_interaction_id": audit_interaction_id,
                "actor_id": user["id"],
                "actor_name": user["display_name"] or user["name"],
                "source": "ha_ingress",
                "action": "keypad_sequence",
                "interaction_complete": True,
                "started_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        response = web.json_response(
            {"accepted": bool(accepted), "status": status},
            status=202 if accepted else 409,
        )
        response.headers["Cache-Control"] = "no-store"
        return response

    async def _websocket(self, request: web.Request) -> web.WebSocketResponse:
        websocket = web.WebSocketResponse(
            heartbeat=30,
            max_msg_size=1024,
            compress=False,
        )
        await websocket.prepare(request)
        user = request["ingress_user"]
        previous = ""

        while not websocket.closed:
            snapshot = self.snapshot_builder.build(user)
            encoded = json.dumps(
                snapshot,
                ensure_ascii=True,
                separators=(",", ":"),
                sort_keys=True,
            )
            if encoded != previous:
                previous = encoded
                await websocket.send_json(
                    {"type": "snapshot", "data": snapshot}
                )

            try:
                message = await websocket.receive(timeout=1.0)
            except asyncio.TimeoutError:
                continue
            if message.type in {
                WSMsgType.CLOSE,
                WSMsgType.CLOSED,
                WSMsgType.ERROR,
            }:
                break
            # The first ingress revision is server-push only. Commands use
            # narrow HTTP endpoints so request validation remains explicit.

        return websocket
