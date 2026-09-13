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


LANTRONIX_STARTUP_REPLY = bytes.fromhex(
    "ff fc 01 "
    "ff fe 01 "
    "ff fb 03 "
    "ff fd 2c "
    "ff fd 03"
)

RFC2217_CONFIG = bytes.fromhex(
    "ff fa 2c 0a ff ff ff f0 "
    "ff fa 2c 0b ff ff ff f0 "
    "ff fa 2c 01 00 00 25 80 ff f0 "
    "ff fa 2c 02 08 ff f0 "
    "ff fa 2c 03 01 ff f0 "
    "ff fa 2c 04 01 ff f0 "
    "ff fa 2c 05 01 ff f0"
)


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
    async def test_lantronix_rfc2217_control_never_reaches_vista_framer(self):
        bridge = VistaBridge.__new__(VistaBridge)
        bridge.settings = SimpleNamespace(panel=SimpleNamespace(frame_idle_ms=1000))
        bridge.framer = VistaStreamFramer()
        bridge._telnet = TelnetSerialFilter()
        bridge.rx_bytes = 0
        frames = []
        bridge._handle_frame = frames.append

        reader = FakeReader(
            [
                # Real Lantronix opening observed on hardware.
                bytes.fromhex("ff fb 01 ff fb 03"),
                # CoBos-style response after the client requests RFC2217.
                bytes.fromhex("ff fc 01 ff fd 03 ff fb 2c"),
                # RFC2217 SET-BAUDRATE acknowledgement followed by serial data.
                bytes.fromhex("ff fa 2c 65 00 00 25 80 ff f0")
                + b"08OK009E\r\n",
                b"",
            ]
        )
        writer = FakeWriter()

        with self.assertRaisesRegex(ConnectionError, "serial server closed"):
            await bridge._read_loop(reader, writer)

        self.assertTrue(bridge._telnet.active)
        self.assertTrue(bridge._telnet.rfc2217_active)
        self.assertTrue(bridge._telnet.rfc2217_configured)
        self.assertEqual(writer.writes, [LANTRONIX_STARTUP_REPLY, RFC2217_CONFIG])
        self.assertEqual(writer.drain_count, 2)
        self.assertEqual(bridge.rx_bytes, len(b"08OK009E\r\n"))
        self.assertEqual(len(frames), 1)
        self.assertEqual(frames[0].data, b"08OK009E")

    async def test_fragmented_rfc2217_negotiation_and_vista_payload(self):
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
                bytes.fromhex("03 ff fc 01 ff"),
                bytes.fromhex("fd 03 ff fb"),
                bytes.fromhex("2c") + b"08OK",
                b"009E\r\n",
                b"",
            ]
        )
        writer = FakeWriter()

        with self.assertRaises(ConnectionError):
            await bridge._read_loop(reader, writer)

        self.assertEqual(writer.writes, [LANTRONIX_STARTUP_REPLY, RFC2217_CONFIG])
        self.assertEqual(len(frames), 1)
        self.assertEqual(frames[0].data, b"08OK009E")


if __name__ == "__main__":
    unittest.main()
