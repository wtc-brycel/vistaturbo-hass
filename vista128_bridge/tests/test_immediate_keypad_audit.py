import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))
sys.path.insert(0, os.path.dirname(__file__))

from fake_paho import install_fake_paho  # noqa: E402

install_fake_paho()

from vista_bridge.mqtt_client import MqttPublisher  # noqa: E402


class ImmediateKeypadAuditTests(unittest.TestCase):
    def test_control_and_audit_interaction_ids_are_separate(self):
        metadata = MqttPublisher._transaction_metadata(
            {
                "transaction_id": "control-key-1",
                "audit_interaction_id": "audit-burst-1",
                "complete": True,
                "source": "ha_frontend",
            },
            1,
            "keypad_sequence",
        )
        self.assertEqual(metadata["interaction_id"], "control-key-1")
        self.assertEqual(metadata["audit_interaction_id"], "audit-burst-1")
        self.assertTrue(metadata["interaction_complete"])

    def test_audit_callback_uses_audit_identity_not_control_identity(self):
        captured = []
        publisher = object.__new__(MqttPublisher)
        publisher.audit_interaction_callback = captured.append
        publisher._audit_interaction(
            {
                "interaction_id": "control-key-1",
                "audit_interaction_id": "audit-burst-1",
                "request_id": "request-1",
                "command_sequence": "1",
            },
            "queued",
            False,
        )
        self.assertEqual(len(captured), 1)
        self.assertEqual(captured[0]["interaction_id"], "audit-burst-1")
        self.assertEqual(captured[0]["command_sequence"], "1")
        self.assertEqual(captured[0]["status"], "queued")


if __name__ == "__main__":
    unittest.main()
