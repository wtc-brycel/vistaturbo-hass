from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .event_codes import EVENT_DESCRIPTIONS


@dataclass(frozen=True)
class ProtocolQuery:
    name: str
    data: bytes
    timeout_seconds: int | None = None
    required: bool = True
    partition: int | None = None


STARTUP_QUERIES: tuple[ProtocolQuery, ...] = (
    ProtocolQuery("arming_status", b"08as0064\r\n"),
    ProtocolQuery("zone_status", b"08zs004B\r\n"),
    ProtocolQuery("zone_partition", b"08ZP008E\r\n"),
    ProtocolQuery("zone_descriptor", b"08ZD009A\r\n", timeout_seconds=45, required=False),
)

STATE_SYNC_QUERIES: tuple[ProtocolQuery, ...] = STARTUP_QUERIES[:2]
EVENT_LOG_QUERY = ProtocolQuery(
    "event_log", b"08LD00A8\r\n", timeout_seconds=45, required=False
)

ARMING_STATUS_TO_HA = {
    "A": "armed_away",
    "H": "armed_home",
    "D": "disarmed",
    "N": "disarmed",
    "B": "armed_custom_bypass",
    "M": "armed_away",
    "I": "armed_night",
}

ARMING_STATUS_NAMES = {
    "A": "away",
    "H": "stay",
    "D": "disarmed",
    "N": "not_ready",
    "B": "bypassed",
    "M": "maximum",
    "I": "instant",
}


@dataclass(frozen=True)
class PacketValidation:
    valid: bool
    length_ok: bool
    checksum_ok: bool
    declared_length: int | None
    actual_length: int
    checksum_expected: int | None
    checksum_received: int | None


@dataclass(frozen=True)
class ArmingStatusReport:
    raw_modes: tuple[str, ...]


@dataclass(frozen=True)
class ZoneStatusReport:
    block: int
    statuses: tuple[int, ...]


@dataclass(frozen=True)
class ZonePartitionReport:
    block: int
    partitions: tuple[int, ...]


@dataclass(frozen=True)
class ZoneDescriptorReport:
    zone: int
    descriptor: str
    end: bool = False


@dataclass(frozen=True)
class KeypadDisplayReport:
    line_1: str
    line_2: str
    backlight: bool
    ready_led: bool
    trouble_led: bool
    armed_led: bool
    led_status: int
    raw_display: bytes


@dataclass(frozen=True)
class SystemEvent:
    code: str
    description: str
    zone: int
    user: int
    partition: int
    minute: int
    hour: int
    day: int
    month: int
    year: int

    @property
    def panel_timestamp(self) -> str | None:
        try:
            value = datetime(2000 + self.year, self.month, self.day, self.hour, self.minute)
        except ValueError:
            return None
        return value.isoformat(timespec="minutes")


def build_keypad_display_query(partition: int) -> ProtocolQuery:
    if partition < 1 or partition > 8:
        raise ValueError("keypad partition must be 1..8")
    prefix = f"09KD{partition}00".encode("ascii")
    checksum = (-sum(prefix)) & 0xFF
    data = prefix + f"{checksum:02X}\r\n".encode("ascii")
    return ProtocolQuery(
        name=f"keypad_display_p{partition}",
        data=data,
        partition=partition,
    )


def validate_packet(data: bytes) -> PacketValidation:
    """Validate packet length and checksum."""
    actual_length = len(data)
    declared_length: int | None = None
    checksum_received: int | None = None
    checksum_expected: int | None = None

    try:
        declared_length = int(data[:2].decode("ascii"), 16)
    except (ValueError, UnicodeDecodeError):
        pass

    try:
        checksum_received = int(data[-2:].decode("ascii"), 16)
        checksum_expected = (-sum(data[:-2])) & 0xFF
    except (ValueError, UnicodeDecodeError):
        pass

    length_ok = declared_length == actual_length if declared_length is not None else False
    checksum_ok = (
        checksum_received == checksum_expected
        if checksum_received is not None and checksum_expected is not None
        else False
    )
    return PacketValidation(
        valid=length_ok and checksum_ok,
        length_ok=length_ok,
        checksum_ok=checksum_ok,
        declared_length=declared_length,
        actual_length=actual_length,
        checksum_expected=checksum_expected,
        checksum_received=checksum_received,
    )


def identify_message(data: bytes) -> str:
    """Classify a VISTA packet."""
    if data.startswith(b"08OK"):
        return "ready"
    if data.startswith(b"08XN"):
        return "communication_on"
    if data.startswith(b"08XF"):
        return "communication_off"
    if data.startswith(b"10DC"):
        return "display_changed"
    if data.startswith(b"10AS"):
        return "arming_status"
    if data.startswith((b"49ZS", b"68ZS", b"69ZS")):
        return "zone_status"
    if data.startswith((b"49ZP", b"68ZP")):
        return "zone_partition"
    if len(data) >= 4 and data[2:4].lower() == b"zd":
        return "zone_descriptor"
    if len(data) >= 4 and data[2:4].lower() == b"kd":
        return "keypad_display"
    if data.startswith((b"1Bnq", b"14NQ")):
        return "system_event"
    if len(data) >= 4 and data[2:4].lower() == b"ld":
        return "event_log_entry"
    if len(data) >= 4 and data[2:4].lower() == b"lc":
        return "event_log_complete"
    if data.startswith(b"0AFV"):
        return "field_value"
    return "unknown"


