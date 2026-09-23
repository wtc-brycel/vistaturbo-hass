from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import AsyncMock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

from aiohttp import ClientResponseError, WSMsgType
from aiohttp.test_utils import TestClient, TestServer
from vista_bridge.admin_auth import AdminAuthorizationUnavailable, HomeAssistantAdminAuthorizer
from vista_bridge.admin_server import AdminServer
from vista_bridge.admin_snapshot import AdminSnapshotBuilder
from vista_bridge.admin_status import event_presentation
from vista_bridge.diagnostics import DiagnosticEvents as DE, DiagnosticJournal
from vista_bridge.event_store import EventStore
from vista_bridge.protocol import SystemEvent
from admin_fixture import Authorizer, Bridge


def event(code, partition=1, zone=1):
    return SystemEvent(code, "Fixture description", zone, 0, partition, 10, 23, 21, 9, 26)


class StatusWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.bridge = Bridge()

    def snapshot(self):
        return AdminSnapshotBuilder(self.bridge).build()

    def test_normal_requires_complete_evidence(self):
        self.assertEqual(self.snapshot()["system"]["condition"]["title"], "SYSTEM NORMAL")
        self.bridge.state.system_battery_low = None
        self.assertEqual(self.snapshot()["system"]["condition"]["title"], "STATUS INCOMPLETE")

    def test_startup_does_not_invent_ready_or_eight_partitions(self):
        self.bridge.state.reset_connection_derived_annunciators()
        s = self.snapshot()
        self.assertEqual(list(s["partitions"]), ["1"])
        self.assertIsNone(s["partitions"]["1"]["ready"])
        self.assertIsNone(s["partitions"]["1"]["vista_mode"])
        self.assertFalse(s["keypads"]["1"]["control_enabled"])
        self.assertNotEqual(s["system"]["condition"]["kind"], "normal")

    def test_core_snapshot_is_not_complete_alarm_knowledge(self):
        self.bridge.state.security_snapshot_complete = False
        s = self.snapshot()
        self.assertTrue(s["panel"]["state_fresh"])
        self.assertFalse(s["system"]["complete"])
        self.assertEqual(s["partitions"]["1"]["condition"]["text"], "UNKNOWN")

    def test_global_fire_is_not_lost(self):
        self.bridge.state.apply_system_event(event("01", 0))
        self.assertEqual(self.snapshot()["system"]["condition"]["kind"], "fire")
        self.assertEqual(self.snapshot()["system"]["conditions"][0]["partition"], 0)

    def test_untyped_zone_alarm_is_not_normal(self):
        self.bridge.state.zones[1].alarm = True
        self.assertEqual(self.snapshot()["system"]["condition"]["title"], "ALARM")

    def test_keypad_only_fire_is_included(self):
        self.bridge.state.keypads[1].fire_alarm_led = True
        self.assertEqual(self.snapshot()["system"]["condition"]["kind"], "fire")

    def test_partition_trouble_and_keypad_trouble_are_included(self):
        self.bridge.state.apply_system_event(event("53"))
        self.assertEqual(self.snapshot()["system"]["condition"]["kind"], "trouble")
        self.bridge = Bridge()
        self.bridge.state.keypads[1].trouble_led = True
        self.assertEqual(self.snapshot()["system"]["condition"]["kind"], "trouble")

    def test_fire_remains_during_incomplete_sync(self):
        self.bridge.state.apply_system_event(event("01"))
        self.bridge.state.begin_query_snapshot("arming_status")
        self.assertEqual(self.snapshot()["system"]["condition"]["kind"], "fire")
        self.assertFalse(self.snapshot()["panel"]["state_fresh"])

    def test_disconnected_cached_values_do_not_look_current(self):
        self.bridge.connected = False
        s = self.snapshot()
        self.assertEqual(s["system"]["condition"]["title"], "PANEL OFFLINE")
        self.assertIsNone(s["partitions"]["1"]["vista_mode"])
        self.assertFalse(s["keypads"]["1"]["available"])

    def test_fault_and_bypass_are_not_fire_or_trouble(self):
        self.bridge.state.zones[1].faulted = True
        self.assertEqual(self.snapshot()["system"]["condition"]["kind"], "fault")
        self.bridge.state.zones[1].bypassed = True
        self.assertEqual(self.snapshot()["system"]["condition"]["kind"], "bypass")

    def test_event_colours_use_codes_not_english(self):
        for code, kind in (("E1", "supervisory"), ("C3", "trouble"), ("07", "neutral"), ("C2", "restore"), ("ZZ", "neutral")):
            with self.subTest(code=code):
                self.assertEqual(event_presentation({"event_code": code, "description": "Fire alarm"})["kind"], kind)

    def test_active_unconfigured_partition_is_not_hidden(self):
        self.bridge.state.apply_system_event(event("41", 7))
        self.assertIn("7", self.snapshot()["partitions"])


