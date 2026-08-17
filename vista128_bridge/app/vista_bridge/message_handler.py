from __future__ import annotations

import logging

from .config import Settings
from .control import VistaControlCoordinator
from .event_store import EventStore
from .mqtt_client import MqttPublisher
from .printer import TransPortEventPrinter, panel_clock_offset_seconds
from .protocol import (
    parse_arming_status,
    parse_event_log_entry,
    parse_keypad_display,
    parse_system_event,
    parse_zone_descriptor,
    parse_zone_partition,
    parse_zone_status,
)
from .state import VistaState
from .synchronizer import VistaSynchronizer

LOG = logging.getLogger(__name__)


class ProtocolMessageHandler:
    def __init__(
        self,
        settings: Settings,
        state: VistaState,
        mqtt: MqttPublisher,
        printer: TransPortEventPrinter,
        synchronizer: VistaSynchronizer,
        event_store: EventStore | None = None,
        control: VistaControlCoordinator | None = None,
    ) -> None:
        self.settings = settings
        self.state = state
        self.mqtt = mqtt
        self.printer = printer
        self.synchronizer = synchronizer
        self.event_store = event_store
        self.control = control
        self._history_dump_seen = 0
        self._history_dump_inserted = 0
        self._history_occurrences: dict[str, int] = {}
        self.last_panel_clock_offset_seconds: int | None = None
        self.last_event_received_at = ""
        self._handlers = {
            "communication_on": self._handle_communication_on,
            "communication_off": self._handle_communication_off,
            "display_changed": self._handle_display_changed,
            "event_log_entry": self._handle_event_log_entry,
            "event_log_complete": self._handle_event_log_complete,
            "arming_status": self._handle_arming_status,
            "zone_status": self._handle_zone_status,
            "zone_partition": self._handle_zone_partition,
            "zone_descriptor": self._handle_zone_descriptor,
            "keypad_display": self._handle_keypad_display,
            "system_event": self._handle_system_event,
        }

    def handle(self, message_type: str, data: bytes, received_at: str) -> None:
        handler = self._handlers.get(message_type)
        if handler is not None:
            handler(data, received_at)

    def _handle_communication_on(self, data: bytes, received_at: str) -> None:
        LOG.info("VISTA reported Communication On")
        self.mqtt.publish("panel/automation_available", "ON", retain=True, qos=1)
        if self.control is not None:
            self.control.set_automation_available(True)
        self.synchronizer.request_full_resync("communication_on")

    def _handle_communication_off(self, data: bytes, received_at: str) -> None:
        LOG.info("VISTA reported Communication Off")
        self.mqtt.publish("panel/automation_available", "OFF", retain=True, qos=1)
        if self.control is not None:
            self.control.set_automation_available(False)

    def _handle_display_changed(self, data: bytes, received_at: str) -> None:
        # Some Turbo integrations document DC display-change notifications, but
        # they have not been observed on the current VISTA-128BPT. Recognize and
        # log them passively before attempting any refresh semantics.
        LOG.info("VISTA reported Display Changed notification: %r", data)

    def _handle_event_log_entry(self, data: bytes, received_at: str) -> None:
        event = parse_event_log_entry(data)
        if event is None:
            return
        self._history_dump_seen += 1
        descriptor = self.state.zones.get(event.zone).descriptor if event.zone in self.state.zones else ""
        fingerprint = EventStore.fingerprint(event)
        occurrence = self._history_occurrences.get(fingerprint, 0) + 1
        self._history_occurrences[fingerprint] = occurrence
        if self.event_store is not None and self.event_store.record(
            event,
            source="history",
            received_at=received_at,
            descriptor=descriptor,
            occurrence=occurrence,
        ):
            self._history_dump_inserted += 1

    def _handle_event_log_complete(self, data: bytes, received_at: str) -> None:
        LOG.info(
            "Historical event-log dump complete: seen=%d inserted=%d",
            self._history_dump_seen,
            self._history_dump_inserted,
        )
        if self.event_store is not None:
            self.event_store.finish_history_dump(
                completed_at=received_at,
                seen=self._history_dump_seen,
                inserted=self._history_dump_inserted,
            )
        self.synchronizer.mark_event_log_complete()
        self.publish_event_history_snapshot()
        self._history_dump_seen = 0
        self._history_dump_inserted = 0
        self._history_occurrences.clear()

    def _handle_arming_status(self, data: bytes, received_at: str) -> None:
        report = parse_arming_status(data)
        if report is None:
            return
        self.state.apply_arming_status(report)
        LOG.info(
            "Decoded arming status: %s",
            " ".join(
                f"P{index}={mode}"
                for index, mode in enumerate(report.raw_modes, start=1)
            ),
        )
        for partition in self.state.partitions.values():
            self.mqtt.publish_partition_discovery(partition.partition)
            self.mqtt.publish_partition_state(partition)

    def _handle_zone_status(self, data: bytes, received_at: str) -> None:
        report = parse_zone_status(data)
        if report is None:
            return
        changed = self.state.apply_zone_status(report)
        start_zone = (report.block - 1) * 64 + 1
        LOG.info(
            "Decoded zone status block %d (zones %d-%d); %d changed",
            report.block,
            start_zone,
            start_zone + 63,
            len(changed),
        )
        for zone_number in changed:
            self._publish_zone(zone_number)
        for partition in self.state.partitions.values():
            self.mqtt.publish_partition_state(partition)
        self.mqtt.publish_zone_summaries(self.state)

    def _handle_zone_partition(self, data: bytes, received_at: str) -> None:
        report = parse_zone_partition(data)
        if report is None:
            return
        self.state.apply_zone_partition(report)
        start_zone = (report.block - 1) * 64 + 1
        end_zone = start_zone + 63
        assigned = [
            zone
            for zone in self.state.zones.values()
            if start_zone <= zone.zone <= end_zone and zone.partition
        ]
        LOG.info(
            "Decoded zone/partition block %d; %d assigned zones",
            report.block,
            len(assigned),
        )
        for zone in assigned:
            self.mqtt.publish_zone_discovery(zone)
            self.mqtt.publish_zone_state(zone)
        self.mqtt.publish_zone_summaries(self.state)

    def _handle_zone_descriptor(self, data: bytes, received_at: str) -> None:
        report = parse_zone_descriptor(data)
        if report is None:
            return
        if report.end:
            LOG.info("Zone descriptor synchronization complete")
            self.mqtt.publish_zone_summaries(self.state)
            self.synchronizer.mark_descriptor_complete()
            return
        if not self.state.set_descriptor(report.zone, report.descriptor):
            return
        zone = self.state.zones.get(report.zone)
        if zone is None or not zone.partition:
            return
        LOG.info("Zone %03d descriptor: %s", report.zone, report.descriptor)
        if self.event_store is not None:
            updated = self.event_store.update_descriptor(report.zone, report.descriptor)
            if updated:
                self.publish_event_history_snapshot()
        self.mqtt.publish_zone_discovery(zone)
        self.mqtt.publish_zone_state(zone)

    def _handle_keypad_display(self, data: bytes, received_at: str) -> None:
        report = parse_keypad_display(data)
        if report is None:
            return
        partition = self.synchronizer.active_keypad_partition()
        if partition is None:
            LOG.warning("Received keypad display without an active keypad query")
            return
        keypad = self.state.apply_keypad_display(partition, report, received_at)
        if keypad is None:
            return
        self.synchronizer.mark_keypad_response()
        LOG.info(
            "Decoded keypad display P%d: %r / %r LEDs=%X backlight=%s",
            partition,
            report.line_1,
            report.line_2,
            report.led_status,
            report.backlight,
        )
        self.mqtt.publish_keypad_discovery(partition)
        self.mqtt.publish_keypad_state(keypad)

    def _handle_system_event(self, data: bytes, received_at: str) -> None:
        event = parse_system_event(data)
        if event is None:
            return
        zone_before = self.state.zones.get(event.zone)
        zone_was_faulted = bool(zone_before and zone_before.faulted)
        changed_zones, changed_partitions = self.state.apply_system_event(event)
        LOG.info(
            "Decoded event %s (%s): zone=%03d user=%03d partition=%d panel_time=%s",
            event.code,
            event.description,
            event.zone,
            event.user,
            event.partition,
            event.panel_timestamp,
        )

        descriptor = self.state.zones.get(event.zone).descriptor if event.zone in self.state.zones else ""
        if self.event_store is not None:
            self.event_store.record(
                event, source="live", received_at=received_at, descriptor=descriptor
            )
            self.publish_event_history_snapshot()

        self.last_event_received_at = received_at
        self.last_panel_clock_offset_seconds = panel_clock_offset_seconds(
            event,
            received_at,
            self.settings.panel.timezone,
        )
        self.mqtt.publish_event(
            event,
            received_at=received_at,
            panel_clock_offset_seconds=self.last_panel_clock_offset_seconds,
        )
        self._handle_system_event_side_effects(event.code)
        self.synchronizer.request_keypad_refresh(event.partition)

        zone_after = self.state.zones.get(event.zone)
        resolved_partition = event.partition
        if resolved_partition not in self.state.partitions and zone_after is not None:
            resolved_partition = zone_after.partition
        partition_state = self.state.partitions.get(resolved_partition)
        should_chime = (
            event.code == "F5"
            and event.zone in self.settings.keypad.chime_zones
            and not zone_was_faulted
            and zone_after is not None
            and zone_after.faulted
            and self.state.arming_initialized
            and partition_state is not None
            and partition_state.raw_mode in {"D", "N"}
        )
        if should_chime:
            keypad = self.state.record_chime(resolved_partition, event.zone, received_at)
            if keypad is not None:
                LOG.info(
                    "Chime zone fault: zone=%03d partition=%d sequence=%d",
                    event.zone,
                    keypad.partition,
                    keypad.chime_sequence,
                )

        # Supplemental 6160CR-2 annunciators and configured chime events are
        # published immediately without waiting for the next KD poll.
        # Publish initialized keypad entities immediately so AC/fire/supervisory
        # changes are visible without waiting for the next KD polling interval.
        self._publish_initialized_keypads()

        self.printer.enqueue_event(
            event=event,
            descriptor=descriptor,
            received_at=received_at,
        )

        for zone_number in changed_zones:
            self._publish_zone(zone_number)
        if changed_zones:
            self.mqtt.publish_zone_summaries(self.state)
        for partition_number in changed_partitions:
            partition = self.state.partitions.get(partition_number)
            if partition is not None:
                self.mqtt.publish_partition_state(partition)

    def publish_event_history_snapshot(self) -> None:
        if self.event_store is None:
            return
        stats = self.event_store.stats()
        recent = self.event_store.recent(self.settings.event_history.recent_limit)
        self.mqtt.publish_event_history(
            count=stats.count,
            last_dump_at=stats.last_dump_at,
            last_dump_seen=stats.last_dump_seen,
            last_dump_inserted=stats.last_dump_inserted,
            events=recent,
        )

    def _handle_system_event_side_effects(self, code: str) -> None:
        if code == "AD":
            self.synchronizer.set_program_mode(True)
        elif code == "BD":
            self.synchronizer.set_program_mode(False)
            self.synchronizer.request_full_resync("program mode exit")
        elif code in {"0E", "3E"}:
            self.synchronizer.request_full_resync("panel power-up")

    def _publish_initialized_keypads(self) -> None:
        for keypad in self.state.keypads.values():
            if keypad.initialized:
                self.mqtt.publish_keypad_state(keypad)

    def _publish_zone(self, zone_number: int) -> None:
        zone = self.state.zones.get(zone_number)
        if zone is None or not zone.partition:
            return
        self.mqtt.publish_zone_discovery(zone)
        self.mqtt.publish_zone_state(zone)
