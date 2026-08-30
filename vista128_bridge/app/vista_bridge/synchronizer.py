from __future__ import annotations

import asyncio
from collections.abc import Callable, Sequence
from datetime import datetime, timezone
from dataclasses import dataclass
import itertools
import logging
import threading

from .config import KeypadSettings, SyncSettings
from .protocol import (
    ARMING_STATUS_QUERY,
    EVENT_LOG_QUERY,
    ProtocolQuery,
    STARTUP_QUERIES,
    STATE_SYNC_QUERIES,
    build_keypad_display_query,
)

LOG = logging.getLogger(__name__)

SendQuery = Callable[[bytes, str, str], tuple[bool, str]]
BoolCallback = Callable[[], bool]
VoidCallback = Callable[[], None]
QueryCallback = Callable[[ProtocolQuery], None]
SnapshotCallback = Callable[[], None]


@dataclass
class PendingTransaction:
    transaction_id: int
    kind: str
    partition: int | None = None
    expected_message: str | None = None
    ready_event: asyncio.Event = None  # type: ignore[assignment]
    response_event: asyncio.Event = None  # type: ignore[assignment]
    response_seen: bool = False

    def __post_init__(self) -> None:
        self.ready_event = asyncio.Event()
        self.response_event = asyncio.Event()


