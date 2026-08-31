import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))

from vista_bridge.command_model import (  # noqa: E402
    CommandValidationError,
    KeypadParseContext,
    KeypadParser,
    VistaCommand,
    command_from_request,
    compile_keypad_segments,
    compile_keypad_sequence,
    normalize_zone,
    plan_command,
    validate_pin,
)


class CommandModelTests(unittest.TestCase):
    def test_pin_and_zone_invariants_are_fixed_width(self):
        self.assertEqual(validate_pin("0042"), "0042")
        for value in ("42", "042", "12345", "12a4"):
            with self.assertRaises(CommandValidationError):
                validate_pin(value)
        self.assertEqual(normalize_zone(1), "001")
        self.assertEqual(normalize_zone("027"), "027")
        self.assertEqual(normalize_zone(104), "104")
        for value in ("1", "27", "0104", 0, 1000):
            with self.assertRaises(CommandValidationError):
                normalize_zone(value)
        with self.assertRaises(CommandValidationError):
            command_from_request(
                {"action": "disarm", "partition": 1, "code": "123"}
            )
        with self.assertRaises(CommandValidationError):
            command_from_request(
                {
                    "action": "bypass_zones",
                    "partition": 1,
                    "code": "1234",
                    "zones": ["27"],
                }
            )

    def test_parser_recognizes_normal_commands_and_operands(self):
        parser = KeypadParser()
        cases = {
            "12341": ("disarm", {}),
            "12342": ("arm_away", {}),
            "12343": ("arm_home", {}),
            "123431": ("arm_home", {"subtype": "1"}),
            "12344": ("arm_maximum", {}),
            "12347": ("arm_instant", {}),
            "123471": ("arm_instant", {"subtype": "1"}),
            "12349": ("chime", {}),
            "1234*3": ("goto_partition", {"target_partition": 3}),
            "1234**": ("user_capabilities", {}),
            "#2": ("arm_away", {}),
            "#3": ("arm_home", {}),
            "#4": ("arm_maximum", {}),
            "#7": ("arm_instant", {}),
            "#9": ("quick_exit", {}),
        }
        for sequence, (command_type, operands) in cases.items():
            command = parser.parse(sequence, partition=1)
            self.assertEqual(command.command_type, command_type, sequence)
            self.assertEqual(command.operands, operands, sequence)

    def test_parser_preserves_three_digit_multi_zone_bypass(self):
        command = KeypadParser().parse("12346001027104**", partition=1)
        self.assertEqual(command.command_type, "zone_bypass")
        self.assertEqual(command.code, "1234")
        self.assertEqual(command.operands["zones"], ["001", "027", "104"])
        self.assertEqual(command.raw_sequence, "12346001027104**")

    def test_parser_supports_quick_group_and_system_families(self):
        self.assertEqual(
            KeypadParser().parse("12346#", partition=1).command_type,
            "quick_bypass",
        )
        group = KeypadParser().parse("12346*04", partition=1)
        self.assertEqual(group.command_type, "group_bypass")
        self.assertEqual(group.operands["group"], "04")
        output = KeypadParser().parse("1234#70041", partition=1)
        self.assertEqual(output.command_type, "output_control")
        self.assertEqual(output.operands["device"], "04")
        self.assertEqual(output.operands["state"], "on")
        instant = KeypadParser().parse("1234#7721", partition=1)
        self.assertEqual(instant.command_type, "instant_activation")
        self.assertEqual(instant.operands["action"], "arm_away")
        automatic_unbypass = KeypadParser().parse(
            "1234#7731*02*1*1*", partition=1
        )
        self.assertEqual(automatic_unbypass.command_type, "instant_activation")
        self.assertEqual(automatic_unbypass.operands["action"], "automatic_unbypass")
        self.assertEqual(automatic_unbypass.operands["zone_list"], "02")
        self.assertEqual(automatic_unbypass.confidence, "high")
        system = KeypadParser().parse("1234#60", partition=1)
        self.assertEqual(system.command_type, "event_log_display")
        self.assertEqual(
            KeypadParser().parse("1234#1", partition=1).command_type,
            "site_download",
        )
        extension = KeypadParser().parse(
            "1234#68",
            partition=1,
            context=KeypadParseContext(
                model="VISTA-250FBPT",
                extensions={"#68": "fire_walk_test_one_man"},
            ),
        )
        self.assertEqual(extension.command_type, "fire_walk_test_one_man")

    def test_parser_does_not_high_confidence_invalid_77_specifier(self):
        invalid_partition = KeypadParser().parse(
            "1234#7721*9*1*1*", partition=1
        )
        self.assertEqual(invalid_partition.command_type, "instant_activation")
        self.assertNotEqual(invalid_partition.confidence, "high")
        self.assertNotIn("partitions", invalid_partition.operands)

        invalid_zone_list = KeypadParser().parse(
            "1234#7731*16*1*1*", partition=1
        )
        self.assertEqual(invalid_zone_list.command_type, "instant_activation")
        self.assertNotEqual(invalid_zone_list.confidence, "high")
        self.assertNotIn("zone_list", invalid_zone_list.operands)

    def test_parser_marks_context_dependent_and_programming_commands(self):
        bare = KeypadParser().parse("1234", partition=1)
        self.assertEqual(bare.command_type, "code_entry_ambiguous")
        function = KeypadParser().parse("A", partition=1)
        self.assertEqual(function.command_type, "function_key_unknown")
        self.assertEqual(
            KeypadParser().parse("12348001", partition=1).command_type,
            "user_management",
        )
        self.assertEqual(
            KeypadParser().parse("98768000", partition=1).command_type,
            "program_enter",
        )
        self.assertEqual(
            KeypadParser().parse(
                "12341", partition=1, context=KeypadParseContext(program_mode=True)
            ).command_type,
            "program_field_change",
        )
        self.assertEqual(
            KeypadParser().parse("#93", partition=1, context=KeypadParseContext(program_mode=True)).command_type,
            "program_menu_enter",
        )

    def test_global_arming_selection_stays_one_command(self):
        command = KeypadParser().parse(
            "12342135*",
            partition=1,
            context=KeypadParseContext(global_arming=True),
        )
        self.assertEqual(command.command_type, "arm_away")
        self.assertEqual(command.operands["partitions"], [1, 3, 5])
        all_partitions = KeypadParser().parse(
            "1234210*",
            partition=1,
            context=KeypadParseContext(global_arming=True),
        )
        self.assertEqual(all_partitions.operands["partitions"], list(range(1, 9)))
        semantic = command_from_request(
            {
                "action": "arm_away",
                "partition": 1,
                "code": "1234",
                "operands": {"partitions": [1, 3, 5]},
            }
        )
        self.assertEqual(compile_keypad_sequence(semantic), "12342135*")

    def test_raw_sequence_cannot_override_semantic_command(self):
        with self.assertRaisesRegex(CommandValidationError, "explicit keypad or interactive"):
            command_from_request(
                {
                    "action": "bypass_zones",
                    "partition": 1,
                    "code": "1234",
                    "zones": [1],
                    "sequence": "12341",
                }
            )

        direct = VistaCommand(
            command_type="bypass_zones",
            partition=1,
            code="1234",
            operands={"zones": ["001"]},
            raw_sequence="12341",
        )
        with self.assertRaisesRegex(CommandValidationError, "cannot override"):
            compile_keypad_sequence(direct)

        with self.assertRaisesRegex(CommandValidationError, "#70 keypad sequence"):
            compile_keypad_sequence(
                command_from_request(
                    {
                        "action": "keypad_command",
                        "partition": 1,
                        "sequence": "1234#70041",
                    }
                )
            )

    def test_native_plan_requires_full_command_semantics(self):
        global_arm = command_from_request(
            {
                "action": "arm_away",
                "partition": 1,
                "code": "1234",
                "operands": {"partitions": [1, 3, 5]},
            }
        )
        global_plan = plan_command(
            global_arm, native_available=True, keypad_available=True
        )
        self.assertEqual(global_plan.mechanism, "keypad")
        self.assertEqual(global_plan.keypad_sequence, "12342135*")

        subtype = command_from_request(
            {
                "action": "arm_home",
                "partition": 1,
                "code": "1234",
                "operands": {"subtype": "1"},
            }
        )
        subtype_plan = plan_command(
            subtype, native_available=True, keypad_available=True
        )
        self.assertEqual(subtype_plan.mechanism, "keypad")
        self.assertEqual(subtype_plan.keypad_sequence, "123431")

    def test_prompt_commands_require_complete_explicit_interactive_sequences(self):
        output = command_from_request(
            {
                "action": "output_control",
                "partition": 1,
                "code": "1234",
                "device": "04",
                "state": "on",
            }
        )
        with self.assertRaisesRegex(CommandValidationError, "complete interactive"):
            plan_command(output, native_available=False, keypad_available=True)

        with self.assertRaisesRegex(CommandValidationError, "explicit interactive"):
            command_from_request(
                {
                    "action": "output_control",
                    "partition": 1,
                    "code": "1234",
                    "device": "04",
                    "state": "on",
                    "sequence": "1234#70041*00",
                }
            )

        complete_output = command_from_request(
            {
                "action": "output_control",
                "partition": 1,
                "code": "1234",
                "device": "04",
                "state": "on",
                "interactive": True,
                "sequence": "1234#70041*00",
            }
        )
        self.assertEqual(
            compile_keypad_sequence(complete_output), "1234#70041*00"
        )
        with self.assertRaisesRegex(CommandValidationError, "one relay action"):
            compile_keypad_sequence(
                VistaCommand(
                    command_type="output_control",
                    partition=1,
                    code="1234",
                    operands={"device": "04", "state": "on"},
                    raw_sequence="1234#70041*051*00",
                )
            )

        instant = command_from_request(
            {
                "action": "instant_activation",
                "partition": 1,
                "code": "1234",
                "action_code": "21",
                "partitions": [1, 3, 5],
                "interactive": True,
                "sequence": "1234#7721*135*1*1*",
            }
        )
        self.assertEqual(
            compile_keypad_sequence(instant), "1234#7721*135*1*1*"
        )
        with self.assertRaisesRegex(CommandValidationError, "quit the menu"):
            compile_keypad_sequence(
                VistaCommand(
                    command_type="instant_activation",
                    partition=1,
                    code="1234",
                    operands={"action_code": "21", "partitions": [1]},
                    raw_sequence="1234#7721*1",
                )
            )

        system = command_from_request(
            {
                "action": "system_command",
                "partition": 1,
                "code": "1234",
                "system_command": "#60",
            }
        )
        system_plan = plan_command(
            system, native_available=False, keypad_available=True
        )
        self.assertEqual(system_plan.mechanism, "keypad")
        self.assertEqual(system_plan.keypad_sequence, "1234#60")

        for namespace in ("#70", "#77"):
            with self.assertRaisesRegex(
                CommandValidationError, "typed or explicit interactive"
            ):
                command_from_request(
                    {
                        "action": "system_command",
                        "partition": 1,
                        "code": "1234",
                        "system_command": namespace,
                    }
                )

    def test_unbypass_zones_requires_documented_zone_list(self):
        with self.assertRaisesRegex(CommandValidationError, "zone list"):
            command_from_request(
                {
                    "action": "unbypass_zones",
                    "partition": 1,
                    "code": "1234",
                    "zones": [1, 27],
                }
            )

        command = command_from_request(
            {
                "action": "unbypass_zones",
                "partition": 1,
                "code": "1234",
                "zone_list": "02",
            }
        )
        self.assertEqual(command.command_type, "unbypass_zone_list")
        self.assertEqual(command.operands, {"zone_list": "02"})
        self.assertEqual(
            compile_keypad_sequence(command), "1234#7731*02*1*1*"
        )

        with self.assertRaisesRegex(CommandValidationError, "01..15"):
            command_from_request(
                {
                    "action": "unbypass_zones",
                    "partition": 1,
                    "code": "1234",
                    "zone_list": "16",
                }
            )

    def test_instant_activation_requires_matching_action_specific_operand(self):
        command = command_from_request(
            {
                "action": "instant_activation",
                "partition": 1,
                "code": "1234",
                "action_code": "21",
                "partitions": [1, 3, 5],
            }
        )
        self.assertEqual(
            compile_keypad_sequence(command), "1234#7721*135*1*1*"
        )
        with self.assertRaisesRegex(CommandValidationError, "action-specific"):
            compile_keypad_sequence(
                VistaCommand(
                    command_type="instant_activation",
                    partition=1,
                    code="1234",
                    operands={
                        "action_code": "21",
                        "partitions": [1, 3, 5],
                    },
                    raw_sequence="1234#7721*13*1*1*",
                )
            )
        with self.assertRaisesRegex(CommandValidationError, "unsupported operand"):
            command_from_request(
                {
                    "action": "instant_activation",
                    "partition": 1,
                    "code": "1234",
                    "action_code": "21",
                    "partitions": [1],
                    "relay": "04",
                }
            )

    def test_goto_zero_returns_to_original_partition(self):
        command = command_from_request(
            {
                "action": "goto_partition",
                "partition": 1,
                "code": "1234",
                "target_partition": 0,
            }
        )
        self.assertEqual(compile_keypad_sequence(command), "1234*0")
        parsed = KeypadParser().parse("1234*0", partition=1)
        self.assertEqual(parsed.operands["target_partition"], 0)

    def test_action_specific_operands_are_not_silently_ignored(self):
        with self.assertRaisesRegex(CommandValidationError, "subtype"):
            command_from_request(
                {
                    "action": "arm_away",
                    "partition": 1,
                    "code": "1234",
                    "operands": {"subtype": "1"},
                }
            )

        for action in ("chime", "quick_bypass", "walk_test"):
            with self.subTest(action=action):
                with self.assertRaisesRegex(CommandValidationError, "unsupported operand"):
                    command_from_request(
                        {
                            "action": action,
                            "partition": 1,
                            "code": "1234",
                            "operands": {"bogus": "not-consumed"},
                        }
                    )

    def test_compile_and_plan_choose_native_or_keypad(self):
        command = command_from_request(
            {"action": "arm", "mode": "away", "partition": 1, "code": "1234"},
            source="ha_frontend",
            interaction_id="i-1",
        )
        self.assertEqual(command.command_type, "arm_away")
        plan = plan_command(command, native_available=True, keypad_available=True)
        self.assertEqual(plan.mechanism, "native")
        self.assertEqual(plan.native_action, "ARM_AWAY")

        fallback = plan_command(command, native_available=False, keypad_available=True)
        self.assertEqual(fallback.mechanism, "keypad")
        self.assertEqual(fallback.keypad_sequence, "12342")
        self.assertEqual(fallback.keypad_segments, ("12342",))

    def test_deterministic_command_round_trip_preserves_semantics(self):
        cases = (
            {"action": "arm_stay", "partition": 1, "code": "1234"},
            {
                "action": "bypass_zones",
                "partition": 1,
                "code": "1234",
                "zones": [1, 27],
            },
        )
        for request in cases:
            original = command_from_request(request)
            parsed = KeypadParser().parse(
                compile_keypad_sequence(original), partition=original.partition
            )
            self.assertEqual(parsed.command_type, original.command_type)
            self.assertEqual(parsed.code, original.code)
            self.assertEqual(parsed.operands, original.operands)

    def test_compile_semantic_zone_command_and_segment_long_sequence(self):
        command = command_from_request(
            {
                "action": "bypass_zones",
                "partition": 1,
                "code": "1234",
                "zones": [1, 27, 104],
            }
        )
        sequence = compile_keypad_sequence(command)
        self.assertEqual(sequence, "12346001027104**")
        segments = compile_keypad_segments(command)
        self.assertEqual("".join(segments), sequence)
        self.assertTrue(all(1 <= len(segment) <= 5 for segment in segments))

    def test_sensitive_fields_are_not_in_default_telemetry_serialization(self):
        command = VistaCommand(
            command_type="keypad_command",
            partition=1,
            code="1234",
            raw_sequence="12342",
        )
        self.assertNotIn("1234", repr(command))
        public = command.to_dict()
        self.assertNotIn("code", public)
        self.assertNotIn("raw_sequence", public)
        self.assertEqual(command.to_dict(include_sensitive=True)["code"], "1234")


if __name__ == "__main__":
    unittest.main()
