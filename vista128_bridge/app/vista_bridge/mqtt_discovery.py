from __future__ import annotations

from collections.abc import Callable

from .state import ZoneState
from .version import VERSION

TopicFn = Callable[[str], str]

ZONE_CONDITION_SPECS = {
    "fault": {
        "attribute": "faulted",
        "label": "Fault",
        "summary_name": "Fault Zones",
        "icon": "mdi:door-open",
    },
    "alarm": {
        "attribute": "alarm",
        "label": "Alarm",
        "summary_name": "Alarm Zones",
        "icon": "mdi:alarm-light-outline",
    },
    "check": {
        "attribute": "trouble",
        "label": "Check",
        "summary_name": "Check Zones",
        "icon": "mdi:alert-circle-outline",
    },
    "bypass": {
        "attribute": "bypassed",
        "label": "Bypass",
        "summary_name": "Bypass Zones",
        "icon": "mdi:shield-off-outline",
    },
}


KEYPAD_ALARM_SPECS = {
    "fire": {
        "attribute": "fire_alarm_led",
        "label": "Fire Alarm",
        "icon": "mdi:fire-alert",
    },
    "panic_audible": {
        "attribute": "audible_panic_alarm",
        "label": "Audible Panic Alarm",
        "icon": "mdi:alarm-bell",
    },
    "burglary": {
        "attribute": "burglary_alarm_led",
        "label": "Burglary Alarm",
        "icon": "mdi:shield-alert-outline",
    },
    "auxiliary": {
        "attribute": "auxiliary_alarm_led",
        "label": "Auxiliary Alarm",
        "icon": "mdi:alarm-light-outline",
    },
}

# Panel-wide alarm entities are derived from the event/state model, not only
# from physical keypad LEDs. Silent and duress alarms have no ordinary speaker
# LED but are still security alarms and must be represented here.
PANEL_ALARM_SPECS = {
    **KEYPAD_ALARM_SPECS,
    "silent": {
        "label": "Silent Alarm",
        "icon": "mdi:alarm-light-outline",
    },
    "duress": {
        "label": "Duress Alarm",
        "icon": "mdi:account-alert-outline",
    },
    "supervisory": {
        "label": "Supervisory Alarm",
        "icon": "mdi:alert-outline",
    },
}


def keypad_alarm_availability(partition: int, alarm_type: str, topic: TopicFn) -> dict:
    return {
        "availability": [
            {
                "topic": topic("bridge/availability"),
                "payload_available": "online",
                "payload_not_available": "offline",
            },
            {
                "topic": topic("panel/connected"),
                "payload_available": "ON",
                "payload_not_available": "OFF",
            },
            {
                "topic": topic(f"keypad/{partition}/alarm/{alarm_type}/available"),
                "payload_available": "ON",
                "payload_not_available": "OFF",
            },
        ],
        "availability_mode": "all",
    }


def keypad_alarm_configs(partition: int, topic: TopicFn) -> dict[str, dict]:
    configs = {
        alarm_type: {
            "name": f"Partition {partition} {spec['label']}",
            "unique_id": f"vista128_keypad_{partition}_{alarm_type}_alarm",
            "state_topic": topic(f"keypad/{partition}/alarm/{alarm_type}"),
            "payload_on": "ON",
            "payload_off": "OFF",
            **keypad_alarm_availability(partition, alarm_type, topic),
            "icon": spec["icon"],
            "device": device_info(),
        }
        for alarm_type, spec in KEYPAD_ALARM_SPECS.items()
    }
    configs["active"] = {
        "name": f"Partition {partition} Alarm Active",
        "unique_id": f"vista128_keypad_{partition}_alarm_active",
        "state_topic": topic(f"keypad/{partition}/alarm/active"),
        "payload_on": "ON",
        "payload_off": "OFF",
        "json_attributes_topic": topic(f"keypad/{partition}/alarm/active/attributes"),
        **keypad_alarm_availability(partition, "active", topic),
        "icon": "mdi:alarm-light",
        "device": device_info(),
    }
    return configs


def panel_alarm_availability(alarm_type: str, topic: TopicFn) -> dict:
    return {
        "availability": [
            {
                "topic": topic("bridge/availability"),
                "payload_available": "online",
                "payload_not_available": "offline",
            },
            {
                "topic": topic("panel/connected"),
                "payload_available": "ON",
                "payload_not_available": "OFF",
            },
            {
                "topic": topic(f"alarm/{alarm_type}/available"),
                "payload_available": "ON",
                "payload_not_available": "OFF",
            },
        ],
        "availability_mode": "all",
    }


