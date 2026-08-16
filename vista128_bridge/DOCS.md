# Vista Turbo RS232

## Compatibility

Developed and tested against a **VISTA-128BPT**. Other VISTA Turbo models are currently untested and are not claimed as supported. This App depends on the VISTA Turbo RS-232 automation interface and should not be assumed to work with non-Turbo VISTA panels.

## Connection model

Vista Turbo RS232 is designed around a network serial server between Home Assistant and the panel. A **Lantronix UDS-series device** is the intended class of hardware. Equivalent transparent serial-to-IP devices may also be used.

The deployment path is:

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
Vista Turbo RS232 App
      |
     MQTT
      |
Home Assistant
```

The App expects the serial server to expose the VISTA automation port as a plain TCP byte stream. It connects to `panel_host` and `panel_port`; it does not currently open a local `/dev/tty*` device.

The **StarTech NETRS2321POE** is the serial-to-IP device currently tested with this project. It works when configured in raw TCP Server mode. On the StarTech, do not use COM Port/RFC2217 mode.

A different serial server should work if it provides the same transparent behavior. Avoid modes that add protocol framing, Telnet negotiation, RFC2217 control traffic, or other transformations to the serial data stream.

## Panel-side RS-232 connection

The VISTA-128BPT exposes the printer/automation serial port at two connection points on the control board:

- **TB4**, a terminal block intended for permanent field wiring
- **J9**, a 10-pin header used with the Honeywell/Resideo VT-SERCBL adapter

This project uses **TB4** for the permanent connection to the serial-to-IP device.

### TB4

The TB4 terminals are labeled:

```text
TXD   RXD   RTS/DTR   CTS/DSR   GND
```

Only three signals are required for Vista Turbo RS232:

```text
VISTA TB4 TXD  -> serial server receive input
VISTA TB4 RXD  -> serial server transmit output
VISTA TB4 GND  -> serial server signal ground
RTS/DTR        -> not connected
CTS/DSR        -> not connected
```

The `TXD` and `RXD` labels above are from the VISTA panel's point of view. The panel transmit signal must reach the serial server's receive input, and the serial server transmit signal must reach the panel receive input.

Do not assume that DB9 pin numbers alone identify signal direction. Serial devices may present themselves as DTE or DCE and may therefore require a straight-through or crossover wiring arrangement. Check the serial server documentation and wire by signal function.

TB4 is an RS-232 electrical interface, not a TTL UART. Do not connect the panel directly to a 3.3 V or 5 V UART without an RS-232 transceiver.

Power down the panel and serial interface before changing field wiring.

### J9 and VT-SERCBL

J9 is the alternate 10-pin serial header. A VT-SERCBL adapter converts J9 to a standard serial connector and is useful for temporary service or programming connections.

**TB4 and J9 are two access points to the same panel serial interface and should not be connected to separate serial devices at the same time.** Disconnect one before using the other.

For a permanent Home Assistant installation, TB4 is preferred because it supports direct field wiring to the serial server without leaving a service cable attached to the board.

### Physical path used by this project

```text
VISTA-128BPT TB4
   TXD -----------------> serial server RX
   RXD <----------------- serial server TX
   GND ------------------ signal ground

serial server
   9600 8N1, no flow control
        |
        | raw TCP
        v
