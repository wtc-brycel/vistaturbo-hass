import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))

from vista_bridge.protocol import (  # noqa: E402
    ArmingStatusReport,
    SystemEvent,
    ZonePartitionReport,
    ZoneStatusReport,
)
from vista_bridge.state import VistaState  # noqa: E402


class StateTests(unittest.TestCase):
    def test_arming_status_maps_stay_and_not_ready(self):
        state = VistaState()
        state.apply_arming_status(ArmingStatusReport(tuple("HNDDDDDD")))
        self.assertEqual(state.partitions[1].ha_state, "armed_home")
        self.assertEqual(state.partitions[2].ha_state, "disarmed")
        self.assertFalse(state.partitions[2].ready)

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
        partitions[33] = 1  # zone 34
        state.apply_zone_partition(ZonePartitionReport(1, tuple(partitions)))
        bypass = SystemEvent("05", "Bypass", 34, 2, 1, 44, 23, 15, 8, 26)
        changed, _ = state.apply_system_event(bypass)
        self.assertIn(34, changed)
        self.assertTrue(state.zones[34].bypassed)
        self.assertEqual(state.zones[34].raw_status & 0x8, 0x8)
        self.assertFalse(state.zones[34].active)



if __name__ == "__main__":
    unittest.main()
