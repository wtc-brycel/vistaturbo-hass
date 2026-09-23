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
bridge.state.apply_system_event(SystemEvent("01", "Fire Alarm", 1, 0, 1, 14, 23, 21, 9, 26))
fire = snapshot(bridge)
fire["last_event"]["descriptor"] = "Lobby smoke"
bridge = Bridge(); bridge.state.system_battery_low = None
unknown = snapshot(bridge)
print(json.dumps({"normal": normal, "fire": fire, "unknown": unknown, "events": records}, separators=(",", ":")))
