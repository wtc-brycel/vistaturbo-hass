from pathlib import Path


def replace_once(path: str, old: str, new: str, label: str) -> None:
    p = Path(path)
    text = p.read_text()
    if old not in text:
        raise SystemExit(f"missing anchor: {label}")
    p.write_text(text.replace(old, new, 1))


# config.py: centralized zone-number list/range parser.
p = Path("vista128_bridge/app/vista_bridge/config.py")
s = p.read_text()
anchor = '''def _partition_list(value: str) -> tuple[int, ...]:
    partitions = tuple(
        sorted({int(item.strip()) for item in value.split(",") if item.strip()})
    )
    if not partitions or any(partition < 1 or partition > 8 for partition in partitions):
        raise ValueError("keypad_partitions must contain partition numbers 1..8")
    return partitions
'''
replacement = anchor + '''

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
'''
if anchor not in s:
    raise SystemExit("missing anchor: zone list parser")
s = s.replace(anchor, replacement, 1)
s = s.replace(
    '''class KeypadSettings:
    enabled: bool
    partitions: tuple[int, ...]
    poll_interval_seconds: int
    event_refresh_delay_ms: int
''',
    '''class KeypadSettings:
    enabled: bool
    partitions: tuple[int, ...]
    poll_interval_seconds: int
    event_refresh_delay_ms: int
    chime_zones: tuple[int, ...]
''',
    1,
)
s = s.replace(
    '''                event_refresh_delay_ms=int(
                    os.environ.get("KEYPAD_EVENT_REFRESH_DELAY_MS", "250")
                ),
            ),''',
    '''                event_refresh_delay_ms=int(
                    os.environ.get("KEYPAD_EVENT_REFRESH_DELAY_MS", "250")
                ),
                chime_zones=_zone_list(os.environ.get("CHIME_ZONES", "")),
            ),''',
    1,
)
p.write_text(s)

# Home Assistant App config + environment bridge.
replace_once(
    "vista128_bridge/config.yaml",
    '  keypad_event_refresh_delay_ms: 250\n',
    '  keypad_event_refresh_delay_ms: 250\n  chime_zones: ""\n',
    "app chime option",
)
replace_once(
    "vista128_bridge/config.yaml",
    '  keypad_event_refresh_delay_ms: int(0,5000)\n',
    '  keypad_event_refresh_delay_ms: int(0,5000)\n  chime_zones: str\n',
    "app chime schema",
)
replace_once(
    "vista128_bridge/run.sh",
    '''export KEYPAD_EVENT_REFRESH_DELAY_MS="$(config_or_default 'keypad_event_refresh_delay_ms' '250')"\n''',
    '''export KEYPAD_EVENT_REFRESH_DELAY_MS="$(config_or_default 'keypad_event_refresh_delay_ms' '250')"\nexport CHIME_ZONES="$(config_or_default 'chime_zones' '')"\n''',
    "chime env",
)

# Keypad state carries an event sequence instead of asking every card to watch zone entities.
p = Path("vista128_bridge/app/vista_bridge/state.py")
s = p.read_text()
s = s.replace(
    '''    supervisory_led: bool | None = None
    led_status: int = 0
''',
    '''    supervisory_led: bool | None = None
    chime_sequence: int = 0
    chime_zone: int | None = None
    chime_descriptor: str = ""
    chime_at: str = ""
    led_status: int = 0
''',
    1,
)
s = s.replace(
    '''            "supervisory": self.supervisory_led,
            "backlight": self.backlight,
''',
    '''            "supervisory": self.supervisory_led,
            "chime_sequence": self.chime_sequence,
            "chime_zone": self.chime_zone,
            "chime_descriptor": self.chime_descriptor,
            "chime_at": self.chime_at,
            "backlight": self.backlight,
''',
    1,
)
anchor = '''    def assigned_zones_with(self, attribute: str) -> list[ZoneState]:
'''
method = '''    def record_chime(self, partition: int, zone_number: int, received_at: str) -> KeypadState | None:
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

'''
if anchor not in s:
    raise SystemExit("missing anchor: record chime")
s = s.replace(anchor, method + anchor, 1)
p.write_text(s)

