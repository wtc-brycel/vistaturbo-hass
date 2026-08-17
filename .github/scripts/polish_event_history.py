from pathlib import Path


def replace_once(path: str, old: str, new: str, label: str) -> None:
    p = Path(path)
    text = p.read_text()
    if old not in text:
        raise SystemExit(f"missing anchor {label} in {path}")
    p.write_text(text.replace(old, new, 1))


# Keep event journal available while only the panel TCP link is down, and add
# the Home Automation communication channel as its own diagnostic entity.
path = "vista128_bridge/app/vista_bridge/mqtt_discovery.py"
replace_once(
    path,
    '''        "rx_frames": (\n''',
    '''        "automation_available": (\n            "binary_sensor",\n            {\n                "name": "Automation Interface Available",\n                "unique_id": "vista128_automation_available",\n                "state_topic": topic("panel/automation_available"),\n                "payload_on": "ON",\n                "payload_off": "OFF",\n                "device_class": "connectivity",\n                "entity_category": "diagnostic",\n            },\n        ),\n        "rx_frames": (\n''',
    "automation diagnostic",
)
replace_once(
    path,
    '''        "device": device_info(),\n        **panel_entity_availability(topic),\n    }\n\n\ndef zone_summary_entities''',
    '''        "device": device_info(),\n        "availability_topic": topic("bridge/availability"),\n        "payload_available": "online",\n        "payload_not_available": "offline",\n    }\n\n\ndef zone_summary_entities''',
    "journal bridge-only availability",
)

# Conservatively mark Home Automation unavailable until a fresh XN arrives,
# and periodically republish the persisted journal so it survives MQTT broker
# restarts even when the panel itself is offline.
path = "vista128_bridge/app/vista_bridge/bridge.py"
replace_once(
    path,
    '''            self.mqtt.publish("panel/connected", "OFF", retain=True)\n            self.mqtt.stop()\n''',
    '''            self.mqtt.publish("panel/connected", "OFF", retain=True)\n            self.mqtt.publish("panel/automation_available", "OFF", retain=True)\n            self.mqtt.stop()\n''',
    "shutdown automation unavailable",
)
replace_once(
    path,
    '''        self.mqtt.publish("panel/connected", "ON", retain=True)\n        self.handler.publish_event_history_snapshot()\n''',
    '''        self.mqtt.publish("panel/connected", "ON", retain=True)\n        self.mqtt.publish("panel/automation_available", "OFF", retain=True)\n        self.handler.publish_event_history_snapshot()\n''',
    "session automation baseline",
)
replace_once(
    path,
    '''        self.mqtt.publish("panel/connected", "OFF", retain=True)\n\n        if self._writer is not None:\n''',
    '''        self.mqtt.publish("panel/connected", "OFF", retain=True)\n        self.mqtt.publish("panel/automation_available", "OFF", retain=True)\n\n        if self._writer is not None:\n''',
    "disconnect automation unavailable",
)
replace_once(
    path,
    '''    def _publish_dynamic_state(self, *, include_discovery: bool = False) -> None:\n        if self.state.arming_initialized:\n''',
    '''    def _publish_dynamic_state(self, *, include_discovery: bool = False) -> None:\n        if include_discovery:\n            self.handler.publish_event_history_snapshot()\n\n        if self.state.arming_initialized:\n''',
    "periodic journal republish",
)

# Safer generic stub entity; the visual editor shows actual discovered sensors.
path = "frontend/vista-keypad-card.js"
replace_once(
    path,
    '''      entity: "sensor.vista_128bpt_event_journal",\n''',
    '''      entity: "sensor.event_journal",\n''',
    "event card stub",
)

# Discovery tests for journal availability and automation channel.
path = "vista128_bridge/tests/test_mqtt_client.py"
insert = '''\n    def test_event_journal_discovery_survives_panel_disconnect(self):\n        self.publisher.publish_discovery()\n        published = {item[0]: item[1] for item in self.publisher._client.published if item[1]}\n        config = json.loads(\n            published["homeassistant/sensor/vista128_bridge/event_journal/config"]\n        )\n        self.assertEqual(config["name"], "Event Journal")\n        self.assertEqual(config["state_topic"], "vista128/event_history/count")\n        self.assertEqual(config["availability_topic"], "vista128/bridge/availability")\n        self.assertNotIn("availability", config)\n\n    def test_automation_interface_has_diagnostic_discovery(self):\n        self.publisher.publish_discovery()\n        published = {item[0]: item[1] for item in self.publisher._client.published if item[1]}\n        config = json.loads(\n            published["homeassistant/binary_sensor/vista128_bridge/automation_available/config"]\n        )\n        self.assertEqual(config["state_topic"], "vista128/panel/automation_available")\n        self.assertEqual(config["entity_category"], "diagnostic")\n        self.assertEqual(config["device_class"], "connectivity")\n\n'''
anchor = '\n\nif __name__ == "__main__":\n'
p = Path(path)
s = p.read_text()
if "test_event_journal_discovery_survives_panel_disconnect" not in s:
    if anchor not in s:
        raise SystemExit("missing mqtt test footer")
    s = s.replace(anchor, insert + anchor, 1)