Vista Turbo RS232 App
```

The current installation uses a StarTech NETRS2321POE. A Lantronix UDS or another transparent RS-232-to-IP device can be wired the same way at the signal level.

## Requirements

- Home Assistant OS or Supervisor
- MQTT service available to the App
- VISTA-128BPT automation serial port
- Lantronix UDS-series device or equivalent transparent serial-to-IP server
- Network reachability from the App to the serial server TCP port

Serial settings:

```text
RS-232
9600 baud
8 data bits
no parity
1 stop bit
no flow control
```

Network serial mode:

```text
transparent raw TCP
server/listen mode
no RFC2217
no Telnet negotiation
no virtual COM-port dependency
```

Port numbers are device-specific. Configure a TCP port on the serial server, then set the same value as `panel_port` in the App. The current StarTech installation uses TCP port `10001`, but that port is not required by the VISTA protocol itself.

## Configuration

```yaml
panel_host: 10.2.2.141
panel_port: 10001
panel_timezone: America/New_York
mqtt_base_topic: vista128
mqtt_discovery_prefix: homeassistant
reconnect_min_seconds: 1
connect_timeout_seconds: 5
reconnect_max_seconds: 30
frame_idle_ms: 250
raw_logging: true
startup_sync_enabled: true
startup_sync_initial_delay_ms: 1000
startup_sync_command_delay_ms: 500
startup_sync_response_timeout_seconds: 5
periodic_sync_enabled: true
periodic_sync_interval_seconds: 300
periodic_sync_reconnect_after_failures: 3
transport_print_enabled: false
transport_host: ""
transport_http_port: 9101
transport_print_timeout_seconds: 5
transport_print_retry_seconds: 10
transport_print_queue_max: 5000
transport_print_width: 32
debug_raw_tx_enabled: false
```

`panel_host` is the IP address or resolvable hostname of the Lantronix UDS or equivalent serial-to-IP device. `panel_port` is the raw TCP listener configured on that device.

## Startup synchronization

A new TCP session requests:

```text
08as0064    arming status
08zs004B    zone status
08ZP008E    zone-to-partition map
08ZD009A    zone descriptors
```

`AS`, `ZS`, and `ZP` complete on `08OK`. `ZD` completes on the panel's `zd000""` terminator. Descriptor retrieval has a longer timeout because the panel walks its zone table before finishing.

Every packet is checked against its declared length and checksum before it can change Home Assistant state. Invalid packets remain available on the raw diagnostic topic.

## Periodic reconciliation

The bridge repeats these dynamic queries every 300 seconds by default:

```text
08as0064    arming status
08zs004B    zone status
```

This catches missed or unknown state transitions without repeatedly requesting static metadata. Startup, periodic, and event-triggered sync operations share one transaction lock.

After repeated failed reconciliations, the bridge closes the panel TCP session and lets the normal reconnect path establish a clean session.

## Home Assistant entities

### Partitions

Partitions are published as MQTT `alarm_control_panel` entities. Partition 1 is enabled by default. Partitions 2 through 8 are discovered but disabled by default.

Current state mapping:

```text
D  disarmed
N  disarmed, not ready
H  armed_home
A  armed_away
I  armed_night
M  armed_away, maximum mode attribute
B  armed_custom_bypass
```

Alarm events can overlay the partition state as `triggered` until restore or disarm.

The MQTT alarm schema requires a command topic. The bridge publishes one but rejects every normal Home Assistant alarm command while control is disabled.

### Zones

Only zones assigned to a VISTA partition are published. The binary sensor is `ON` for fault or alarm. Additional state is kept in attributes:

```yaml
zone: 21
partition: 1
descriptor: FRONT DOOR
faulted: false
trouble: false
alarm: false
bypassed: true
low_battery: false
tamper: false
raw_status: "8"
```

Zone names come directly from the VISTA alpha descriptor stream.

### Aggregate zone conditions

Four Home Assistant sensors summarize the per-zone conditions available in the authoritative `49ZS` zone-status snapshot:

```text
Faulted Zones
Zones in Check
Zones in Alarm
Bypassed Zones
```

The sensor state is the number of matching assigned zones. The attributes include the zone number, partition, and current VISTA alpha descriptor for each matching zone.

Example:

```yaml
state: 2
attributes:
  count: 2
  zone_numbers:
    - 21
    - 34
  zones:
    - zone: 21
      partition: 1
      descriptor: FRONT DOOR
    - zone: 34
      partition: 1
      descriptor: MAIN BEDROOM WINDOW
