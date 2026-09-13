import os
import queue
import sys
import threading
import unittest
from types import SimpleNamespace

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))
sys.path.insert(0, os.path.dirname(__file__))

from fake_paho import install_fake_paho  # noqa: E402

install_fake_paho()

from vista_bridge.bridge import VistaBridge  # noqa: E402
from vista_bridge.programming_guard import InstallerProgrammingGuard  # noqa: E402
from vista_bridge.protocol import build_keypad_stroke_command  # noqa: E402


class FakeSynchronizer:
    def is_active(self):
        return False


class BridgeProgrammingGuardTests(unittest.TestCase):
    def make_bridge(self, *, queue_size=16):
        bridge = VistaBridge.__new__(VistaBridge)
        bridge._panel_connected = threading.Event()
        bridge._panel_connected.set()
        bridge._tx_queue = queue.Queue(maxsize=queue_size)
        bridge._raw_tx_queue = queue.Queue(maxsize=queue_size)
        bridge._installer_guard = InstallerProgrammingGuard()
        bridge._tx_safety_lock = threading.Lock()
        bridge.synchronizer = FakeSynchronizer()
        bridge.settings = SimpleNamespace()
        return bridge

    def enqueue(self, bridge, keys, *, source="control"):
        return bridge._enqueue_tx(
            build_keypad_stroke_command(1, keys),
            source=source,
            label="test",
        )

    def test_individual_keypresses_block_before_programming_entry(self):
        bridge = self.make_bridge()
        for keys in ("1234", "8", "0"):
            self.assertEqual(
                self.enqueue(bridge, keys),
                (True, "queued for immediate transmit"),
            )

        with self.assertLogs("vista_bridge.bridge", level="WARNING") as logs:
            result = self.enqueue(bridge, "0")

        self.assertEqual(result, (False, "installer_programming_blocked"))
        self.assertEqual(bridge._tx_queue.qsize(), 3)
        output = "\n".join(logs.output)
        self.assertIn("Blocked installer-programming keypad sequence", output)
        self.assertNotIn("1234", output)

    def test_privileged_raw_tx_cannot_bypass_guard(self):
        bridge = self.make_bridge()
        for keys in ("4321", "80"):
            self.assertTrue(self.enqueue(bridge, keys, source="debug")[0])

        result = self.enqueue(bridge, "0", source="debug")

        self.assertEqual(result, (False, "installer_programming_blocked"))
        self.assertEqual(bridge._raw_tx_queue.qsize(), 2)

    def test_non_numeric_key_breaks_rolling_history(self):
        bridge = self.make_bridge()
        for keys in ("1234", "#", "800"):
            self.assertTrue(self.enqueue(bridge, keys)[0])

        self.assertEqual(bridge._tx_queue.qsize(), 3)

    def test_queue_full_does_not_record_unsent_keypad_history(self):
        bridge = self.make_bridge(queue_size=1)
        bridge._tx_queue.put_nowait(object())

        result = self.enqueue(bridge, "1234")
        self.assertEqual(result, (False, "tx_queue_full"))

        bridge._tx_queue.get_nowait()
        self.assertTrue(self.enqueue(bridge, "800")[0])

    def test_non_keypad_tx_is_unaffected(self):
        bridge = self.make_bridge()

        result = bridge._enqueue_tx(
            b"08as0064\r\n",
            source="startup",
            label="arming_status",
        )

        self.assertEqual(result, (True, "queued for immediate transmit"))


if __name__ == "__main__":
    unittest.main()
