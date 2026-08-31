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


if __name__ == "__main__":
    unittest.main()
