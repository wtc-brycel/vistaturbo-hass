from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text()
    if old not in text:
        raise RuntimeError(f"anchor not found in {path}: {old[:100]!r}")
    path.write_text(text.replace(old, new, 1))


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
config = ROOT / "vista128_bridge/app/vista_bridge/config.py"
replace_once(
    config,
    "@dataclass(frozen=True)\nclass EventHistorySettings:\n",
    "@dataclass(frozen=True)\nclass ControlSettings:\n"
    "    enabled: bool\n"
    "    keypad_enabled: bool\n"
    "    native_alarm_enabled: bool\n"
    "    response_timeout_seconds: int\n"
    "    verify_delay_ms: int\n\n\n"
    "@dataclass(frozen=True)\nclass EventHistorySettings:\n",
)
replace_once(
    config,
    "    keypad: KeypadSettings\n    event_history: EventHistorySettings\n",
    "    keypad: KeypadSettings\n    control: ControlSettings\n    event_history: EventHistorySettings\n",
)
replace_once(
    config,
    "            event_history=EventHistorySettings(\n",
    "            control=ControlSettings(\n"
    "                enabled=_bool_env(\"CONTROL_ENABLED\", False),\n"
    "                keypad_enabled=_bool_env(\"KEYPAD_CONTROL_ENABLED\", False),\n"
    "                native_alarm_enabled=_bool_env(\"NATIVE_ALARM_CONTROL_ENABLED\", False),\n"
    "                response_timeout_seconds=int(os.environ.get(\"CONTROL_RESPONSE_TIMEOUT_SECONDS\", \"3\")),\n"
    "                verify_delay_ms=int(os.environ.get(\"CONTROL_VERIFY_DELAY_MS\", \"400\")),\n"
    "            ),\n"
    "            event_history=EventHistorySettings(\n",
)
replace_once(
    config,
    "        if not self.event_history.sqlite_path:\n",
    "        if not 1 <= self.control.response_timeout_seconds <= 10:\n"
    "            raise ValueError(\"control_response_timeout_seconds must be 1..10\")\n"
    "        if not 0 <= self.control.verify_delay_ms <= 5000:\n"
    "            raise ValueError(\"control_verify_delay_ms must be 0..5000\")\n"
    "        if not self.event_history.sqlite_path:\n",
)

helpers = ROOT / "vista128_bridge/tests/helpers.py"
replace_once(
    helpers,
    "    KeypadSettings,\n",
    "    ControlSettings,\n    KeypadSettings,\n",
)
replace_once(
    helpers,
    "    chime_zones: tuple[int, ...] = (),\n) -> Settings:\n",
    "    chime_zones: tuple[int, ...] = (),\n"
    "    control_enabled: bool = False,\n"
    "    keypad_control_enabled: bool = False,\n"
    "    native_alarm_control_enabled: bool = False,\n"
    ") -> Settings:\n",
)
replace_once(
    helpers,
    "        event_history=EventHistorySettings(\n",
    "        control=ControlSettings(\n"
    "            enabled=control_enabled,\n"
    "            keypad_enabled=keypad_control_enabled,\n"
    "            native_alarm_enabled=native_alarm_control_enabled,\n"
    "            response_timeout_seconds=3,\n"
    "            verify_delay_ms=0,\n"
    "        ),\n"
    "        event_history=EventHistorySettings(\n",
)

manifest = ROOT / "vista128_bridge/config.yaml"
replace_once(
    manifest,
    "  chime_zones: \"\"\n",
    "  chime_zones: \"\"\n"
    "  control_enabled: false\n"
    "  keypad_control_enabled: false\n"
    "  native_alarm_control_enabled: false\n"
    "  control_response_timeout_seconds: 3\n"
    "  control_verify_delay_ms: 400\n",
)
replace_once(
    manifest,
    "  chime_zones: str\n",
    "  chime_zones: str\n"
    "  control_enabled: bool\n"
    "  keypad_control_enabled: bool\n"
    "  native_alarm_control_enabled: bool\n"
    "  control_response_timeout_seconds: int(1,10)\n"
    "  control_verify_delay_ms: int(0,5000)\n",
)

run_sh = ROOT / "vista128_bridge/run.sh"
replace_once(
    run_sh,
    "export CHIME_ZONES=\"$(config_or_default 'chime_zones' '')\"\n",
    "export CHIME_ZONES=\"$(config_or_default 'chime_zones' '')\"\n"
    "export CONTROL_ENABLED=\"$(config_or_default 'control_enabled' 'false')\"\n"
    "export KEYPAD_CONTROL_ENABLED=\"$(config_or_default 'keypad_control_enabled' 'false')\"\n"
    "export NATIVE_ALARM_CONTROL_ENABLED=\"$(config_or_default 'native_alarm_control_enabled' 'false')\"\n"
    "export CONTROL_RESPONSE_TIMEOUT_SECONDS=\"$(config_or_default 'control_response_timeout_seconds' '3')\"\n"
    "export CONTROL_VERIFY_DELAY_MS=\"$(config_or_default 'control_verify_delay_ms' '400')\"\n",
)
replace_once(
    run_sh,
    "if bashio::var.true \"${TRANSPORT_PRINT_ENABLED}\"; then\n",
    "if bashio::var.true \"${CONTROL_ENABLED}\"; then\n"
    "  bashio::log.warning \"Panel control ENABLED: keypad=${KEYPAD_CONTROL_ENABLED}, native_alarm=${NATIVE_ALARM_CONTROL_ENABLED}\"\n"
    "fi\n"
    "if bashio::var.true \"${TRANSPORT_PRINT_ENABLED}\"; then\n",
)

