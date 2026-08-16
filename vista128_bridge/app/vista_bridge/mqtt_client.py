from __future__ import annotations

import json
import logging
from typing import Callable

import paho.mqtt.client as mqtt

from .config import Settings
from .mqtt_discovery import (
    ZONE_CONDITION_SPECS,
    device_info,
    diagnostic_entities,
    keypad_config,
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
    ) -> None:
        self.settings = settings
        self.mqtt = settings.mqtt
        self.raw_tx_callback = raw_tx_callback
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
            self._publish_discovery_config(
                "sensor",
                object_id,
                {**config, **availability},
            )
        if self.settings.keypad.enabled:
            for partition in self.settings.keypad.partitions:
                self.publish_keypad_discovery(partition)

    def publish_partition_discovery(self, partition: int) -> None:
        self._publish_discovery_config(
            "alarm_control_panel",
            f"partition_{partition}",
            partition_config(partition, self.topic),
        )

    def publish_partition_state(self, partition: PartitionState) -> None:
        prefix = f"partition/{partition.partition}"
        self.publish(f"{prefix}/state", partition.ha_state, retain=True, qos=1)
        self.publish_json(
            f"{prefix}/attributes",
            partition.attributes(),
            retain=True,
            qos=1,
        )

    def publish_keypad_discovery(self, partition: int) -> None:
        self._publish_discovery_config(
            "sensor",
            f"keypad_{partition}",
            keypad_config(partition, self.topic),
        )

    def publish_keypad_state(self, keypad: KeypadState) -> None:
        if not keypad.initialized:
            return
        prefix = f"keypad/{keypad.partition}"
        self.publish(f"{prefix}/state", keypad.ha_state, retain=True, qos=1)
        self.publish_json(
            f"{prefix}/attributes",
            keypad.attributes(),
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
        client.subscribe(self.topic("partition/+/command"), qos=1)
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
        if self._is_partition_command(message.topic):
            self._reject_partition_command(message.topic, message.payload)
            return
        if message.topic == self.topic("debug/tx") and self.settings.debug_raw_tx_enabled:
            self._handle_raw_tx(message.payload)

    def _is_partition_command(self, topic: str) -> bool:
        return topic.startswith(self.topic("partition/")) and topic.endswith("/command")

    def _reject_partition_command(self, topic: str, payload: bytes) -> None:
        text = payload.decode("utf-8", errors="replace")
        LOG.warning("Rejected alarm command on %s: %r", topic, text)
        self.publish_json(
            "control/rejected",
            {"topic": topic, "payload": text, "reason": "control_disabled"},
        )

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
