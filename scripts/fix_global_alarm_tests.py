from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f"missing patch anchor: {label}")
    return text.replace(old, new, 1)

# Fake MQTT fixture needs the new publisher surface.
path = Path("vista128_bridge/tests/test_message_handler.py")
text = path.read_text(encoding="utf-8")
text = replace_once(
    text,
    '''    def publish_keypad_state(self, keypad):\n        self.keypad_states.append(keypad)\n\n    def publish_zone_discovery''',
    '''    def publish_keypad_state(self, keypad):\n        self.keypad_states.append(keypad)\n\n    def publish_alarm_states(self, state):\n        pass\n\n    def publish_zone_discovery''',
    "FakeMqtt alarm publisher",
)
path.write_text(text, encoding="utf-8")

# Per-partition alarm tests now use the public aggregate publisher.
path = Path("vista128_bridge/tests/test_mqtt_client.py")
text = path.read_text(encoding="utf-8")
text = replace_once(
    text,
    '''        self.publisher.publish_keypad_state(keypad)\n        published = {item[0]: item[1] for item in self.publisher._client.published}\n        self.assertEqual(published["vista128/keypad/1/alarm/fire"], "ON")\n''',
    '''        state = VistaState()\n        state.keypads[1] = keypad\n        self.publisher.publish_keypad_state(keypad)\n        self.publisher.publish_alarm_states(state)\n        published = {item[0]: item[1] for item in self.publisher._client.published}\n        self.assertEqual(published["vista128/keypad/1/alarm/fire"], "ON")\n''',
    "known keypad alarm test",
)
text = replace_once(
    text,
    '''        keypad = KeypadState(partition=1, initialized=True)\n        self.publisher.publish_keypad_state(keypad)\n        published = {item[0]: item[1] for item in self.publisher._client.published}\n''',
    '''        keypad = KeypadState(partition=1, initialized=True)\n        state = VistaState()\n        state.keypads[1] = keypad\n        self.publisher.publish_keypad_state(keypad)\n        self.publisher.publish_alarm_states(state)\n        published = {item[0]: item[1] for item in self.publisher._client.published}\n''',
    "unknown keypad alarm test",
)
path.write_text(text, encoding="utf-8")