# ---------------------------------------------------------------------------
# Protocol builders
# ---------------------------------------------------------------------------
protocol = ROOT / "vista128_bridge/app/vista_bridge/protocol.py"
replace_once(
    protocol,
    "STATE_SYNC_QUERIES: tuple[ProtocolQuery, ...] = STARTUP_QUERIES[:2]\n",
    "STATE_SYNC_QUERIES: tuple[ProtocolQuery, ...] = STARTUP_QUERIES[:2]\n"
    "ARMING_STATUS_QUERY = STARTUP_QUERIES[0]\n",
)
replace_once(
    protocol,
    "def build_keypad_display_query(partition: int) -> ProtocolQuery:\n",
    "KEYSTROKE_CODES = {\n"
    "    **{str(value): str(value) for value in range(10)},\n"
    "    \"*\": \"A\",\n"
    "    \"#\": \"B\",\n"
    "    \"PANIC_A\": \"C\",\n"
    "    \"PANIC_B\": \"D\",\n"
    "    \"PANIC_C\": \"E\",\n"
    "}\n\n"
    "NATIVE_ARM_COMMANDS = {\n"
    "    \"ARM_AWAY\": \"AA\",\n"
    "    \"ARM_HOME\": \"AH\",\n"
    "    \"ARM_NIGHT\": \"AI\",\n"
    "    \"ARM_MAXIMUM\": \"AM\",\n"
    "    \"FORCE_ARM_AWAY\": \"FA\",\n"
    "    \"FORCE_ARM_HOME\": \"FH\",\n"
    "    \"DISARM\": \"AD\",\n"
    "}\n\n\n"
    "def build_command_frame(command: str, data: str) -> bytes:\n"
    "    if len(command) != 2 or not command.isascii():\n"
    "        raise ValueError(\"VISTA command must be two ASCII characters\")\n"
    "    if not data.isascii():\n"
    "        raise ValueError(\"VISTA command data must be ASCII\")\n"
    "    body = f\"{command}{data}00\"\n"
    "    total_length = 2 + len(body) + 2\n"
    "    if total_length > 0xFF:\n"
    "        raise ValueError(\"VISTA command frame is too long\")\n"
    "    prefix = f\"{total_length:02X}{body}\".encode(\"ascii\")\n"
    "    checksum = (-sum(prefix)) & 0xFF\n"
    "    return prefix + f\"{checksum:02X}\\r\\n\".encode(\"ascii\")\n\n\n"
    "def build_keypad_stroke_command(partition: int, keys) -> bytes:\n"
    "    if partition < 1 or partition > 8:\n"
    "        raise ValueError(\"keypad partition must be 1..8\")\n"
    "    if isinstance(keys, str):\n"
    "        tokens = [keys] if keys.upper().startswith(\"PANIC_\") else list(keys)\n"
    "    else:\n"
    "        tokens = list(keys)\n"
    "    if not 1 <= len(tokens) <= 5:\n"
    "        raise ValueError(\"keypad command must contain 1..5 keystrokes\")\n"
    "    encoded = []\n"
    "    for token in tokens:\n"
    "        normalized = str(token).upper() if str(token).upper().startswith(\"PANIC_\") else str(token)\n"
    "        code = KEYSTROKE_CODES.get(normalized)\n"
    "        if code is None:\n"
    "            raise ValueError(f\"unsupported keypad keystroke: {token!r}\")\n"
    "        encoded.append(code)\n"
    "    return build_command_frame(\"KS\", f\"{partition}{''.join(encoded)}\")\n\n\n"
    "def build_native_alarm_command(action: str, code: str, partitions) -> bytes:\n"
    "    normalized_action = str(action).upper()\n"
    "    command = NATIVE_ARM_COMMANDS.get(normalized_action)\n"
    "    if command is None:\n"
    "        raise ValueError(f\"unsupported native alarm action: {action!r}\")\n"
    "    code = str(code)\n"
    "    if len(code) != 4 or not code.isdigit():\n"
    "        raise ValueError(\"VISTA user code must contain exactly four digits\")\n"
    "    selected = {int(value) for value in partitions}\n"
    "    if not selected or any(value < 1 or value > 8 for value in selected):\n"
    "        raise ValueError(\"alarm command partitions must contain 1..8\")\n"
    "    partition_mask = ''.join('1' if value in selected else '0' for value in range(1, 9))\n"
    "    return build_command_frame(command, f\"00{code}{partition_mask}\")\n\n\n"
    "def build_keypad_display_query(partition: int) -> ProtocolQuery:\n",
)