def panel_alarm_configs(topic: TopicFn) -> dict[str, dict]:
    configs = {
        alarm_type: {
            "name": spec["label"],
            "unique_id": f"vista128_{alarm_type}_alarm",
            "state_topic": topic(f"alarm/{alarm_type}"),
            "payload_on": "ON",
            "payload_off": "OFF",
            "json_attributes_topic": topic(f"alarm/{alarm_type}/attributes"),
            **panel_alarm_availability(alarm_type, topic),
            "icon": spec["icon"],
            "device": device_info(),
        }
        for alarm_type, spec in PANEL_ALARM_SPECS.items()
    }
    configs["active"] = {
        "name": "Alarm Active",
        "unique_id": "vista128_alarm_active",
        "state_topic": topic("alarm/active"),
        "payload_on": "ON",
        "payload_off": "OFF",
        "json_attributes_topic": topic("alarm/active/attributes"),
        **panel_alarm_availability("active", topic),
        "icon": "mdi:alarm-light",
        "device": device_info(),
    }
    return configs


def device_info() -> dict:
    return {
        "identifiers": ["vista128_bridge"],
        "name": "VISTA 128BPT",
        "manufacturer": "Resideo / Honeywell",
        "model": "VISTA-128BPT via TCP Bridge",
        "sw_version": VERSION,
    }


def panel_entity_availability(topic: TopicFn) -> dict:
    return {
        "availability": [
            {
                "topic": topic("bridge/availability"),
                "payload_available": "online",
                "payload_not_available": "offline",
            },
            {
                "topic": topic("panel/connected"),
                "payload_available": "ON",
                "payload_not_available": "OFF",
            },
            {
                "topic": topic("panel/state_fresh"),
                "payload_available": "ON",
                "payload_not_available": "OFF",
            },
        ],
        "availability_mode": "all",
    }


def diagnostic_entities(
    topic: TopicFn,
    *,
    include_raw: bool = False,
) -> dict[str, tuple[str, dict]]:
    entities = {
        "connection": (
            "binary_sensor",
            {
                "name": "Panel TCP Connection",
                "unique_id": "vista128_bridge_connection",
                "state_topic": topic("panel/connected"),
                "payload_on": "ON",
                "payload_off": "OFF",
                "device_class": "connectivity",
                "entity_category": "diagnostic",
            },
        ),
        "automation_available": (
            "binary_sensor",
            {
                "name": "Automation Interface Available",
                "unique_id": "vista128_automation_available",
                "state_topic": topic("panel/automation_available"),
                "payload_on": "ON",
                "payload_off": "OFF",
                "device_class": "connectivity",
                "entity_category": "diagnostic",
            },
        ),
        "automation_availability_source": (
            "sensor",
            {
                "name": "Automation Availability Source",
                "unique_id": "vista128_automation_availability_source",
                "state_topic": topic("panel/automation_availability_source"),
                "entity_category": "diagnostic",
                "icon": "mdi:connection",
            },
        ),
        "rx_frames": (
            "sensor",
            {
                "name": "Received Frames",
                "unique_id": "vista128_bridge_rx_frames",
                "state_topic": topic("stats/rx_frames"),
                "state_class": "total_increasing",
                "entity_category": "diagnostic",
            },
        ),
        "rx_bytes": (
            "sensor",
            {
                "name": "Received Bytes",
                "unique_id": "vista128_bridge_rx_bytes",
                "state_topic": topic("stats/rx_bytes"),
                "state_class": "total_increasing",
                "unit_of_measurement": "B",
                "entity_category": "diagnostic",
            },
        ),
        "tx_frames": (
            "sensor",
            {
                "name": "Transmitted Frames",
                "unique_id": "vista128_bridge_tx_frames",
                "state_topic": topic("stats/tx_frames"),
                "state_class": "total_increasing",
                "entity_category": "diagnostic",
            },
        ),
        "tx_bytes": (
            "sensor",
            {
                "name": "Transmitted Bytes",
                "unique_id": "vista128_bridge_tx_bytes",
                "state_topic": topic("stats/tx_bytes"),
                "state_class": "total_increasing",
                "unit_of_measurement": "B",
                "entity_category": "diagnostic",
            },
        ),
        "invalid_frames": (
            "sensor",
            {
                "name": "Invalid Frames",
                "unique_id": "vista128_bridge_invalid_frames",
                "state_topic": topic("stats/invalid_frames"),
                "state_class": "total_increasing",
                "entity_category": "diagnostic",
            },
        ),
        "last_sync": (
            "sensor",
            {
                "name": "Last State Reconciliation",
                "unique_id": "vista128_bridge_last_sync",
                "state_topic": topic("sync/last_success"),
                "device_class": "timestamp",
                "entity_category": "diagnostic",
            },
        ),
        "sync_failures": (
            "sensor",
            {
                "name": "Consecutive Sync Failures",
                "unique_id": "vista128_bridge_sync_failures",
                "state_topic": topic("sync/consecutive_failures"),
                "entity_category": "diagnostic",
            },
        ),
        "panel_clock_offset": (
            "sensor",
            {
                "name": "Panel Clock Offset",
                "unique_id": "vista128_bridge_panel_clock_offset",
                "state_topic": topic("panel/clock_offset_seconds"),
                "unit_of_measurement": "s",
                "entity_category": "diagnostic",
            },
        ),
        "printer_status": (
            "sensor",
            {
                "name": "Event Printer Status",
                "unique_id": "vista128_bridge_printer_status",
                "state_topic": topic("printer/status"),
                "entity_category": "diagnostic",
                "enabled_by_default": False,
            },
        ),
        "printer_queue": (
            "sensor",
            {
                "name": "Event Printer Queue",
                "unique_id": "vista128_bridge_printer_queue",
                "state_topic": topic("printer/queue_depth"),
                "entity_category": "diagnostic",
                "enabled_by_default": False,
            },
        ),
        "printer_uncertain": (
            "sensor",
            {
                "name": "Uncertain Print Jobs",
                "unique_id": "vista128_bridge_printer_uncertain",
                "state_topic": topic("printer/uncertain"),
                "entity_category": "diagnostic",
                "enabled_by_default": False,
            },
        ),
        "last_message_type": (
            "sensor",
            {
                "name": "Last Protocol Message Type",
                "unique_id": "vista128_bridge_last_message_type",
                "state_topic": topic("protocol/last_message_type"),
                "entity_category": "diagnostic",
                "enabled_by_default": False,
            },
        ),
        "last_frame": (
            "sensor",
            {
                "name": "Last Diagnostic Frame Metadata",
                "unique_id": "vista128_bridge_last_frame",
                "state_topic": topic("raw/last_metadata"),
                "json_attributes_topic": topic("raw/last_metadata"),
                "entity_category": "diagnostic",
                "enabled_by_default": False,
            },
        ),
        "last_event": (
            "sensor",
            {
                "name": "Last Event",
                "unique_id": "vista128_bridge_last_event",
                "state_topic": topic("event/last_description"),
                "json_attributes_topic": topic("event/last"),
                "icon": "mdi:shield-alert-outline",
            },
        ),
    }
    if not include_raw:
        entities.pop("last_frame", None)
    return entities


