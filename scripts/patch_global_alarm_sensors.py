from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f"missing patch anchor: {label}")
    return text.replace(old, new, 1)


# mqtt_discovery.py
path = Path("vista128_bridge/app/vista_bridge/mqtt_discovery.py")
text = path.read_text(encoding="utf-8")
anchor = '''def device_info() -> dict:\n'''
addition = '''def panel_alarm_availability(alarm_type: str, topic: TopicFn) -> dict:\n    return {\n        "availability": [\n            {\n                "topic": topic("bridge/availability"),\n                "payload_available": "online",\n                "payload_not_available": "offline",\n            },\n            {\n                "topic": topic("panel/connected"),\n                "payload_available": "ON",\n                "payload_not_available": "OFF",\n            },\n            {\n                "topic": topic(f"alarm/{alarm_type}/available"),\n                "payload_available": "ON",\n                "payload_not_available": "OFF",\n            },\n        ],\n        "availability_mode": "all",\n    }\n\n\ndef panel_alarm_configs(topic: TopicFn) -> dict[str, dict]:\n    configs = {\n        alarm_type: {\n            "name": spec["label"],\n            "unique_id": f"vista128_{alarm_type}_alarm",\n            "state_topic": topic(f"alarm/{alarm_type}"),\n            "payload_on": "ON",\n            "payload_off": "OFF",\n            "json_attributes_topic": topic(f"alarm/{alarm_type}/attributes"),\n            **panel_alarm_availability(alarm_type, topic),\n            "icon": spec["icon"],\n            "device": device_info(),\n        }\n        for alarm_type, spec in KEYPAD_ALARM_SPECS.items()\n    }\n    configs["active"] = {\n        "name": "Alarm Active",\n        "unique_id": "vista128_alarm_active",\n        "state_topic": topic("alarm/active"),\n        "payload_on": "ON",\n        "payload_off": "OFF",\n        "json_attributes_topic": topic("alarm/active/attributes"),\n        **panel_alarm_availability("active", topic),\n        "icon": "mdi:alarm-light",\n        "device": device_info(),\n    }\n    return configs\n\n\n'''
text = replace_once(text, anchor, addition + anchor, "panel alarm discovery")
path.write_text(text, encoding="utf-8")


# mqtt_client.py
path = Path("vista128_bridge/app/vista_bridge/mqtt_client.py")
text = path.read_text(encoding="utf-8")
text = replace_once(
    text,
    "    keypad_config,\n    partition_config,\n",
    "    keypad_config,\n    panel_alarm_configs,\n    partition_config,\n",
    "panel alarm config import",
)
text = replace_once(
    text,
    '''        for object_id, config in zone_summary_entities(self.topic).items():\n            self._publish_discovery_config("sensor", object_id, config)\n''',
    '''        for object_id, config in zone_summary_entities(self.topic).items():\n            self._publish_discovery_config("sensor", object_id, config)\n        for alarm_type, config in panel_alarm_configs(self.topic).items():\n            self._publish_discovery_config(\n                "binary_sensor", f"alarm_{alarm_type}", config\n            )\n''',
    "panel alarm discovery publish",
)
text = replace_once(
    text,
    '''        self._publish_keypad_alarm_states(keypad)\n\n    def _publish_keypad_alarm_states(self, keypad: KeypadState) -> None:\n''',
    '''\n    def publish_alarm_states(self, state: VistaState) -> None:\n        if self.settings.keypad.enabled:\n            for partition in self.settings.keypad.partitions:\n                keypad = state.keypads.get(partition)\n                if keypad is not None:\n                    self._publish_keypad_alarm_states(keypad)\n        self._publish_panel_alarm_states(state)\n\n    def _publish_keypad_alarm_states(self, keypad: KeypadState) -> None:\n''',
    "alarm state coordinator",
)
# Insert global aggregation before zone discovery.
anchor = '''    def publish_zone_discovery(self, zone: ZoneState) -> None:\n'''
addition = '''    def _publish_panel_alarm_states(self, state: VistaState) -> None:\n        prefix = "alarm"\n        configured = (\n            tuple(self.settings.keypad.partitions)\n            if self.settings.keypad.enabled and self.settings.keypad.partitions\n            else tuple(range(1, 9))\n        )\n        global_values: dict[str, bool | None] = {}\n        active_partitions_by_type: dict[str, list[int]] = {}\n\n        for alarm_type, spec in KEYPAD_ALARM_SPECS.items():\n            values = {\n                partition: getattr(keypad, spec["attribute"])\n                for partition, keypad in state.keypads.items()\n            }\n            active_partitions = sorted(\n                partition for partition, value in values.items() if value is True\n            )\n            active_partitions_by_type[alarm_type] = active_partitions\n            configured_values = [values[partition] for partition in configured]\n            available = bool(active_partitions) or all(\n                value is not None for value in configured_values\n            )\n            value: bool | None = True if active_partitions else (False if available else None)\n            global_values[alarm_type] = value\n\n            self.publish(\n                f"{prefix}/{alarm_type}/available",\n                "ON" if available else "OFF",\n                retain=True,\n                qos=1,\n            )\n            if available:\n                self.publish(\n                    f"{prefix}/{alarm_type}",\n                    "ON" if value else "OFF",\n                    retain=True,\n                    qos=1,\n                )\n            self.publish_json(\n                f"{prefix}/{alarm_type}/attributes",\n                {\n                    "active_partitions": active_partitions,\n                    "configured_partitions": list(configured),\n                    "partition_states": {\n                        str(partition): values[partition]\n                        for partition in sorted(values)\n                    },\n                },\n                retain=True,\n                qos=1,\n            )\n\n        active_types = [\n            alarm_type\n            for alarm_type, value in global_values.items()\n            if value is True\n        ]\n        aggregate_available = bool(active_types) or all(\n            value is not None for value in global_values.values()\n        )\n        self.publish(\n            f"{prefix}/active/available",\n            "ON" if aggregate_available else "OFF",\n            retain=True,\n            qos=1,\n        )\n        if aggregate_available:\n            self.publish(\n                f"{prefix}/active",\n                "ON" if active_types else "OFF",\n                retain=True,\n                qos=1,\n            )\n        self.publish_json(\n            f"{prefix}/active/attributes",\n            {\n                "active_types": active_types,\n                "fire_partitions": active_partitions_by_type["fire"],\n                "burglary_partitions": active_partitions_by_type["burglary"],\n                "auxiliary_partitions": active_partitions_by_type["auxiliary"],\n                "configured_partitions": list(configured),\n            },\n            retain=True,\n            qos=1,\n        )\n\n'''
text = replace_once(text, anchor, addition + anchor, "global alarm state publication")
path.write_text(text, encoding="utf-8")