# ---------------------------------------------------------------------------
# Synchronizer helpers for externally serialized control transactions.
# ---------------------------------------------------------------------------
sync = ROOT / "vista128_bridge/app/vista_bridge/synchronizer.py"
replace_once(
    sync,
    "    EVENT_LOG_QUERY,\n",
    "    ARMING_STATUS_QUERY,\n    EVENT_LOG_QUERY,\n",
)
replace_once(
    sync,
    "    def mark_ready(self) -> None:\n        self.ready_event.set()\n",
    "    def mark_ready(self) -> None:\n        self.ready_event.set()\n\n"
    "    def begin_external_transaction(self) -> None:\n"
    "        self._active.set()\n"
    "        self.ready_event.clear()\n\n"
    "    def end_external_transaction(self) -> None:\n"
    "        self._active.clear()\n\n"
    "    async def wait_ready(self, timeout_seconds: int) -> bool:\n"
    "        try:\n"
    "            await asyncio.wait_for(self.ready_event.wait(), timeout=timeout_seconds)\n"
    "            return True\n"
    "        except asyncio.TimeoutError:\n"
    "            return False\n\n"
    "    async def run_arming_refresh(self) -> bool:\n"
    "        return await self.run_sync(\n"
    "            (ARMING_STATUS_QUERY,),\n"
    "            source=\"control-verify\",\n"
    "            description=\"post-control arming verification\",\n"
    "        )\n",
)

