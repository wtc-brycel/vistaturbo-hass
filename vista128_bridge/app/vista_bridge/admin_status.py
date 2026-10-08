"""Presentation of existing VISTA evidence; no protocol or control inference."""
from __future__ import annotations

from .event_codes import classify_alarm_event
from .state import PARTITION_TROUBLE_RESTORE_TO_START

ALARM_LABELS = {
    "fire": ("fire", "FIRE ALARM"),
    "burglary": ("security", "BURGLARY ALARM"),
    "auxiliary": ("security", "AUXILIARY ALARM"),
    "panic_audible": ("security", "AUDIBLE PANIC"),
    "silent": ("security", "SILENT ALARM"),
    "duress": ("security", "DURESS ALARM"),
    "supervisory": ("supervisory", "SUPERVISORY"),
}
PRIORITY = {"fire": 0, "security": 1, "alarm": 2, "supervisory": 3,
            "trouble": 4, "bypass": 5, "fault": 6, "unknown": 7, "normal": 8}


def event_presentation(event: dict) -> dict:
    """Classify by canonical event code, never by English description matching."""
    code = str(event.get("event_code", "")).upper()
    alarm_type, transition = classify_alarm_event(code)
    if alarm_type:
        family = ALARM_LABELS[alarm_type][0]
    elif code in PARTITION_TROUBLE_RESTORE_TO_START or code in {"1C", "2A"}:
        family, transition = "trouble", "restore"
    elif code in set(PARTITION_TROUBLE_RESTORE_TO_START.values()) | {"1B", "29"}:
        family, transition = "trouble", "active"
    elif code in {"05", "06"}:
        family, transition = "bypass", "restore" if code == "06" else "active"
    elif code in {"F5", "F6"}:
        family, transition = "fault", "restore" if code == "F6" else "active"
    else:
        family, transition = "neutral", None
    return {**event, "family": family, "transition": transition,
            "kind": "restore" if transition == "restore" else family}


