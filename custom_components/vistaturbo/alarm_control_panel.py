from __future__ import annotations

from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntity,
    AlarmControlPanelEntityFeature,
    AlarmControlPanelState,
    CodeFormat,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .api import (
    VistaTurboAuthError,
    VistaTurboCannotConnect,
    VistaTurboCommandError,
    VistaTurboProtocolError,
)
from .entity import VistaTurboEntity
from .hub import VistaTurboHub

SUPPORTED_FEATURES = (
    AlarmControlPanelEntityFeature.ARM_AWAY
    | AlarmControlPanelEntityFeature.ARM_HOME
    | AlarmControlPanelEntityFeature.ARM_NIGHT
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry[VistaTurboHub],
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    hub = entry.runtime_data
    if not hub.snapshot.get("control", {}).get("native_alarm"):
        return
    async_add_entities(
        VistaPartitionAlarm(hub, int(item["partition"]))
        for item in hub.snapshot.get("partitions", [])
    )


class VistaPartitionAlarm(VistaTurboEntity, AlarmControlPanelEntity):
    _attr_code_format = CodeFormat.NUMBER
    _attr_code_arm_required = True
    _attr_supported_features = SUPPORTED_FEATURES

    def __init__(self, hub: VistaTurboHub, partition: int) -> None:
        super().__init__(hub)
        self.partition = partition
        self._attr_unique_id = f"{hub.identity}-partition-{partition}"
        self._attr_name = f"Partition {partition}"

    def _data(self) -> dict | None:
        return next(
            (
                item
                for item in self.hub.snapshot.get("partitions", [])
                if int(item["partition"]) == self.partition
            ),
            None,
        )

    @property
    def alarm_state(self) -> AlarmControlPanelState | None:
        data = self._data()
        if data is None:
            return None
        try:
            return AlarmControlPanelState(str(data["state"]))
        except (KeyError, ValueError):
            return None

    @property
    def extra_state_attributes(self) -> dict:
        data = self._data() or {}
        return {
            **{key: value for key, value in data.items() if key != "state"},
            "native_control_available": bool(
                self.hub.snapshot.get("control", {}).get("automation_available")
            ),
        }

    @property
    def available(self) -> bool:
        panel = self.hub.snapshot.get("panel", {})
        return bool(
            super().available
            and panel.get("connected")
            and panel.get("state_fresh")
            and self._data() is not None
        )

    async def _async_alarm_command(self, action: str, code: str | None) -> None:
        if not isinstance(code, str) or len(code) != 4 or not code.isdigit():
            raise HomeAssistantError("Vista Turbo requires an exactly four-digit user code")

        context = getattr(self, "_context", None)
        user_id = str(context.user_id or "") if context is not None else ""
        context_id = str(context.id) if context is not None else ""

        try:
            await self.hub.client.async_alarm_command(
                partition=self.partition,
                action=action,
                code=code,
                user_id=user_id,
                user_name="",
                context_id=context_id,
            )
        except VistaTurboCommandError as err:
            raise HomeAssistantError(
                f"Vista Turbo rejected the alarm command: {err.status}"
            ) from err
        except VistaTurboAuthError as err:
            raise HomeAssistantError(
                "Vista Turbo rejected the Supervisor-provisioned machine credential"
            ) from err
        except VistaTurboCannotConnect as err:
            raise HomeAssistantError("Vista Turbo app is unavailable") from err
        except VistaTurboProtocolError as err:
            raise HomeAssistantError("Vista Turbo returned an invalid control response") from err

    async def async_alarm_disarm(self, code: str | None = None) -> None:
        await self._async_alarm_command("disarm", code)

    async def async_alarm_arm_away(self, code: str | None = None) -> None:
        await self._async_alarm_command("arm_away", code)

    async def async_alarm_arm_home(self, code: str | None = None) -> None:
        await self._async_alarm_command("arm_home", code)

    async def async_alarm_arm_night(self, code: str | None = None) -> None:
        await self._async_alarm_command("arm_night", code)
