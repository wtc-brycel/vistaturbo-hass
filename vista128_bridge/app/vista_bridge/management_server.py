from __future__ import annotations

from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import logging
import mimetypes
from pathlib import Path
import re
import threading
from urllib.parse import parse_qs, unquote, urlparse

from .management_auth import ManagementAuthorizer
from .management_store import ManagementStore

LOG = logging.getLogger(__name__)
_SESSION_COOKIE = "vista_admin_session"
_DEFAULT_INGRESS_PROXY = "172.30.32.2"
_INGRESS_PATH = re.compile(r"^/api/hassio_ingress/[A-Za-z0-9._~-]{8,128}/$")


class ManagementServer:
    """Supervisor-ingress-only management UI/API server."""

    def __init__(
        self,
        bridge,
        *,
        host: str = "0.0.0.0",
        port: int = 8099,
        static_dir: str = "/app/management_static",
        allowed_proxy_ips: tuple[str, ...] = (_DEFAULT_INGRESS_PROXY,),
    ) -> None:
        if bridge.event_store is None:
            raise RuntimeError("management server requires the event store")
        self.bridge = bridge
        self.static_dir = Path(static_dir)
        self.allowed_proxy_ips = frozenset(
            str(address).strip() for address in allowed_proxy_ips if str(address).strip()
        )
        if not self.allowed_proxy_ips:
            raise ValueError("at least one ingress proxy address is required")
        self.store = ManagementStore(bridge.settings.event_history.sqlite_path)
        self.store.ensure_indexes()
        self.auth = ManagementAuthorizer(self.store)
        handler = self._handler_type()
        self._httpd = ThreadingHTTPServer((host, int(port)), handler)
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(
            target=self._httpd.serve_forever,
            name="management-http",
            daemon=True,
        )
        self._thread.start()
        LOG.info("Management ingress listening on %s:%s", *self._httpd.server_address)
        if not self.auth.unlock_configured():
            LOG.info("Vista management administrator password is not configured yet")

    def stop(self) -> None:
        if self._thread is None:
            return
        self._httpd.shutdown()
        self._httpd.server_close()
        self._thread.join(timeout=3)
        self._thread = None

    def _handler_type(self):
        owner = self

        class Handler(BaseHTTPRequestHandler):
            server_version = "VistaTurboManagement/1"

            def log_message(self, fmt, *args):
                LOG.debug("management: " + fmt, *args)

            def _identity(self):
                remote_address = str(self.client_address[0])
                if remote_address not in owner.allowed_proxy_ips:
                    LOG.warning(
                        "Rejected management request from non-ingress address %s",
                        remote_address,
                    )
                    self._json(
                        {"error": "Supervisor ingress proxy required"},
                        HTTPStatus.FORBIDDEN,
                    )
                    return None
                try:
                    return owner.auth.identity_from_headers(self.headers)
                except PermissionError:
                    self._json(
                        {"error": "Home Assistant ingress identity required"},
                        HTTPStatus.FORBIDDEN,
                    )
                    return None

            def _ingress_cookie_path(self) -> str | None:
                value = str(self.headers.get("X-Vista-Ingress-Base", "")).strip()
                return value if _INGRESS_PATH.fullmatch(value) else None

            def _token(self) -> str:
                cookie = SimpleCookie()
                cookie.load(self.headers.get("Cookie", ""))
                morsel = cookie.get(_SESSION_COOKIE)
                return morsel.value if morsel else ""

            def _elevated(self, identity) -> bool:
                return owner.auth.elevated(identity, self._token())

            def _require_elevated(self, identity) -> bool:
                if self._elevated(identity):
                    return True
                self._json(
                    {"error": "Vista administrator unlock required"},
                    HTTPStatus.FORBIDDEN,
                )
                return False

            def _json(
                self,
                payload,
                status=HTTPStatus.OK,
                *,
                cookie: str | None = None,
            ):
                body = json.dumps(
                    payload,
                    ensure_ascii=True,
                    separators=(",", ":"),
                ).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.send_header("X-Frame-Options", "SAMEORIGIN")
                if cookie is not None:
                    self.send_header("Set-Cookie", cookie)
                self.end_headers()
                self.wfile.write(body)

            def _read_json(self):
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                except ValueError:
                    length = 0
                if length < 0 or length > 16384:
                    raise ValueError("request body too large")
                raw = self.rfile.read(length) if length else b"{}"
                value = json.loads(raw.decode("utf-8"))
                if not isinstance(value, dict):
                    raise ValueError("JSON object required")
                return value

            def do_GET(self):
                identity = self._identity()
                if identity is None:
                    return
                parsed = urlparse(self.path)
                path = parsed.path.rstrip("/") or "/"
                if path == "/api/session":
                    self._json(
                        {
                            "user_id": identity.user_id,
                            "user_name": identity.user_name,
                            "ha_admin_panel": True,
                            "unlock_configured": owner.auth.unlock_configured(),
                            "elevated": self._elevated(identity),
                        }
                    )
                    return
                if path.startswith("/api/") and not self._require_elevated(identity):
                    return
                if path == "/api/partitions":
                    self._json(owner._partition_payload())
                    return
                if path == "/api/logs":
                    q = parse_qs(parsed.query)

                    def one(name, default=""):
                        return q.get(name, [default])[0]

                    try:
                        page = owner.store.query_logs(
                            search=one("q"),
                            record_type=one("type", "all"),
                            partition=(
                                int(one("partition")) if one("partition") else None
                            ),
                            source_result=one("source"),
                            zone=int(one("zone")) if one("zone") else None,
                            user_number=(
                                int(one("user")) if one("user") else None
                            ),
                            actor=one("actor"),
                            status=one("status"),
                            start_at=one("start"),
                            end_at=one("end"),
                            sort=one("sort", "time"),
                            direction=one("direction", "desc"),
                            page=int(one("page", "1")),
                            page_size=int(one("page_size", "50")),
                        )
                    except (ValueError, TypeError) as exc:
                        self._json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
                        return
                    self._json(
                        {
                            "records": page.records,
                            "total": page.total,
                            "page": page.page,
                            "page_size": page.page_size,
                        }
                    )
                    return
                if path.startswith("/api/audit/"):
                    interaction_id = unquote(path[len("/api/audit/") :])
                    detail = owner.store.audit_detail(
                        interaction_id,
                        include_sensitive=True,
                    )
                    if detail is None:
                        self._json({"error": "not found"}, HTTPStatus.NOT_FOUND)
                        return
                    detail["sensitive_included"] = True
                    self._json(detail)
                    return
                if path.startswith("/api/"):
                    self._json({"error": "not found"}, HTTPStatus.NOT_FOUND)
                    return
                self._static(path)

            def do_POST(self):
                identity = self._identity()
                if identity is None:
                    return
                path = urlparse(self.path).path.rstrip("/")
                try:
                    payload = self._read_json()
                except (ValueError, json.JSONDecodeError, UnicodeDecodeError) as exc:
                    self._json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
                    return
                if path in {
                    "/api/admin/setup",
                    "/api/admin/unlock",
                    "/api/admin/lock",
                }:
                    cookie_path = self._ingress_cookie_path()
                    if cookie_path is None:
                        self._json(
                            {"error": "valid Vista ingress base path required"},
                            HTTPStatus.BAD_REQUEST,
                        )
                        return
                else:
                    cookie_path = None
                if path == "/api/admin/setup":
                    if owner.auth.unlock_configured():
                        self._json(
                            {"error": "administrator unlock is already configured"},
                            HTTPStatus.CONFLICT,
                        )
                        return
                    try:
                        token = owner.auth.setup(
                            identity,
                            str(payload.get("secret", "")),
                        )
                    except (ValueError, RuntimeError) as exc:
                        self._json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
                        return
                    self._json(
                        {"elevated": True},
                        cookie=owner._session_cookie(token, cookie_path),
                    )
                    return
                if path == "/api/admin/unlock":
                    try:
                        token = owner.auth.unlock(
                            identity,
                            str(payload.get("secret", "")),
                        )
                    except PermissionError as exc:
                        self._json({"error": str(exc)}, HTTPStatus.FORBIDDEN)
                        return
                    self._json(
                        {"elevated": True},
                        cookie=owner._session_cookie(token, cookie_path),
                    )
                    return
                if path == "/api/admin/lock":
                    owner.auth.lock(identity, self._token())
                    self._json(
                        {"elevated": False},
                        cookie=owner._expired_cookie(cookie_path),
                    )
                    return
                if not self._require_elevated(identity):
                    return
                if path == "/api/keypad":
                    try:
                        partition = int(payload.get("partition", 0))
                        key = str(payload.get("key", ""))
                    except (TypeError, ValueError):
                        self._json(
                            {"error": "invalid keypad request"},
                            HTTPStatus.BAD_REQUEST,
                        )
                        return
                    if (
                        partition < 1
                        or partition > 8
                        or key not in set("0123456789*#")
                    ):
                        self._json(
                            {"error": "invalid keypad request"},
                            HTTPStatus.BAD_REQUEST,
                        )
                        return
                    metadata = {
                        "interaction_id": str(
                            payload.get(
                                "transaction_id",
                                payload.get("interaction_id", ""),
                            )
                        )[:96],
                        "audit_interaction_id": str(
                            payload.get("audit_interaction_id", "")
                        )[:96],
                        "actor_id": identity.user_id,
                        "actor_name": identity.user_name,
                        "source": "ha_frontend",
                        "action": "keypad_sequence",
                        "interaction_complete": bool(
                            payload.get("complete", True)
                        ),
                    }
                    ok, status = owner.bridge.enqueue_keypad_control(
                        partition,
                        key,
                        metadata,
                    )
                    self._json(
                        {"ok": bool(ok), "status": status},
                        HTTPStatus.OK if ok else HTTPStatus.CONFLICT,
                    )
                    return
                self._json({"error": "not found"}, HTTPStatus.NOT_FOUND)

            def _static(self, path: str):
                rel = "index.html" if path == "/" else unquote(path.lstrip("/"))
                if ".." in Path(rel).parts:
                    self._json({"error": "not found"}, HTTPStatus.NOT_FOUND)
                    return
                file = (owner.static_dir / rel).resolve()
                try:
                    file.relative_to(owner.static_dir.resolve())
                except ValueError:
                    self._json({"error": "not found"}, HTTPStatus.NOT_FOUND)
                    return
                if not file.is_file():
                    file = owner.static_dir / "index.html"
                    if not file.is_file():
                        self._json(
                            {"error": "management frontend unavailable"},
                            HTTPStatus.NOT_FOUND,
                        )
                        return
                body = file.read_bytes()
                mime = mimetypes.guess_type(str(file))[0] or "application/octet-stream"
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", mime)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-cache")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.send_header("X-Frame-Options", "SAMEORIGIN")
                self.send_header(
                    "Content-Security-Policy",
                    "default-src 'self'; style-src 'self' 'unsafe-inline'; "
                    "script-src 'self'; img-src 'self' data:; connect-src 'self'; "
                    "frame-ancestors 'self'",
                )
                self.end_headers()
                self.wfile.write(body)

        return Handler

    def _partition_payload(self) -> dict:
        partitions = []
        for number, state in sorted(self.bridge.state.partitions.items()):
            attrs = state.attributes()
            attrs["partition"] = number
            attrs["arming_state"] = attrs.get("vista_mode", "unknown")
            keypad = self.bridge.state.keypads.get(number)
            if keypad is not None:
                attrs["keypad"] = {
                    "state": keypad.ha_state,
                    "attributes": keypad.attributes(),
                }
            partitions.append(attrs)
        zones = [
            zone.attributes()
            for zone in self.bridge.state.zones.values()
            if zone.partition
        ]
        return {
            "authoritative": bool(self.bridge.state.security_snapshot_complete),
            "partitions": partitions,
            "zones": zones,
        }

    @staticmethod
    def _session_cookie(token: str, path: str) -> str:
        return (
            f"{_SESSION_COOKIE}={token}; Path={path}; HttpOnly; "
            "SameSite=Strict; Max-Age=1200"
        )

    @staticmethod
    def _expired_cookie(path: str) -> str:
        return (
            f"{_SESSION_COOKIE}=; Path={path}; HttpOnly; "
            "SameSite=Strict; Max-Age=0"
        )
