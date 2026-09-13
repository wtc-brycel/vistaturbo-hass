from __future__ import annotations

IAC = 0xFF
DONT = 0xFE
DO = 0xFD
WONT = 0xFC
WILL = 0xFB
SB = 0xFA
SE = 0xF0

# Lantronix Telnet-mode serial servers advertise ECHO and
# SUPPRESS-GO-AHEAD when the TCP client connects. Accept both server-side
# options so the session completes the normal character-at-a-time Telnet
# negotiation used by legacy clients such as terminal programs/redirectors.
# Telnet control traffic is still consumed here and never reaches VISTA.
OPT_ECHO = 0x01
OPT_SUPPRESS_GO_AHEAD = 0x03


class TelnetSerialFilter:
    """Strip Telnet control traffic from a serial-over-TCP byte stream.

    Legacy serial servers such as Lantronix UDS units can expose their serial
    channel through a Telnet-mode TCP listener rather than a completely raw
    socket. VISTA protocol bytes are ASCII and must never see Telnet IAC
    negotiation sequences. This filter auto-detects IAC traffic, preserves its
    parser state across arbitrary TCP read boundaries, emits the minimum
    required negotiation replies, and otherwise leaves raw TCP payloads alone.
    """

    _DATA = 0
    _IAC = 1
    _NEGOTIATION = 2
    _SUBNEGOTIATION = 3
    _SUBNEGOTIATION_IAC = 4

    def __init__(self) -> None:
        self._state = self._DATA
        self._command: int | None = None
        self._active = False

    @property
    def active(self) -> bool:
        """Whether Telnet control traffic has been observed this session."""

        return self._active

    def feed(self, chunk: bytes) -> tuple[bytes, bytes]:
        """Return ``(serial_data, telnet_replies)`` for one TCP read."""

        serial = bytearray()
        replies = bytearray()

        for value in chunk:
            if self._state == self._DATA:
                if value == IAC:
                    self._state = self._IAC
                else:
                    serial.append(value)
                continue

            if self._state == self._IAC:
                self._active = True
                if value == IAC:
                    # IAC IAC represents a literal 0xFF byte in Telnet data.
                    serial.append(IAC)
                    self._state = self._DATA
                elif value in (WILL, WONT, DO, DONT):
                    self._command = value
                    self._state = self._NEGOTIATION
                elif value == SB:
                    self._state = self._SUBNEGOTIATION
                else:
                    # One-byte Telnet command (NOP, GA, AYT, etc.). It has no
                    # meaning to the serial protocol and is consumed here.
                    self._state = self._DATA
                continue

            if self._state == self._NEGOTIATION:
                command = self._command
                self._command = None
                self._state = self._DATA
                replies.extend(self._reply_to_negotiation(command, value))
                continue

            if self._state == self._SUBNEGOTIATION:
                if value == IAC:
                    self._state = self._SUBNEGOTIATION_IAC
                continue

            if self._state == self._SUBNEGOTIATION_IAC:
                if value == SE:
                    self._state = self._DATA
                elif value == IAC:
                    # Escaped IAC inside subnegotiation; still not serial data.
                    self._state = self._SUBNEGOTIATION
                else:
                    self._state = self._SUBNEGOTIATION

        return bytes(serial), bytes(replies)

    def encode(self, data: bytes) -> bytes:
        """Encode serial bytes for the socket once Telnet mode is detected."""

        if not self._active or IAC not in data:
            return data
        return data.replace(bytes((IAC,)), bytes((IAC, IAC)))

    @staticmethod
    def _reply_to_negotiation(command: int | None, option: int) -> bytes:
        if command == WILL:
            # Accept the two options used by the observed Lantronix Telnet
            # listener. In particular, WILL ECHO must be answered with DO ECHO;
            # refusing it leaves some legacy servers outside their expected
            # character-at-a-time Telnet state even though the TCP socket stays
            # open. Unknown server options remain refused.
            response = (
                DO
                if option in (OPT_ECHO, OPT_SUPPRESS_GO_AHEAD)
                else DONT
            )
            return bytes((IAC, response, option))
        if command == DO:
            # The bridge can safely agree that it will suppress Telnet Go Ahead
            # markers, but it must not claim that it will echo server data.
            response = WILL if option == OPT_SUPPRESS_GO_AHEAD else WONT
            return bytes((IAC, response, option))
        # WONT and DONT are acknowledgements/refusals and need no reply.
        return b""
