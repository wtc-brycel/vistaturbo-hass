import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))

from vista_bridge.protocol import (  # noqa: E402
    ArmingStatusReport,
    ZonePartitionReport,
    ZoneStatusReport,
)
from vista_bridge.state import VistaState  # noqa: E402


class SnapshotFreshnessTests(unittest.TestCase):
    @staticmethod
    def _set_keypad_alarm_state_known(state: VistaState, partition: int) -> None:
        keypad = state.keypads[partition]
        keypad.session_fresh = True
        keypad.fire_alarm_led = False
        keypad.supervisory_led = False
        keypad.burglary_alarm_led = False
        keypad.auxiliary_alarm_led = False
        keypad.audible_panic_alarm = False

    def test_core_snapshot_can_be_fresh_before_alarm_knowledge_is_complete(self) -> None:
        state = VistaState()
        state.apply_arming_status(ArmingStatusReport(tuple("DDDDDDDD")))
        for block in (1, 2):
            state.apply_zone_partition(ZonePartitionReport(block, tuple([0] * 64)))
            state.apply_zone_status(ZoneStatusReport(block, tuple([0] * 64)))

        self.assertTrue(state.mark_authoritative_snapshot())
        self.assertTrue(state.live_snapshot_complete)
        self.assertFalse(state.alarm_knowledge_complete)

    def test_core_snapshot_becomes_stale_when_zone_snapshot_is_invalidated(self) -> None:
        state = VistaState()
        state.apply_arming_status(ArmingStatusReport(tuple("DDDDDDDD")))
        for block in (1, 2):
            state.apply_zone_partition(ZonePartitionReport(block, tuple([0] * 64)))
            state.apply_zone_status(ZoneStatusReport(block, tuple([0] * 64)))
        self.assertTrue(state.mark_authoritative_snapshot())

        state.begin_query_snapshot("zone_status")
        self.assertFalse(state.mark_authoritative_snapshot())
        self.assertFalse(state.live_snapshot_complete)

    def test_alarm_completeness_requires_only_partitions_present_in_zone_map(self) -> None:
        state = VistaState()
        state.apply_arming_status(ArmingStatusReport(tuple("DDDDDDDD")))
        block_one_partitions = [0] * 64
        block_one_partitions[0] = 1
        state.apply_zone_partition(ZonePartitionReport(1, tuple(block_one_partitions)))
        state.apply_zone_partition(ZonePartitionReport(2, tuple([0] * 64)))
        for block in (1, 2):
            state.apply_zone_status(ZoneStatusReport(block, tuple([0] * 64)))
        self._set_keypad_alarm_state_known(state, 1)

        self.assertEqual(state.alarm_keypad_partitions, (1,))
        self.assertTrue(state.mark_authoritative_snapshot())
        self.assertTrue(state.alarm_knowledge_complete)

    def test_alarm_completeness_stays_fail_safe_for_another_mapped_partition(self) -> None:
        state = VistaState()
        state.apply_arming_status(ArmingStatusReport(tuple("DDDDDDDD")))
        block_one_partitions = [0] * 64
        block_one_partitions[0] = 1
        block_one_partitions[1] = 2
        state.apply_zone_partition(ZonePartitionReport(1, tuple(block_one_partitions)))
        state.apply_zone_partition(ZonePartitionReport(2, tuple([0] * 64)))
        for block in (1, 2):
            state.apply_zone_status(ZoneStatusReport(block, tuple([0] * 64)))
        self._set_keypad_alarm_state_known(state, 1)

        self.assertEqual(state.alarm_keypad_partitions, (1, 2))
        self.assertTrue(state.mark_authoritative_snapshot())
        self.assertFalse(state.alarm_knowledge_complete)


if __name__ == "__main__":
    unittest.main()
