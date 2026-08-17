from pathlib import Path


def replace_once(path: str, old: str, new: str, label: str) -> None:
    p = Path(path)
    text = p.read_text()
    if old not in text:
        raise SystemExit(f"missing anchor {label} in {path}")
    p.write_text(text.replace(old, new, 1))


# config.py
path = "vista128_bridge/app/vista_bridge/config.py"
replace_once(
    path,
    '''@dataclass(frozen=True)\nclass PrinterSettings:\n''',
    '''@dataclass(frozen=True)\nclass EventHistorySettings:\n    enabled: bool\n    startup_dump_enabled: bool\n    sqlite_path: str\n    recent_limit: int\n\n\n@dataclass(frozen=True)\nclass PrinterSettings:\n''',
    "event history settings class",
)
replace_once(
    path,
    '''    keypad: KeypadSettings\n    printer: PrinterSettings\n''',
    '''    keypad: KeypadSettings\n    event_history: EventHistorySettings\n    printer: PrinterSettings\n''',
    "settings field",
)
replace_once(
    path,
    '''            printer=PrinterSettings(\n''',
    '''            event_history=EventHistorySettings(\n                enabled=_bool_env("EVENT_HISTORY_ENABLED", True),\n                startup_dump_enabled=_bool_env("EVENT_HISTORY_STARTUP_DUMP_ENABLED", False),\n                sqlite_path=os.environ.get(\n                    "EVENT_HISTORY_SQLITE_PATH", "/data/vista128_events.sqlite3"\n                ).strip(),\n                recent_limit=int(os.environ.get("EVENT_HISTORY_RECENT_LIMIT", "20")),\n            ),\n            printer=PrinterSettings(\n''',
    "event history env",
)
replace_once(
    path,
    '''        if self.printer.enabled and not self.printer.host:\n''',
    '''        if not self.event_history.sqlite_path:\n            raise ValueError("event_history_sqlite_path must not be empty")\n        if not 1 <= self.event_history.recent_limit <= 100:\n            raise ValueError("event_history_recent_limit must be 1..100")\n        if self.printer.enabled and not self.printer.host:\n''',
    "event history validation",
)

# protocol.py
path = "vista128_bridge/app/vista_bridge/protocol.py"
replace_once(
    path,
    '''STATE_SYNC_QUERIES: tuple[ProtocolQuery, ...] = STARTUP_QUERIES[:2]\n''',
    '''STATE_SYNC_QUERIES: tuple[ProtocolQuery, ...] = STARTUP_QUERIES[:2]\nEVENT_LOG_QUERY = ProtocolQuery(\n    "event_log", b"08LD00A8\\r\\n", timeout_seconds=45, required=False\n)\n''',
    "event log query",
)
replace_once(
    path,
    '''    if data.startswith(b"08XN"):\n        return "communication_on"\n''',
    '''    if data.startswith(b"08XN"):\n        return "communication_on"\n    if data.startswith(b"08XF"):\n        return "communication_off"\n    if data.startswith(b"10DC"):\n        return "display_changed"\n''',
    "passive message types",
)
replace_once(
    path,
    '''    if data.startswith((b"1Bnq", b"14NQ")):\n        return "system_event"\n''',
    '''    if data.startswith((b"1Bnq", b"14NQ")):\n        return "system_event"\n    if len(data) >= 4 and data[2:4].lower() == b"ld":\n        return "event_log_entry"\n    if len(data) >= 4 and data[2:4].lower() == b"lc":\n        return "event_log_complete"\n''',
    "history message types",
)
replace_once(
    path,
    '''def parse_system_event(data: bytes) -> SystemEvent | None:\n''',
    '''def parse_event_log_entry(data: bytes) -> SystemEvent | None:\n    if len(data) < 27 or data[2:4].lower() != b"ld":\n        return None\n\n    payload = data[4:-4].decode("ascii", errors="strict")\n    if len(payload) != 19:\n        return None\n\n    code = payload[0:2]\n    fields = (\n        payload[2:5],\n        payload[5:8],\n        payload[8:9],\n        payload[9:11],\n        payload[11:13],\n        payload[13:15],\n        payload[15:17],\n        payload[17:19],\n    )\n    try:\n        zone, user, partition, minute, hour, day, month, year = map(int, fields)\n    except ValueError:\n        return None\n\n    return SystemEvent(\n        code=code,\n        description=EVENT_DESCRIPTIONS.get(code, f"Event {code}"),\n        zone=zone,\n        user=user,\n        partition=partition,\n        minute=minute,\n        hour=hour,\n        day=day,\n        month=month,\n        year=year,\n    )\n\n\ndef parse_system_event(data: bytes) -> SystemEvent | None:\n''',
    "event log parser",
)

