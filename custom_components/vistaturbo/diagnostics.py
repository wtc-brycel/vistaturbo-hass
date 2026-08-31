from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from .const import CONF_PORT
from .hub import VistaTurboHub


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry[VistaTurboHub]
) -> dict:
    """Return native integration diagnostics without credentials or panel layout."""
    hub = entry.runtime_data
    snapshot = hub.snapshot
    panel = snapshot.get("panel", {})
    control = snapshot.get("control", {})
    events = snapshot.get("events", {})
    return {
        "connection": {
            "host": entry.data.get(CONF_HOST),
            "port": entry.data.get(CONF_PORT),
            "api_available": hub.api_available,
            "event_stream_available": hub.event_stream_available,
        },
        "api": {
            "schema": snapshot.get("schema"),
            "revision": snapshot.get("revision"),
        },
        "panel": {
            "connected": panel.get("connected"),
            "state_fresh": panel.get("state_fresh"),
            "alarm_knowledge_complete": panel.get("alarm_knowledge_complete"),
            "session_generation": panel.get("session_generation"),
        },
        "control": {
            "native_alarm": control.get("native_alarm"),
            "automation_available": control.get("automation_available"),
        },
        "events": {
            "advertised_type_count": len(events.get("types", [])),
            "replay_capacity": events.get("replay_capacity"),
            "last_sequence": hub.last_event_sequence,
            "gap_detected": hub.event_stream_gap_detected,
            "last_gap": hub.event_stream_gap,
        },
        "entity_source_counts": {
            "partitions": len(snapshot.get("partitions", [])),
            "zones": len(snapshot.get("zones", [])),
            "keypads": len(snapshot.get("keypads", [])),
            "has_last_event": snapshot.get("last_event") is not None,
        },
    }
