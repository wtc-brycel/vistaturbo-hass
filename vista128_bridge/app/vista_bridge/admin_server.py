from __future__ import annotations

import asyncio
import base64
from collections import OrderedDict
from datetime import datetime, timezone
import hashlib
import hmac
import ipaddress
import json
import logging
from pathlib import Path
import re
import secrets
import time
from urllib.parse import urlsplit

from aiohttp import WSMsgType, web

from .admin_auth import AdminAuthorizationUnavailable, HomeAssistantAdminAuthorizer
from .admin_snapshot import AdminSnapshotBuilder
from .admin_status import event_presentation
from .diagnostics import (
    DIAGNOSTIC_CATEGORIES,
    DIAGNOSTIC_EVENT_TYPES,
    DIAGNOSTIC_SEVERITIES,
)

LOG = logging.getLogger(__name__)
DEFAULT_INGRESS_PORT = 8099
DEFAULT_INGRESS_PROXY = "172.30.32.2"
STATIC_ROOT = Path(__file__).with_name("admin_frontend")
IDENTIFIER = re.compile(r"[A-Za-z0-9_.:-]{1,96}\Z")


def _bounded_header(value, limit):
    return "".join(c for c in (value or "") if c.isprintable())[:limit]


def _encode_cursor(cursor):
    if not cursor:
        return ""
    return base64.urlsafe_b64encode(json.dumps(cursor, separators=(",", ":")).encode()).decode().rstrip("=")


def _decode_cursor(value):
    if not value:
        return None
    if not isinstance(value, str) or len(value) > 512:
        raise ValueError("invalid cursor")
    try:
        payload = json.loads(base64.b64decode(value + "=" * (-len(value) % 4), altchars=b"-_", validate=True))
    except (ValueError, UnicodeError) as exc:
        raise ValueError("invalid cursor") from exc
    if not isinstance(payload, dict) or set(payload) != {"id", "sort_at"}:
        raise ValueError("invalid cursor")
    if type(payload["id"]) is not int or not 1 <= payload["id"] < 2**63:
        raise ValueError("invalid cursor")
    if not isinstance(payload["sort_at"], str) or not 1 <= len(payload["sort_at"]) <= 64:
        raise ValueError("invalid cursor")
    return payload


def _encode_diagnostic_cursor(cursor):
    if not cursor:
        return ""
    return base64.urlsafe_b64encode(
        json.dumps(cursor, separators=(",", ":")).encode()
    ).decode().rstrip("=")


def _decode_diagnostic_cursor(value):
    if not value:
        return None
    if not isinstance(value, str) or len(value) > 512:
        raise ValueError("invalid cursor")
    try:
        payload = json.loads(
            base64.b64decode(
                value + "=" * (-len(value) % 4),
                altchars=b"-_",
                validate=True,
            )
        )
    except (ValueError, UnicodeError) as exc:
        raise ValueError("invalid cursor") from exc
    if not isinstance(payload, dict) or set(payload) != {"id", "occurred_at"}:
        raise ValueError("invalid cursor")
    if type(payload["id"]) is not int or not 1 <= payload["id"] < 2**63:
        raise ValueError("invalid cursor")
    if (
        not isinstance(payload["occurred_at"], str)
        or not 1 <= len(payload["occurred_at"]) <= 64
    ):
        raise ValueError("invalid cursor")
    return payload


def _diagnostic_record(record):
    return {
        "id": record.id,
        "event_id": record.event_id,
        "occurred_at": record.occurred_at,
        "severity": record.severity,
        "category": record.category,
        "component": record.component,
        "event_type": record.event_type,
        "message": record.message,
        "boot_id": record.boot_id,
        "panel_session_id": record.panel_session_id,
        "transport_session_id": record.transport_session_id,
        "correlation_id": record.correlation_id,
        "details": record.details,
    }


def _integer(value, minimum, maximum):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]{1,4}", value):
        raise ValueError("invalid integer")
    number = int(value)
    if not minimum <= number <= maximum:
        raise ValueError("integer out of range")
    return number


