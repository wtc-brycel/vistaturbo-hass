from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

def patch(path, old, new, count=1):
    p = ROOT / path
    text = p.read_text()
    if old not in text:
        raise SystemExit(f'missing patch anchor in {path}: {old[:80]!r}')
    text = text.replace(old, new, count)
    p.write_text(text)

# ---- control availability: explicit XF latch, XN explicit restore, successful OK inference ----
p = 'vista128_bridge/app/vista_bridge/control.py'
patch(p,
'''        self._automation_available = threading.Event()\n        self._generation_lock = threading.Lock()\n''',
'''        self._automation_available = threading.Event()\n        self._automation_state_lock = threading.Lock()\n        self._automation_source = "unknown"\n        self._automation_blocked = False\n        self._generation_lock = threading.Lock()\n''')
patch(p,
'''    def automation_available(self) -> bool:\n        return self._automation_available.is_set()\n\n    def set_automation_available(self, available: bool) -> None:\n        if available:\n            self._automation_available.set()\n        else:\n            self._automation_available.clear()\n            self.discard_pending("automation_unavailable")\n\n    def reset_session(self) -> int:\n        with self._generation_lock:\n            self._generation += 1\n            generation = self._generation\n        self._automation_available.clear()\n        self.discard_pending("panel_session_reset")\n        return generation\n''',
'''    def automation_available(self) -> bool:\n        return self._automation_available.is_set()\n\n    def automation_availability_source(self) -> str:\n        with self._automation_state_lock:\n            return self._automation_source\n\n    def infer_automation_available(self) -> bool:\n        """Infer automation availability from a successful structured transaction.\n\n        An explicit XF Communication Off latches the session blocked and cannot be\n        overridden by ordinary OK replies. A new TCP session clears the latch.\n        """\n        with self._automation_state_lock:\n            if self._automation_blocked or self._automation_available.is_set():\n                return False\n            self._automation_available.set()\n            self._automation_source = "inferred"\n            return True\n\n    def set_automation_available(self, available: bool, *, source: str = "explicit") -> bool:\n        with self._automation_state_lock:\n            before = self._automation_available.is_set()\n            before_source = self._automation_source\n            if available:\n                self._automation_blocked = False\n                self._automation_available.set()\n                self._automation_source = source\n            else:\n                self._automation_blocked = True\n                self._automation_available.clear()\n                self._automation_source = "communication_off"\n            changed = (before != self._automation_available.is_set()) or (before_source != self._automation_source)\n        if not available:\n            self.discard_pending("automation_unavailable")\n        return changed\n\n    def reset_session(self) -> int:\n        with self._generation_lock:\n            self._generation += 1\n            generation = self._generation\n        with self._automation_state_lock:\n            self._automation_available.clear()\n            self._automation_blocked = False\n            self._automation_source = "unknown"\n        self.discard_pending("panel_session_reset")\n        return generation\n''')

# ---- bridge: infer availability from a valid OK, publish source diagnostics ----
p = 'vista128_bridge/app/vista_bridge/bridge.py'
patch(p,
'''        self.mqtt.publish("panel/connected", "ON", retain=True)\n        self.mqtt.publish("panel/automation_available", "OFF", retain=True)\n        self.handler.publish_event_history_snapshot()\n''',
'''        self.mqtt.publish("panel/connected", "ON", retain=True)\n        self.mqtt.publish("panel/automation_available", "OFF", retain=True)\n        self.mqtt.publish("panel/automation_availability_source", "unknown", retain=True)\n        self.handler.publish_event_history_snapshot()\n''')
patch(p,
'''        self.mqtt.publish("panel/connected", "OFF", retain=True)\n        self.mqtt.publish("panel/automation_available", "OFF", retain=True)\n\n        if self._writer is not None:\n''',
'''        self.mqtt.publish("panel/connected", "OFF", retain=True)\n        self.mqtt.publish("panel/automation_available", "OFF", retain=True)\n        self.mqtt.publish("panel/automation_availability_source", "offline", retain=True)\n\n        if self._writer is not None:\n''')
patch(p,
'''        if message_type == "ready":\n            self.synchronizer.mark_ready()\n        self.handler.handle(message_type, frame.data, frame.received_at)\n''',
'''        if message_type == "ready":\n            self.synchronizer.mark_ready()\n            if self.control.infer_automation_available():\n                LOG.info("VISTA automation interface inferred available from successful transaction")\n                self.mqtt.publish("panel/automation_available", "ON", retain=True, qos=1)\n                self.mqtt.publish("panel/automation_availability_source", "inferred", retain=True, qos=1)\n        self.handler.handle(message_type, frame.data, frame.received_at)\n''')