# synchronizer.py
path = "vista128_bridge/app/vista_bridge/synchronizer.py"
replace_once(
    path,
    '''    ProtocolQuery,\n    STARTUP_QUERIES,\n''',
    '''    EVENT_LOG_QUERY,\n    ProtocolQuery,\n    STARTUP_QUERIES,\n''',
    "event query import",
)
replace_once(
    path,
    '''        keypad_settings: KeypadSettings,\n        is_connected: BoolCallback,\n''',
    '''        keypad_settings: KeypadSettings,\n        event_history_enabled: bool,\n        event_history_startup_dump_enabled: bool,\n        is_connected: BoolCallback,\n''',
    "synchronizer constructor params",
)
replace_once(
    path,
    '''        self.keypad_settings = keypad_settings\n        self.is_connected = is_connected\n''',
    '''        self.keypad_settings = keypad_settings\n        self.event_history_enabled = event_history_enabled\n        self.event_history_startup_dump_enabled = event_history_startup_dump_enabled\n        self.is_connected = is_connected\n''',
    "history flags",
)
replace_once(
    path,
    '''        self.keypad_response_event = asyncio.Event()\n''',
    '''        self.keypad_response_event = asyncio.Event()\n        self.event_log_complete_event = asyncio.Event()\n''',
    "history completion event",
)
replace_once(
    path,
    '''        self.keypad_response_event.clear()\n''',
    '''        self.keypad_response_event.clear()\n        self.event_log_complete_event.clear()\n''',
    "history reset",
)
replace_once(
    path,
    '''    def mark_keypad_response(self) -> None:\n        self.keypad_response_event.set()\n\n''',
    '''    def mark_keypad_response(self) -> None:\n        self.keypad_response_event.set()\n\n    def mark_event_log_complete(self) -> None:\n        self.event_log_complete_event.set()\n\n''',
    "history complete marker",
)
replace_once(
    path,
    '''        self._startup_complete = ok\n        if not ok:\n            LOG.warning("Startup synchronization failed; reconnecting")\n            self.force_reconnect()\n''',
    '''        self._startup_complete = ok\n        if not ok:\n            LOG.warning("Startup synchronization failed; reconnecting")\n            self.force_reconnect()\n            return\n        if self.event_history_enabled and self.event_history_startup_dump_enabled:\n            await self.run_event_log_dump()\n''',
    "startup history dump",
)
replace_once(
    path,
    '''    async def run_sync(\n''',
    '''    async def run_event_log_dump(self) -> bool:\n        if not self.is_connected():\n            return False\n\n        async with self.lock:\n            self._active.set()\n            self.event_log_complete_event.clear()\n            try:\n                accepted, detail = self.send_query(\n                    EVENT_LOG_QUERY.data, "history", EVENT_LOG_QUERY.name\n                )\n                if not accepted:\n                    LOG.warning("Event-log query was not sent: %s", detail)\n                    return False\n                LOG.info("Queued VISTA historical event-log dump")\n                try:\n                    await asyncio.wait_for(\n                        self.event_log_complete_event.wait(),\n                        timeout=EVENT_LOG_QUERY.timeout_seconds or 45,\n                    )\n                except asyncio.TimeoutError:\n                    LOG.warning(\n                        "Historical event-log dump timed out after %ss",\n                        EVENT_LOG_QUERY.timeout_seconds or 45,\n                    )\n                    return False\n                await asyncio.sleep(self.settings.command_delay_ms / 1000)\n                return True\n            finally:\n                self._active.clear()\n\n    async def run_sync(\n''',
    "event log transaction",
)

