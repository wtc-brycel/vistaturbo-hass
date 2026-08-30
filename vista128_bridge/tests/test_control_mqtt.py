import json
import os
import sys
import types
import unittest
from dataclasses import replace

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
        keypad = KeypadState(partition=1, initialized=True, session_fresh=True, line_1="DISARMED        ", line_2="READY TO ARM    ")
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
        message = types.SimpleNamespace(topic="vista128/keypad/1/command", payload=b'{"keys":"7"}')
        publisher._on_message(None, None, message)
        self.assertEqual(received, [(1, "7")])

    def test_legacy_one_byte_keypad_message_remains_compatible(self):
        received = []
        settings = make_settings(control_enabled=True, keypad_control_enabled=True)
        publisher = MqttPublisher(
            settings,
            lambda data: (True, "queued"),
            lambda partition, key: (received.append((partition, key)) or True, "queued"),
        )
        publisher._on_message(
            None,
            None,
            types.SimpleNamespace(
                topic="vista128/keypad/1/command",
                payload=b"7",
                retain=False,
            ),
        )
        self.assertEqual(received, [(1, "7")])

    def test_keypad_message_carries_compact_actor_metadata_for_audit(self):
        received = []
        settings = make_settings(control_enabled=True, keypad_control_enabled=True)
        publisher = MqttPublisher(
            settings,
            lambda data: (True, "queued"),
            lambda partition, key, metadata: (received.append((partition, key, metadata)) or True, "queued"),
        )
        publisher._on_message(
            None,
            None,
            types.SimpleNamespace(
                topic="vista128/keypad/2/command",
                payload=(
                    b'{"keys":"1234","transaction_id":"interaction-1",'
                    b'"source":"ha_frontend","actor_id":"alice-id",'
                    b'"actor_name":"Alice"}'
                ),
            ),
        )
        self.assertEqual(received[0][0:2], (2, "1234"))
        self.assertEqual(
            {
                key: value
                for key, value in received[0][2].items()
                if key not in {"started_at", "request_id", "audit_interaction_id"}
            },
            {
                "interaction_id": "interaction-1",
                "actor_id": "alice-id",
                "actor_name": "Alice",
                "partition": 2,
                "source": "ha_frontend",
                "action": "keypad_sequence",
                "command_sequence": "1234",
                "interaction_complete": True,
            },
        )
        self.assertRegex(received[0][2]["started_at"], r"^\d{4}-\d{2}-\d{2}T")
        self.assertRegex(received[0][2]["request_id"], r"^[0-9a-f]{32}$")

    def test_rejected_keypad_interaction_is_audited_without_envelope(self):
        audit = []
        settings = make_settings(control_enabled=True, keypad_control_enabled=True)
        publisher = MqttPublisher(
            settings,
            lambda data: (True, "queued"),
            lambda partition, key, metadata: (False, "control_queue_full"),
            None,
            audit.append,
        )
        publisher._on_message(
            None,
            None,
            types.SimpleNamespace(
                topic="vista128/keypad/1/command",
                payload=b'{"keys":"1234#","transaction_id":"interaction-1"}',
                retain=False,
            ),
        )
        self.assertEqual(len(audit), 1)
        self.assertEqual(audit[0]["command_sequence"], "1234#")
        self.assertEqual(audit[0]["status"], "rejected")
        self.assertNotIn("payload", audit[0])

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

    def test_retained_control_messages_are_rejected_without_execution(self):
        keypad_received = []
        alarm_received = []
        settings = make_settings(control_enabled=True, keypad_control_enabled=True, native_alarm_control_enabled=True)
        publisher = MqttPublisher(
            settings,
            lambda data: (True, "queued"),
            lambda partition, key: (keypad_received.append((partition, key)) or True, "queued"),
            lambda partition, action, code: (alarm_received.append((partition, action, code)) or True, "queued"),
        )
        publisher._on_message(None, None, types.SimpleNamespace(topic="vista128/keypad/1/command", payload=b'{"keys":"7"}', retain=True))
        publisher._on_message(None, None, types.SimpleNamespace(topic="vista128/partition/1/command", payload=b'{"action":"DISARM","code":"1234"}', retain=True))
        self.assertEqual(keypad_received, [])
        self.assertEqual(alarm_received, [])
        published = [str(item[1]) for item in publisher._client.published]
        self.assertTrue(any("retained_control_message" in item for item in published))
        self.assertFalse(any("1234" in item for item in published))

    def test_malformed_keypad_payload_is_rejected_without_echoing_payload(self):
        received = []
        settings = make_settings(control_enabled=True, keypad_control_enabled=True)
        publisher = MqttPublisher(settings, lambda data: (True, "queued"), lambda partition, key: (received.append((partition, key)) or True, "queued"))
        publisher._on_message(None, None, types.SimpleNamespace(topic="vista128/keypad/1/command", payload=b"1234", retain=False))
        self.assertEqual(received, [])
        published = [str(item[1]) for item in publisher._client.published]
        self.assertTrue(any("keypad_payload_must_be_object" in item for item in published))
        self.assertFalse(any("1234" in item for item in published))

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

    def test_semantic_command_topic_parses_and_preserves_actor_metadata(self):
        received = []
        settings = make_settings(control_enabled=True, keypad_control_enabled=True)
        publisher = MqttPublisher(
            settings,
            lambda data: (True, "queued"),
            None,
            None,
            None,
            lambda command, metadata: (received.append((command, metadata)) or (True, "queued")),
        )
        publisher._on_connect(publisher._client, None, None, 0, None)
        subscriptions = {topic for topic, _ in publisher._client.subscriptions}
        self.assertIn("vista128/control/execute", subscriptions)
        publisher._on_message(
            None,
            None,
            types.SimpleNamespace(
                topic="vista128/control/execute",
                payload=(
                    b'{"action":"bypass_zones","partition":1,"code":"1234",'
                    b'"zones":[1,27],"source":"ha_frontend",'
                    b'"actor_id":"alice","actor_name":"Alice",'
                    b'"transaction_id":"interaction-1"}'
                ),
                retain=False,
            ),
        )
        command, metadata = received[0]
        self.assertEqual(command.command_type, "zone_bypass")
        self.assertEqual(command.operands["zones"], ["001", "027"])
        self.assertEqual(metadata["interaction_id"], "interaction-1")
        self.assertEqual(metadata["actor_name"], "Alice")
        self.assertEqual(metadata["code"], "1234")

    def test_semantic_command_rejection_does_not_echo_pin(self):
        settings = make_settings(control_enabled=True, keypad_control_enabled=True)
        publisher = MqttPublisher(
            settings,
            lambda data: (True, "queued"),
            None,
            None,
            None,
            lambda command, metadata: (False, "control_queue_full"),
        )
        publisher._on_message(
            None,
            None,
            types.SimpleNamespace(
                topic="vista128/control/execute",
                payload=b'{"action":"disarm","partition":1,"code":"1234"}',
                retain=False,
            ),
        )
        published = [str(item[1]) for item in publisher._client.published]
        self.assertTrue(any("control_queue_full" in item for item in published))
        self.assertFalse(any("1234" in item for item in published))

    def test_privileged_raw_topic_is_separate_and_explicitly_opt_in(self):
        settings = replace(make_settings(), debug_raw_tx_enabled=True)
        sent = []
        publisher = MqttPublisher(settings, lambda data: (sent.append(data) or (True, "queued")))
        publisher._on_connect(publisher._client, None, None, 0, None)
        subscriptions = {topic for topic, _ in publisher._client.subscriptions}
        self.assertIn("vista128/admin/raw_tx", subscriptions)
        self.assertNotIn("vista128/debug/tx", subscriptions)
        publisher._on_message(
            None,
            None,
            types.SimpleNamespace(
                topic="vista128/admin/raw_tx",
                payload=b'{"hex":"4142"}',
                retain=False,
            ),
        )
        self.assertEqual(sent, [b"AB"])


if __name__ == "__main__":
    unittest.main()
