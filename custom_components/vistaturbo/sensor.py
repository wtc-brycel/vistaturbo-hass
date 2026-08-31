from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
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
    known: set[int] = set()
    async_add_entities([VistaBridgeStatusSensor(hub)])

    @callback
    def add_missing_keypads() -> None:
        entities = []
        for item in hub.snapshot.get("keypads", []):
            partition = int(item["partition"])
            if partition in known:
                continue
            known.add(partition)
            entities.append(VistaKeypadSensor(hub, partition))
        if entities:
            async_add_entities(entities)

    add_missing_keypads()
    entry.async_on_unload(hub.async_add_listener(add_missing_keypads))


class VistaBridgeStatusSensor(VistaTurboEntity, SensorEntity):
    _attr_name = "Bridge status"

    def __init__(self, hub: VistaTurboHub) -> None:
        super().__init__(hub)
        self._attr_unique_id = f"{hub.identity}-bridge-status"

    @property
    def native_value(self) -> str:
        if not self.hub.api_available:
            return "api_unavailable"
        return (
            "connected"
            if self.hub.snapshot.get("panel", {}).get("connected")
            else "disconnected"
        )

    @property
    def extra_state_attributes(self) -> dict:
        return dict(self.hub.snapshot.get("panel", {}))


class VistaKeypadSensor(VistaTurboEntity, SensorEntity):
    def __init__(self, hub: VistaTurboHub, partition: int) -> None:
        super().__init__(hub)
        self.partition = partition
        self._attr_unique_id = f"{hub.identity}-keypad-{partition}"
        self._attr_name = f"Partition {partition} keypad"

    def _data(self) -> dict | None:
        return next(
            (
                item
                for item in self.hub.snapshot.get("keypads", [])
                if int(item["partition"]) == self.partition
            ),
            None,
        )

    @property
    def native_value(self) -> str | None:
        data = self._data()
        return str(data["state"]) if data else None

    @property
    def extra_state_attributes(self) -> dict:
        data = self._data() or {}
        return {
            key: value
            for key, value in data.items()
            if key not in {"state", "available"}
        }

    @property
    def available(self) -> bool:
        data = self._data()
        return bool(super().available and data and data.get("available"))