# bridge.py
path = "vista128_bridge/app/vista_bridge/bridge.py"
replace_once(
    path,
    '''from .framing import RawFrame, VistaStreamFramer\n''',
    '''from .event_store import EventStore\nfrom .framing import RawFrame, VistaStreamFramer\n''',
    "event store import",
)
replace_once(
    path,
    '''        self.printer = TransPortEventPrinter(settings)\n        self.mqtt = MqttPublisher(settings, self.enqueue_raw_tx)\n''',
    '''        self.printer = TransPortEventPrinter(settings)\n        self.event_store = (\n            EventStore(settings.event_history.sqlite_path)\n            if settings.event_history.enabled\n            else None\n        )\n        self.mqtt = MqttPublisher(settings, self.enqueue_raw_tx)\n''',
    "event store instance",
)
replace_once(
    path,
    '''            settings.keypad,\n            self._is_connected,\n''',
    '''            settings.keypad,\n            settings.event_history.enabled,\n            settings.event_history.startup_dump_enabled,\n            self._is_connected,\n''',
    "synchronizer history settings",
)
replace_once(
    path,
    '''            self.printer,\n            self.synchronizer,\n''',
    '''            self.printer,\n            self.synchronizer,\n            self.event_store,\n''',
    "handler store",
)
replace_once(
    path,
    '''        self.mqtt.publish("panel/connected", "ON", retain=True)\n''',
    '''        self.mqtt.publish("panel/connected", "ON", retain=True)\n        self.handler.publish_event_history_snapshot()\n''',
    "publish journal snapshot",
)

