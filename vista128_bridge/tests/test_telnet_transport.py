import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))

from vista_bridge.telnet_transport import (  # noqa: E402
    DO,
    DONT,
    IAC,
    OPT_BINARY,
    OPT_COM_PORT,
    OPT_ECHO,
    OPT_SUPPRESS_GO_AHEAD,
    RFC2217_FLOWCONTROL_NONE,
    RFC2217_SET_BAUDRATE,
    RFC2217_SET_CONTROL,
    RFC2217_SET_DATASIZE,
    RFC2217_SET_LINESTATE_MASK,
    RFC2217_SET_MODEMSTATE_MASK,
    RFC2217_SET_PARITY,
    RFC2217_SET_STOPSIZE,
    SB,
    SE,
    WILL,
    WONT,
    TelnetSerialFilter,
)


def option(command, value):
    return bytes((IAC, command, value))


def subnegotiation(command, payload=b""):
    body = bytes((OPT_COM_PORT, command)) + payload
    body = body.replace(bytes((IAC,)), bytes((IAC, IAC)))
    return bytes((IAC, SB)) + body + bytes((IAC, SE))


LANTRONIX_STARTUP = b"".join(
    (
        option(WONT, OPT_ECHO),
        option(DONT, OPT_ECHO),
        option(WILL, OPT_SUPPRESS_GO_AHEAD),
        option(WILL, OPT_BINARY),
        option(DO, OPT_BINARY),
        option(DO, OPT_COM_PORT),
    )
)

RFC2217_CONFIG = b"".join(
    (
        subnegotiation(RFC2217_SET_LINESTATE_MASK, bytes((0xFF,))),
        subnegotiation(RFC2217_SET_MODEMSTATE_MASK, bytes((0xFF,))),
        subnegotiation(RFC2217_SET_BAUDRATE, (9600).to_bytes(4, "big")),
        subnegotiation(RFC2217_SET_DATASIZE, bytes((8,))),
        subnegotiation(RFC2217_SET_PARITY, bytes((1,))),
        subnegotiation(RFC2217_SET_STOPSIZE, bytes((1,))),
        subnegotiation(RFC2217_SET_CONTROL, bytes((RFC2217_FLOWCONTROL_NONE,))),
    )
)


