from __future__ import annotations

IAC = 0xFF
DONT = 0xFE
DO = 0xFD
WONT = 0xFC
WILL = 0xFB
SB = 0xFA
SE = 0xF0

# Telnet options used by Lantronix CoBos/TruPort serial servers.
OPT_BINARY = 0x00
OPT_ECHO = 0x01
OPT_SUPPRESS_GO_AHEAD = 0x03
OPT_COM_PORT = 0x2C

# RFC2217 client-to-server COM-PORT-OPTION commands.
RFC2217_SET_BAUDRATE = 0x01
RFC2217_SET_DATASIZE = 0x02
RFC2217_SET_PARITY = 0x03
RFC2217_SET_STOPSIZE = 0x04
RFC2217_SET_CONTROL = 0x05
RFC2217_NOTIFY_LINESTATE = 0x06
RFC2217_NOTIFY_MODEMSTATE = 0x07
RFC2217_FLOWCONTROL_SUSPEND = 0x08
RFC2217_FLOWCONTROL_RESUME = 0x09
RFC2217_SET_LINESTATE_MASK = 0x0A
RFC2217_SET_MODEMSTATE_MASK = 0x0B
RFC2217_PURGE_DATA = 0x0C

# RFC2217 values used by Vista Turbo's known-good serial configuration.
RFC2217_PARITY_NONE = 0x01
RFC2217_STOPBITS_ONE = 0x01
RFC2217_FLOWCONTROL_NONE = 0x01