class VistaSynchronizer:
    def __init__(
        self,
        settings: SyncSettings,
        keypad_settings: KeypadSettings,
        event_history_enabled: bool,
        event_history_startup_dump_enabled: bool,
        is_connected: BoolCallback,
        send_query: SendQuery,
        force_reconnect: VoidCallback,
        on_query_start: QueryCallback | None = None,
        on_snapshot_check: SnapshotCallback | None = None,
    ) -> None:
        self.settings = settings
        self.keypad_settings = keypad_settings
        self.event_history_enabled = event_history_enabled
        self.event_history_startup_dump_enabled = event_history_startup_dump_enabled
        self.is_connected = is_connected
        self.send_query = send_query
        self.force_reconnect = force_reconnect
        self.on_query_start = on_query_start
        self.on_snapshot_check = on_snapshot_check
        self.ready_event = asyncio.Event()
        self.descriptor_complete_event = asyncio.Event()
        self.keypad_response_event = asyncio.Event()
        self.event_log_complete_event = asyncio.Event()
        self.lock = asyncio.Lock()
        self._active = threading.Event()
        self._resync_requested = asyncio.Event()
        self._keypad_refresh_requested = asyncio.Event()
        self._keypad_refresh_partitions: set[int] = set()
        self._active_keypad_partition: int | None = None
        self._transactions = itertools.count(1)
        self._pending_transaction: PendingTransaction | None = None
        self._session_tainted = False
        self._resync_reason = ""
        self._recovery_resync_pending = False
        self._startup_complete = False
        self._program_mode = False
        self.failures_total = 0
        self.failures_consecutive = 0
        self.last_success_at = ""

    def is_active(self) -> bool:
        return self._active.is_set()

    def active_keypad_partition(self) -> int | None:
        return self._active_keypad_partition

    def pending_transaction_kind(self) -> str | None:
        transaction = self._pending_transaction
        return transaction.kind if transaction is not None else None

    def reset_connection_state(self) -> None:
        self.ready_event.clear()
        self.descriptor_complete_event.clear()
        self.keypad_response_event.clear()
        self.event_log_complete_event.clear()
        self._active.clear()
        self._resync_requested.clear()
        self._keypad_refresh_requested.clear()
        self._keypad_refresh_partitions.clear()
        self._active_keypad_partition = None
        self._pending_transaction = None
        self._session_tainted = False
        self._resync_reason = ""
        self._recovery_resync_pending = False
        self._startup_complete = False
        self._program_mode = False

    def mark_ready(self) -> bool:
        """Accept 08OK only for the transaction currently awaiting it."""
        transaction = self._pending_transaction
        if transaction is None:
            LOG.debug("Ignoring unowned VISTA 08OK acknowledgement")
            return False
        if (
            transaction.expected_message is not None
            and not transaction.response_seen
        ):
            LOG.warning(
                "Ignoring VISTA 08OK for transaction %d before its expected %s response",
                transaction.transaction_id,
                transaction.expected_message,
            )
            return False
        transaction.ready_event.set()
        self.ready_event.set()
        return True

    def begin_external_transaction(self) -> bool:
        if self._session_tainted or not self.is_connected():
            return False
        self._active.set()
        self._begin_transaction("control")
        return True

    def end_external_transaction(self) -> None:
        self._finish_transaction()
        self._active.clear()

    async def wait_ready(self, timeout_seconds: int) -> bool:
        transaction = self._pending_transaction
        if transaction is None:
            return False
        try:
            await asyncio.wait_for(transaction.ready_event.wait(), timeout=timeout_seconds)
            return True
        except asyncio.TimeoutError:
            self._taint_session("control transaction acknowledgement timeout")
            return False

    async def run_arming_refresh(self) -> bool:
        # Verification is a read-only reconciliation of one already-known
        # dimension. Do not make all HA state unavailable merely because the
        # verification query is in flight; a timeout already taints/reconnects
        # the session and therefore invalidates state through the session reset.
        return await self.run_sync(
            (ARMING_STATUS_QUERY,),
            source="control-verify",
            description="post-control arming verification",
            invalidate_snapshot=False,
        )

    def mark_descriptor_complete(self) -> bool:
        transaction = self._pending_transaction
        if transaction is None or transaction.kind != "zone_descriptor":
            return False
        transaction.response_seen = True
        transaction.response_event.set()
        self.descriptor_complete_event.set()
        return True

    def accept_keypad_response(self, report=None) -> int | None:
        transaction = self._pending_transaction
        if transaction is None or transaction.kind != "keypad":
            LOG.debug("Ignoring keypad response without a pending keypad transaction")
            return None
        if transaction.response_seen:
            LOG.warning(
                "Ignoring duplicate keypad response for transaction %d",
                transaction.transaction_id,
            )
            return None
        if report is not None:
            line_1 = str(getattr(report, "line_1", ""))
            # The KD response used by the bridge normally starts with the
            # partition digit (the optional P prefix appears in some test and
            # panel variants). An absent or different marker is ambiguous and
            # must not be allowed to overwrite another partition.
            if line_1[:1].upper() == "P" and line_1[1:2].isdigit():
                response_partition = line_1[1]
            elif line_1[:1].isdigit():
                response_partition = line_1[0]
            else:
                LOG.warning(
                    "Ignoring keypad response without a partition marker while awaiting P%s",
                    transaction.partition,
                )
                return None
            if response_partition != str(transaction.partition):
                LOG.warning(
                    "Ignoring keypad response for P%s while awaiting P%s",
                    response_partition,
                    transaction.partition,
                )
                return None
        transaction.response_seen = True
        transaction.response_event.set()
        self.keypad_response_event.set()
        return transaction.partition

    def mark_keypad_response(self) -> bool:
        return self.accept_keypad_response() is not None

    def mark_event_log_complete(self) -> bool:
        transaction = self._pending_transaction
        if transaction is None or transaction.kind != "event_log":
            return False
        transaction.response_seen = True
        transaction.response_event.set()
        self.event_log_complete_event.set()
        return True

    def mark_protocol_message(self, message_type: str) -> bool:
        """Record the response type before accepting a flow-control ACK."""
        transaction = self._pending_transaction
        if transaction is None or transaction.expected_message != message_type:
            return False
        transaction.response_seen = True
        transaction.response_event.set()
        return True

    def set_program_mode(self, active: bool) -> None:
        self._program_mode = active
        if (
            not active
            and self._recovery_resync_pending
            and self._startup_complete
            and self.is_connected()
        ):
            self._recovery_resync_pending = False
            self._resync_requested.set()

    def request_full_resync(self, reason: str) -> None:
        if not self.is_connected():
            return
        if reason == "communication_on" and not self._startup_complete:
            return
        self._resync_reason = reason
        self._resync_requested.set()

    def request_recovery_resync(self, reason: str) -> bool:
        """Queue one full snapshot after detected loss of trustworthy RX state."""
        if not self.is_connected() or self._session_tainted:
            return False
        self._resync_reason = reason
        if not self._startup_complete or self._program_mode:
            self._recovery_resync_pending = True
            return True
        self._resync_requested.set()
        return True

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
            return
        self._check_snapshot()
        if self._recovery_resync_pending and not self._program_mode:
            self._recovery_resync_pending = False
            self._resync_requested.set()
        if self.event_history_enabled and self.event_history_startup_dump_enabled:
            await self.run_event_log_dump()

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
                invalidate_snapshot=False,
            )
            if ok and self.keypad_settings.enabled:
                await self._refresh_keypads(tuple(range(1, 9)))
            if not ok:
                # A routine reconciliation does not create an availability gap
                # while it is in flight. If it actually fails, however, the
                # corresponding state is no longer trustworthy and must become
                # unavailable until reconciliation or reconnect restores it.
                self._invalidate_queries(STATE_SYNC_QUERIES)
            self._check_snapshot()
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
        await self._refresh_keypads(tuple(range(1, 9)))
        self._check_snapshot()

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
            self._check_snapshot()

    async def resync_loop(self) -> None:
        while self.is_connected():
            await self._resync_requested.wait()
            if not self.is_connected():
                return
            # Coalesce a burst of recovery requests before issuing the expensive
            # full snapshot. Requests arriving while the transaction itself is
            # running remain set and will receive another pass afterward.
            await asyncio.sleep(0.5)
            if not self.is_connected():
                return
            reason = self._resync_reason or "panel event"
            self._resync_requested.clear()
            ok = await self.run_sync(
                STARTUP_QUERIES,
                source="resync",
                description=f"full VISTA resynchronization ({reason})",
            )
            if not ok:
                LOG.warning("Full VISTA resynchronization failed; reconnecting")
                self.force_reconnect()
                return
            self._check_snapshot()

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
            self._active_keypad_partition = partition
            try:
                transaction = self._begin_transaction(
                    "keypad", partition=partition, expected_message="keypad_display"
                )
            except RuntimeError:
                self._active_keypad_partition = None
                self._active.clear()
                return False
            try:
                accepted, detail = self.send_query(query.data, "keypad", query.name)
                if not accepted:
                    LOG.warning("Keypad query P%d was not sent: %s", partition, detail)
                    return False
                LOG.info("Queued keypad display query: partition %d", partition)
                try:
                    await asyncio.wait_for(
                        transaction.ready_event.wait(),
                        timeout=self.settings.response_timeout_seconds,
                    )
                except asyncio.TimeoutError:
                    self._taint_session(f"keypad P{partition} transaction timeout")
                    LOG.warning(
                        "Keypad display query P%d timed out after %ss",
                        partition,
                        self.settings.response_timeout_seconds,
                    )
                    return False

                if not transaction.response_event.is_set():
                    self._taint_session(f"keypad P{partition} response missing")
                    LOG.warning("Keypad display query P%d returned no display data", partition)
                    return False
                await asyncio.sleep(self.settings.command_delay_ms / 1000)
                return True
            finally:
                self._finish_transaction(transaction)
                self._active_keypad_partition = None
                self._active.clear()

    async def run_event_log_dump(self) -> bool:
        if not self.is_connected():
            return False

        async with self.lock:
            self._active.set()
            transaction = self._begin_transaction("event_log")
            try:
                accepted, detail = self.send_query(
                    EVENT_LOG_QUERY.data, "history", EVENT_LOG_QUERY.name
                )
                if not accepted:
                    LOG.warning("Event-log query was not sent: %s", detail)
                    return False
                LOG.info("Queued VISTA historical event-log dump")
                try:
                    await asyncio.wait_for(
                        transaction.response_event.wait(),
                        timeout=EVENT_LOG_QUERY.timeout_seconds or 45,
                    )
                except asyncio.TimeoutError:
                    self._taint_session("event-log transaction timeout")
                    LOG.warning(
                        "Historical event-log dump timed out after %ss",
                        EVENT_LOG_QUERY.timeout_seconds or 45,
                    )
                    return False
                await asyncio.sleep(self.settings.command_delay_ms / 1000)
                return True
            finally:
                self._finish_transaction(transaction)
                self._active.clear()

    async def run_sync(
        self,
        queries: Sequence[ProtocolQuery],
        *,
        source: str,
        description: str,
        invalidate_snapshot: bool = True,
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
                    self._prepare_query(query, invalidate_snapshot=invalidate_snapshot)
                    transaction = self._pending_transaction
                    accepted, detail = self.send_query(query.data, source, query.name)
                    if not accepted:
                        LOG.warning("Sync query %s was not sent: %s", query.name, detail)
                        failures += 1
                        break
                    LOG.info("Queued %s query: %s", source, query.name)

                    if not await self._wait_for_query(query, transaction):
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
                    self._finish_transaction(transaction)
                    await asyncio.sleep(self.settings.command_delay_ms / 1000)
            finally:
                self._finish_transaction()
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

    def _prepare_query(
        self,
        query: ProtocolQuery,
        *,
        invalidate_snapshot: bool = True,
    ) -> None:
        expected_message = {
            "arming_status": "arming_status",
            "zone_status": "zone_status",
            "zone_partition": "zone_partition",
        }.get(query.name)
        self.ready_event.clear()
        self.descriptor_complete_event.clear()
        self._begin_transaction(
            query.name,
            partition=query.partition,
            expected_message=expected_message,
        )
        if invalidate_snapshot and self.on_query_start is not None:
            self.on_query_start(query)

    def _invalidate_queries(self, queries: Sequence[ProtocolQuery]) -> None:
        if self.on_query_start is None:
            return
        for query in queries:
            self.on_query_start(query)

    async def _wait_for_query(
        self,
        query: ProtocolQuery,
        transaction: PendingTransaction | None,
    ) -> bool:
        if transaction is None:
            return False
        event = transaction.response_event if query.name in {"zone_descriptor"} else transaction.ready_event
        try:
            await asyncio.wait_for(event.wait(), timeout=self._query_timeout(query))
            return True
        except asyncio.TimeoutError:
            self._taint_session(f"{query.name} transaction timeout")
            return False

    def _query_timeout(self, query: ProtocolQuery) -> int:
        return query.timeout_seconds or self.settings.response_timeout_seconds

    def _begin_transaction(
        self,
        kind: str,
        *,
        partition: int | None = None,
        expected_message: str | None = None,
    ) -> PendingTransaction:
        if self._pending_transaction is not None:
            raise RuntimeError("a VISTA transaction is already pending")
        if self._session_tainted:
            raise RuntimeError("VISTA session is tainted; reconnect required")
        transaction = PendingTransaction(
            transaction_id=next(self._transactions),
            kind=kind,
            partition=partition,
            expected_message=expected_message,
        )
        self._pending_transaction = transaction
        return transaction

    def _finish_transaction(self, transaction: PendingTransaction | None = None) -> None:
        if transaction is None or transaction is self._pending_transaction:
            self._pending_transaction = None
        self.ready_event.clear()
        self.descriptor_complete_event.clear()
        self.keypad_response_event.clear()
        self.event_log_complete_event.clear()

    def _taint_session(self, reason: str) -> None:
        if self._session_tainted:
            return
        self._session_tainted = True
        LOG.warning("VISTA session marked unsafe after %s; reconnecting", reason)
        self.force_reconnect()

    def _check_snapshot(self) -> None:
        if self.on_snapshot_check is not None:
            self.on_snapshot_check()
