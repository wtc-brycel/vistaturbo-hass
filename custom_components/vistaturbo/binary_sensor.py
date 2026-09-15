from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import VistaTurboEntity
from .hub import VistaTurboHub


@dataclass(frozen=True)
class ZoneCondition:
    key: str
    name: str
    device_class: BinarySensorDeviceClass | None = None


CONDITIONS = (
    ZoneCondition("faulted", "Fault"),
    ZoneCondition("alarm", "Alarm", BinarySensorDeviceClass.SAFETY),
    ZoneCondition("trouble", "Check", BinarySensorDeviceClass.PROBLEM),
    ZoneCondition("bypassed", "Bypass"),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry[VistaTurboHub],
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    hub = entry.runtime_data
    known: set[tuple[int, str]] = set()

    @callback
    def add_missing() -> None:
        entities = []
        for zone in hub.snapshot.get("zones", []):
            zone_number = int(zone["zone"])
            for condition in CONDITIONS:
                key = (zone_number, condition.key)
                if key in known:
                    continue
                known.add(key)
                entities.append(VistaZoneBinarySensor(hub, zone_number, condition))
        if entities:
            async_add_entities(entities)

    add_missing()
    entry.async_on_unload(hub.async_add_listener(add_missing))


class VistaZoneBinarySensor(VistaTurboEntity, BinarySensorEntity):
    def __init__(
        self, hub: VistaTurboHub, zone_number: int, condition: ZoneCondition
    ) -> None:
        super().__init__(hub)
        self.zone_number = zone_number
        self.condition = condition
        self._attr_unique_id = f"{hub.identity}-zone-{zone_number}-{condition.key}"
        self._attr_device_class = condition.device_class

    def _data(self) -> dict | None:
        return next(
            (
                item
                for item in self.hub.snapshot.get("zones", [])
                if int(item["zone"]) == self.zone_number
            ),
            None,
        )

    @property
    def name(self) -> str:
        data = self._data() or {}
        descriptor = str(data.get("descriptor") or f"Zone {self.zone_number:03d}")
        return f"{descriptor} {self.condition.name}"

    @property
    def is_on(self) -> bool | None:
        data = self._data()
        return bool(data[self.condition.key]) if data else None

    @property
    def extra_state_attributes(self) -> dict:
        data = self._data() or {}
        return {
            "zone": self.zone_number,
            "partition": data.get("partition"),
            "descriptor": data.get("descriptor", ""),
        }

    @property
    def available(self) -> bool:
        panel = self.hub.snapshot.get("panel", {})
        return bool(
            super().available
            and panel.get("connected")
            and panel.get("state_fresh")
            and self._data() is not None
        )
