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
from vista_bridge.state import VistaState, ZoneState  # noqa: E402
from vista_bridge.version import VERSION  # noqa: E402


class MqttPublisherTests(unittest.TestCase):
    def setUp(self):
        self.publisher = MqttPublisher(make_settings(), lambda data: (True, "queued"))

    def test_discovery_uses_runtime_version(self):
        self.publisher.publish_discovery()
        payloads = [json.loads(item[1]) for item in self.publisher._client.published]
        self.assertTrue(payloads)
        self.assertTrue(all(item["origin"]["sw_version"] == VERSION for item in payloads))

    def test_zone_discovery_keeps_topic_contract(self):
        zone = ZoneState(21, partition=1, descriptor="FRONT DOOR")
        self.publisher.publish_zone_discovery(zone)
        topic, payload, qos, retain = self.publisher._client.published[-1]
        self.assertEqual(
            topic,
            "homeassistant/binary_sensor/vista128_bridge/zone_021/config",
        )
        config = json.loads(payload)
        self.assertEqual(config["state_topic"], "vista128/zone/021/state")
        self.assertEqual(config["name"], "021 FRONT DOOR")
        self.assertEqual(qos, 1)
        self.assertTrue(retain)

    def test_zone_summary_discovery_uses_count_and_attributes_topics(self):
        self.publisher.publish_discovery()
        expected_topic = "homeassistant/sensor/vista128_bridge/bypassed_zones/config"
        match = next(
            item for item in self.publisher._client.published if item[0] == expected_topic
        )
        config = json.loads(match[1])
        self.assertEqual(config["name"], "Bypassed Zones")
        self.assertEqual(config["state_topic"], "vista128/zone_summary/bypassed/count")
        self.assertEqual(
            config["json_attributes_topic"],
            "vista128/zone_summary/bypassed/attributes",
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
        self.assertEqual(published["vista128/zone_summary/bypassed/count"], 2)
        attributes = json.loads(
            published["vista128/zone_summary/bypassed/attributes"]
        )
        self.assertEqual(attributes["zone_numbers"], [21, 34])
        self.assertEqual(attributes["zones"][0]["descriptor"], "FRONT DOOR")
        self.assertEqual(attributes["zones"][1]["partition"], 1)


if __name__ == "__main__":
    unittest.main()