# ---------------------------------------------------------------------------
# Control coordinator
# ---------------------------------------------------------------------------
control_py = ROOT / "vista128_bridge/app/vista_bridge/control.py"
control_py.write_text('''from __future__ import annotations

import asyncio
from dataclasses import dataclass
import itertools
import logging
import queue
import threading
import time
from collections.abc import Callable

from .config import ControlSettings
from .protocol import build_keypad_stroke_command, build_native_alarm_command
from .state import VistaState
from .synchronizer import VistaSynchronizer

LOG = logging.getLogger(__name__)

SendQuery = Callable[[bytes, str, str], tuple[bool, str]]
BoolCallback = Callable[[], bool]
PublishResult = Callable[[dict], None]


@dataclass(frozen=True)
class ControlRequest:
    request_id: int
    kind: str
    partition: int
    value: str
    code: str
    generation: int
    enqueued_at: float


EXPECTED_ARMING_MODES = {
    "ARM_AWAY": {"A"},
    "ARM_HOME": {"H"},
    "ARM_NIGHT": {"I"},
    "ARM_MAXIMUM": {"M"},
    "FORCE_ARM_AWAY": {"A", "B"},
    "FORCE_ARM_HOME": {"H", "B"},
    "DISARM": {"D", "N"},
}


class VistaControlCoordinator:
    """Serialized, non-replaying VISTA write coordinator.

    MQTT callbacks run on Paho's network thread, so enqueue methods use a
    thread-safe queue. The async worker serializes control transactions through
    the same synchronizer lock used by all read queries. A request belongs to a
    single panel TCP generation and is never carried across reconnects.
    """

    def __init__(
        self,
        settings: ControlSettings,
        state: VistaState,
        synchronizer: VistaSynchronizer,
        is_connected: BoolCallback,
        send_query: SendQuery,
        publish_result: PublishResult,
    ) -> None:
        self.settings = settings
        self.state = state
        self.synchronizer = synchronizer
        self.is_connected = is_connected
        self.send_query = send_query
        self.publish_result = publish_result
        self._queue: queue.Queue[ControlRequest] = queue.Queue(maxsize=64)
        self._automation_available = threading.Event()
        self._generation_lock = threading.Lock()
        self._generation = 0
        self._request_ids = itertools.count(1)

    def automation_available(self) -> bool:
        return self._automation_available.is_set()

    def set_automation_available(self, available: bool) -> None:
        if available:
            self._automation_available.set()
        else:
            self._automation_available.clear()
            self.discard_pending("automation_unavailable")

    def reset_session(self) -> int:
        with self._generation_lock:
            self._generation += 1
            generation = self._generation
        self._automation_available.clear()
        self.discard_pending("panel_session_reset")
        return generation

    def _current_generation(self) -> int:
        with self._generation_lock:
            return self._generation

    def discard_pending(self, reason: str) -> int:
        discarded = 0
        while True:
            try:
                request = self._queue.get_nowait()
            except queue.Empty:
                break
            discarded += 1
            self._result(request, False, reason)
        if discarded:
            LOG.warning("Discarded %d pending VISTA control request(s): %s", discarded, reason)
        return discarded

    def _preflight(self, kind: str) -> tuple[bool, str]:
        if not self.settings.enabled:
            return False, "control_disabled"
        if kind == "keypad" and not self.settings.keypad_enabled:
            return False, "keypad_control_disabled"
        if kind == "alarm" and not self.settings.native_alarm_enabled:
            return False, "native_alarm_control_disabled"
        if not self.is_connected():
            return False, "panel_offline"
        if not self.automation_available():
            return False, "automation_interface_unavailable"
        return True, "accepted"

    def enqueue_keypad(self, partition: int, key: str) -> tuple[bool, str]:
        ok, detail = self._preflight("keypad")
        if not ok:
            return ok, detail
        try:
            build_keypad_stroke_command(partition, [key])
        except ValueError as exc:
            return False, str(exc)
        return self._enqueue("keypad", partition, key, "")

    def enqueue_alarm(self, partition: int, action: str, code: str) -> tuple[bool, str]:
        ok, detail = self._preflight("alarm")
        if not ok:
            return ok, detail
        try:
            build_native_alarm_command(action, code, (partition,))
        except ValueError as exc:
            return False, str(exc)
        return self._enqueue("alarm", partition, str(action).upper(), str(code))

    def _enqueue(self, kind: str, partition: int, value: str, code: str) -> tuple[bool, str]:
        request = ControlRequest(
            request_id=next(self._request_ids),
            kind=kind,
            partition=partition,
            value=value,
            code=code,
            generation=self._current_generation(),
            enqueued_at=time.monotonic(),
        )
        try:
            self._queue.put_nowait(request)
        except queue.Full:
            return False, "control_queue_full"
        return True, "queued"

    async def run(self, stop_event: asyncio.Event) -> None:
        while not stop_event.is_set():
            if not await self.process_next():
                await asyncio.sleep(0.02)

    async def process_next(self) -> bool:
        try:
            request = self._queue.get_nowait()
        except queue.Empty:
            return False
        await self._process(request)
        return True

    async def _process(self, request: ControlRequest) -> None:
        if request.generation != self._current_generation():
            self._result(request, False, "stale_session")
            return
        if time.monotonic() - request.enqueued_at > 4.5:
            self._result(request, False, "request_expired")
            return
        ok, detail = self._preflight(request.kind)
        if not ok:
            self._result(request, False, detail)
            return

        if request.kind == "keypad":
            frame = build_keypad_stroke_command(request.partition, [request.value])
            label = f"keypad_p{request.partition}"
        else:
            frame = build_native_alarm_command(request.value, request.code, (request.partition,))
            label = f"{request.value.lower()}_p{request.partition}"

        async with self.synchronizer.lock:
            if request.generation != self._current_generation() or not self.is_connected():
                self._result(request, False, "stale_session")
                return
            if not self.automation_available():
                self._result(request, False, "automation_interface_unavailable")
                return
            self.synchronizer.begin_external_transaction()
            try:
                accepted, detail = self.send_query(frame, "control", label)
                if not accepted:
                    self._result(request, False, detail)
                    return
                if not await self.synchronizer.wait_ready(self.settings.response_timeout_seconds):
                    self._result(request, False, "no_ready_ack")
                    return
            finally:
                self.synchronizer.end_external_transaction()

        if self.settings.verify_delay_ms:
            await asyncio.sleep(self.settings.verify_delay_ms / 1000)
        if request.generation != self._current_generation() or not self.is_connected():
            self._result(request, False, "connection_lost_after_send")
            return

        if request.kind == "keypad":
            refreshed = await self.synchronizer.run_keypad_refresh(request.partition)
            self._result(
                request,
                True,
                "accepted",
                display_refreshed=bool(refreshed),
            )
            return

        refreshed = await self.synchronizer.run_arming_refresh()
        partition = self.state.partitions.get(request.partition)
        raw_mode = partition.raw_mode if partition is not None else ""
        expected = EXPECTED_ARMING_MODES.get(request.value, set())
        confirmed = bool(refreshed and raw_mode in expected)
        self._result(
            request,
            confirmed,
            "confirmed" if confirmed else "verification_mismatch",
            action=request.value,
            raw_mode=raw_mode or None,
        )

    def _result(self, request: ControlRequest, ok: bool, status: str, **extra) -> None:
        payload = {
            "request_id": request.request_id,
            "ok": bool(ok),
            "kind": request.kind,
            "partition": request.partition,
            "status": status,
            **extra,
        }
        # Never publish a keypad digit or alarm credential in result telemetry.
        if request.kind == "keypad":
            payload["action"] = "keypress"
        self.publish_result(payload)
''')

