import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))

from vista_bridge.config import MQTT_OUTBOUND_QUEUE_MIN, Settings  # noqa: E402


class ConfigTests(unittest.TestCase):
    def test_mqtt_tls_and_retention_settings_parse_from_environment(self):
        environment = {
            "PANEL_HOST": "127.0.0.1",
            "PANEL_PORT": "10001",
            "MQTT_HOST": "127.0.0.1",
            "MQTT_TLS_ENABLED": "true",
            "MQTT_TLS_CA": "/config/ca.pem",
            "MQTT_TLS_CLIENT_CERT": "/config/client.pem",
            "MQTT_TLS_CLIENT_KEY": "/config/client.key",
            "EVENT_HISTORY_MAX_AGE_DAYS": "30",
            "EVENT_HISTORY_MAX_ROWS": "500",
            "RAW_LOGGING": "false",
            "RAW_MQTT_ENABLED": "false",
            "MQTT_OUTBOUND_QUEUE_MAX": "512",
            "MQTT_INFLIGHT_MESSAGES_MAX": "32",
        }
        with patch.dict(os.environ, environment, clear=True):
            settings = Settings.from_env()
        self.assertTrue(settings.mqtt.tls_enabled)
        self.assertEqual(settings.mqtt.tls_ca, "/config/ca.pem")
        self.assertEqual(settings.mqtt.tls_client_cert, "/config/client.pem")
        self.assertEqual(settings.mqtt.tls_client_key, "/config/client.key")
        self.assertEqual(settings.event_history.max_age_days, 30)
        self.assertEqual(settings.event_history.max_rows, 500)
        self.assertFalse(settings.raw_logging)
        self.assertFalse(settings.raw_mqtt_enabled)
        self.assertEqual(settings.mqtt.outbound_queue_max, MQTT_OUTBOUND_QUEUE_MIN)
        self.assertEqual(settings.mqtt.inflight_messages_max, 32)

    def test_existing_small_mqtt_queue_is_raised_for_full_bootstrap(self):
        environment = {
            "PANEL_HOST": "127.0.0.1",
            "PANEL_PORT": "10001",
            "MQTT_HOST": "127.0.0.1",
            "MQTT_OUTBOUND_QUEUE_MAX": "256",
        }
        with patch.dict(os.environ, environment, clear=True):
            settings = Settings.from_env()
        self.assertEqual(settings.mqtt.outbound_queue_max, 4096)

    def test_larger_mqtt_queue_setting_is_preserved(self):
        environment = {
            "PANEL_HOST": "127.0.0.1",
            "PANEL_PORT": "10001",
            "MQTT_HOST": "127.0.0.1",
            "MQTT_OUTBOUND_QUEUE_MAX": "8192",
        }
        with patch.dict(os.environ, environment, clear=True):
            settings = Settings.from_env()
        self.assertEqual(settings.mqtt.outbound_queue_max, 8192)

    def test_tls_client_certificate_and_key_must_be_a_pair(self):
        environment = {
            "PANEL_HOST": "127.0.0.1",
            "PANEL_PORT": "10001",
            "MQTT_HOST": "127.0.0.1",
            "MQTT_TLS_CLIENT_CERT": "/config/client.pem",
        }
        with patch.dict(os.environ, environment, clear=True):
            with self.assertRaises(ValueError):
                Settings.from_env()


if __name__ == "__main__":
    unittest.main()
