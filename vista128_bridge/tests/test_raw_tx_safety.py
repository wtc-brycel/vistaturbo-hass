import os
import queue
import sys
import threading
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))
sys.path.insert(0, os.path.dirname(__file__))

from fake_paho import install_fake_paho  # noqa: E402

install_fake_paho()

from vista_bridge.bridge import VistaBridge  # noqa: E402


class SyncStub:
    @staticmethod
    def is_active() -> bool:
        return False


class RawTxSafetyTests(unittest.TestCase):
    def make_bridge_shell(self):
        bridge = VistaBridge.__new__(VistaBridge)
        bridge._tx_queue = queue.Queue()
        bridge._panel_connected = threading.Event()
        bridge.synchronizer = SyncStub()
        return bridge

    def test_raw_tx_rejected_while_offline(self):
        bridge = self.make_bridge_shell()
        accepted, message = bridge.enqueue_raw_tx(b"test")
        self.assertFalse(accepted)
        self.assertIn("offline", message)
        self.assertTrue(bridge._tx_queue.empty())

    def test_disconnect_flush_discards_pending_tx(self):
        bridge = self.make_bridge_shell()
        bridge._panel_connected.set()
        accepted, _ = bridge.enqueue_raw_tx(b"test")
        self.assertTrue(accepted)
        self.assertEqual(bridge._discard_pending_tx(), 1)
        self.assertTrue(bridge._tx_queue.empty())


if __name__ == "__main__":
    unittest.main()
