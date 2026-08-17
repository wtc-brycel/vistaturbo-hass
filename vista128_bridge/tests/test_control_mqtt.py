import json
import os
import sys
import types
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))
sys.path.insert(0, os.path.dirname(__file__))

from fake_paho import install_fake_paho  # noqa: E402

install_fake_paho()

from helpers import make_settings  # noqa: E402
from vista_bridge.mqtt_client import MqttPublisher  # noqa: E402
from vista_bridge.state import KeypadState  # noqa: E402


class ControlMqttTests(unittest.TestCase):
    def test_monitor_only_partition_discovery_has_no_command_topic(self):
        publisher = MqttPublisher(make_settings(), lambda data: (True, "queued"))
        publisher.publish_partition_discovery(1)
        topic = "homeassistant/alarm_control_panel/vista128_bridge/partition_1/config"
        payload = next(item[1] for item in publisher._client.published if item[0] == topic)
        config = json.loads(payload)
        self.assertNotIn("command_topic", config)
        self.assertEqual(config["supported_features"], [])

    def test_control_partition_discovery_uses_remote_code(self):
        settings = make_settings(control_enabled=True, native_alarm_control_enabled=True)
        publisher = MqttPublisher(settings, lambda data: (True, "queued"))
        publisher.publish_partition_discovery(1)
        topic = "homeassistant/alarm_control_panel/vista128_bridge/partition_1/config"
        payload = next(item[1] for item in publisher._client.published if item[0] == topic)
        config = json.loads(payload)
        self.assertEqual(config["command_topic"], "vista128/partition/1/command")
        self.assertEqual(config["code"], "REMOTE_CODE")
        self.assertTrue(config["code_arm_required"])
        self.assertTrue(config["code_disarm_required"])
        self.assertEqual(config["supported_features"], ["arm_home", "arm_away", "arm_night"])
        self.assertIn("{{ code }}", config["command_template"])
        self.assertFalse(config["retain"])

    def test_keypad_state_advertises_command_topic_when_enabled(self):
        settings = make_settings(control_enabled=True, keypad_control_enabled=True)
        publisher = MqttPublisher(settings, lambda data: (True, "queued"))
        keypad = KeypadState(partition=1, initialized=True, line_1="DISARMED        ", line_2="READY TO ARM    ")
        publisher.publish_keypad_state(keypad)
        published = {item[0]: item[1] for item in publisher._client.published}
        attrs = json.loads(published["vista128/keypad/1/attributes"])
        self.assertTrue(attrs["control_enabled"])
        self.assertEqual(attrs["command_topic"], "vista128/keypad/1/command")

    def test_keypad_message_invokes_callback(self):
        received = []
        settings = make_settings(control_enabled=True, keypad_control_enabled=True)
        publisher = MqttPublisher(
            settings,
            lambda data: (True, "queued"),
            lambda partition, key: (received.append((partition, key)) or True, "queued"),
        )
        message = types.SimpleNamespace(topic="vista128/keypad/1/command", payload=b"7")
        publisher._on_message(None, None, message)
        self.assertEqual(received, [(1, "7")])

    def test_alarm_message_passes_remote_code_to_callback_only(self):
        received = []
        settings = make_settings(control_enabled=True, native_alarm_control_enabled=True)
        publisher = MqttPublisher(
            settings,
            lambda data: (True, "queued"),
            None,
            lambda partition, action, code: (received.append((partition, action, code)) or True, "queued"),
        )
        message = types.SimpleNamespace(
            topic="vista128/partition/1/command",
            payload=b'{"action":"ARM_AWAY","code":"1234"}',
        )
        publisher._on_message(None, None, message)
        self.assertEqual(received, [(1, "ARM_AWAY", "1234")])
        published_payloads = [str(item[1]) for item in publisher._client.published]
        self.assertFalse(any("1234" in item for item in published_payloads))

    def test_connect_subscribes_only_enabled_control_topics(self):
        settings = make_settings(
            control_enabled=True,
            keypad_control_enabled=True,
            native_alarm_control_enabled=True,
        )
        publisher = MqttPublisher(settings, lambda data: (True, "queued"))
        publisher._on_connect(publisher._client, None, None, 0, None)
        subscriptions = {topic for topic, _ in publisher._client.subscriptions}
        self.assertIn("vista128/keypad/+/command", subscriptions)
        self.assertIn("vista128/partition/+/command", subscriptions)


if __name__ == "__main__":
    unittest.main()
