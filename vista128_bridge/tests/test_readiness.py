import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))

from vista_bridge.mqtt_discovery import keypad_config, partition_config, zone_summary_entities
from vista_bridge.protocol import KeypadDisplayReport, SystemEvent
from vista_bridge.state import VistaState


def topic(suffix: str) -> str:
    return f"vista128/{suffix}"


def keypad_report(line1="P1   DISARMED   ", line2="READY TO ARM    ", *, ready=True, trouble=False):
    return KeypadDisplayReport(
        line_1=line1,
        line_2=line2,
        backlight=True,
        ready_led=ready,
        trouble_led=trouble,
        armed_led=False,
        led_status=(1 if ready else 0) | (2 if trouble else 0),
        raw_display=b"\xd0" + (line1 + line2).encode("ascii", errors="replace"),
    )


def event(code: str, zone=0, partition=1) -> SystemEvent:
    return SystemEvent(code, code, zone, 0, partition, 0, 0, 15, 8, 26)


class ReadinessTests(unittest.TestCase):
    def test_panel_entities_require_bridge_and_panel_availability(self):
        expected = [
            {
                "topic": "vista128/bridge/availability",
                "payload_available": "online",
                "payload_not_available": "offline",
            },
            {
                "topic": "vista128/panel/connected",
                "payload_available": "ON",
                "payload_not_available": "OFF",
            },
        ]
        for config in (
            keypad_config(1, topic),
            partition_config(1, topic),
            next(iter(zone_summary_entities(topic).values())),
        ):
            self.assertEqual(config["availability_mode"], "all")
            self.assertEqual(config["availability"], expected)

    def test_power_up_report_does_not_invent_ac_state(self):
        state = VistaState()
        state.apply_system_event(event("0E", partition=0))
        self.assertIsNone(state.ac_power)
        state.apply_system_event(event("1C", partition=0))
        self.assertTrue(state.ac_power)

    def test_reconnect_discards_event_derived_cr2_state(self):
        state = VistaState()
        keypad = state.apply_keypad_display(1, keypad_report(), "2026-08-16T13:22:28-04:00")
        state.apply_system_event(event("1B", partition=0))
        state.apply_system_event(event("C1", zone=5))
        state.apply_system_event(event("43", zone=12))
        self.assertFalse(keypad.power_led)
        self.assertTrue(keypad.fire_alarm_led)
        self.assertTrue(keypad.supervisory_led)

        state.reset_connection_derived_annunciators()
        self.assertIsNone(keypad.power_led)
        self.assertIsNone(keypad.fire_alarm_led)
        self.assertIsNone(keypad.silenced_led)
        self.assertIsNone(keypad.supervisory_led)
        self.assertFalse(state.partitions[1].active_fire_tokens)
        self.assertFalse(state.partitions[1].active_supervisory_tokens)
        self.assertTrue(keypad.ready_led)

    def test_fire_latch_clears_after_restore_when_burglary_not_ready(self):
        state = VistaState()
        keypad = state.apply_keypad_display(1, keypad_report(), "2026-08-16T13:22:28-04:00")
        state.apply_system_event(event("C1", zone=5))
        state.apply_system_event(event("C2", zone=5))
        state.apply_keypad_display(
            1,
            keypad_report(
                "FAULT 005       ",
                "KITCHEN WINDOW  ",
                ready=False,
                trouble=False,
            ),
            "2026-08-16T13:23:00-04:00",
        )
        self.assertFalse(keypad.fire_alarm_led)


if __name__ == "__main__":
    unittest.main()
