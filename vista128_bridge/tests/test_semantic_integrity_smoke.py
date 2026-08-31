import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))

from vista_bridge.command_model import (  # noqa: E402
    CommandValidationError,
    command_from_request,
    compile_keypad_sequence,
)


class SemanticIntegritySmokeTests(unittest.TestCase):
    def test_audited_operands_cannot_outlive_execution_semantics(self):
        for action in ("chime", "quick_bypass", "walk_test"):
            with self.subTest(action=action):
                with self.assertRaises(CommandValidationError):
                    command_from_request(
                        {
                            "action": action,
                            "partition": 1,
                            "code": "1234",
                            "operands": {"ignored": 1},
                        }
                    )

    def test_unbypass_compilation_is_zone_list_based(self):
        command = command_from_request(
            {
                "action": "unbypass_zone_list",
                "partition": 1,
                "code": "1234",
                "zone_list": 3,
            }
        )
        self.assertEqual(command.operands["zone_list"], "03")
        self.assertEqual(
            compile_keypad_sequence(command), "1234#7731*03*1*1*"
        )


if __name__ == "__main__":
    unittest.main()
