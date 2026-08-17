from __future__ import annotations

from dataclasses import dataclass, field

from .event_codes import (
    ALARM_RESTORE_TO_START,
    ALARM_START_CODES,
    AUXILIARY_RESTORE_TO_START,
    AUXILIARY_START_CODES,
    BURGLARY_RESTORE_TO_START,
    BURGLARY_START_CODES,
    DISARM_EVENT_CODES,
    ZONE_EVENT_TRANSITIONS,
)
from .protocol import (
    ARMING_STATUS_NAMES,
    ARMING_STATUS_TO_HA,
    ArmingStatusReport,
    KeypadDisplayReport,
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

# 6160CR-2 supplemental annunciators are not present in the KD LED bitfield.
# They are reconstructed from nq system events plus keypad-display reconciliation.
FIRE_ALARM_RESTORE_TO_START = {
    "02": "01",  # fire alarm restore
    "C2": "C1",  # smoke alarm restore
    "D2": "D1",  # waterflow restore
}
FIRE_ALARM_START_CODES = set(FIRE_ALARM_RESTORE_TO_START.values())

SUPERVISORY_RESTORE_TO_START = {
    "44": "43",  # supervisory restore
    "E2": "E1",  # fire supervisory restore
}
SUPERVISORY_START_CODES = set(SUPERVISORY_RESTORE_TO_START.values())

AC_POWER_EVENT_STATES = {
    "1B": False,  # AC loss
    "1C": True,   # AC restore
}

FIRE_DISPLAY_TOKENS = ("FIRE ALARM", "SMOKE ALARM", "WATERFLOW ALARM")
SUPERVISORY_DISPLAY_TOKENS = ("SUPERVISORY", "SUPV")
AC_LOSS_DISPLAY_TOKENS = ("AC LOSS", "AC FAIL")
SILENCED_DISPLAY_TOKENS = ("SILENCED", "SILENCE")
TROUBLE_DISPLAY_TOKENS = (
    "TROUBLE", "TRBL", "CHECK ", "LOW BAT", "FAIL TO COMM", "COMM FAIL", "BELL TROUBLE",
)

PARTITION_TROUBLE_RESTORE_TO_START = {
    "04": "03",
    "54": "53",
    "64": "63",
    "A2": "A1",
    "A4": "A3",
    "C4": "C3",
    "D4": "D3",
    "E4": "E3",
    "F4": "F3",
    "FE": "FD",
}
PARTITION_TROUBLE_START_CODES = set(PARTITION_TROUBLE_RESTORE_TO_START.values())
SYSTEM_BATTERY_EVENT_STATES = {"29": True, "2A": False}


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
    active_fire_tokens: set[str] = field(default_factory=set)
    active_supervisory_tokens: set[str] = field(default_factory=set)
    active_burglary_tokens: set[str] = field(default_factory=set)
    active_auxiliary_tokens: set[str] = field(default_factory=set)
    active_trouble_tokens: set[str] = field(default_factory=set)
    fire_silenced: bool = False

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

    @property
    def fire_alarm_active(self) -> bool:
        return bool(self.active_fire_tokens)

    @property
    def supervisory_active(self) -> bool:
        return bool(self.active_supervisory_tokens)

    @property
    def burglary_alarm_active(self) -> bool:
        return bool(self.active_burglary_tokens)

    @property
    def auxiliary_alarm_active(self) -> bool:
        return bool(self.active_auxiliary_tokens)

    def attributes(self) -> dict:
        return {
            "partition": self.partition,
            "vista_mode": self.vista_mode,
            "vista_mode_code": self.raw_mode,
            "ready": self.ready,
            "active_alarm_count": len(self.active_alarm_tokens),
            "fire_alarm_active": self.fire_alarm_active,
            "fire_silenced": self.fire_silenced,
            "supervisory_active": self.supervisory_active,
            "burglary_alarm_active": self.burglary_alarm_active,
            "auxiliary_alarm_active": self.auxiliary_alarm_active,
        }


@dataclass
class KeypadState:
    partition: int
    initialized: bool = False
    line_1: str = ""
    line_2: str = ""
    backlight: bool = False
    ready_led: bool = False
    trouble_led: bool = False
    trouble_led_raw: bool = False
    armed_led: bool = False
    power_led: bool | None = None
    fire_alarm_led: bool | None = None
    silenced_led: bool | None = None
    supervisory_led: bool | None = None
    burglary_alarm_led: bool | None = None
    auxiliary_alarm_led: bool | None = None
    chime_sequence: int = 0
    chime_zone: int | None = None
    chime_descriptor: str = ""
    chime_at: str = ""
    led_status: int = 0
    raw_display: bytes = b""
    updated_at: str = ""

    @property
    def ha_state(self) -> str:
        lines = [line.rstrip() for line in (self.line_1, self.line_2)]
        return " | ".join(line for line in lines if line) or "blank"

    @property
    def sound_mode(self) -> str:
        if self.fire_alarm_led is True and self.silenced_led is not True:
            return "fire"
        if self.burglary_alarm_led is True:
            return "burglary"
        if self.auxiliary_alarm_led is True:
            return "auxiliary"
        if any(
            value is None
            for value in (
                self.fire_alarm_led,
                self.burglary_alarm_led,
                self.auxiliary_alarm_led,
            )
        ):
            return "unknown"
        return "none"

    def attributes(self) -> dict:
        return {
            "partition": self.partition,
            "line_1": self.line_1,
            "line_2": self.line_2,
            "display": f"{self.line_1}\n{self.line_2}",
            "ready": self.ready_led,
            "trouble": self.trouble_led,
            "trouble_led_raw": self.trouble_led_raw,
            "armed": self.armed_led,
            "power": self.power_led,
            "fire_alarm": self.fire_alarm_led,
            "silenced": self.silenced_led,
            "supervisory": self.supervisory_led,
            "burglary_alarm": self.burglary_alarm_led,
            "auxiliary_alarm": self.auxiliary_alarm_led,
            "sound_mode": self.sound_mode,
            "chime_sequence": self.chime_sequence,
            "chime_zone": self.chime_zone,
            "chime_descriptor": self.chime_descriptor,
            "chime_at": self.chime_at,
            "backlight": self.backlight,
            "led_status": f"{self.led_status:X}",
            "raw_display_hex": self.raw_display.hex(" "),
            "updated_at": self.updated_at,
        }


class VistaState:
    def __init__(self) -> None:
        self.partitions = {
            partition: PartitionState(partition) for partition in range(1, 9)
        }
        self.keypads = {partition: KeypadState(partition) for partition in range(1, 9)}
        self.zones = {zone: ZoneState(zone) for zone in range(1, 129)}
        self.last_event: SystemEvent | None = None
        self.ac_power: bool | None = None
        self.system_battery_low: bool | None = None
        self.active_global_trouble_tokens: set[str] = set()
        self.arming_initialized = False
        self.zone_status_initialized = False
        self.zone_partition_initialized = False

    def reset_connection_derived_annunciators(self) -> None:
        self.ac_power = None
        self.system_battery_low = None
        self.active_global_trouble_tokens.clear()
        for partition in self.partitions.values():
            partition.active_fire_tokens.clear()
            partition.active_supervisory_tokens.clear()
            partition.active_burglary_tokens.clear()
            partition.active_auxiliary_tokens.clear()
            partition.active_trouble_tokens.clear()
            partition.fire_silenced = False
        for keypad in self.keypads.values():
            keypad.power_led = None
            keypad.fire_alarm_led = None
            keypad.silenced_led = None
            keypad.supervisory_led = None
            keypad.burglary_alarm_led = None
            keypad.auxiliary_alarm_led = None

    def record_chime(self, partition: int, zone_number: int, received_at: str) -> KeypadState | None:
        zone = self.zones.get(zone_number)
        resolved_partition = partition if partition in self.keypads else 0
        if not resolved_partition and zone is not None:
            resolved_partition = zone.partition
        keypad = self.keypads.get(resolved_partition)
        if keypad is None:
            return None
        keypad.chime_sequence += 1
        keypad.chime_zone = zone_number
        keypad.chime_descriptor = zone.descriptor if zone is not None else ""
        keypad.chime_at = received_at
        return keypad

    def assigned_zones_with(self, attribute: str) -> list[ZoneState]:
        if attribute not in ZONE_STATUS_BITS:
            raise ValueError(f"{attribute} is not a zone-status condition")
        return [
            zone
            for zone in self.zones.values()
            if zone.partition and getattr(zone, attribute)
        ]

    def apply_arming_status(self, report: ArmingStatusReport) -> set[int]:
        self.arming_initialized = True
        changed: set[int] = set()
        for partition_number, raw_mode in enumerate(report.raw_modes, start=1):
            partition = self.partitions[partition_number]
            if partition.raw_mode != raw_mode:
                partition.raw_mode = raw_mode
                changed.add(partition_number)
            if raw_mode in {"D", "N"} and partition.active_alarm_tokens:
                partition.active_alarm_tokens.clear()
                changed.add(partition_number)
        return changed

    def apply_keypad_display(
        self,
        partition: int,
        report: KeypadDisplayReport,
        received_at: str,
    ) -> KeypadState | None:
        keypad = self.keypads.get(partition)
        partition_state = self.partitions.get(partition)
        if keypad is None or partition_state is None:
            return None

        keypad.initialized = True
        keypad.line_1 = report.line_1
        keypad.line_2 = report.line_2
        keypad.backlight = report.backlight
        keypad.ready_led = report.ready_led
        keypad.trouble_led_raw = report.trouble_led
        keypad.armed_led = report.armed_led
        keypad.led_status = report.led_status
        keypad.raw_display = report.raw_display
        keypad.updated_at = received_at

        display = f"{report.line_1} {report.line_2}".upper()

        # AC is panel-global. A displayed AC failure is definitive. Conversely, a
        # keypad with no TROUBLE LED cannot currently be in AC-loss trouble, so it
        # gives us a safe startup reconciliation path for the POWER annunciator.
        if self._contains_any(display, AC_LOSS_DISPLAY_TOKENS):
            self._set_ac_power(False)
        keypad.power_led = self.ac_power

        explicit_fire = self._contains_any(display, FIRE_DISPLAY_TOKENS)
        explicit_supervisory = self._contains_any(display, SUPERVISORY_DISPLAY_TOKENS)
        explicit_silenced = self._contains_any(display, SILENCED_DISPLAY_TOKENS)
        normal_ready = report.ready_led and not report.trouble_led and not explicit_fire and not explicit_supervisory

        if partition_state.fire_alarm_active or explicit_fire:
            keypad.fire_alarm_led = True
        elif keypad.fire_alarm_led is True:
            # With all initiating fire events restored, a later non-fire KD is reset/
            # normalization evidence. Burglary READY is intentionally not required.
            keypad.fire_alarm_led = False
            partition_state.fire_silenced = False
        elif normal_ready:
            keypad.fire_alarm_led = False
            partition_state.fire_silenced = False

        if explicit_silenced and keypad.fire_alarm_led is not False:
            partition_state.fire_silenced = True
            keypad.silenced_led = True
        elif keypad.fire_alarm_led is False:
            partition_state.fire_silenced = False
            keypad.silenced_led = False
        elif partition_state.fire_silenced:
            keypad.silenced_led = True

        if partition_state.supervisory_active or explicit_supervisory:
            keypad.supervisory_led = True
        elif normal_ready:
            keypad.supervisory_led = False

        if partition_state.burglary_alarm_active:
            keypad.burglary_alarm_led = True
        elif normal_ready:
            keypad.burglary_alarm_led = False

        if partition_state.auxiliary_alarm_active:
            keypad.auxiliary_alarm_led = True
        elif normal_ready:
            keypad.auxiliary_alarm_led = False

        self._reconcile_keypad_trouble(partition)
        return keypad

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
        self._reconcile_all_keypad_trouble()
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
        self._apply_cr2_annunciator_event(event, changed_partitions)
        self._apply_audible_alarm_event(event, changed_partitions)
        self._apply_trouble_event(event, changed_partitions)
        self._reconcile_all_keypad_trouble()
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

    def _apply_cr2_annunciator_event(
        self,
        event: SystemEvent,
        changed_partitions: set[int],
    ) -> None:
        power_state = AC_POWER_EVENT_STATES.get(event.code)
        if power_state is not None:
            self._set_ac_power(power_state)

        partition = self.partitions.get(event.partition)
        keypad = self.keypads.get(event.partition)
        if partition is None:
            return

        token_prefix = f"{event.zone:03d}:"

        if event.code in FIRE_ALARM_START_CODES:
            token = token_prefix + event.code
            if token not in partition.active_fire_tokens:
                partition.active_fire_tokens.add(token)
                changed_partitions.add(event.partition)
            partition.fire_silenced = False
            if keypad is not None:
                keypad.fire_alarm_led = True
                keypad.silenced_led = False

        fire_start = FIRE_ALARM_RESTORE_TO_START.get(event.code)
        if fire_start is not None:
            token = token_prefix + fire_start
            if token in partition.active_fire_tokens:
                partition.active_fire_tokens.remove(token)
                changed_partitions.add(event.partition)
            # Do not extinguish FIRE ALARM here. The CR-2 fire indication is
            # intentionally latched until a subsequent normal/reset keypad display.

        if event.code in SUPERVISORY_START_CODES:
            token = token_prefix + event.code
            if token not in partition.active_supervisory_tokens:
                partition.active_supervisory_tokens.add(token)
                changed_partitions.add(event.partition)
            if keypad is not None:
                keypad.supervisory_led = True

        supervisory_start = SUPERVISORY_RESTORE_TO_START.get(event.code)
        if supervisory_start is not None:
            token = token_prefix + supervisory_start
            if token in partition.active_supervisory_tokens:
                partition.active_supervisory_tokens.remove(token)
                changed_partitions.add(event.partition)
            if keypad is not None and not partition.active_supervisory_tokens:
                keypad.supervisory_led = False

    def _apply_audible_alarm_event(
        self,
        event: SystemEvent,
        changed_partitions: set[int],
    ) -> None:
        partition = self.partitions.get(event.partition)
        keypad = self.keypads.get(event.partition)
        if partition is None:
            return

        token_prefix = f"{event.zone:03d}:"

        if event.code in BURGLARY_START_CODES:
            token = token_prefix + event.code
            if token not in partition.active_burglary_tokens:
                partition.active_burglary_tokens.add(token)
                changed_partitions.add(event.partition)
            if keypad is not None:
                keypad.burglary_alarm_led = True

        burglary_start = BURGLARY_RESTORE_TO_START.get(event.code)
        if burglary_start is not None:
            token = token_prefix + burglary_start
            if token in partition.active_burglary_tokens:
                partition.active_burglary_tokens.remove(token)
                changed_partitions.add(event.partition)
            if keypad is not None and not partition.active_burglary_tokens:
                keypad.burglary_alarm_led = False

        if event.code in AUXILIARY_START_CODES:
            token = token_prefix + event.code
            if token not in partition.active_auxiliary_tokens:
                partition.active_auxiliary_tokens.add(token)
                changed_partitions.add(event.partition)
            if keypad is not None:
                keypad.auxiliary_alarm_led = True

        auxiliary_start = AUXILIARY_RESTORE_TO_START.get(event.code)
        if auxiliary_start is not None:
            token = token_prefix + auxiliary_start
            if token in partition.active_auxiliary_tokens:
                partition.active_auxiliary_tokens.remove(token)
                changed_partitions.add(event.partition)
            if keypad is not None and not partition.active_auxiliary_tokens:
                keypad.auxiliary_alarm_led = False

        if event.code in DISARM_EVENT_CODES:
            if partition.active_burglary_tokens:
                partition.active_burglary_tokens.clear()
                changed_partitions.add(event.partition)
            if keypad is not None:
                keypad.burglary_alarm_led = False

    def _apply_trouble_event(self, event: SystemEvent, changed_partitions: set[int]) -> None:
        battery_state = SYSTEM_BATTERY_EVENT_STATES.get(event.code)
        if battery_state is not None:
            self.system_battery_low = battery_state

        start_code = None
        if event.code in PARTITION_TROUBLE_START_CODES:
            start_code = event.code
            adding = True
        else:
            start_code = PARTITION_TROUBLE_RESTORE_TO_START.get(event.code)
            adding = False
        if start_code is None:
            return

        token = f"{event.zone:03d}:{start_code}"
        partition = self.partitions.get(event.partition)
        tokens = partition.active_trouble_tokens if partition is not None else self.active_global_trouble_tokens
        before = token in tokens
        if adding:
            tokens.add(token)
        else:
            tokens.discard(token)
        if partition is not None and before != (token in tokens):
            changed_partitions.add(event.partition)

    def _partition_has_known_trouble(self, partition_number: int) -> bool:
        if self.ac_power is False or self.system_battery_low is True or self.active_global_trouble_tokens:
            return True
        partition = self.partitions.get(partition_number)
        if partition is not None and partition.active_trouble_tokens:
            return True
        return any(
            zone.partition == partition_number and (zone.trouble or zone.low_battery or zone.tamper)
            for zone in self.zones.values()
        )

    def _reconcile_keypad_trouble(self, partition_number: int) -> None:
        keypad = self.keypads.get(partition_number)
        if keypad is None or not keypad.initialized:
            return
        display = f"{keypad.line_1} {keypad.line_2}".upper()
        explicit = keypad.trouble_led_raw or self._contains_any(display, TROUBLE_DISPLAY_TOKENS)
        keypad.trouble_led = bool(explicit or self._partition_has_known_trouble(partition_number))

    def _reconcile_all_keypad_trouble(self) -> None:
        for partition_number in self.keypads:
            self._reconcile_keypad_trouble(partition_number)

    def _set_ac_power(self, value: bool) -> None:
        self.ac_power = value
        for keypad in self.keypads.values():
            keypad.power_led = value
        self._reconcile_all_keypad_trouble()

    @staticmethod
    def _contains_any(text: str, tokens: tuple[str, ...]) -> bool:
        return any(token in text for token in tokens)

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