p.write_text(s)

# Root README overview.
path = "README.md"
p = Path(path)
s = p.read_text()
if "persistent SQLite event journal" not in s:
    s = s.replace(
        "- Supports a centralized configurable dashboard chime-zone list\n",
        "- Supports a centralized configurable dashboard chime-zone list\n- Maintains a persistent SQLite event journal from live panel events, with optional historical panel-log import\n- Includes a responsive Home Assistant event-journal card for recent panel history\n",
        1,
    )
    anchor = "## Adaptive Lovelace layout\n"
    section = '''## Persistent event journal\n\nVista Turbo RS232 can preserve VISTA system events in `/data/vista128_events.sqlite3`. Live `nq` notifications are journaled as they arrive. An optional startup import can request the panel's historical event log using the documented `08LD00A8` transaction and merge `ld` records into the same database without replaying live alarm, chime, keypad-refresh, or printer side effects.\n\nThe full journal stays in SQLite. Home Assistant receives only a configurable recent window so Recorder is not forced to store the entire panel history on every sensor update. The matching frontend resource also registers `custom:vista-event-log-card` for a responsive recent-history view.\n\nThe historical startup import is disabled by default in the first test release because the `LD/ld/lc` transaction has not yet been physically validated against this VISTA-128BPT. Live SQLite journaling is enabled by default.\n\n'''
    if anchor in s:
        s = s.replace(anchor, section + anchor, 1)
p.write_text(s)

# App README.
path = "vista128_bridge/README.md"
p = Path(path)
s = p.read_text()
if "Persistent event journal" not in s:
    s = s.replace(
        "- Optional TransPort event receipts\n",
        "- Optional TransPort event receipts\n- Persistent SQLite event journal with optional historical panel event-log import\n",
        1,
    )
    anchor = "## Zone state\n"
    section = '''## Persistent event journal\n\nWhen `event_history_enabled` is true, every decoded live system event is persisted in `/data/vista128_events.sqlite3`. The journal keeps event code, panel timestamp, partition, zone, user number, descriptor, and whether the row was observed live, in the historical panel log, or both. Repeated identical events within the same panel minute remain separate occurrences.\n\nThe App discovers an **Event Journal** sensor whose state is the total journal row count. Its attributes contain dump metadata and only the configured recent window. The complete database is not copied into Home Assistant state.\n\nSet `event_history_startup_dump_enabled: true` to request the VISTA historical log once after successful startup synchronization. The first test release leaves this disabled by default pending physical VISTA-128BPT validation. Historical records are storage-only and do not mutate live panel state or generate chimes, alarm sounds, keypad refreshes, or printer receipts.\n\n'''
    if anchor in s:
        s = s.replace(anchor, section + anchor, 1)
p.write_text(s)

# Detailed operator docs.
path = "vista128_bridge/DOCS.md"
p = Path(path)
s = p.read_text()
if "event_history_enabled" not in s:
    s = s.replace(
        'chime_zones: ""\n',
        'chime_zones: ""\nevent_history_enabled: true\nevent_history_startup_dump_enabled: false\nevent_history_recent_limit: 20\n',
        1,
    )
    anchor = "## Startup synchronization\n"
    section = '''## Event journal and historical panel log\n\n`event_history_enabled` defaults to `true`. The App stores decoded events in `/data/vista128_events.sqlite3` using SQLite WAL mode. Live `1Bnq` notifications are written immediately. The journal is local to the App data directory and survives App upgrades/restarts.\n\n`event_history_recent_limit` controls how many recent rows (1 through 100, default 20) are mirrored into the Home Assistant **Event Journal** sensor attributes. This is intentionally a window rather than the complete journal so Home Assistant Recorder does not repeatedly persist hundreds of historical events. The Event Journal entity remains available while the panel TCP link is down as long as the bridge process itself is online.\n\n`event_history_startup_dump_enabled` defaults to `false` in the first release containing this feature. When enabled, a successful startup synchronization is followed by the documented historical-log request:\n\n```text\n08LD00A8\n```\n\nHistorical entries are decoded from `ld` packets and the transaction completes on `08lc0069`. The query uses the same serialized transaction lock as keypad and state synchronization. Historical rows are merged with matching live occurrences, and repeated identical events within one panel minute are preserved with stable occurrence numbers. Imported historical entries never call the live event state machine and therefore cannot create alarm/chime/printer/keypad side effects.\n\nThe protocol parser also recognizes `08XF` (Communication Off) and `10DC` (Display Changed). `08XF` drives the **Automation Interface Available** diagnostic. `10DC` is logged passively only until it is observed and validated on the current panel.\n\n'''
    if anchor in s:
        s = s.replace(anchor, section + anchor, 1)
p.write_text(s)
