"""Emit browser-test fixtures using the production snapshot builder."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from vista_bridge.admin_snapshot import AdminSnapshotBuilder
from vista_bridge.admin_status import event_presentation
from vista_bridge.event_codes import EVENT_DESCRIPTIONS
from vista_bridge.protocol import SystemEvent
from admin_fixture import Bridge


def snapshot(bridge):
    result = AdminSnapshotBuilder(bridge).build({"id": "admin", "name": "Fixture administrator", "display_name": "Fixture administrator"})
    result["app"].update(started_at="2026-09-21T08:00:00-04:00", uptime_seconds=54720)
    result["instance_id"] = "fixture-instance"
    result["csrf_token"] = "fixture-not-a-real-token"
    result["control_results"] = []
    result["journal"].update(enabled=True, count=65, last_dump_at="2026-09-21T08:02:00-04:00", last_dump_seen=32, last_dump_inserted=32)
    return result


bridge = Bridge()
bridge.state.zones[1].descriptor = "Lobby smoke"
bridge.state.zones[2].descriptor = "East exit"
normal = snapshot(bridge)
records = []
start = datetime(2026, 9, 21, 23, 12)
codes = ["F6", "F5", "08", "07", "1C", "1B", "53", "54", "01", "02", "E1", "E2"]
for index in range(65):
    code = codes[index % len(codes)]
    panel_time = start - timedelta(minutes=index * 4)
    records.append(event_presentation({
        "id": 65 - index, "occurrence": 1, "event_code": code,
        "description": EVENT_DESCRIPTIONS[code], "zone": 0 if code in {"1B", "1C", "07", "08"} else 2,
        "user": 12 if code in {"07", "08"} else 0,
        "partition": 0 if code in {"1B", "1C"} else 1,
        "panel_timestamp": panel_time.isoformat(timespec="minutes"),
        "received_at": (panel_time + timedelta(hours=4)).replace(tzinfo=timezone.utc).isoformat(),
        "descriptor": "East exit" if code in {"F5", "F6"} else "",
        "source": ["live", "history", "both"][index % 3],
    }))
normal["last_event"] = records[0]

diagnostic_records = []
diag_start = datetime(2026, 9, 21, 23, 15, tzinfo=timezone.utc)
diagnostic_types = [
    ("error", "ha_transport", "mqtt", "ha_transport.watchdog_triggered", "Heartbeat acknowledgement timed out", "ha_fixture_1"),
    ("warning", "ha_transport", "mqtt", "ha_transport.recovery_started", "Replacing MQTT transport after watchdog trigger", "ha_fixture_1"),
    ("info", "ha_transport", "mqtt", "ha_transport.connected", "MQTT broker connection established", "ha_fixture_1"),
    ("info", "state_delivery", "mqtt", "state_delivery.replay_completed", "Home Assistant discovery and state replay completed", "ha_fixture_1"),
    ("warning", "protocol", "vista-rs232", "protocol.invalid_frame", "Invalid VISTA protocol frame rejected", ""),
    ("info", "synchronization", "synchronizer", "synchronization.completed", "read-only VISTA startup synchronization", "sync_fixture_1"),
]
for index in range(65):
    severity, category, component, event_type, message, correlation = diagnostic_types[index % len(diagnostic_types)]
    occurred = diag_start - timedelta(minutes=index * 3)
    diagnostic_records.append({
        "id": 200 - index,
        "event_id": f"diag_fixture_{index:02d}",
        "occurred_at": occurred.isoformat(),
        "severity": severity,
        "category": category,
        "component": component,
        "event_type": event_type,
        "message": message,
        "boot_id": "boot_fixture",
        "panel_session_id": "panel_fixture",
        "transport_session_id": "ha_session_fixture" if component == "mqtt" else "",
        "correlation_id": correlation,
        "details": (
            {"last_puback_age_seconds": 61.2, "transport_generation": 7}
            if event_type == "ha_transport.watchdog_triggered"
            else {}
        ),
    })
diagnostic_incidents = [{
    "correlation_id": "ha_fixture_1",
    "started_at": diagnostic_records[3]["occurred_at"],
    "ended_at": diagnostic_records[0]["occurred_at"],
    "event_count": 4,
    "severity": "error",
    "categories": ["ha_transport", "state_delivery"],
    "components": ["mqtt"],
    "event_types": [item["event_type"] for item in diagnostic_records[:4]],
    "summary": "Heartbeat acknowledgement timed out",
}]
diagnostics_api = {
    "records": diagnostic_records,
    "next_cursor": "",
    "incidents": diagnostic_incidents,
    "stats": {
        "count": 65,
        "oldest_at": diagnostic_records[-1]["occurred_at"],
        "newest_at": diagnostic_records[0]["occurred_at"],
        "write_errors": 0,
        "dropped_events": 0,
        "pending_writes": 0,
    },
    "runtime": {
        "available": True,
        "write_errors": 0,
        "dropped_events": 0,
        "pending_writes": 0,
        "writer_alive": True,
    },
    "retention_days": 30,
    "max_rows": 25000,
    "enabled": True,
}

bridge.state.apply_system_event(SystemEvent("01", "Fire Alarm", 1, 0, 1, 14, 23, 21, 9, 26))
fire = snapshot(bridge)
fire["last_event"]["descriptor"] = "Lobby smoke"
bridge = Bridge(); bridge.state.system_battery_low = None
unknown = snapshot(bridge)
print(json.dumps({
    "normal": normal,
    "fire": fire,
    "unknown": unknown,
    "events": records,
    "diagnostics_api": diagnostics_api,
}, separators=(",", ":")))
