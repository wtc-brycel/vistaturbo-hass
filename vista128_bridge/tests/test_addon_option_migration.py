from __future__ import annotations

from pathlib import Path
import unittest

RUN_SH = (Path(__file__).resolve().parents[1] / "run.sh").read_text(encoding="utf-8")


class AddonOptionMigrationTests(unittest.TestCase):
    def test_run_script_keeps_runtime_defaults_internal(self) -> None:
        expected_defaults = {
            "CONNECT_TIMEOUT_SECONDS": "5",
            "RECONNECT_MIN_SECONDS": "1",
            "RECONNECT_MAX_SECONDS": "30",
            "FRAME_IDLE_MS": "250",
            "MQTT_OUTBOUND_QUEUE_MAX": "256",
            "MQTT_INFLIGHT_MESSAGES_MAX": "20",
            "STARTUP_SYNC_ENABLED": "true",
            "STARTUP_SYNC_INITIAL_DELAY_MS": "1000",
            "STARTUP_SYNC_COMMAND_DELAY_MS": "500",
            "STARTUP_SYNC_RESPONSE_TIMEOUT_SECONDS": "5",
            "PERIODIC_SYNC_ENABLED": "true",
            "PERIODIC_SYNC_INTERVAL_SECONDS": "300",
            "PERIODIC_SYNC_RECONNECT_AFTER_FAILURES": "3",
            "KEYPAD_DISPLAY_ENABLED": "true",
            "KEYPAD_POLL_INTERVAL_SECONDS": "7",
            "KEYPAD_EVENT_REFRESH_DELAY_MS": "250",
            "CONTROL_RESPONSE_TIMEOUT_SECONDS": "3",
            "CONTROL_VERIFY_DELAY_MS": "400",
            "EVENT_HISTORY_ENABLED": "true",
            "EVENT_HISTORY_RECENT_LIMIT": "20",
            "KEYPAD_AUDIT_ENABLED": "true",
            "EVENT_HISTORY_MAX_ROWS": "10000",
            "TRANSPORT_PRINT_TIMEOUT_SECONDS": "5",
            "TRANSPORT_PRINT_RETRY_SECONDS": "10",
            "TRANSPORT_PRINT_QUEUE_MAX": "5000",
            "TX_QUEUE_MAX": "128",
            "RAW_TX_QUEUE_MAX": "16",
        }
        for variable, default in expected_defaults.items():
            with self.subTest(variable=variable):
                self.assertIn(f'export {variable}="{default}"', RUN_SH)

    def test_optional_settings_preserve_custom_values_with_safe_defaults(self) -> None:
        expected = {
            "EVENT_HISTORY_MAX_AGE_DAYS": ("event_history_max_age_days", "90"),
            "MQTT_BASE_TOPIC": ("mqtt_base_topic", "vista128"),
            "MQTT_DISCOVERY_PREFIX": ("mqtt_discovery_prefix", "homeassistant"),
            "MQTT_TLS_ENABLED": ("mqtt_tls_enabled", "false"),
            "MQTT_TLS_CA": ("mqtt_tls_ca", ""),
            "MQTT_TLS_CLIENT_CERT": ("mqtt_tls_client_cert", ""),
            "MQTT_TLS_CLIENT_KEY": ("mqtt_tls_client_key", ""),
            "RAW_MQTT_ENABLED": ("raw_mqtt_enabled", "false"),
        }
        for variable, (key, default) in expected.items():
            with self.subTest(variable=variable):
                self.assertIn(
                    f'export {variable}="$(config_or_default \'{key}\' \'{default}\')"',
                    RUN_SH,
                )

    def test_run_script_reads_required_deployment_choices_from_options(self) -> None:
        exposed_keys = {
            "panel_host",
            "panel_port",
            "panel_timezone",
            "keypad_partitions",
            "chime_zones",
            "control_enabled",
            "keypad_control_enabled",
            "native_alarm_control_enabled",
            "event_history_startup_dump_enabled",
            "transport_print_enabled",
            "transport_host",
            "transport_http_port",
            "transport_print_width",
            "raw_logging",
            "debug_raw_tx_enabled",
        }
        for key in exposed_keys:
            with self.subTest(key=key):
                self.assertIn(f"bashio::config '{key}'", RUN_SH)

    def test_run_script_removes_only_obsolete_stored_tuning(self) -> None:
        for key in (
            "connect_timeout_seconds",
            "startup_sync_initial_delay_ms",
            "periodic_sync_interval_seconds",
            "keypad_poll_interval_seconds",
            "control_verify_delay_ms",
            "event_history_max_rows",
            "transport_print_queue_max",
            "tx_queue_max",
        ):
            with self.subTest(key=key):
                self.assertIn(f"    {key} \\", RUN_SH)

        for retained in (
            "event_history_max_age_days",
            "event_history_startup_dump_enabled",
            "mqtt_base_topic",
            "mqtt_discovery_prefix",
            "mqtt_tls_enabled",
            "mqtt_tls_ca",
            "mqtt_tls_client_cert",
            "mqtt_tls_client_key",
            "raw_mqtt_enabled",
        ):
            with self.subTest(retained=retained):
                self.assertNotIn(f"    {retained} \\", RUN_SH)

        self.assertIn('bashio::addon.option "${old_key}"', RUN_SH)


if __name__ == "__main__":
    unittest.main()
