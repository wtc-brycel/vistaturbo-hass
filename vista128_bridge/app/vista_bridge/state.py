from __future__ import annotations

from dataclasses import dataclass, field
from .event_codes import (
    ALARM_RESTORE_TO_START,
    ALARM_START_CODES,
    DISARM_EVENT_CODES,
    ZONE_EVENT_TRANSITIONS,
)
from .protocol import (
    ARMING_STATUS_NAMES,
    ARMING_STATUS_TO_HA,
    ArmingStatusReport,
    SystemEvent,
    ZonePartitionReport,
    ZoneStatusReport,
)

ZONE_STATUS_BITS = {
    "faulted": 0x1,
    "trouble": 0x2,
    "alarm": 0x4,
    "bypassed": 0x8,
}

ARM_EVENT_MODES = {
    "B7": "H",
    "47": "H",
    "07": "A",
    "17": "A",
    "37": "A",
}


@dataclass
class ZoneState:
    zone: int
    partition: int = 0
    descriptor: str = ""
    faulted: bool = False
    trouble: bool = False
    alarm: bool = False
    bypassed: bool = False
    low_battery: bool = False
    tamper: bool = False
    raw_status: int = 0

    @property
    def active(self) -> bool:
        return self.faulted or self.alarm

    @property
    def name(self) -> str:
        return self.descriptor or f"Zone {self.zone:03d}"

    def attributes(self) -> dict:
        return {
            "zone": self.zone,
            "partition": self.partition,
            "descriptor": self.descriptor,
            "faulted": self.faulted,
            "trouble": self.trouble,
            "alarm": self.alarm,
            "bypassed": self.bypassed,
            "low_battery": self.low_battery,
            "tamper": self.tamper,
            "raw_status": f"{self.raw_status:X}",
        }


@dataclass
class PartitionState:
    partition: int
    raw_mode: str = "D"
    active_alarm_tokens: set[str] = field(default_factory=set)

    @property
    def vista_mode(self) -> str:
        return ARMING_STATUS_NAMES.get(self.raw_mode, "unknown")

    @property
    def ready(self) -> bool:
        return self.raw_mode != "N"

    @property
    def base_ha_state(self) -> str:
        return ARMING_STATUS_TO_HA.get(self.raw_mode, "disarmed")

    @property
    def ha_state(self) -> str:
        return "triggered" if self.active_alarm_tokens else self.base_ha_state

    def attributes(self) -> dict:
        return {
            "partition": self.partition,
            "vista_mode": self.vista_mode,
            "vista_mode_code": self.raw_mode,
            "ready": self.ready,
            "active_alarm_count": len(self.active_alarm_tokens),
            "control_enabled": False,
        }


