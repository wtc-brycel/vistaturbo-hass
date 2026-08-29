from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
import logging
import queue
import threading

from .config import Settings
from .control import VistaControlCoordinator
from .event_store import EventStore
from .framing import RawFrame, VistaStreamFramer
from .message_handler import ProtocolMessageHandler
from .mqtt_client import MqttPublisher
from .printer import TransPortEventPrinter
from .protocol import identify_message, validate_packet
from .state import VistaState
from .synchronizer import VistaSynchronizer

LOG = logging.getLogger(__name__)


@dataclass(frozen=True)
class TxItem:
    source: str
    label: str
    data: bytes


class VistaBridge:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.state = VistaState()
        self.framer = VistaStreamFramer()
        self.printer = TransPortEventPrinter(settings)
        self.event_store = (
            EventStore(
                settings.event_history.sqlite_path,
                max_age_days=settings.event_history.max_age_days,
                max_rows=settings.event_history.max_rows,
            )
            if settings.event_history.enabled or settings.event_history.audit_enabled
            else None
        )
        self.rx_frames = 0
        self.rx_bytes = 0
        self.tx_frames = 0
        self.tx_bytes = 0
        self.invalid_frames = 0
        self._tx_queue: queue.Queue[TxItem] = queue.Queue(maxsize=settings.tx_queue_max)
        self._raw_tx_queue: queue.Queue[TxItem] = queue.Queue(
            maxsize=settings.raw_tx_queue_max
        )
        self._writer: asyncio.StreamWriter | None = None
        self._stop = asyncio.Event()
        self._panel_connected = threading.Event()
        self.synchronizer = VistaSynchronizer(
            settings.sync,
            settings.keypad,
            settings.event_history.enabled,
            settings.event_history.startup_dump_enabled,
            self._is_connected,
            self._send_sync_query,
            self._force_reconnect,
            self._on_query_start,
            self._on_snapshot_check,
        )
        self.control = VistaControlCoordinator(
            settings.control,
            self.state,
            self.synchronizer,
            self._is_connected,
            self._send_sync_query,
            self._publish_control_result,
            self._record_control_audit,
        )
        self.mqtt = MqttPublisher(
            settings,
            self.enqueue_raw_tx,
            self.enqueue_keypad_control,
            self.enqueue_alarm_control,
            self._record_control_audit,
        )
        self.handler = ProtocolMessageHandler(
            settings,
            self.state,
            self.mqtt,
            self.printer,
            self.synchronizer,
            self.event_store,
            self.control,
        )

    def _publish_control_result(self, payload: dict) -> None:
        self.mqtt.publish_json("control/result", payload, qos=1)

    def _record_control_audit(self, payload: dict) -> None:
        if self.event_store is None or not self.settings.event_history.audit_enabled:
            return
        interaction_id = str(payload.get("interaction_id", "")).strip()
        if not interaction_id:
            return
        self.event_store.record_keypad_interaction(
            interaction_id=interaction_id,
            observed_at=datetime.now(timezone.utc).isoformat(),
            started_at=str(payload.get("started_at", "")),
            actor_id=str(payload.get("actor_id", "")),
            actor_name=str(payload.get("actor_name", "")),
            partition=int(payload.get("partition", 0) or 0),
            source=str(payload.get("source", "mqtt")),
            action=str(payload.get("action", "keypad_sequence")),
            command_sequence=str(payload.get("command_sequence", "")),
            operands=(
                payload.get("operands")
                if isinstance(payload.get("operands"), dict)
                else None
            ),
            status=str(payload.get("status", "unknown")),
            ok=bool(payload.get("ok", False)),
            request_id=str(payload.get("request_id", "")),
        )

    def enqueue_keypad_control(
        self,
        partition: int,
        key: str,
        metadata: dict | None = None,
    ) -> tuple[bool, str]:
        return self.control.enqueue_keypad(partition, key, metadata)

    def enqueue_alarm_control(
        self,
        partition: int,
        action: str,
        code: str,
        metadata: dict | None = None,
    ) -> tuple[bool, str]:
        return self.control.enqueue_alarm(partition, action, code, metadata)

    def enqueue_raw_tx(self, data: bytes) -> tuple[bool, str]:
        return self._enqueue_tx(data, source="debug", label="raw")

    async def run(self) -> None:
        self.mqtt.start()
        background = [
            asyncio.create_task(self._metrics_loop(), name="metrics"),
            asyncio.create_task(self.control.run(self._stop), name="panel-control"),
            asyncio.create_task(self.printer.run(self._stop), name="transport-printer"),
        ]
        try:
            await self._connection_loop()
        finally:
            self._stop.set()
            for task in background:
                task.cancel()
            await asyncio.gather(*background, return_exceptions=True)
            self.mqtt.publish("panel/connected", "OFF", retain=True)
            self.mqtt.publish("panel/state_fresh", "OFF", retain=True, qos=1)
            self.mqtt.publish("panel/automation_available", "OFF", retain=True)
            self.mqtt.publish("panel/automation_availability_source", "offline", retain=True)
            self.mqtt.stop()

    async def _connection_loop(self) -> None:
        delay = self.settings.panel.reconnect_min_seconds
        while not self._stop.is_set():
            tasks: set[asyncio.Task] = set()
            try:
                reader, writer = await self._connect_panel()
                self._start_session(writer)
                delay = self.settings.panel.reconnect_min_seconds

                tasks.add(asyncio.create_task(self._read_loop(reader), name="panel-read"))
                tasks.add(asyncio.create_task(self._write_loop(writer), name="panel-write"))
                tasks.add(asyncio.create_task(self.synchronizer.resync_loop(), name="resync"))
                if self.settings.sync.startup_enabled:
                    tasks.add(
                        asyncio.create_task(self.synchronizer.startup(), name="startup-sync")
                    )
                if self.settings.sync.periodic_enabled:
                    tasks.add(
                        asyncio.create_task(
                            self.synchronizer.periodic_loop(),
                            name="periodic-sync",
                        )
                    )
                if self.settings.keypad.enabled:
                    tasks.add(
                        asyncio.create_task(
                            self.synchronizer.keypad_loop(),
                            name="keypad-display",
                        )
                    )

                done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_EXCEPTION)
                for task in done:
                    if task.cancelled():
                        continue
                    error = task.exception()
                    if error is not None:
                        raise error
            except asyncio.CancelledError:
                raise
            except asyncio.TimeoutError:
                LOG.warning(
                    "Panel TCP connect to %s:%s timed out after %ss",
                    self.settings.panel.host,
                    self.settings.panel.port,
                    self.settings.panel.connect_timeout_seconds,
                )
            except Exception as exc:
                LOG.warning(
                    "Panel connection lost/failed (%s): %s",
                    type(exc).__name__,
                    exc,
                )
            finally:
                await self._stop_session(tasks)

            if self._stop.is_set():
                return
            LOG.info("Reconnecting in %ss", delay)
            await asyncio.sleep(delay)
            delay = min(delay * 2, self.settings.panel.reconnect_max_seconds)

    async def _connect_panel(
        self,
    ) -> tuple[asyncio.StreamReader, asyncio.StreamWriter]:
        LOG.info(
            "Connecting to panel serial server at %s:%s",
            self.settings.panel.host,
            self.settings.panel.port,
        )
        return await asyncio.wait_for(
            asyncio.open_connection(self.settings.panel.host, self.settings.panel.port),
            timeout=self.settings.panel.connect_timeout_seconds,
        )

    def _start_session(self, writer: asyncio.StreamWriter) -> None:
        self._writer = writer
        self.framer = VistaStreamFramer()
        self.synchronizer.reset_connection_state()
        self.control.reset_session()
        self.state.reset_connection_derived_annunciators()
        self.mqtt.publish_alarm_states(self.state)
        self._panel_connected.set()
        LOG.info("Panel TCP connection established")
        self.mqtt.publish("panel/connected", "ON", retain=True)
        self.mqtt.publish("panel/state_fresh", "OFF", retain=True, qos=1)
        self.mqtt.publish("panel/automation_available", "OFF", retain=True)
        self.mqtt.publish("panel/automation_availability_source", "unknown", retain=True)
        self.handler.publish_event_history_snapshot()

    async def _stop_session(self, tasks: set[asyncio.Task]) -> None:
        self._panel_connected.clear()
        self.synchronizer.reset_connection_state()
        self.control.reset_session()
        self.state.reset_connection_derived_annunciators()
        for task in tasks:
            if not task.done():
                task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

        discarded = self._discard_pending_tx()
        if discarded:
            LOG.warning("Discarded %d pending TX request(s)", discarded)
        self.mqtt.publish("panel/connected", "OFF", retain=True)
        self.mqtt.publish("panel/state_fresh", "OFF", retain=True, qos=1)
        self.mqtt.publish("panel/automation_available", "OFF", retain=True)
        self.mqtt.publish("panel/automation_availability_source", "offline", retain=True)

        if self._writer is not None:
            self._writer.close()
            try:
                await self._writer.wait_closed()
            except Exception:
                pass
            self._writer = None

    def _is_connected(self) -> bool:
        return self._panel_connected.is_set()

    def _force_reconnect(self) -> None:
        if self._writer is not None:
            self._writer.close()

    def _send_sync_query(
        self,
        data: bytes,
        source: str,
        label: str,
    ) -> tuple[bool, str]:
        return self._enqueue_tx(data, source=source, label=label)

    def _enqueue_tx(
        self,
        data: bytes,
        *,
        source: str,
        label: str,
    ) -> tuple[bool, str]:
        if not self._is_connected():
            return False, "panel TCP connection is offline"
        if source == "debug" and (
            not isinstance(data, bytes) or not 1 <= len(data) <= 512
        ):
            return False, "invalid_raw_tx"
        if source == "debug" and self.synchronizer.is_active():
            return False, "panel synchronization is in progress"
        item = TxItem(source=source, label=label, data=data)
        raw_queue = getattr(self, "_raw_tx_queue", self._tx_queue)
        target = raw_queue if source == "debug" else self._tx_queue
        try:
            target.put_nowait(item)
        except queue.Full:
            reason = "raw_tx_queue_full" if source == "debug" else "tx_queue_full"
            LOG.warning("Rejected %s because its bounded TX queue is full", source)
            return False, reason
        return True, "queued for immediate transmit"

    def _discard_pending_tx(self) -> int:
        discarded = 0
        targets = (self._tx_queue, getattr(self, "_raw_tx_queue", self._tx_queue))
        for target in targets:
            while True:
                try:
                    target.get_nowait()
                    discarded += 1
                except queue.Empty:
                    break
        return discarded

    async def _read_loop(self, reader: asyncio.StreamReader) -> None:
        idle_seconds = self.settings.panel.frame_idle_ms / 1000
        while True:
            try:
                chunk = await asyncio.wait_for(reader.read(4096), timeout=idle_seconds)
            except asyncio.TimeoutError:
                self._flush_idle_frame()
                continue

            if not chunk:
                self._flush_idle_frame()
                raise ConnectionError("serial server closed TCP connection")

            self.rx_bytes += len(chunk)
            for frame in self.framer.feed(chunk):
                self._handle_frame(frame)

    def _flush_idle_frame(self) -> None:
        frame = self.framer.flush_idle()
        if frame is not None:
            self._handle_frame(frame)

    async def _write_loop(self, writer: asyncio.StreamWriter) -> None:
        while True:
            item = None
            for target in (self._tx_queue, self._raw_tx_queue):
                try:
                    item = target.get_nowait()
                    break
                except queue.Empty:
                    continue
            if item is None:
                await asyncio.sleep(0.05)
                continue

            writer.write(item.data)
            await writer.drain()
            self.tx_frames += 1
            self.tx_bytes += len(item.data)
            self._log_tx(item)

    def _log_tx(self, item: TxItem) -> None:
        if item.source == "debug":
            LOG.warning("RAW TX sent (%d bytes; payload redacted)", len(item.data))
            return
        if item.source == "control":
            LOG.info("TX control [%s] %d bytes (payload redacted)", item.label, len(item.data))
            return
        if self.settings.raw_logging:
            LOG.info(
                "TX %s [%s] %d bytes ASCII=%r HEX=%s",
                item.source,
                item.label,
                len(item.data),
                item.data.decode("ascii", errors="replace"),
                item.data.hex(" "),
            )
        else:
            LOG.info("TX %s [%s] %d bytes", item.source, item.label, len(item.data))

    def _handle_frame(self, frame: RawFrame) -> None:
        self.rx_frames += 1
        message_type = identify_message(frame.data)
        validation = validate_packet(frame.data)

        if not validation.valid:
            self.invalid_frames += 1
            self._log_invalid_frame(validation)
        if self.settings.raw_logging:
            LOG.info(
                "RX frame #%d [%s] type=%s valid=%s %d bytes ASCII=%r HEX=%s",
                self.rx_frames,
                frame.termination,
                message_type,
                validation.valid,
                len(frame.data),
                frame.ascii,
                frame.hex,
            )

        self._publish_raw_frame(frame, message_type, validation)
        if not validation.valid:
            return
        if message_type != "keypad_display":
            mark_protocol_message = getattr(
                self.synchronizer, "mark_protocol_message", None
            )
            if callable(mark_protocol_message):
                mark_protocol_message(message_type)
        if message_type == "ready":
            pending_kind = getattr(self.synchronizer, "pending_transaction_kind", None)
            transaction_kind = pending_kind() if callable(pending_kind) else None
            acknowledged = self.synchronizer.mark_ready()
            control = getattr(self, "control", None)
            if (
                acknowledged
                and transaction_kind == "control"
                and control is not None
                and control.infer_automation_available()
            ):
                LOG.info("VISTA automation interface inferred available from successful transaction")
                self.mqtt.publish("panel/automation_available", "ON", retain=True, qos=1)
                self.mqtt.publish("panel/automation_availability_source", "inferred", retain=True, qos=1)
        self.handler.handle(message_type, frame.data, frame.received_at)

    def _log_invalid_frame(self, validation) -> None:
        expected = (
            f"{validation.checksum_expected:02X}"
            if validation.checksum_expected is not None
            else None
        )
        received = (
            f"{validation.checksum_received:02X}"
            if validation.checksum_received is not None
            else None
        )
        LOG.warning(
            "Invalid VISTA packet #%d: length_ok=%s checksum_ok=%s declared=%s "
            "actual=%s checksum_expected=%s checksum_received=%s",
            self.rx_frames,
            validation.length_ok,
            validation.checksum_ok,
            validation.declared_length,
            validation.actual_length,
            expected,
            received,
        )

    def _publish_raw_frame(self, frame: RawFrame, message_type: str, validation) -> None:
        metadata = {
            "sequence": self.rx_frames,
            "received_at": frame.received_at,
            "termination": frame.termination,
            "message_type": message_type,
            "valid": validation.valid,
            "length_ok": validation.length_ok,
            "checksum_ok": validation.checksum_ok,
            "length": len(frame.data),
        }
        if getattr(self.settings, "raw_mqtt_enabled", False) and validation.valid:
            self.mqtt.publish_json(
                "raw/frame",
                {**metadata, "ascii": frame.ascii, "hex": frame.hex},
                qos=0,
            )
        self.mqtt.publish_json("raw/last_metadata", metadata, retain=True, qos=1)
        self.mqtt.publish("protocol/last_message_type", message_type, retain=True)

    def _on_query_start(self, query) -> None:
        self.state.begin_query_snapshot(query.name)
        self.mqtt.publish("panel/state_fresh", "OFF", retain=True, qos=1)

    def _on_snapshot_check(self) -> None:
        complete = self.state.mark_authoritative_snapshot()
        self.mqtt.publish(
            "panel/state_fresh", "ON" if complete else "OFF", retain=True, qos=1
        )
        if complete:
            self._publish_dynamic_state()
            self.mqtt.publish_alarm_states(self.state)

    def _publish_dynamic_state(self, *, include_discovery: bool = False) -> None:
        if include_discovery:
            self.handler.publish_event_history_snapshot()

        if self.state.arming_initialized:
            for partition in self.state.partitions.values():
                if include_discovery:
                    self.mqtt.publish_partition_discovery(partition.partition)
                self.mqtt.publish_partition_state(partition)

        for keypad in self.state.keypads.values():
            if not keypad.initialized or not keypad.session_fresh:
                continue
            if (
                not self.settings.keypad.enabled
                or keypad.partition not in self.settings.keypad.partitions
            ):
                continue
            if include_discovery:
                self.mqtt.publish_keypad_discovery(keypad.partition)
            self.mqtt.publish_keypad_state(keypad)

        if self.state.zone_snapshot_complete:
            for zone in self.state.zones.values():
                if not zone.partition:
                    continue
                if include_discovery:
                    self.mqtt.publish_zone_discovery(zone)
                self.mqtt.publish_zone_state(zone)

        if self.state.last_event is not None:
            self.mqtt.publish_event(
                self.state.last_event,
                emit_stream=False,
                received_at=self.handler.last_event_received_at or None,
                panel_clock_offset_seconds=self.handler.last_panel_clock_offset_seconds,
            )

    async def _metrics_loop(self) -> None:
        ticks = 0
        while True:
            self._publish_metrics()
            if ticks % 2 == 0:
                self._publish_dynamic_state(include_discovery=ticks % 12 == 0)
            ticks += 1
            await asyncio.sleep(5)

    def _publish_metrics(self) -> None:
        self.mqtt.publish(
            "panel/connected",
            "ON" if self._is_connected() else "OFF",
            retain=True,
        )
        metrics = {
            "stats/rx_frames": self.rx_frames,
            "stats/rx_bytes": self.rx_bytes,
            "stats/tx_frames": self.tx_frames,
            "stats/tx_bytes": self.tx_bytes,
            "stats/invalid_frames": self.invalid_frames,
            "stats/mqtt_publish_errors": self.mqtt.publish_errors,
            "sync/consecutive_failures": self.synchronizer.failures_consecutive,
            "sync/failures_total": self.synchronizer.failures_total,
        }
        for topic, value in metrics.items():
            self.mqtt.publish(topic, value, retain=True)

        if self.synchronizer.last_success_at:
            self.mqtt.publish(
                "sync/last_success",
                self.synchronizer.last_success_at,
                retain=True,
            )
        if self.handler.last_panel_clock_offset_seconds is not None:
            self.mqtt.publish(
                "panel/clock_offset_seconds",
                self.handler.last_panel_clock_offset_seconds,
                retain=True,
            )

        printer = self.printer.metrics
        printer_metrics = {
            "printer/status": printer.status,
            "printer/queue_depth": printer.queue_depth,
            "printer/completed": printer.completed,
            "printer/uncertain": printer.uncertain,
            "printer/failed": printer.failed,
            "printer/dropped": printer.dropped,
        }
        for topic, value in printer_metrics.items():
            self.mqtt.publish(topic, value, retain=True)
        if printer.last_error:
            self.mqtt.publish("printer/last_error", printer.last_error[:240], retain=True)
        if printer.last_completed_at:
            self.mqtt.publish(
                "printer/last_completed_at",
                printer.last_completed_at,
                retain=True,
            )
