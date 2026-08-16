import json
import os
import sys
import unittest

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
        match = next(item for item in self.publisher._client.published if item[0] == topic)
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
        self.assertEqual(attributes["raw_display_hex"].split()[0], "d0")

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


if __name__ == "__main__":
    unittest.main()