# ---- explicit XN/XF diagnostics ----
p = 'vista128_bridge/app/vista_bridge/message_handler.py'
patch(p,
'''        self.mqtt.publish("panel/automation_available", "ON", retain=True, qos=1)\n        if self.control is not None:\n            self.control.set_automation_available(True)\n''',
'''        self.mqtt.publish("panel/automation_available", "ON", retain=True, qos=1)\n        self.mqtt.publish("panel/automation_availability_source", "explicit", retain=True, qos=1)\n        if self.control is not None:\n            self.control.set_automation_available(True, source="explicit")\n''')
patch(p,
'''        self.mqtt.publish("panel/automation_available", "OFF", retain=True, qos=1)\n        if self.control is not None:\n            self.control.set_automation_available(False)\n''',
'''        self.mqtt.publish("panel/automation_available", "OFF", retain=True, qos=1)\n        self.mqtt.publish("panel/automation_availability_source", "communication_off", retain=True, qos=1)\n        if self.control is not None:\n            self.control.set_automation_available(False)\n''')

# ---- discovery: expose availability source ----
p = 'vista128_bridge/app/vista_bridge/mqtt_discovery.py'
patch(p,
'''        "automation_available": (\n            "binary_sensor",\n            {\n                "name": "Automation Interface Available",\n                "unique_id": "vista128_automation_available",\n                "state_topic": topic("panel/automation_available"),\n                "payload_on": "ON",\n                "payload_off": "OFF",\n                "device_class": "connectivity",\n                "entity_category": "diagnostic",\n            },\n        ),\n''',
'''        "automation_available": (\n            "binary_sensor",\n            {\n                "name": "Automation Interface Available",\n                "unique_id": "vista128_automation_available",\n                "state_topic": topic("panel/automation_available"),\n                "payload_on": "ON",\n                "payload_off": "OFF",\n                "device_class": "connectivity",\n                "entity_category": "diagnostic",\n            },\n        ),\n        "automation_availability_source": (\n            "sensor",\n            {\n                "name": "Automation Availability Source",\n                "unique_id": "vista128_automation_availability_source",\n                "state_topic": topic("panel/automation_availability_source"),\n                "entity_category": "diagnostic",\n                "icon": "mdi:connection",\n            },\n        ),\n''')

