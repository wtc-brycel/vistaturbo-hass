from __future__ import annotations

import asyncio
from collections.abc import Callable, Sequence
from datetime import datetime, timezone
import logging
import threading

from .config import SyncSettings
from .protocol import ProtocolQuery, STARTUP_QUERIES, STATE_SYNC_QUERIES

LOG = logging.getLogger(__name__)

SendQuery = Callable[[bytes, str, str], tuple[bool, str]]
BoolCallback = Callable[[], bool]
VoidCallback = Callable[[], None]


class VistaSynchronizer:
    def __init__(
        self,
        settings: SyncSettings,
        is_connected: BoolCallback,
        send_query: SendQuery,
        force_reconnect: VoidCallback,
    ) -> None:
        self.settings = settings
        self.is_connected = is_connected
        self.send_query = send_query
        self.force_reconnect = force_reconnect
        self.ready_event = asyncio.Event()
        self.descriptor_complete_event = asyncio.Event()
        self.lock = asyncio.Lock()
        self._active = threading.Event()
        self._resync_requested = asyncio.Event()
        self._resync_reason = ""
        self._startup_complete = False
        self._program_mode = False
        self.failures_total = 0
        self.failures_consecutive = 0
        self.last_success_at = ""

    def is_active(self) -> bool:
        return self._active.is_set()

    def reset_connection_state(self) -> None:
        self.ready_event.clear()
        self.descriptor_complete_event.clear()
        self._active.clear()
        self._resync_requested.clear()
        self._resync_reason = ""
        self._startup_complete = False
        self._program_mode = False

    def mark_ready(self) -> None:
        self.ready_event.set()

    def mark_descriptor_complete(self) -> None:
        self.descriptor_complete_event.set()

    def set_program_mode(self, active: bool) -> None:
        self._program_mode = active

    def request_full_resync(self, reason: str) -> None:
        if not self.is_connected():
            return
        if reason == "communication_on" and not self._startup_complete:
            return
        self._resync_reason = reason
        self._resync_requested.set()

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