class VistaState:
    def __init__(self) -> None:
        self.partitions = {
            partition: PartitionState(partition) for partition in range(1, 9)
        }
        self.zones = {zone: ZoneState(zone) for zone in range(1, 129)}
        self.last_event: SystemEvent | None = None
        self.arming_initialized = False
        self.zone_status_initialized = False
        self.zone_partition_initialized = False

    def apply_arming_status(self, report: ArmingStatusReport) -> set[int]:
        self.arming_initialized = True
        changed: set[int] = set()
        for partition_number, raw_mode in enumerate(report.raw_modes, start=1):
            partition = self.partitions[partition_number]
            if partition.raw_mode != raw_mode:
                partition.raw_mode = raw_mode
                changed.add(partition_number)
            if raw_mode == "D" and partition.active_alarm_tokens:
                partition.active_alarm_tokens.clear()
                changed.add(partition_number)
        return changed

    def apply_zone_status(self, report: ZoneStatusReport) -> set[int]:
        self.zone_status_initialized = True
        changed: set[int] = set()
        start_zone = (report.block - 1) * 64 + 1
        for offset, raw_status in enumerate(report.statuses):
            zone_number = start_zone + offset
            zone = self.zones.get(zone_number)
            if zone is None:
                continue
            if zone.raw_status != raw_status:
                zone.raw_status = raw_status
                changed.add(zone_number)
            for attribute, bit in ZONE_STATUS_BITS.items():
                value = bool(raw_status & bit)
                if getattr(zone, attribute) != value:
                    setattr(zone, attribute, value)
                    changed.add(zone_number)
        self._reconcile_partition_zone_alarms()
        return changed

    def apply_zone_partition(self, report: ZonePartitionReport) -> set[int]:
        self.zone_partition_initialized = True
        changed: set[int] = set()
        start_zone = (report.block - 1) * 64 + 1
        for offset, partition_number in enumerate(report.partitions):
            zone_number = start_zone + offset
            zone = self.zones.get(zone_number)
            if zone is None or zone.partition == partition_number:
                continue
            zone.partition = partition_number
            changed.add(zone_number)
        self._reconcile_partition_zone_alarms()
        return changed

    def set_descriptor(self, zone_number: int, descriptor: str) -> bool:
        zone = self.zones.get(zone_number)
        if zone is None or zone.descriptor == descriptor:
            return False
        zone.descriptor = descriptor
        return True

    def apply_system_event(self, event: SystemEvent) -> tuple[set[int], set[int]]:
        self.last_event = event
        changed_zones: set[int] = set()
        changed_partitions: set[int] = set()

        self._apply_zone_transition(event, changed_zones)
        self._apply_partition_event(event, changed_zones, changed_partitions)
        return changed_zones, changed_partitions

    def _apply_zone_transition(self, event: SystemEvent, changed: set[int]) -> None:
        transition = ZONE_EVENT_TRANSITIONS.get(event.code)
        zone = self.zones.get(event.zone)
        if transition is None or zone is None:
            return
        attribute, value = transition
        if self._set_zone_flag(zone, attribute, value):
            changed.add(event.zone)

    def _apply_partition_event(
        self,
        event: SystemEvent,
        changed_zones: set[int],
        changed_partitions: set[int],
    ) -> None:
        partition = self.partitions.get(event.partition)
        if partition is None:
            return

        new_mode = ARM_EVENT_MODES.get(event.code)
        if event.code in DISARM_EVENT_CODES:
            new_mode = "D"
        if new_mode is not None and partition.raw_mode != new_mode:
            partition.raw_mode = new_mode
            self.arming_initialized = True
            changed_partitions.add(event.partition)

        self._apply_alarm_event(event, partition, changed_zones, changed_partitions)
        if event.code in DISARM_EVENT_CODES and partition.active_alarm_tokens:
            partition.active_alarm_tokens.clear()
            changed_partitions.add(event.partition)

    def _apply_alarm_event(
        self,
        event: SystemEvent,
        partition: PartitionState,
        changed_zones: set[int],
        changed_partitions: set[int],
    ) -> None:
        token_prefix = f"{event.zone:03d}:"
        if event.code in ALARM_START_CODES:
            token = token_prefix + event.code
            if token not in partition.active_alarm_tokens:
                partition.active_alarm_tokens.add(token)
                changed_partitions.add(event.partition)
            self._set_event_zone_alarm(event.zone, True, changed_zones)
            return

        start_code = ALARM_RESTORE_TO_START.get(event.code)
        if start_code is None:
            return
        token = token_prefix + start_code
        if token in partition.active_alarm_tokens:
            partition.active_alarm_tokens.remove(token)
            changed_partitions.add(event.partition)
        self._set_event_zone_alarm(event.zone, False, changed_zones)

    def _set_event_zone_alarm(
        self,
        zone_number: int,
        value: bool,
        changed: set[int],
    ) -> None:
        zone = self.zones.get(zone_number)
        if zone is not None and self._set_zone_flag(zone, "alarm", value):
            changed.add(zone_number)

    @staticmethod
    def _set_zone_flag(zone: ZoneState, attribute: str, value: bool) -> bool:
        if getattr(zone, attribute) == value:
            return False
        setattr(zone, attribute, value)
        bit = ZONE_STATUS_BITS.get(attribute)
        if bit is not None:
            zone.raw_status = (zone.raw_status | bit) if value else (zone.raw_status & ~bit)
        return True

    def _reconcile_partition_zone_alarms(self) -> None:
        for zone in self.zones.values():
            partition = self.partitions.get(zone.partition)
            if partition is None:
                continue
            token = f"zone-status:{zone.zone:03d}"
            if zone.alarm:
                partition.active_alarm_tokens.add(token)
            else:
                partition.active_alarm_tokens.discard(token)
