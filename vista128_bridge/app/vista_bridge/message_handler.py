from __future__ import annotations

import logging

from .config import Settings
from .mqtt_client import MqttPublisher
from .printer import TransPortEventPrinter, panel_clock_offset_seconds
from .protocol import (
    parse_arming_status,
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
    ) -> None:
        self.settings = settings
        self.state = state
        self.mqtt = mqtt
        self.printer = printer
        self.synchronizer = synchronizer
        self.last_panel_clock_offset_seconds: int | None = None
        self.last_event_received_at = ""
        self._handlers = {
            "communication_on": self._handle_communication_on,
            "arming_status": self._handle_arming_status,
            "zone_status": self._handle_zone_status,
            "zone_partition": self._handle_zone_partition,
            "zone_descriptor": self._handle_zone_descriptor,
            "system_event": self._handle_system_event,
        }

    def handle(self, message_type: str, data: bytes, received_at: str) -> None:
        handler = self._handlers.get(message_type)
        if handler is not None:
            handler(data, received_at)

    def _handle_communication_on(self, data: bytes, received_at: str) -> None:
        LOG.info("VISTA reported Communication On")
        self.synchronizer.request_full_resync("communication_on")

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

    def _handle_zone_descriptor(self, data: bytes, received_at: str) -> None:
        report = parse_zone_descriptor(data)
        if report is None:
            return
        if report.end:
            LOG.info("Zone descriptor synchronization complete")
            self.synchronizer.mark_descriptor_complete()
            return
        if not self.state.set_descriptor(report.zone, report.descriptor):
            return
        zone = self.state.zones.get(report.zone)
        if zone is None or not zone.partition:
            return
        LOG.info("Zone %03d descriptor: %s", report.zone, report.descriptor)
        self.mqtt.publish_zone_discovery(zone)
        self.mqtt.publish_zone_state(zone)

    def _handle_system_event(self, data: bytes, received_at: str) -> None:
        event = parse_system_event(data)
        if event is None:
            return
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

        descriptor = ""
        if event.zone in self.state.zones:
            descriptor = self.state.zones[event.zone].descriptor
        self.printer.enqueue_event(
            event=event,
            descriptor=descriptor,
            received_at=received_at,
        )

        for zone_number in changed_zones:
            self._publish_zone(zone_number)
        for partition_number in changed_partitions:
            partition = self.state.partitions.get(partition_number)
            if partition is not None:
                self.mqtt.publish_partition_state(partition)

    def _handle_system_event_side_effects(self, code: str) -> None:
        if code == "AD":
            self.synchronizer.set_program_mode(True)
        elif code == "BD":
            self.synchronizer.set_program_mode(False)
            self.synchronizer.request_full_resync("program mode exit")
        elif code in {"0E", "3E"}:
            self.synchronizer.request_full_resync("panel power-up")

    def _publish_zone(self, zone_number: int) -> None:
        zone = self.state.zones.get(zone_number)
        if zone is None or not zone.partition:
            return
        self.mqtt.publish_zone_discovery(zone)
        self.mqtt.publish_zone_state(zone)