# message_handler.py
path = Path("vista128_bridge/app/vista_bridge/message_handler.py")
text = path.read_text(encoding="utf-8")
text = replace_once(
    text,
    '''        for partition in self.state.partitions.values():\n            self.mqtt.publish_partition_discovery(partition.partition)\n            self.mqtt.publish_partition_state(partition)\n\n    def _handle_zone_status''',
    '''        for partition in self.state.partitions.values():\n            self.mqtt.publish_partition_discovery(partition.partition)\n            self.mqtt.publish_partition_state(partition)\n        self.mqtt.publish_alarm_states(self.state)\n\n    def _handle_zone_status''',
    "arming status alarm republish",
)
text = replace_once(
    text,
    '''        self.mqtt.publish_keypad_discovery(partition)\n        self.mqtt.publish_keypad_state(keypad)\n\n    def _handle_system_event''',
    '''        self.mqtt.publish_keypad_discovery(partition)\n        self.mqtt.publish_keypad_state(keypad)\n        self.mqtt.publish_alarm_states(self.state)\n\n    def _handle_system_event''',
    "KD alarm republish",
)
text = replace_once(
    text,
    '''        self._publish_initialized_keypads()\n\n        self.printer.enqueue_event(''',
    '''        self._publish_initialized_keypads()\n        self.mqtt.publish_alarm_states(self.state)\n\n        self.printer.enqueue_event(''',
    "system event alarm republish",
)
path.write_text(text, encoding="utf-8")


# bridge.py: publish unknown global/per-partition alarm validity at a new session.
path = Path("vista128_bridge/app/vista_bridge/bridge.py")
text = path.read_text(encoding="utf-8")
text = replace_once(
    text,
    '''        for keypad in self.state.keypads.values():\n            if keypad.initialized:\n                self.mqtt.publish_keypad_state(keypad)\n        self._panel_connected.set()\n''',
    '''        for keypad in self.state.keypads.values():\n            if keypad.initialized:\n                self.mqtt.publish_keypad_state(keypad)\n        self.mqtt.publish_alarm_states(self.state)\n        self._panel_connected.set()\n''',
    "session reset alarm state",
)
path.write_text(text, encoding="utf-8")


# state.py: authoritative disarmed reconciliation also clears stale burglary-specific state.
path = Path("vista128_bridge/app/vista_bridge/state.py")
text = path.read_text(encoding="utf-8")
old = '''            if raw_mode in {"D", "N"} and partition.active_alarm_tokens:\n                partition.active_alarm_tokens.clear()\n                changed.add(partition_number)\n'''
new = '''            if raw_mode in {"D", "N"}:\n                if partition.active_alarm_tokens:\n                    partition.active_alarm_tokens.clear()\n                    changed.add(partition_number)\n                if partition.active_burglary_tokens:\n                    partition.active_burglary_tokens.clear()\n                    changed.add(partition_number)\n                keypad = self.keypads.get(partition_number)\n                if keypad is not None and keypad.burglary_alarm_led is True:\n                    keypad.burglary_alarm_led = False\n                    changed.add(partition_number)\n'''
text = replace_once(text, old, new, "burglary AS reconciliation")
path.write_text(text, encoding="utf-8")


