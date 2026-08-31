import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))

from vista_bridge.protocol import (  # noqa: E402
    ArmingStatusReport,
    KeypadDisplayReport,
    SystemEvent,
    ZonePartitionReport,
    ZoneStatusReport,
)
from vista_bridge.state import VistaState  # noqa: E402


def keypad_report(
    line_1: str = "P1   DISARMED   ",
    line_2: str = "READY TO ARM    ",
    *,
    backlight: bool = True,
    ready: bool = True,
    trouble: bool = False,
    armed: bool = False,
) -> KeypadDisplayReport:
    led_status = (1 if ready else 0) | (2 if trouble else 0) | (4 if armed else 0)
    return KeypadDisplayReport(
        line_1=line_1,
        line_2=line_2,
        backlight=backlight,
        ready_led=ready,
        trouble_led=trouble,
        armed_led=armed,
        led_status=led_status,
        raw_display=(line_1 + line_2).encode("ascii", errors="replace"),
    )


class StateTests(unittest.TestCase):
    def _authoritative_no_alarm(self, state: VistaState) -> None:
        state.apply_arming_status(ArmingStatusReport(tuple("DDDDDDDD")))
        for block in (1, 2):
            state.apply_zone_partition(ZonePartitionReport(block, tuple([0] * 64)))
            state.apply_zone_status(ZoneStatusReport(block, tuple([0] * 64)))
        for partition in range(1, 9):
            state.apply_keypad_display(
                partition,
                keypad_report(
                    f"P{partition}   DISARMED"[:16].ljust(16),
                    "READY TO ARM    ",
                ),
                "2026-08-16T13:22:28-04:00",
            )
        self.assertTrue(state.mark_authoritative_snapshot())

    def test_arming_status_maps_stay_and_not_ready(self):
        state = VistaState()
        state.apply_arming_status(ArmingStatusReport(tuple("HNDDDDDD")))
        self.assertEqual(state.partitions[1].ha_state, "armed_home")
        self.assertEqual(state.partitions[2].ha_state, "disarmed")
        self.assertFalse(state.partitions[2].ready)

    def test_keypad_display_preserves_exact_lines_and_status(self):
        state = VistaState()
        report = KeypadDisplayReport(
            line_1="P1   DISARMED   ",
            line_2="BYPAS-RDY TO ARM",
            backlight=True,
            ready_led=True,
            trouble_led=False,
            armed_led=False,
            led_status=1,
            raw_display=b"\xd01   DISARMED   BYPAS-RDY TO ARM",
        )
        keypad = state.apply_keypad_display(1, report, "2026-08-16T13:22:28-04:00")
        self.assertIsNotNone(keypad)
        self.assertTrue(keypad.initialized)
        self.assertEqual(keypad.line_1, "P1   DISARMED   ")
        self.assertEqual(keypad.line_2, "BYPAS-RDY TO ARM")
        self.assertEqual(keypad.ha_state, "P1   DISARMED | BYPAS-RDY TO ARM")
        self.assertTrue(keypad.backlight)
        self.assertTrue(keypad.ready_led)
        self.assertEqual(keypad.attributes()["led_status"], "1")
        self.assertIsNone(keypad.attributes()["power"])
        self.assertFalse(keypad.attributes()["fire_alarm"])
        self.assertFalse(keypad.attributes()["silenced"])
        self.assertFalse(keypad.attributes()["supervisory"])

    def test_not_ready_arming_snapshot_does_not_clear_active_alarm_tokens(self):
        state = VistaState()
        state.partitions[1].active_alarm_tokens.add("010:31")
        state.apply_arming_status(ArmingStatusReport(tuple("NDDDDDDD")))
        self.assertEqual(state.partitions[1].ha_state, "triggered")
        self.assertTrue(state.partitions[1].active_alarm_tokens)

    def test_keypad_trouble_does_not_guess_power_without_ac_evidence(self):
        state = VistaState()
        keypad = state.apply_keypad_display(
            1,
            keypad_report("TROUBLE         ", "CHECK ZONE 005  ", ready=False, trouble=True),
            "2026-08-16T13:22:28-04:00",
        )
        self.assertIsNone(keypad.power_led)
        self.assertTrue(keypad.trouble_led)
        self.assertTrue(keypad.trouble_led_raw)

    def test_kd_page_without_trouble_bit_does_not_infer_ac_restore(self):
        state = VistaState()
        state.ac_power = False
        keypad = state.apply_keypad_display(
            1,
            keypad_report("P1   DISARMED   ", "ZONES IN TROUBLE", ready=False, trouble=False),
            "2026-08-17T17:00:19-04:00",
        )
        self.assertFalse(keypad.power_led)
        self.assertTrue(keypad.trouble_led)
        self.assertFalse(keypad.trouble_led_raw)

    def test_semantic_trouble_stays_on_across_alternating_kd_pages(self):
        state = VistaState()
        partitions = [0] * 64
        partitions[20] = 1
        state.apply_zone_partition(ZonePartitionReport(1, tuple(partitions)))
        statuses = [0] * 64
        statuses[20] = 0x2
        state.apply_zone_status(ZoneStatusReport(1, tuple(statuses)))

        keypad = state.apply_keypad_display(
            1,
            keypad_report("P1   DISARMED   ", "ZONES IN TROUBLE", ready=False, trouble=False),
            "2026-08-17T17:00:19-04:00",
        )
        self.assertTrue(keypad.trouble_led)
        self.assertFalse(keypad.trouble_led_raw)
        state.apply_keypad_display(
            1,
            keypad_report("TRBL  021 FRONT ", "DOOR            ", ready=False, trouble=True),
            "2026-08-17T17:00:34-04:00",
        )
        self.assertTrue(keypad.trouble_led)
        self.assertTrue(keypad.trouble_led_raw)
        state.apply_keypad_display(
            1,
            keypad_report("FAULT 021 FRONT ", "DOOR            ", ready=False, trouble=False),
            "2026-08-17T17:00:42-04:00",
        )
        self.assertTrue(keypad.trouble_led)
        self.assertFalse(keypad.trouble_led_raw)

    def test_ac_loss_restore_drives_cr2_power_annunciator(self):
        state = VistaState()
        keypad = state.apply_keypad_display(1, keypad_report(), "2026-08-16T13:22:28-04:00")
        self.assertIsNone(keypad.power_led)

        state.apply_system_event(SystemEvent("1B", "AC Loss", 0, 0, 0, 0, 0, 15, 8, 26))
        self.assertFalse(keypad.power_led)
        state.apply_system_event(SystemEvent("1C", "AC Restore", 0, 0, 0, 0, 0, 15, 8, 26))
        self.assertTrue(keypad.power_led)

    def test_fire_alarm_latches_until_normal_keypad_reset_state(self):
        state = VistaState()
        keypad = state.apply_keypad_display(1, keypad_report(), "2026-08-16T13:22:28-04:00")
        self.assertFalse(keypad.fire_alarm_led)

        state.apply_system_event(SystemEvent("C1", "Smoke Alarm", 5, 0, 1, 0, 0, 15, 8, 26))
        self.assertTrue(keypad.fire_alarm_led)
        state.apply_system_event(SystemEvent("C2", "Smoke Alarm Restore", 5, 0, 1, 0, 0, 15, 8, 26))
        self.assertTrue(keypad.fire_alarm_led)

        state.apply_keypad_display(1, keypad_report(), "2026-08-16T13:23:00-04:00")
        self.assertFalse(keypad.fire_alarm_led)
        self.assertFalse(keypad.silenced_led)

    def test_fire_alarm_silenced_is_reconstructed_from_keypad_display(self):
        state = VistaState()
        keypad = state.apply_keypad_display(1, keypad_report(), "2026-08-16T13:22:28-04:00")
        state.apply_system_event(SystemEvent("01", "Fire Alarm", 5, 0, 1, 0, 0, 15, 8, 26))
        state.apply_keypad_display(
            1,
            keypad_report(
                "FIRE ALARM      ",
                "SILENCED        ",
                ready=False,
                trouble=True,
            ),
            "2026-08-16T13:22:40-04:00",
        )
        self.assertTrue(keypad.fire_alarm_led)
        self.assertTrue(keypad.silenced_led)
        self.assertTrue(state.partitions[1].fire_silenced)

    def test_auxiliary_is_distinct_from_burglary_and_audible_panic(self):
        state = VistaState()
        keypad = state.keypads[1]
        keypad.initialized = True
        keypad.fire_alarm_led = False
        keypad.silenced_led = False
        keypad.burglary_alarm_led = False
        keypad.auxiliary_alarm_led = False

        state.apply_system_event(SystemEvent("31", "Audible Alarm", 10, 0, 1, 0, 0, 15, 8, 26))
        self.assertFalse(keypad.burglary_alarm_led)
        self.assertFalse(keypad.auxiliary_alarm_led)
        self.assertIn("panic_audible", state.partitions[1].alarm_types())
        self.assertNotIn("burglary", state.partitions[1].alarm_types())
        state.apply_system_event(SystemEvent("32", "Audible Alarm Restore", 10, 0, 1, 0, 0, 15, 8, 26))
        self.assertNotIn("panic_audible", state.partitions[1].alarm_types())

        state.apply_system_event(SystemEvent("B1", "24 Hour Auxiliary Alarm", 11, 0, 1, 0, 0, 15, 8, 26))
        self.assertTrue(keypad.auxiliary_alarm_led)
        self.assertFalse(keypad.burglary_alarm_led)
        self.assertEqual(keypad.sound_mode, "auxiliary")
        self.assertIn("auxiliary", state.partitions[1].alarm_types())
        self.assertNotIn("burglary", state.partitions[1].alarm_types())
        state.apply_system_event(SystemEvent("B2", "24 Hour Auxiliary Alarm Restore", 11, 0, 1, 0, 0, 15, 8, 26))
        self.assertFalse(keypad.auxiliary_alarm_led)
        self.assertEqual(keypad.sound_mode, "none")
        self.assertNotIn("auxiliary", state.partitions[1].alarm_types())

    def test_burglary_event_families_do_not_set_auxiliary(self):
        families = (
            ("41", "42", "Perimeter Alarm"),
            ("51", "52", "Interior Alarm"),
            ("61", "62", "24 Hour Burglary Alarm"),
            ("71", "72", "Day/Night Burglary Alarm"),
            ("81", "82", "Entry/Exit Burglary Alarm"),
        )
        for start, restore, description in families:
            with self.subTest(start=start):
                state = VistaState()
                keypad = state.keypads[1]
                keypad.burglary_alarm_led = False
                keypad.auxiliary_alarm_led = False
                state.apply_system_event(SystemEvent(start, description, 12, 0, 1, 0, 0, 15, 8, 26))
                self.assertTrue(state.partitions[1].burglary_alarm_active)
                self.assertFalse(state.partitions[1].auxiliary_alarm_active)
                self.assertTrue(keypad.burglary_alarm_led)
                self.assertFalse(keypad.auxiliary_alarm_led)
                state.apply_system_event(SystemEvent(restore, f"{description} Restore", 12, 0, 1, 0, 0, 15, 8, 26))
                self.assertFalse(state.partitions[1].burglary_alarm_active)
                self.assertFalse(keypad.burglary_alarm_led)

    def test_silent_and_duress_events_do_not_drive_burglary_speaker_state(self):
        state = VistaState()
        keypad = state.keypads[1]
        keypad.burglary_alarm_led = False
        keypad.auxiliary_alarm_led = False
        keypad.fire_alarm_led = False
        keypad.silenced_led = False
        state.apply_system_event(SystemEvent("21", "Silent Alarm", 12, 0, 1, 0, 0, 15, 8, 26))
        state.apply_system_event(SystemEvent("11", "Duress Alarm", 0, 1, 1, 0, 0, 15, 8, 26))
        self.assertFalse(keypad.burglary_alarm_led)
        self.assertEqual(keypad.sound_mode, "none")

    def test_silent_alarm_forces_panel_aggregate_on(self):
        state = VistaState()
        state.apply_system_event(SystemEvent("21", "Silent Alarm", 12, 0, 1, 0, 0, 15, 8, 26))
        alarm = state.panel_alarm_states()
        self.assertTrue(alarm["active"])
        self.assertTrue(alarm["values"]["silent"])

    def test_duress_alarm_forces_panel_aggregate_on(self):
        state = VistaState()
        state.apply_system_event(SystemEvent("11", "Duress Alarm", 0, 1, 1, 0, 0, 15, 8, 26))
        alarm = state.panel_alarm_states()
        self.assertTrue(alarm["active"])
        self.assertTrue(alarm["values"]["duress"])

    def test_unconfigured_partition_alarm_cannot_report_false_off(self):
        state = VistaState()
        state.apply_system_event(SystemEvent("31", "Audible Alarm", 9, 0, 4, 0, 0, 15, 8, 26))
        self.assertTrue(state.panel_alarm_states()["active"])

    def test_incomplete_panel_knowledge_is_unknown(self):
        state = VistaState()
        self.assertIsNone(state.panel_alarm_states()["active"])

    def test_incomplete_keypad_alarm_knowledge_is_unknown(self):
        state = VistaState()
        self._authoritative_no_alarm(state)
        state.keypads[8].supervisory_led = None
        state.security_snapshot_complete = False
        self.assertTrue(state.mark_authoritative_snapshot())
        self.assertFalse(state.alarm_knowledge_complete)
        self.assertIsNone(state.panel_alarm_states()["active"])

    def test_complete_no_alarm_snapshot_reports_off(self):
        state = VistaState()
        self._authoritative_no_alarm(state)
        self.assertFalse(state.panel_alarm_states()["active"])

    def test_reconnect_invalidates_security_freshness_without_losing_durable_state(self):
        state = VistaState()
        state.apply_arming_status(ArmingStatusReport(tuple("DDDDDDDD")))
        state.keypads[1].line_1 = "P1   DISARMED   "
        state.keypads[1].initialized = True
        state.last_event = SystemEvent("07", "Close (Arm)", 0, 1, 1, 0, 0, 15, 8, 26)
        state.reset_connection_derived_annunciators()
        self.assertFalse(state.arming_initialized)
        self.assertFalse(state.keypads[1].session_fresh)
        self.assertIsNone(state.panel_alarm_states()["active"])
        self.assertEqual(state.keypads[1].line_1, "P1   DISARMED   ")
        self.assertIsNotNone(state.last_event)

    def test_supervisory_start_restore_drives_cr2_annunciator(self):
        state = VistaState()
        keypad = state.apply_keypad_display(1, keypad_report(), "2026-08-16T13:22:28-04:00")
        state.apply_system_event(SystemEvent("43", "Supervisory Alarm", 12, 0, 1, 0, 0, 15, 8, 26))
        self.assertTrue(keypad.supervisory_led)
        state.apply_system_event(SystemEvent("44", "Supervisory Alarm Restore", 12, 0, 1, 0, 0, 15, 8, 26))
        self.assertFalse(keypad.supervisory_led)

    def test_zone_snapshot_bitmask(self):
        state = VistaState()
        state.apply_zone_partition(ZonePartitionReport(1, tuple([1] + [0] * 63)))
        state.apply_zone_status(ZoneStatusReport(1, tuple([0xB] + [0] * 63)))
        zone = state.zones[1]
        self.assertTrue(zone.faulted)
        self.assertTrue(zone.trouble)
        self.assertFalse(zone.alarm)
        self.assertTrue(zone.bypassed)
        self.assertTrue(zone.active)

    def test_zone_summaries_only_use_snapshot_conditions_and_assigned_zones(self):
        state = VistaState()
        partitions = [1, 1] + [0] * 62
        statuses = [0xB, 0x4, 0x8] + [0] * 61
        state.apply_zone_partition(ZonePartitionReport(1, tuple(partitions)))
        state.apply_zone_status(ZoneStatusReport(1, tuple(statuses)))

        self.assertEqual([zone.zone for zone in state.assigned_zones_with("faulted")], [1])
        self.assertEqual([zone.zone for zone in state.assigned_zones_with("trouble")], [1])
        self.assertEqual([zone.zone for zone in state.assigned_zones_with("alarm")], [2])
        self.assertEqual([zone.zone for zone in state.assigned_zones_with("bypassed")], [1])
        with self.assertRaises(ValueError):
            state.assigned_zones_with("low_battery")

    def test_arm_stay_event_updates_partition(self):
        state = VistaState()
        event = SystemEvent("B7", "Arm STAY", 0, 2, 1, 21, 3, 15, 8, 26)
        _, changed_partitions = state.apply_system_event(event)
        self.assertIn(1, changed_partitions)
        self.assertEqual(state.partitions[1].ha_state, "armed_home")

    def test_fault_restore_event_updates_zone(self):
        state = VistaState()
        state.apply_zone_partition(ZonePartitionReport(1, tuple([1] + [0] * 63)))
        fault = SystemEvent("F5", "Fault", 1, 0, 1, 0, 0, 15, 8, 26)
        changed, _ = state.apply_system_event(fault)
        self.assertIn(1, changed)
        self.assertTrue(state.zones[1].faulted)
        self.assertEqual(state.zones[1].raw_status & 0x1, 1)

        restore = SystemEvent("F6", "Fault Restore", 1, 0, 1, 0, 0, 15, 8, 26)
        state.apply_system_event(restore)
        self.assertFalse(state.zones[1].faulted)
        self.assertEqual(state.zones[1].raw_status & 0x1, 0)

    def test_silent_alarm_triggers_partition_until_restore(self):
        state = VistaState()
        alarm = SystemEvent("21", "Silent Alarm", 0, 0, 1, 0, 0, 15, 8, 26)
        state.apply_system_event(alarm)
        self.assertEqual(state.partitions[1].ha_state, "triggered")
        restore = SystemEvent("22", "Silent Alarm Restore", 0, 0, 1, 0, 0, 15, 8, 26)
        state.apply_system_event(restore)
        self.assertEqual(state.partitions[1].ha_state, "disarmed")

    def test_captured_bypass_event_updates_zone_attribute(self):
        state = VistaState()
        partitions = [0] * 64
        partitions[33] = 1
        state.apply_zone_partition(ZonePartitionReport(1, tuple(partitions)))
        bypass = SystemEvent("05", "Bypass", 34, 2, 1, 44, 23, 15, 8, 26)
        changed, _ = state.apply_system_event(bypass)
        self.assertIn(34, changed)
        self.assertTrue(state.zones[34].bypassed)
        self.assertEqual(state.zones[34].raw_status & 0x8, 0x8)
        self.assertFalse(state.zones[34].active)


if __name__ == "__main__":
    unittest.main()