# ---------------------------------------------------------------------------
# MQTT discovery and command ingestion
# ---------------------------------------------------------------------------
discovery = ROOT / "vista128_bridge/app/vista_bridge/mqtt_discovery.py"
replace_once(
    discovery,
    "def partition_config(partition: int, topic: TopicFn) -> dict:\n    return {\n",
    "def partition_config(partition: int, topic: TopicFn, control_enabled: bool = False) -> dict:\n"
    "    config = {\n",
)
replace_once(
    discovery,
    "        \"command_topic\": topic(f\"partition/{partition}/command\"),\n",
    "",
)
replace_once(
    discovery,
    "        \"supported_features\": [],\n        \"code_arm_required\": False,\n        \"code_disarm_required\": False,\n",
    "        \"supported_features\": [],\n",
)
replace_once(
    discovery,
    "        \"enabled_by_default\": partition == 1,\n    }\n\n\ndef keypad_config",
    "        \"enabled_by_default\": partition == 1,\n"
    "    }\n"
    "    if control_enabled:\n"
    "        config.update(\n"
    "            {\n"
    "                \"command_topic\": topic(f\"partition/{partition}/command\"),\n"
    "                \"code\": \"REMOTE_CODE\",\n"
    "                \"code_arm_required\": True,\n"
    "                \"code_disarm_required\": True,\n"
    "                \"code_trigger_required\": False,\n"
    "                \"command_template\": '{\"action\":\"{{ action }}\",\"code\":\"{{ code }}\"}',\n"
    "                \"supported_features\": [\"arm_home\", \"arm_away\", \"arm_night\"],\n"
    "                \"retain\": False,\n"
    "            }\n"
    "        )\n"
    "    return config\n\n\n"
    "def keypad_config",
)

mqtt = ROOT / "vista128_bridge/app/vista_bridge/mqtt_client.py"
replace_once(
    mqtt,
    "        raw_tx_callback: Callable[[bytes], tuple[bool, str]],\n    ) -> None:\n",
    "        raw_tx_callback: Callable[[bytes], tuple[bool, str]],\n"
    "        keypad_command_callback: Callable[[int, str], tuple[bool, str]] | None = None,\n"
    "        alarm_command_callback: Callable[[int, str, str], tuple[bool, str]] | None = None,\n"
    "    ) -> None:\n",
)
replace_once(
    mqtt,
    "        self.raw_tx_callback = raw_tx_callback\n",
    "        self.raw_tx_callback = raw_tx_callback\n"
    "        self.keypad_command_callback = keypad_command_callback\n"
    "        self.alarm_command_callback = alarm_command_callback\n",
)
replace_once(
    mqtt,
    "            partition_config(partition, self.topic),\n",
    "            partition_config(\n"
    "                partition,\n"
    "                self.topic,\n"
    "                control_enabled=(\n"
    "                    self.settings.control.enabled\n"
    "                    and self.settings.control.native_alarm_enabled\n"
    "                ),\n"
    "            ),\n",
)
replace_once(
    mqtt,
    "        self.publish_json(\n            f\"{prefix}/attributes\",\n            keypad.attributes(),\n            retain=True,\n            qos=1,\n        )\n",
    "        attributes = keypad.attributes()\n"
    "        keypad_control = bool(\n"
    "            self.settings.control.enabled and self.settings.control.keypad_enabled\n"
    "        )\n"
    "        attributes[\"control_enabled\"] = keypad_control\n"
    "        attributes[\"command_topic\"] = (\n"
    "            self.topic(f\"keypad/{keypad.partition}/command\")\n"
    "            if keypad_control\n"
    "            else None\n"
    "        )\n"
    "        self.publish_json(\n"
    "            f\"{prefix}/attributes\",\n"
    "            attributes,\n"
    "            retain=True,\n"
    "            qos=1,\n"
    "        )\n",
)
replace_once(
    mqtt,
    "        client.subscribe(self.topic(\"partition/+/command\"), qos=1)\n",
    "        if self.settings.control.enabled and self.settings.control.native_alarm_enabled:\n"
    "            client.subscribe(self.topic(\"partition/+/command\"), qos=1)\n"
    "        if self.settings.control.enabled and self.settings.control.keypad_enabled:\n"
    "            client.subscribe(self.topic(\"keypad/+/command\"), qos=1)\n",
)
replace_once(
    mqtt,
    "    def _on_message(self, client, userdata, message) -> None:\n        if self._is_partition_command(message.topic):\n            self._reject_partition_command(message.topic, message.payload)\n            return\n",
    "    def _on_message(self, client, userdata, message) -> None:\n"
    "        if self._is_keypad_command(message.topic):\n"
    "            self._handle_keypad_command(message.topic, message.payload)\n"
    "            return\n"
    "        if self._is_partition_command(message.topic):\n"
    "            self._handle_partition_command(message.topic, message.payload)\n"
    "            return\n",
)
replace_once(
    mqtt,
    "    def _is_partition_command(self, topic: str) -> bool:\n        return topic.startswith(self.topic(\"partition/\")) and topic.endswith(\"/command\")\n\n    def _reject_partition_command(self, topic: str, payload: bytes) -> None:\n        text = payload.decode(\"utf-8\", errors=\"replace\")\n        LOG.warning(\"Rejected alarm command on %s: %r\", topic, text)\n        self.publish_json(\n            \"control/rejected\",\n            {\"topic\": topic, \"payload\": text, \"reason\": \"control_disabled\"},\n        )\n",
    "    def _is_partition_command(self, topic: str) -> bool:\n"
    "        return topic.startswith(self.topic(\"partition/\")) and topic.endswith(\"/command\")\n\n"
    "    def _is_keypad_command(self, topic: str) -> bool:\n"
    "        return topic.startswith(self.topic(\"keypad/\")) and topic.endswith(\"/command\")\n\n"
    "    def _partition_from_topic(self, topic: str, category: str) -> int:\n"
    "        prefix = self.topic(f\"{category}/\")\n"
    "        if not topic.startswith(prefix) or not topic.endswith(\"/command\"):\n"
    "            raise ValueError(\"invalid command topic\")\n"
    "        value = topic[len(prefix):-len(\"/command\")]\n"
    "        partition = int(value)\n"
    "        if partition < 1 or partition > 8:\n"
    "            raise ValueError(\"partition must be 1..8\")\n"
    "        return partition\n\n"
    "    def _publish_control_rejection(self, kind: str, partition: int | None, reason: str) -> None:\n"
    "        LOG.warning(\"Rejected %s control request P%s: %s\", kind, partition or \"?\", reason)\n"
    "        self.publish_json(\n"
    "            \"control/rejected\",\n"
    "            {\"kind\": kind, \"partition\": partition, \"reason\": reason},\n"
    "        )\n\n"
    "    def _handle_keypad_command(self, topic: str, payload: bytes) -> None:\n"
    "        partition = None\n"
    "        try:\n"
    "            partition = self._partition_from_topic(topic, \"keypad\")\n"
    "            key = payload.decode(\"ascii\", errors=\"strict\")\n"
    "            if self.keypad_command_callback is None:\n"
    "                raise ValueError(\"keypad control callback unavailable\")\n"
    "            accepted, detail = self.keypad_command_callback(partition, key)\n"
    "            if not accepted:\n"
    "                raise ValueError(detail)\n"
    "        except Exception as exc:\n"
    "            self._publish_control_rejection(\"keypad\", partition, str(exc))\n\n"
    "    def _handle_partition_command(self, topic: str, payload: bytes) -> None:\n"
    "        partition = None\n"
    "        action = \"\"\n"
    "        try:\n"
    "            partition = self._partition_from_topic(topic, \"partition\")\n"
    "            request = json.loads(payload.decode(\"utf-8\"))\n"
    "            action = str(request.get(\"action\", \"\")).upper()\n"
    "            code = str(request.get(\"code\", \"\"))\n"
    "            if self.alarm_command_callback is None:\n"
    "                raise ValueError(\"native alarm control callback unavailable\")\n"
    "            accepted, detail = self.alarm_command_callback(partition, action, code)\n"
    "            if not accepted:\n"
    "                raise ValueError(detail)\n"
    "        except Exception as exc:\n"
    "            # Never include the inbound payload or credential in logs/telemetry.\n"
    "            self._publish_control_rejection(\"alarm\", partition, str(exc))\n",
)