class AdminServer:
    """Read-only inspection and narrowly scoped keypad input through ingress."""

    def __init__(self, bridge, *, port=DEFAULT_INGRESS_PORT, trusted_proxy_ips=None, authorizer=None):
        self.bridge = bridge
        self.port = int(port)
        self.trusted_proxy_ips = {str(ipaddress.ip_address(v)) for v in (
            {DEFAULT_INGRESS_PROXY} if trusted_proxy_ips is None else trusted_proxy_ips
        )}
        self.authorizer = authorizer or HomeAssistantAdminAuthorizer()
        self.snapshot_builder = AdminSnapshotBuilder(bridge)
        self._runner = None
        self._instance = secrets.token_hex(16)
        self._secret = secrets.token_bytes(32)
        self._records = OrderedDict()
        self._db_slots = asyncio.Semaphore(2)
        self._stats_lock = asyncio.Lock()
        self._stats = None
        self._stats_at = 0.0
        self._sockets = set()
        self._unsubscribe = None
        self._loop = None
        self.app = web.Application(middlewares=[self._ingress], client_max_size=4096)
        self.app.on_response_prepare.append(self._headers)
        self.app.on_startup.append(self._startup)
        self.app.on_shutdown.append(self._shutdown)
        self.app.add_routes([
            web.get("/", self._index), web.get("/index.html", self._index),
            web.get("/admin.css", self._static), web.get("/admin.js", self._static),
            web.get("/vista-keypad-card.js", self._static),
            web.get("/api/snapshot", self._snapshot), web.get("/api/events", self._events),
            web.get("/api/diagnostics", self._diagnostics),
            web.post("/api/keypad", self._keypad), web.get("/ws", self._websocket),
        ])

    @web.middleware
    async def _ingress(self, request, handler):
        try:
            remote = str(ipaddress.ip_address(request.remote or ""))
        except ValueError:
            remote = ""
        if remote not in self.trusted_proxy_ips:
            raise web.HTTPForbidden(text="Ingress proxy required")
        user_id = _bounded_header(request.headers.get("X-Remote-User-Id"), 128)
        if not user_id:
            raise web.HTTPUnauthorized(text="Ingress identity required")
        try:
            allowed = await self.authorizer.allowed(user_id)
        except AdminAuthorizationUnavailable:
            raise web.HTTPServiceUnavailable(text="Administrator verification unavailable") from None
        if not allowed:
            raise web.HTTPForbidden(text="Administrator access required")
        request["ingress_user"] = {
            "id": user_id,
            "name": _bounded_header(request.headers.get("X-Remote-User-Name"), 128),
            "display_name": _bounded_header(request.headers.get("X-Remote-User-Display-Name"), 128),
        }
        if request.method == "POST" or request.path == "/ws":
            try:
                origin = urlsplit(request.headers.get("Origin", ""))
            except ValueError:
                raise web.HTTPForbidden(text="Same-origin request required") from None
            host = request.headers.get("X-Forwarded-Host", request.host)
            scheme = request.headers.get("X-Forwarded-Proto", request.scheme)
            if origin.scheme != scheme or origin.netloc != host:
                raise web.HTTPForbidden(text="Same-origin request required")
        return await handler(request)

    async def _headers(self, request, response):
        response.headers.update({
            "X-Content-Type-Options": "nosniff", "Referrer-Policy": "no-referrer",
            "Cache-Control": "no-store",
            "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
            # Existing keypad uses inline shadow-root styles, not inline script.
            "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'self'",
        })

    async def _startup(self, app):
        self._loop = asyncio.get_running_loop()
        self._unsubscribe = self.bridge.subscribe_control_results(self._control_result)

    async def _shutdown(self, app):
        if self._unsubscribe:
            self._unsubscribe()
        await asyncio.gather(*(ws.close(code=1001) for ws in tuple(self._sockets)))

    async def start(self):
        if self._runner is None:
            self._runner = web.AppRunner(self.app, access_log=None)
            await self._runner.setup()
            await web.TCPSite(self._runner, "0.0.0.0", self.port).start()
            LOG.info("Admin ingress service listening on port %d", self.port)

    async def stop(self):
        runner, self._runner = self._runner, None
        if runner is not None:
            await runner.cleanup()

    def _csrf(self, user_id):
        return hmac.new(self._secret, user_id.encode(), hashlib.sha256).hexdigest()

    def _prune_requests(self):
        now = time.monotonic()
        for key, record in tuple(self._records.items()):
            if now - record["at"] > 300:
                del self._records[key]

    def _control_result(self, payload):
        if self._loop and not self._loop.is_closed():
            self._loop.call_soon_threadsafe(self._collect_result, payload)

    def _collect_result(self, payload):
        record = self._records.get(payload.get("interaction_id"))
        if record is not None:
            record["result"] = {
                "transaction_id": record["transaction_id"],
                "partition": record["partition"], "ok": payload.get("ok") is True,
                "status": str(payload.get("status", "unknown"))[:64],
            }

    async def _snapshot_data(self, user):
        store = self.bridge.event_store
        async with self._stats_lock:
            if store is not None and (self._stats is None or time.monotonic() - self._stats_at >= 5):
                async with self._db_slots:
                    self._stats = await asyncio.to_thread(store.stats)
                self._stats_at = time.monotonic()
        data = self.snapshot_builder.build(user, journal_stats=self._stats)
        data["instance_id"] = self._instance
        data["csrf_token"] = self._csrf(user["id"])
        self._prune_requests()
        data["control_results"] = [r["result"] for r in self._records.values()
                                   if r["user_id"] == user["id"] and r.get("result")][-32:]
        return data

    async def _index(self, request):
        return web.FileResponse(STATIC_ROOT / "index.html")

    async def _static(self, request):
        return web.FileResponse(STATIC_ROOT / request.path.rsplit("/", 1)[-1])

    async def _snapshot(self, request):
        return web.json_response(await self._snapshot_data(request["ingress_user"]))

    async def _events(self, request):
        store = self.bridge.event_store
        if store is None or not self.bridge.settings.event_history.enabled:
            return web.json_response({"events": [], "next_cursor": "", "enabled": False})
        try:
            limit = _integer(request.query.get("limit", "50"), 1, 100)
            scope = request.query.get("partition", "0")
            partition = 0 if scope == "system" else _integer(scope, 0, 8)
            zone = _integer(request.query.get("zone", "0"), 0, 999)
            user = _integer(request.query.get("user", "0"), 0, 999)
            cursor = _decode_cursor(request.query.get("cursor", ""))
            code = request.query.get("event_code", "").upper()
            source = request.query.get("source", "")
            search = request.query.get("q", "").strip()
            if (code and not re.fullmatch(r"[0-9A-F]{2}", code)) or source not in {"", "live", "history", "both"} or len(search) > 80:
                raise ValueError("invalid filter")
        except (ValueError, TypeError):
            raise web.HTTPBadRequest(text="Invalid event query") from None
        async with self._db_slots:
            page = await asyncio.to_thread(store.query_page, limit=limit, partition=partition,
                                           system_only=scope == "system", zone=zone, user=user,
                                           event_code=code, source=source, search=search, cursor=cursor)
        return web.json_response({"events": [event_presentation(e) for e in page["events"]],
                                  "next_cursor": _encode_cursor(page["next_cursor"]), "enabled": True})

    async def _diagnostics(self, request):
        journal = getattr(self.bridge, "diagnostics", None)
        if journal is None or not journal.available:
            return web.json_response(
                {
                    "records": [],
                    "next_cursor": "",
                    "incidents": [],
                    "stats": {
                        "count": 0,
                        "oldest_at": "",
                        "newest_at": "",
                        "write_errors": 0,
                        "dropped_events": 0,
                        "pending_writes": 0,
                    },
                    "runtime": {
                        "available": False,
                        "write_errors": 0,
                        "dropped_events": 0,
                        "pending_writes": 0,
                        "writer_alive": False,
                    },
                    "enabled": False,
                }
            )
        try:
            limit = _integer(request.query.get("limit", "50"), 1, 100)
            cursor = _decode_diagnostic_cursor(request.query.get("cursor", ""))
            severity = request.query.get("severity", "").strip().lower()
            category = request.query.get("category", "").strip().lower()
            component = request.query.get("component", "").strip()
            event_type = request.query.get("event_type", "").strip().lower()
            correlation_id = request.query.get("correlation_id", "").strip()
            order = request.query.get("order", "newest").strip().lower()
            if severity and severity not in DIAGNOSTIC_SEVERITIES:
                raise ValueError("invalid severity")
            if category and category not in DIAGNOSTIC_CATEGORIES:
                raise ValueError("invalid category")
            if event_type and event_type not in DIAGNOSTIC_EVENT_TYPES:
                raise ValueError("invalid event type")
            if component and not IDENTIFIER.fullmatch(component):
                raise ValueError("invalid component")
            if correlation_id and not IDENTIFIER.fullmatch(correlation_id):
                raise ValueError("invalid correlation")
            if order not in {"newest", "oldest"}:
                raise ValueError("invalid order")
        except (ValueError, TypeError):
            raise web.HTTPBadRequest(text="Invalid diagnostic query") from None

        def read_diagnostics():
            page = journal.query_page(
                limit=limit,
                cursor=cursor,
                severity=severity or None,
                category=category or None,
                component=component or None,
                event_type=event_type or None,
                correlation_id=correlation_id or None,
                order=order,
            )
            stats = journal.stats()
            return page, journal.recent_incidents(limit=12), stats, journal.runtime_state()

        async with self._db_slots:
            page, incidents, stats, runtime = await asyncio.to_thread(read_diagnostics)

        return web.json_response(
            {
                "records": [_diagnostic_record(record) for record in page["records"]],
                "next_cursor": _encode_diagnostic_cursor(page["next_cursor"]),
                "incidents": incidents,
                "stats": {
                    "count": stats.count,
                    "oldest_at": stats.oldest_at,
                    "newest_at": stats.newest_at,
                    "write_errors": stats.write_errors,
                    "dropped_events": stats.dropped_events,
                    "pending_writes": stats.pending_writes,
                },
                "runtime": runtime,
                "retention_days": self.bridge.settings.diagnostics.max_age_days,
                "max_rows": self.bridge.settings.diagnostics.max_rows,
                "enabled": True,
            }
        )

    async def _keypad(self, request):
        user = request["ingress_user"]
        if not hmac.compare_digest(request.headers.get("X-Vista-CSRF", "").encode("utf-8"), self._csrf(user["id"]).encode("ascii")):
            raise web.HTTPForbidden(text="Invalid request token")
        if request.content_type != "application/json":
            raise web.HTTPUnsupportedMediaType()
        try:
            payload = await request.json()
        except (ValueError, UnicodeError):
            raise web.HTTPBadRequest(text="Invalid JSON") from None
        fields = {"key", "partition", "transaction_id", "audit_interaction_id", "session_generation", "instance_id"}
        if not isinstance(payload, dict) or set(payload) - fields:
            raise web.HTTPBadRequest(text="Invalid keypad request")
        key, p, txn = payload.get("key"), payload.get("partition"), payload.get("transaction_id")
        audit = payload.get("audit_interaction_id", txn)
        if not isinstance(key, str) or len(key) != 1 or key not in "0123456789*#":
            raise web.HTTPBadRequest(text="Unsupported keypad key")
        if type(p) is not int or p not in self.bridge.settings.keypad.partitions:
            raise web.HTTPBadRequest(text="Partition not configured")
        if not all(isinstance(v, str) and IDENTIFIER.fullmatch(v) for v in (txn, audit)):
            raise web.HTTPBadRequest(text="Invalid transaction identifier")
        generation = payload.get("session_generation")
        if type(generation) is not int or generation != self.bridge.state.session_generation or payload.get("instance_id") != self._instance:
            return web.json_response({"accepted": False, "status": "stale_session"}, status=409)
        self._prune_requests()
        internal = "ingress:" + hashlib.sha256(f"{user['id']}:{txn}".encode()).hexdigest()
        digest = hmac.new(self._secret, json.dumps(payload, sort_keys=True).encode(), hashlib.sha256).hexdigest()
        if internal in self._records:
            record = self._records[internal]
            if record["digest"] != digest:
                return web.json_response({"accepted": False, "status": "transaction_conflict"}, status=409)
            return web.json_response(record["response"], status=record["http_status"])
        if len(self._records) >= 512:
            return web.json_response({"accepted": False, "status": "request_limit"}, status=429)
        # Admission uses exactly the same freshness/control gates as the page.
        state = self.bridge.state
        keypad = state.keypads[p]
        if not (state.live_snapshot_complete and keypad.initialized and keypad.session_fresh):
            return web.json_response({"accepted": False, "status": "state_not_current"}, status=409)
        namespace = hashlib.sha256(f"{user['id']}:{generation}:{p}:{audit}".encode()).hexdigest()
        accepted, status = self.bridge.enqueue_keypad_control(p, key, {
            "interaction_id": internal, "audit_interaction_id": "ingress:" + namespace,
            "audit_request_id": internal, "actor_id": user["id"],
            "actor_name": user["display_name"] or user["name"], "source": "ha_ingress",
            "action": "keypad_sequence", "interaction_complete": True,
            "started_at": datetime.now(timezone.utc).isoformat(),
        })
        response = {"accepted": bool(accepted), "status": status, "transaction_id": txn}
        http_status = 202 if accepted else 409
        self._records[internal] = {"at": time.monotonic(), "user_id": user["id"], "partition": p,
                                   "transaction_id": txn, "digest": digest, "response": response,
                                   "http_status": http_status}
        return web.json_response(response, status=http_status)

    async def _websocket(self, request):
        if len(self._sockets) >= 8:
            raise web.HTTPServiceUnavailable(text="Too many status connections")
        ws = web.WebSocketResponse(heartbeat=15, max_msg_size=1024, compress=False)
        await ws.prepare(request)
        self._sockets.add(ws)
        user = request["ingress_user"]
        try:
            while not ws.closed:
                if not await self.authorizer.allowed(user["id"]):
                    await ws.close(code=1008, message=b"Administrator access required")
                    break
                async with asyncio.timeout(5):
                    await ws.send_json({"type": "snapshot", "data": await self._snapshot_data(user)})
                try:
                    message = await ws.receive(timeout=1)
                except asyncio.TimeoutError:
                    continue
                if message.type in {WSMsgType.CLOSE, WSMsgType.CLOSED, WSMsgType.ERROR}:
                    break
        except (AdminAuthorizationUnavailable, TimeoutError, ConnectionError):
            await ws.close(code=1011)
        finally:
            self._sockets.discard(ws)
        return ws
