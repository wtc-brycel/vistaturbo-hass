import json
import os
import sys
import unittest
from dataclasses import replace
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))
sys.path.insert(0, os.path.dirname(__file__))

from fake_paho import install_fake_paho  # noqa: E402

install_fake_paho()

from helpers import make_settings  # noqa: E402
from vista_bridge.mqtt_client import MqttPublisher  # noqa: E402
from vista_bridge.state import KeypadState, VistaState, ZoneState  # noqa: E402
from vista_bridge.version import VERSION  # noqa: E402


class MqttPublisherTests(unittest.TestCase):
    def setUp(self):
        self.publisher = MqttPublisher(make_settings(), lambda data: (True, "queued"))

    def test_discovery_uses_runtime_version(self):
        self.publisher.publish_discovery()
        payloads = [
            json.loads(item[1])
            for item in self.publisher._client.published
            if item[1]
        ]
        self.assertTrue(payloads)
        self.assertTrue(all(item["origin"]["sw_version"] == VERSION for item in payloads))

    def test_keypad_discovery_and_state(self):
        self.publisher.publish_discovery()
        topic = "homeassistant/sensor/vista128_bridge/keypad_1/config"
        match = next(
            item for item in self.publisher._client.published
            if item[0] == topic and item[1]
        )
        config = json.loads(match[1])
        self.assertEqual(config["name"], "Partition 1 Keypad")
        self.assertEqual(config["state_topic"], "vista128/keypad/1/state")
        self.assertEqual(
            config["json_attributes_topic"],
            "vista128/keypad/1/attributes",
        )

        keypad = KeypadState(
            partition=1,
            initialized=True,
            session_fresh=True,
            line_1="P1   DISARMED   ",
            line_2="BYPAS-RDY TO ARM",
            backlight=True,
            ready_led=True,
            led_status=1,
            raw_display=b"\xd01   DISARMED   BYPAS-RDY TO ARM",
            updated_at="2026-08-16T13:22:28-04:00",
        )
        self.publisher.publish_keypad_state(keypad)
        published = {item[0]: item[1] for item in self.publisher._client.published}
        self.assertEqual(
            published["vista128/keypad/1/state"],
            "P1   DISARMED | BYPAS-RDY TO ARM",
        )
        attributes = json.loads(published["vista128/keypad/1/attributes"])
        self.assertEqual(attributes["line_1"], "P1   DISARMED   ")
        self.assertEqual(attributes["line_2"], "BYPAS-RDY TO ARM")
        self.assertTrue(attributes["backlight"])
        self.assertTrue(attributes["ready"])
        self.assertNotIn("raw_display_hex", attributes)

    def test_keypad_alarm_binary_sensor_discovery_and_state(self):
        self.publisher.publish_keypad_discovery(1)
        configs = {
            item[0]: json.loads(item[1])
            for item in self.publisher._client.published
            if item[1] and item[0].startswith("homeassistant/binary_sensor/")
        }
        expected = {
            "fire": "Partition 1 Fire Alarm",
            "panic_audible": "Partition 1 Audible Panic Alarm",
            "burglary": "Partition 1 Burglary Alarm",
            "auxiliary": "Partition 1 Auxiliary Alarm",
            "active": "Partition 1 Alarm Active",
        }
        for alarm_type, name in expected.items():
            topic = (
                "homeassistant/binary_sensor/vista128_bridge/"
                f"keypad_1_alarm_{alarm_type}/config"
            )
            self.assertIn(topic, configs)
            self.assertEqual(configs[topic]["name"], name)
            self.assertEqual(
                configs[topic]["state_topic"],
                f"vista128/keypad/1/alarm/{alarm_type}",
            )
            self.assertEqual(configs[topic]["availability_mode"], "all")
            self.assertEqual(len(configs[topic]["availability"]), 3)

        keypad = KeypadState(
            partition=1,
            initialized=True,
            session_fresh=True,
            fire_alarm_led=True,
            audible_panic_alarm=False,
            burglary_alarm_led=False,
            auxiliary_alarm_led=False,
        )
        state = VistaState()
        state.keypads[1] = keypad
        self.publisher.publish_keypad_state(keypad)
        self.publisher.publish_alarm_states(state)
        published = {item[0]: item[1] for item in self.publisher._client.published}
        self.assertEqual(published["vista128/keypad/1/alarm/fire"], "ON")
        self.assertEqual(published["vista128/keypad/1/alarm/panic_audible"], "OFF")
        self.assertEqual(published["vista128/keypad/1/alarm/burglary"], "OFF")
        self.assertEqual(published["vista128/keypad/1/alarm/auxiliary"], "OFF")
        self.assertEqual(published["vista128/keypad/1/alarm/active"], "ON")
        attrs = json.loads(published["vista128/keypad/1/alarm/active/attributes"])
        self.assertEqual(attrs["active_types"], ["fire"])
        self.assertTrue(attrs["fire_alarm"])

    def test_keypad_alarm_binary_sensors_are_unavailable_while_state_is_unknown(self):
        keypad = KeypadState(partition=1, initialized=True)
        state = VistaState()
        state.keypads[1] = keypad
        self.publisher.publish_keypad_state(keypad)
        self.publisher.publish_alarm_states(state)
        published = {item[0]: item[1] for item in self.publisher._client.published}
        for alarm_type in ("fire", "panic_audible", "burglary", "auxiliary", "active"):
            self.assertEqual(
                published[f"vista128/keypad/1/alarm/{alarm_type}/available"],
                "OFF",
            )

    def test_global_alarm_sensors_or_across_all_partitions(self):
        self.publisher.publish_discovery()
        configs = {
            item[0]: json.loads(item[1])
            for item in self.publisher._client.published
            if item[1]
        }
        for alarm_type, name in {
            "fire": "Fire Alarm",
            "panic_audible": "Audible Panic Alarm",
            "burglary": "Burglary Alarm",
            "auxiliary": "Auxiliary Alarm",
            "active": "Alarm Active",
        }.items():
            topic = f"homeassistant/binary_sensor/vista128_bridge/alarm_{alarm_type}/config"
            self.assertIn(topic, configs)
            self.assertEqual(configs[topic]["name"], name)

        state = VistaState()
        state.keypads[1].fire_alarm_led = False
        state.keypads[1].audible_panic_alarm = False
        state.keypads[1].burglary_alarm_led = False
        state.keypads[1].auxiliary_alarm_led = False
        # Partition 4 is not a configured keypad partition, but a live alarm there
        # must still drive the panel-level aggregate immediately.
        state.keypads[4].fire_alarm_led = True
        self.publisher.publish_alarm_states(state)
        published = {item[0]: item[1] for item in self.publisher._client.published}
        self.assertEqual(published["vista128/alarm/fire"], "ON")
        self.assertEqual(published["vista128/alarm/fire/available"], "ON")
        self.assertEqual(published["vista128/alarm/active"], "ON")
        attrs = json.loads(published["vista128/alarm/fire/attributes"])
        self.assertEqual(attrs["active_partitions"], [4])
        aggregate = json.loads(published["vista128/alarm/active/attributes"])
        self.assertEqual(aggregate["active_types"], ["fire"])
        self.assertEqual(aggregate["active_partitions_by_type"]["fire"], [4])

    def test_global_alarm_off_requires_configured_partition_known_false(self):
        state = VistaState()
        self.publisher.publish_alarm_states(state)
        published = {item[0]: item[1] for item in self.publisher._client.published}
        self.assertEqual(published["vista128/alarm/fire/available"], "OFF")
        self.assertEqual(published["vista128/alarm/active/available"], "OFF")

        for keypad in state.keypads.values():
            keypad.session_fresh = True
            keypad.fire_alarm_led = False
            keypad.supervisory_led = False
            keypad.audible_panic_alarm = False
            keypad.burglary_alarm_led = False
            keypad.auxiliary_alarm_led = False
        state.arming_initialized = True
        state.zone_status_blocks_seen.update({1, 2})
        state.zone_partition_blocks_seen.update({1, 2})
        state.zone_status_initialized = True
        state.zone_partition_initialized = True
        state.mark_authoritative_snapshot()
        self.publisher.publish_alarm_states(state)
        published = {item[0]: item[1] for item in self.publisher._client.published}
        self.assertEqual(published["vista128/alarm/fire/available"], "ON")
        self.assertEqual(published["vista128/alarm/fire"], "OFF")
        self.assertEqual(published["vista128/alarm/panic_audible/available"], "ON")
        self.assertEqual(published["vista128/alarm/panic_audible"], "OFF")
        self.assertEqual(published["vista128/alarm/active/available"], "ON")
        self.assertEqual(published["vista128/alarm/active"], "OFF")

    def test_silent_and_duress_are_panel_alarm_entities(self):
        self.publisher.publish_discovery()
        for alarm_type in ("panic_audible", "silent", "duress", "supervisory"):
            topic = f"homeassistant/binary_sensor/vista128_bridge/alarm_{alarm_type}/config"
            self.assertTrue(any(item[0] == topic and item[1] for item in self.publisher._client.published))

    def test_discovery_tombstones_removed_partition_and_dynamic_state(self):
        self.publisher.publish("keypad/8/state", "READY", retain=True, qos=1)
        self.publisher.publish_discovery()
        published = [item for item in self.publisher._client.published if item[0] == "vista128/keypad/8/state"]
        self.assertEqual(published[-1][1], "")
        config = [
            item for item in self.publisher._client.published
            if item[0] == "homeassistant/sensor/vista128_bridge/keypad_8/config"
        ]
        self.assertEqual(config[-1][1], "")

    def test_mqtt_tls_uses_verification_and_never_adds_plaintext_fallback(self):
        settings = make_settings()
        settings = replace(
            settings,
            mqtt=replace(
                settings.mqtt,
                tls_enabled=True,
                tls_ca="/config/ca.pem",
                tls_client_cert="/config/client.pem",
                tls_client_key="/config/client.key",
            ),
        )
        publisher = MqttPublisher(settings, lambda data: (True, "queued"))
        self.assertIsNotNone(publisher._client.tls)
        kwargs = publisher._client.tls[1]
        self.assertEqual(kwargs["ca_certs"], "/config/ca.pem")
        self.assertEqual(kwargs["certfile"], "/config/client.pem")
        self.assertEqual(kwargs["keyfile"], "/config/client.key")
        self.assertEqual(kwargs["cert_reqs"], 2)  # ssl.CERT_REQUIRED

    def test_paho_outbound_queues_are_bounded(self):
        self.assertEqual(self.publisher._client.max_queued_messages, 256)
        self.assertEqual(self.publisher._client.max_inflight_messages, 20)

    def test_raw_diagnostics_are_not_discovered_by_default(self):
        self.publisher.publish_discovery()
        raw_configs = [
            item for item in self.publisher._client.published
            if item[0].endswith("/last_frame/config") and item[1]
        ]
        self.assertEqual(raw_configs, [])

    def test_raw_tx_decoder_rejects_malformed_and_oversized_input(self):
        self.assertEqual(MqttPublisher._decode_raw_tx({"hex": "4142"}), b"AB")
        for request in (
            {"hex": "0"},
            {"hex": "gg"},
            {"ascii": "é"},
            {"ascii": "A" * 513},
            {"hex": "00" * 513},
            {"hex": "4142", "ascii": "AB"},
        ):
            with self.assertRaises(ValueError):
                MqttPublisher._decode_raw_tx(request)

    def test_publish_failure_is_counted_and_logged(self):
        self.publisher._client.publish = lambda *args, **kwargs: type(
            "RejectedPublish", (), {"rc": 5}
        )()
        with self.assertLogs("vista_bridge.mqtt_client", level="ERROR") as logs:
            self.assertFalse(self.publisher.publish("alarm/active", "OFF", retain=True))
        self.assertEqual(self.publisher.publish_errors, 1)
        self.assertIn("MQTT publish rejected", "\n".join(logs.output))

    def test_tls_setup_failure_is_not_replaced_with_plaintext(self):
        settings = replace(
            make_settings(),
            mqtt=replace(make_settings().mqtt, tls_enabled=True),
        )
        with patch("vista_bridge.mqtt_client.mqtt.Client") as client_class:
            client = client_class.return_value
            client.tls_set.side_effect = RuntimeError("certificate failure")
            with self.assertRaises(RuntimeError):
                MqttPublisher(settings, lambda data: (True, "queued"))
            client.connect_async.assert_not_called()

    def test_zone_discovery_publishes_four_literal_conditions(self):
        zone = ZoneState(21, partition=1, descriptor="FRONT DOOR")
        self.publisher.publish_zone_discovery(zone)
        published = {item[0]: json.loads(item[1]) for item in self.publisher._client.published}

        expected = {
            "fault": "021 FRONT DOOR Fault",
            "alarm": "021 FRONT DOOR Alarm",
            "check": "021 FRONT DOOR Check",
            "bypass": "021 FRONT DOOR Bypass",
        }
        for condition, name in expected.items():
            topic = (
                "homeassistant/binary_sensor/vista128_bridge/"
                f"zone_021_{condition}/config"
            )
            self.assertIn(topic, published)
            self.assertEqual(published[topic]["name"], name)
            self.assertEqual(
                published[topic]["state_topic"],
                f"vista128/zone/021/{condition}",
            )

    def test_zone_state_publishes_four_independent_binary_states(self):
        zone = ZoneState(
            34,
            partition=1,
            descriptor="MAIN BEDROOM WINDOW",
            faulted=False,
            trouble=True,
            alarm=False,
            bypassed=True,
        )
        self.publisher.publish_zone_state(zone)
        published = {item[0]: item[1] for item in self.publisher._client.published}
        self.assertEqual(published["vista128/zone/034/fault"], "OFF")
        self.assertEqual(published["vista128/zone/034/alarm"], "OFF")
        self.assertEqual(published["vista128/zone/034/check"], "ON")
        self.assertEqual(published["vista128/zone/034/bypass"], "ON")

    def test_discovery_clears_legacy_combined_zone_entities(self):
        self.publisher.publish_discovery()
        published = {item[0]: item[1] for item in self.publisher._client.published}
        self.assertEqual(
            published[
                "homeassistant/binary_sensor/vista128_bridge/zone_021/config"
            ],
            "",
        )
        self.assertEqual(
            published[
                "homeassistant/sensor/vista128_bridge/faulted_zones/config"
            ],
            "",
        )
        self.assertEqual(
            published[
                "homeassistant/sensor/vista128_bridge/bypassed_zones/config"
            ],
            "",
        )

    def test_zone_summary_discovery_uses_literal_panel_terms(self):
        self.publisher.publish_discovery()
        expected = {
            "fault_zones": ("Fault Zones", "fault"),
            "alarm_zones": ("Alarm Zones", "alarm"),
            "check_zones": ("Check Zones", "check"),
            "bypass_zones": ("Bypass Zones", "bypass"),
        }
        for object_id, (name, condition) in expected.items():
            topic = f"homeassistant/sensor/vista128_bridge/{object_id}/config"
            match = next(
                item for item in self.publisher._client.published if item[0] == topic and item[1]
            )
            config = json.loads(match[1])
            self.assertEqual(config["name"], name)
            self.assertEqual(
                config["state_topic"],
                f"vista128/zone_summary/{condition}/count",
            )

    def test_zone_summary_publication_lists_matching_assigned_zones(self):
        state = VistaState()
        state.zones[21].partition = 1
        state.zones[21].descriptor = "FRONT DOOR"
        state.zones[21].bypassed = True
        state.zones[34].partition = 1
        state.zones[34].descriptor = "MAIN BEDROOM WINDOW"
        state.zones[34].bypassed = True
        state.zones[90].bypassed = True

        self.publisher.publish_zone_summaries(state)
        published = {item[0]: item[1] for item in self.publisher._client.published}
        self.assertEqual(published["vista128/zone_summary/bypass/count"], 2)
        attributes = json.loads(
            published["vista128/zone_summary/bypass/attributes"]
        )
        self.assertEqual(attributes["zone_numbers"], [21, 34])
        self.assertEqual(attributes["zones"][0]["descriptor"], "FRONT DOOR")
        self.assertEqual(attributes["zones"][1]["partition"], 1)

    def test_event_journal_discovery_survives_panel_disconnect(self):
        self.publisher.publish_discovery()
        published = {item[0]: item[1] for item in self.publisher._client.published if item[1]}
        config = json.loads(
            published["homeassistant/sensor/vista128_bridge/event_journal/config"]
        )
        self.assertEqual(config["name"], "Event Journal")
        self.assertEqual(config["state_topic"], "vista128/event_history/count")
        self.assertEqual(config["availability_topic"], "vista128/bridge/availability")
        self.assertNotIn("availability", config)

    def test_partition_control_attribute_reflects_settings(self):
        settings = make_settings(control_enabled=True, native_alarm_control_enabled=True)
        publisher = MqttPublisher(settings, lambda data: (True, "queued"))
        state = VistaState()
        publisher.publish_partition_state(state.partitions[1])
        published = {item[0]: item[1] for item in publisher._client.published}
        attrs = json.loads(published["vista128/partition/1/attributes"])
        self.assertTrue(attrs["control_enabled"])

    def test_automation_interface_has_diagnostic_discovery(self):
        self.publisher.publish_discovery()
        published = {item[0]: item[1] for item in self.publisher._client.published if item[1]}
        config = json.loads(
            published["homeassistant/binary_sensor/vista128_bridge/automation_available/config"]
        )
        self.assertEqual(config["state_topic"], "vista128/panel/automation_available")
        self.assertEqual(config["entity_category"], "diagnostic")
        self.assertEqual(config["device_class"], "connectivity")
        source = json.loads(
            published["homeassistant/sensor/vista128_bridge/automation_availability_source/config"]
        )
        self.assertEqual(source["state_topic"], "vista128/panel/automation_availability_source")


if __name__ == "__main__":
    unittest.main()
