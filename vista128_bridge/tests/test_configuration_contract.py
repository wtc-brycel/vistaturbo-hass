from __future__ import annotations

from pathlib import Path
import unittest

CONFIG_TEXT = (Path(__file__).resolve().parents[1] / "config.yaml").read_text(encoding="utf-8")


def _mapping_keys(section: str) -> list[str]:
    keys: list[str] = []
    in_section = False
    for line in CONFIG_TEXT.splitlines():
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


class ConfigurationContractTests(unittest.TestCase):
    def test_default_options_are_user_deployment_choices_only(self) -> None:
        self.assertEqual(
            _mapping_keys("options"),
            [
                "panel_host",
                "panel_port",
                "panel_timezone",
                "keypad_partitions",
                "control_enabled",
                "keypad_control_enabled",
                "native_alarm_control_enabled",
                "chime_zones",
                "transport_print_enabled",
                "transport_host",
                "transport_http_port",
                "transport_print_width",
                "raw_logging",
                "debug_raw_tx_enabled",
            ],
        )

    def test_newer_settings_are_optional_but_supported(self) -> None:
        self.assertIn('  event_history_max_age_days: "int(1,3650)?"', CONFIG_TEXT)
        self.assertIn("  raw_mqtt_enabled: bool?", CONFIG_TEXT)
        options = _mapping_keys("options")
        self.assertNotIn("event_history_max_age_days", options)
        self.assertNotIn("raw_mqtt_enabled", options)

    def test_removed_engineering_options_are_not_schema_fields(self) -> None:
        schema = set(_mapping_keys("schema"))
        self.assertNotIn("event_history_enabled", schema)
        self.assertNotIn("event_history_startup_dump_enabled", schema)
        self.assertNotIn("transport_print_queue_max", schema)
        self.assertNotIn("mqtt_outbound_queue_max", schema)
        self.assertNotIn("keypad_poll_interval_seconds", schema)


if __name__ == "__main__":
    unittest.main()
