# Vista Turbo HASS

Vista Turbo HASS is a local Home Assistant App for the RS-232 automation interface used by Honeywell/Resideo VISTA Turbo alarm panels. It is intended to connect to the panel through a transparent serial-to-IP device, such as a Lantronix UDS-series device or an equivalent serial server, and publishes panel state through MQTT Discovery.

The project has been developed and tested against a **VISTA-128BPT**. Other VISTA Turbo models are currently untested and are not claimed as supported. This project is not intended for non-Turbo VISTA panels unless their compatibility is specifically established.

Read-only monitoring is the current stable baseline. This includes querying the partition keypad display over the native Turbo RS-232 automation interface. Home Assistant arm/disarm commands are intentionally not sent to the panel yet.

## Intended hardware path

```text
VISTA Turbo panel
      |
    RS-232
      |
Lantronix UDS or equivalent
transparent serial-to-IP server
      |
     TCP
      |
Vista Turbo RS232
      |
     MQTT
      |
Home Assistant
```

A **Lantronix UDS-series serial server** is the intended type of transport. An equivalent device is also suitable if it can expose the VISTA serial stream as a plain TCP socket without altering the data. Development and current operation have been tested with a **StarTech NETRS2321POE** configured in raw TCP Server mode.

The App expects a TCP host and port for the panel connection. It does not currently open a local `/dev/tty*` serial device directly.

## Panel-side RS-232 wiring

For permanent automation wiring on the VISTA-128BPT, use terminal block **TB4** on the control board. The terminals are labeled:

```text
TXD   RXD   RTS/DTR   CTS/DSR   GND
```

Vista Turbo RS232 only requires three signals:

```text
VISTA TB4 TXD  -> serial server receive input
VISTA TB4 RXD  -> serial server transmit output
VISTA TB4 GND  -> serial server signal ground
RTS/DTR        -> not connected
CTS/DSR        -> not connected
```

Wire by signal function, not by DB9 pin number alone. Serial servers may present their DB9 connector as DTE or DCE, which changes whether a straight-through or crossover connection is appropriate.

The panel also exposes the serial port on the **J9 10-pin header** for use with a VT-SERCBL adapter. J9 is useful for temporary or service connections. **Do not use TB4 and J9 at the same time.** This project uses TB4 for the permanent serial-server connection.

TB4 carries normal RS-232 signaling, not TTL-level UART signaling. Do not connect TB4 directly to a 3.3 V or 5 V UART without an RS-232 transceiver.

## Features

- Partition state in Home Assistant
- Partition 2 x 16 keypad display retrieval over RS-232
- Event-triggered and periodic keypad refresh
- Four binary sensors per assigned zone: Fault, Alarm, Check, and Bypass
- Aggregate Fault Zones, Alarm Zones, Check Zones, and Bypass Zones sensors
- VISTA alpha descriptor import
- Real-time automation event decoding
- Periodic state reconciliation
- Packet length and checksum validation
- Panel clock-offset diagnostics
- Optional continuous event receipts through TransPort
- Guarded raw transmit for protocol testing

The four per-zone binary sensors and four aggregate sensors are derived from the VISTA `49ZS` snapshot. They reconcile with the panel every five minutes by default and also update from relevant unsolicited events.

Keypad display support uses the VISTA Turbo `KD` request. Partition 1 polling is enabled by default at a 7-second interval. A valid system event for a configured partition also requests a debounced keypad refresh.

## Install as a Home Assistant App repository

Add this repository to the Home Assistant App Store:

```text
https://github.com/wtc-brycel/vistaturbo-hass
```

Then install **Vista Turbo RS232** from the repository and configure the serial-to-IP server address and TCP port.

The serial side should be configured as:

```text
RS-232
9600 baud
8 data bits
no parity
1 stop bit
no flow control
```

The network side should provide a transparent raw TCP server connection. RFC2217, virtual COM-port drivers, and device-specific encapsulation are not required. On the StarTech NETRS2321POE, use raw TCP Server mode rather than COM Port/RFC2217 mode.

See [`vista128_bridge/DOCS.md`](vista128_bridge/DOCS.md) for configuration and protocol details.

## AI disclosure

This App was made with the use of AI - ChatGPT Codex, specifically - to understand how the RS232 automation protocol exposed by the Vista works. Much of the information surrounding the Vista Turbo panels was not easily available to me and buried in manufacturer-specific documentation that was not provided by Honeywell. Much of this reverse-engineering was assisted by Crestron's documentation for their integration with the Vista Turbo panels.

Despite my reservations, this would not have been possible without the use of AI. I encourage you to review the source code for yourself to understand how it works. I have taken effort to ensure modularity and optimization in the code to the best I am able to for a project of this size that will only ever likely be used by me.

I will report back with my experiences as I use this. So far, it is a substantial improvement over the cloud-based TotalConnect 2.0 integration.
