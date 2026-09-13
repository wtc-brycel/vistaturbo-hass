import os
import sys
import unittest
from types import SimpleNamespace

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))
sys.path.insert(0, os.path.dirname(__file__))

from fake_paho import install_fake_paho  # noqa: E402

install_fake_paho()

from vista_bridge.bridge import VistaBridge  # noqa: E402
from vista_bridge.framing import VistaStreamFramer  # noqa: E402
from vista_bridge.telnet_transport import TelnetSerialFilter  # noqa: E402


class FakeReader:
    def __init__(self, chunks):
        self._chunks = iter(chunks)

    async def read(self, _size):
        return next(self._chunks, b"")


class FakeWriter:
    def __init__(self):
        self.writes = []
        self.drain_count = 0

    def write(self, data):
        self.writes.append(data)

    async def drain(self):
        self.drain_count += 1


class BridgeTelnetTests(unittest.IsolatedAsyncioTestCase):
    async def test_lantronix_negotiation_never_reaches_vista_framer(self):
        bridge = VistaBridge.__new__(VistaBridge)
        bridge.settings = SimpleNamespace(panel=SimpleNamespace(frame_idle_ms=1000))
        bridge.framer = VistaStreamFramer()
        bridge._telnet = TelnetSerialFilter()
        bridge.rx_bytes = 0
        frames = []
        bridge._handle_frame = frames.append

        reader = FakeReader(
            [
                bytes.fromhex("ff fb 01 ff fb 03"),
                b"08OK009E\r\n",
                b"",
            ]
        )
        writer = FakeWriter()

        with self.assertRaisesRegex(ConnectionError, "serial server closed"):
            await bridge._read_loop(reader, writer)

        self.assertTrue(bridge._telnet.active)
        self.assertEqual(writer.writes, [bytes.fromhex("ff fd 01 ff fd 03")])
        self.assertEqual(writer.drain_count, 1)
        self.assertEqual(bridge.rx_bytes, len(b"08OK009E\r\n"))
        self.assertEqual(len(frames), 1)
        self.assertEqual(frames[0].data, b"08OK009E")

    async def test_fragmented_negotiation_and_vista_payload_can_share_reads(self):
        bridge = VistaBridge.__new__(VistaBridge)
        bridge.settings = SimpleNamespace(panel=SimpleNamespace(frame_idle_ms=1000))
        bridge.framer = VistaStreamFramer()
        bridge._telnet = TelnetSerialFilter()
        bridge.rx_bytes = 0
        frames = []
        bridge._handle_frame = frames.append

        reader = FakeReader(
            [
                bytes.fromhex("ff"),
                bytes.fromhex("fb 01 ff fb"),
                bytes.fromhex("03") + b"08OK",
                b"009E\r\n",
                b"",
            ]
        )
        writer = FakeWriter()

        with self.assertRaises(ConnectionError):
            await bridge._read_loop(reader, writer)

        self.assertEqual(
            b"".join(writer.writes),
            bytes.fromhex("ff fd 01 ff fd 03"),
        )
        self.assertEqual(len(frames), 1)
        self.assertEqual(frames[0].data, b"08OK009E")


if __name__ == "__main__":
    unittest.main()
