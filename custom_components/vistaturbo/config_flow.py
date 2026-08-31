from __future__ import annotations

from typing import Any

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_HOST
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.service_info.hassio import HassioServiceInfo

from .api import VistaTurboApiClient, VistaTurboApiError
from .const import API_SCHEMA, CONF_PORT, CONF_TOKEN, DEFAULT_PORT, DOMAIN


class VistaTurboConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Configure the integration from Supervisor app discovery."""

    VERSION = 1

    def __init__(self) -> None:
        self._discovery: dict[str, Any] | None = None
        self._title = "Vista Turbo RS232"

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        return self.async_abort(reason="app_discovery_required")

    async def async_step_hassio(
        self, discovery_info: HassioServiceInfo
    ) -> ConfigFlowResult:
        config = discovery_info.config
        try:
            schema = int(config.get("schema", 0))
            port = int(config.get(CONF_PORT, DEFAULT_PORT))
        except (TypeError, ValueError):
            return self.async_abort(reason="invalid_discovery")
        if schema != API_SCHEMA:
            return self.async_abort(reason="unsupported_app_api")

        token = str(config.get(CONF_TOKEN, "")).strip()
        if not token or not 1 <= port <= 65535:
            return self.async_abort(reason="invalid_discovery")

        self._title = discovery_info.name or self._title
        self._discovery = {
            CONF_HOST: str(
                config.get(CONF_HOST) or discovery_info.slug.replace("_", "-")
            ),
            CONF_PORT: port,
            CONF_TOKEN: token,
        }
        # Home Assistant's Supervisor discovery cleanup keys HASSIO-sourced
        # entries by this discovery UUID. Using the add-on slug here would leave
        # a stale ConfigEntry behind when the Supervisor discovery is removed.
        await self.async_set_unique_id(discovery_info.uuid)
        self._abort_if_unique_id_configured(updates=self._discovery)
        return await self.async_step_hassio_confirm()

    async def async_step_hassio_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if self._discovery is None:
            return self.async_abort(reason="invalid_discovery")

        errors: dict[str, str] = {}
        if user_input is not None:
            client = VistaTurboApiClient(
                async_get_clientsession(self.hass),
                self._discovery[CONF_HOST],
                self._discovery[CONF_PORT],
                self._discovery[CONF_TOKEN],
            )
            try:
                await client.async_get_snapshot()
            except VistaTurboApiError:
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(title=self._title, data=self._discovery)

        return self.async_show_form(step_id="hassio_confirm", errors=errors)
