from __future__ import annotations

from homeassistant.components.event import EventEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import VistaTurboEntity
from .hub import VistaTurboHub


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry[VistaTurboHub],
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    hub = entry.runtime_data
    event_types = hub.snapshot.get("events", {}).get("types", [])
    supported = [str(value) for value in event_types if isinstance(value, str)]
    if not supported:
        return
    async_add_entities([VistaPanelEvent(hub, supported)])


class VistaPanelEvent(VistaTurboEntity, EventEntity):
    """Ordered transient events reported directly by the VISTA panel."""

    def __init__(self, hub: VistaTurboHub, event_types: list[str]) -> None:
        super().__init__(hub)
        self._attr_unique_id = f"{hub.identity}-panel-event"
        self._attr_name = "Event"
        self._attr_event_types = event_types

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(self.hub.async_add_event_listener(self._handle_panel_event))

    @callback
    def _handle_panel_event(self, event: dict) -> None:
        event_type = str(event.get("event_type", ""))
        if event_type not in self.event_types:
            return
        attributes = {
            key: value
            for key, value in event.items()
            if key not in {"schema", "event_type"}
        }
        self._trigger_event(event_type, attributes)
        self.async_write_ha_state()

    @property
    def available(self) -> bool:
        return bool(super().available and self.hub.event_stream_available)
