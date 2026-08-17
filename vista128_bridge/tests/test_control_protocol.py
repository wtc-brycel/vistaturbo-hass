import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))

from vista_bridge.protocol import (  # noqa: E402
    build_keypad_stroke_command,
    build_native_alarm_command,
    validate_packet,
)


class ControlProtocolTests(unittest.TestCase):
    def test_single_key_frames_match_documented_vista_framing(self):
        expected = {
            "1": b"0AKS11002F\r\n",
            "*": b"0AKS1A001F\r\n",
            "#": b"0AKS1B001E\r\n",
            "PANIC_A": b"0AKS1C001D\r\n",
            "PANIC_B": b"0AKS1D001C\r\n",
            "PANIC_C": b"0AKS1E001B\r\n",
        }
        for key, frame in expected.items():
            with self.subTest(key=key):
                actual = build_keypad_stroke_command(1, [key])
                self.assertEqual(actual, frame)
                self.assertTrue(validate_packet(actual[:-2]).valid)

    def test_keypad_builder_supports_up_to_five_strokes(self):
        frame = build_keypad_stroke_command(2, "1234#")
        self.assertTrue(frame.startswith(b"0EKS21234B00"))
        self.assertTrue(validate_packet(frame[:-2]).valid)
        with self.assertRaises(ValueError):
            build_keypad_stroke_command(1, "")
        with self.assertRaises(ValueError):
            build_keypad_stroke_command(1, "123456")
        with self.assertRaises(ValueError):
            build_keypad_stroke_command(1, ["A"])

    def test_native_alarm_frames_partition_one(self):
        expected = {
            "ARM_AWAY": b"16AA00123410000000000C\r\n",
            "ARM_HOME": b"16AH001234100000000005\r\n",
            "ARM_NIGHT": b"16AI001234100000000004\r\n",
            "ARM_MAXIMUM": b"16AM001234100000000000\r\n",
            "FORCE_ARM_AWAY": b"16FA001234100000000007\r\n",
            "FORCE_ARM_HOME": b"16FH001234100000000000\r\n",
            "DISARM": b"16AD001234100000000009\r\n",
        }
        for action, frame in expected.items():
            with self.subTest(action=action):
                actual = build_native_alarm_command(action, "1234", (1,))
                self.assertEqual(actual, frame)
                self.assertTrue(validate_packet(actual[:-2]).valid)

    def test_native_alarm_partition_mask_and_validation(self):
        frame = build_native_alarm_command("ARM_AWAY", "2468", (2, 4))
        self.assertIn(b"01010000", frame)
        with self.assertRaises(ValueError):
            build_native_alarm_command("ARM_AWAY", "123", (1,))
        with self.assertRaises(ValueError):
            build_native_alarm_command("ARM_AWAY", "12A4", (1,))
        with self.assertRaises(ValueError):
            build_native_alarm_command("BOGUS", "1234", (1,))
        with self.assertRaises(ValueError):
            build_native_alarm_command("DISARM", "1234", (9,))


if __name__ == "__main__":
    unittest.main()
