# Vista Turbo RS232

## Compatibility

Developed and tested against a **VISTA-128BPT**. Other VISTA Turbo models are currently untested and are not claimed as supported. This App depends on the VISTA Turbo RS-232 automation interface and should not be assumed to work with non-Turbo VISTA panels.

## Connection model

Vista Turbo RS232 is designed around a network serial server between Home Assistant and the panel. A **Lantronix UDS-series device** is the intended class of hardware. Equivalent transparent serial-to-IP devices may also be used.

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

```text
TXD   RXD   RTS/DTR   CTS/DSR   GND
```

Only three signals are required:

```text
VISTA TB4 TXD  -> serial server receive input
VISTA TB4 RXD  -> serial server transmit output
VISTA TB4 GND  -> serial server signal ground
RTS/DTR        -> not connected
CTS/DSR        -> not connected
```

The `TXD` and `RXD` labels are from the VISTA panel's point of view. Wire by signal function rather than assuming a DB9 pin mapping. Serial servers may present their connector as DTE or DCE.

TB4 is an RS-232 electrical interface, not a TTL UART. Do not connect the panel directly to a 3.3 V or 5 V UART without an RS-232 transceiver.

Power down the panel and serial interface before changing field wiring.

### J9 and VT-SERCBL

J9 is the alternate 10-pin serial header. A VT-SERCBL adapter converts J9 to a standard serial connector and is useful for temporary service or programming connections.

**Do not connect separate serial devices to TB4 and J9 at the same time.** Disconnect one before using the other.

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

Port numbers are device-specific. The current StarTech installation uses TCP port `10001`, but that port is not required by the VISTA protocol itself.

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
keypad_display_enabled: true
keypad_partitions: "1"
keypad_poll_interval_seconds: 7
keypad_event_refresh_delay_ms: 250
transport_print_enabled: false
transport_host: ""
transport_http_port: 9101
transport_print_timeout_seconds: 5
transport_print_retry_seconds: 10
transport_print_queue_max: 5000
transport_print_width: 32
debug_raw_tx_enabled: false
```

`panel_host` is the IP address or resolvable hostname of the serial-to-IP device. `panel_port` is its raw TCP listener.

`keypad_partitions` is a comma-separated list of partitions whose keypad display should be queried, for example `"1"` or `"1,2"`. A real keypad should exist on each queried partition. Partition 1 is the default.

The keypad display is queried every 7 seconds by default. Valid unsolicited system events also request a debounced keypad refresh for the affected configured partition. All keypad queries share the same serialized transaction lock as startup and periodic synchronization.

## Startup synchronization

A new TCP session requests:

```text
08as0064    arming status
08zs004B    zone status
08ZP008E    zone-to-partition map
08ZD009A    zone descriptors
```

`AS`, `ZS`, and `ZP` complete on `08OK`. `ZD` completes on the panel's `zd000""` terminator.

Every packet is checked against its declared length and checksum before it can change Home Assistant state. Invalid packets remain available on the raw diagnostic topic.

## Periodic reconciliation

The bridge repeats these dynamic queries every 300 seconds by default:

```text
08as0064    arming status
08zs004B    zone status
```

This catches missed or unknown state transitions without repeatedly requesting static metadata. After repeated failed reconciliations, the bridge closes the panel TCP session and lets the normal reconnect path establish a clean session.

## Keypad display polling

The VISTA Turbo RS-232 automation interface can return the 2 x 16 character keypad display for a partition. This was physically validated on the VISTA-128BPT with the Partition 1 request:

```text
09KD10077\r\n
```

The captured panel transaction was:

```text
0AFVKD0004
29kd<32 display bytes><LED nibble>00<checksum>
08OK009E
```

The captured display decoded to:

```text
P1   DISARMED   
BYPAS-RDY TO ARM
```

The high bit of the first display byte indicates keypad backlight state. That bit is removed before the first display character is decoded. The status nibble currently maps as:

```text
0x1  Ready LED
0x2  Trouble LED
0x4  Armed LED
```

The raw display bytes and status nibble remain available in Home Assistant attributes for verification.

Keypad display packets do not identify their partition in the response. Vista Turbo RS232 therefore associates a `kd` response with the currently active serialized keypad query. A valid keypad display response and the following valid `08OK` are both required for a successful keypad transaction.

The panel has not been observed to stream keypad text changes unsolicited. The App uses two refresh paths instead:

```text
configured interval -> KD query -> keypad state
system event         -> short debounce -> KD query -> keypad state
```

The periodic query catches display changes caused by physical keypad interaction or other activity that may not produce a decoded system event. The event-driven refresh makes alarm, fault, bypass, trouble, and arming display changes available sooner when the panel also emits a partition event.

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

### Keypad display

Each configured keypad partition is published as one MQTT `sensor`, for example:

```text
Partition 1 Keypad
```

The sensor state is a compact representation of both display lines:

```text
P1   DISARMED | BYPAS-RDY TO ARM
```

Attributes preserve the exact two 16-character lines and keypad indicators:

```yaml
partition: 1
line_1: "P1   DISARMED   "
line_2: "BYPAS-RDY TO ARM"
display: |-
  P1   DISARMED   
  BYPAS-RDY TO ARM
