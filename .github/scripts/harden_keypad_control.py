from pathlib import Path


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text()
    if old not in text:
        raise RuntimeError(f"anchor not found in {path}: {old[:120]!r}")
    path.write_text(text.replace(old, new, 1))


mqtt = Path("vista128_bridge/app/vista_bridge/mqtt_client.py")
replace_once(
    mqtt,
    '''    def _on_message(self, client, userdata, message) -> None:
        if self._is_keypad_command(message.topic):
            self._handle_keypad_command(message.topic, message.payload)
            return
        if self._is_partition_command(message.topic):
            self._handle_partition_command(message.topic, message.payload)
            return
''',
    '''    def _on_message(self, client, userdata, message) -> None:
        is_keypad = self._is_keypad_command(message.topic)
        is_partition = self._is_partition_command(message.topic)
        if (is_keypad or is_partition) and bool(getattr(message, "retain", False)):
            kind = "keypad" if is_keypad else "alarm"
            category = "keypad" if is_keypad else "partition"
            try:
                partition = self._partition_from_topic(message.topic, category)
            except Exception:
                partition = None
            self._publish_control_rejection(kind, partition, "retained_control_message")
            return
        if is_keypad:
            self._handle_keypad_command(message.topic, message.payload)
            return
        if is_partition:
            self._handle_partition_command(message.topic, message.payload)
            return
''',
)
replace_once(
    mqtt,
    '''            key = payload.decode("ascii", errors="strict")
            if self.keypad_command_callback is None:
''',
    '''            key = payload.decode("ascii", errors="strict")
            if len(key) != 1 or key not in "0123456789*#":
                raise ValueError("unsupported_keypad_payload")
            if self.keypad_command_callback is None:
''',
)

control_test = Path("vista128_bridge/tests/test_control.py")
replace_once(control_test, "        self.keypad_refreshes = []\n        self.arming_refreshes = 0\n", "        self.keypad_refresh_requests = []\n        self.direct_keypad_refreshes = []\n        self.arming_refreshes = 0\n")
replace_once(control_test, "    async def run_keypad_refresh(self, partition):\n        self.keypad_refreshes.append(partition)\n        return True\n\n", "    def request_keypad_refresh(self, partition):\n        self.keypad_refresh_requests.append(partition)\n\n    async def run_keypad_refresh(self, partition):\n        self.direct_keypad_refreshes.append(partition)\n        return True\n\n")
replace_once(control_test, "        self.assertEqual(self.sync.keypad_refreshes, [1])\n        self.assertTrue(self.results[-1][\"ok\"])\n", "        self.assertEqual(self.sync.keypad_refresh_requests, [1])\n        self.assertEqual(self.sync.direct_keypad_refreshes, [])\n        self.assertTrue(self.results[-1][\"ok\"])\n")
replace_once(
    control_test,
    '''    async def test_function_letter_is_rejected_not_reencoded_as_star(self):
        control = self.make_control()
        control.set_automation_available(True)
        ok, reason = control.enqueue_keypad(1, "A")
        self.assertFalse(ok)
        self.assertIn("unsupported keypad keystroke", reason)
        self.assertEqual(self.sent, [])

''',
    '''    async def test_function_and_panic_tokens_are_not_exposed_by_normal_keypad_control(self):
        control = self.make_control()
        control.set_automation_available(True)
        for key in ("A", "D", "PANIC_A", "1234"):
            ok, reason = control.enqueue_keypad(1, key)
            self.assertFalse(ok)
            self.assertEqual(reason, "unsupported_keypad_key")
        self.assertEqual(self.sent, [])

    async def test_rapid_code_digits_are_not_blocked_by_direct_kd_round_trips(self):
        control = self.make_control()
        control.set_automation_available(True)
        for key in "1234":
            self.assertTrue(control.enqueue_keypad(1, key)[0])
        for _ in range(4):
            self.assertTrue(await control.process_next())
        self.assertEqual(len(self.sent), 4)
        self.assertEqual(self.sync.direct_keypad_refreshes, [])
        self.assertEqual(self.sync.keypad_refresh_requests, [1, 1, 1, 1])
        self.assertTrue(all(result["ok"] for result in self.results[-4:]))

''',
)

mqtt_test = Path("vista128_bridge/tests/test_control_mqtt.py")
replace_once(
    mqtt_test,
    "    def test_connect_subscribes_only_enabled_control_topics(self):\n",
    '''    def test_retained_control_messages_are_rejected_without_execution(self):
        keypad_received = []
        alarm_received = []
        settings = make_settings(control_enabled=True, keypad_control_enabled=True, native_alarm_control_enabled=True)
        publisher = MqttPublisher(
            settings,
            lambda data: (True, "queued"),
            lambda partition, key: (keypad_received.append((partition, key)) or True, "queued"),
            lambda partition, action, code: (alarm_received.append((partition, action, code)) or True, "queued"),
        )
        publisher._on_message(None, None, types.SimpleNamespace(topic="vista128/keypad/1/command", payload=b"7", retain=True))
        publisher._on_message(None, None, types.SimpleNamespace(topic="vista128/partition/1/command", payload=b'{"action":"DISARM","code":"1234"}', retain=True))
        self.assertEqual(keypad_received, [])
        self.assertEqual(alarm_received, [])
        published = [str(item[1]) for item in publisher._client.published]
        self.assertTrue(any("retained_control_message" in item for item in published))
        self.assertFalse(any("1234" in item for item in published))

    def test_malformed_keypad_payload_is_rejected_without_echoing_payload(self):
        received = []
        settings = make_settings(control_enabled=True, keypad_control_enabled=True)
        publisher = MqttPublisher(settings, lambda data: (True, "queued"), lambda partition, key: (received.append((partition, key)) or True, "queued"))
        publisher._on_message(None, None, types.SimpleNamespace(topic="vista128/keypad/1/command", payload=b"1234", retain=False))
        self.assertEqual(received, [])
        published = [str(item[1]) for item in publisher._client.published]
        self.assertTrue(any("unsupported_keypad_payload" in item for item in published))
        self.assertFalse(any("1234" in item for item in published))

    def test_connect_subscribes_only_enabled_control_topics(self):
''',
)
