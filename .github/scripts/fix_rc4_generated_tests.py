from pathlib import Path

p = Path("vista128_bridge/tests/test_state.py")
s = p.read_text()
s = s.replace(
    '''    def test_audible_alarm_families_drive_native_keypad_sound_state(self):
        keypad = self.state.keypads[1]
''',
    '''    def test_audible_alarm_families_drive_native_keypad_sound_state(self):
        state = VistaState()
        keypad = state.keypads[1]
''',
    1,
)
s = s.replace(
    '''    def test_silent_and_duress_events_do_not_drive_burglary_speaker_state(self):
        keypad = self.state.keypads[1]
''',
    '''    def test_silent_and_duress_events_do_not_drive_burglary_speaker_state(self):
        state = VistaState()
        keypad = state.keypads[1]
''',
    1,
)
s = s.replace("self.state.apply_system_event", "state.apply_system_event")
s = s.replace('SystemEvent("31", "Audible Alarm", 10, 0, 1, "")', 'SystemEvent("31", "Audible Alarm", 10, 0, 1, 0, 0, 15, 8, 26)')
s = s.replace('SystemEvent("32", "Audible Alarm Restore", 10, 0, 1, "")', 'SystemEvent("32", "Audible Alarm Restore", 10, 0, 1, 0, 0, 15, 8, 26)')
s = s.replace('SystemEvent("B1", "24 Hour Auxiliary Alarm", 11, 0, 1, "")', 'SystemEvent("B1", "24 Hour Auxiliary Alarm", 11, 0, 1, 0, 0, 15, 8, 26)')
s = s.replace('SystemEvent("B2", "24 Hour Auxiliary Alarm Restore", 11, 0, 1, "")', 'SystemEvent("B2", "24 Hour Auxiliary Alarm Restore", 11, 0, 1, 0, 0, 15, 8, 26)')
s = s.replace('SystemEvent("21", "Silent Alarm", 12, 0, 1, "")', 'SystemEvent("21", "Silent Alarm", 12, 0, 1, 0, 0, 15, 8, 26)')
s = s.replace('SystemEvent("11", "Duress Alarm", 0, 1, 1, "")', 'SystemEvent("11", "Duress Alarm", 0, 1, 1, 0, 0, 15, 8, 26)')
p.write_text(s)

p = Path("vista128_bridge/tests/test_readiness.py")
s = p.read_text()
s = s.replace(
    '''    def test_reconnect_invalidates_native_audible_state(self):
        keypad = self.state.keypads[1]
''',
    '''    def test_reconnect_invalidates_native_audible_state(self):
        state = VistaState()
        keypad = state.keypads[1]
''',
    1,
)
s = s.replace("self.state.partitions[1].active_burglary_tokens", "state.partitions[1].active_burglary_tokens")
s = s.replace("self.state.reset_connection_derived_annunciators()", "state.reset_connection_derived_annunciators()")
p.write_text(s)
