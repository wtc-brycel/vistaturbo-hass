import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))

from vista_bridge.framing import VistaStreamFramer  # noqa: E402


class VistaStreamFramerTests(unittest.TestCase):
    def test_crlf_frames(self):
        framer = VistaStreamFramer()
        frames = framer.feed(b"08OK009E\r\n0AFVOK00F9\r\n")
        self.assertEqual([frame.data for frame in frames], [b"08OK009E", b"0AFVOK00F9"])
        self.assertEqual([frame.termination for frame in frames], ["crlf", "crlf"])

    def test_split_across_tcp_reads(self):
        framer = VistaStreamFramer()
        self.assertEqual(framer.feed(b"08OK"), [])
        frames = framer.feed(b"009E\r\n")
        self.assertEqual(len(frames), 1)
        self.assertEqual(frames[0].data, b"08OK009E")

    def test_idle_flush_preserves_unknown_protocol_data(self):
        framer = VistaStreamFramer()
        self.assertEqual(framer.feed(b"1BnqSOMETHING"), [])
        frame = framer.flush_idle()
        self.assertIsNotNone(frame)
        self.assertEqual(frame.data, b"1BnqSOMETHING")
        self.assertEqual(frame.termination, "idle")


if __name__ == "__main__":
    unittest.main()
