from __future__ import annotations

from datetime import datetime, timezone
import time
from typing import Any

from .version import VERSION
from .admin_status import event_presentation, operational_status


class AdminSnapshotBuilder:
    """Build a privacy-bounded snapshot for the ingress management UI."""

    def __init__(self, bridge) -> None:
        self.bridge = bridge
        self.started_at = datetime.now(timezone.utc).isoformat()
        self._started_monotonic = time.monotonic()

    def build(self, user: dict[str, str] | None = None, *, journal_stats=None) -> dict[str, Any]:
        bridge = self.bridge
        state = bridge.state
        status = operational_status(bridge)
        connected = bool(bridge._is_connected())
        automation_available = bool(bridge.control.automation_available())
        keypad_control_available = bool(
            connected
            and automation_available
            and status["state_fresh"]
            and bridge.settings.control.enabled
            and bridge.settings.control.keypad_enabled
        )

        event_stats = None
        if bridge.event_store is not None and getattr(bridge.settings.event_history, "enabled", True):
            stats = journal_stats if journal_stats is not None else bridge.event_store.stats()
            event_stats = {
                "enabled": True,
                "count": stats.count,
                "last_dump_at": stats.last_dump_at,
                "last_dump_seen": stats.last_dump_seen,
                "last_dump_inserted": stats.last_dump_inserted,
                "retention_days": bridge.settings.event_history.max_age_days,
                "max_rows": bridge.settings.event_history.max_rows,
            }
        else:
            event_stats = {
                "enabled": False,
                "count": 0,
                "last_dump_at": "",
                "last_dump_seen": 0,
                "last_dump_inserted": 0,
                "retention_days": bridge.settings.event_history.max_age_days,
                "max_rows": bridge.settings.event_history.max_rows,
            }

        partitions = status["partitions"]

        keypads = {}
        for number in bridge.settings.keypad.partitions:
            keypad = state.keypads[number]
            keypads[str(number)] = {
                **keypad.attributes(),
                "state": keypad.ha_state,
                "initialized": keypad.initialized,
                "available": bool(
                    status["state_fresh"] and keypad.initialized and keypad.session_fresh
                ),
                "control_enabled": bool(keypad_control_available and keypad.initialized and keypad.session_fresh),
                # The existing keypad component uses the topic shape to infer
                # the partition. In ingress this is only an adapter identifier;
                # browser keypresses never traverse MQTT.
                "command_topic": f"vista/ingress/keypad/{number}/command",
            }

        last_event = None
        event = state.last_event
        if event is not None:
            descriptor = ""
            if event.zone in state.zones:
                descriptor = state.zones[event.zone].descriptor
            last_event = {
                "event_code": event.code,
                "description": event.description,
                "zone": event.zone,
                "user": event.user,
                "partition": event.partition,
                "panel_timestamp": event.panel_timestamp,
                "descriptor": descriptor,
            }

        if last_event is not None:
            last_event["received_at"] = getattr(getattr(bridge, "handler", None), "last_event_received_at", "")
            last_event = event_presentation(last_event)

        printer_metrics = bridge.printer.metrics
        mqtt_connected = False
        try:
            mqtt_connected = bool(bridge.mqtt.connected)
        except Exception:
            mqtt_connected = False
        diagnostic_runtime = (
            bridge.diagnostics.runtime_state()
            if getattr(bridge, "diagnostics", None) is not None
            else {
                "available": False,
                "write_errors": 0,
                "dropped_events": 0,
                "pending_writes": 0,
                "writer_alive": False,
            }
        )

        return {
            "app": {
                "name": "Vista Turbo RS232",
                "version": VERSION,
                "started_at": self.started_at,
                "uptime_seconds": max(
                    0, int(time.monotonic() - self._started_monotonic)
                ),
            },
            "user": dict(user or {}),
            "panel": {
                "connected": connected,
                "host": bridge.settings.panel.host,
                "port": bridge.settings.panel.port,
                "timezone": bridge.settings.panel.timezone,
                "automation_available": automation_available,
                "automation_availability_source": (
                    bridge.control.automation_availability_source()
                ),
                "state_fresh": status["state_fresh"],
                "alarm_knowledge_complete": bool(
                    connected and state.alarm_knowledge_complete
                ),
                "session_generation": state.session_generation,
            },
            "system": {
                "condition": status["condition"],
                "conditions": status["conditions"],
                "complete": status["complete"],
                "alarm_states": status["alarm_states"],
                "ac_power": state.ac_power,
                "battery_low": state.system_battery_low,
                "active_global_alarm_count": len(
                    state.active_global_alarm_tokens
                ),
                "active_global_trouble_count": len(
                    state.active_global_trouble_tokens
                ),
            },
            "control": {
                "enabled": bridge.settings.control.enabled,
                "keypad_enabled": bridge.settings.control.keypad_enabled,
                "native_alarm_enabled": (
                    bridge.settings.control.native_alarm_enabled
                ),
                "keypad_available": keypad_control_available,
            },
            "partitions": partitions,
            "keypads": keypads,
            "last_event": last_event,
            "journal": event_stats,
            "synchronizer": {
                "active": bridge.synchronizer.is_active(),
                "pending_transaction": (
                    bridge.synchronizer.pending_transaction_kind()
                ),
                "failures_total": bridge.synchronizer.failures_total,
                "failures_consecutive": (
                    bridge.synchronizer.failures_consecutive
                ),
                "last_success_at": bridge.synchronizer.last_success_at,
            },
            "transport": {
                "rx_frames": bridge.rx_frames,
                "rx_bytes": bridge.rx_bytes,
                "tx_frames": bridge.tx_frames,
                "tx_bytes": bridge.tx_bytes,
                "invalid_frames": bridge.invalid_frames,
                "tx_queue_depth": bridge._tx_queue.qsize(),
                "raw_tx_queue_depth": bridge._raw_tx_queue.qsize(),
                "telnet_active": bool(bridge._telnet.active),
            },
            "mqtt": {
                "connected": mqtt_connected,
                "publish_errors": bridge.mqtt.publish_errors,
                "tls_enabled": bridge.settings.mqtt.tls_enabled,
            },
            "diagnostics": {
                **diagnostic_runtime,
                "retention_days": bridge.settings.diagnostics.max_age_days,
                "max_rows": bridge.settings.diagnostics.max_rows,
            },
            "printer": {
                "enabled": bridge.printer.enabled,
                "status": printer_metrics.status,
                "queue_depth": printer_metrics.queue_depth,
                "completed": printer_metrics.completed,
                "uncertain": printer_metrics.uncertain,
                "failed": printer_metrics.failed,
                "dropped": printer_metrics.dropped,
                "last_error": printer_metrics.last_error,
                "last_completed_at": printer_metrics.last_completed_at,
            },
        }
