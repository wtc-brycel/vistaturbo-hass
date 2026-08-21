from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f"missing patch anchor: {label}")
    return text.replace(old, new, 1)


# mqtt_discovery.py
path = Path("vista128_bridge/app/vista_bridge/mqtt_discovery.py")
text = path.read_text(encoding="utf-8")
text = replace_once(
    text,
    "}\n\n\ndef device_info() -> dict:\n",
    '''}\n\n\nKEYPAD_ALARM_SPECS = {\n    "fire": {\n        "attribute": "fire_alarm_led",\n        "label": "Fire Alarm",\n        "icon": "mdi:fire-alert",\n    },\n    "burglary": {\n        "attribute": "burglary_alarm_led",\n        "label": "Burglary Alarm",\n        "icon": "mdi:shield-alert-outline",\n    },\n    "auxiliary": {\n        "attribute": "auxiliary_alarm_led",\n        "label": "Auxiliary Alarm",\n        "icon": "mdi:alarm-light-outline",\n    },\n}\n\n\ndef keypad_alarm_availability(partition: int, alarm_type: str, topic: TopicFn) -> dict:\n    return {\n        "availability": [\n            {\n                "topic": topic("bridge/availability"),\n                "payload_available": "online",\n                "payload_not_available": "offline",\n            },\n            {\n                "topic": topic("panel/connected"),\n                "payload_available": "ON",\n                "payload_not_available": "OFF",\n            },\n            {\n                "topic": topic(f"keypad/{partition}/alarm/{alarm_type}/available"),\n                "payload_available": "ON",\n                "payload_not_available": "OFF",\n            },\n        ],\n        "availability_mode": "all",\n    }\n\n\ndef keypad_alarm_configs(partition: int, topic: TopicFn) -> dict[str, dict]:\n    configs = {\n        alarm_type: {\n            "name": f"Partition {partition} {spec['label']}",\n            "unique_id": f"vista128_keypad_{partition}_{alarm_type}_alarm",\n            "state_topic": topic(f"keypad/{partition}/alarm/{alarm_type}"),\n            "payload_on": "ON",\n            "payload_off": "OFF",\n            **keypad_alarm_availability(partition, alarm_type, topic),\n            "icon": spec["icon"],\n            "device": device_info(),\n        }\n        for alarm_type, spec in KEYPAD_ALARM_SPECS.items()\n    }\n    configs["active"] = {\n        "name": f"Partition {partition} Alarm Active",\n        "unique_id": f"vista128_keypad_{partition}_alarm_active",\n        "state_topic": topic(f"keypad/{partition}/alarm/active"),\n        "payload_on": "ON",\n        "payload_off": "OFF",\n        "json_attributes_topic": topic(f"keypad/{partition}/alarm/active/attributes"),\n        **keypad_alarm_availability(partition, "active", topic),\n        "icon": "mdi:alarm-light",\n        "device": device_info(),\n    }\n    return configs\n\n\ndef device_info() -> dict:\n''',
    "alarm discovery helpers",
)
path.write_text(text, encoding="utf-8")