# ---------------------------------------------------------------------------
# Bridge and message handler wiring
# ---------------------------------------------------------------------------
bridge = ROOT / "vista128_bridge/app/vista_bridge/bridge.py"
replace_once(
    bridge,
    "from .config import Settings\n",
    "from .config import Settings\nfrom .control import VistaControlCoordinator\n",
)
replace_once(
    bridge,
    "        self.mqtt = MqttPublisher(settings, self.enqueue_raw_tx)\n",
    "",
)
replace_once(
    bridge,
    "        self.synchronizer = VistaSynchronizer(\n",
    "        self.synchronizer = VistaSynchronizer(\n",
)
replace_once(
    bridge,
    "        self.handler = ProtocolMessageHandler(\n",
    "        self.control = VistaControlCoordinator(\n"
    "            settings.control,\n"
    "            self.state,\n"
    "            self.synchronizer,\n"
    "            self._is_connected,\n"
    "            self._send_sync_query,\n"
    "            self._publish_control_result,\n"
    "        )\n"
    "        self.mqtt = MqttPublisher(\n"
    "            settings,\n"
    "            self.enqueue_raw_tx,\n"
    "            self.enqueue_keypad_control,\n"
    "            self.enqueue_alarm_control,\n"
    "        )\n"
    "        self.handler = ProtocolMessageHandler(\n",
)
replace_once(
    bridge,
    "            self.event_store,\n        )\n\n    def enqueue_raw_tx",
    "            self.event_store,\n"
    "            self.control,\n"
    "        )\n\n"
    "    def _publish_control_result(self, payload: dict) -> None:\n"
    "        self.mqtt.publish_json(\"control/result\", payload, qos=1)\n\n"
    "    def enqueue_keypad_control(self, partition: int, key: str) -> tuple[bool, str]:\n"
    "        return self.control.enqueue_keypad(partition, key)\n\n"
    "    def enqueue_alarm_control(self, partition: int, action: str, code: str) -> tuple[bool, str]:\n"
    "        return self.control.enqueue_alarm(partition, action, code)\n\n"
    "    def enqueue_raw_tx",
)
replace_once(
    bridge,
    "        background = [\n            asyncio.create_task(self._metrics_loop(), name=\"metrics\"),\n",
    "        background = [\n"
    "            asyncio.create_task(self._metrics_loop(), name=\"metrics\"),\n"
    "            asyncio.create_task(self.control.run(self._stop), name=\"panel-control\"),\n",
)
replace_once(
    bridge,
    "        self.synchronizer.reset_connection_state()\n        self.state.reset_connection_derived_annunciators()\n",
    "        self.synchronizer.reset_connection_state()\n"
    "        self.control.reset_session()\n"
    "        self.state.reset_connection_derived_annunciators()\n",
)
replace_once(
    bridge,
    "        self._panel_connected.clear()\n        self.synchronizer.reset_connection_state()\n",
    "        self._panel_connected.clear()\n"
    "        self.synchronizer.reset_connection_state()\n"
    "        self.control.reset_session()\n",
)
replace_once(
    bridge,
    "        if item.source == \"debug\":\n            LOG.warning(\"RAW TX sent (%d bytes): %s\", len(item.data), item.data.hex(\" \"))\n            return\n",
    "        if item.source == \"debug\":\n"
    "            LOG.warning(\"RAW TX sent (%d bytes): %s\", len(item.data), item.data.hex(\" \"))\n"
    "            return\n"
    "        if item.source == \"control\":\n"
    "            LOG.info(\"TX control [%s] %d bytes (payload redacted)\", item.label, len(item.data))\n"
    "            return\n",
)

