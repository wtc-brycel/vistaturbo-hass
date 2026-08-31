from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
import itertools
import logging
import queue
import threading
import time
from collections.abc import Callable

from .command_model import (
    MAX_LOGICAL_KEYPAD_SEQUENCE,
    ExecutionPlan,
    KeypadParser,
    NATIVE_COMMANDS,
    VistaCommand,
    plan_command,
)
from .config import ControlSettings
from .protocol import build_keypad_stroke_command, build_native_alarm_command
from .state import VistaState
from .synchronizer import VistaSynchronizer

LOG = logging.getLogger(__name__)

SendQuery = Callable[[bytes, str, str], tuple[bool, str]]
BoolCallback = Callable[[], bool]
PublishResult = Callable[[dict], None]
AuditResult = Callable[[dict], None]

BASIC_KEYPAD_KEYS = frozenset("0123456789*#")
MAX_KEYPAD_STROKES = 5


@dataclass(frozen=True)
class ControlRequest:
    request_id: int
    kind: str
    partition: int
    value: str = field(repr=False)
    code: str = field(repr=False)
    generation: int
    enqueued_at: float
    started_at: str = ""
    command_sequence: str = field(default="", repr=False)
    operands: dict | None = None
    interaction_id: str = ""
    audit_interaction_id: str = ""
    actor_id: str = ""
    actor_name: str = ""
    source: str = "mqtt"
    action: str = "keypad_sequence"
    interaction_complete: bool = True
    audit_request_id: str = ""
    command: VistaCommand | None = None
    plan: ExecutionPlan | None = None


EXPECTED_ARMING_MODES = {
    "ARM_AWAY": {"A"},
    "ARM_HOME": {"H"},
    "ARM_NIGHT": {"I"},
    "ARM_MAXIMUM": {"M"},
    "FORCE_ARM_AWAY": {"A", "B"},
    "FORCE_ARM_HOME": {"H", "B"},
    "DISARM": {"D", "N"},
}