# message_handler.py
path = "vista128_bridge/app/vista_bridge/message_handler.py"
replace_once(
    path,
    '''from .config import Settings\n''',
    '''from .config import Settings\nfrom .event_store import EventStore\n''',
    "store import",
)
replace_once(
    path,
    '''    parse_arming_status,\n''',
    '''    parse_arming_status,\n    parse_event_log_entry,\n''',
    "event log parser import",
)
replace_once(
    path,
    '''        synchronizer: VistaSynchronizer,\n    ) -> None:\n''',
    '''        synchronizer: VistaSynchronizer,\n        event_store: EventStore | None = None,\n    ) -> None:\n''',
    "handler store param",
)
replace_once(
    path,
    '''        self.synchronizer = synchronizer\n        self.last_panel_clock_offset_seconds: int | None = None\n''',
    '''        self.synchronizer = synchronizer\n        self.event_store = event_store\n        self._history_dump_seen = 0\n        self._history_dump_inserted = 0\n        self.last_panel_clock_offset_seconds: int | None = None\n''',
    "handler store state",
)
replace_once(
    path,
    '''            "communication_on": self._handle_communication_on,\n''',
    '''            "communication_on": self._handle_communication_on,\n            "communication_off": self._handle_communication_off,\n            "display_changed": self._handle_display_changed,\n            "event_log_entry": self._handle_event_log_entry,\n            "event_log_complete": self._handle_event_log_complete,\n''',
    "new handlers",
)
replace_once(
    path,
    '''    def _handle_communication_on(self, data: bytes, received_at: str) -> None:\n        LOG.info("VISTA reported Communication On")\n        self.synchronizer.request_full_resync("communication_on")\n\n''',
    '''    def _handle_communication_on(self, data: bytes, received_at: str) -> None:\n        LOG.info("VISTA reported Communication On")\n        self.mqtt.publish("panel/automation_available", "ON", retain=True, qos=1)\n        self.synchronizer.request_full_resync("communication_on")\n\n    def _handle_communication_off(self, data: bytes, received_at: str) -> None:\n        LOG.info("VISTA reported Communication Off")\n        self.mqtt.publish("panel/automation_available", "OFF", retain=True, qos=1)\n\n    def _handle_display_changed(self, data: bytes, received_at: str) -> None:\n        # Some Turbo integrations document DC display-change notifications, but\n        # they have not been observed on the current VISTA-128BPT. Recognize and\n        # log them passively before attempting any refresh semantics.\n        LOG.info("VISTA reported Display Changed notification: %r", data)\n\n    def _handle_event_log_entry(self, data: bytes, received_at: str) -> None:\n        event = parse_event_log_entry(data)\n        if event is None:\n            return\n        self._history_dump_seen += 1\n        descriptor = self.state.zones.get(event.zone).descriptor if event.zone in self.state.zones else ""\n        if self.event_store is not None and self.event_store.record(\n            event, source="history", received_at=received_at, descriptor=descriptor\n        ):\n            self._history_dump_inserted += 1\n\n    def _handle_event_log_complete(self, data: bytes, received_at: str) -> None:\n        LOG.info(\n            "Historical event-log dump complete: seen=%d inserted=%d",\n            self._history_dump_seen,\n            self._history_dump_inserted,\n        )\n        if self.event_store is not None:\n            self.event_store.finish_history_dump(\n                completed_at=received_at,\n                seen=self._history_dump_seen,\n                inserted=self._history_dump_inserted,\n            )\n        self.synchronizer.mark_event_log_complete()\n        self.publish_event_history_snapshot()\n        self._history_dump_seen = 0\n        self._history_dump_inserted = 0\n\n''',
    "history handlers",
)
replace_once(
    path,
    '''        self.last_event_received_at = received_at\n''',
    '''        descriptor = self.state.zones.get(event.zone).descriptor if event.zone in self.state.zones else ""\n        if self.event_store is not None:\n            self.event_store.record(\n                event, source="live", received_at=received_at, descriptor=descriptor\n            )\n            self.publish_event_history_snapshot()\n\n        self.last_event_received_at = received_at\n''',
    "record live event",
)
replace_once(
    path,
    '''        descriptor = ""\n        if event.zone in self.state.zones:\n            descriptor = self.state.zones[event.zone].descriptor\n        self.printer.enqueue_event(\n''',
    '''        self.printer.enqueue_event(\n''',
    "reuse descriptor",
)
replace_once(
    path,
    '''    def _handle_system_event_side_effects(self, code: str) -> None:\n''',
    '''    def publish_event_history_snapshot(self) -> None:\n        if self.event_store is None:\n            return\n        stats = self.event_store.stats()\n        recent = self.event_store.recent(self.settings.event_history.recent_limit)\n        self.mqtt.publish_event_history(\n            count=stats.count,\n            last_dump_at=stats.last_dump_at,\n            last_dump_seen=stats.last_dump_seen,\n            last_dump_inserted=stats.last_dump_inserted,\n            events=recent,\n        )\n\n    def _handle_system_event_side_effects(self, code: str) -> None:\n''',
    "journal snapshot method",
)

# mqtt_discovery.py
path = "vista128_bridge/app/vista_bridge/mqtt_discovery.py"
replace_once(
    path,
    '''def zone_summary_entities(topic: TopicFn) -> dict[str, dict]:\n''',
    '''def event_history_config(topic: TopicFn) -> dict:\n    return {\n        "name": "Event Journal",\n        "unique_id": "vista128_event_journal",\n        "state_topic": topic("event_history/count"),\n        "json_attributes_topic": topic("event_history/attributes"),\n        "icon": "mdi:history",\n        "device": device_info(),\n        **panel_entity_availability(topic),\n    }\n\n\ndef zone_summary_entities(topic: TopicFn) -> dict[str, dict]:\n''',
    "history discovery function",
)

