"""Replay bypass evidence without guessing clears or issuing panel polls."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'app'))
sys.path.insert(0, os.path.dirname(__file__))
from fake_paho import install_fake_paho
install_fake_paho()
from vista_bridge.bridge import VistaBridge
from vista_bridge.protocol import ArmingStatusReport, SystemEvent, ZonePartitionReport, ZoneStatusReport
from vista_bridge.state import VistaState


def event(code, zone):
    return SystemEvent(code, 'Fixture event', zone, 0, 1, 0, 12, 7, 10, 26)


def full_snapshot(state, bypassed=()):
    state.apply_arming_status(ArmingStatusReport(('D',) * 8))
    for block in (1, 2):
        state.apply_zone_status(ZoneStatusReport(block, tuple(
            8 if (block - 1) * 64 + offset + 1 in bypassed else 0
            for offset in range(64)
        )), '2026-10-07T12:00:00+00:00')
        state.apply_zone_partition(ZonePartitionReport(block, (1,) * 64))


class Delivery:
    def __init__(self):
        self.connected = True
        self.publish_errors = 0
        self.calls = []
        self.replays = 0
        self.fail_summary_once = False
        self.fail_fresh_once = False

    def publish(self, topic, value, **kwargs):
        self.calls.append((topic, value))
        if topic == 'panel/state_fresh' and self.fail_fresh_once:
            self.fail_fresh_once = False
            self.publish_errors += 1
            return False
        return True

    def publish_partition_state(self, partition):
        pass

    def publish_zone_state(self, zone):
        self.calls.append(('zone', (zone.zone, zone.bypassed)))

    def publish_zone_summaries(self, state):
        if self.fail_summary_once:
            self.fail_summary_once = False
            self.publish_errors += 1
            return
        self.calls.append(('summary', tuple(z.zone for z in state.assigned_zones_with('bypassed'))))

    def publish_alarm_states(self, state):
        self.calls.append(('alarm', state.alarm_knowledge_complete))

    def request_recovery_replay(self):
        self.replays += 1


class BypassDeliveryTests(unittest.TestCase):
    def bridge(self):
        bridge = VistaBridge.__new__(VistaBridge)
        bridge.state = VistaState()
        full_snapshot(bridge.state, (64, 65, 128))
        bridge.mqtt = Delivery()
        return bridge

    def test_snapshot_publishes_zone_values_and_summary_before_freshness(self):
        bridge = self.bridge()
        bridge._on_snapshot_check()
        self.assertEqual(bridge.mqtt.calls[-1], ('panel/state_fresh', 'ON'))
        self.assertIn(('summary', (64, 65, 128)), bridge.mqtt.calls)
        self.assertIn(('zone', (65, True)), bridge.mqtt.calls)

    def test_rejected_summary_keeps_delivery_unavailable_and_requests_replay(self):
        bridge = self.bridge()
        bridge.mqtt.fail_summary_once = True
        bridge._on_snapshot_check()
        self.assertEqual(bridge.mqtt.calls[-1], ('panel/state_fresh', 'OFF'))
        self.assertEqual(bridge.mqtt.replays, 1)
        self.assertTrue(bridge.state.zones[65].bypassed)
        bridge._on_snapshot_check()
        self.assertIn(('summary', (64, 65, 128)), bridge.mqtt.calls)
        self.assertEqual(bridge.mqtt.calls[-1], ('panel/state_fresh', 'ON'))

    def test_periodic_delivery_repairs_summary_without_changing_panel_state(self):
        bridge = self.bridge()
        bridge.mqtt.fail_summary_once = True
        bridge._publish_dynamic_state()
        bridge.mqtt.calls.clear()
        bridge._publish_dynamic_state()
        self.assertIn(('summary', (64, 65, 128)), bridge.mqtt.calls)
        self.assertTrue(bridge.state.live_snapshot_complete)

    def test_partial_or_disconnected_snapshot_never_marks_delivery_fresh(self):
        bridge = self.bridge()
        bridge.state.begin_query_snapshot('zone_status')
        bridge._on_snapshot_check()
        self.assertNotIn(('summary', (64, 65, 128)), bridge.mqtt.calls)
        self.assertEqual(bridge.mqtt.calls[-1], ('panel/state_fresh', 'OFF'))
        full_snapshot(bridge.state)
        bridge.mqtt.connected = False
        bridge._on_snapshot_check()
        self.assertEqual(bridge.mqtt.calls[-1], ('panel/state_fresh', 'OFF'))
        self.assertEqual(bridge.mqtt.replays, 1)

    def test_rejected_freshness_publication_is_retried(self):
        bridge = self.bridge()
        bridge.mqtt.fail_fresh_once = True
        bridge._on_snapshot_check()
        self.assertEqual(bridge.mqtt.replays, 1)

    def test_zone_identity_and_explicit_bypass_restore_across_block_boundary(self):
        state = VistaState()
        full_snapshot(state, (64, 65, 128))
        state.apply_system_event(event('06', 65), '2026-10-07T12:01:00+00:00')
        self.assertEqual([z.zone for z in state.assigned_zones_with('bypassed')], [64, 128])
        self.assertEqual(state.zones[65].bypass_source, 'event_06')
        self.assertEqual(state.zones[65].bypass_reported_at, '2026-10-07T12:01:00+00:00')
        self.assertEqual(state.zones[65].raw_status & 8, 0)

    def test_disarm_or_other_zone_events_cannot_clear_a_bypass(self):
        state = VistaState()
        full_snapshot(state, (65,))
        for code in ('08', '18', '38', 'F6'):
            state.apply_system_event(event(code, 65), '2026-10-07T12:01:00+00:00')
        self.assertTrue(state.zones[65].bypassed)
        self.assertEqual(state.zones[65].bypass_source, 'zone_status')

    def test_reconnect_preserves_last_evidence_until_complete_new_snapshot(self):
        state = VistaState()
        full_snapshot(state, (65,))
        state.reset_connection_derived_annunciators()
        self.assertFalse(state.live_snapshot_complete)
        self.assertTrue(state.zones[65].bypassed)
        self.assertEqual(state.zones[65].bypass_source, 'zone_status')
        state.apply_zone_status(ZoneStatusReport(1, (0,) * 64))
        self.assertFalse(state.zone_snapshot_complete)
        self.assertTrue(state.zones[65].bypassed)
        full_snapshot(state)
        self.assertFalse(state.zones[65].bypassed)
        self.assertTrue(state.live_snapshot_complete)

    def test_repeated_event_updates_report_time_without_inventing_transition(self):
        state = VistaState()
        full_snapshot(state, (65,))
        changed, _ = state.apply_system_event(event('05', 65), '2026-10-07T12:02:00+00:00')
        self.assertEqual(changed, set())
        self.assertTrue(state.zones[65].bypassed)
        self.assertEqual(state.zones[65].bypass_source, 'event_05')
        self.assertEqual(state.zones[65].bypass_reported_at, '2026-10-07T12:02:00+00:00')