def event_history_config(topic: TopicFn) -> dict:
    return {
        "name": "Event Journal",
        "unique_id": "vista128_event_journal",
        "state_topic": topic("event_history/count"),
        "json_attributes_topic": topic("event_history/attributes"),
        "icon": "mdi:history",
        "device": device_info(),
        "availability_topic": topic("bridge/availability"),
        "payload_available": "online",
        "payload_not_available": "offline",
    }


def zone_summary_entities(topic: TopicFn) -> dict[str, dict]:
    return {
        f"{key}_zones": {
            "name": spec["summary_name"],
            "unique_id": f"vista128_{key}_zones",
            "state_topic": topic(f"zone_summary/{key}/count"),
            "json_attributes_topic": topic(f"zone_summary/{key}/attributes"),
            "icon": spec["icon"],
            "device": device_info(),
            **panel_entity_availability(topic),
        }
        for key, spec in ZONE_CONDITION_SPECS.items()
    }


def partition_config(partition: int, topic: TopicFn, control_enabled: bool = False) -> dict:
    config = {
        "name": f"Partition {partition}",
        "unique_id": f"vista128_partition_{partition}",
        "state_topic": topic(f"partition/{partition}/state"),
        "json_attributes_topic": topic(f"partition/{partition}/attributes"),
        **panel_entity_availability(topic),
        "supported_features": [],
        "device": device_info(),
        "enabled_by_default": partition == 1,
    }
    if control_enabled:
        config.update(
            {
                "command_topic": topic(f"partition/{partition}/command"),
                "code": "REMOTE_CODE",
                "code_arm_required": True,
                "code_disarm_required": True,
                "code_trigger_required": False,
                "command_template": '{"action":"{{ action }}","code":"{{ code }}"}',
                "supported_features": ["arm_home", "arm_away", "arm_night"],
                "retain": False,
            }
        )
    return config


def keypad_config(partition: int, topic: TopicFn) -> dict:
    return {
        "name": f"Partition {partition} Keypad",
        "unique_id": f"vista128_keypad_{partition}",
        "state_topic": topic(f"keypad/{partition}/state"),
        "json_attributes_topic": topic(f"keypad/{partition}/attributes"),
        **panel_entity_availability(topic),
        "icon": "mdi:alarm-panel-outline",
        "device": device_info(),
    }


def zone_condition_configs(zone: ZoneState, topic: TopicFn) -> dict[str, dict]:
    base_name = (
        f"{zone.zone:03d} {zone.descriptor}"
        if zone.descriptor
        else f"Zone {zone.zone:03d}"
    )
    return {
        key: {
            "name": f"{base_name} {spec['label']}",
            "unique_id": f"vista128_zone_{zone.zone:03d}_{key}",
            "state_topic": topic(f"zone/{zone.zone:03d}/{key}"),
            "payload_on": "ON",
            "payload_off": "OFF",
            "json_attributes_topic": topic(f"zone/{zone.zone:03d}/attributes"),
            **panel_entity_availability(topic),
            "icon": spec["icon"],
            "device": device_info(),
        }
        for key, spec in ZONE_CONDITION_SPECS.items()
    }
