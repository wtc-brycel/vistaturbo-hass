import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))

from vista_bridge.programming_guard import InstallerProgrammingGuard  # noqa: E402
from vista_bridge.protocol import build_keypad_stroke_command  # noqa: E402


class InstallerProgrammingGuardTests(unittest.TestCase):
    def commit(self, guard, partition, keys):
        update = guard.inspect_frame(build_keypad_stroke_command(partition, keys))
        self.assertIsNotNone(update)
        self.assertFalse(update.blocked)
        guard.commit(update)

    def test_blocks_any_four_digits_followed_by_800_across_frames(self):
        guard = InstallerProgrammingGuard()
        self.commit(guard, 1, "1234")
        self.commit(guard, 1, "8")
        self.commit(guard, 1, "0")

        update = guard.inspect_frame(build_keypad_stroke_command(1, "0"))

        self.assertIsNotNone(update)
        self.assertTrue(update.blocked)
        self.assertEqual(update.partition, 1)

    def test_blocking_800_also_stops_turbo_8000_before_final_digit(self):
        guard = InstallerProgrammingGuard()
        self.commit(guard, 1, "2468")
        self.commit(guard, 1, "80")

        update = guard.inspect_frame(build_keypad_stroke_command(1, "00"))

        self.assertIsNotNone(update)
        self.assertTrue(update.blocked)

    def test_multi_key_frame_is_rejected_atomically(self):
        guard = InstallerProgrammingGuard()
        self.commit(guard, 1, "12")

        update = guard.inspect_frame(build_keypad_stroke_command(1, "34800"))

        self.assertIsNotNone(update)
        self.assertTrue(update.blocked)
        # Because the blocked frame is never committed, a fresh 800 does not
        # inherit the unsent 348 prefix.
        follow_up = guard.inspect_frame(build_keypad_stroke_command(1, "800"))
        self.assertIsNotNone(follow_up)
        self.assertFalse(follow_up.blocked)

    def test_non_numeric_key_breaks_the_sequence(self):
        guard = InstallerProgrammingGuard()
        self.commit(guard, 1, "1234")
        self.commit(guard, 1, "#")

        update = guard.inspect_frame(build_keypad_stroke_command(1, "800"))

        self.assertIsNotNone(update)
        self.assertFalse(update.blocked)

    def test_partitions_have_independent_history(self):
        guard = InstallerProgrammingGuard()
        self.commit(guard, 1, "1234")
        self.commit(guard, 2, "800")

        update = guard.inspect_frame(build_keypad_stroke_command(1, "800"))

        self.assertIsNotNone(update)
        self.assertTrue(update.blocked)

    def test_reset_clears_history(self):
        guard = InstallerProgrammingGuard()
        self.commit(guard, 1, "1234")
        guard.reset()

        update = guard.inspect_frame(build_keypad_stroke_command(1, "800"))

        self.assertIsNotNone(update)
        self.assertFalse(update.blocked)

    def test_non_keypad_and_invalid_frames_are_ignored(self):
        guard = InstallerProgrammingGuard()
        self.assertIsNone(guard.inspect_frame(b"08as0064\r\n"))
        self.assertIsNone(guard.inspect_frame(b"0AKS110000\r\n"))


if __name__ == "__main__":
    unittest.main()
