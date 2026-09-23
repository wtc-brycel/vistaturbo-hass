"""Deterministic test data, never imported by the production application."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from queue import Queue
from types import SimpleNamespace as NS

from vista_bridge.config import ControlSettings, KeypadSettings, SyncSettings
from vista_bridge.control import VistaControlCoordinator
from vista_bridge.protocol import ArmingStatusReport, KeypadDisplayReport, ZonePartitionReport, ZoneStatusReport
from vista_bridge.state import VistaState


class Authorizer:
    def __init__(self):
        self.ids = {"admin", "second-admin"}

    async def allowed(self, user_id):
        return user_id in self.ids


class Bridge:
    def __init__(self, store=None):
        self.connected = True
        self.state = VistaState()
        self.state.apply_arming_status(ArmingStatusReport(("D",) * 8))
        self.state.apply_zone_status(ZoneStatusReport(1, (0,) * 64))
        self.state.apply_zone_status(ZoneStatusReport(2, (0,) * 64))
        self.state.apply_zone_partition(ZonePartitionReport(1, (1,) * 7 + (0,) * 57))
        self.state.apply_zone_partition(ZonePartitionReport(2, (0,) * 64))
        self.state.ac_power = True
        self.state.system_battery_low = False
        self.state.apply_keypad_display(1, KeypadDisplayReport(
            "DISARMED        ", "READY TO ARM    ", True, True, False, False, 1, b""
        ), "2026-09-21T23:12:00-04:00")
        self.state.mark_authoritative_snapshot()
        self.settings = NS(
            panel=NS(host="192.0.2.10", port=10001, timezone="America/New_York"),
            keypad=NS(partitions=(1,)),
            control=ControlSettings(True, True, False, 3, 0),
            event_history=NS(enabled=True, max_age_days=90, max_rows=10000),
            mqtt=NS(tls_enabled=False, password="never-export-mqtt-password"),
        )
        self.synchronizer = NS(
            lock=asyncio.Lock(), is_active=lambda: False, pending_transaction_kind=lambda: None,
            failures_total=0, failures_consecutive=0, last_success_at="2026-09-21T23:12:00-04:00",
            begin_external_transaction=lambda: True, end_external_transaction=lambda: None,
            wait_ready=self.wait_ready, request_keypad_refresh=lambda partition: None,
        )
        self.listeners = set()
        self.audit = []
        self.control = VistaControlCoordinator(self.settings.control, self.state, self.synchronizer,
                                               self._is_connected, lambda *args: (True, "queued"),
                                               self.publish_result, self.audit.append)
        self.control.infer_automation_available()
        self.event_store = store
        self.handler = NS(last_event_received_at="")
        self.printer = NS(enabled=False, metrics=NS(status="disabled", queue_depth=0, completed=0,
                          uncertain=0, failed=0, dropped=0, last_error="", last_completed_at=""))
        self.mqtt = NS(_client=NS(is_connected=lambda: True), publish_errors=0)
        self.rx_frames, self.rx_bytes, self.tx_frames, self.tx_bytes, self.invalid_frames = 6248, 109520, 1802, 25180, 0
        self._tx_queue, self._raw_tx_queue = Queue(), Queue()
        self._telnet = NS(active=True)

    async def wait_ready(self, timeout):
        return True

    def _is_connected(self):
        return self.connected

    def enqueue_keypad_control(self, *args):
        return self.control.enqueue_keypad(*args)

    def subscribe_control_results(self, listener):
        self.listeners.add(listener)
        return lambda: self.listeners.discard(listener)

    def publish_result(self, payload):
        for listener in self.listeners:
            listener(payload)