def operational_status(bridge) -> dict:
    state = bridge.state
    connected = bool(bridge._is_connected())
    automation = bool(bridge.control.automation_available())
    fresh = connected and automation and state.live_snapshot_complete
    alarms = state.panel_alarm_states()
    required = set(state.alarm_keypad_partitions) | set(bridge.settings.keypad.partitions)
    required_keypads = [state.keypads[p] for p in required]
    trouble_complete = bool(
        fresh and state.ac_power is not None and state.system_battery_low is not None
        and all(k.initialized and k.session_fresh for k in required_keypads)
    )
    complete = bool(fresh and alarms["complete"] and trouble_complete)
    conditions = []

    def add(kind, title, partition=None, detail="", observed=True):
        conditions.append({"kind": kind, "title": title, "partition": partition,
                           "detail": detail, "state": "ACTIVE" if observed else "LAST KNOWN"})

    # A positive alarm stays visible until the domain engine clears it. Lack of
    # synchronization must never downgrade known positive evidence to normal.
    for alarm_type, (kind, label) in ALARM_LABELS.items():
        scopes = set(alarms["active_partitions_by_type"].get(alarm_type, []))
        if alarm_type == "supervisory":
            scopes |= {p for p, k in state.keypads.items() if k.supervisory_led is True}
        for p in sorted(scopes):
            silenced = alarm_type == "fire" and p in state.keypads and state.keypads[p].silenced_led is True
            add(kind, label, p, "Silenced" if silenced else "", connected and automation)
    for p in alarms["active_partitions"]:
        if not any(c["partition"] == p for c in conditions):
            add("alarm", "ALARM", p, observed=connected and automation)

    if connected and state.ac_power is False:
        add("trouble", "AC POWER LOSS", 0, observed=automation)
    if connected and state.system_battery_low is True:
        add("trouble", "BATTERY LOW", 0, observed=automation)
    if connected and state.active_global_trouble_tokens:
        add("trouble", "SYSTEM TROUBLE", 0, observed=automation)
    global_trouble = bool(conditions and any(c["kind"] == "trouble" for c in conditions))

    for p, partition in state.partitions.items():
        keypad = state.keypads[p]
        zones = [z for z in state.zones.values() if z.partition == p]
        known_trouble = bool(partition.active_trouble_tokens)
        # Only use zone bits after a complete zone snapshot; disconnect leaves
        # some of these cached bits intact in VistaState.
        troubled_zones = [z for z in zones if state.zone_snapshot_complete and z.trouble]
        keypad_trouble = keypad.initialized and keypad.session_fresh and keypad.trouble_led
        if connected and (known_trouble or troubled_zones or (keypad_trouble and not global_trouble)):
            detail = ", ".join(f"Zone {z.zone:03d}" for z in troubled_zones)
            add("trouble", "TROUBLE", p, detail, automation)
        if fresh:
            for field, kind, label in (("bypassed", "bypass", "ZONE BYPASSED"), ("faulted", "fault", "ZONE FAULT")):
                for z in zones:
                    if getattr(z, field):
                        add(kind, label, p, f"Zone {z.zone:03d}" + (f" · {z.descriptor}" if z.descriptor else ""))

    conditions.sort(key=lambda c: (PRIORITY[c["kind"]], c["partition"] or 0))
    if not connected:
        condition = {"kind": "offline", "title": "PANEL OFFLINE", "detail": ""}
    elif conditions and PRIORITY[conditions[0]["kind"]] < PRIORITY["bypass"]:
        first = conditions[0]
        condition = {"kind": first["kind"], "title": first["title"],
                     "detail": "" if fresh else "State not current"}
        fire = [c for c in conditions if c["kind"] == "fire"]
        if fire and all(c["detail"] == "Silenced" for c in fire):
            condition.update(kind="fire-silenced", title="FIRE ALARM · SILENCED")
    elif not automation:
        condition = {"kind": "unknown", "title": "AUTOMATION UNAVAILABLE", "detail": ""}
    elif not fresh:
        condition = {"kind": "syncing", "title": "SYNCHRONIZING", "detail": ""}
    elif not complete:
        missing = []
        if not alarms["complete"]:
            missing.append("Alarm state")
        if state.ac_power is None:
            missing.append("AC power")
        if state.system_battery_low is None:
            missing.append("Battery")
        if not all(k.initialized and k.session_fresh for k in required_keypads):
            missing.append("Keypad state")
        condition = {"kind": "unknown", "title": "STATUS INCOMPLETE",
                     "detail": ", ".join(missing) + " unknown"}
    elif conditions:
        first = conditions[0]
        condition = {"kind": first["kind"], "title": first["title"], "detail": ""}
    else:
        condition = {"kind": "normal", "title": "SYSTEM NORMAL", "detail": ""}

    visible = set(bridge.settings.keypad.partitions)
    if state.zone_partition_initialized:
        visible |= {z.partition for z in state.zones.values() if z.partition in state.partitions}
    visible |= {c["partition"] for c in conditions if c["partition"] in state.partitions}
    partitions = {}
    for p in sorted(visible):
        partition, keypad = state.partitions[p], state.keypads[p]
        mode_current = connected and automation and state.arming_initialized
        keypad_current = fresh and keypad.initialized and keypad.session_fresh
        scoped = [c for c in conditions if c["partition"] == p]
        scoped_condition = {"kind": scoped[0]["kind"], "text": scoped[0]["title"]} if scoped else {
            "kind": "normal" if complete else "unknown",
            "text": "NORMAL" if complete else "UNKNOWN",
        }
        # AS D/N carries a readiness distinction. Other modes must not be
        # converted into a fabricated ready flag when no current KD exists.
        ready = keypad.ready_led if keypad_current else (
            partition.raw_mode == "D" if mode_current and partition.raw_mode in {"D", "N"} else None
        )
        partitions[str(p)] = {
            "partition": p, "vista_mode": partition.vista_mode if mode_current else None,
            "ready": ready, "condition": scoped_condition,
        }
    return {"condition": condition, "conditions": conditions, "partitions": partitions,
            "alarm_states": alarms, "complete": complete, "state_fresh": fresh}
