import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))

from vista_bridge.protocol import SystemEvent, ZonePartitionReport  # noqa: E402
from vista_bridge.state import VistaState  # noqa: E402


class EventZoneProjectionTests(unittest.TestCase):
    def test_nq_transitions_maintain_all_zone_status_bits_between_snapshots(self):
        state = VistaState()
        state.apply_zone_partition(ZonePartitionReport(1, tuple([1] + [0] * 63)))
        zone = state.zones[1]

        transitions = (
            ("F5", "Fault", "faulted", 0x1, True),
            ("03", "Trouble", "trouble", 0x2, True),
            ("41", "Perimeter Alarm", "alarm", 0x4, True),
            ("05", "Bypass", "bypassed", 0x8, True),
            ("F6", "Fault Restore", "faulted", 0x1, False),
            ("04", "Trouble Restore", "trouble", 0x2, False),
            ("42", "Perimeter Alarm Restore", "alarm", 0x4, False),
            ("06", "Bypass Restore", "bypassed", 0x8, False),
        )

        for code, description, attribute, bit, expected in transitions:
            with self.subTest(code=code):
                changed_zones, _ = state.apply_system_event(
                    SystemEvent(code, description, 1, 0, 1, 0, 0, 15, 8, 26)
                )
                self.assertIn(1, changed_zones)
                self.assertIs(getattr(zone, attribute), expected)
                self.assertEqual(bool(zone.raw_status & bit), expected)

        self.assertEqual(zone.raw_status, 0)


if __name__ == "__main__":
    unittest.main()
