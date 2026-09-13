from __future__ import annotations

import logging

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

LOG = logging.getLogger(__name__)

_COMMAND_NAMES = {
    WILL: "WILL",
    WONT: "WONT",
    DO: "DO",
    DONT: "DONT",
}

_OPTION_NAMES = {
    OPT_BINARY: "BINARY",
    OPT_ECHO: "ECHO",
    OPT_SUPPRESS_GO_AHEAD: "SUPPRESS-GO-AHEAD",
    OPT_COM_PORT: "COM-PORT-OPTION",
}


class TelnetSerialFilter:
    """Telnet/RFC2217 compatibility layer for serial-over-TCP servers.

    Transparent raw TCP payloads pass through unchanged. If Telnet IAC traffic
    is observed, the filter consumes Telnet control traffic so it never reaches
    the VISTA frame parser. Telnet BINARY is requested in both directions so
    serial data is not subject to NVT CR/LF processing. If the peer supports
    RFC2217 COM-PORT-OPTION, the filter also requests the known-good VISTA
    serial parameters: 9600 baud, 8 data bits, no parity, one stop bit, and no
    flow control.
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
        self._tx_binary_active = False
        self._rx_binary_active = False
        self._tx_binary_refused = False
        self._rx_binary_refused = False
        self._rfc2217_active = False
        self._rfc2217_configured = False
        self._rfc2217_refused = False
        self._subnegotiation = bytearray()

    @property
    def active(self) -> bool:
        """Whether Telnet control traffic has been observed this session."""

        return self._active

    @property
    def tx_binary_active(self) -> bool:
        """Whether the peer agreed that Vista Turbo may transmit binary data."""

        return self._tx_binary_active

    @property
    def rx_binary_active(self) -> bool:
        """Whether the peer agreed to transmit binary data to Vista Turbo."""

        return self._rx_binary_active

    @property
    def tx_binary_refused(self) -> bool:
        return self._tx_binary_refused

    @property
    def rx_binary_refused(self) -> bool:
        return self._rx_binary_refused

    @property
    def rfc2217_active(self) -> bool:
        """Whether the peer has agreed to RFC2217 COM-PORT-OPTION."""

        return self._rfc2217_active

    @property
    def rfc2217_configured(self) -> bool:
        """Whether Vista Turbo has sent its RFC2217 serial configuration."""

        return self._rfc2217_configured

    @property
    def rfc2217_refused(self) -> bool:
        """Whether the peer explicitly refused RFC2217 COM-PORT-OPTION."""

        return self._rfc2217_refused

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
                    LOG.info(
                        "Telnet control detected; requesting transparent binary serial mode"
                    )
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
                    LOG.info("Telnet RX command 0x%02X", value)
                    self._state = self._DATA
                continue

            if self._state == self._NEGOTIATION:
                command = self._command
                self._command = None
                self._state = self._DATA
                self._log_negotiation(command, value)
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
                    LOG.info("Telnet subnegotiation command 0x%02X consumed", value)
                    self._state = self._SUBNEGOTIATION

        return bytes(serial), bytes(replies)

    def encode(self, data: bytes) -> bytes:
        """Encode serial bytes for the socket once Telnet mode is detected."""

        if not self._active or IAC not in data:
            return data
        return data.replace(bytes((IAC,)), bytes((IAC, IAC)))

    def _startup_negotiation(self) -> bytes:
        """Request a transparent Telnet data path and probe RFC2217 support."""

        if self._startup_sent:
            return b""
        self._startup_sent = True
        LOG.info(
            "Telnet TX options: WONT ECHO, DONT ECHO, WILL SGA, WILL BINARY, "
            "DO BINARY, DO COM-PORT-OPTION"
        )
        return b"".join(
            (
                self._option(WONT, OPT_ECHO),
                self._option(DONT, OPT_ECHO),
                self._option(WILL, OPT_SUPPRESS_GO_AHEAD),
                self._option(WILL, OPT_BINARY),
                self._option(DO, OPT_BINARY),
                self._option(DO, OPT_COM_PORT),
            )
        )

    def _reply_to_negotiation(self, command: int | None, option: int) -> bytes:
        if command == WILL:
            if option == OPT_ECHO:
                # The startup preamble already sent DONT ECHO.
                return b""
            if option == OPT_SUPPRESS_GO_AHEAD:
                return self._option(DO, option)
            if option == OPT_COM_PORT:
                # Lantronix CoBos commonly responds to DO 0x2C with WILL 0x2C.
                self._rfc2217_refused = False
                LOG.info("RFC2217 COM-PORT-OPTION accepted by serial server")
                return self._activate_rfc2217()
            if option == OPT_BINARY:
                # Acknowledges our DO BINARY request: peer -> bridge is binary.
                if not self._rx_binary_active:
                    LOG.info("Telnet binary mode accepted for panel-to-bridge data")
                self._rx_binary_active = True
                self._rx_binary_refused = False
                return b""
            return self._option(DONT, option)

        if command == DO:
            if option == OPT_SUPPRESS_GO_AHEAD:
                # Acknowledges WILL SGA from the startup preamble.
                return b""
            if option == OPT_COM_PORT:
                # Support the RFC's usual client-WILL/server-DO direction too.
                self._rfc2217_refused = False
                LOG.info("RFC2217 COM-PORT-OPTION requested by serial server")
                return self._option(WILL, option) + self._activate_rfc2217()
            if option == OPT_BINARY:
                # Acknowledges our WILL BINARY request: bridge -> peer is binary.
                if not self._tx_binary_active:
                    LOG.info("Telnet binary mode accepted for bridge-to-panel data")
                self._tx_binary_active = True
                self._tx_binary_refused = False
                return b""
            if option == OPT_ECHO:
                return self._option(WONT, option)
            return self._option(WONT, option)

        if command == WONT:
            if option == OPT_BINARY:
                self._rx_binary_active = False
                self._rx_binary_refused = True
                LOG.warning("Serial server refused panel-to-bridge Telnet BINARY mode")
            elif option == OPT_COM_PORT:
                self._rfc2217_active = False
                self._rfc2217_refused = True
                LOG.info(
                    "Serial server refused RFC2217 COM-PORT-OPTION; using configured serial settings"
                )
            return b""

        if command == DONT:
            if option == OPT_BINARY:
                self._tx_binary_active = False
                self._tx_binary_refused = True
                LOG.warning("Serial server refused bridge-to-panel Telnet BINARY mode")
            elif option == OPT_COM_PORT:
                self._rfc2217_active = False
                self._rfc2217_refused = True
                LOG.info(
                    "Serial server refused RFC2217 COM-PORT-OPTION; using configured serial settings"
                )
            return b""

        return b""

    def _activate_rfc2217(self) -> bytes:
        self._rfc2217_active = True
        if self._rfc2217_configured:
            return b""
        self._rfc2217_configured = True
        LOG.info("RFC2217 TX serial configuration: 9600 baud, 8N1, no flow control")
        return self._rfc2217_configuration()

    def _process_subnegotiation(self, payload: bytes) -> bytes:
        # RFC2217 acknowledgements, modem/line-state notifications, and flow
        # notifications are transport metadata. Consume them completely so they
        # never reach the VISTA protocol parser.
        if payload[:1] == bytes((OPT_COM_PORT,)):
            self._rfc2217_active = True
            command = payload[1] if len(payload) > 1 else None
            if command is None:
                LOG.info("RFC2217 RX empty COM-PORT subnegotiation")
            else:
                LOG.info("RFC2217 RX COM-PORT subnegotiation command=%d", command)
        else:
            option = payload[0] if payload else None
            if option is not None:
                LOG.info("Telnet RX subnegotiation option=0x%02X", option)
        return b""

    def _log_negotiation(self, command: int | None, option: int) -> None:
        command_name = _COMMAND_NAMES.get(command, f"0x{command:02X}" if command is not None else "?")
        option_name = _OPTION_NAMES.get(option, f"option-0x{option:02X}")
        LOG.info("Telnet RX: %s %s", command_name, option_name)

    @classmethod
    def _rfc2217_configuration(cls) -> bytes:
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