handler = ROOT / "vista128_bridge/app/vista_bridge/message_handler.py"
replace_once(
    handler,
    "from .config import Settings\n",
    "from .config import Settings\nfrom .control import VistaControlCoordinator\n",
)
replace_once(
    handler,
    "        event_store: EventStore | None = None,\n    ) -> None:\n",
    "        event_store: EventStore | None = None,\n"
    "        control: VistaControlCoordinator | None = None,\n"
    "    ) -> None:\n",
)
replace_once(
    handler,
    "        self.event_store = event_store\n",
    "        self.event_store = event_store\n        self.control = control\n",
)
replace_once(
    handler,
    "        self.mqtt.publish(\"panel/automation_available\", \"ON\", retain=True, qos=1)\n",
    "        self.mqtt.publish(\"panel/automation_available\", \"ON\", retain=True, qos=1)\n"
    "        if self.control is not None:\n"
    "            self.control.set_automation_available(True)\n",
)
replace_once(
    handler,
    "        self.mqtt.publish(\"panel/automation_available\", \"OFF\", retain=True, qos=1)\n",
    "        self.mqtt.publish(\"panel/automation_available\", \"OFF\", retain=True, qos=1)\n"
    "        if self.control is not None:\n"
    "            self.control.set_automation_available(False)\n",
)

