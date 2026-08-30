from __future__ import annotations

import json
import inspect
import logging
import ssl
from datetime import datetime, timezone
from typing import Callable
import uuid

import paho.mqtt.client as mqtt

from .command_model import VistaCommand, command_from_request
from .config import Settings
from .mqtt_discovery import (
    KEYPAD_ALARM_SPECS,
    PANEL_ALARM_SPECS,
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
        keypad_command_callback: Callable[..., tuple[bool, str]] | None = None,
        alarm_command_callback: Callable[..., tuple[bool, str]] | None = None,
        audit_interaction_callback: Callable[[dict], None] | None = None,
        semantic_command_callback: Callable[..., tuple[bool, str]] | None = None,
    ) -> None:
        self.settings = settings
        self.mqtt = settings.mqtt
        self.raw_tx_callback = raw_tx_callback
        self.keypad_command_callback = keypad_command_callback
        self.alarm_command_callback = alarm_command_callback
        self.audit_interaction_callback = audit_interaction_callback
        self.semantic_command_callback = semantic_command_callback
        self._keypad_callback_with_metadata = self._accepts_metadata(
            keypad_command_callback, 3
        )
        self._alarm_callback_with_metadata = self._accepts_metadata(
            alarm_command_callback, 4
        )
        self._semantic_callback_with_metadata = self._accepts_metadata(
            semantic_command_callback, 2
        )
        self.publish_errors = 0
        self._retained_payloads: dict[str, tuple[str, int]] = {}
        self._client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id="vista128-bridge",
            protocol=mqtt.MQTTv311,
        )
        # Paho otherwise defaults its disconnected QoS outbound queue to
        # unlimited (0). Keep broker outages from turning retained/state
        # publication into unbounded process memory growth. Paho rejects new
        # publishes once either finite limit is reached; this bridge does not
        # add a second retry queue.
        self._client.max_inflight_messages_set(self.mqtt.inflight_messages_max)
        self._client.max_queued_messages_set(self.mqtt.outbound_queue_max)
        if self.mqtt.tls_enabled:
            # Paho raises on unusable certificate configuration and the broker
            # connection cannot fall back to plaintext after this point.
            self._client.tls_set(
                ca_certs=self.mqtt.tls_ca or None,
                certfile=self.mqtt.tls_client_cert or None,
                keyfile=self.mqtt.tls_client_key or None,
                cert_reqs=ssl.CERT_REQUIRED,
            )
            LOG.info("MQTT TLS enabled with certificate verification")
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
    ) -> bool:
        return self._publish_topic(
            self.topic(suffix), payload, qos=qos, retain=retain
        )

    def _publish_topic(
        self,
        topic: str,
        payload: str | int,
        *,
        qos: int = 0,
        retain: bool = False,
    ) -> bool:
        value = str(payload)
        if retain and self._retained_payloads.get(topic) == (value, qos):
            return True
        try:
            result = self._client.publish(
                topic, payload=payload, qos=qos, retain=retain
            )
        except Exception as exc:
            self.publish_errors += 1
            LOG.error("MQTT publish failed for %s: %s", topic, type(exc).__name__)
            return False
        result_code = getattr(result, "rc", None)
        if result_code not in (None, 0):
            self.publish_errors += 1
            LOG.error("MQTT publish rejected for %s (rc=%s)", topic, result_code)
            return False
        if retain:
            self._retained_payloads[topic] = (value, qos)
        return True

    def publish_json(
        self,
        suffix: str,
        payload: dict,
        *,
        retain: bool = False,
        qos: int = 0,
    ) -> bool:
        encoded = json.dumps(payload, separators=(",", ":"))
        return self.publish(suffix, encoded, retain=retain, qos=qos)

    def publish_discovery(self) -> None:
        self._clear_legacy_discovery()
        self._clear_retained_dynamic_state()
        availability = {
            "availability_topic": self.topic("bridge/availability"),
            "payload_available": "online",
            "payload_not_available": "offline",
            "device": device_info(),
        }
        for object_id, (component, config) in diagnostic_entities(
            self.topic, include_raw=self.settings.raw_mqtt_enabled
        ).items():
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
        else:
            self._clear_discovery_config("sensor", "event_journal")
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

    def _clear_retained_dynamic_state(self) -> None:
        """Tombstone dynamic state before a new session can make it current."""
        suffixes = [
            "panel/state_fresh",
            "raw/last_ascii",
            "raw/last_metadata",
        ]
        for partition in range(1, 9):
            suffixes.extend(
                (
                    f"partition/{partition}/state",
                    f"partition/{partition}/attributes",
                    f"keypad/{partition}/state",
                    f"keypad/{partition}/attributes",
                )
            )
            for alarm_type in KEYPAD_ALARM_SPECS:
                suffixes.extend(
                    (
                        f"keypad/{partition}/alarm/{alarm_type}",
                        f"keypad/{partition}/alarm/{alarm_type}/available",
                    )
                )
            suffixes.extend(
                (
                    f"keypad/{partition}/alarm/active",
                    f"keypad/{partition}/alarm/active/available",
                    f"keypad/{partition}/alarm/active/attributes",
                )
            )
        for zone in range(1, 129):
            for condition in ZONE_CONDITION_SPECS:
                suffixes.append(f"zone/{zone:03d}/{condition}")
            suffixes.append(f"zone/{zone:03d}/attributes")
        for condition in ZONE_CONDITION_SPECS:
            suffixes.extend(
                (
                    f"zone_summary/{condition}/count",
                    f"zone_summary/{condition}/attributes",
                )
            )
        for alarm_type in (*PANEL_ALARM_SPECS, "active"):
            suffixes.extend(
                (
                    f"alarm/{alarm_type}",
                    f"alarm/{alarm_type}/available",
                    f"alarm/{alarm_type}/attributes",
                )
            )
        for suffix in suffixes:
            self.publish(suffix, "", retain=True, qos=1)

    def publish_keypad_state(self, keypad: KeypadState) -> None:
        if not keypad.initialized or not keypad.session_fresh:
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
                partition_state = state.partitions.get(partition)
                if keypad is not None and partition_state is not None:
                    self._publish_keypad_alarm_states(keypad, partition_state)
        self._publish_panel_alarm_states(state)

    def _publish_keypad_alarm_states(
        self, keypad: KeypadState, partition: PartitionState
    ) -> None:
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
        if partition.has_active_alarm and "alarm" not in active_types:
            active_types.append("alarm")
        all_known = all(value is not None for value in values.values())
        aggregate_available = bool(active_types) or (keypad.session_fresh and all_known)
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
                "partition_alarm_active": partition.has_active_alarm,
                "sound_mode": keypad.sound_mode,
            },
            retain=True,
            qos=1,
        )

    def _publish_panel_alarm_states(self, state: VistaState) -> None:
        prefix = "alarm"
        alarm_state = state.panel_alarm_states()
        values = alarm_state["values"]
        active_partitions_by_type = alarm_state["active_partitions_by_type"]

        for alarm_type in PANEL_ALARM_SPECS:
            value = values.get(alarm_type)
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
            self.publish_json(
                f"{prefix}/{alarm_type}/attributes",
                {
                    "active_partitions": active_partitions_by_type.get(alarm_type, []),
                    "complete": alarm_state["complete"],
                },
                retain=True,
                qos=1,
            )

        aggregate = alarm_state["active"]
        aggregate_available = aggregate is not None
        self.publish(
            f"{prefix}/active/available",
            "ON" if aggregate_available else "OFF",
            retain=True,
            qos=1,
        )
        if aggregate_available:
            self.publish(
                f"{prefix}/active",
                "ON" if aggregate else "OFF",
                retain=True,
                qos=1,
            )
        self.publish_json(
            f"{prefix}/active/attributes",
            {
                "active_types": [
                    alarm_type for alarm_type, value in values.items() if value is True
                ],
                "active_partitions": alarm_state["active_partitions"],
                "active_partitions_by_type": active_partitions_by_type,
                "complete": alarm_state["complete"],
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
        self._publish_topic(topic, payload, qos=1, retain=True)

    def _clear_discovery_config(self, component: str, object_id: str) -> None:
        topic = (
            f"{self.mqtt.discovery_prefix}/{component}/"
            f"vista128_bridge/{object_id}/config"
        )
        self._publish_topic(topic, "", qos=1, retain=True)

    def _clear_legacy_discovery(self) -> None:
        for object_id in (*PANEL_ALARM_SPECS, "active"):
            self._clear_discovery_config("binary_sensor", f"alarm_{object_id}")
        for partition in range(1, 9):
            self._clear_discovery_config("alarm_control_panel", f"partition_{partition}")
            self._clear_discovery_config("sensor", f"keypad_{partition}")
            for alarm_type in (*KEYPAD_ALARM_SPECS, "active"):
                self._clear_discovery_config(
                    "binary_sensor", f"keypad_{partition}_alarm_{alarm_type}"
                )
        for zone in range(1, 129):
            self._clear_discovery_config("binary_sensor", f"zone_{zone:03d}")
            for condition in ZONE_CONDITION_SPECS:
                self._clear_discovery_config(
                    "binary_sensor", f"zone_{zone:03d}_{condition}"
                )
        for object_id in (
            "faulted_zones",
            "alarm_zones",
            "check_zones",
            "bypassed_zones",
        ):
            self._clear_discovery_config("sensor", object_id)
        for object_id in zone_summary_entities(self.topic):
            self._clear_discovery_config("sensor", object_id)
        for object_id, (component, _) in diagnostic_entities(
            self.topic, include_raw=True
        ).items():
            self._clear_discovery_config(component, object_id)
        self._clear_discovery_config("sensor", "event_journal")

    def _on_connect(self, client, userdata, flags, reason_code, properties) -> None:
        if reason_code != 0:
            LOG.error("MQTT connection rejected: %s", reason_code)
            return
        LOG.info("Connected to MQTT broker")
        self._retained_payloads.clear()
        self.publish("bridge/availability", "online", retain=True, qos=1)
        self.publish_discovery()
        if self.settings.control.enabled and self.settings.control.native_alarm_enabled:
            client.subscribe(self.topic("partition/+/command"), qos=1)
        if self.settings.control.enabled and self.settings.control.keypad_enabled:
            client.subscribe(self.topic("keypad/+/command"), qos=1)
        if self.settings.control.enabled and (
            self.settings.control.keypad_enabled
            or self.settings.control.native_alarm_enabled
        ):
            client.subscribe(self.topic("control/execute"), qos=1)
        if self.settings.debug_raw_tx_enabled:
            client.subscribe(self.topic("admin/raw_tx"), qos=1)
            LOG.warning("Privileged raw transmit enabled on %s", self.topic("admin/raw_tx"))

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
        is_semantic = self._is_semantic_command(message.topic)
        is_raw_admin = message.topic == self.topic("admin/raw_tx")
        if (is_keypad or is_partition or is_semantic) and bool(getattr(message, "retain", False)):
            kind = "keypad" if is_keypad else ("alarm" if is_partition else "command")
            category = "keypad" if is_keypad else "partition"
            try:
                partition = self._partition_from_topic(message.topic, category)
            except Exception:
                partition = None
            self._publish_control_rejection(kind, partition, "retained_control_message")
            return
        if is_raw_admin and bool(getattr(message, "retain", False)):
            self._publish_control_rejection("raw", None, "retained_admin_message")
            return
        if is_keypad:
            self._handle_keypad_command(message.topic, message.payload)
            return
        if is_partition:
            self._handle_partition_command(message.topic, message.payload)
            return
        if is_semantic:
            self._handle_semantic_command(message.payload)
            return
        if is_raw_admin and self.settings.debug_raw_tx_enabled:
            self._handle_raw_tx(message.payload)

    def _is_partition_command(self, topic: str) -> bool:
        return topic.startswith(self.topic("partition/")) and topic.endswith("/command")

    def _is_keypad_command(self, topic: str) -> bool:
        return topic.startswith(self.topic("keypad/")) and topic.endswith("/command")

    def _is_semantic_command(self, topic: str) -> bool:
        return topic == self.topic("control/execute")

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

    @staticmethod
    def _accepts_metadata(callback: Callable | None, argument_count: int) -> bool:
        if callback is None:
            return False
        try:
            inspect.signature(callback).bind(*([None] * argument_count))
        except (TypeError, ValueError):
            return False
        return True

    @staticmethod
    def _transaction_metadata(
        request: dict,
        partition: int,
        default_action: str,
    ) -> dict:
        def bounded_text(value, limit: int) -> str:
            if not isinstance(value, str):
                return ""
            return "".join(character for character in value if character.isprintable())[:limit]

        interaction_id = bounded_text(
            request.get("transaction_id", request.get("interaction_id", "")),
            96,
        ) or uuid.uuid4().hex
        audit_interaction_id = bounded_text(request.get("audit_interaction_id", ""), 96)
        interaction_complete = request.get(
            "complete", request.get("sequence_complete", True)
        )
        if not isinstance(interaction_complete, bool):
            raise ValueError("interaction completion flag must be boolean")
        source = bounded_text(request.get("source", ""), 32)
        if source != "ha_frontend":
            source = "mqtt"
        return {
            "interaction_id": interaction_id,
            "audit_interaction_id": audit_interaction_id,
            "request_id": uuid.uuid4().hex,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "actor_id": bounded_text(request.get("actor_id", ""), 128),
            "actor_name": bounded_text(request.get("actor_name", ""), 128),
            "partition": partition,
            "source": source,
            "action": default_action,
            "interaction_complete": interaction_complete,
        }

    def _invoke_keypad_callback(
        self, partition: int, key: str, metadata: dict
    ) -> tuple[bool, str]:
        if self.keypad_command_callback is None:
            return False, "keypad control callback unavailable"
        if self._keypad_callback_with_metadata:
            return self.keypad_command_callback(partition, key, metadata)
        return self.keypad_command_callback(partition, key)

    def _invoke_alarm_callback(
        self, partition: int, action: str, code: str, metadata: dict
    ) -> tuple[bool, str]:
        if self.alarm_command_callback is None:
            return False, "native alarm control callback unavailable"
        if self._alarm_callback_with_metadata:
            return self.alarm_command_callback(partition, action, code, metadata)
        return self.alarm_command_callback(partition, action, code)

    def _invoke_semantic_callback(
        self, command: VistaCommand, metadata: dict
    ) -> tuple[bool, str]:
        if self.semantic_command_callback is None:
            return False, "semantic command callback unavailable"
        if self._semantic_callback_with_metadata:
            return self.semantic_command_callback(command, metadata)
        return self.semantic_command_callback(command)

    def _audit_interaction(self, metadata: dict, status: str, ok: bool) -> None:
        if self.audit_interaction_callback is None:
            return
        try:
            audit_metadata = dict(metadata)
            audit_interaction_id = str(audit_metadata.get("audit_interaction_id", "")).strip()
            if audit_interaction_id:
                audit_metadata["interaction_id"] = audit_interaction_id
            self.audit_interaction_callback(
                {
                    **audit_metadata,
                    "status": status,
                    "ok": ok,
                }
            )
        except Exception as exc:
            # Audit failure must not turn a bounded control rejection into a
            # retry loop, and no command payload is included in this log.
            LOG.error("Keypad interaction audit failed: %s", type(exc).__name__)

    def _audit_rejected_interaction(self, metadata: dict) -> None:
        self._audit_interaction(metadata, "rejected", False)

    def _handle_keypad_command(self, topic: str, payload: bytes) -> None:
        partition = None
        try:
            if len(payload) > 4096:
                raise ValueError("keypad payload is too large")
            partition = self._partition_from_topic(topic, "keypad")
            # Keep the former one-byte MQTT interface working for existing
            # automations. New callers should use one JSON logical sequence so
            # actor and interaction metadata can travel with it.
            if len(payload) == 1:
                legacy_key = payload.decode("ascii", errors="strict")
                request = {"keys": legacy_key}
            else:
                request = json.loads(payload.decode("utf-8"))
            if not isinstance(request, dict):
                raise ValueError("keypad_payload_must_be_object")
            key = request.get("keys", request.get("key", ""))
            if not isinstance(key, str) or not 1 <= len(key) <= 5:
                raise ValueError("keypad_sequence_length_must_be_1_to_5")
            if any(character not in "0123456789*#" for character in key):
                raise ValueError("unsupported_keypad_payload")
            if self.keypad_command_callback is None:
                raise ValueError("keypad control callback unavailable")
            metadata = self._transaction_metadata(
                request, partition, "keypad_sequence"
            )
            # The bridge records this exact completed logical sequence. It is
            # deliberately a single bounded field, not an MQTT envelope or a
            # stream of individual keypresses.
            metadata["command_sequence"] = key
            accepted, detail = self._invoke_keypad_callback(partition, key, metadata)
            if not accepted:
                self._audit_rejected_interaction(metadata)
                raise ValueError(detail)
            self._audit_interaction(metadata, "queued", False)
        except Exception as exc:
            self._publish_control_rejection("keypad", partition, str(exc))

    def _handle_partition_command(self, topic: str, payload: bytes) -> None:
        partition = None
        action = ""
        try:
            partition = self._partition_from_topic(topic, "partition")
            request = json.loads(payload.decode("utf-8"))
            if not isinstance(request, dict):
                raise ValueError("partition_payload_must_be_object")
            action = str(request.get("action", "")).upper()
            code = str(request.get("code", ""))
            metadata = self._transaction_metadata(request, partition, action.lower())
            metadata["command_sequence"] = code
            metadata["operands"] = {"native_action": action}
            accepted, detail = self._invoke_alarm_callback(
                partition, action, code, metadata
            )
            if not accepted:
                if len(code) == 4 and code.isdigit():
                    self._audit_rejected_interaction(metadata)
                raise ValueError(detail)
            self._audit_interaction(metadata, "queued", False)
        except Exception as exc:
            # Never include the inbound payload or credential in logs/telemetry.
            self._publish_control_rejection("alarm", partition, str(exc))

    def _handle_semantic_command(self, payload: bytes) -> None:
        partition = None
        try:
            if len(payload) > 8192:
                raise ValueError("command payload is too large")
            request = json.loads(payload.decode("utf-8"))
            if not isinstance(request, dict):
                raise ValueError("command_payload_must_be_object")
            partition_value = request.get("partition")
            partition = int(partition_value) if not isinstance(partition_value, bool) else None
            command = command_from_request(
                request,
                source=(
                    request.get("source", "")
                    if request.get("source") == "ha_frontend"
                    else "mqtt"
                ),
                actor_id=request.get("actor_id", ""),
                actor_name=request.get("actor_name", ""),
                interaction_id=request.get(
                    "transaction_id", request.get("interaction_id", "")
                ),
            )
            metadata = self._transaction_metadata(
                request, command.partition or 0, command.command_type
            )
            metadata.update(
                {
                    "command_sequence": command.raw_sequence,
                    "operands": command.operands,
                    "command_type": command.command_type,
                    "code": command.code,
                    "confidence": command.confidence,
                }
            )
            accepted, detail = self._invoke_semantic_callback(command, metadata)
            if not accepted:
                self._audit_interaction(
                    metadata, "rejected", False
                )
                raise ValueError(detail)
            self._audit_interaction(metadata, "queued", False)
        except Exception as exc:
            self._publish_control_rejection("command", partition, str(exc))

    def _handle_raw_tx(self, payload: bytes) -> None:
        try:
            if len(payload) > 2048:
                raise ValueError("raw TX request is too large")
            request = json.loads(payload.decode("utf-8"))
            if not isinstance(request, dict):
                raise ValueError("raw TX request must be an object")
            data = self._decode_raw_tx(request)
            accepted, detail = self.raw_tx_callback(data)
            if not accepted:
                raise ValueError(detail)
            self.publish_json(
                "admin/raw_tx_result",
                {"ok": True, "bytes": len(data), "status": detail},
            )
        except Exception as exc:
            LOG.warning("Rejected raw TX request: %s", type(exc).__name__)
            self.publish_json("admin/raw_tx_result", {"ok": False, "error": str(exc)})

    @staticmethod
    def _decode_raw_tx(request: dict) -> bytes:
        has_hex = "hex" in request
        has_ascii = "ascii" in request
        if has_hex == has_ascii:
            raise ValueError("payload must contain exactly one of 'hex' or 'ascii'")
        if has_hex:
            value = request["hex"]
            if not isinstance(value, str) or len(value) % 2:
                raise ValueError("hex payload must be an even-length string")
            try:
                data = bytes.fromhex(value)
            except ValueError as exc:
                raise ValueError("hex payload is malformed") from exc
        elif "ascii" in request:
            value = request["ascii"]
            if not isinstance(value, str):
                raise ValueError("ascii payload must be a string")
            try:
                data = value.encode("ascii")
            except UnicodeEncodeError as exc:
                raise ValueError("ascii payload is not 7-bit ASCII") from exc
        else:
            raise ValueError("payload must contain 'hex' or 'ascii'")
        if not data or len(data) > 512:
            raise ValueError("raw TX length must be 1..512 bytes")
        return data
