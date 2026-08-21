from __future__ import annotations

import json
import logging
from typing import Callable

import paho.mqtt.client as mqtt

from .config import Settings
from .mqtt_discovery import (
    KEYPAD_ALARM_SPECS,
    ZONE_CONDITION_SPECS,
    device_info,
    diagnostic_entities,
    event_history_config,
    keypad_alarm_configs,
    keypad_config,
    panel_alarm_configs,
    partition_config,
    zone_condition_configs,
    zone_summary_entities,
)
from .protocol import SystemEvent
from .state import KeypadState, PartitionState, VistaState, ZoneState
from .version import VERSION

LOG = logging.getLogger(__name__)


class MqttPublisher:
    def __init__(
        self,
        settings: Settings,
        raw_tx_callback: Callable[[bytes], tuple[bool, str]],
        keypad_command_callback: Callable[[int, str], tuple[bool, str]] | None = None,
        alarm_command_callback: Callable[[int, str, str], tuple[bool, str]] | None = None,
    ) -> None:
        self.settings = settings
        self.mqtt = settings.mqtt
        self.raw_tx_callback = raw_tx_callback
        self.keypad_command_callback = keypad_command_callback
        self.alarm_command_callback = alarm_command_callback
        self._client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id="vista128-bridge",
            protocol=mqtt.MQTTv311,
        )
        if self.mqtt.username:
            self._client.username_pw_set(self.mqtt.username, self.mqtt.password)
        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect
        self._client.on_message = self._on_message
        self._client.reconnect_delay_set(min_delay=1, max_delay=30)
        self._client.will_set(
            self.topic("bridge/availability"),
            "offline",
            qos=1,
            retain=True,
        )

    def topic(self, suffix: str) -> str:
        return f"{self.mqtt.base_topic}/{suffix.strip('/')}"

    def start(self) -> None:
        self._client.connect_async(self.mqtt.host, self.mqtt.port, keepalive=30)
        self._client.loop_start()

    def stop(self) -> None:
        try:
            self.publish("bridge/availability", "offline", retain=True)
            self._client.disconnect()
        finally:
            self._client.loop_stop()

    def publish(
        self,
        suffix: str,
        payload: str | int,
        *,
        retain: bool = False,
        qos: int = 0,
    ) -> None:
        self._client.publish(self.topic(suffix), payload=payload, qos=qos, retain=retain)

    def publish_json(
        self,
        suffix: str,
        payload: dict,
        *,
        retain: bool = False,
        qos: int = 0,
    ) -> None:
        encoded = json.dumps(payload, separators=(",", ":"))
        self.publish(suffix, encoded, retain=retain, qos=qos)

    def publish_discovery(self) -> None:
        self._clear_legacy_discovery()
        availability = {
            "availability_topic": self.topic("bridge/availability"),
            "payload_available": "online",
            "payload_not_available": "offline",
            "device": device_info(),
        }
        for object_id, (component, config) in diagnostic_entities(self.topic).items():
            self._publish_discovery_config(
                component,
                object_id,
                {**config, **availability},
            )
        for object_id, config in zone_summary_entities(self.topic).items():
            self._publish_discovery_config("sensor", object_id, config)
        for alarm_type, config in panel_alarm_configs(self.topic).items():
            self._publish_discovery_config(
                "binary_sensor", f"alarm_{alarm_type}", config
            )
        if self.settings.event_history.enabled:
            self._publish_discovery_config(
                "sensor", "event_journal", event_history_config(self.topic)
            )
        if self.settings.keypad.enabled:
            for partition in self.settings.keypad.partitions:
                self.publish_keypad_discovery(partition)

    def publish_partition_discovery(self, partition: int) -> None:
        self._publish_discovery_config(
            "alarm_control_panel",
            f"partition_{partition}",
            partition_config(
                partition,
                self.topic,
                control_enabled=(
                    self.settings.control.enabled
                    and self.settings.control.native_alarm_enabled
                ),
            ),
        )

    def publish_partition_state(self, partition: PartitionState) -> None:
        prefix = f"partition/{partition.partition}"
        self.publish(f"{prefix}/state", partition.ha_state, retain=True, qos=1)
        attributes = partition.attributes()
        attributes["control_enabled"] = bool(
            self.settings.control.enabled and self.settings.control.native_alarm_enabled
        )
        self.publish_json(
            f"{prefix}/attributes",
            attributes,
            retain=True,
            qos=1,
        )

    def publish_keypad_discovery(self, partition: int) -> None:
        self._publish_discovery_config(
            "sensor",
            f"keypad_{partition}",
            keypad_config(partition, self.topic),
        )
        for alarm_type, config in keypad_alarm_configs(partition, self.topic).items():
            self._publish_discovery_config(
                "binary_sensor",
                f"keypad_{partition}_alarm_{alarm_type}",
                config,
            )

    def publish_keypad_state(self, keypad: KeypadState) -> None:
        if not keypad.initialized:
            return
        prefix = f"keypad/{keypad.partition}"
        self.publish(f"{prefix}/state", keypad.ha_state, retain=True, qos=1)
        attributes = keypad.attributes()
        keypad_control = bool(
            self.settings.control.enabled and self.settings.control.keypad_enabled
        )
        attributes["control_enabled"] = keypad_control
        attributes["command_topic"] = (
            self.topic(f"keypad/{keypad.partition}/command")
            if keypad_control
            else None
        )
        self.publish_json(
            f"{prefix}/attributes",
            attributes,
            retain=True,
            qos=1,
        )

    def publish_alarm_states(self, state: VistaState) -> None:
        if self.settings.keypad.enabled:
            for partition in self.settings.keypad.partitions:
                keypad = state.keypads.get(partition)
                if keypad is not None:
                    self._publish_keypad_alarm_states(keypad)
        self._publish_panel_alarm_states(state)

    def _publish_keypad_alarm_states(self, keypad: KeypadState) -> None:
        prefix = f"keypad/{keypad.partition}/alarm"
        values: dict[str, bool | None] = {}
        for alarm_type, spec in KEYPAD_ALARM_SPECS.items():
            value = getattr(keypad, spec["attribute"])
            values[alarm_type] = value
            available = value is not None
            self.publish(
                f"{prefix}/{alarm_type}/available",
                "ON" if available else "OFF",
                retain=True,
                qos=1,
            )
            if available:
                self.publish(
                    f"{prefix}/{alarm_type}",
                    "ON" if value else "OFF",
                    retain=True,
                    qos=1,
                )

        active_types = [
            alarm_type for alarm_type, value in values.items() if value is True
        ]
        all_known = all(value is not None for value in values.values())
        aggregate_available = bool(active_types) or all_known
        self.publish(
            f"{prefix}/active/available",
            "ON" if aggregate_available else "OFF",
            retain=True,
            qos=1,
        )
        if aggregate_available:
            self.publish(
                f"{prefix}/active",
                "ON" if active_types else "OFF",
                retain=True,
                qos=1,
            )
        self.publish_json(
            f"{prefix}/active/attributes",
            {
                "active_types": active_types,
                "fire_alarm": values["fire"],
                "burglary_alarm": values["burglary"],
                "auxiliary_alarm": values["auxiliary"],
                "sound_mode": keypad.sound_mode,
            },
            retain=True,
            qos=1,
        )

    def _publish_panel_alarm_states(self, state: VistaState) -> None:
        prefix = "alarm"
        configured = (
            tuple(self.settings.keypad.partitions)
            if self.settings.keypad.enabled and self.settings.keypad.partitions
            else tuple(range(1, 9))
        )
        global_values: dict[str, bool | None] = {}
        active_partitions_by_type: dict[str, list[int]] = {}

        for alarm_type, spec in KEYPAD_ALARM_SPECS.items():
            values = {
                partition: getattr(keypad, spec["attribute"])
                for partition, keypad in state.keypads.items()
            }
            active_partitions = sorted(
                partition for partition, value in values.items() if value is True
            )
            active_partitions_by_type[alarm_type] = active_partitions
            configured_values = [values[partition] for partition in configured]
            available = bool(active_partitions) or all(
                value is not None for value in configured_values
            )
            value: bool | None = True if active_partitions else (False if available else None)
            global_values[alarm_type] = value

            self.publish(
                f"{prefix}/{alarm_type}/available",
                "ON" if available else "OFF",
                retain=True,
                qos=1,
            )
            if available:
                self.publish(
                    f"{prefix}/{alarm_type}",
                    "ON" if value else "OFF",
                    retain=True,
                    qos=1,
                )
            self.publish_json(
                f"{prefix}/{alarm_type}/attributes",
                {
                    "active_partitions": active_partitions,
                    "configured_partitions": list(configured),
                    "partition_states": {
                        str(partition): values[partition]
                        for partition in sorted(values)
                    },
                },
                retain=True,
                qos=1,
            )

        active_types = [
            alarm_type
            for alarm_type, value in global_values.items()
            if value is True
        ]
        aggregate_available = bool(active_types) or all(
            value is not None for value in global_values.values()
        )
        self.publish(
            f"{prefix}/active/available",
            "ON" if aggregate_available else "OFF",
            retain=True,
            qos=1,
        )
        if aggregate_available:
            self.publish(
                f"{prefix}/active",
                "ON" if active_types else "OFF",
                retain=True,
                qos=1,
            )
        self.publish_json(
            f"{prefix}/active/attributes",
            {
                "active_types": active_types,
                "fire_partitions": active_partitions_by_type["fire"],
                "burglary_partitions": active_partitions_by_type["burglary"],
                "auxiliary_partitions": active_partitions_by_type["auxiliary"],
                "configured_partitions": list(configured),
            },
            retain=True,
            qos=1,
        )

    def publish_zone_discovery(self, zone: ZoneState) -> None:
        if not zone.partition:
            return
        for key, config in zone_condition_configs(zone, self.topic).items():
            self._publish_discovery_config(
                "binary_sensor",
                f"zone_{zone.zone:03d}_{key}",
                config,
            )

    def publish_zone_state(self, zone: ZoneState) -> None:
        if not zone.partition:
            return
        prefix = f"zone/{zone.zone:03d}"
        for key, spec in ZONE_CONDITION_SPECS.items():
            active = bool(getattr(zone, spec["attribute"]))
            self.publish(f"{prefix}/{key}", "ON" if active else "OFF", retain=True, qos=1)
        self.publish_json(
            f"{prefix}/attributes",
            zone.attributes(),
            retain=True,
            qos=1,
        )

    def publish_zone_summaries(self, state: VistaState) -> None:
        for key, spec in ZONE_CONDITION_SPECS.items():
            zones = state.assigned_zones_with(spec["attribute"])
            prefix = f"zone_summary/{key}"
            self.publish(f"{prefix}/count", len(zones), retain=True, qos=1)
            self.publish_json(
                f"{prefix}/attributes",
                {
                    "count": len(zones),
                    "zone_numbers": [zone.zone for zone in zones],
                    "zones": [
                        {
                            "zone": zone.zone,
                            "partition": zone.partition,
                            "descriptor": zone.descriptor,
                        }
                        for zone in zones
                    ],
                },
                retain=True,
                qos=1,
            )

    def publish_event_history(
        self,
        *,
        count: int,
        last_dump_at: str,
        last_dump_seen: int,
        last_dump_inserted: int,
        events: list[dict],
    ) -> None:
        self.publish("event_history/count", count, retain=True, qos=1)
        self.publish_json(
            "event_history/attributes",
            {
                "count": count,
                "last_dump_at": last_dump_at or None,
                "last_dump_seen": last_dump_seen,
                "last_dump_inserted": last_dump_inserted,
                "events": events,
            },
            retain=True,
            qos=1,
        )

    def publish_event(
        self,
        event: SystemEvent,
        *,
        emit_stream: bool = True,
        received_at: str | None = None,
        panel_clock_offset_seconds: int | None = None,
    ) -> None:
        payload = {
            "event_code": event.code,
            "description": event.description,
            "zone": event.zone,
            "user": event.user,
            "partition": event.partition,
            "panel_timestamp": event.panel_timestamp,
            "minute": event.minute,
            "hour": event.hour,
            "day": event.day,
            "month": event.month,
            "year": 2000 + event.year,
        }
        if received_at:
            payload["received_at"] = received_at
        if panel_clock_offset_seconds is not None:
            payload["panel_clock_offset_seconds"] = panel_clock_offset_seconds

        self.publish_json("event/last", payload, retain=True, qos=1)
        self.publish("event/last_description", event.description, retain=True, qos=1)
        if emit_stream:
            self.publish_json("event", payload, qos=1)

    def _publish_discovery_config(
        self,
        component: str,
        object_id: str,
        config: dict,
    ) -> None:
        config.setdefault(
            "origin",
            {"name": "Vista Turbo RS232", "sw_version": VERSION},
        )
        topic = (
            f"{self.mqtt.discovery_prefix}/{component}/"
            f"vista128_bridge/{object_id}/config"
        )
        payload = json.dumps(config, separators=(",", ":"))
        self._client.publish(topic, payload, qos=1, retain=True)

    def _clear_discovery_config(self, component: str, object_id: str) -> None:
        topic = (
            f"{self.mqtt.discovery_prefix}/{component}/"
            f"vista128_bridge/{object_id}/config"
        )
        self._client.publish(topic, "", qos=1, retain=True)

    def _clear_legacy_discovery(self) -> None:
        for zone in range(1, 129):
            self._clear_discovery_config("binary_sensor", f"zone_{zone:03d}")
        for object_id in (
            "faulted_zones",
            "alarm_zones",
            "check_zones",
            "bypassed_zones",
        ):
            self._clear_discovery_config("sensor", object_id)

    def _on_connect(self, client, userdata, flags, reason_code, properties) -> None:
        if reason_code != 0:
            LOG.error("MQTT connection rejected: %s", reason_code)
            return
        LOG.info("Connected to MQTT broker")
        self.publish("bridge/availability", "online", retain=True, qos=1)
        self.publish_discovery()
        if self.settings.control.enabled and self.settings.control.native_alarm_enabled:
            client.subscribe(self.topic("partition/+/command"), qos=1)
        if self.settings.control.enabled and self.settings.control.keypad_enabled:
            client.subscribe(self.topic("keypad/+/command"), qos=1)
        if self.settings.debug_raw_tx_enabled:
            client.subscribe(self.topic("debug/tx"), qos=1)
            LOG.warning("Raw transmit enabled on %s", self.topic("debug/tx"))

    def _on_disconnect(
        self,
        client,
        userdata,
        disconnect_flags,
        reason_code,
        properties,
    ) -> None:
        LOG.warning("Disconnected from MQTT broker: %s", reason_code)

    def _on_message(self, client, userdata, message) -> None:
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
        if message.topic == self.topic("debug/tx") and self.settings.debug_raw_tx_enabled:
            self._handle_raw_tx(message.payload)

    def _is_partition_command(self, topic: str) -> bool:
        return topic.startswith(self.topic("partition/")) and topic.endswith("/command")

    def _is_keypad_command(self, topic: str) -> bool:
        return topic.startswith(self.topic("keypad/")) and topic.endswith("/command")

    def _partition_from_topic(self, topic: str, category: str) -> int:
        prefix = self.topic(category) + "/"
        if not topic.startswith(prefix) or not topic.endswith("/command"):
            raise ValueError("invalid command topic")
        value = topic[len(prefix):-len("/command")]
        partition = int(value)
        if partition < 1 or partition > 8:
            raise ValueError("partition must be 1..8")
        return partition

    def _publish_control_rejection(self, kind: str, partition: int | None, reason: str) -> None:
        LOG.warning("Rejected %s control request P%s: %s", kind, partition or "?", reason)
        self.publish_json(
            "control/rejected",
            {"kind": kind, "partition": partition, "reason": reason},
        )

    def _handle_keypad_command(self, topic: str, payload: bytes) -> None:
        partition = None
        try:
            partition = self._partition_from_topic(topic, "keypad")
            key = payload.decode("ascii", errors="strict")
            if len(key) != 1 or key not in "0123456789*#":
                raise ValueError("unsupported_keypad_payload")
            if self.keypad_command_callback is None:
                raise ValueError("keypad control callback unavailable")
            accepted, detail = self.keypad_command_callback(partition, key)
            if not accepted:
                raise ValueError(detail)
        except Exception as exc:
            self._publish_control_rejection("keypad", partition, str(exc))

    def _handle_partition_command(self, topic: str, payload: bytes) -> None:
        partition = None
        action = ""
        try:
            partition = self._partition_from_topic(topic, "partition")
            request = json.loads(payload.decode("utf-8"))
            action = str(request.get("action", "")).upper()
            code = str(request.get("code", ""))
            if self.alarm_command_callback is None:
                raise ValueError("native alarm control callback unavailable")
            accepted, detail = self.alarm_command_callback(partition, action, code)
            if not accepted:
                raise ValueError(detail)
        except Exception as exc:
            # Never include the inbound payload or credential in logs/telemetry.
            self._publish_control_rejection("alarm", partition, str(exc))

    def _handle_raw_tx(self, payload: bytes) -> None:
        try:
            request = json.loads(payload.decode("utf-8"))
            if request.get("confirm") != "I_UNDERSTAND_RAW_PANEL_TX":
                raise ValueError("missing confirmation token")
            data = self._decode_raw_tx(request)
            accepted, detail = self.raw_tx_callback(data)
            if not accepted:
                raise ValueError(detail)
            self.publish_json(
                "debug/tx_result",
                {"ok": True, "bytes": len(data), "status": detail},
            )
        except Exception as exc:
            LOG.warning("Rejected raw TX request: %s", exc)
            self.publish_json("debug/tx_result", {"ok": False, "error": str(exc)})

    @staticmethod
    def _decode_raw_tx(request: dict) -> bytes:
        if "hex" in request:
            data = bytes.fromhex(request["hex"])
        elif "ascii" in request:
            data = request["ascii"].encode("ascii")
        else:
            raise ValueError("payload must contain 'hex' or 'ascii'")
        if not data or len(data) > 512:
            raise ValueError("raw TX length must be 1..512 bytes")
        return data
