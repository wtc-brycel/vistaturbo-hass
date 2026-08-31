import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))

from vista_bridge.command_model import (  # noqa: E402
    CommandValidationError,
    command_from_request,
    compile_keypad_sequence,
)


class SystemCommandPolicyTests(unittest.TestCase):
    def test_documented_one_shot_namespaces_compile_directly(self):
        for namespace in ("#41", "#42", "#65", "#71", "#72", "#73"):
            with self.subTest(namespace=namespace):
                command = command_from_request(
                    {
                        "action": "system_command",
                        "partition": 1,
                        "code": "1234",
                        "system_command": namespace,
                    }
                )
                self.assertEqual(
                    compile_keypad_sequence(command), f"1234{namespace}"
                )

    def test_prompt_driven_namespaces_are_not_generic_direct_commands(self):
        for namespace in (
            "#60", "#61", "#62", "#63", "#70", "#74", "#75", "#77",
            "#79", "#80", "#81", "#82", "#83",
        ):
            with self.subTest(namespace=namespace):
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


if __name__ == "__main__":
    unittest.main()