# ---- state model: raw vs semantic trouble, AC no-positive-inference, D/N reconciliation ----
p = 'vista128_bridge/app/vista_bridge/state.py'
patch(p,
'''SILENCED_DISPLAY_TOKENS = ("SILENCED", "SILENCE")\n''',
'''SILENCED_DISPLAY_TOKENS = ("SILENCED", "SILENCE")\nTROUBLE_DISPLAY_TOKENS = (\n    "TROUBLE", "TRBL", "CHECK ", "LOW BAT", "FAIL TO COMM", "COMM FAIL", "BELL TROUBLE",\n)\n\nPARTITION_TROUBLE_RESTORE_TO_START = {\n    "04": "03",\n    "54": "53",\n    "64": "63",\n    "A2": "A1",\n    "A4": "A3",\n    "C4": "C3",\n    "D4": "D3",\n    "E4": "E3",\n    "F4": "F3",\n    "FE": "FD",\n}\nPARTITION_TROUBLE_START_CODES = set(PARTITION_TROUBLE_RESTORE_TO_START.values())\nSYSTEM_BATTERY_EVENT_STATES = {"29": True, "2A": False}\n''')
patch(p,
'''    active_auxiliary_tokens: set[str] = field(default_factory=set)\n    fire_silenced: bool = False\n''',
'''    active_auxiliary_tokens: set[str] = field(default_factory=set)\n    active_trouble_tokens: set[str] = field(default_factory=set)\n    fire_silenced: bool = False\n''')
patch(p,
'''    trouble_led: bool = False\n    armed_led: bool = False\n''',
'''    trouble_led: bool = False\n    trouble_led_raw: bool = False\n    armed_led: bool = False\n''')
patch(p,
'''            "trouble": self.trouble_led,\n            "armed": self.armed_led,\n''',
'''            "trouble": self.trouble_led,\n            "trouble_led_raw": self.trouble_led_raw,\n            "armed": self.armed_led,\n''')
patch(p,
'''        self.ac_power: bool | None = None\n        self.arming_initialized = False\n''',
'''        self.ac_power: bool | None = None\n        self.system_battery_low: bool | None = None\n        self.active_global_trouble_tokens: set[str] = set()\n        self.arming_initialized = False\n''')
patch(p,
'''        self.ac_power = None\n        for partition in self.partitions.values():\n''',
'''        self.ac_power = None\n        self.system_battery_low = None\n        self.active_global_trouble_tokens.clear()\n        for partition in self.partitions.values():\n''')
patch(p,
'''            partition.active_auxiliary_tokens.clear()\n            partition.fire_silenced = False\n''',
'''            partition.active_auxiliary_tokens.clear()\n            partition.active_trouble_tokens.clear()\n            partition.fire_silenced = False\n''')
patch(p,
'''            if raw_mode == "D" and partition.active_alarm_tokens:\n                partition.active_alarm_tokens.clear()\n                changed.add(partition_number)\n''',
'''            if raw_mode in {"D", "N"} and partition.active_alarm_tokens:\n                partition.active_alarm_tokens.clear()\n                changed.add(partition_number)\n''')
patch(p,
'''        keypad.ready_led = report.ready_led\n        keypad.trouble_led = report.trouble_led\n        keypad.armed_led = report.armed_led\n''',
'''        keypad.ready_led = report.ready_led\n        keypad.trouble_led_raw = report.trouble_led\n        keypad.armed_led = report.armed_led\n''')
patch(p,
'''        if self._contains_any(display, AC_LOSS_DISPLAY_TOKENS):\n            self._set_ac_power(False)\n        elif not report.trouble_led:\n            self._set_ac_power(True)\n        keypad.power_led = self.ac_power\n\n        explicit_fire = self._contains_any(display, FIRE_DISPLAY_TOKENS)\n''',
'''        if self._contains_any(display, AC_LOSS_DISPLAY_TOKENS):\n            self._set_ac_power(False)\n        keypad.power_led = self.ac_power\n\n        explicit_fire = self._contains_any(display, FIRE_DISPLAY_TOKENS)\n''')
patch(p,
'''        if partition_state.auxiliary_alarm_active:\n            keypad.auxiliary_alarm_led = True\n        elif normal_ready:\n            keypad.auxiliary_alarm_led = False\n\n        return keypad\n''',
'''        if partition_state.auxiliary_alarm_active:\n            keypad.auxiliary_alarm_led = True\n        elif normal_ready:\n            keypad.auxiliary_alarm_led = False\n\n        self._reconcile_keypad_trouble(partition)\n        return keypad\n''')
patch(p,
'''        self._reconcile_partition_zone_alarms()\n        return changed\n\n    def apply_zone_partition''',
'''        self._reconcile_partition_zone_alarms()\n        self._reconcile_all_keypad_trouble()\n        return changed\n\n    def apply_zone_partition''', 1)
patch(p,
'''        self._apply_cr2_annunciator_event(event, changed_partitions)\n        self._apply_audible_alarm_event(event, changed_partitions)\n        return changed_zones, changed_partitions\n''',
'''        self._apply_cr2_annunciator_event(event, changed_partitions)\n        self._apply_audible_alarm_event(event, changed_partitions)\n        self._apply_trouble_event(event, changed_partitions)\n        self._reconcile_all_keypad_trouble()\n        return changed_zones, changed_partitions\n''')
# insert trouble helpers before _set_ac_power
patch(p,
'''    def _set_ac_power(self, value: bool) -> None:\n        self.ac_power = value\n        for keypad in self.keypads.values():\n            keypad.power_led = value\n''',
'''    def _apply_trouble_event(self, event: SystemEvent, changed_partitions: set[int]) -> None:\n        battery_state = SYSTEM_BATTERY_EVENT_STATES.get(event.code)\n        if battery_state is not None:\n            self.system_battery_low = battery_state\n\n        start_code = None\n        if event.code in PARTITION_TROUBLE_START_CODES:\n            start_code = event.code\n            adding = True\n        else:\n            start_code = PARTITION_TROUBLE_RESTORE_TO_START.get(event.code)\n            adding = False\n        if start_code is None:\n            return\n\n        token = f"{event.zone:03d}:{start_code}"\n        partition = self.partitions.get(event.partition)\n        tokens = partition.active_trouble_tokens if partition is not None else self.active_global_trouble_tokens\n        before = token in tokens\n        if adding:\n            tokens.add(token)\n        else:\n            tokens.discard(token)\n        if partition is not None and before != (token in tokens):\n            changed_partitions.add(event.partition)\n\n    def _partition_has_known_trouble(self, partition_number: int) -> bool:\n        if self.ac_power is False or self.system_battery_low is True or self.active_global_trouble_tokens:\n            return True\n        partition = self.partitions.get(partition_number)\n        if partition is not None and partition.active_trouble_tokens:\n            return True\n        return any(\n            zone.partition == partition_number and (zone.trouble or zone.low_battery or zone.tamper)\n            for zone in self.zones.values()\n        )\n\n    def _reconcile_keypad_trouble(self, partition_number: int) -> None:\n        keypad = self.keypads.get(partition_number)\n        if keypad is None or not keypad.initialized:\n            return\n        display = f"{keypad.line_1} {keypad.line_2}".upper()\n        explicit = keypad.trouble_led_raw or self._contains_any(display, TROUBLE_DISPLAY_TOKENS)\n        keypad.trouble_led = bool(explicit or self._partition_has_known_trouble(partition_number))\n\n    def _reconcile_all_keypad_trouble(self) -> None:\n        for partition_number in self.keypads:\n            self._reconcile_keypad_trouble(partition_number)\n\n    def _set_ac_power(self, value: bool) -> None:\n        self.ac_power = value\n        for keypad in self.keypads.values():\n            keypad.power_led = value\n        self._reconcile_all_keypad_trouble()\n''')