# F5 is the validated real-time fault transition. Only configured zones generate chimes.
p = Path("vista128_bridge/app/vista_bridge/message_handler.py")
s = p.read_text()
anchor = '''        self._handle_system_event_side_effects(event.code)
        self.synchronizer.request_keypad_refresh(event.partition)

        # Supplemental 6160CR-2 annunciators are reconstructed from nq events.
'''
replacement = '''        self._handle_system_event_side_effects(event.code)
        self.synchronizer.request_keypad_refresh(event.partition)

        if event.code == "F5" and event.zone in self.settings.keypad.chime_zones:
            keypad = self.state.record_chime(event.partition, event.zone, received_at)
            if keypad is not None:
                LOG.info(
                    "Chime zone fault: zone=%03d partition=%d sequence=%d",
                    event.zone,
                    keypad.partition,
                    keypad.chime_sequence,
                )

        # Supplemental 6160CR-2 annunciators and configured chime events are
        # published immediately without waiting for the next KD poll.
'''
if anchor not in s:
    raise SystemExit("missing anchor: message chime")
s = s.replace(anchor, replacement, 1)
p.write_text(s)

# Test settings support explicit chime lists.
p = Path("vista128_bridge/tests/helpers.py")
s = p.read_text()
s = s.replace(
    '''    printer_port: int = 9101,
) -> Settings:
''',
    '''    printer_port: int = 9101,
    chime_zones: tuple[int, ...] = (),
) -> Settings:
''',
    1,
)
s = s.replace(
    '''            event_refresh_delay_ms=250,
        ),
''',
    '''            event_refresh_delay_ms=250,
            chime_zones=chime_zones,
        ),
''',
    1,
)
p.write_text(s)

# Focused regression tests for range parsing and listed/unlisted F5 events.
p = Path("vista128_bridge/tests/test_message_handler.py")
s = p.read_text()
marker = '''    def test_captured_bypass_event_refreshes_zone_summaries(self):
'''
tests = '''    def test_configured_fault_zone_increments_keypad_chime_sequence(self):
        handler = ProtocolMessageHandler(
            make_settings(chime_zones=(27,)),
            self.state,
            self.mqtt,
            self.printer,
            self.sync,
        )
        self.sync.keypad_partition = 1
        handler.handle(
            "keypad_display",
            b"29kd\\xd01   DISARMED   BYPAS-RDY TO ARM100CD",
            "2026-08-16T13:22:28-04:00",
        )
        self.state.zones[27].partition = 1
        self.state.zones[27].descriptor = "GLASS BREAK KITCHEN"
        before = len(self.mqtt.keypad_states)
        handler.handle(
            "system_event",
            b"1BnqF502700012123150826007B",
            "2026-08-16T13:23:00-04:00",
        )
        keypad = self.state.keypads[1]
        self.assertEqual(keypad.chime_sequence, 1)
        self.assertEqual(keypad.chime_zone, 27)
        self.assertEqual(keypad.chime_descriptor, "GLASS BREAK KITCHEN")
        self.assertGreater(len(self.mqtt.keypad_states), before)

    def test_unlisted_fault_zone_does_not_chime(self):
        handler = ProtocolMessageHandler(
            make_settings(chime_zones=(28,)),
            self.state,
            self.mqtt,
            self.printer,
            self.sync,
        )
        handler.handle(
            "system_event",
            b"1BnqF502700012123150826007B",
            "2026-08-16T13:23:00-04:00",
        )
        self.assertEqual(self.state.keypads[1].chime_sequence, 0)

'''
if marker not in s:
    raise SystemExit("missing anchor: chime tests")
s = s.replace(marker, tests + marker, 1)
p.write_text(s)

Path("vista128_bridge/tests/test_chime_config.py").write_text('''import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))

from vista_bridge.config import _zone_list


class ChimeZoneConfigTests(unittest.TestCase):
    def test_empty_list(self):
        self.assertEqual(_zone_list(""), ())

    def test_numbers_and_ranges(self):
        self.assertEqual(_zone_list("1, 2, 5-8,27"), (1, 2, 5, 6, 7, 8, 27))

    def test_invalid_zone_rejected(self):
        with self.assertRaises(ValueError):
            _zone_list("1,129")

    def test_descending_range_rejected(self):
        with self.assertRaises(ValueError):
            _zone_list("8-5")


if __name__ == "__main__":
    unittest.main()
''')
