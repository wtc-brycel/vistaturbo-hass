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
        bridge._raw_tx_queue = queue.Queue()
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

    def test_raw_tx_queue_is_bounded_and_rejects_overflow(self):
        bridge = self.make_bridge_shell()
        bridge._raw_tx_queue = queue.Queue(maxsize=1)
        bridge._panel_connected.set()
        self.assertTrue(bridge.enqueue_raw_tx(b"one")[0])
        accepted, reason = bridge.enqueue_raw_tx(b"two")
        self.assertFalse(accepted)
        self.assertEqual(reason, "raw_tx_queue_full")
        self.assertEqual(bridge._raw_tx_queue.qsize(), 1)

    def test_normal_tx_queue_is_bounded_and_rejects_overflow(self):
        bridge = self.make_bridge_shell()
        bridge._tx_queue = queue.Queue(maxsize=1)
        bridge._panel_connected.set()
        self.assertTrue(bridge._enqueue_tx(b"one", source="sync", label="one")[0])
        accepted, reason = bridge._enqueue_tx(b"two", source="sync", label="two")
        self.assertFalse(accepted)
        self.assertEqual(reason, "tx_queue_full")
        self.assertEqual(bridge._tx_queue.qsize(), 1)

    def test_direct_raw_tx_payload_is_type_and_length_checked(self):
        bridge = self.make_bridge_shell()
        bridge._panel_connected.set()
        for payload in (bytearray(b"A"), b"A" * 513, b""):
            accepted, reason = bridge._enqueue_tx(payload, source="debug", label="raw")
            self.assertFalse(accepted)
            self.assertEqual(reason, "invalid_raw_tx")


if __name__ == "__main__":
    unittest.main()
