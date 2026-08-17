from __future__ import annotations

from dataclasses import dataclass
import os


def _bool_env(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _partition_list(value: str) -> tuple[int, ...]:
    partitions = tuple(
        sorted({int(item.strip()) for item in value.split(",") if item.strip()})
    )
    if not partitions or any(partition < 1 or partition > 8 for partition in partitions):
        raise ValueError("keypad_partitions must contain partition numbers 1..8")
    return partitions


def _zone_list(value: str) -> tuple[int, ...]:
    zones: set[int] = set()
    for item in value.split(","):
        token = item.strip()
        if not token:
            continue
        if "-" in token:
            start_text, end_text = token.split("-", 1)
            start = int(start_text.strip())
            end = int(end_text.strip())
            if end < start:
                raise ValueError("chime_zones ranges must be ascending")
            zones.update(range(start, end + 1))
        else:
            zones.add(int(token))
    if any(zone < 1 or zone > 128 for zone in zones):
        raise ValueError("chime_zones must contain zone numbers 1..128")
    return tuple(sorted(zones))


@dataclass(frozen=True)
class PanelSettings:
    host: str
    port: int
    timezone: str
    connect_timeout_seconds: int
    reconnect_min_seconds: int
    reconnect_max_seconds: int
    frame_idle_ms: int


@dataclass(frozen=True)
class MqttSettings:
    host: str
    port: int
    username: str
    password: str
    base_topic: str
    discovery_prefix: str


@dataclass(frozen=True)
class SyncSettings:
    startup_enabled: bool
    initial_delay_ms: int
    command_delay_ms: int
    response_timeout_seconds: int
    periodic_enabled: bool
    periodic_interval_seconds: int
    reconnect_after_failures: int


@dataclass(frozen=True)
class KeypadSettings:
    enabled: bool
    partitions: tuple[int, ...]
    poll_interval_seconds: int
    event_refresh_delay_ms: int
    chime_zones: tuple[int, ...] = ()


@dataclass(frozen=True)
class ControlSettings:
    enabled: bool
    keypad_enabled: bool
    native_alarm_enabled: bool
    response_timeout_seconds: int
    verify_delay_ms: int


@dataclass(frozen=True)
class EventHistorySettings:
    enabled: bool
    startup_dump_enabled: bool
    sqlite_path: str
    recent_limit: int


@dataclass(frozen=True)
class PrinterSettings:
    enabled: bool
    host: str
    http_port: int
    timeout_seconds: int
    retry_seconds: int
    queue_max: int
    width: int
    spool_path: str


@dataclass(frozen=True)
class Settings:
    panel: PanelSettings
    mqtt: MqttSettings
    sync: SyncSettings
    keypad: KeypadSettings
    control: ControlSettings
    event_history: EventHistorySettings
    printer: PrinterSettings
    raw_logging: bool
    debug_raw_tx_enabled: bool

    @classmethod
    def from_env(cls) -> "Settings":
        settings = cls(
            panel=PanelSettings(
                host=os.environ["PANEL_HOST"].strip(),
                port=int(os.environ["PANEL_PORT"]),
                timezone=os.environ.get("PANEL_TIMEZONE", "America/New_York").strip(),
                connect_timeout_seconds=int(os.environ.get("CONNECT_TIMEOUT_SECONDS", "5")),
                reconnect_min_seconds=int(os.environ.get("RECONNECT_MIN_SECONDS", "1")),
                reconnect_max_seconds=int(os.environ.get("RECONNECT_MAX_SECONDS", "30")),
                frame_idle_ms=int(os.environ.get("FRAME_IDLE_MS", "250")),
            ),
            mqtt=MqttSettings(
                host=os.environ["MQTT_HOST"].strip(),
                port=int(os.environ.get("MQTT_PORT", "1883")),
                username=os.environ.get("MQTT_USERNAME", ""),
                password=os.environ.get("MQTT_PASSWORD", ""),
                base_topic=os.environ.get("MQTT_BASE_TOPIC", "vista128").strip("/"),
                discovery_prefix=os.environ.get(
                    "MQTT_DISCOVERY_PREFIX", "homeassistant"
                ).strip("/"),
            ),
            sync=SyncSettings(
                startup_enabled=_bool_env("STARTUP_SYNC_ENABLED", True),
                initial_delay_ms=int(os.environ.get("STARTUP_SYNC_INITIAL_DELAY_MS", "1000")),
                command_delay_ms=int(os.environ.get("STARTUP_SYNC_COMMAND_DELAY_MS", "500")),
                response_timeout_seconds=int(
                    os.environ.get("STARTUP_SYNC_RESPONSE_TIMEOUT_SECONDS", "5")
                ),
                periodic_enabled=_bool_env("PERIODIC_SYNC_ENABLED", True),
                periodic_interval_seconds=int(
                    os.environ.get("PERIODIC_SYNC_INTERVAL_SECONDS", "300")
                ),
                reconnect_after_failures=int(
                    os.environ.get("PERIODIC_SYNC_RECONNECT_AFTER_FAILURES", "3")
                ),
            ),
            keypad=KeypadSettings(
                enabled=_bool_env("KEYPAD_DISPLAY_ENABLED", True),
                partitions=_partition_list(os.environ.get("KEYPAD_PARTITIONS", "1")),
                poll_interval_seconds=int(
                    os.environ.get("KEYPAD_POLL_INTERVAL_SECONDS", "7")
                ),
                event_refresh_delay_ms=int(
                    os.environ.get("KEYPAD_EVENT_REFRESH_DELAY_MS", "250")
                ),
                chime_zones=_zone_list(os.environ.get("CHIME_ZONES", "")),
            ),
            control=ControlSettings(
                enabled=_bool_env("CONTROL_ENABLED", False),
                keypad_enabled=_bool_env("KEYPAD_CONTROL_ENABLED", False),
                native_alarm_enabled=_bool_env("NATIVE_ALARM_CONTROL_ENABLED", False),
                response_timeout_seconds=int(os.environ.get("CONTROL_RESPONSE_TIMEOUT_SECONDS", "3")),
                verify_delay_ms=int(os.environ.get("CONTROL_VERIFY_DELAY_MS", "400")),
            ),
            event_history=EventHistorySettings(
                enabled=_bool_env("EVENT_HISTORY_ENABLED", True),
                startup_dump_enabled=_bool_env("EVENT_HISTORY_STARTUP_DUMP_ENABLED", False),
                sqlite_path=os.environ.get(
                    "EVENT_HISTORY_SQLITE_PATH", "/data/vista128_events.sqlite3"
                ).strip(),
                recent_limit=int(os.environ.get("EVENT_HISTORY_RECENT_LIMIT", "20")),
            ),
            printer=PrinterSettings(
                enabled=_bool_env("TRANSPORT_PRINT_ENABLED", False),
                host=os.environ.get("TRANSPORT_HOST", "").strip(),
                http_port=int(os.environ.get("TRANSPORT_HTTP_PORT", "9101")),
                timeout_seconds=int(os.environ.get("TRANSPORT_PRINT_TIMEOUT_SECONDS", "5")),
                retry_seconds=int(os.environ.get("TRANSPORT_PRINT_RETRY_SECONDS", "10")),
                queue_max=int(os.environ.get("TRANSPORT_PRINT_QUEUE_MAX", "5000")),
                width=int(os.environ.get("TRANSPORT_PRINT_WIDTH", "32")),
                spool_path=os.environ.get(
                    "TRANSPORT_PRINT_SPOOL_PATH", "/data/vista128_print_queue.sqlite3"
                ).strip(),
            ),
            raw_logging=_bool_env("RAW_LOGGING", True),
            debug_raw_tx_enabled=_bool_env("DEBUG_RAW_TX_ENABLED", False),
        )
        settings.validate()
        return settings

    def validate(self) -> None:
        if self.panel.reconnect_max_seconds < self.panel.reconnect_min_seconds:
            raise ValueError("reconnect_max_seconds must be >= reconnect_min_seconds")
        if self.sync.periodic_interval_seconds < 60:
            raise ValueError("periodic_sync_interval_seconds must be >= 60")
        if self.sync.reconnect_after_failures < 1:
            raise ValueError("periodic_sync_reconnect_after_failures must be >= 1")
        if self.keypad.poll_interval_seconds < 2:
            raise ValueError("keypad_poll_interval_seconds must be >= 2")
        if not 0 <= self.keypad.event_refresh_delay_ms <= 5000:
            raise ValueError("keypad_event_refresh_delay_ms must be 0..5000")
        if not 1 <= self.control.response_timeout_seconds <= 10:
            raise ValueError("control_response_timeout_seconds must be 1..10")
        if not 0 <= self.control.verify_delay_ms <= 5000:
            raise ValueError("control_verify_delay_ms must be 0..5000")
        if not self.event_history.sqlite_path:
            raise ValueError("event_history_sqlite_path must not be empty")
        if not 1 <= self.event_history.recent_limit <= 100:
            raise ValueError("event_history_recent_limit must be 1..100")
        if self.printer.enabled and not self.printer.host:
            raise ValueError("transport_host is required when transport_print_enabled is true")
        if not 1 <= self.printer.http_port <= 65535:
            raise ValueError("transport_http_port must be 1..65535")
        if not 24 <= self.printer.width <= 64:
            raise ValueError("transport_print_width must be 24..64")
        if self.printer.queue_max < 1:
            raise ValueError("transport_print_queue_max must be >= 1")