# Tests: mqtt client global aggregation.
path = Path("vista128_bridge/tests/test_mqtt_client.py")
text = path.read_text(encoding="utf-8")
anchor = '''    def test_zone_discovery_publishes_four_literal_conditions(self):\n'''
addition = '''    def test_global_alarm_sensors_or_across_all_partitions(self):\n        self.publisher.publish_discovery()\n        configs = {\n            item[0]: json.loads(item[1])\n            for item in self.publisher._client.published\n            if item[1]\n        }\n        for alarm_type, name in {\n            "fire": "Fire Alarm",\n            "burglary": "Burglary Alarm",\n            "auxiliary": "Auxiliary Alarm",\n            "active": "Alarm Active",\n        }.items():\n            topic = f"homeassistant/binary_sensor/vista128_bridge/alarm_{alarm_type}/config"\n            self.assertIn(topic, configs)\n            self.assertEqual(configs[topic]["name"], name)\n\n        state = VistaState()\n        state.keypads[1].fire_alarm_led = False\n        state.keypads[1].burglary_alarm_led = False\n        state.keypads[1].auxiliary_alarm_led = False\n        # Partition 4 is not a configured keypad partition, but a live alarm there\n        # must still drive the panel-level aggregate immediately.\n        state.keypads[4].fire_alarm_led = True\n        self.publisher.publish_alarm_states(state)\n        published = {item[0]: item[1] for item in self.publisher._client.published}\n        self.assertEqual(published["vista128/alarm/fire"], "ON")\n        self.assertEqual(published["vista128/alarm/fire/available"], "ON")\n        self.assertEqual(published["vista128/alarm/active"], "ON")\n        attrs = json.loads(published["vista128/alarm/fire/attributes"])\n        self.assertEqual(attrs["active_partitions"], [4])\n        aggregate = json.loads(published["vista128/alarm/active/attributes"])\n        self.assertEqual(aggregate["active_types"], ["fire"])\n        self.assertEqual(aggregate["fire_partitions"], [4])\n\n    def test_global_alarm_off_requires_configured_partition_known_false(self):\n        state = VistaState()\n        self.publisher.publish_alarm_states(state)\n        published = {item[0]: item[1] for item in self.publisher._client.published}\n        self.assertEqual(published["vista128/alarm/fire/available"], "OFF")\n        self.assertEqual(published["vista128/alarm/active/available"], "OFF")\n\n        state.keypads[1].fire_alarm_led = False\n        state.keypads[1].burglary_alarm_led = False\n        state.keypads[1].auxiliary_alarm_led = False\n        self.publisher.publish_alarm_states(state)\n        published = {item[0]: item[1] for item in self.publisher._client.published}\n        self.assertEqual(published["vista128/alarm/fire/available"], "ON")\n        self.assertEqual(published["vista128/alarm/fire"], "OFF")\n        self.assertEqual(published["vista128/alarm/active/available"], "ON")\n        self.assertEqual(published["vista128/alarm/active"], "OFF")\n\n'''
text = replace_once(text, anchor, addition + anchor, "global alarm tests")
path.write_text(text, encoding="utf-8")


# Tests: authoritative disarm clears stale burglary class.
path = Path("vista128_bridge/tests/test_readiness.py")
text = path.read_text(encoding="utf-8")
insert_before = '''if __name__ == "__main__":\n'''
addition = '''    def test_authoritative_not_ready_disarmed_clears_stale_burglary_class(self):\n        state = VistaState()\n        partition = state.partitions[1]\n        keypad = state.keypads[1]\n        partition.active_alarm_tokens.add("021:41")\n        partition.active_burglary_tokens.add("021:41")\n        keypad.burglary_alarm_led = True\n        report = ArmingStatusReport(raw_modes=("N", "D", "D", "D", "D", "D", "D", "D"))\n        changed = state.apply_arming_status(report)\n        self.assertIn(1, changed)\n        self.assertFalse(partition.active_alarm_tokens)\n        self.assertFalse(partition.active_burglary_tokens)\n        self.assertFalse(keypad.burglary_alarm_led)\n\n'''
text = replace_once(text, insert_before, addition + insert_before, "burglary reconcile test")
path.write_text(text, encoding="utf-8")

print("Patched global alarm sensors and reconciliation")