class VistaControlCoordinator:
    """Serialized, non-replaying VISTA write coordinator.

    MQTT callbacks run on Paho's network thread, so enqueue methods use a
    thread-safe queue. The async worker serializes control transactions through
    the same synchronizer lock used by all read queries. A request belongs to a
    single panel TCP generation and is never carried across reconnects.
    """

    def __init__(
        self,
        settings: ControlSettings,
        state: VistaState,
        synchronizer: VistaSynchronizer,
        is_connected: BoolCallback,
        send_query: SendQuery,
        publish_result: PublishResult,
        audit_result: AuditResult | None = None,
    ) -> None:
        self.settings = settings
        self.state = state
        self.synchronizer = synchronizer
        self.is_connected = is_connected
        self.send_query = send_query
        self.publish_result = publish_result
        self.audit_result = audit_result
        self._queue: queue.Queue[ControlRequest] = queue.Queue(maxsize=64)
        self._automation_available = threading.Event()
        self._automation_state_lock = threading.Lock()
        self._automation_source = "unknown"
        self._automation_blocked = False
        self._generation_lock = threading.Lock()
        self._generation = 0
        self._request_ids = itertools.count(1)
        self._keypad_reservation_lock = threading.Lock()
        self._keypad_owner = ""
        self._keypad_owner_partition = 0
        self._interaction_sequences: dict[str, str] = {}

    def automation_available(self) -> bool:
        return self._automation_available.is_set()

    def automation_availability_source(self) -> str:
        with self._automation_state_lock:
            return self._automation_source

    def infer_automation_available(self) -> bool:
        """Infer automation availability from a successful structured transaction.

        An explicit XF Communication Off latches the session blocked and cannot be
        overridden by ordinary OK replies. A new TCP session clears the latch.
        """
        with self._automation_state_lock:
            if self._automation_blocked or self._automation_available.is_set():
                return False
            self._automation_available.set()
            self._automation_source = "inferred"
            return True

    def set_automation_available(self, available: bool, *, source: str = "explicit") -> bool:
        with self._automation_state_lock:
            before = self._automation_available.is_set()
            before_source = self._automation_source
            if available:
                self._automation_blocked = False
                self._automation_available.set()
                self._automation_source = source
            else:
                self._automation_blocked = True
                self._automation_available.clear()
                self._automation_source = "communication_off"
            changed = (before != self._automation_available.is_set()) or (before_source != self._automation_source)
        if not available:
            self.discard_pending("automation_unavailable")
        return changed

    def reset_session(self) -> int:
        with self._generation_lock:
            self._generation += 1
            generation = self._generation
        with self._automation_state_lock:
            self._automation_available.clear()
            self._automation_blocked = False
            self._automation_source = "unknown"
        self.discard_pending("panel_session_reset")
        with self._keypad_reservation_lock:
            self._keypad_owner = ""
            self._keypad_owner_partition = 0
            self._interaction_sequences.clear()
        return generation

    def _reserve_keypad_interaction(
        self, partition: int, interaction_id: str
    ) -> tuple[bool, bool]:
        """Reserve the panel keypad for one logical interaction.

        The VISTA KS path has no transaction identifier. The owner therefore
        remains held for the complete logical interaction so two callers
        cannot interleave segmented commands. An explicit final segment,
        cancellation, or panel session reset releases it. There is no elapsed
        time boundary: a slow but active interaction must not be split.
        """
        if not interaction_id:
            return True, False
        with self._keypad_reservation_lock:
            if not self._keypad_owner:
                self._keypad_owner = interaction_id
                self._keypad_owner_partition = partition
                return True, True
            if (
                self._keypad_owner == interaction_id
                and self._keypad_owner_partition == partition
            ):
                return True, False
            return False, False

    def _admit_keypad_request(
        self,
        partition: int,
        interaction_id: str,
        interaction_complete: bool,
    ) -> tuple[bool, bool]:
        """Admit one keypad request without over-reserving physical keypresses.

        A completed request is already an atomic KS transaction and only needs
        FIFO ordering. Exclusive ownership is required only while a caller has
        deliberately left a logical interaction open across multiple requests.
        If an open interaction already owns the keypad, only that same owner may
        append its next/final segment.
        """
        with self._keypad_reservation_lock:
            if self._keypad_owner:
                if (
                    self._keypad_owner == interaction_id
                    and self._keypad_owner_partition == partition
                ):
                    return True, False
                return False, False
            if interaction_complete:
                return True, False
            if not interaction_id:
                return False, False
            self._keypad_owner = interaction_id
            self._keypad_owner_partition = partition
            return True, True

    def _release_keypad_interaction(self, interaction_id: str) -> None:
        if not interaction_id:
            return
        with self._keypad_reservation_lock:
            if self._keypad_owner == interaction_id:
                self._keypad_owner = ""
                self._keypad_owner_partition = 0

    def _current_generation(self) -> int:
        with self._generation_lock:
            return self._generation

    def discard_pending(self, reason: str) -> int:
        discarded = 0
        while True:
            try:
                request = self._queue.get_nowait()
            except queue.Empty:
                break
            discarded += 1
            self._result(request, False, reason)
        if discarded:
            LOG.warning("Discarded %d pending VISTA control request(s): %s", discarded, reason)
        return discarded

    def _preflight(self, kind: str) -> tuple[bool, str]:
        if not self.settings.enabled:
            return False, "control_disabled"
        if kind == "keypad" and not self.settings.keypad_enabled:
            return False, "keypad_control_disabled"
        if kind == "alarm" and not self.settings.native_alarm_enabled:
            return False, "native_alarm_control_disabled"
        if kind == "command" and not (
            self.settings.native_alarm_enabled or self.settings.keypad_enabled
        ):
            return False, "command_control_disabled"
        if not self.is_connected():
            return False, "panel_offline"
        if not self.automation_available():
            return False, "automation_interface_unavailable"
        return True, "accepted"

    def enqueue_keypad(
        self,
        partition: int,
        key: str,
        metadata: dict | None = None,
    ) -> tuple[bool, str]:
        """Queue one or more keypad strokes as one serialized transaction."""
        ok, detail = self._preflight("keypad")
        if not ok:
            return ok, detail
        if (
            not isinstance(key, str)
            or not 1 <= len(key) <= MAX_KEYPAD_STROKES
            or any(stroke not in BASIC_KEYPAD_KEYS for stroke in key)
        ):
            return False, "unsupported_keypad_key"
        try:
            build_keypad_stroke_command(partition, key)
        except ValueError:
            return False, "invalid_keypad_command"
        return self._enqueue("keypad", partition, key, "", metadata)

    def enqueue_command(
        self,
        command: VistaCommand,
        metadata: dict | None = None,
    ) -> tuple[bool, str]:
        """Queue one canonical command through the normal transaction path."""
        if not isinstance(command, VistaCommand):
            return False, "invalid_vista_command"
        ok, detail = self._preflight("command")
        if not ok:
            return ok, detail
        try:
            plan = plan_command(
                command,
                native_available=self.settings.native_alarm_enabled,
                keypad_available=self.settings.keypad_enabled,
            )
        except ValueError as exc:
            return False, str(exc)
        metadata = dict(metadata) if isinstance(metadata, dict) else {}
        metadata.setdefault("interaction_id", command.interaction_id)
        metadata.setdefault("actor_id", command.actor_id)
        metadata.setdefault("actor_name", command.actor_name)
        metadata.setdefault("source", command.source)
        metadata.setdefault("action", command.command_type)
        metadata.setdefault("command_sequence", plan.keypad_sequence)
        metadata.setdefault("operands", command.operands)
        metadata.setdefault("interaction_complete", True)
        return self._enqueue_command(command, plan, metadata)

    def _enqueue_command(
        self,
        command: VistaCommand,
        plan: ExecutionPlan,
        metadata: dict,
    ) -> tuple[bool, str]:
        request_id = next(self._request_ids)
        interaction_id = str(metadata.get("interaction_id", "")) or f"command-{request_id}"
        reservation_created = False
        if plan.mechanism == "keypad":
            available, reservation_created = self._reserve_keypad_interaction(
                command.partition or 0, interaction_id
            )
            if not available:
                return False, "keypad_interaction_busy"
            if interaction_id and len(plan.keypad_sequence) > MAX_LOGICAL_KEYPAD_SEQUENCE:
                if reservation_created:
                    self._release_keypad_interaction(interaction_id)
                return False, "keypad_sequence_too_long"
        request = ControlRequest(
            request_id=request_id,
            kind="command",
            partition=command.partition or 0,
            value=plan.native_action,
            code=command.code,
            generation=self._current_generation(),
            enqueued_at=time.monotonic(),
            started_at=str(metadata.get("started_at", "")),
            command_sequence=plan.keypad_sequence,
            operands=dict(command.operands),
            interaction_id=interaction_id,
            audit_interaction_id=str(metadata.get("audit_interaction_id", "")),
            actor_id=str(metadata.get("actor_id", command.actor_id)),
            actor_name=str(metadata.get("actor_name", command.actor_name)),
            source=str(metadata.get("source", command.source)),
            action=str(metadata.get("action", command.command_type)),
            interaction_complete=True,
            audit_request_id=str(
                metadata.get("audit_request_id", metadata.get("request_id", ""))
                or f"control-{request_id}"
            ),
            command=command,
            plan=plan,
        )
        try:
            self._queue.put_nowait(request)
        except queue.Full:
            if reservation_created:
                self._release_keypad_interaction(interaction_id)
            return False, "control_queue_full"
        if plan.mechanism == "keypad" and interaction_id:
            with self._keypad_reservation_lock:
                self._interaction_sequences[interaction_id] = plan.keypad_sequence
        return True, "queued"

    def enqueue_alarm(
        self,
        partition: int,
        action: str,
        code: str,
        metadata: dict | None = None,
    ) -> tuple[bool, str]:
        ok, detail = self._preflight("alarm")
        if not ok:
            return ok, detail
        try:
            build_native_alarm_command(action, code, (partition,))
        except ValueError as exc:
            return False, str(exc)
        return self._enqueue(
            "alarm", partition, str(action).upper(), str(code), metadata
        )

    def _enqueue(
        self,
        kind: str,
        partition: int,
        value: str,
        code: str,
        metadata: dict | None = None,
    ) -> tuple[bool, str]:
        metadata = metadata if isinstance(metadata, dict) else {}
        request_id = next(self._request_ids)
        interaction_id = str(metadata.get("interaction_id", ""))
        interaction_complete = bool(metadata.get("interaction_complete", True))
        reservation_created = False
        if kind == "keypad":
            available, reservation_created = self._admit_keypad_request(
                partition, interaction_id, interaction_complete
            )
            if not available:
                return False, "keypad_interaction_busy"
            with self._keypad_reservation_lock:
                current = self._interaction_sequences.get(interaction_id, "")
            if len(current) + len(value) > MAX_LOGICAL_KEYPAD_SEQUENCE:
                if reservation_created:
                    self._release_keypad_interaction(interaction_id)
                return False, "keypad_sequence_too_long"
        request = ControlRequest(
            request_id=request_id,
            kind=kind,
            partition=partition,
            value=value,
            code=code,
            generation=self._current_generation(),
            enqueued_at=time.monotonic(),
            started_at=str(metadata.get("started_at", "")),
            command_sequence=str(
                metadata.get("command_sequence", value if kind == "keypad" else code)
            ),
            operands=(
                dict(metadata["operands"])
                if isinstance(metadata.get("operands"), dict)
                else None
            ),
            interaction_id=interaction_id,
            audit_interaction_id=str(metadata.get("audit_interaction_id", "")),
            actor_id=str(metadata.get("actor_id", "")),
            actor_name=str(metadata.get("actor_name", "")),
            source=str(metadata.get("source", "mqtt")),
            action=str(
                metadata.get(
                    "action",
                    "keypad_sequence" if kind == "keypad" else value.lower(),
                )
            ),
            interaction_complete=interaction_complete,
            audit_request_id=str(
                metadata.get("audit_request_id", metadata.get("request_id", ""))
                or f"control-{request_id}"
            ),
            command=VistaCommand(
                command_type="keypad_command" if kind == "keypad" else str(value).lower(),
                partition=partition,
                code=code,
                raw_sequence=value if kind == "keypad" else "",
                operands=(
                    dict(metadata["operands"])
                    if isinstance(metadata.get("operands"), dict)
                    else {}
                ),
                source=str(metadata.get("source", "mqtt")),
                actor_id=str(metadata.get("actor_id", "")),
                actor_name=str(metadata.get("actor_name", "")),
                interaction_id=interaction_id,
            ),
        )
        try:
            self._queue.put_nowait(request)
        except queue.Full:
            if reservation_created:
                self._release_keypad_interaction(interaction_id)
            return False, "control_queue_full"
        if kind == "keypad" and interaction_id:
            with self._keypad_reservation_lock:
                self._interaction_sequences[interaction_id] = (
                    f"{self._interaction_sequences.get(interaction_id, '')}{value}"
                )
        return True, "queued"

    async def run(self, stop_event: asyncio.Event) -> None:
        while not stop_event.is_set():
            if not await self.process_next():
                await asyncio.sleep(0.02)

    async def process_next(self) -> bool:
        request = self._dequeue_request()
        if request is None:
            return False
        await self._process(request)
        return True

    def _dequeue_request(self) -> ControlRequest | None:
        """Choose only the current keypad owner while a sequence is open."""
        try:
            first = self._queue.get_nowait()
        except queue.Empty:
            return None
        with self._keypad_reservation_lock:
            owner = self._keypad_owner
        if not owner:
            return first

        selected = (
            first
            if first.interaction_id == owner
            and first.kind in {"keypad", "command"}
            else None
        )
        pending = [] if selected is not None else [first]
        while True:
            try:
                candidate = self._queue.get_nowait()
            except queue.Empty:
                break
            if selected is None and (
                candidate.interaction_id == owner
                and candidate.kind in {"keypad", "command"}
            ):
                selected = candidate
            else:
                pending.append(candidate)
        for candidate in pending:
            try:
                self._queue.put_nowait(candidate)
            except queue.Full:
                # A concurrent producer can fill the queue while it is being
                # rotated. Never lose the operation silently.
                LOG.error("Could not restore deferred VISTA control request")
                self._result(candidate, False, "control_queue_requeue_failed")
        return selected

    async def _process(self, request: ControlRequest) -> None:
        if request.generation != self._current_generation():
            self._result(request, False, "stale_session")
            return
        if time.monotonic() - request.enqueued_at > 4.5:
            self._result(request, False, "request_expired")
            return
        ok, detail = self._preflight(request.kind)
        if not ok:
            self._result(request, False, detail)
            return

        if request.kind == "command" and request.plan is not None:
            await self._process_command(request)
            return

        await self._process_legacy(request)

    async def _send_external_transaction(
        self, frame: bytes, label: str
    ) -> tuple[bool, str]:
        transaction_started = self.synchronizer.begin_external_transaction()
        if transaction_started is False:
            return False, "transaction_unavailable"
        try:
            accepted, detail = self.send_query(frame, "control", label)
            if not accepted:
                return False, detail
            if not await self.synchronizer.wait_ready(
                self.settings.response_timeout_seconds
            ):
                return False, "no_ready_ack"
            return True, "acknowledged"
        finally:
            self.synchronizer.end_external_transaction()

    async def _process_legacy(self, request: ControlRequest) -> None:
        if request.kind == "keypad":
            frame = build_keypad_stroke_command(request.partition, request.value)
            label = f"keypad_p{request.partition}"
        else:
            frame = build_native_alarm_command(
                request.value, request.code, (request.partition,)
            )
            label = f"{request.value.lower()}_p{request.partition}"

        async with self.synchronizer.lock:
            if request.generation != self._current_generation() or not self.is_connected():
                self._result(request, False, "stale_session")
                return
            if not self.automation_available():
                self._result(request, False, "automation_interface_unavailable")
                return
            accepted, detail = await self._send_external_transaction(frame, label)
            if not accepted:
                self._result(request, False, detail)
                return

        if request.generation != self._current_generation() or not self.is_connected():
            self._result(request, False, "connection_lost_after_send")
            return

        if request.kind == "keypad":
            # Keep code entry responsive. Do not block each digit behind a full
            # KD round trip; the existing keypad loop coalesces refresh requests.
            self.synchronizer.request_keypad_refresh(request.partition)
            self._result(request, True, "accepted")
            return

        if self.settings.verify_delay_ms:
            await asyncio.sleep(self.settings.verify_delay_ms / 1000)
        if request.generation != self._current_generation() or not self.is_connected():
            self._result(request, False, "connection_lost_after_send")
            return

        refreshed = await self.synchronizer.run_arming_refresh()
        partition = self.state.partitions.get(request.partition)
        raw_mode = partition.raw_mode if partition is not None else ""
        expected = EXPECTED_ARMING_MODES.get(request.value, set())
        confirmed = bool(refreshed and raw_mode in expected)
        self._result(
            request,
            confirmed,
            "confirmed" if confirmed else "verification_mismatch",
            action=request.value,
            raw_mode=raw_mode or None,
        )

    async def _process_command(self, request: ControlRequest) -> None:
        plan = request.plan
        command = request.command
        if plan is None or command is None:
            self._result(request, False, "invalid_command_plan")
            return

        if plan.mechanism == "keypad":
            async with self.synchronizer.lock:
                if request.generation != self._current_generation() or not self.is_connected():
                    self._result(request, False, "stale_session")
                    return
                for index, segment in enumerate(plan.keypad_segments):
                    accepted, detail = await self._send_external_transaction(
                        build_keypad_stroke_command(request.partition, segment),
                        f"keypad_p{request.partition}_segment_{index + 1}",
                    )
                    if not accepted:
                        self._result(request, False, detail)
                        return
            if request.generation != self._current_generation() or not self.is_connected():
                self._result(request, False, "connection_lost_after_send")
                return
            self.synchronizer.request_keypad_refresh(request.partition)

            native_action = NATIVE_COMMANDS.get(command.command_type, "")
            if native_action:
                confirmed, verification_status = await self._verify_arming(
                    request, native_action
                )
                self._result(
                    request,
                    confirmed,
                    verification_status,
                    action=command.command_type,
                )
            else:
                self._result(
                    request,
                    True,
                    "accepted",
                    action=command.command_type,
                    verification="acknowledged",
                )
            return

        frame = build_native_alarm_command(
            plan.native_action, command.code, (request.partition,)
        )
        async with self.synchronizer.lock:
            if request.generation != self._current_generation() or not self.is_connected():
                self._result(request, False, "stale_session")
                return
            accepted, detail = await self._send_external_transaction(
                frame, f"{plan.native_action.lower()}_p{request.partition}"
            )
            if not accepted:
                self._result(request, False, detail)
                return
        if request.generation != self._current_generation() or not self.is_connected():
            self._result(request, False, "connection_lost_after_send")
            return
        confirmed, verification_status = await self._verify_arming(
            request, plan.native_action
        )
        self._result(
            request,
            confirmed,
            verification_status,
            action=command.command_type,
        )

    async def _verify_arming(
        self, request: ControlRequest, action: str
    ) -> tuple[bool, str]:
        if self.settings.verify_delay_ms:
            await asyncio.sleep(self.settings.verify_delay_ms / 1000)
        if request.generation != self._current_generation() or not self.is_connected():
            return False, "verification_mismatch"
        refreshed = await self.synchronizer.run_arming_refresh()
        if not refreshed:
            return False, "verification_mismatch"
        expected = EXPECTED_ARMING_MODES.get(action, set())
        command = request.command
        operands = command.operands if command is not None else request.operands or {}
        selected = operands.get("partitions") if isinstance(operands, dict) else None
        partitions = (
            tuple(int(value) for value in selected)
            if isinstance(selected, (list, tuple)) and selected
            else (request.partition,)
        )
        for partition_number in partitions:
            partition = self.state.partitions.get(partition_number)
            raw_mode = partition.raw_mode if partition is not None else ""
            if raw_mode not in expected:
                return False, "verification_mismatch"
        # H/I telemetry proves the arming family but not the requested
        # subtype (the panel does not expose that distinction in this
        # snapshot). Never upgrade that partial evidence to "confirmed".
        subtype = operands.get("subtype") if isinstance(operands, dict) else None
        if subtype:
            return True, "acknowledged_unverified"
        return True, "confirmed"

    def _audit_command(self, request: ControlRequest) -> tuple[VistaCommand, str]:
        command = request.command
        sequence = request.command_sequence
        if request.interaction_id:
            with self._keypad_reservation_lock:
                sequence = self._interaction_sequences.get(
                    request.interaction_id, sequence
                )
        if request.kind == "keypad" and sequence:
            try:
                command = KeypadParser().parse(
                    sequence,
                    partition=request.partition,
                    source=request.source,
                    actor_id=request.actor_id,
                    actor_name=request.actor_name,
                    interaction_id=request.interaction_id,
                )
            except ValueError:
                command = VistaCommand(
                    command_type="unclassified_keypad_command",
                    partition=request.partition,
                    raw_sequence=sequence,
                    source=request.source,
                    actor_id=request.actor_id,
                    actor_name=request.actor_name,
                    interaction_id=request.interaction_id,
                    confidence="low",
                )
        if (
            command is not None
            and command.command_type in {
                "unclassified_keypad_command",
                "code_entry_ambiguous",
                "keypad_command",
            }
            and request.operands
        ):
            command = VistaCommand(
                command_type=command.command_type,
                partition=command.partition,
                code=command.code,
                operands=dict(request.operands),
                raw_sequence=command.raw_sequence,
                source=command.source,
                actor_id=command.actor_id,
                actor_name=command.actor_name,
                interaction_id=command.interaction_id,
                confidence=command.confidence,
            )
        if command is None:
            command = VistaCommand(
                command_type="unclassified_keypad_command",
                partition=request.partition,
                raw_sequence=sequence,
                source=request.source,
                actor_id=request.actor_id,
                actor_name=request.actor_name,
                interaction_id=request.interaction_id,
                confidence="low",
            )
        return command, sequence

    def _result(self, request: ControlRequest, ok: bool, status: str, **extra) -> None:
        command, logical_sequence = self._audit_command(request)
        verification = str(extra.get("verification", ""))
        payload = {
            "request_id": request.request_id,
            "ok": bool(ok),
            "kind": request.kind,
            "partition": request.partition,
            "status": status,
            **extra,
        }
        # The command model is safe to serialize without code or raw input.
        payload.update(
            {
                "command_type": command.command_type,
                "confidence": command.confidence,
                "execution_mechanism": (
                    request.plan.mechanism
                    if request.plan is not None
                    else ("keypad" if request.kind == "keypad" else "native")
                ),
            }
        )
        if request.kind == "keypad":
            payload["action"] = "keypress"
        payload.pop("code", None)
        payload.pop("command_sequence", None)
        payload.pop("raw_sequence", None)
        self.publish_result(payload)
        audit_interaction_id = request.audit_interaction_id or request.interaction_id
        if self.audit_result is not None and audit_interaction_id:
            audit = command.audit_fields()
            audit_payload = {
                "interaction_id": audit_interaction_id,
                "request_id": request.audit_request_id,
                "actor_id": request.actor_id,
                "actor_name": request.actor_name,
                "partition": request.partition,
                "source": request.source,
                "started_at": request.started_at,
                "action": (
                    audit["action"]
                    if audit["command_type"]
                    not in {"unclassified_keypad_command", "code_entry_ambiguous", "keypad_command"}
                    else request.action
                ),
                "command_sequence": logical_sequence,
                "operands": audit["operands"] or request.operands,
                "status": status,
                "ok": ok,
            }
            if (
                request.plan is not None
                or audit["command_type"]
                not in {"unclassified_keypad_command", "code_entry_ambiguous", "keypad_command"}
            ):
                audit_payload.update(
                    {
                        "logical_command_sequence": logical_sequence,
                        "command_type": audit["command_type"],
                        "code": audit["code"],
                        "execution_mechanism": (
                            request.plan.mechanism
                            if request.plan is not None
                            else ("keypad" if request.kind == "keypad" else "native")
                        ),
                        "confidence": audit["confidence"],
                        "verification": verification or status,
                    }
                )
            self.audit_result(audit_payload)
        if (
            request.kind == "keypad"
            and status not in {"queued"}
            and (request.interaction_complete or not ok)
        ):
            self._release_keypad_interaction(request.interaction_id)
            with self._keypad_reservation_lock:
                self._interaction_sequences.pop(request.interaction_id, None)
        elif request.kind == "command" and request.plan is not None:
            self._release_keypad_interaction(request.interaction_id)
            with self._keypad_reservation_lock:
                self._interaction_sequences.pop(request.interaction_id, None)
