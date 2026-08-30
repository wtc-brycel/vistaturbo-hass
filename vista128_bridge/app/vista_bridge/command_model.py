"""Canonical VISTA command model, keypad parser, and execution planner.

The panel has two useful write interfaces: native automation commands and
keypad emulation.  This module keeps their semantic representation together so
that parsing, execution, and auditing cannot quietly drift apart.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
import re
from typing import Any, Mapping


MAX_LOGICAL_KEYPAD_SEQUENCE = 256
MAX_OPERAND_ZONES = 64
KEYPAD_SEQUENCE_RE = re.compile(r"[0-9*#ABCD]+\Z")
PIN_RE = re.compile(r"[0-9]{4}\Z")

# A raw sequence is an executable capability, not an alternate spelling for
# every semantic command.  Keep this allow-list narrow so a caller cannot
# label one operation while transmitting another operation's keypad input.
RAW_SEQUENCE_COMMAND_TYPES = frozenset(
    {
        "keypad_command",
        "interactive_menu",
        "programming_session",
        "access_control",
        "program_enter",
        "program_menu_enter",
        "program_exit",
        "program_exit_local",
        "program_field_change",
        "program_reset",
        "program_download",
        # These are prompt-driven semantic operations.  They are allowed to
        # carry a sequence only after their semantic prefix and terminal menu
        # exit have been checked below.
        "output_control",
        "instant_activation",
    }
)


class CommandValidationError(ValueError):
    """Raised when a semantic or keypad command is not safe to execute."""


def validate_pin(value: Any) -> str:
    """Validate the fixed four-digit VISTA user/security PIN invariant."""
    if not isinstance(value, str) or PIN_RE.fullmatch(value) is None:
        raise CommandValidationError("VISTA PIN must contain exactly four digits")
    return value


def normalize_zone(value: Any) -> str:
    """Return a VISTA zone operand in its exact three-digit keypad form."""
    if isinstance(value, bool):
        raise CommandValidationError("VISTA zone must be a positive number")
    if isinstance(value, int):
        if not 1 <= value <= 999:
            raise CommandValidationError("VISTA zone must be 001..999")
        return f"{value:03d}"
    if isinstance(value, str) and re.fullmatch(r"[0-9]{3}", value):
        if int(value) == 0:
            raise CommandValidationError("VISTA zone must be 001..999")
        return value
    raise CommandValidationError("VISTA zone must be exactly three digits")


def normalize_zones(values: Any) -> tuple[str, ...]:
    if not isinstance(values, (list, tuple)) or not values:
        raise CommandValidationError("VISTA command requires one or more zones")
    if len(values) > MAX_OPERAND_ZONES:
        raise CommandValidationError("too many VISTA zones")
    normalized = tuple(normalize_zone(value) for value in values)
    if len(set(normalized)) != len(normalized):
        raise CommandValidationError("VISTA zone list contains duplicates")
    return normalized


def normalize_partitions(values: Any) -> tuple[int, ...]:
    if not isinstance(values, (list, tuple)) or not values:
        raise CommandValidationError("global arming requires one or more partitions")
    if len(values) > 8:
        raise CommandValidationError("too many global arming partitions")
    normalized = []
    for value in values:
        if isinstance(value, bool):
            raise CommandValidationError("VISTA partition must be 1..8")
        try:
            partition = int(value)
        except (TypeError, ValueError) as exc:
            raise CommandValidationError("VISTA partition must be 1..8") from exc
        if not 1 <= partition <= 8:
            raise CommandValidationError("VISTA partition must be 1..8")
        normalized.append(partition)
    if len(set(normalized)) != len(normalized):
        raise CommandValidationError("global arming partitions contain duplicates")
    return tuple(sorted(normalized))


def validate_keypad_sequence(value: Any) -> str:
    if not isinstance(value, str) or not 1 <= len(value) <= MAX_LOGICAL_KEYPAD_SEQUENCE:
        raise CommandValidationError(
            f"keypad sequence length must be 1..{MAX_LOGICAL_KEYPAD_SEQUENCE}"
        )
    if KEYPAD_SEQUENCE_RE.fullmatch(value) is None:
        raise CommandValidationError("keypad sequence contains an unsupported token")
    return value


def _bounded_text(value: Any, limit: int) -> str:
    if not isinstance(value, str):
        return ""
    return "".join(character for character in value if character.isprintable())[:limit]


@dataclass(frozen=True, repr=False)
class VistaCommand:
    """One logical VISTA operation, whether parsed or requested semantically."""

    command_type: str
    partition: int | None = None
    code: str = field(default="", repr=False)
    operands: dict[str, Any] = field(default_factory=dict)
    raw_sequence: str = field(default="", repr=False)
    source: str = "mqtt"
    actor_id: str = ""
    actor_name: str = ""
    interaction_id: str = field(default="", repr=False)
    confidence: str = "high"
    execution_mechanism: str = "unplanned"
    status: str = "requested"
    verification: str = ""

    def __post_init__(self) -> None:
        command_type = _bounded_text(self.command_type, 64)
        if not command_type:
            raise CommandValidationError("VISTA command type is required")
        object.__setattr__(self, "command_type", command_type)
        if self.partition is not None:
            try:
                normalized_partition = int(self.partition)
            except (TypeError, ValueError) as exc:
                raise CommandValidationError("VISTA partition must be 1..8") from exc
            if isinstance(self.partition, bool) or not 1 <= normalized_partition <= 8:
                raise CommandValidationError("VISTA partition must be 1..8")
            object.__setattr__(self, "partition", normalized_partition)
        if self.code:
            object.__setattr__(self, "code", validate_pin(self.code))
        if self.raw_sequence:
            object.__setattr__(self, "raw_sequence", validate_keypad_sequence(self.raw_sequence))
        if not isinstance(self.operands, dict):
            raise CommandValidationError("VISTA command operands must be an object")
        operands = dict(self.operands)
        if "zones" in operands:
            operands["zones"] = list(normalize_zones(operands["zones"]))
        if "group" in operands:
            group = operands["group"]
            try:
                group_number = int(group)
            except (TypeError, ValueError) as exc:
                raise CommandValidationError("VISTA bypass group must be 01..15") from exc
            if not 1 <= group_number <= 15:
                raise CommandValidationError("VISTA bypass group must be 01..15")
            operands["group"] = f"{group_number:02d}"
        object.__setattr__(self, "operands", operands)
        object.__setattr__(self, "source", _bounded_text(self.source, 32) or "mqtt")
        object.__setattr__(self, "actor_id", _bounded_text(self.actor_id, 128))
        object.__setattr__(self, "actor_name", _bounded_text(self.actor_name, 128))
        object.__setattr__(self, "interaction_id", _bounded_text(self.interaction_id, 96))
        object.__setattr__(self, "confidence", _bounded_text(self.confidence, 16) or "unknown")
        object.__setattr__(self, "execution_mechanism", _bounded_text(self.execution_mechanism, 16) or "unplanned")
        object.__setattr__(self, "status", _bounded_text(self.status, 32) or "requested")
        object.__setattr__(self, "verification", _bounded_text(self.verification, 64))

    def __repr__(self) -> str:
        """Avoid leaking PINs or exact keypad input through accidental logging."""
        return (
            "VistaCommand("
            f"command_type={self.command_type!r}, partition={self.partition!r}, "
            f"operands={self.operands!r}, source={self.source!r}, "
            f"confidence={self.confidence!r}, execution_mechanism={self.execution_mechanism!r}, "
            f"status={self.status!r})"
        )

    def with_execution(
        self,
        *,
        execution_mechanism: str,
        status: str,
        verification: str = "",
    ) -> "VistaCommand":
        return replace(
            self,
            execution_mechanism=execution_mechanism,
            status=status,
            verification=verification,
        )

    def to_dict(self, *, include_sensitive: bool = False) -> dict[str, Any]:
        """Serialize for control telemetry, omitting sensitive input by default."""
        payload: dict[str, Any] = {
            "command_type": self.command_type,
            "partition": self.partition,
            "operands": dict(self.operands),
            "source": self.source,
            "actor_id": self.actor_id,
            "actor_name": self.actor_name,
            "interaction_id": self.interaction_id,
            "confidence": self.confidence,
            "execution_mechanism": self.execution_mechanism,
            "status": self.status,
            "verification": self.verification,
        }
        if include_sensitive:
            payload["code"] = self.code
            payload["raw_sequence"] = self.raw_sequence
        return payload

    def audit_fields(self) -> dict[str, Any]:
        return {
            "command_type": self.command_type,
            "code": self.code,
            "command_sequence": self.raw_sequence,
            "operands": dict(self.operands),
            "confidence": self.confidence,
            "execution_mechanism": self.execution_mechanism,
            "verification": self.verification,
            "action": self.command_type,
        }


@dataclass(frozen=True)
class KeypadParseContext:
    program_mode: bool = False
    global_arming: bool = False
    panic_mode: bool = False
    model: str = "VISTA-128BPT"
    function_keys: Mapping[str, str] = field(default_factory=dict)
    extensions: Mapping[str, str] = field(default_factory=dict)
    prompt: str = ""


class ParserState:
    IDLE = "idle"
    CODE_PREFIX = "code_prefix"
    NORMAL_COMMAND = "normal_command"
    BYPASS_ZONES = "bypass_zones"
    HASH_COMMAND = "hash_command"
    OUTPUT_MENU = "output_menu"
    INSTANT_ACTIVATION = "instant_activation"
    USER_MANAGEMENT = "user_management"
    GLOBAL_PARTITIONS = "global_partitions"
    PROGRAMMING = "programming"
    MACRO = "macro"
    UNCLASSIFIED = "unclassified"


@dataclass
class KeypadParser:
    """Deterministic parser for a completed logical keypad sequence."""

    sequence: str = ""
    state: str = ParserState.IDLE

    def reset(self) -> None:
        self.sequence = ""
        self.state = ParserState.IDLE

    def feed(self, keys: str) -> str:
        if not isinstance(keys, str) or not keys:
            raise CommandValidationError("keypad input is required")
        validate_keypad_sequence(keys)
        if len(self.sequence) + len(keys) > MAX_LOGICAL_KEYPAD_SEQUENCE:
            raise CommandValidationError("keypad sequence is too long")
        self.sequence += keys
        self.state = self._state_for(self.sequence)
        return self.state

    def complete(
        self,
        *,
        partition: int | None = None,
        source: str = "ha_frontend",
        actor_id: str = "",
        actor_name: str = "",
        interaction_id: str = "",
        context: KeypadParseContext | Mapping[str, Any] | None = None,
    ) -> VistaCommand:
        return self.parse(
            self.sequence,
            partition=partition,
            source=source,
            actor_id=actor_id,
            actor_name=actor_name,
            interaction_id=interaction_id,
            context=context,
        )

    def parse(
        self,
        sequence: str,
        *,
        partition: int | None = None,
        source: str = "ha_frontend",
        actor_id: str = "",
        actor_name: str = "",
        interaction_id: str = "",
        context: KeypadParseContext | Mapping[str, Any] | None = None,
    ) -> VistaCommand:
        sequence = validate_keypad_sequence(sequence)
        context = self._context(context)
        self.sequence = sequence
        self.state = self._state_for(sequence, context)
        common = {
            "partition": partition,
            "raw_sequence": sequence,
            "source": source,
            "actor_id": actor_id,
            "actor_name": actor_name,
            "interaction_id": interaction_id,
        }

        if context.program_mode:
            return self._parse_programming(sequence, common)
        if sequence in {"*97", "*94", "*99", "*98"}:
            types = {
                "*97": "program_reset",
                "*94": "program_download",
                "*99": "program_exit",
                "*98": "program_exit_local",
            }
            return VistaCommand(command_type=types[sequence], confidence="high", **common)
        if sequence == "#93":
            return VistaCommand(
                command_type="program_menu_enter",
                confidence="medium",
                operands={"menu": "#93"},
                **common,
            )
        if sequence[:1] in {"A", "B", "C", "D"}:
            return self._parse_function_key(sequence, context, common)
        if sequence.startswith("#"):
            return self._parse_quick(sequence, context, common)
        if sequence.startswith("*"):
            if sequence in {"*1", "*#"} or (sequence == "#3" and context.panic_mode):
                return VistaCommand(
                    command_type="panic",
                    operands={"function": sequence},
                    confidence="medium",
                    **common,
                )
            if sequence == "*":
                return VistaCommand(command_type="display_function", confidence="high", **common)
            return VistaCommand(
                command_type="unclassified_keypad_command",
                confidence="low",
                operands={"reason": "unsupported_star_sequence"},
                **common,
            )
        if len(sequence) < 4 or not sequence[:4].isdigit():
            return VistaCommand(
                command_type="unclassified_keypad_command",
                confidence="low",
                operands={"parser_state": self.state},
                **common,
            )
        code = sequence[:4]
        tail = sequence[4:]
        common["code"] = code
        if not tail:
            return VistaCommand(
                command_type="code_entry_ambiguous",
                confidence="low",
                operands={"requires_panel_context": True},
                **common,
            )
        return self._parse_code_command(code, tail, context, common)

    @staticmethod
    def _context(context: KeypadParseContext | Mapping[str, Any] | None) -> KeypadParseContext:
        if context is None:
            return KeypadParseContext()
        if isinstance(context, KeypadParseContext):
            return context
        if not isinstance(context, Mapping):
            raise CommandValidationError("invalid keypad parser context")
        return KeypadParseContext(
            program_mode=bool(context.get("program_mode", False)),
            global_arming=bool(context.get("global_arming", False)),
            panic_mode=bool(context.get("panic_mode", False)),
            model=_bounded_text(context.get("model", "VISTA-128BPT"), 64) or "VISTA-128BPT",
            function_keys=context.get("function_keys", {}) if isinstance(context.get("function_keys", {}), Mapping) else {},
            extensions=context.get("extensions", {}) if isinstance(context.get("extensions", {}), Mapping) else {},
            prompt=_bounded_text(context.get("prompt", ""), 64),
        )

    @staticmethod
    def _state_for(sequence: str, context: KeypadParseContext | None = None) -> str:
        if context is not None and context.program_mode:
            return ParserState.PROGRAMMING
        if not sequence:
            return ParserState.IDLE
        if sequence[:1] in {"A", "B", "C", "D"}:
            return ParserState.MACRO
        if sequence.startswith("#"):
            return ParserState.HASH_COMMAND
        if len(sequence) < 4:
            return ParserState.CODE_PREFIX
        if sequence[4:5] == "6":
            return ParserState.BYPASS_ZONES
        if sequence[4:5] == "8":
            return ParserState.USER_MANAGEMENT
        if sequence[4:5] == "#":
            return ParserState.HASH_COMMAND
        return ParserState.NORMAL_COMMAND

    def _parse_quick(self, sequence: str, context: KeypadParseContext, common: dict[str, Any]) -> VistaCommand:
        if sequence == "#3" and context.panic_mode:
            return VistaCommand(command_type="panic", operands={"function": sequence}, confidence="medium", **common)
        quick = {
            "#2": ("arm_away", {}),
            "#3": ("arm_home", {}),
            "#4": ("arm_maximum", {}),
            "#7": ("arm_instant", {}),
            "#9": ("quick_exit", {}),
        }
        if sequence in quick:
            command_type, operands = quick[sequence]
            return VistaCommand(command_type=command_type, confidence="high", operands=operands, **common)
        if len(sequence) == 3 and sequence[:2] in {"#3", "#7"} and sequence[2] in "123":
            command_type = "arm_home" if sequence[:2] == "#3" else "arm_instant"
            return VistaCommand(
                command_type=command_type,
                confidence="high",
                operands={"subtype": sequence[2]},
                **common,
            )
        return VistaCommand(
            command_type="unclassified_keypad_command",
            confidence="low",
            operands={"parser_state": ParserState.HASH_COMMAND},
            **common,
        )

    def _parse_function_key(self, sequence: str, context: KeypadParseContext, common: dict[str, Any]) -> VistaCommand:
        key = sequence[0]
        mapped = context.function_keys.get(key) or context.function_keys.get(key.lower())
        if mapped:
            return VistaCommand(
                command_type="configured_function_key",
                confidence="medium",
                operands={"key": key, "configured_action": _bounded_text(mapped, 64)},
                **common,
            )
        command_type = "macro_or_function_key" if key == "D" else "function_key_unknown"
        return VistaCommand(
            command_type=command_type,
            confidence="low",
            operands={"key": key, "configuration_required": True},
            **common,
        )

    def _parse_code_command(self, code: str, tail: str, context: KeypadParseContext, common: dict[str, Any]) -> VistaCommand:
        if context.global_arming and len(tail) >= 3 and tail[-1] == "*":
            action = {"1": "disarm", "2": "arm_away", "3": "arm_home", "4": "arm_maximum", "7": "arm_instant"}.get(tail[0])
            selection = tail[1:-1]
            if action and selection and all(character.isdigit() for character in selection):
                partitions = [int(character) for character in selection]
                if 0 in partitions:
                    partitions = list(range(1, 9))
                if all(1 <= value <= 8 for value in partitions):
                    return VistaCommand(
                        command_type=action,
                        confidence="medium",
                        operands={"partitions": sorted(set(partitions)), "global_arming": True},
                        **common,
                    )

        simple = {
            "1": ("disarm", {}),
            "2": ("arm_away", {}),
            "4": ("arm_maximum", {}),
            "5": ("walk_test", {}),
            "9": ("chime", {}),
            "0": ("access_relay", {}),
            "**": ("user_capabilities", {}),
        }
        if tail in simple:
            command_type, operands = simple[tail]
            return VistaCommand(command_type=command_type, confidence="high", operands=operands, **common)
        if tail == "8000":
            return VistaCommand(command_type="program_enter", confidence="medium", operands={"installer_code_entry": True}, **common)
        if tail == "#93":
            return VistaCommand(command_type="program_menu_enter", confidence="high", operands={"menu": "#93"}, **common)
        if tail.startswith("3"):
            if len(tail) == 1:
                return VistaCommand(command_type="arm_home", confidence="high", operands={}, **common)
            if len(tail) == 2 and tail[1] in "123":
                return VistaCommand(command_type="arm_home", confidence="high", operands={"subtype": tail[1]}, **common)
        if tail.startswith("7"):
            if len(tail) == 1:
                return VistaCommand(command_type="arm_instant", confidence="high", operands={}, **common)
            if len(tail) == 2 and tail[1] in "123":
                return VistaCommand(command_type="arm_instant", confidence="high", operands={"subtype": tail[1]}, **common)
        if tail.startswith("6"):
            return self._parse_bypass(code, tail[1:], common)
        if tail.startswith("8"):
            user = tail[1:4] if len(tail) >= 4 and tail[1:4].isdigit() else ""
            return VistaCommand(
                command_type="user_management",
                confidence="medium" if user else "low",
                operands={"user": user, "interactive": True} if user else {"interactive": True},
                **common,
            )
        if tail.startswith("*") and len(tail) == 2 and tail[1] in "12345678":
            return VistaCommand(command_type="goto_partition", confidence="high", operands={"target_partition": int(tail[1])}, **common)
        if tail.startswith("#"):
            return self._parse_system_namespace(tail[1:], context, common)
        return VistaCommand(
            command_type="unclassified_keypad_command",
            confidence="low",
            operands={"parser_state": self.state},
            **common,
        )

    def _parse_bypass(self, code: str, tail: str, common: dict[str, Any]) -> VistaCommand:
        if tail == "#":
            return VistaCommand(command_type="quick_bypass", confidence="high", operands={}, **common)
        if tail.startswith("*") and len(tail) == 3 and tail[1:].isdigit() and 1 <= int(tail[1:]) <= 15:
            return VistaCommand(command_type="group_bypass", confidence="high", operands={"group": f"{int(tail[1:]):02d}"}, **common)
        if tail.endswith("**"):
            zone_text = tail[:-2]
            if zone_text and len(zone_text) % 3 == 0 and zone_text.isdigit():
                zones = tuple(zone_text[index:index + 3] for index in range(0, len(zone_text), 3))
                try:
                    zones = normalize_zones(zones)
                except CommandValidationError:
                    zones = ()
                if zones:
                    return VistaCommand(command_type="zone_bypass", confidence="high", operands={"zones": list(zones)}, **common)
        if not tail:
            return VistaCommand(command_type="bypass_display", confidence="medium", operands={"interactive": True}, **common)
        return VistaCommand(command_type="unclassified_keypad_command", confidence="low", operands={"parser_state": ParserState.BYPASS_ZONES}, **common)

    def _parse_system_namespace(self, value: str, context: KeypadParseContext, common: dict[str, Any]) -> VistaCommand:
        if not value or not value[0].isdigit():
            return VistaCommand(command_type="unclassified_keypad_command", confidence="low", operands={"namespace": "#"}, **common)
        single_digit = {
            "1": "site_download",
            "2": "house_id_sniffer",
            "3": "transmitter_id_test",
            "5": "direct_wire_download",
        }
        if value[0] in single_digit and (len(value) == 1 or value[1] not in "0123456789"):
            return VistaCommand(
                command_type=single_digit[value[0]],
                confidence="medium",
                operands={"system_command": f"#{value[0]}", "suffix": value[1:]},
                **common,
            )
        if len(value) < 2 or not value[:2].isdigit():
            return VistaCommand(command_type="unclassified_keypad_command", confidence="low", operands={"namespace": "#"}, **common)
        command_number = value[:2]
        supported = {
            "01": "site_download",
            "02": "house_id_sniffer",
            "03": "transmitter_id_test",
            "05": "direct_wire_download",
            "41": "randomize_outputs",
            "42": "randomize_outputs_window",
            "60": "event_log_display",
            "61": "event_log_print",
            "62": "event_log_clear",
            "63": "clock_set",
            "64": "persistent_bypass_reset",
            "65": "programming_lockout_window",
            "67": "auxiliary_relay_reset",
            "68": "fire_walk_test",
            "69": "fire_drill",
            "70": "output_control",
            "71": "programmed_output_action",
            "72": "programmed_output_action",
            "73": "access_enter_exit_request",
            "74": "access_point_request",
            "75": "access_point_state",
            "77": "instant_activation",
            "78": "vistakey_test",
            "79": "access_card_function",
            "80": "scheduling",
            "81": "temporary_schedule",
            "82": "extend_closing_window",
            "83": "output_timer_programming",
        }
        suffix = value[2:]
        if command_number == "70" and len(suffix) >= 3 and suffix[:2].isdigit() and suffix[2] in "01":
            return VistaCommand(
                command_type="output_control",
                confidence="medium",
                operands={"device": suffix[:2], "state": "on" if suffix[2] == "1" else "off", "interactive": True},
                **common,
            )
        if command_number == "77" and len(suffix) >= 2 and suffix[:2].isdigit():
            actions = {
                "01": "relay_on", "02": "relay_off", "03": "relay_close_2_seconds",
                "04": "relay_close_minutes", "05": "relay_close_seconds", "06": "relay_group_on",
                "07": "relay_group_off", "08": "relay_group_close_2_seconds", "09": "relay_group_close_minutes",
                "10": "relay_group_close_seconds", "20": "arm_stay", "21": "arm_away", "22": "disarm",
                "23": "force_arm_stay", "24": "force_arm_away", "25": "arm_instant", "26": "arm_maximum",
                "30": "automatic_bypass", "31": "automatic_unbypass", "40": "opening_window",
                "41": "closing_window", "42": "access_window",
            }
            action_code = suffix[:2]
            zone_text = suffix[2:-2] if suffix.endswith("**") else ""
            if action_code in {"30", "31"} and zone_text:
                if len(zone_text) % 3 == 0 and zone_text.isdigit():
                    zones = tuple(
                        zone_text[index:index + 3]
                        for index in range(0, len(zone_text), 3)
                    )
                    try:
                        normalized_zones = normalize_zones(zones)
                    except CommandValidationError:
                        normalized_zones = ()
                    if normalized_zones:
                        return VistaCommand(
                            command_type=(
                                "automatic_bypass"
                                if action_code == "30"
                                else "automatic_unbypass"
                            ),
                            confidence="high",
                            operands={
                                "action_code": action_code,
                                "zones": list(normalized_zones),
                            },
                            **common,
                        )
            return VistaCommand(
                command_type="instant_activation",
                confidence="medium" if action_code in actions else "low",
                operands={"action_code": action_code, "action": actions.get(action_code), "interactive": True},
                **common,
            )
        extension = context.extensions.get(f"#{command_number}") or context.extensions.get(command_number)
        command_type = extension or supported.get(command_number, "system_command")
        return VistaCommand(
            command_type=command_type,
            confidence="medium" if command_number in supported or extension else "low",
            operands={"system_command": f"#{command_number}", "suffix": suffix, "prompt": context.prompt},
            **common,
        )

    @staticmethod
    def _parse_programming(sequence: str, common: dict[str, Any]) -> VistaCommand:
        if sequence == "#93":
            command_type = "program_menu_enter"
        elif sequence in {"*97", "*94", "*99", "*98"}:
            command_type = "program_exit" if sequence in {"*99", "*98"} else "program_field_change"
        else:
            command_type = "program_field_change"
        return VistaCommand(command_type=command_type, confidence="medium", operands={"program_mode": True}, **common)


def command_from_request(
    request: Mapping[str, Any],
    *,
    source: str = "mqtt",
    actor_id: str = "",
    actor_name: str = "",
    interaction_id: str = "",
) -> VistaCommand:
    if not isinstance(request, Mapping):
        raise CommandValidationError("command payload must be an object")
    action = request.get("action", request.get("command_type", request.get("type", "")))
    if not isinstance(action, str) or not action.strip():
        raise CommandValidationError("command action is required")
    action = action.strip().lower().replace("-", "_")
    if action == "arm":
        mode = request.get("mode", request.get("operands", {}).get("mode") if isinstance(request.get("operands"), Mapping) else "")
        action = f"arm_{str(mode).lower()}" if mode else ""
    aliases = {
        "away": "arm_away", "stay": "arm_home", "arm_stay": "arm_home",
        "home": "arm_home", "night": "arm_night", "instant": "arm_instant",
        "maximum": "arm_maximum", "off": "disarm",
        "keypad": "keypad_command", "raw_keypad": "keypad_command",
        "raw_logical_keypad": "keypad_command", "logical_keypad": "keypad_command",
        "interactive_keypad": "interactive_menu",
    }
    action = aliases.get(action, action)
    partition = request.get("partition")
    if partition is None:
        raise CommandValidationError("semantic command requires a partition")
    if isinstance(partition, bool):
        raise CommandValidationError("VISTA partition must be 1..8")
    try:
        partition = int(partition)
    except (TypeError, ValueError) as exc:
        raise CommandValidationError("VISTA partition must be 1..8") from exc
    if not 1 <= partition <= 8:
        raise CommandValidationError("VISTA partition must be 1..8")

    operands = request.get("operands", {})
    if not isinstance(operands, Mapping):
        raise CommandValidationError("command operands must be an object")
    operands = dict(operands)
    code = request.get("code", operands.get("code", ""))
    if code:
        code = validate_pin(code)
    raw_sequence = request.get("sequence", request.get("keys", request.get("raw_sequence", "")))
    if raw_sequence in (None, ""):
        raw_sequence = ""
    else:
        if action not in RAW_SEQUENCE_COMMAND_TYPES:
            raise CommandValidationError(
                "raw keypad sequence requires an explicit keypad or interactive command"
            )
        raw_sequence = validate_keypad_sequence(raw_sequence)
        if any(character not in "0123456789*#" for character in raw_sequence):
            raise CommandValidationError(
                "executable keypad commands support only 0-9, *, and #"
            )
        interactive = request.get("interactive", operands.get("interactive", False))
        if action in {"output_control", "instant_activation"} and interactive is not True:
            raise CommandValidationError(
                f"{action} raw sequence requires explicit interactive mode"
            )
        if action in {"output_control", "instant_activation"}:
            operands["interactive"] = True
    required_code = {
        "disarm", "arm_away", "arm_home", "arm_night", "arm_instant", "arm_maximum",
        "force_arm_away", "force_arm_home", "walk_test", "zone_bypass", "unbypass_zones",
        "bypass_zones", "quick_bypass",
        "group_bypass", "bypass_display", "user_management", "chime", "goto_partition",
        "user_capabilities", "access_relay", "system_command", "output_control", "instant_activation",
        "access_control",
    }
    if action in {"access_control", "interactive_menu", "programming_session"}:
        if not raw_sequence:
            raise CommandValidationError(
                "this interactive command requires its exact keypad sequence"
            )
    if action in required_code and not code:
        raise CommandValidationError("this VISTA command requires an exactly four-digit PIN")
    if action in {"zone_bypass", "unbypass_zones", "bypass_zones"}:
        values = request.get("zones", operands.get("zones", []))
        operands["zones"] = list(normalize_zones(values))
        action = "zone_bypass" if action != "unbypass_zones" else "unbypass_zones"
    if action == "group_bypass":
        group = operands.get("group", request.get("group"))
        try:
            group_number = int(group)
        except (TypeError, ValueError) as exc:
            raise CommandValidationError("VISTA bypass group must be 01..15") from exc
        if not 1 <= group_number <= 15:
            raise CommandValidationError("VISTA bypass group must be 01..15")
        operands["group"] = f"{group_number:02d}"
    if action == "goto_partition":
        target = operands.get("target_partition", request.get("target_partition"))
        if isinstance(target, bool) or not isinstance(target, int) or not 1 <= target <= 8:
            raise CommandValidationError("GOTO target partition must be 1..8")
        operands["target_partition"] = target
    if action == "output_control":
        device = operands.get("device", request.get("device"))
        if isinstance(device, int):
            device = f"{device:02d}"
        if not isinstance(device, str) or re.fullmatch(r"[0-9]{2}", device) is None:
            raise CommandValidationError("output device must be exactly two digits")
        state = str(operands.get("state", request.get("state", ""))).lower()
        if state not in {"on", "off"}:
            raise CommandValidationError("output state must be on or off")
        operands.update({"device": device, "state": state})
    if action == "instant_activation":
        action_code = operands.get("action_code", request.get("action_code", ""))
        if isinstance(action_code, int):
            action_code = f"{action_code:02d}"
        if not isinstance(action_code, str) or re.fullmatch(r"[0-9]{2}", action_code) is None:
            raise CommandValidationError("instant activation action code must be two digits")
        operands["action_code"] = action_code
    if action in {"arm_away", "arm_home", "arm_maximum", "arm_instant", "arm_night", "disarm"}:
        selected = operands.get("partitions")
        if selected is not None:
            if not isinstance(selected, (list, tuple)) or not selected:
                raise CommandValidationError("global arming partitions are required")
            normalized_partitions = []
            for selected_partition in selected:
                if isinstance(selected_partition, bool):
                    raise CommandValidationError("global arming partition must be 1..8")
                try:
                    selected_number = int(selected_partition)
                except (TypeError, ValueError) as exc:
                    raise CommandValidationError("global arming partition must be 1..8") from exc
                if not 1 <= selected_number <= 8:
                    raise CommandValidationError("global arming partition must be 1..8")
                normalized_partitions.append(selected_number)
            operands["partitions"] = sorted(set(normalized_partitions))
            operands["global_arming"] = True
    if action == "system_command":
        namespace = operands.get("system_command", request.get("system_command", ""))
        if not isinstance(namespace, str) or re.fullmatch(r"#[0-9]{2}", namespace) is None:
            raise CommandValidationError("system command must use the #nn namespace")
        operands["system_command"] = namespace
    return VistaCommand(
        command_type=action,
        partition=partition,
        code=code,
        operands=operands,
        raw_sequence=raw_sequence,
        source=source,
        actor_id=actor_id,
        actor_name=actor_name,
        interaction_id=interaction_id,
        confidence="high",
        status="requested",
    )


def compile_keypad_sequence(command: VistaCommand) -> str:
    """Compile a semantic command into the exact logical keypad sequence."""
    if command.raw_sequence:
        if command.command_type not in RAW_SEQUENCE_COMMAND_TYPES:
            raise CommandValidationError(
                "semantic command cannot override its operation with a raw keypad sequence"
            )
        if any(character not in "0123456789*#" for character in command.raw_sequence):
            raise CommandValidationError(
                "executable keypad commands support only 0-9, *, and #"
            )
        _validate_interactive_sequence(command)
        return command.raw_sequence
    code = validate_pin(command.code)
    operands = command.operands
    command_type = command.command_type
    global_partitions = operands.get("partitions")
    if (
        operands.get("global_arming")
        and isinstance(global_partitions, (list, tuple))
        and command_type in {"disarm", "arm_away", "arm_home", "arm_maximum", "arm_instant", "arm_night"}
    ):
        if operands.get("subtype"):
            raise CommandValidationError(
                "global arming with a subtype requires its exact keypad sequence"
            )
        action_digit = {
            "disarm": "1",
            "arm_away": "2",
            "arm_home": "3",
            "arm_maximum": "4",
            "arm_instant": "7",
            "arm_night": "7",
        }[command_type]
        partitions = normalize_partitions(global_partitions)
        return code + action_digit + "".join(str(partition) for partition in partitions) + "*"
    if "partitions" in operands and command_type in {
        "disarm", "arm_away", "arm_home", "arm_maximum", "arm_instant", "arm_night"
    }:
        raise CommandValidationError(
            "partition operands require an explicit global arming selection"
        )
    simple = {
        "disarm": "1", "arm_away": "2", "arm_maximum": "4", "walk_test": "5",
        "chime": "9", "access_relay": "0", "user_capabilities": "**",
    }
    if command_type in simple:
        return code + simple[command_type]
    if command_type == "arm_home":
        subtype = str(operands.get("subtype", ""))
        if subtype and subtype not in "123":
            raise CommandValidationError("arm home subtype must be 1, 2, or 3")
        return code + "3" + subtype
    if command_type in {"arm_instant", "arm_night"}:
        subtype = str(operands.get("subtype", ""))
        if subtype and subtype not in "123":
            raise CommandValidationError("arm instant subtype must be 1, 2, or 3")
        return code + "7" + subtype
    if command_type == "zone_bypass":
        zones = normalize_zones(operands.get("zones", []))
        return code + "6" + "".join(zones) + "**"
    if command_type == "unbypass_zones":
        zones = normalize_zones(operands.get("zones", []))
        return code + "#7731" + "".join(zones) + "**"
    if command_type == "quick_bypass":
        return code + "6#"
    if command_type == "group_bypass":
        group = operands.get("group", "")
        if not isinstance(group, str) or re.fullmatch(r"(?:0[1-9]|1[0-5])", group) is None:
            raise CommandValidationError("VISTA bypass group must be 01..15")
        return code + "6*" + group
    if command_type == "goto_partition":
        target = operands.get("target_partition")
        if not isinstance(target, int) or not 1 <= target <= 8:
            raise CommandValidationError("GOTO target partition must be 1..8")
        return code + "*" + str(target)
    if command_type == "output_control":
        raise CommandValidationError(
            "output_control requires its complete interactive keypad sequence, including menu exit"
        )
    if command_type == "instant_activation":
        raise CommandValidationError(
            "instant_activation requires its complete interactive keypad sequence, including menu exit"
        )
    if command_type == "system_command":
        raise CommandValidationError(
            "system_command requires its complete interactive keypad sequence"
        )
    if command_type in {"program_enter", "program_menu_enter", "program_exit", "program_exit_local", "program_field_change"}:
        raise CommandValidationError("programming commands require their exact keypad sequence")
    raise CommandValidationError(f"no keypad compiler exists for {command_type}")


def _validate_interactive_sequence(command: VistaCommand) -> None:
    """Ensure a prompt-driven semantic command carries its full safe flow.

    The panel does not treat the namespace prefix as the completed operation.
    Requiring the semantic prefix to match the exact sequence prevents a
    mislabeled command from becoming a different keypad operation, while the
    terminal markers prevent releasing the keypad owner inside a menu.
    """
    if command.command_type in {"keypad_command", "interactive_menu"}:
        _validate_known_menu_exit(command.raw_sequence)
        return
    if command.command_type not in {"output_control", "instant_activation"}:
        return
    if not command.code:
        raise CommandValidationError("interactive VISTA command requires an exactly four-digit PIN")
    sequence = command.raw_sequence
    if command.command_type == "output_control":
        device = command.operands.get("device")
        state = command.operands.get("state")
        if (
            not isinstance(device, str)
            or re.fullmatch(r"[0-9]{2}", device) is None
            or state not in {"on", "off"}
        ):
            raise CommandValidationError("output control operands are invalid")
        prefix = command.code + "#70" + device + ("1" if state == "on" else "0")
        if not sequence.startswith(prefix):
            raise CommandValidationError(
                "output control sequence does not match its semantic operands"
            )
        # Keypad #70 returns to ENTER DEVICE NO. after '*'; 00 is the
        # documented quit entry that restores the normal keypad context.
        if sequence != prefix + "*00":
            raise CommandValidationError(
                "output control sequence must perform one relay action, press *, and exit with 00"
            )
        return

    action_code = command.operands.get("action_code")
    if not isinstance(action_code, str) or re.fullmatch(r"[0-9]{2}", action_code) is None:
        raise CommandValidationError("instant activation action code must be two digits")
    prefix = command.code + "#77" + action_code
    if not sequence.startswith(prefix):
        raise CommandValidationError(
            "instant activation sequence does not match its action code"
        )
    # #77 is committed only after its action specifier, confirmation, and
    # quit-menu prompts have been completed.  Each continuation is a '*'.
    if not sequence.endswith("*1*1*"):
        raise CommandValidationError(
            "instant activation sequence must complete confirmation and quit the menu"
        )


def _validate_known_menu_exit(sequence: str) -> None:
    """Reject a raw logical command that stops inside a known VISTA menu."""
    if re.match(r"[0-9]{4}#70", sequence) and not sequence.endswith("*00"):
        raise CommandValidationError(
            "#70 keypad sequence must press * and exit the relay menu with 00"
        )
    if re.match(r"[0-9]{4}#77[0-9]{2}", sequence) and not sequence.endswith("*1*1*"):
        raise CommandValidationError(
            "#77 keypad sequence must complete confirmation and quit the menu"
        )


def compile_keypad_segments(command: VistaCommand, *, max_strokes: int = 5) -> tuple[str, ...]:
    if not 1 <= max_strokes <= 5:
        raise CommandValidationError("keypad frame size must be 1..5")
    sequence = compile_keypad_sequence(command)
    return tuple(sequence[index:index + max_strokes] for index in range(0, len(sequence), max_strokes))


@dataclass(frozen=True)
class ExecutionPlan:
    command: VistaCommand
    mechanism: str
    native_action: str = ""
    keypad_sequence: str = ""
    keypad_segments: tuple[str, ...] = ()


NATIVE_COMMANDS = {
    "disarm": "DISARM",
    "arm_away": "ARM_AWAY",
    "arm_home": "ARM_HOME",
    "arm_night": "ARM_NIGHT",
    "arm_maximum": "ARM_MAXIMUM",
    "force_arm_away": "FORCE_ARM_AWAY",
    "force_arm_home": "FORCE_ARM_HOME",
}


def native_command_covers_entire_command(command: VistaCommand) -> bool:
    """Return whether the native one-partition operation preserves all semantics."""
    return bool(
        command.command_type in NATIVE_COMMANDS
        and command.partition is not None
        and bool(command.code)
        and not command.raw_sequence
        and not command.operands
    )


def plan_command(
    command: VistaCommand,
    *,
    native_available: bool,
    keypad_available: bool,
) -> ExecutionPlan:
    if native_available and native_command_covers_entire_command(command):
        return ExecutionPlan(
            command=command.with_execution(execution_mechanism="native", status="planned"),
            mechanism="native",
            native_action=NATIVE_COMMANDS[command.command_type],
        )
    if not keypad_available:
        raise CommandValidationError("no enabled VISTA execution mechanism supports this command")
    sequence = compile_keypad_sequence(command)
    return ExecutionPlan(
        command=command.with_execution(execution_mechanism="keypad", status="planned"),
        mechanism="keypad",
        keypad_sequence=sequence,
        keypad_segments=compile_keypad_segments(command),
    )