```

The four snapshot bits are interpreted as:

```text
0x1  faulted
0x2  trouble / CHECK
0x4  alarm
0x8  bypassed
```

`Zones in Check` is the Home Assistant display name for the VISTA trouble bit because CHECK is the operator-facing terminology used by the panel.

The aggregate sensors are refreshed from `49ZS` during startup and every periodic reconciliation. They are also updated immediately when an unsolicited event changes one of these tracked zone conditions.

RF low-battery and sensor-tamper conditions are currently learned from unsolicited event codes rather than the `49ZS` snapshot. They remain available in zone attributes and event data, but are not exposed as snapshot-backed aggregate sensors.

### Events

Decoded `1Bnq` events are published to:

- `vista128/event`: non-retained event stream
- `vista128/event/last`: retained event data
- `vista128/event/last_description`: retained event description

The state engine handles common arm/disarm, fault, trouble, bypass, alarm, RF low-battery, and tamper transitions. Unknown valid event codes are still published.

## Raw diagnostics

Default topics:

- `vista128/bridge/availability`: App MQTT availability
- `vista128/panel/connected`: panel TCP state
- `vista128/raw/frame`: every captured frame as JSON
- `vista128/raw/last_ascii`: last frame text
- `vista128/protocol/last_message_type`: packet class
- `vista128/stats/rx_frames`: received frame count
- `vista128/stats/rx_bytes`: received byte count
- `vista128/stats/tx_frames`: transmitted frame count
- `vista128/stats/tx_bytes`: transmitted byte count
- `vista128/stats/invalid_frames`: invalid packet count
- `vista128/sync/last_success`: last successful reconciliation
- `vista128/sync/consecutive_failures`: current sync failure count
- `vista128/panel/clock_offset_seconds`: panel time offset from receive time

The observed `69ZS` packet is validated and retained as raw data but does not update zone state. `49ZS` block reports are used for zone state.

## TransPort event receipts

When enabled, each decoded unsolicited system event is submitted as plain text to:

```text
POST http://<transport_host>:9101/print
Content-Type: text/plain
```

Startup traffic and periodic reconciliation do not print.

Example:

```text
VISTA EVENT #000001
2026-08-15 21:50:02
BYPASS [05]
P1 Z034 U002
MAIN BEDROOM WINDOW
PANEL 2026-08-15 23:44
--------------------------------
```

Pending receipts are stored in `/data/vista128_print_queue.sqlite3`.

Delivery rules:

- TCP connection failure: retry later
- HTTP 204: complete
- HTTP 4xx: failed
- timeout, disconnect, or 5xx after submission starts: uncertain, no automatic replay

This prevents an ambiguous network failure from automatically producing duplicate paper output.

## Raw transmit

`debug_raw_tx_enabled` is false by default. When enabled, the bridge accepts guarded test traffic on `vista128/debug/tx`.

```json
{"confirm":"I_UNDERSTAND_RAW_PANEL_TX","ascii":"..."}
```

Raw transmit is rejected while the panel is offline or a synchronization transaction is active.

## Design constraints

- The VISTA is authoritative.
- Invalid packets never change state.
- No optimistic alarm state.
- Pending panel commands are discarded on disconnect.
- Unknown valid events remain visible.
- Home Assistant is not required for VISTA alarm operation.

## Source layout

```text
bridge.py             connection and I/O orchestration
synchronizer.py       startup and periodic protocol transactions
message_handler.py    decoded packet handling
protocol.py           packet validation and parsers
event_codes.py        VISTA event code tables
state.py              partition and zone state
mqtt_client.py        MQTT transport and publication
mqtt_discovery.py     Home Assistant discovery payloads
printer.py            receipt formatting and delivery
printer_store.py      durable print queue
config.py             runtime settings
```

## AI disclosure

This App was made with the use of AI - ChatGPT Codex, specifically - to understand how the RS232 automation protocol exposed by the Vista works. Much of the information surrounding the Vista Turbo panels was not easily available to me and buried in manufacturer-specific documentation that was not provided by Honeywell. Much of this reverse-engineering was assisted by Crestron's documentation for their integration with the Vista Turbo panels.

Despite my reservations, this would not have been possible without the use of AI. I encourage you to review the source code for yourself to understand how it works. I have taken effort to ensure modularity and optimization in the code to the best I am able to for a project of this size that will only ever likely be used by me.

I will report back with my experiences as I use this. So far, it is a substantial improvement over the cloud-based TotalConnect 2.0 integration.
