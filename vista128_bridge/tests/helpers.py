from vista_bridge.config import (
    EventHistorySettings,
    KeypadSettings,
    MqttSettings,
    PanelSettings,
    PrinterSettings,
    Settings,
    SyncSettings,
)


def make_settings(
    *,
    spool_path: str = "/tmp/vista128-test-queue.sqlite3",
    printer_enabled: bool = False,
    printer_host: str = "127.0.0.1",
    printer_port: int = 9101,
    chime_zones: tuple[int, ...] = (),
) -> Settings:
    return Settings(
        panel=PanelSettings(
            host="127.0.0.1",
            port=10001,
            timezone="America/New_York",
            connect_timeout_seconds=5,
            reconnect_min_seconds=1,
            reconnect_max_seconds=30,
            frame_idle_ms=250,
        ),
        mqtt=MqttSettings(
            host="127.0.0.1",
            port=1883,
            username="",
            password="",
            base_topic="vista128",
            discovery_prefix="homeassistant",
        ),
        sync=SyncSettings(
            startup_enabled=True,
            initial_delay_ms=1000,
            command_delay_ms=500,
            response_timeout_seconds=5,
            periodic_enabled=True,
            periodic_interval_seconds=300,
            reconnect_after_failures=3,
        ),
        keypad=KeypadSettings(
            enabled=True,
            partitions=(1,),
            poll_interval_seconds=7,
            event_refresh_delay_ms=250,
            chime_zones=chime_zones,
        ),
        event_history=EventHistorySettings(
            enabled=True,
            startup_dump_enabled=False,
            sqlite_path=spool_path + ".events",
            recent_limit=20,
        ),
        printer=PrinterSettings(
            enabled=printer_enabled,
            host=printer_host,
            http_port=printer_port,
            timeout_seconds=2,
            retry_seconds=1,
            queue_max=100,
            width=32,
            spool_path=spool_path,
        ),
        raw_logging=True,
        debug_raw_tx_enabled=False,
    )