class TelnetSerialFilterTests(unittest.TestCase):
    def test_raw_tcp_payload_passes_through_unchanged(self):
        transport = TelnetSerialFilter()
        payload = b"08as0064\r\n"

        serial, replies = transport.feed(payload)

        self.assertEqual(serial, payload)
        self.assertEqual(replies, b"")
        self.assertFalse(transport.active)
        self.assertFalse(transport.tx_binary_active)
        self.assertFalse(transport.rx_binary_active)
        self.assertFalse(transport.rfc2217_active)
        self.assertFalse(transport.rfc2217_configured)
        self.assertIs(transport.encode(payload), payload)

    def test_lantronix_telnet_detection_requests_binary_both_directions(self):
        transport = TelnetSerialFilter()

        serial, replies = transport.feed(
            bytes((IAC, WILL, OPT_ECHO, IAC, WILL, OPT_SUPPRESS_GO_AHEAD))
        )

        self.assertEqual(serial, b"")
        self.assertEqual(
            replies,
            LANTRONIX_STARTUP + option(DO, OPT_SUPPRESS_GO_AHEAD),
        )
        self.assertTrue(transport.active)
        self.assertFalse(transport.tx_binary_active)
        self.assertFalse(transport.rx_binary_active)
        self.assertFalse(transport.rfc2217_active)

    def test_binary_acceptance_is_tracked_for_each_direction(self):
        transport = TelnetSerialFilter()
        transport.feed(bytes((IAC, WILL, OPT_ECHO)))

        serial, replies = transport.feed(
            bytes((IAC, WILL, OPT_BINARY, IAC, DO, OPT_BINARY))
        )

        self.assertEqual(serial, b"")
        self.assertEqual(replies, b"")
        self.assertTrue(transport.rx_binary_active)
        self.assertTrue(transport.tx_binary_active)
        self.assertFalse(transport.rx_binary_refused)
        self.assertFalse(transport.tx_binary_refused)

    def test_binary_refusal_is_tracked_for_each_direction(self):
        transport = TelnetSerialFilter()
        transport.feed(bytes((IAC, WILL, OPT_ECHO)))

        serial, replies = transport.feed(
            bytes((IAC, WONT, OPT_BINARY, IAC, DONT, OPT_BINARY))
        )

        self.assertEqual(serial, b"")
        self.assertEqual(replies, b"")
        self.assertFalse(transport.rx_binary_active)
        self.assertFalse(transport.tx_binary_active)
        self.assertTrue(transport.rx_binary_refused)
        self.assertTrue(transport.tx_binary_refused)

    def test_lantronix_rfc2217_acceptance_sends_9600_8n1_no_flow(self):
        transport = TelnetSerialFilter()
        transport.feed(
            bytes((IAC, WILL, OPT_ECHO, IAC, WILL, OPT_SUPPRESS_GO_AHEAD))
        )

        serial, replies = transport.feed(
            bytes(
                (
                    IAC,
                    WONT,
                    OPT_ECHO,
                    IAC,
                    DO,
                    OPT_SUPPRESS_GO_AHEAD,
                    IAC,
                    WILL,
                    OPT_BINARY,
                    IAC,
                    DO,
                    OPT_BINARY,
                    IAC,
                    WILL,
                    OPT_COM_PORT,
                )
            )
        )

        self.assertEqual(serial, b"")
        self.assertEqual(replies, RFC2217_CONFIG)
        self.assertTrue(transport.rx_binary_active)
        self.assertTrue(transport.tx_binary_active)
        self.assertTrue(transport.rfc2217_active)
        self.assertTrue(transport.rfc2217_configured)
        self.assertFalse(transport.rfc2217_refused)

    def test_rfc2217_refusal_falls_back_to_preconfigured_serial_settings(self):
        transport = TelnetSerialFilter()
        transport.feed(bytes((IAC, WILL, OPT_ECHO)))

        serial, replies = transport.feed(bytes((IAC, WONT, OPT_COM_PORT)))

        self.assertEqual(serial, b"")
        self.assertEqual(replies, b"")
        self.assertFalse(transport.rfc2217_active)
        self.assertFalse(transport.rfc2217_configured)
        self.assertTrue(transport.rfc2217_refused)

    def test_fragmented_negotiation_survives_tcp_read_boundaries(self):
        transport = TelnetSerialFilter()
        serial = bytearray()
        replies = bytearray()

        for chunk in (
            bytes((IAC,)),
            bytes((WILL, OPT_ECHO, IAC)),
            bytes((WILL,)),
            bytes((OPT_SUPPRESS_GO_AHEAD, IAC, WILL)),
            bytes((OPT_BINARY, IAC, DO)),
            bytes((OPT_BINARY, IAC, WILL)),
            bytes((OPT_COM_PORT,)),
            b"08OK009E\r\n",
        ):
            filtered, response = transport.feed(chunk)
            serial.extend(filtered)
            replies.extend(response)

        self.assertEqual(serial, b"08OK009E\r\n")
        self.assertEqual(
            replies,
            LANTRONIX_STARTUP
            + option(DO, OPT_SUPPRESS_GO_AHEAD)
            + RFC2217_CONFIG,
        )
        self.assertTrue(transport.rx_binary_active)
        self.assertTrue(transport.tx_binary_active)
        self.assertTrue(transport.rfc2217_active)

    def test_standard_server_do_com_port_variant_is_supported(self):
        transport = TelnetSerialFilter()

        serial, replies = transport.feed(bytes((IAC, DO, OPT_COM_PORT)))

        self.assertEqual(serial, b"")
        self.assertEqual(
            replies,
            LANTRONIX_STARTUP + option(WILL, OPT_COM_PORT) + RFC2217_CONFIG,
        )
        self.assertTrue(transport.rfc2217_active)

    def test_unknown_server_option_is_refused_after_startup(self):
        transport = TelnetSerialFilter()

        serial, replies = transport.feed(bytes((IAC, WILL, 42)))

        self.assertEqual(serial, b"")
        self.assertEqual(replies, LANTRONIX_STARTUP + option(DONT, 42))

    def test_unknown_client_option_is_refused_after_startup(self):
        transport = TelnetSerialFilter()

        serial, replies = transport.feed(bytes((IAC, DO, 42)))

        self.assertEqual(serial, b"")
        self.assertEqual(replies, LANTRONIX_STARTUP + option(WONT, 42))

    def test_rfc2217_ack_subnegotiation_is_consumed(self):
        transport = TelnetSerialFilter()
        transport.feed(bytes((IAC, WILL, OPT_COM_PORT)))

        # Server acknowledgment of SET-BAUDRATE 9600 uses command 101.
        serial, replies = transport.feed(
            bytes((IAC, SB, OPT_COM_PORT, 101, 0, 0, 0x25, 0x80, IAC, SE))
            + b"08OK009E\r\n"
        )

        self.assertEqual(serial, b"08OK009E\r\n")
        self.assertEqual(replies, b"")

    def test_subnegotiation_escaped_iac_is_consumed(self):
        transport = TelnetSerialFilter()
        transport.feed(bytes((IAC, WILL, OPT_COM_PORT)))

        serial, replies = transport.feed(
            bytes((IAC, SB, OPT_COM_PORT, 110, IAC, IAC, IAC, SE))
            + b"08OK009E\r\n"
        )

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
