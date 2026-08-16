from __future__ import annotations

from collections.abc import Callable

from .state import ZoneState
from .version import VERSION

TopicFn = Callable[[str], str]

ZONE_SUMMARY_SPECS = {
    "faulted": {
        "attribute": "faulted",
        "name": "Faulted Zones",
        "icon": "mdi:door-open",
    },
    "check": {
        "attribute": "trouble",
        "name": "Zones in Check",
        "icon": "mdi:alert-circle-outline",
    },
    "alarm": {
        "attribute": "alarm",
        "name": "Zones in Alarm",
        "icon": "mdi:alarm-light-outline",
    },
    "bypassed": {
        "attribute": "bypassed",
        "name": "Bypassed Zones",
        "icon": "mdi:shield-off-outline",
    },
}


def device_info() -> dict:
    return {
        "identifiers": ["vista128_bridge"],
        "name": "VISTA 128BPT",
        "manufacturer": "Resideo / Honeywell",
        "model": "VISTA-128BPT via TCP Bridge",
        "sw_version": VERSION,
    }


def diagnostic_entities(topic: TopicFn) -> dict[str, tuple[str, dict]]:
    return {
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
                "name": "Last Raw Frame",
                "unique_id": "vista128_bridge_last_frame",
                "state_topic": topic("raw/last_ascii"),
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


def zone_summary_entities(topic: TopicFn) -> dict[str, dict]:
    return {
        f"{key}_zones": {
            "name": spec["name"],
            "unique_id": f"vista128_{key}_zones",
            "state_topic": topic(f"zone_summary/{key}/count"),
            "json_attributes_topic": topic(f"zone_summary/{key}/attributes"),
            "icon": spec["icon"],
        }
        for key, spec in ZONE_SUMMARY_SPECS.items()
    }


def partition_config(partition: int, topic: TopicFn) -> dict:
    return {
        "name": f"Partition {partition}",
        "unique_id": f"vista128_partition_{partition}",
        "state_topic": topic(f"partition/{partition}/state"),
        "command_topic": topic(f"partition/{partition}/command"),
        "json_attributes_topic": topic(f"partition/{partition}/attributes"),
        "availability_topic": topic("panel/connected"),
        "payload_available": "ON",
        "payload_not_available": "OFF",
        "supported_features": [],
        "code_arm_required": False,
        "code_disarm_required": False,
        "device": device_info(),
        "enabled_by_default": partition == 1,
    }


def zone_config(zone: ZoneState, topic: TopicFn) -> dict:
    display_name = (
        f"{zone.zone:03d} {zone.descriptor}"
        if zone.descriptor
        else f"Zone {zone.zone:03d}"
    )
    return {
        "name": display_name,
        "unique_id": f"vista128_zone_{zone.zone:03d}",
        "state_topic": topic(f"zone/{zone.zone:03d}/state"),
        "payload_on": "ON",
        "payload_off": "OFF",
        "json_attributes_topic": topic(f"zone/{zone.zone:03d}/attributes"),
        "availability_topic": topic("panel/connected"),
        "payload_available": "ON",
        "payload_not_available": "OFF",
        "device": device_info(),
    }
