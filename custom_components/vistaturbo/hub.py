from __future__ import annotations

import asyncio
from collections.abc import Callable
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback

from .api import VistaTurboApiClient, VistaTurboApiError, VistaTurboAuthError

_LOGGER = logging.getLogger(__name__)


def _entity_capabilities(snapshot: dict) -> tuple[bool, tuple[str, ...]]:
    event_types = snapshot.get("events", {}).get("types", [])
    return (
        bool(snapshot.get("control", {}).get("native_alarm")),
        tuple(str(value) for value in event_types if isinstance(value, str)),
    )


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
        self.event_stream_available = True
        self.last_event_sequence = 0
        self.event_stream_gap_detected = False
        self.event_stream_gap: dict | None = None
        self._listeners: set[Callable[[], None]] = set()
        self._event_listeners: set[Callable[[dict], None]] = set()

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
    def async_add_event_listener(
        self, listener: Callable[[dict], None]
    ) -> Callable[[], None]:
        self._event_listeners.add(listener)

        @callback
        def remove_listener() -> None:
            self._event_listeners.discard(listener)

        return remove_listener

    @callback
    def _notify(self) -> None:
        for listener in tuple(self._listeners):
            listener()

    @callback
    def _notify_event(self, event: dict) -> None:
        for listener in tuple(self._event_listeners):
            listener(event)

    async def async_listen(self) -> None:
        """Consume the app's state push stream and reconnect without HTTP polling."""
        delay = 1
        while True:
            try:
                async for snapshot in self.client.async_snapshots():
                    capability_changed = _entity_capabilities(snapshot) != _entity_capabilities(
                        self.snapshot
                    )
                    self.snapshot = snapshot
                    self.api_available = True
                    delay = 1
                    self._notify()
                    if capability_changed:
                        _LOGGER.info(
                            "Vista Turbo entity capabilities changed; reloading integration"
                        )
                        self.hass.config_entries.async_schedule_reload(self.entry.entry_id)
                        return
            except asyncio.CancelledError:
                raise
            except VistaTurboAuthError:
                self.api_available = False
                self._notify()
                _LOGGER.error("Vista Turbo app rejected its discovered machine token")
                await asyncio.sleep(30)
            except VistaTurboApiError as err:
                if self.api_available:
                    _LOGGER.warning("Vista Turbo app state stream unavailable: %s", err)
                self.api_available = False
                self._notify()
                await asyncio.sleep(delay)
                delay = min(delay * 2, 30)

    async def async_listen_events(self) -> None:
        """Consume ordered transient panel events with replay after reconnect."""
        delay = 1
        while True:
            try:
                async for message in self.client.async_events(self.last_event_sequence):
                    kind = message.get("kind")
                    data = message.get("data")
                    if not isinstance(data, dict):
                        continue
                    if kind == "gap":
                        self.event_stream_gap_detected = True
                        self.event_stream_gap = dict(data)
                        self.last_event_sequence = int(data["reset_to"])
                        _LOGGER.error(
                            "Vista Turbo native event replay gap detected: %s",
                            data.get("reason"),
                        )
                        self._notify()
                        continue
                    if kind != "event":
                        continue
                    self.last_event_sequence = int(data["sequence"])
                    if not self.event_stream_available:
                        self.event_stream_available = True
                        self._notify()
                    delay = 1
                    self._notify_event(data)

                if self.event_stream_available:
                    _LOGGER.warning("Vista Turbo app event stream closed; reconnecting")
                self.event_stream_available = False
                self._notify()
                await asyncio.sleep(delay)
                delay = min(delay * 2, 30)
            except asyncio.CancelledError:
                raise
            except VistaTurboAuthError:
                self.event_stream_available = False
                self._notify()
                _LOGGER.error(
                    "Vista Turbo app rejected its discovered machine token on event stream"
                )
                await asyncio.sleep(30)
            except VistaTurboApiError as err:
                if self.event_stream_available:
                    _LOGGER.warning("Vista Turbo app event stream unavailable: %s", err)
                self.event_stream_available = False
                self._notify()
                await asyncio.sleep(delay)
                delay = min(delay * 2, 30)
