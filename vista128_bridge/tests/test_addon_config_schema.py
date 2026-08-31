from __future__ import annotations

from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
CONFIG_TEXT = (ROOT / "config.yaml").read_text(encoding="utf-8")
TRANSLATION_TEXT = (ROOT / "translations" / "en.yaml").read_text(encoding="utf-8")


def _mapping_keys(text: str, section: str) -> list[str]:
    keys: list[str] = []
    in_section = False
    for line in text.splitlines():
        if line == f"{section}:":
            in_section = True
            continue
        if not in_section:
            continue
        if line and not line.startswith(" "):
            break
        if line.startswith("  ") and not line.startswith("    "):
            stripped = line.strip()
            if stripped and not stripped.startswith("#") and ":" in stripped:
                keys.append(stripped.split(":", 1)[0])
    return keys


class AddonConfigSchemaTests(unittest.TestCase):
    def test_default_configuration_surface_is_small(self) -> None:
        self.assertLessEqual(len(_mapping_keys(CONFIG_TEXT, "options")), 14)
        self.assertLessEqual(len(_mapping_keys(CONFIG_TEXT, "schema")), 22)

    def test_schema_order_keeps_categories_contiguous(self) -> None:
        self.assertEqual(
            _mapping_keys(CONFIG_TEXT, "schema"),
            [
                "panel_host",
                "panel_port",
                "panel_timezone",
                "keypad_partitions",
                "control_enabled",
                "keypad_control_enabled",
                "native_alarm_control_enabled",
                "chime_zones",
                "event_history_max_age_days",
                "transport_print_enabled",
                "transport_host",
                "transport_http_port",
                "transport_print_width",
                "raw_logging",
                "raw_mqtt_enabled",
                "debug_raw_tx_enabled",
                "mqtt_base_topic",
                "mqtt_discovery_prefix",
                "mqtt_tls_enabled",
                "mqtt_tls_ca",
                "mqtt_tls_client_cert",
                "mqtt_tls_client_key",
            ],
        )

    def test_unsupported_and_engineering_settings_are_not_exposed(self) -> None:
        exposed = set(_mapping_keys(CONFIG_TEXT, "schema"))
        hidden_keys = {
            "event_history_startup_dump_enabled",
            "mqtt_outbound_queue_max",
            "mqtt_inflight_messages_max",
            "reconnect_min_seconds",
            "connect_timeout_seconds",
            "reconnect_max_seconds",
            "frame_idle_ms",
            "startup_sync_enabled",
            "startup_sync_initial_delay_ms",
            "startup_sync_command_delay_ms",
            "startup_sync_response_timeout_seconds",
            "periodic_sync_enabled",
            "periodic_sync_interval_seconds",
            "periodic_sync_reconnect_after_failures",
            "keypad_display_enabled",
            "keypad_poll_interval_seconds",
            "keypad_event_refresh_delay_ms",
            "control_response_timeout_seconds",
            "control_verify_delay_ms",
            "event_history_enabled",
            "event_history_recent_limit",
            "keypad_audit_enabled",
            "event_history_max_rows",
            "transport_print_timeout_seconds",
            "transport_print_retry_seconds",
            "transport_print_queue_max",
            "tx_queue_max",
            "raw_tx_queue_max",
        }
        self.assertTrue(hidden_keys.isdisjoint(exposed))

    def test_all_configuration_fields_have_translations(self) -> None:
        schema_keys = set(_mapping_keys(CONFIG_TEXT, "schema"))
        translation_keys = set(_mapping_keys(TRANSLATION_TEXT, "configuration"))
        self.assertTrue(schema_keys <= translation_keys)

    def test_optional_settings_are_upgrade_safe(self) -> None:
        options = set(_mapping_keys(CONFIG_TEXT, "options"))
        optional_keys = {
            "event_history_max_age_days",
            "mqtt_base_topic",
            "mqtt_discovery_prefix",
            "mqtt_tls_enabled",
            "mqtt_tls_ca",
            "mqtt_tls_client_cert",
            "mqtt_tls_client_key",
            "raw_mqtt_enabled",
        }
        schema_text = CONFIG_TEXT.split("schema:\n", 1)[1]
        for key in optional_keys:
            with self.subTest(key=key):
                self.assertIn(f"  {key}: ", schema_text)
                self.assertNotIn(key, options)
        self.assertIn('  event_history_max_age_days: "int(1,3650)?"', CONFIG_TEXT)
        self.assertIn("  raw_mqtt_enabled: bool?", CONFIG_TEXT)


if __name__ == "__main__":
    unittest.main()
