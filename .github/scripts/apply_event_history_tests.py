from pathlib import Path


def replace_once(path: str, old: str, new: str, label: str) -> None:
    p = Path(path)
    text = p.read_text()
    if old not in text:
        raise SystemExit(f"missing anchor {label} in {path}")
    p.write_text(text.replace(old, new, 1))


path = "vista128_bridge/tests/test_protocol.py"
replace_once(
    path,
    '''    STARTUP_QUERIES,\n    STATE_SYNC_QUERIES,\n''',
    '''    EVENT_LOG_QUERY,\n    STARTUP_QUERIES,\n    STATE_SYNC_QUERIES,\n''',
    "event query import",
)
replace_once(
    path,
    '''    parse_arming_status,\n''',
    '''    parse_arming_status,\n    parse_event_log_entry,\n''',
    "history parser import",
)
replace_once(
    path,
    '''        self.assertEqual(identify_message(b"1BnqSOMETHING"), "system_event")\n''',
    '''        self.assertEqual(identify_message(b"1BnqSOMETHING"), "system_event")\n        self.assertEqual(identify_message(b"08XF009A"), "communication_off")\n        self.assertEqual(identify_message(b"10DC000000000000"), "display_changed")\n        self.assertEqual(identify_message(b"1BldSOMETHING"), "event_log_entry")\n        self.assertEqual(identify_message(b"08lc0069"), "event_log_complete")\n''',
    "new message types",
)
replace_once(
    path,
    '''    def test_periodic_state_sync_is_dynamic_state_only(self):\n''',
    '''    def test_event_log_query_is_exact_and_long_running(self):\n        self.assertEqual(EVENT_LOG_QUERY.name, "event_log")\n        self.assertEqual(EVENT_LOG_QUERY.data, b"08LD00A8\\r\\n")\n        self.assertEqual(EVENT_LOG_QUERY.timeout_seconds, 45)\n        self.assertFalse(EVENT_LOG_QUERY.required)\n\n    def test_periodic_state_sync_is_dynamic_state_only(self):\n''',
    "event query test",
)
replace_once(
    path,
    '''    def test_parse_zone_descriptor_and_end_marker(self):\n''',
    '''    def test_parse_historical_event_log_entry(self):\n        packet = make_packet("ldB70000021210315082600")\n        self.assertTrue(validate_packet(packet).valid)\n        self.assertEqual(identify_message(packet), "event_log_entry")\n        event = parse_event_log_entry(packet)\n        self.assertIsNotNone(event)\n        self.assertEqual(event.code, "B7")\n        self.assertEqual(event.user, 2)\n        self.assertEqual(event.partition, 1)\n        self.assertEqual(event.panel_timestamp, "2026-08-15T03:21")\n\n    def test_parse_zone_descriptor_and_end_marker(self):\n''',
    "historical event parser test",
)

path = "vista128_bridge/tests/test_synchronizer.py"
p = Path(path)
text = p.read_text()
old = '''            keypad_settings(),\n            lambda: True,\n'''
new = '''            keypad_settings(),\n            False,\n            False,\n            lambda: True,\n'''
if text.count(old) < 3:
    raise SystemExit("expected three synchronizer constructor anchors")
text = text.replace(old, new)
p.write_text(text)