# ---------------------------------------------------------------------------
# Frontend keypad command path.
# ---------------------------------------------------------------------------
frontend = ROOT / "frontend/vista-keypad-card.js"
replace_once(frontend, 'const VISTA_KEYPAD_CARD_VERSION = "0.3.19";', 'const VISTA_KEYPAD_CARD_VERSION = "0.3.20";')
replace_once(
    frontend,
    "        <div class=\"readonly\">Monitoring remains read-only. The editor does not expose a panel-control toggle.</div>\n",
    "        <div class=\"toggle\"><span class=\"label\">Enable keypad input</span><input data-control-toggle type=\"checkbox\" ${checked(this._config.read_only === false)}></div>\n"
    "        <div class=\"readonly\">Requires bridge <code>control_enabled</code> and <code>keypad_control_enabled</code>. A-D function buttons remain inert until explicitly mapped.</div>\n",
)
replace_once(
    frontend,
    "    this.shadowRoot.querySelectorAll(\"[data-top]\").forEach((el) => {\n",
    "    this.shadowRoot.querySelector(\"[data-control-toggle]\")?.addEventListener(\"change\", (event) => {\n"
    "      this._topLevel(\"read_only\", !event.currentTarget.checked);\n"
    "    });\n"
    "    this.shadowRoot.querySelectorAll(\"[data-top]\").forEach((el) => {\n",
)
replace_once(
    frontend,
    "      a.chime_descriptor ?? null,\n",
    "      a.chime_descriptor ?? null,\n"
    "      a.control_enabled ?? null,\n"
    "      a.command_topic ?? null,\n",
)
replace_once(
    frontend,
    "        chimeDescriptor: \"\",\n",
    "        chimeDescriptor: \"\",\n"
    "        controlEnabled: false,\n"
    "        commandTopic: \"\",\n",
)
replace_once(
    frontend,
    "      chimeDescriptor: String(a.chime_descriptor ?? \"\"),\n",
    "      chimeDescriptor: String(a.chime_descriptor ?? \"\"),\n"
    "      controlEnabled: boolValue(a.control_enabled, false),\n"
    "      commandTopic: String(a.command_topic ?? \"\"),\n",
)
replace_once(
    frontend,
    "      <div class=\"read-only-note\" id=\"read-only-note\">Read-only monitoring. Keypad control is not enabled.</div>\n",
    "      <div class=\"read-only-note\" id=\"read-only-note\">Keypad control is not enabled.</div>\n",
)
old_handle = '''  _handleKey(button) {
    const key = button?.dataset?.key;
    if (!key) return;


    if (this._config.read_only !== false) {
      const note = this.shadowRoot.getElementById("read-only-note");
      if (note) {
        note.classList.add("show");
        clearTimeout(this._pressTimer);
        this._pressTimer = setTimeout(() => note.classList.remove("show"), 1200);
      }
      return;
    }

    this.dispatchEvent(new CustomEvent("vista-keypad-key", {
      bubbles: true,
      composed: true,
      detail: {
        key,
        entity: this._config.entity,
        model: this._config.model,
      },
    }));
  }
'''
new_handle = '''  _showControlNote(message) {
    const note = this.shadowRoot?.getElementById("read-only-note");
    if (!note) return;
    note.textContent = message;
    note.classList.add("show");
    clearTimeout(this._pressTimer);
    this._pressTimer = setTimeout(() => note.classList.remove("show"), 1600);
  }

  async _handleKey(button) {
    const key = button?.dataset?.key;
    if (!key) return;

    if (this._config.read_only !== false) {
      this._showControlNote("Enable keypad input in the card editor first.");
      return;
    }

    if (![..."0123456789", "*", "#"].includes(key)) {
      this._showControlNote("A-D function keys are not mapped yet.");
      return;
    }

    const display = this._displayState();
    if (!display.available) {
      this._showControlNote("Panel is offline.");
      return;
    }
    if (!display.controlEnabled || !display.commandTopic) {
      this._showControlNote("Bridge keypad control is disabled or unavailable.");
      return;
    }
    if (!this._hass?.callService) {
      this._showControlNote("Home Assistant MQTT publish action is unavailable.");
      return;
    }

    try {
      await this._hass.callService("mqtt", "publish", {
        topic: display.commandTopic,
        payload: key,
        qos: 1,
        retain: false,
      });
    } catch (_) {
      this._showControlNote("Keypad command could not be published.");
      return;
    }

    this.dispatchEvent(new CustomEvent("vista-keypad-key", {
      bubbles: true,
      composed: true,
      detail: {
        key,
        entity: this._config.entity,
        model: this._config.model,
      },
    }));
  }
'''
replace_once(frontend, old_handle, new_handle)

# ---------------------------------------------------------------------------
# Documentation
# ---------------------------------------------------------------------------
readme = ROOT / "vista128_bridge/README.md"
replace_once(
    readme,
    "> **Release candidate status:** 0.2.6-rc.6 is read-only.",
    "> **Release candidate status:** 0.2.6-rc.6 is read-only.",
) if False else None
# Append control-development notes without changing the currently packaged RC6 version text.
text = readme.read_text()
if "## Experimental panel control" not in text:
    text += '''\n\n## Experimental panel control\n\nThe next release candidate adds a gated native write path. Control remains disabled unless all required App toggles are explicitly enabled.\n\n```yaml\ncontrol_enabled: true\nkeypad_control_enabled: true\nnative_alarm_control_enabled: true\n```\n\nKeypad input uses typed VISTA `KS` frames for `0-9`, `*`, and `#`. The A-D visual function keys are intentionally not transmitted as literal letters because the VISTA protocol uses those data characters for other keystroke encodings.\n\nNative Home Assistant alarm control uses the documented VISTA arm/disarm command families and Home Assistant MQTT remote-code validation. PIN values are never retained, written to App logs, or echoed in control telemetry. Control TX payloads are redacted from bridge logging.\n'''
    readme.write_text(text)

frontend_readme = ROOT / "frontend/README.md"
text = frontend_readme.read_text()
if "### Keypad input" not in text:
    text += '''\n\n### Keypad input\n\nCard `0.3.20` can publish real keypad input when both the bridge and card are explicitly enabled for control. Enable the App's `control_enabled` and `keypad_control_enabled`, then enable **Keypad input** in the card visual editor. Numeric keys, `*`, and `#` publish non-retained MQTT commands through Home Assistant's MQTT publish action. A-D function buttons remain intentionally unmapped pending explicit action/hold semantics.\n'''
    frontend_readme.write_text(text)
