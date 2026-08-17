from __future__ import annotations

import asyncio
from dataclasses import dataclass
import itertools
import logging
import queue
import threading
import time
from collections.abc import Callable

from .config import ControlSettings
from .protocol import build_keypad_stroke_command, build_native_alarm_command
from .state import VistaState
from .synchronizer import VistaSynchronizer

LOG = logging.getLogger(__name__)

SendQuery = Callable[[bytes, str, str], tuple[bool, str]]
BoolCallback = Callable[[], bool]
PublishResult = Callable[[dict], None]


@dataclass(frozen=True)
class ControlRequest:
    request_id: int
    kind: str
    partition: int
    value: str
    code: str
    generation: int
    enqueued_at: float


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
    ) -> None:
        self.settings = settings
        self.state = state
        self.synchronizer = synchronizer
        self.is_connected = is_connected
        self.send_query = send_query
        self.publish_result = publish_result
        self._queue: queue.Queue[ControlRequest] = queue.Queue(maxsize=64)
        self._automation_available = threading.Event()
        self._generation_lock = threading.Lock()
        self._generation = 0
        self._request_ids = itertools.count(1)

    def automation_available(self) -> bool:
        return self._automation_available.is_set()

    def set_automation_available(self, available: bool) -> None:
        if available:
            self._automation_available.set()
        else:
            self._automation_available.clear()
            self.discard_pending("automation_unavailable")

    def reset_session(self) -> int:
        with self._generation_lock:
            self._generation += 1
            generation = self._generation
        self._automation_available.clear()
        self.discard_pending("panel_session_reset")
        return generation

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
        if not self.is_connected():
            return False, "panel_offline"
        if not self.automation_available():
            return False, "automation_interface_unavailable"
        return True, "accepted"

    def enqueue_keypad(self, partition: int, key: str) -> tuple[bool, str]:
        ok, detail = self._preflight("keypad")
        if not ok:
            return ok, detail
        try:
            build_keypad_stroke_command(partition, [key])
        except ValueError as exc:
            return False, str(exc)
        return self._enqueue("keypad", partition, key, "")

    def enqueue_alarm(self, partition: int, action: str, code: str) -> tuple[bool, str]:
        ok, detail = self._preflight("alarm")
        if not ok:
            return ok, detail
        try:
            build_native_alarm_command(action, code, (partition,))
        except ValueError as exc:
            return False, str(exc)
        return self._enqueue("alarm", partition, str(action).upper(), str(code))

    def _enqueue(self, kind: str, partition: int, value: str, code: str) -> tuple[bool, str]:
        request = ControlRequest(
            request_id=next(self._request_ids),
            kind=kind,
            partition=partition,
            value=value,
            code=code,
            generation=self._current_generation(),
            enqueued_at=time.monotonic(),
        )
        try:
            self._queue.put_nowait(request)
        except queue.Full:
            return False, "control_queue_full"
        return True, "queued"

    async def run(self, stop_event: asyncio.Event) -> None:
        while not stop_event.is_set():
            if not await self.process_next():
                await asyncio.sleep(0.02)

    async def process_next(self) -> bool:
        try:
            request = self._queue.get_nowait()
        except queue.Empty:
            return False
        await self._process(request)
        return True

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

        if request.kind == "keypad":
            frame = build_keypad_stroke_command(request.partition, [request.value])
            label = f"keypad_p{request.partition}"
        else:
            frame = build_native_alarm_command(request.value, request.code, (request.partition,))
            label = f"{request.value.lower()}_p{request.partition}"

        async with self.synchronizer.lock:
            if request.generation != self._current_generation() or not self.is_connected():
                self._result(request, False, "stale_session")
                return
            if not self.automation_available():
                self._result(request, False, "automation_interface_unavailable")
                return
            self.synchronizer.begin_external_transaction()
            try:
                accepted, detail = self.send_query(frame, "control", label)
                if not accepted:
                    self._result(request, False, detail)
                    return
                if not await self.synchronizer.wait_ready(self.settings.response_timeout_seconds):
                    self._result(request, False, "no_ready_ack")
                    return
            finally:
                self.synchronizer.end_external_transaction()

        if self.settings.verify_delay_ms:
            await asyncio.sleep(self.settings.verify_delay_ms / 1000)
        if request.generation != self._current_generation() or not self.is_connected():
            self._result(request, False, "connection_lost_after_send")
            return

        if request.kind == "keypad":
            refreshed = await self.synchronizer.run_keypad_refresh(request.partition)
            self._result(
                request,
                True,
                "accepted",
                display_refreshed=bool(refreshed),
            )
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

    def _result(self, request: ControlRequest, ok: bool, status: str, **extra) -> None:
        payload = {
            "request_id": request.request_id,
            "ok": bool(ok),
            "kind": request.kind,
            "partition": request.partition,
            "status": status,
            **extra,
        }
        # Never publish a keypad digit or alarm credential in result telemetry.
        if request.kind == "keypad":
            payload["action"] = "keypress"
        self.publish_result(payload)