class TelnetSerialFilter:
    """Telnet/RFC2217 compatibility layer for serial-over-TCP servers.

    Transparent raw TCP payloads pass through unchanged. If Telnet IAC traffic
    is observed, the filter consumes Telnet control traffic so it never reaches
    the VISTA frame parser. For Lantronix CoBos/TruPort sessions it also
    negotiates RFC2217 COM-PORT-OPTION and requests the same serial parameters
    used by the working panel connection: 9600 baud, 8 data bits, no parity,
    one stop bit, and no flow control.
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
        self._startup_sent = False
        self._rfc2217_active = False
        self._rfc2217_configured = False
        self._subnegotiation = bytearray()

    @property
    def active(self) -> bool:
        """Whether Telnet control traffic has been observed this session."""

        return self._active

    @property
    def rfc2217_active(self) -> bool:
        """Whether the peer has agreed to RFC2217 COM-PORT-OPTION."""

        return self._rfc2217_active

    @property
    def rfc2217_configured(self) -> bool:
        """Whether Vista Turbo has sent its RFC2217 serial configuration."""

        return self._rfc2217_configured

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
                if not self._active:
                    self._active = True
                    replies.extend(self._startup_negotiation())

                if value == IAC:
                    # IAC IAC represents a literal 0xFF byte in Telnet data.
                    serial.append(IAC)
                    self._state = self._DATA
                elif value in (WILL, WONT, DO, DONT):
                    self._command = value
                    self._state = self._NEGOTIATION
                elif value == SB:
                    self._subnegotiation.clear()
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
                else:
                    self._subnegotiation.append(value)
                continue

            if self._state == self._SUBNEGOTIATION_IAC:
                if value == SE:
                    replies.extend(
                        self._process_subnegotiation(bytes(self._subnegotiation))
                    )
                    self._subnegotiation.clear()
                    self._state = self._DATA
                elif value == IAC:
                    # Escaped IAC inside a subnegotiation payload.
                    self._subnegotiation.append(IAC)
                    self._state = self._SUBNEGOTIATION
                else:
                    # Invalid/unsupported command inside subnegotiation. Consume
                    # it rather than exposing control bytes as serial payload.
                    self._state = self._SUBNEGOTIATION

        return bytes(serial), bytes(replies)

    def encode(self, data: bytes) -> bytes:
        """Encode serial bytes for the socket once Telnet mode is detected."""

        if not self._active or IAC not in data:
            return data
        return data.replace(bytes((IAC,)), bytes((IAC, IAC)))

    def _startup_negotiation(self) -> bytes:
        """Send the Lantronix-documented Telnet/RFC2217 client preamble."""

        if self._startup_sent:
            return b""
        self._startup_sent = True
        return b"".join(
            (
                self._option(WONT, OPT_ECHO),
                self._option(DONT, OPT_ECHO),
                self._option(WILL, OPT_SUPPRESS_GO_AHEAD),
                self._option(DO, OPT_COM_PORT),
            )
        )

    def _reply_to_negotiation(self, command: int | None, option: int) -> bytes:
        if command == WILL:
            if option == OPT_ECHO:
                # Already requested by the startup preamble. Do not accept
                # server-side echo on a binary serial transport.
                return b""
            if option == OPT_SUPPRESS_GO_AHEAD:
                return self._option(DO, option)
            if option == OPT_COM_PORT:
                # This is the expected Lantronix response to our DO 0x2C.
                return self._activate_rfc2217()
            if option == OPT_BINARY:
                return self._option(DO, option)
            return self._option(DONT, option)

        if command == DO:
            if option == OPT_SUPPRESS_GO_AHEAD:
                # We already advertised WILL SGA in the startup preamble.
                return b""
            if option == OPT_COM_PORT:
                # Some RFC2217 servers use the RFC's client-WILL/server-DO
                # direction. Support that variant too.
                return self._option(WILL, option) + self._activate_rfc2217()
            if option == OPT_BINARY:
                return self._option(WILL, option)
            if option == OPT_ECHO:
                return self._option(WONT, option)
            return self._option(WONT, option)

        # WONT and DONT are acknowledgements/refusals and need no reply.
        return b""

    def _activate_rfc2217(self) -> bytes:
        self._rfc2217_active = True
        if self._rfc2217_configured:
            return b""
        self._rfc2217_configured = True
        return self._rfc2217_configuration()

    def _process_subnegotiation(self, payload: bytes) -> bytes:
        # RFC2217 acknowledgements, modem/line-state notifications, and flow
        # notifications are transport metadata. Vista Turbo currently does not
        # need to expose them; consume them completely so they never reach the
        # VISTA protocol parser.
        if payload[:1] == bytes((OPT_COM_PORT,)):
            self._rfc2217_active = True
        return b""

    @classmethod
    def _rfc2217_configuration(cls) -> bytes:
        # Lantronix's documented sequence requests masks before setting port
        # parameters. 0xFF values are doubled by _subnegotiation() as required
        # by Telnet escaping rules.
        return b"".join(
            (
                cls._subnegotiation(
                    RFC2217_SET_LINESTATE_MASK,
                    bytes((0xFF,)),
                ),
                cls._subnegotiation(
                    RFC2217_SET_MODEMSTATE_MASK,
                    bytes((0xFF,)),
                ),
                cls._subnegotiation(
                    RFC2217_SET_BAUDRATE,
                    (9600).to_bytes(4, byteorder="big"),
                ),
                cls._subnegotiation(
                    RFC2217_SET_DATASIZE,
                    bytes((8,)),
                ),
                cls._subnegotiation(
                    RFC2217_SET_PARITY,
                    bytes((RFC2217_PARITY_NONE,)),
                ),
                cls._subnegotiation(
                    RFC2217_SET_STOPSIZE,
                    bytes((RFC2217_STOPBITS_ONE,)),
                ),
                cls._subnegotiation(
                    RFC2217_SET_CONTROL,
                    bytes((RFC2217_FLOWCONTROL_NONE,)),
                ),
            )
        )

    @staticmethod
    def _option(command: int, option: int) -> bytes:
        return bytes((IAC, command, option))

    @staticmethod
    def _subnegotiation(command: int, payload: bytes = b"") -> bytes:
        body = bytes((OPT_COM_PORT, command)) + payload
        body = body.replace(bytes((IAC,)), bytes((IAC, IAC)))
        return bytes((IAC, SB)) + body + bytes((IAC, SE))
