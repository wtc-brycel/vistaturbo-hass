from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN
from .hub import VistaTurboHub


class VistaTurboEntity(Entity):
    _attr_has_entity_name = True

    def __init__(self, hub: VistaTurboHub) -> None:
        self.hub = hub
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, hub.identity)},
            name="VISTA Turbo Panel",
            manufacturer="Honeywell / Resideo",
            model="VISTA Turbo",
        )

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(self.hub.async_add_listener(self._handle_hub_update))

    def _handle_hub_update(self) -> None:
        self.async_write_ha_state()

    @property
    def available(self) -> bool:
        return self.hub.api_available
