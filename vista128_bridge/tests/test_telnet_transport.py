import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))

from vista_bridge.telnet_transport import (  # noqa: E402
    DO,
    DONT,
    IAC,
    OPT_ECHO,
    OPT_SUPPRESS_GO_AHEAD,
    SB,
    SE,
    WILL,
    WONT,
    TelnetSerialFilter,
)


class TelnetSerialFilterTests(unittest.TestCase):
    def test_raw_tcp_payload_passes_through_unchanged(self):
        transport = TelnetSerialFilter()
        payload = b"08as0064\r\n"

        serial, replies = transport.feed(payload)

        self.assertEqual(serial, payload)
        self.assertEqual(replies, b"")
        self.assertFalse(transport.active)
        self.assertIs(transport.encode(payload), payload)

    def test_lantronix_echo_and_sga_negotiation_is_consumed(self):
        transport = TelnetSerialFilter()

        serial, replies = transport.feed(
            bytes((IAC, WILL, OPT_ECHO, IAC, WILL, OPT_SUPPRESS_GO_AHEAD))
        )

        self.assertEqual(serial, b"")
        self.assertEqual(
            replies,
            bytes(
                (
                    IAC,
                    DONT,
                    OPT_ECHO,
                    IAC,
                    DO,
                    OPT_SUPPRESS_GO_AHEAD,
                )
            ),
        )
        self.assertTrue(transport.active)

    def test_fragmented_telnet_negotiation_survives_tcp_read_boundaries(self):
        transport = TelnetSerialFilter()
        serial = bytearray()
        replies = bytearray()

        for chunk in (
            bytes((IAC,)),
            bytes((WILL, OPT_ECHO, IAC)),
            bytes((WILL,)),
            bytes((OPT_SUPPRESS_GO_AHEAD,)),
            b"08OK009E\r\n",
        ):
            filtered, response = transport.feed(chunk)
            serial.extend(filtered)
            replies.extend(response)

        self.assertEqual(serial, b"08OK009E\r\n")
        self.assertEqual(
            replies,
            bytes(
                (
                    IAC,
                    DONT,
                    OPT_ECHO,
                    IAC,
                    DO,
                    OPT_SUPPRESS_GO_AHEAD,
                )
            ),
        )

    def test_unknown_server_option_is_refused(self):
        transport = TelnetSerialFilter()

        serial, replies = transport.feed(bytes((IAC, WILL, 42)))

        self.assertEqual(serial, b"")
        self.assertEqual(replies, bytes((IAC, DONT, 42)))

    def test_client_option_request_is_refused(self):
        transport = TelnetSerialFilter()

        serial, replies = transport.feed(bytes((IAC, DO, 42)))

        self.assertEqual(serial, b"")
        self.assertEqual(replies, bytes((IAC, WONT, 42)))

    def test_wont_and_dont_are_consumed_without_reply(self):
        transport = TelnetSerialFilter()

        serial, replies = transport.feed(
            bytes((IAC, WONT, OPT_ECHO, IAC, DONT, OPT_SUPPRESS_GO_AHEAD))
        )

        self.assertEqual(serial, b"")
        self.assertEqual(replies, b"")
        self.assertTrue(transport.active)

    def test_subnegotiation_is_consumed_and_following_serial_data_preserved(self):
        transport = TelnetSerialFilter()
        serial = bytearray()
        replies = bytearray()

        for chunk in (
            bytes((IAC, SB, 44, 1, 2, IAC)),
            bytes((SE,)) + b"08OK009E\r\n",
        ):
            filtered, response = transport.feed(chunk)
            serial.extend(filtered)
            replies.extend(response)

        self.assertEqual(serial, b"08OK009E\r\n")
        self.assertEqual(replies, b"")

    def test_literal_iac_is_unescaped_on_receive_and_escaped_on_transmit(self):
        transport = TelnetSerialFilter()
        transport.feed(bytes((IAC, WILL, OPT_SUPPRESS_GO_AHEAD)))

        serial, replies = transport.feed(bytes((IAC, IAC)))

        self.assertEqual(serial, bytes((IAC,)))
        self.assertEqual(replies, b"")
        self.assertEqual(
            transport.encode(b"abc" + bytes((IAC,)) + b"def"),
            b"abc" + bytes((IAC, IAC)) + b"def",
        )


if __name__ == "__main__":
    unittest.main()
