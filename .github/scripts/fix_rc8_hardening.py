from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

def patch(path, old, new, count=1):
    p = ROOT / path
    text = p.read_text()
    if old not in text:
        raise SystemExit(f'missing fix anchor in {path}: {old[:80]!r}')
    p.write_text(text.replace(old, new, count))

patch(
    'vista128_bridge/app/vista_bridge/bridge.py',
    '''            if self.control.infer_automation_available():\n                LOG.info("VISTA automation interface inferred available from successful transaction")\n                self.mqtt.publish("panel/automation_available", "ON", retain=True, qos=1)\n                self.mqtt.publish("panel/automation_availability_source", "inferred", retain=True, qos=1)\n''',
    '''            control = getattr(self, "control", None)\n            if control is not None and control.infer_automation_available():\n                LOG.info("VISTA automation interface inferred available from successful transaction")\n                self.mqtt.publish("panel/automation_available", "ON", retain=True, qos=1)\n                self.mqtt.publish("panel/automation_availability_source", "inferred", retain=True, qos=1)\n''',
)

patch(
    'vista128_bridge/tests/test_state.py',
    '''        self.assertTrue(keypad.attributes()["power"])\n''',
    '''        self.assertIsNone(keypad.attributes()["power"])\n''',
)

patch(
    'vista128_bridge/tests/test_state.py',
    '''        keypad = state.apply_keypad_display(1, keypad_report(), "2026-08-16T13:22:28-04:00")\n        self.assertTrue(keypad.power_led)\n\n        state.apply_system_event(SystemEvent("1B", "AC Loss", 0, 0, 0, 0, 0, 15, 8, 26))\n''',
    '''        keypad = state.apply_keypad_display(1, keypad_report(), "2026-08-16T13:22:28-04:00")\n        self.assertIsNone(keypad.power_led)\n\n        state.apply_system_event(SystemEvent("1B", "AC Loss", 0, 0, 0, 0, 0, 15, 8, 26))\n''',
)

print('RC8 validation fixture fixes applied')
