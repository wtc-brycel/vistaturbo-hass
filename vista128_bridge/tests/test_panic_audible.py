import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))

from vista_bridge.mqtt_discovery import keypad_alarm_configs, panel_alarm_configs  # noqa: E402
from vista_bridge.protocol import KeypadDisplayReport, SystemEvent  # noqa: E402
from vista_bridge.state import VistaState  # noqa: E402


def topic(suffix: str) -> str:
    return f"vista128/{suffix}"


def keypad_report() -> KeypadDisplayReport:
    return KeypadDisplayReport(
        line_1="P1   DISARMED   ",
        line_2="READY TO ARM    ",
        backlight=True,
        ready_led=True,
        trouble_led=False,
        armed_led=False,
        led_status=1,
        raw_display=b"P1   DISARMED   READY TO ARM    ",
    )


def event(code: str, zone: int = 10) -> SystemEvent:
    return SystemEvent(code, code, zone, 0, 1, 0, 0, 15, 8, 26)


class AudiblePanicTests(unittest.TestCase):
    def test_audible_panic_drives_distinct_sound_state_until_restore(self):
        state = VistaState()
        keypad = state.apply_keypad_display(1, keypad_report(), "2026-08-30T16:00:00-04:00")
        self.assertFalse(keypad.audible_panic_alarm)
        self.assertEqual(keypad.sound_mode, "none")

        state.apply_system_event(event("31"))
        self.assertTrue(state.partitions[1].audible_panic_alarm_active)
        self.assertTrue(keypad.audible_panic_alarm)
        self.assertEqual(keypad.sound_mode, "panic_audible")
        self.assertFalse(keypad.burglary_alarm_led)
        self.assertFalse(keypad.auxiliary_alarm_led)
        self.assertTrue(state.panel_alarm_states()["values"]["panic_audible"])

        state.apply_system_event(event("32"))
        self.assertFalse(state.partitions[1].audible_panic_alarm_active)
        self.assertFalse(keypad.audible_panic_alarm)
        self.assertEqual(keypad.sound_mode, "none")

    def test_one_restore_does_not_clear_another_active_audible_panic(self):
        state = VistaState()
        keypad = state.apply_keypad_display(1, keypad_report(), "2026-08-30T16:00:00-04:00")
        state.apply_system_event(event("31", zone=10))
        state.apply_system_event(event("31", zone=11))
        state.apply_system_event(event("32", zone=10))
        self.assertTrue(state.partitions[1].audible_panic_alarm_active)
        self.assertTrue(keypad.audible_panic_alarm)
        self.assertEqual(keypad.sound_mode, "panic_audible")

        state.apply_system_event(event("32", zone=11))
        self.assertFalse(state.partitions[1].audible_panic_alarm_active)
        self.assertFalse(keypad.audible_panic_alarm)

    def test_disarm_clears_audible_panic_state(self):
        state = VistaState()
        keypad = state.apply_keypad_display(1, keypad_report(), "2026-08-30T16:00:00-04:00")
        state.apply_system_event(event("31"))
        state.apply_system_event(event("08", zone=0))
        self.assertFalse(state.partitions[1].audible_panic_alarm_active)
        self.assertFalse(keypad.audible_panic_alarm)
        self.assertEqual(keypad.sound_mode, "none")

    def test_audible_panic_has_keypad_and_panel_discovery(self):
        keypad = keypad_alarm_configs(1, topic)["panic_audible"]
        self.assertEqual(keypad["name"], "Partition 1 Audible Panic Alarm")
        self.assertEqual(keypad["state_topic"], "vista128/keypad/1/alarm/panic_audible")

        panel = panel_alarm_configs(topic)["panic_audible"]
        self.assertEqual(panel["name"], "Audible Panic Alarm")
        self.assertEqual(panel["state_topic"], "vista128/alarm/panic_audible")


if __name__ == "__main__":
    unittest.main()