# ---- publisher: real partition control diagnostic ----
p = 'vista128_bridge/app/vista_bridge/mqtt_client.py'
patch(p,
'''        self.publish_json(\n            f"{prefix}/attributes",\n            partition.attributes(),\n            retain=True,\n            qos=1,\n        )\n''',
'''        attributes = partition.attributes()\n        attributes["control_enabled"] = bool(\n            self.settings.control.enabled and self.settings.control.native_alarm_enabled\n        )\n        self.publish_json(\n            f"{prefix}/attributes",\n            attributes,\n            retain=True,\n            qos=1,\n        )\n''')

# ---- state base attributes should not claim control policy ----
p = 'vista128_bridge/app/vista_bridge/state.py'
patch(p,
'''            "auxiliary_alarm_active": self.auxiliary_alarm_active,\n            "control_enabled": False,\n''',
'''            "auxiliary_alarm_active": self.auxiliary_alarm_active,\n''')

# ---- frontend: at-most-once keypress and no digit leak in DOM event ----
p = 'frontend/vista-keypad-card.js'
patch(p,
'''        qos: 1,\n        retain: false,\n''',
'''        qos: 0,\n        retain: false,\n''')
patch(p,
'''      detail: {\n        key,\n        entity: this._config.entity,\n        model: this._config.model,\n      },\n''',
'''      detail: {\n        action: "keypress",\n        entity: this._config.entity,\n        model: this._config.model,\n      },\n''')

# ---- tests ----
p = 'vista128_bridge/tests/test_control.py'
patch(p,
'''    async def test_keypad_requires_automation_on_and_never_echoes_key(self):\n''',
'''    async def test_successful_transaction_can_infer_availability_but_xf_latches_blocked(self):\n        control = self.make_control()\n        self.assertEqual(control.automation_availability_source(), "unknown")\n        self.assertTrue(control.infer_automation_available())\n        self.assertTrue(control.automation_available())\n        self.assertEqual(control.automation_availability_source(), "inferred")\n\n        control.set_automation_available(False)\n        self.assertFalse(control.automation_available())\n        self.assertEqual(control.automation_availability_source(), "communication_off")\n        self.assertFalse(control.infer_automation_available())\n        self.assertFalse(control.automation_available())\n\n        control.set_automation_available(True, source="explicit")\n        self.assertTrue(control.automation_available())\n        self.assertEqual(control.automation_availability_source(), "explicit")\n\n        control.reset_session()\n        self.assertFalse(control.automation_available())\n        self.assertEqual(control.automation_availability_source(), "unknown")\n        self.assertTrue(control.infer_automation_available())\n\n    async def test_keypad_requires_automation_on_and_never_echoes_key(self):\n''')

