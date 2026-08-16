from __future__ import annotations

import asyncio
from collections.abc import Callable, Sequence
from datetime import datetime, timezone
import logging
import threading

from .config import KeypadSettings, SyncSettings
from .protocol import (
    ProtocolQuery,
    STARTUP_QUERIES,
    STATE_SYNC_QUERIES,
    build_keypad_display_query,
)

LOG = logging.getLogger(__name__)

SendQuery = Callable[[bytes, str, str], tuple[bool, str]]
BoolCallback = Callable[[], bool]
VoidCallback = Callable[[], None]


class VistaSynchronizer:
    def __init__(
        self,
        settings: SyncSettings,
        keypad_settings: KeypadSettings,
        is_connected: BoolCallback,
        send_query: SendQuery,
        force_reconnect: VoidCallback,
    ) -> None:
        self.settings = settings
        self.keypad_settings = keypad_settings
        self.is_connected = is_connected
        self.send_query = send_query
        self.force_reconnect = force_reconnect
        self.ready_event = asyncio.Event()
        self.descriptor_complete_event = asyncio.Event()
        self.keypad_response_event = asyncio.Event()
        self.lock = asyncio.Lock()
        self._active = threading.Event()
        self._resync_requested = asyncio.Event()
        self._keypad_refresh_requested = asyncio.Event()
        self._keypad_refresh_partitions: set[int] = set()
        self._active_keypad_partition: int | None = None
        self._resync_reason = ""
        self._startup_complete = False
        self._program_mode = False
        self.failures_total = 0
        self.failures_consecutive = 0
        self.last_success_at = ""

    def is_active(self) -> bool:
        return self._active.is_set()

    def active_keypad_partition(self) -> int | None:
        return self._active_keypad_partition

    def reset_connection_state(self) -> None:
        self.ready_event.clear()
        self.descriptor_complete_event.clear()
        self.keypad_response_event.clear()
        self._active.clear()
        self._resync_requested.clear()
        self._keypad_refresh_requested.clear()
        self._keypad_refresh_partitions.clear()
        self._active_keypad_partition = None
        self._resync_reason = ""
        self._startup_complete = False
        self._program_mode = False

    def mark_ready(self) -> None:
        self.ready_event.set()

    def mark_descriptor_complete(self) -> None:
        self.descriptor_complete_event.set()

    def mark_keypad_response(self) -> None:
        self.keypad_response_event.set()

    def set_program_mode(self, active: bool) -> None:
        self._program_mode = active

    def request_full_resync(self, reason: str) -> None:
        if not self.is_connected():
            return
        if reason == "communication_on" and not self._startup_complete:
            return
        self._resync_reason = reason
        self._resync_requested.set()

    def request_keypad_refresh(self, partition: int) -> None:
        if not self.keypad_settings.enabled or not self.is_connected():
            return
        if partition not in self.keypad_settings.partitions:
            return
        self._keypad_refresh_partitions.add(partition)
        self._keypad_refresh_requested.set()

    async def startup(self) -> None:
        await asyncio.sleep(self.settings.initial_delay_ms / 1000)
        if not self.is_connected():
            return
        ok = await self.run_sync(
            STARTUP_QUERIES,
            source="startup",
            description="read-only VISTA startup synchronization",
        )
        self._startup_complete = ok
        if not ok:
            LOG.warning("Startup synchronization failed; reconnecting")
            self.force_reconnect()

    async def periodic_loop(self) -> None:
        while self.is_connected():
            await asyncio.sleep(self.settings.periodic_interval_seconds)
            if not self.is_connected():
                return
            if self._program_mode:
                LOG.info("Skipping reconciliation during programming mode")
                continue
            ok = await self.run_sync(
                STATE_SYNC_QUERIES,
                source="periodic",
                description="periodic VISTA state reconciliation",
            )
            if not ok and self.failures_consecutive >= self.settings.reconnect_after_failures:
                LOG.warning(
                    "Reconnecting after %d failed synchronizations",
                    self.failures_consecutive,
                )
                self.force_reconnect()
                return

    async def keypad_loop(self) -> None:
        initial_delay = max(1.0, (self.settings.initial_delay_ms / 1000) + 0.5)
        await asyncio.sleep(initial_delay)
        if not self.is_connected():
            return

        self._keypad_refresh_partitions.clear()
        self._keypad_refresh_requested.clear()
        await self._refresh_keypads(self.keypad_settings.partitions)

        while self.is_connected():
            try:
                await asyncio.wait_for(
                    self._keypad_refresh_requested.wait(),
                    timeout=self.keypad_settings.poll_interval_seconds,
                )
            except asyncio.TimeoutError:
                partitions = self.keypad_settings.partitions
            else:
                await asyncio.sleep(self.keypad_settings.event_refresh_delay_ms / 1000)
                partitions = tuple(sorted(self._keypad_refresh_partitions))
                self._keypad_refresh_partitions.clear()
                self._keypad_refresh_requested.clear()

            if not self.is_connected():
                return
            await self._refresh_keypads(partitions)

    async def resync_loop(self) -> None:
        while self.is_connected():
            await self._resync_requested.wait()
            self._resync_requested.clear()
            if not self.is_connected():
                return
            reason = self._resync_reason or "panel event"
            await asyncio.sleep(0.5)
            await self.run_sync(
                STARTUP_QUERIES,
                source="resync",
                description=f"full VISTA resynchronization ({reason})",
            )

    async def _refresh_keypads(self, partitions: Sequence[int]) -> None:
        if self._program_mode:
            return
        for partition in partitions:
            if not self.is_connected():
                return
            await self.run_keypad_refresh(partition)

    async def run_keypad_refresh(self, partition: int) -> bool:
        if not self.is_connected():
            return False

        query = build_keypad_display_query(partition)
        async with self.lock:
            self._active.set()
            self.ready_event.clear()
            self.keypad_response_event.clear()
            self._active_keypad_partition = partition
            try:
                accepted, detail = self.send_query(query.data, "keypad", query.name)
                if not accepted:
                    LOG.warning("Keypad query P%d was not sent: %s", partition, detail)
                    return False
                LOG.info("Queued keypad display query: partition %d", partition)
                try:
                    await asyncio.wait_for(
                        self.ready_event.wait(),
                        timeout=self.settings.response_timeout_seconds,
                    )
                except asyncio.TimeoutError:
                    LOG.warning(
                        "Keypad display query P%d timed out after %ss",
                        partition,
                        self.settings.response_timeout_seconds,
                    )
                    return False

                if not self.keypad_response_event.is_set():
                    LOG.warning("Keypad display query P%d returned no display data", partition)
                    return False
                await asyncio.sleep(self.settings.command_delay_ms / 1000)
                return True
            finally:
                self._active_keypad_partition = None
                self._active.clear()

    async def run_sync(
        self,
        queries: Sequence[ProtocolQuery],
        *,
        source: str,
        description: str,
    ) -> bool:
        if not self.is_connected():
            return False

        failures = 0
        async with self.lock:
            self._active.set()
            try:
                LOG.info("Starting %s", description)
                for query in queries:
                    if not self.is_connected():
                        return False
                    self._prepare_query(query)
                    accepted, detail = self.send_query(query.data, source, query.name)
                    if not accepted:
                        LOG.warning("Sync query %s was not sent: %s", query.name, detail)
                        failures += 1
                        break
                    LOG.info("Queued %s query: %s", source, query.name)

                    if not await self._wait_for_query(query):
                        if query.required:
                            failures += 1
                            LOG.warning(
                                "Required %s query %s timed out after %ss",
                                source,
                                query.name,
                                self._query_timeout(query),
                            )
                        else:
                            LOG.warning(
                                "Optional %s query %s timed out after %ss",
                                source,
                                query.name,
                                self._query_timeout(query),
                            )
                        break
                    await asyncio.sleep(self.settings.command_delay_ms / 1000)
            finally:
                self._active.clear()

        if failures:
            self.failures_total += 1
            self.failures_consecutive += 1
            LOG.warning(
                "%s failed; consecutive failures=%d",
                description,
                self.failures_consecutive,
            )
            return False

        self.last_success_at = datetime.now(timezone.utc).isoformat()
        self.failures_consecutive = 0
        LOG.info("%s complete", description)
        return True

    def _prepare_query(self, query: ProtocolQuery) -> None:
        self.ready_event.clear()
        if query.name == "zone_descriptor":
            self.descriptor_complete_event.clear()

    async def _wait_for_query(self, query: ProtocolQuery) -> bool:
        event = (
            self.descriptor_complete_event
            if query.name == "zone_descriptor"
            else self.ready_event
        )
        try:
            await asyncio.wait_for(event.wait(), timeout=self._query_timeout(query))
            return True
        except asyncio.TimeoutError:
            return False

    def _query_timeout(self, query: ProtocolQuery) -> int:
        return query.timeout_seconds or self.settings.response_timeout_seconds
