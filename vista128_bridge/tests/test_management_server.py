from __future__ import annotations

from contextlib import closing
from http.client import HTTPConnection
import json
from pathlib import Path
import sqlite3
import tempfile
from types import SimpleNamespace
import unittest

from vista_bridge.management_server import ManagementServer
from vista_bridge.state import VistaState

_INGRESS_BASE = "/api/hassio_ingress/test-token-12345678/"


def _initialize(path: str) -> None:
    with closing(sqlite3.connect(path)) as db, db:
        db.executescript(
            """
            CREATE TABLE metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL);
            CREATE TABLE events(
                id INTEGER PRIMARY KEY, occurrence INTEGER NOT NULL DEFAULT 1,
                event_code TEXT NOT NULL, description TEXT NOT NULL,
                zone INTEGER NOT NULL, user_number INTEGER NOT NULL,
                partition_number INTEGER NOT NULL, panel_timestamp TEXT,
                descriptor TEXT NOT NULL DEFAULT '', seen_live INTEGER NOT NULL DEFAULT 0,
                seen_history INTEGER NOT NULL DEFAULT 0,
                last_received_at TEXT NOT NULL
            );
            CREATE TABLE keypad_interactions(
                interaction_id TEXT PRIMARY KEY, started_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL, completed_at TEXT NOT NULL DEFAULT '',
                actor_id TEXT NOT NULL DEFAULT '', actor_name TEXT NOT NULL DEFAULT '',
                partition_number INTEGER NOT NULL, source TEXT NOT NULL,
                action TEXT NOT NULL, command_sequence TEXT NOT NULL DEFAULT '',
                operands_json TEXT NOT NULL DEFAULT '{}', last_request_id TEXT NOT NULL DEFAULT '',
                command_type TEXT NOT NULL DEFAULT '', code TEXT NOT NULL DEFAULT '',
                execution_mechanism TEXT NOT NULL DEFAULT '', confidence TEXT NOT NULL DEFAULT '',
                verification TEXT NOT NULL DEFAULT '', status TEXT NOT NULL, ok INTEGER NOT NULL DEFAULT 0
            );
            """
        )
        db.execute(
            "INSERT INTO keypad_interactions VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                "audit-1",
                "2026-08-30T20:20:00-04:00",
                "2026-08-30T20:20:02-04:00",
                "2026-08-30T20:20:02-04:00",
                "ha-1",
                "Administrator",
                1,
                "ha_frontend",
                "disarm",
                "24681",
                '{"partition":1}',
                "request-1",
                "disarm",
                "2468",
                "native",
                "high",
                "confirmed",
                "confirmed",
                1,
            ),
        )


class FakeBridge:
    def __init__(self, path: str) -> None:
        self.event_store = object()
        self.settings = SimpleNamespace(
            event_history=SimpleNamespace(sqlite_path=path)
        )
        self.state = VistaState()
        self.state.partitions[1].raw_mode = "D"
        self.state.zones[27].partition = 1
        self.state.zones[27].descriptor = "FRONT DOOR"
        self.keypad_calls = []

    def enqueue_keypad_control(self, partition, key, metadata):
        self.keypad_calls.append((partition, key, metadata))
        return True, "queued"


def _request(
    server: ManagementServer,
    method: str,
    path: str,
    *,
    body=None,
    headers=None,
):
    host, port = server._httpd.server_address
    connection = HTTPConnection(host, port, timeout=3)
    payload = None if body is None else json.dumps(body)
    request_headers = dict(headers or {})
    if payload is not None:
        request_headers["Content-Type"] = "application/json"
    connection.request(method, path, body=payload, headers=request_headers)
    response = connection.getresponse()
    raw = response.read()
    result = json.loads(raw.decode("utf-8")) if raw else {}
    set_cookie = response.getheader("Set-Cookie") or ""
    status = response.status
    connection.close()
    return status, result, set_cookie


def _identity_headers(cookie: str = "") -> dict[str, str]:
    headers = {
        "X-Remote-User-Id": "ha-1",
        "X-Remote-User-Name": "Administrator",
        "X-Vista-Ingress-Base": _INGRESS_BASE,
    }
    if cookie:
        headers["Cookie"] = cookie.split(";", 1)[0]
    return headers