p = 'vista128_bridge/tests/test_state.py'
patch(p,
'''    def test_keypad_trouble_does_not_guess_power_without_ac_evidence(self):\n''',
'''    def test_not_ready_arming_snapshot_clears_stale_alarm_tokens(self):\n        state = VistaState()\n        state.partitions[1].active_alarm_tokens.add("010:31")\n        state.apply_arming_status(ArmingStatusReport(tuple("NDDDDDDD")))\n        self.assertEqual(state.partitions[1].ha_state, "disarmed")\n        self.assertFalse(state.partitions[1].active_alarm_tokens)\n\n    def test_keypad_trouble_does_not_guess_power_without_ac_evidence(self):\n''')
patch(p,
'''        self.assertIsNone(keypad.power_led)\n\n    def test_ac_loss_restore_drives_cr2_power_annunciator(self):\n''',
'''        self.assertIsNone(keypad.power_led)\n        self.assertTrue(keypad.trouble_led)\n        self.assertTrue(keypad.trouble_led_raw)\n\n    def test_kd_page_without_trouble_bit_does_not_infer_ac_restore(self):\n        state = VistaState()\n        state.ac_power = False\n        keypad = state.apply_keypad_display(\n            1,\n            keypad_report("P1   DISARMED   ", "ZONES IN TROUBLE", ready=False, trouble=False),\n            "2026-08-17T17:00:19-04:00",\n        )\n        self.assertFalse(keypad.power_led)\n        self.assertTrue(keypad.trouble_led)\n        self.assertFalse(keypad.trouble_led_raw)\n\n    def test_semantic_trouble_stays_on_across_alternating_kd_pages(self):\n        state = VistaState()\n        partitions = [0] * 64\n        partitions[20] = 1\n        state.apply_zone_partition(ZonePartitionReport(1, tuple(partitions)))\n        statuses = [0] * 64\n        statuses[20] = 0x2\n        state.apply_zone_status(ZoneStatusReport(1, tuple(statuses)))\n\n        keypad = state.apply_keypad_display(\n            1,\n            keypad_report("P1   DISARMED   ", "ZONES IN TROUBLE", ready=False, trouble=False),\n            "2026-08-17T17:00:19-04:00",\n        )\n        self.assertTrue(keypad.trouble_led)\n        self.assertFalse(keypad.trouble_led_raw)\n        state.apply_keypad_display(\n            1,\n            keypad_report("TRBL  021 FRONT ", "DOOR            ", ready=False, trouble=True),\n            "2026-08-17T17:00:34-04:00",\n        )\n        self.assertTrue(keypad.trouble_led)\n        self.assertTrue(keypad.trouble_led_raw)\n        state.apply_keypad_display(\n            1,\n            keypad_report("FAULT 021 FRONT ", "DOOR            ", ready=False, trouble=False),\n            "2026-08-17T17:00:42-04:00",\n        )\n        self.assertTrue(keypad.trouble_led)\n        self.assertFalse(keypad.trouble_led_raw)\n\n    def test_ac_loss_restore_drives_cr2_power_annunciator(self):\n''')

p = 'vista128_bridge/tests/test_mqtt_client.py'
patch(p,
'''    def test_automation_interface_has_diagnostic_discovery(self):\n''',
'''    def test_partition_control_attribute_reflects_settings(self):\n        settings = make_settings(control_enabled=True, native_alarm_control_enabled=True)\n        publisher = MqttPublisher(settings, lambda data: (True, "queued"))\n        state = VistaState()\n        publisher.publish_partition_state(state.partitions[1])\n        published = {item[0]: item[1] for item in publisher._client.published}\n        attrs = json.loads(published["vista128/partition/1/attributes"])\n        self.assertTrue(attrs["control_enabled"])\n\n    def test_automation_interface_has_diagnostic_discovery(self):\n''')
patch(p,
'''        self.assertEqual(config["device_class"], "connectivity")\n\n\n\nif __name__ == "__main__":\n''',
'''        self.assertEqual(config["device_class"], "connectivity")\n        source = json.loads(\n            published["homeassistant/sensor/vista128_bridge/automation_availability_source/config"]\n        )\n        self.assertEqual(source["state_topic"], "vista128/panel/automation_availability_source")\n\n\n\nif __name__ == "__main__":\n''')

p = 'frontend/tests/control.spec.mjs'
patch(p,
'''    qos: 1,\n    retain: false,\n''',
'''    qos: 0,\n    retain: false,\n''')
patch(p,
'''test("star and pound publish their literal keypad symbols", async ({ page }) => {\n''',
'''test("keypress DOM event does not expose the entered digit", async ({ page }) => {\n  await mount(page);\n  await page.evaluate(() => {\n    window.keyEvents = [];\n    document.getElementById("card").addEventListener("vista-keypad-key", (event) => window.keyEvents.push(event.detail));\n  });\n  await clickKey(page, "7");\n  const events = await page.evaluate(() => window.keyEvents);\n  expect(events).toHaveLength(1);\n  expect(events[0].action).toBe("keypress");\n  expect(events[0].key).toBeUndefined();\n});\n\ntest("star and pound publish their literal keypad symbols", async ({ page }) => {\n''')

print('RC8 hardening patch applied')
