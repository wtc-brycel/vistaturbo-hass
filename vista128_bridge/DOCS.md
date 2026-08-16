# Vista Turbo RS232

## Compatibility

Developed and tested against a **VISTA-128BPT**. Other VISTA Turbo models are currently untested and are not claimed as supported. This App depends on the VISTA Turbo RS-232 automation interface and should not be assumed to work with non-Turbo VISTA panels.

## Requirements

- Home Assistant OS or Supervisor
- MQTT service available to the App
- VISTA-128BPT automation serial port
- Transparent TCP serial server

Serial settings:

```text
RS-232
9600 baud
8 data bits
no parity
1 stop bit
no flow control
TCP server mode
```

The StarTech NETRS2321POE is known to work when configured as a raw TCP server. Do not use its COM Port/RFC2217 mode.

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