class AuthorizationTests(unittest.IsolatedAsyncioTestCase):
    def test_only_active_human_admins_and_owner(self):
        users = [
            {"id": "owner", "is_active": True, "system_generated": False, "is_owner": True},
            {"id": "admin", "is_active": True, "system_generated": False, "group_ids": ["system-admin"]},
            {"id": "member", "is_active": True, "system_generated": False, "group_ids": ["system-users"]},
            {"id": "inactive", "is_active": False, "system_generated": False, "group_ids": ["system-admin"]},
            {"id": "service", "is_active": True, "system_generated": True, "group_ids": ["system-admin"]},
        ]
        self.assertEqual(HomeAssistantAdminAuthorizer.admin_ids(users), {"owner", "admin"})

    async def test_lookup_failure_does_not_reuse_expired_allowance(self):
        authorizer = HomeAssistantAdminAuthorizer(token="test-not-a-real-token")
        authorizer._load = AsyncMock(return_value=frozenset({"admin"}))
        self.assertTrue(await authorizer.allowed("admin"))
        authorizer._expires = 0
        authorizer._load.side_effect = AdminAuthorizationUnavailable()
        with self.assertRaises(AdminAuthorizationUnavailable):
            await authorizer.allowed("admin")
        self.assertFalse(authorizer._ids)


class AdminApiWorkflowTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.store = EventStore(str(Path(self.directory.name) / "journal.db"))
        self.diagnostics = DiagnosticJournal(
            str(Path(self.directory.name) / "diagnostics.db"),
            max_age_days=30,
            max_rows=25000,
        )
        self.bridge = Bridge(self.store, self.diagnostics)
        self.authorizer = Authorizer()
        self.server = AdminServer(self.bridge, trusted_proxy_ips={"127.0.0.1"}, authorizer=self.authorizer)
        self.client = TestClient(TestServer(self.server.app))
        await self.client.start_server()
        self.headers = {"X-Remote-User-Id": "admin", "X-Remote-User-Display-Name": "Fixture Administrator", "Origin": str(self.client.make_url("/")).rstrip("/")}
        self.snapshot = await (await self.client.get("/api/snapshot", headers=self.headers)).json()
        self.headers["X-Vista-CSRF"] = self.snapshot["csrf_token"]
        self.payload = {"key": "7", "partition": 1, "transaction_id": "fixture-key-1", "audit_interaction_id": "fixture-group",
                        "session_generation": self.snapshot["panel"]["session_generation"], "instance_id": self.snapshot["instance_id"]}

    async def asyncTearDown(self):
        await self.client.close()
        self.diagnostics.close(timeout=2.0)
        self.directory.cleanup()

    async def post(self, payload=None, headers=None):
        return await self.client.post("/api/keypad", json=self.payload if payload is None else payload, headers=self.headers if headers is None else headers)

    async def test_non_admin_denied_even_with_spoofed_admin_header(self):
        h = {**self.headers, "X-Remote-User-Id": "member", "X-Remote-User-Admin": "true"}
        self.assertEqual((await self.client.get("/api/snapshot", headers=h)).status, 403)

    async def test_proxy_peer_not_forwarded_for_is_authoritative(self):
        self.server.trusted_proxy_ips = {"172.30.32.2"}
        h = {**self.headers, "X-Forwarded-For": "172.30.32.2"}
        self.assertEqual((await self.client.get("/api/snapshot", headers=h)).status, 403)

    async def test_missing_identity_denied(self):
        self.assertEqual((await self.client.get("/api/snapshot")).status, 401)

    async def test_unverifiable_admin_denied(self):
        self.authorizer.allowed = AsyncMock(side_effect=AdminAuthorizationUnavailable())
        self.assertEqual((await self.client.get("/api/snapshot", headers=self.headers)).status, 503)

    async def test_key_queued_then_panel_acknowledged(self):
        response = await self.post()
        self.assertEqual(response.status, 202)
        self.assertEqual((await response.json())["status"], "queued")
        await self.bridge.control.process_next()
        await asyncio.sleep(0)
        snapshot = await (await self.client.get("/api/snapshot", headers=self.headers)).json()
        self.assertEqual(snapshot["control_results"][0]["status"], "accepted")
        self.assertEqual(set(snapshot["control_results"][0]), {"transaction_id", "partition", "ok", "status"})
        self.assertEqual(self.bridge.audit[0]["actor_id"], "admin")
        self.assertNotIn("never-export-mqtt-password", json.dumps(snapshot))

    async def test_control_results_not_shared_between_users(self):
        await self.post(); await self.bridge.control.process_next(); await asyncio.sleep(0)
        h = {**self.headers, "X-Remote-User-Id": "second-admin"}
        snapshot = await (await self.client.get("/api/snapshot", headers=h)).json()
        self.assertEqual(snapshot["control_results"], [])

    async def test_duplicate_key_does_not_enqueue_twice(self):
        await self.post(); response = await self.post()
        self.assertEqual(response.status, 202)
        self.assertEqual(self.bridge.control._queue.qsize(), 1)
        self.assertEqual((await self.post({**self.payload, "key": "8"})).status, 409)
        self.assertEqual(self.bridge.control._queue.qsize(), 1)

    async def test_stale_session_rejected_before_enqueue(self):
        self.bridge.state.session_generation += 1
        self.assertEqual((await self.post()).status, 409)
        self.assertTrue(self.bridge.control._queue.empty())

    async def test_stale_display_rejected_before_enqueue(self):
        self.bridge.state.keypads[1].session_fresh = False
        self.assertEqual((await self.post()).status, 409)
        self.assertTrue(self.bridge.control._queue.empty())

    async def test_disabled_control_stays_disabled(self):
        self.bridge.control.settings = replace(self.bridge.control.settings, enabled=False)
        result = await self.post()
        self.assertEqual((await result.json())["status"], "control_disabled")
        self.assertTrue(self.bridge.control._queue.empty())

    async def test_cross_origin_and_missing_csrf_denied(self):
        self.assertEqual((await self.post(headers={**self.headers, "Origin": "https://example.invalid"})).status, 403)
        self.assertEqual((await self.post(headers={k: v for k, v in self.headers.items() if k != "X-Vista-CSRF"})).status, 403)

    async def test_invalid_inputs_and_actor_spoof_rejected(self):
        for patch in ({"partition": True}, {"partition": 2}, {"key": "1234"}, {"key": "PANIC_A"}, {"transaction_id": ""}, {"actor_id": "other"}):
            with self.subTest(patch=patch):
                self.assertEqual((await self.post({**self.payload, **patch})).status, 400)
        self.assertTrue(self.bridge.control._queue.empty())

    async def test_history_available_while_panel_offline(self):
        self.store.record(event("01"), source="live", received_at=datetime.now(timezone.utc).isoformat())
        self.bridge.connected = False
        result = await (await self.client.get("/api/events", headers=self.headers)).json()
        self.assertEqual(result["events"][0]["event_code"], "01")

    async def test_system_filter_is_not_all_partitions(self):
        for p in (0, 1):
            self.store.record(event("1C", p), source="live", received_at=datetime.now(timezone.utc).isoformat())
        result = await (await self.client.get("/api/events?partition=system", headers=self.headers)).json()
        self.assertEqual([e["partition"] for e in result["events"]], [0])

    async def test_invalid_queries_are_400_not_clamped_or_500(self):
        for query in ("partition=9", "partition=-1", "limit=101", "source=no", "cursor=!!", "event_code=invalid", "zone=99999"):
            with self.subTest(query=query):
                self.assertEqual((await self.client.get("/api/events?" + query, headers=self.headers)).status, 400)

    async def test_literal_search_and_bounded_pages(self):
        for i, descriptor in enumerate(("Door_1", "DoorX1")):
            self.store.record(event("F5", zone=i + 1), source="live", received_at=datetime.now(timezone.utc).isoformat(), descriptor=descriptor)
        result = await (await self.client.get("/api/events?q=_", headers=self.headers)).json()
        self.assertEqual(len(result["events"]), 1)
        page = await (await self.client.get("/api/events?limit=1", headers=self.headers)).json()
        following = await (await self.client.get("/api/events?limit=1&cursor=" + page["next_cursor"], headers=self.headers)).json()
        self.assertNotEqual(page["events"][0]["id"], following["events"][0]["id"])

    async def test_diagnostics_api_filters_pages_and_groups_incidents(self):
        correlation = self.diagnostics.new_id("ha")
        self.diagnostics.record(
            DE.HA_WATCHDOG_TRIGGERED,
            severity="error",
            component="mqtt",
            message="Heartbeat acknowledgement timed out",
            correlation_id=correlation,
            occurred_at="2026-09-23T10:00:00+00:00",
        )
        self.diagnostics.record(
            DE.HA_RECOVERY_STARTED,
            severity="warning",
            component="mqtt",
            correlation_id=correlation,
            occurred_at="2026-09-23T10:00:01+00:00",
        )
        self.diagnostics.record(
            DE.STATE_REPLAY_COMPLETED,
            component="mqtt",
            correlation_id=correlation,
            occurred_at="2026-09-23T10:00:02+00:00",
        )
        self.diagnostics.record(
            DE.INVALID_FRAME,
            severity="warning",
            component="vista-rs232",
            occurred_at="2026-09-23T10:01:00+00:00",
        )

        first = await (
            await self.client.get(
                "/api/diagnostics?limit=1&category=ha_transport",
                headers=self.headers,
            )
        ).json()
        self.assertTrue(first["enabled"])
        self.assertEqual(len(first["records"]), 1)
        self.assertTrue(first["next_cursor"])
        self.assertEqual(first["records"][0]["category"], "ha_transport")
        self.assertEqual(first["incidents"][0]["correlation_id"], correlation)

        second = await (
            await self.client.get(
                "/api/diagnostics?limit=1&category=ha_transport&cursor="
                + first["next_cursor"],
                headers=self.headers,
            )
        ).json()
        self.assertNotEqual(first["records"][0]["id"], second["records"][0]["id"])

        oldest = await (
            await self.client.get(
                "/api/diagnostics?limit=1&order=oldest",
                headers=self.headers,
            )
        ).json()
        self.assertEqual(oldest["records"][0]["event_type"], DE.HA_WATCHDOG_TRIGGERED)

        incident = await (
            await self.client.get(
                "/api/diagnostics?correlation_id=" + correlation,
                headers=self.headers,
            )
        ).json()
        self.assertEqual(len(incident["records"]), 3)
        self.assertEqual(
            {record["correlation_id"] for record in incident["records"]},
            {correlation},
        )

    async def test_diagnostics_api_never_exposes_sensitive_detail_values(self):
        secret = "never-export-this-diagnostic-secret"
        self.diagnostics.record(
            DE.QUEUE_SATURATED,
            severity="warning",
            component="runtime",
            details={"password": secret, "payload": secret, "queue": "tx"},
        )
        response = await self.client.get("/api/diagnostics", headers=self.headers)
        body = await response.text()
        self.assertEqual(response.status, 200)
        self.assertNotIn(secret, body)
        result = json.loads(body)
        self.assertEqual(result["records"][0]["details"]["password"], "[redacted]")
        self.assertEqual(result["records"][0]["details"]["payload"], "[redacted]")

    async def test_invalid_diagnostic_queries_are_rejected(self):
        for query in (
            "limit=101",
            "severity=fatal",
            "category=unknown",
            "event_type=ha_transport.nope",
            "component=bad%20component",
            "correlation_id=bad%20incident",
            "order=sideways",
            "cursor=!!",
        ):
            with self.subTest(query=query):
                response = await self.client.get(
                    "/api/diagnostics?" + query,
                    headers=self.headers,
                )
                self.assertEqual(response.status, 400)

    async def test_snapshot_exposes_diagnostic_writer_health_only(self):
        snapshot = await (
            await self.client.get("/api/snapshot", headers=self.headers)
        ).json()
        self.assertTrue(snapshot["diagnostics"]["available"])
        self.assertTrue(snapshot["diagnostics"]["writer_alive"])
        self.assertEqual(snapshot["diagnostics"]["retention_days"], 30)
        self.assertEqual(snapshot["diagnostics"]["max_rows"], 25000)
        encoded = json.dumps(snapshot)
        self.assertNotIn(str(self.diagnostics.path), encoded)

    async def test_revoked_admin_socket_closes(self):
        socket = await self.client.ws_connect("/ws", headers=self.headers)
        await socket.receive_json()
        self.authorizer.ids.clear()
        await socket.receive(timeout=3)
        self.assertEqual(socket.close_code, 1008)

    async def test_html_has_no_top_bar_or_description_overlines(self):
        page = await (await self.client.get("/", headers=self.headers)).text()
        self.assertNotIn('class="app-header"', page)
        self.assertNotIn('class="eyebrow"', page)
        self.assertIn('id="system-banner"', page)


if __name__ == "__main__":
    unittest.main()
