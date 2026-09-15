from __future__ import annotations

import asyncio
from collections.abc import Callable
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback

from .api import VistaTurboApiClient, VistaTurboApiError, VistaTurboAuthError

_LOGGER = logging.getLogger(__name__)


class VistaTurboHub:
    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: VistaTurboApiClient,
        snapshot: dict,
    ) -> None:
        self.hass = hass
        self.entry = entry
        self.client = client
        self.snapshot = snapshot
        self.api_available = True
        self._listeners: set[Callable[[], None]] = set()

    @property
    def identity(self) -> str:
        return self.entry.unique_id or self.entry.entry_id

    @callback
    def async_add_listener(self, listener: Callable[[], None]) -> Callable[[], None]:
        self._listeners.add(listener)

        @callback
        def remove_listener() -> None:
            self._listeners.discard(listener)

        return remove_listener

    @callback
    def _notify(self) -> None:
        for listener in tuple(self._listeners):
            listener()

    async def async_listen(self) -> None:
        """Consume the app's push stream and reconnect without HTTP polling."""
        delay = 1
        while True:
            try:
                async for snapshot in self.client.async_snapshots():
                    self.snapshot = snapshot
                    self.api_available = True
                    delay = 1
                    self._notify()
            except asyncio.CancelledError:
                raise
            except VistaTurboAuthError:
                self.api_available = False
                self._notify()
                _LOGGER.error("Vista Turbo app rejected its discovered machine token")
                await asyncio.sleep(30)
            except VistaTurboApiError as err:
                if self.api_available:
                    _LOGGER.warning("Vista Turbo app event stream unavailable: %s", err)
                self.api_available = False
                self._notify()
                await asyncio.sleep(delay)
                delay = min(delay * 2, 30)
