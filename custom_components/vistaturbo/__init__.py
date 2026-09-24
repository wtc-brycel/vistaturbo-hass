from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import (
    VistaTurboApiClient,
    VistaTurboAuthError,
    VistaTurboCannotConnect,
    VistaTurboProtocolError,
)
from .const import CONF_PORT, CONF_TOKEN, DOMAIN
from .hub import VistaTurboHub

PLATFORMS = [Platform.BINARY_SENSOR, Platform.SENSOR]
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)
type VistaTurboConfigEntry = ConfigEntry[VistaTurboHub]


async def _async_reload_entry(
    hass: HomeAssistant, entry: VistaTurboConfigEntry
) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_setup_entry(hass: HomeAssistant, entry: VistaTurboConfigEntry) -> bool:
    client = VistaTurboApiClient(
        async_get_clientsession(hass),
        entry.data[CONF_HOST],
        entry.data[CONF_PORT],
        entry.data[CONF_TOKEN],
    )
    try:
        snapshot = await client.async_get_snapshot()
    except VistaTurboAuthError as err:
        # This credential is installation-local machine trust provisioned by
        # Supervisor discovery. There is intentionally no human reauth form.
        # A later discovery refresh updates the entry data and reloads it.
        raise ConfigEntryNotReady(
            "Vista Turbo app rejected its discovered machine token"
        ) from err
    except (VistaTurboCannotConnect, VistaTurboProtocolError) as err:
        raise ConfigEntryNotReady from err

    hub = VistaTurboHub(hass, entry, client, snapshot)
    entry.runtime_data = hub
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))
    entry.async_create_background_task(hass, hub.async_listen(), "vistaturbo-native-stream")
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: VistaTurboConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
