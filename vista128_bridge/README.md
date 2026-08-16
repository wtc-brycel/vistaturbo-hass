# Vista Turbo RS232

Home Assistant App for the RS-232 automation interface used by Honeywell/Resideo VISTA Turbo alarm panels.

This project has been developed and tested against a **VISTA-128BPT**. Other VISTA Turbo models are currently untested and are not claimed as supported. It is not a general VISTA integration.

The App is designed to reach the panel through a **Lantronix UDS-series serial server or an equivalent transparent serial-to-IP device**. Development and current operation have been tested with a **StarTech NETRS2321POE** in raw TCP Server mode.

Current status: read-only monitoring is operational. The bridge publishes partition state, assigned zones, aggregate zone-condition sensors, VISTA alpha descriptors, decoded events, health metrics, and optional TransPort receipt output through MQTT Discovery. Home Assistant arm/disarm commands are not sent to the panel.

## Runtime path

```text
VISTA Turbo panel
    |
  RS-232
    |
Lantronix UDS or equivalent
serial-to-IP device
    |
 raw TCP
    |
Vista Turbo RS232
    |
   MQTT
    |
Home Assistant
```

The serial-to-IP device must present the panel data as a transparent TCP stream. The App connects to a configured host and TCP port and does not currently open a local `/dev/tty*` serial device directly.

Use these serial settings:

```text
9600 baud
8 data bits
no parity
1 stop bit
no flow control
```

On devices that offer several network modes, use a plain raw TCP server mode. RFC2217, virtual COM-port drivers, and vendor-specific framing are not required. The StarTech NETRS2321POE should be configured in raw TCP Server mode rather than COM Port/RFC2217 mode.

## Panel connection

For a permanent VISTA-128BPT installation, connect the serial server to the panel's **TB4** RS-232 terminal block:

```text
TB4 TXD  -> serial server RX
TB4 RXD  -> serial server TX
TB4 GND  -> serial server signal ground
```

Leave `RTS/DTR` and `CTS/DSR` unconnected for this App. Check the serial server documentation for its DB9 DTE/DCE pinout rather than assuming a cable pin mapping.

The alternate **J9 10-pin header** may be used with a VT-SERCBL adapter for a temporary serial connection. Do not use TB4 and J9 simultaneously. This project uses TB4 for the permanent connection.

TB4 is RS-232 level signaling. It is not a TTL UART connection.

## Current features

- Raw VISTA frame capture with length and checksum validation
- Startup state and metadata synchronization
- Five-minute state reconciliation by default
- Partition and assigned-zone MQTT Discovery entities
- Aggregate Faulted Zones, Zones in Check, Zones in Alarm, and Bypassed Zones sensors
- Real-time `1Bnq` event handling
- Zone alpha descriptor import
- Panel clock-offset diagnostics
- Optional continuous event receipts through TransPort
- Guarded raw transmit for protocol testing

The aggregate zone-condition sensors use only the four conditions available in the `49ZS` snapshot. Their state is a count and their attributes contain the matching assigned zones. RF low-battery and sensor-tamper events remain event-derived and are not presented as snapshot-backed aggregate sensors.

See `DOCS.md` for configuration and protocol behavior.

## AI disclosure

This App was made with the use of AI - ChatGPT Codex, specifically - to understand how the RS232 automation protocol exposed by the Vista works. Much of the information surrounding the Vista Turbo panels was not easily available to me and buried in manufacturer-specific documentation that was not provided by Honeywell. Much of this reverse-engineering was assisted by Crestron's documentation for their integration with the Vista Turbo panels.

Despite my reservations, this would not have been possible without the use of AI. I encourage you to review the source code for yourself to understand how it works. I have taken effort to ensure modularity and optimization in the code to the best I am able to for a project of this size that will only ever likely be used by me. 

I will report back with my experiences as I use this. So far, it is a substantial improvement over the cloud-based TotalConnect 2.0 integration.
