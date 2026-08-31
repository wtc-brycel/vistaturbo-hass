from __future__ import annotations

import json
from pathlib import Path
import unittest

REPO_ROOT = Path(__file__).resolve().parents[2]
COMPONENT = REPO_ROOT / "custom_components" / "vistaturbo"
ADDON_CONFIG = REPO_ROOT / "vista128_bridge" / "config.yaml"
RUN_SCRIPT = REPO_ROOT / "vista128_bridge" / "run.sh"
NATIVE_API = REPO_ROOT / "vista128_bridge" / "app" / "vista_bridge" / "native_api.py"


class NativeComponentContractTests(unittest.TestCase):
    def test_manifest_declares_local_push_config_flow(self) -> None:
        manifest = json.loads((COMPONENT / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["domain"], "vistaturbo")
        self.assertEqual(manifest["iot_class"], "local_push")
        self.assertTrue(manifest["config_flow"])
        self.assertEqual(manifest["requirements"], [])

    def test_component_python_is_syntax_valid_without_importing_home_assistant(self) -> None:
        for path in COMPONENT.glob("*.py"):
            with self.subTest(path=path.name):
                compile(path.read_text(encoding="utf-8"), str(path), "exec")

    def test_supervisor_discovery_bootstraps_private_api_without_user_token(self) -> None:
        config = ADDON_CONFIG.read_text(encoding="utf-8")
        run_script = RUN_SCRIPT.read_text(encoding="utf-8")
        flow_source = (COMPONENT / "config_flow.py").read_text(encoding="utf-8")
        self.assertIn("discovery:\n  - vistaturbo", config)
        self.assertIn("8098/tcp: null", config)
        self.assertIn('bashio::discovery "vistaturbo"', run_script)
        self.assertIn("vistaturbo_native_api_token", run_script)
        self.assertNotIn("native_api_token:", config)
        self.assertIn("async_set_unique_id(discovery_info.uuid)", flow_source)
        self.assertNotIn("async_set_unique_id(discovery_info.slug)", flow_source)

    def test_ha1_alarm_control_is_semantic_and_never_exposes_keypad_grammar(self) -> None:
        source = NATIVE_API.read_text(encoding="utf-8")
        alarm_source = (COMPONENT / "alarm_control_panel.py").read_text(encoding="utf-8")
        api_source = (COMPONENT / "api.py").read_text(encoding="utf-8")
        init_source = (COMPONENT / "__init__.py").read_text(encoding="utf-8")

        self.assertIn('path == "/v1/control/alarm"', source)
        self.assertIn("VistaCommand(", source)
        self.assertIn('source="home_assistant"', source)
        self.assertNotIn("enqueue_keypad", source)
        self.assertNotIn("build_keypad_stroke_command", source)
        self.assertNotIn("/v1/control/keypad", source)

        self.assertIn("async_alarm_command", api_source)
        self.assertIn("async_alarm_disarm", alarm_source)
        self.assertIn("async_alarm_arm_away", alarm_source)
        self.assertIn("async_alarm_arm_home", alarm_source)
        self.assertIn("async_alarm_arm_night", alarm_source)
        self.assertIn("context.user_id", alarm_source)
        self.assertIn("Platform.ALARM_CONTROL_PANEL", init_source)
        self.assertNotIn("keypress", alarm_source.lower())
        self.assertNotIn("raw_sequence", alarm_source)

    def test_native_alarm_capability_change_reloads_entity_platforms(self) -> None:
        hub_source = (COMPONENT / "hub.py").read_text(encoding="utf-8")
        self.assertIn("_native_alarm_capability", hub_source)
        self.assertIn("async_schedule_reload", hub_source)
        self.assertIn("capability_changed", hub_source)

    def test_machine_auth_does_not_create_human_reauth_surface(self) -> None:
        init_source = (COMPONENT / "__init__.py").read_text(encoding="utf-8")
        flow_source = (COMPONENT / "config_flow.py").read_text(encoding="utf-8")
        self.assertIn("config_entry_only_config_schema", init_source)
        self.assertNotIn("ConfigEntryAuthFailed", init_source)
        self.assertNotIn("async_step_reauth", flow_source)

    def test_component_validates_native_api_schema_on_snapshot_and_stream(self) -> None:
        api_source = (COMPONENT / "api.py").read_text(encoding="utf-8")
        self.assertIn("def _validate_snapshot", api_source)
        self.assertIn('payload.get("schema") != API_SCHEMA', api_source)
        self.assertGreaterEqual(api_source.count("_validate_snapshot("), 3)


if __name__ == "__main__":
    unittest.main()