ready: true
trouble: false
armed: false
backlight: true
led_status: "1"
raw_display_hex: "d0 31 ..."
updated_at: "2026-08-16T13:22:28-04:00"
```

### Zone conditions

Only zones assigned to a VISTA partition are published. Each assigned zone has four independent binary sensors:

```text
021 FRONT DOOR Fault
021 FRONT DOOR Alarm
021 FRONT DOOR Check
021 FRONT DOOR Bypass
```

These map directly to the four per-zone bits in the authoritative `49ZS` snapshot:

```text
0x1  Fault
0x2  Check
0x4  Alarm
0x8  Bypass
```

Example zone 34 with a `49ZS` value of `A`:

```text
034 MAIN BEDROOM WINDOW Fault    OFF
034 MAIN BEDROOM WINDOW Alarm    OFF
034 MAIN BEDROOM WINDOW Check    ON
034 MAIN BEDROOM WINDOW Bypass   ON
```

Each condition entity also references the common zone attribute payload containing zone number, partition, descriptor, raw status, and internal decoded flags.

The old combined zone binary sensor is removed in 0.2.4. The App clears its retained MQTT Discovery configuration when it connects so Home Assistant can remove the stale entity.

### Aggregate zone conditions

Four count sensors summarize the same snapshot-backed conditions:

```text
Fault Zones
Alarm Zones
Check Zones
Bypass Zones
```

The state is the number of matching assigned zones. Attributes include the zone number, partition, and VISTA alpha descriptor for each match.

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

The per-zone binary sensors and aggregate sensors refresh from `49ZS` during startup and periodic reconciliation. Relevant unsolicited events also update them immediately.

RF low-battery and sensor-tamper conditions are learned from unsolicited event codes rather than the `49ZS` snapshot. They are not presented as equivalent persistent zone-condition entities.

### Events

Decoded `1Bnq` events are published to:

- `vista128/event`: non-retained event stream
- `vista128/event/last`: retained event data
- `vista128/event/last_description`: retained event description

Unknown valid event codes are still published.

## Raw diagnostics

Default topics include:

- `vista128/bridge/availability`
- `vista128/panel/connected`
- `vista128/raw/frame`
- `vista128/raw/last_ascii`
- `vista128/protocol/last_message_type`
- `vista128/stats/rx_frames`
- `vista128/stats/rx_bytes`
- `vista128/stats/tx_frames`
- `vista128/stats/tx_bytes`
- `vista128/stats/invalid_frames`
- `vista128/sync/last_success`
- `vista128/sync/consecutive_failures`
- `vista128/panel/clock_offset_seconds`

The observed `69ZS` packet is validated and retained as raw data but does not update zone state. `49ZS` block reports are used for zone state.

## TransPort event receipts

When enabled, each decoded unsolicited system event is submitted as plain text to:

```text
POST http://<transport_host>:9101/print
Content-Type: text/plain
```

Startup traffic and periodic reconciliation do not print. Pending receipts are stored in `/data/vista128_print_queue.sqlite3`.

Delivery rules:

- TCP connection failure: retry later
- HTTP 204: complete
- HTTP 4xx: failed
- timeout, disconnect, or 5xx after submission starts: uncertain, no automatic replay

## Raw transmit

`debug_raw_tx_enabled` is false by default. When enabled, the bridge accepts guarded test traffic on `vista128/debug/tx`.

```json
{"confirm":"I_UNDERSTAND_RAW_PANEL_TX","ascii":"..."}
```

Raw transmit is rejected while the panel is offline or another serialized synchronization or keypad transaction is active.

## Design constraints

- The VISTA is authoritative.
- Invalid packets never change state.
- No optimistic alarm state.
- Pending panel commands are discarded on disconnect.
- Unknown valid events remain visible.
- Keypad display queries are read-only and serialized with state synchronization.
- Home Assistant is not required for VISTA alarm operation.

## Source layout

```text
bridge.py             connection and I/O orchestration
synchronizer.py       startup, periodic, and keypad protocol transactions
message_handler.py    decoded packet handling
protocol.py           packet validation, queries, and parsers
event_codes.py        VISTA event code tables
state.py              partition, keypad, and zone state
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