def parse_arming_status(data: bytes) -> ArmingStatusReport | None:
    if not data.startswith(b"10AS") or len(data) < 16:
        return None
    modes = data[4:12].decode("ascii", errors="strict")
    if len(modes) != 8:
        return None
    return ArmingStatusReport(raw_modes=tuple(modes))


def _parse_block64(data: bytes, prefix: bytes) -> tuple[int, str] | None:
    if not data.startswith(prefix) or len(data) < 73:
        return None
    try:
        block = int(chr(data[4]))
        payload = data[5:69].decode("ascii")
    except (ValueError, UnicodeDecodeError):
        return None
    if block < 1 or block > 4 or len(payload) != 64:
        return None
    return block, payload


def parse_zone_status(data: bytes) -> ZoneStatusReport | None:
    parsed = _parse_block64(data, b"49ZS")
    if parsed is None:
        return None
    block, payload = parsed
    try:
        statuses = tuple(int(ch, 16) for ch in payload)
    except ValueError:
        return None
    return ZoneStatusReport(block=block, statuses=statuses)


def parse_zone_partition(data: bytes) -> ZonePartitionReport | None:
    parsed = _parse_block64(data, b"49ZP")
    if parsed is None:
        return None
    block, payload = parsed
    try:
        partitions = tuple(int(ch, 10) for ch in payload)
    except ValueError:
        return None
    if any(partition < 0 or partition > 8 for partition in partitions):
        return None
    return ZonePartitionReport(block=block, partitions=partitions)


def parse_zone_descriptor(data: bytes) -> ZoneDescriptorReport | None:
    if len(data) < 11 or data[2:4].lower() != b"zd":
        return None
    try:
        zone = int(data[4:7].decode("ascii"))
    except (ValueError, UnicodeDecodeError):
        return None

    body = data[7:-4]
    if len(body) < 2 or body[:1] != b'"' or body[-1:] != b'"':
        return None
    descriptor = body[1:-1].decode("ascii", errors="replace").strip()
    return ZoneDescriptorReport(
        zone=zone,
        descriptor=descriptor,
        end=zone == 0 and not descriptor,
    )


def parse_keypad_display(data: bytes) -> KeypadDisplayReport | None:
    if len(data) != 41 or data[2:4].lower() != b"kd":
        return None

    raw_display = data[4:36]
    display = bytearray(raw_display)
    backlight = bool(display[0] & 0x80)
    display[0] &= 0x7F
    try:
        led_status = int(chr(data[36]), 16)
        line_1 = bytes(display[:16]).decode("ascii", errors="strict")
        line_2 = bytes(display[16:32]).decode("ascii", errors="strict")
    except (ValueError, UnicodeDecodeError):
        return None

    return KeypadDisplayReport(
        line_1=line_1,
        line_2=line_2,
        backlight=backlight,
        ready_led=bool(led_status & 0x1),
        trouble_led=bool(led_status & 0x2),
        armed_led=bool(led_status & 0x4),
        led_status=led_status,
        raw_display=raw_display,
    )


def parse_event_log_entry(data: bytes) -> SystemEvent | None:
    if len(data) < 27 or data[2:4].lower() != b"ld":
        return None

    payload = data[4:-4].decode("ascii", errors="strict")
    if len(payload) != 19:
        return None

    code = payload[0:2]
    fields = (
        payload[2:5],
        payload[5:8],
        payload[8:9],
        payload[9:11],
        payload[11:13],
        payload[13:15],
        payload[15:17],
        payload[17:19],
    )
    try:
        zone, user, partition, minute, hour, day, month, year = map(int, fields)
    except ValueError:
        return None

    return SystemEvent(
        code=code,
        description=EVENT_DESCRIPTIONS.get(code, f"Event {code}"),
        zone=zone,
        user=user,
        partition=partition,
        minute=minute,
        hour=hour,
        day=day,
        month=month,
        year=year,
    )


def parse_system_event(data: bytes) -> SystemEvent | None:
    if not data.startswith(b"1Bnq"):
        return None
    if len(data) < 27:
        return None

    payload = data[4:-4].decode("ascii", errors="strict")
    if len(payload) != 19:
        return None

    code = payload[0:2]
    fields = (
        payload[2:5],
        payload[5:8],
        payload[8:9],
        payload[9:11],
        payload[11:13],
        payload[13:15],
        payload[15:17],
        payload[17:19],
    )
    try:
        zone, user, partition, minute, hour, day, month, year = map(int, fields)
    except ValueError:
        return None

    return SystemEvent(
        code=code,
        description=EVENT_DESCRIPTIONS.get(code, f"Event {code}"),
        zone=zone,
        user=user,
        partition=partition,
        minute=minute,
        hour=hour,
        day=day,
        month=month,
        year=year,
    )
