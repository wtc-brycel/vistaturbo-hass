from __future__ import annotations

from dataclasses import dataclass
import os


MQTT_OUTBOUND_QUEUE_MIN = 4096


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
    tls_enabled: bool = False
    tls_ca: str = ""
    tls_client_cert: str = ""
    tls_client_key: str = ""
    outbound_queue_max: int = 256
    inflight_messages_max: int = 20


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
    audit_enabled: bool = True
    max_age_days: int = 90
    max_rows: int = 10000


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
    raw_mqtt_enabled: bool = False
    tx_queue_max: int = 128
    raw_tx_queue_max: int = 16

    @classmethod
    def from_env(cls) -> "Settings":
        requested_outbound_queue = int(
            os.environ.get("MQTT_OUTBOUND_QUEUE_MAX", str(MQTT_OUTBOUND_QUEUE_MIN))
        )
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
                tls_enabled=_bool_env("MQTT_TLS_ENABLED", False),
                tls_ca=os.environ.get("MQTT_TLS_CA", "").strip(),
                tls_client_cert=os.environ.get("MQTT_TLS_CLIENT_CERT", "").strip(),
                tls_client_key=os.environ.get("MQTT_TLS_CLIENT_KEY", "").strip(),
                outbound_queue_max=max(
                    MQTT_OUTBOUND_QUEUE_MIN,
                    requested_outbound_queue,
                ),
                inflight_messages_max=int(
                    os.environ.get("MQTT_INFLIGHT_MESSAGES_MAX", "20")
                ),
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
                audit_enabled=_bool_env("KEYPAD_AUDIT_ENABLED", True),
                max_age_days=int(os.environ.get("EVENT_HISTORY_MAX_AGE_DAYS", "90")),
                max_rows=int(os.environ.get("EVENT_HISTORY_MAX_ROWS", "10000")),
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
            raw_logging=_bool_env("RAW_LOGGING", False),
            debug_raw_tx_enabled=_bool_env("DEBUG_RAW_TX_ENABLED", False),
            raw_mqtt_enabled=_bool_env("RAW_MQTT_ENABLED", False),
            tx_queue_max=int(os.environ.get("TX_QUEUE_MAX", "128")),
            raw_tx_queue_max=int(os.environ.get("RAW_TX_QUEUE_MAX", "16")),
        )
        settings.validate()
        return settings

    def validate(self) -> None:
        if self.panel.reconnect_max_seconds < self.panel.reconnect_min_seconds:
            raise ValueError("reconnect_max_seconds must be >= reconnect_min_seconds")
        if not 1 <= self.mqtt.port <= 65535:
            raise ValueError("mqtt_port must be 1..65535")
        if bool(self.mqtt.tls_client_cert) != bool(self.mqtt.tls_client_key):
            raise ValueError(
                "mqtt_tls_client_cert and mqtt_tls_client_key must be configured together"
            )
        if not MQTT_OUTBOUND_QUEUE_MIN <= self.mqtt.outbound_queue_max <= 10000:
            raise ValueError(
                f"mqtt_outbound_queue_max must be {MQTT_OUTBOUND_QUEUE_MIN}..10000"
            )
        if not 1 <= self.mqtt.inflight_messages_max <= 1000:
            raise ValueError("mqtt_inflight_messages_max must be 1..1000")
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
        if not 1 <= self.event_history.max_age_days <= 3650:
            raise ValueError("event_history_max_age_days must be 1..3650")
        if not 100 <= self.event_history.max_rows <= 1_000_000:
            raise ValueError("event_history_max_rows must be 100..1000000")
        if self.printer.enabled and not self.printer.host:
            raise ValueError("transport_host is required when transport_print_enabled is true")
        if not 1 <= self.printer.http_port <= 65535:
            raise ValueError("transport_http_port must be 1..65535")
        if not 24 <= self.printer.width <= 64:
            raise ValueError("transport_print_width must be 24..64")
        if self.printer.queue_max < 1:
            raise ValueError("transport_print_queue_max must be >= 1")
        if not 1 <= self.tx_queue_max <= 10000:
            raise ValueError("tx_queue_max must be 1..10000")
        if not 1 <= self.raw_tx_queue_max <= 1000:
            raise ValueError("raw_tx_queue_max must be 1..1000")