# mqtt_client.py
path = Path("vista128_bridge/app/vista_bridge/mqtt_client.py")
text = path.read_text(encoding="utf-8")
text = replace_once(
    text,
    "from .mqtt_discovery import (\n    ZONE_CONDITION_SPECS,\n",
    "from .mqtt_discovery import (\n    KEYPAD_ALARM_SPECS,\n    ZONE_CONDITION_SPECS,\n",
    "mqtt client alarm spec import",
)
text = replace_once(
    text,
    "    event_history_config,\n    keypad_config,\n",
    "    event_history_config,\n    keypad_alarm_configs,\n    keypad_config,\n",
    "mqtt client alarm config import",
)
text = replace_once(
    text,
    '''    def publish_keypad_discovery(self, partition: int) -> None:\n        self._publish_discovery_config(\n            "sensor",\n            f"keypad_{partition}",\n            keypad_config(partition, self.topic),\n        )\n\n    def publish_keypad_state(self, keypad: KeypadState) -> None:\n''',
    '''    def publish_keypad_discovery(self, partition: int) -> None:\n        self._publish_discovery_config(\n            "sensor",\n            f"keypad_{partition}",\n            keypad_config(partition, self.topic),\n        )\n        for alarm_type, config in keypad_alarm_configs(partition, self.topic).items():\n            self._publish_discovery_config(\n                "binary_sensor",\n                f"keypad_{partition}_alarm_{alarm_type}",\n                config,\n            )\n\n    def publish_keypad_state(self, keypad: KeypadState) -> None:\n''',
    "keypad alarm discovery publication",
)
text = replace_once(
    text,
    '''        self.publish_json(\n            f"{prefix}/attributes",\n            attributes,\n            retain=True,\n            qos=1,\n        )\n\n    def publish_zone_discovery(self, zone: ZoneState) -> None:\n''',
    '''        self.publish_json(\n            f"{prefix}/attributes",\n            attributes,\n            retain=True,\n            qos=1,\n        )\n        self._publish_keypad_alarm_states(keypad)\n\n    def _publish_keypad_alarm_states(self, keypad: KeypadState) -> None:\n        prefix = f"keypad/{keypad.partition}/alarm"\n        values: dict[str, bool | None] = {}\n        for alarm_type, spec in KEYPAD_ALARM_SPECS.items():\n            value = getattr(keypad, spec["attribute"])\n            values[alarm_type] = value\n            available = value is not None\n            self.publish(\n                f"{prefix}/{alarm_type}/available",\n                "ON" if available else "OFF",\n                retain=True,\n                qos=1,\n            )\n            if available:\n                self.publish(\n                    f"{prefix}/{alarm_type}",\n                    "ON" if value else "OFF",\n                    retain=True,\n                    qos=1,\n                )\n\n        active_types = [\n            alarm_type for alarm_type, value in values.items() if value is True\n        ]\n        all_known = all(value is not None for value in values.values())\n        aggregate_available = bool(active_types) or all_known\n        self.publish(\n            f"{prefix}/active/available",\n            "ON" if aggregate_available else "OFF",\n            retain=True,\n            qos=1,\n        )\n        if aggregate_available:\n            self.publish(\n                f"{prefix}/active",\n                "ON" if active_types else "OFF",\n                retain=True,\n                qos=1,\n            )\n        self.publish_json(\n            f"{prefix}/active/attributes",\n            {\n                "active_types": active_types,\n                "fire_alarm": values["fire"],\n                "burglary_alarm": values["burglary"],\n                "auxiliary_alarm": values["auxiliary"],\n                "sound_mode": keypad.sound_mode,\n            },\n            retain=True,\n            qos=1,\n        )\n\n    def publish_zone_discovery(self, zone: ZoneState) -> None:\n''',
    "keypad alarm state publication",
)
path.write_text(text, encoding="utf-8")


# tests/test_mqtt_client.py
path = Path("vista128_bridge/tests/test_mqtt_client.py")
text = path.read_text(encoding="utf-8")
anchor = '''    def test_zone_discovery_publishes_four_literal_conditions(self):\n'''
addition = '''    def test_keypad_alarm_binary_sensor_discovery_and_state(self):\n        self.publisher.publish_keypad_discovery(1)\n        configs = {\n            item[0]: json.loads(item[1])\n            for item in self.publisher._client.published\n            if item[1] and item[0].startswith("homeassistant/binary_sensor/")\n        }\n        expected = {\n            "fire": "Partition 1 Fire Alarm",\n            "burglary": "Partition 1 Burglary Alarm",\n            "auxiliary": "Partition 1 Auxiliary Alarm",\n            "active": "Partition 1 Alarm Active",\n        }\n        for alarm_type, name in expected.items():\n            topic = (\n                "homeassistant/binary_sensor/vista128_bridge/"\n                f"keypad_1_alarm_{alarm_type}/config"\n            )\n            self.assertIn(topic, configs)\n            self.assertEqual(configs[topic]["name"], name)\n            self.assertEqual(\n                configs[topic]["state_topic"],\n                f"vista128/keypad/1/alarm/{alarm_type}",\n            )\n            self.assertEqual(configs[topic]["availability_mode"], "all")\n            self.assertEqual(len(configs[topic]["availability"]), 3)\n\n        keypad = KeypadState(\n            partition=1,\n            initialized=True,\n            fire_alarm_led=True,\n            burglary_alarm_led=False,\n            auxiliary_alarm_led=False,\n        )\n        self.publisher.publish_keypad_state(keypad)\n        published = {item[0]: item[1] for item in self.publisher._client.published}\n        self.assertEqual(published["vista128/keypad/1/alarm/fire"], "ON")\n        self.assertEqual(published["vista128/keypad/1/alarm/burglary"], "OFF")\n        self.assertEqual(published["vista128/keypad/1/alarm/auxiliary"], "OFF")\n        self.assertEqual(published["vista128/keypad/1/alarm/active"], "ON")\n        attrs = json.loads(published["vista128/keypad/1/alarm/active/attributes"])\n        self.assertEqual(attrs["active_types"], ["fire"])\n        self.assertTrue(attrs["fire_alarm"])\n\n    def test_keypad_alarm_binary_sensors_are_unavailable_while_state_is_unknown(self):\n        keypad = KeypadState(partition=1, initialized=True)\n        self.publisher.publish_keypad_state(keypad)\n        published = {item[0]: item[1] for item in self.publisher._client.published}\n        for alarm_type in ("fire", "burglary", "auxiliary", "active"):\n            self.assertEqual(\n                published[f"vista128/keypad/1/alarm/{alarm_type}/available"],\n                "OFF",\n            )\n\n'''
text = replace_once(text, anchor, addition + anchor, "mqtt alarm tests")
path.write_text(text, encoding="utf-8")

print("Patched alarm binary sensors and tests")
