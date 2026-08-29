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
            "1234#7731001027**", partition=1
        )
        self.assertEqual(automatic_unbypass.command_type, "automatic_unbypass")
        self.assertEqual(automatic_unbypass.operands["zones"], ["001", "027"])
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