class ManagementServerTests(unittest.TestCase):
    def _server(self, directory: str, *, allow_local: bool = True):
        path = str(Path(directory) / "events.sqlite3")
        _initialize(path)
        bridge = FakeBridge(path)
        server = ManagementServer(
            bridge,
            host="127.0.0.1",
            port=0,
            static_dir=str(Path(directory) / "none"),
            allowed_proxy_ips=("127.0.0.1",) if allow_local else ("172.30.32.2",),
        )
        server.start()
        return bridge, server

    def _elevate(self, server: ManagementServer) -> str:
        status, result, cookie = _request(
            server,
            "POST",
            "/api/admin/setup",
            body={"secret": "correct horse battery staple"},
            headers=_identity_headers(),
        )
        self.assertEqual(status, 200)
        self.assertTrue(result["elevated"])
        self.assertIn("HttpOnly", cookie)
        self.assertIn("SameSite=Strict", cookie)
        self.assertIn(f"Path={_INGRESS_BASE}", cookie)
        self.assertNotIn("Path=/;", cookie)
        return cookie

    def test_default_proxy_allowlist_rejects_direct_local_requests(self):
        with tempfile.TemporaryDirectory() as directory:
            _, server = self._server(directory, allow_local=False)
            try:
                status, result, _ = _request(
                    server,
                    "GET",
                    "/api/session",
                    headers=_identity_headers(),
                )
                self.assertEqual(status, 403)
                self.assertEqual(result["error"], "Supervisor ingress proxy required")
            finally:
                server.stop()

    def test_identity_is_required_and_panel_data_requires_elevation(self):
        with tempfile.TemporaryDirectory() as directory:
            _, server = self._server(directory)
            try:
                status, _, _ = _request(server, "GET", "/api/session")
                self.assertEqual(status, 403)

                status, session, _ = _request(
                    server,
                    "GET",
                    "/api/session",
                    headers=_identity_headers(),
                )
                self.assertEqual(status, 200)
                self.assertEqual(session["user_id"], "ha-1")
                self.assertTrue(session["ha_admin_panel"])
                self.assertFalse(session["elevated"])
                self.assertFalse(session["unlock_configured"])

                status, result, _ = _request(
                    server,
                    "GET",
                    "/api/partitions",
                    headers=_identity_headers(),
                )
                self.assertEqual(status, 403)
                self.assertEqual(
                    result["error"],
                    "Vista administrator unlock required",
                )

                cookie = self._elevate(server)
                status, payload, _ = _request(
                    server,
                    "GET",
                    "/api/partitions",
                    headers=_identity_headers(cookie),
                )
                self.assertEqual(status, 200)
                self.assertEqual(payload["partitions"][0]["partition"], 1)
                self.assertTrue(
                    any(
                        zone["zone"] == 27
                        and zone["descriptor"] == "FRONT DOOR"
                        for zone in payload["zones"]
                    )
                )
            finally:
                server.stop()

    def test_admin_cookie_requires_valid_ingress_base_path(self):
        with tempfile.TemporaryDirectory() as directory:
            _, server = self._server(directory)
            try:
                headers = _identity_headers()
                headers["X-Vista-Ingress-Base"] = "/"
                status, result, cookie = _request(
                    server,
                    "POST",
                    "/api/admin/setup",
                    body={"secret": "correct horse battery staple"},
                    headers=headers,
                )
                self.assertEqual(status, 400)
                self.assertEqual(
                    result["error"],
                    "valid Vista ingress base path required",
                )
                self.assertEqual(cookie, "")
                self.assertFalse(server.auth.unlock_configured())
            finally:
                server.stop()

    def test_first_run_setup_does_not_require_out_of_band_token(self):
        with tempfile.TemporaryDirectory() as directory:
            _, server = self._server(directory)
            try:
                status, result, cookie = _request(
                    server,
                    "POST",
                    "/api/admin/setup",
                    body={"secret": "correct horse battery staple"},
                    headers=_identity_headers(),
                )
                self.assertEqual(status, 200)
                self.assertTrue(result["elevated"])
                self.assertTrue(cookie)
                self.assertTrue(server.auth.unlock_configured())

                status, result, _ = _request(
                    server,
                    "POST",
                    "/api/admin/setup",
                    body={"secret": "another correct horse battery staple"},
                    headers=_identity_headers(),
                )
                self.assertEqual(status, 409)
                self.assertEqual(
                    result["error"],
                    "administrator unlock is already configured",
                )
            finally:
                server.stop()

    def test_audit_detail_is_inaccessible_until_step_up_unlock(self):
        with tempfile.TemporaryDirectory() as directory:
            _, server = self._server(directory)
            try:
                status, result, _ = _request(
                    server,
                    "GET",
                    "/api/audit/audit-1",
                    headers=_identity_headers(),
                )
                self.assertEqual(status, 403)
                self.assertEqual(
                    result["error"],
                    "Vista administrator unlock required",
                )

                cookie = self._elevate(server)
                status, detail, _ = _request(
                    server,
                    "GET",
                    "/api/audit/audit-1",
                    headers=_identity_headers(cookie),
                )
                self.assertEqual(status, 200)
                self.assertTrue(detail["sensitive_included"])
                self.assertEqual(detail["command_sequence"], "24681")
                self.assertEqual(detail["code"], "2468")
            finally:
                server.stop()

    def test_keypad_requires_elevation_and_uses_ingress_actor(self):
        with tempfile.TemporaryDirectory() as directory:
            bridge, server = self._server(directory)
            try:
                request = {
                    "key": "1",
                    "partition": 1,
                    "transaction_id": "tx-1",
                    "audit_interaction_id": "audit-browser-1",
                    "complete": True,
                    "actor_id": "spoofed",
                    "actor_name": "spoofed",
                }
                status, _, _ = _request(
                    server,
                    "POST",
                    "/api/keypad",
                    body=request,
                    headers=_identity_headers(),
                )
                self.assertEqual(status, 403)
                self.assertEqual(bridge.keypad_calls, [])

                cookie = self._elevate(server)
                status, result, _ = _request(
                    server,
                    "POST",
                    "/api/keypad",
                    body=request,
                    headers=_identity_headers(cookie),
                )
                self.assertEqual(status, 200)
                self.assertEqual(result, {"ok": True, "status": "queued"})
                self.assertEqual(len(bridge.keypad_calls), 1)
                partition, key, metadata = bridge.keypad_calls[0]
                self.assertEqual((partition, key), (1, "1"))
                self.assertEqual(metadata["actor_id"], "ha-1")
                self.assertEqual(metadata["actor_name"], "Administrator")
                self.assertEqual(metadata["interaction_id"], "tx-1")
                self.assertEqual(
                    metadata["audit_interaction_id"],
                    "audit-browser-1",
                )
                self.assertTrue(metadata["interaction_complete"])
            finally:
                server.stop()


if __name__ == "__main__":
    unittest.main()