# mqtt_client.py
path = "vista128_bridge/app/vista_bridge/mqtt_client.py"
replace_once(
    path,
    '''    diagnostic_entities,\n''',
    '''    diagnostic_entities,\n    event_history_config,\n''',
    "history discovery import",
)
replace_once(
    path,
    '''        if self.settings.keypad.enabled:\n''',
    '''        if self.settings.event_history.enabled:\n            self._publish_discovery_config(\n                "sensor", "event_journal", event_history_config(self.topic)\n            )\n        if self.settings.keypad.enabled:\n''',
    "history discovery publish",
)
replace_once(
    path,
    '''    def publish_event(\n''',
    '''    def publish_event_history(\n        self,\n        *,\n        count: int,\n        last_dump_at: str,\n        last_dump_seen: int,\n        last_dump_inserted: int,\n        events: list[dict],\n    ) -> None:\n        self.publish("event_history/count", count, retain=True, qos=1)\n        self.publish_json(\n            "event_history/attributes",\n            {\n                "count": count,\n                "last_dump_at": last_dump_at or None,\n                "last_dump_seen": last_dump_seen,\n                "last_dump_inserted": last_dump_inserted,\n                "events": events,\n            },\n            retain=True,\n            qos=1,\n        )\n\n    def publish_event(\n''',
    "history mqtt state",
)

# test helpers
path = "vista128_bridge/tests/helpers.py"
replace_once(
    path,
    '''    KeypadSettings,\n''',
    '''    EventHistorySettings,\n    KeypadSettings,\n''',
    "helper import",
)
replace_once(
    path,
    '''        printer=PrinterSettings(\n''',
    '''        event_history=EventHistorySettings(\n            enabled=True,\n            startup_dump_enabled=False,\n            sqlite_path=spool_path + ".events",\n            recent_limit=20,\n        ),\n        printer=PrinterSettings(\n''',
    "helper history settings",
)

# config.yaml
path = "vista128_bridge/config.yaml"
replace_once(
    path,
    '''  chime_zones: ""\n  transport_print_enabled: false\n''',
    '''  chime_zones: ""\n  event_history_enabled: true\n  event_history_startup_dump_enabled: false\n  event_history_recent_limit: 20\n  transport_print_enabled: false\n''',
    "app options",
)
replace_once(
    path,
    '''  chime_zones: str\n  transport_print_enabled: bool\n''',
    '''  chime_zones: str\n  event_history_enabled: bool\n  event_history_startup_dump_enabled: bool\n  event_history_recent_limit: int(1,100)\n  transport_print_enabled: bool\n''',
    "app schema",
)

# run.sh
path = "vista128_bridge/run.sh"
replace_once(
    path,
    '''export CHIME_ZONES="$(config_or_default 'chime_zones' '')"\n''',
    '''export CHIME_ZONES="$(config_or_default 'chime_zones' '')"\nexport EVENT_HISTORY_ENABLED="$(config_or_default 'event_history_enabled' 'true')"\nexport EVENT_HISTORY_STARTUP_DUMP_ENABLED="$(config_or_default 'event_history_startup_dump_enabled' 'false')"\nexport EVENT_HISTORY_RECENT_LIMIT="$(config_or_default 'event_history_recent_limit' '20')"\nexport EVENT_HISTORY_SQLITE_PATH="/data/vista128_events.sqlite3"\n''',
    "history env exports",
)
replace_once(
    path,
    '''if bashio::var.true "${TRANSPORT_PRINT_ENABLED}"; then\n''',
    '''if bashio::var.true "${EVENT_HISTORY_ENABLED}"; then\n  bashio::log.info "Event journal: ${EVENT_HISTORY_SQLITE_PATH}; recent HA window ${EVENT_HISTORY_RECENT_LIMIT}"\n  if bashio::var.true "${EVENT_HISTORY_STARTUP_DUMP_ENABLED}"; then\n    bashio::log.info "Historical event-log dump enabled at startup"\n  fi\nfi\nif bashio::var.true "${TRANSPORT_PRINT_ENABLED}"; then\n''',
    "history startup log",
)

# Event codes observed/documented but missing from current table.
path = "vista128_bridge/app/vista_bridge/event_codes.py"
replace_once(
    path,
    '''    "C4": "Fire Trouble Restore",\n''',
    '''    "C4": "Fire Trouble Restore",\n    "C7": "Fail To Arm",\n    "C8": "Fail To Disarm",\n''',
    "fail arm events",
)
