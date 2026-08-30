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

The Home Assistant Options editor intentionally exposes deployment choices and user-facing features rather than every runtime constant. Normal installations should only need the panel connection, partitions, desired control surfaces, and any optional features in use.

Default options:

```yaml
panel_host: 10.2.2.141
panel_port: 10001
panel_timezone: America/New_York
keypad_partitions: "1"

control_enabled: false
keypad_control_enabled: false
native_alarm_control_enabled: false
chime_zones: ""

event_history_startup_dump_enabled: false

transport_print_enabled: false
transport_host: ""
transport_http_port: 9101
transport_print_width: 32

raw_logging: false
debug_raw_tx_enabled: false
```

The editor also supports these optional settings without requiring them to exist in older installations:

```yaml
event_history_max_age_days: 90
mqtt_base_topic: vista128
mqtt_discovery_prefix: homeassistant
mqtt_tls_enabled: false
mqtt_tls_ca: ""
mqtt_tls_client_cert: ""
mqtt_tls_client_key: ""
raw_mqtt_enabled: false
```

`panel_host` is the IP address or resolvable hostname of the serial-to-IP device. `panel_port` is its raw TCP listener.

`keypad_partitions` is a comma-separated list of partitions whose keypad display should be queried, for example `"1"` or `"1,2"`. A real keypad should exist on each queried partition. Partition 1 is the default.

`chime_zones` is Vista Turbo RS232's centralized dashboard-chime policy. Supply comma-separated VISTA zone numbers and ascending ranges, for example `"1,2,5-8,27"`. Valid zones are 1 through 128. An empty string disables bridge-generated chime events. A listed zone increments `chime_sequence` only for a new false-to-faulted `F5` transition after arming state is initialized and while the resolved partition is disarmed. Duplicate fault reports and faults while armed do not chime.

### Internal operating defaults

Protocol timing and bounded-resource controls are intentionally not user-facing. The supported runtime defaults are:

- TCP connect timeout: 5 seconds
- reconnect backoff: 1 to 30 seconds
- serial idle-frame flush: 250 ms
- MQTT disconnected queue: 256 messages
- MQTT in-flight window: 20 messages
- startup synchronization: enabled, with 1000 ms initial delay, 500 ms command pacing, and 5 second response timeout
- periodic arming reconciliation: enabled every 300 seconds; reconnect after 3 consecutive failures
- keypad display polling: enabled every 7 seconds with a 250 ms event-refresh debounce
- control response timeout: 3 seconds; verification delay: 400 ms
- event journal: enabled, recent Home Assistant window 20 rows, keypad audit enabled, internal row cap 10000
- TransPort delivery: 5 second timeout, 10 second retry delay, internal pending queue cap 5000
- command queues: 128 normal commands and 16 guarded raw commands

These values are implementation behavior, not tuning knobs. Old stored values for removed tuning options are deleted from Supervisor configuration during startup so upgrades do not leave stale schema warnings.

### MQTT security and namespaces

The App gets broker host, port, username, and password from Home Assistant's MQTT service. `mqtt_base_topic` and `mqtt_discovery_prefix` remain optional overrides for installations that deliberately customized their MQTT namespace.

Panel TCP transport is unauthenticated plaintext. The VISTA packet checksum is error detection, not authentication. Place the serial server on an isolated security VLAN and use a firewall rule allowing only this bridge to reach its TCP port.

MQTT can remain plaintext for an isolated trusted LAN. TLS remains available with the optional settings:

```yaml
mqtt_tls_enabled: true
mqtt_tls_ca: /config/mqtt/ca.pem
# Optional mutual-TLS client credentials:
mqtt_tls_client_cert: /config/mqtt/client.pem
mqtt_tls_client_key: /config/mqtt/client.key
```

When enabled, the broker certificate is verified and TLS failures never downgrade to plaintext. The client certificate and key must be configured together. Broker ACLs are required with or without TLS. Grant normal operation topics such as `vista128/keypad/+/command` and `vista128/partition/+/command` separately from the privileged raw topic.

## Experimental keypad and native alarm control

Panel write paths remain disabled by default. Enabling a control surface requires the global gate plus the corresponding feature gate:

```yaml
control_enabled: true
keypad_control_enabled: true
native_alarm_control_enabled: true
```

`keypad_control_enabled` permits ordinary keypad interaction through the serialized logical keypad path. The bridge ties queued commands to one panel TCP session so a reconnect cannot replay a stale key or alarm request. Control transactions share the same transaction serialization used by synchronization.

The bounded local keypad-interaction audit records accepted and rejected logical interactions with actor metadata supplied by Home Assistant, partition, source, normalized action and operands when known, timestamps, outcome, and the exact completed logical keypad sequence. PINs are therefore present in this administrator-only local audit by design; they are not emitted in MQTT result telemetry, Home Assistant entities, or bridge logs. Actor metadata is attribution, not authentication, and must not replace MQTT/Home Assistant/broker access control.

`native_alarm_control_enabled` adds Home Assistant Away, Home/Stay, Night/Instant, and Disarm actions to the MQTT alarm-control-panel entity. Home Assistant uses remote-code validation and passes the entered four-digit code to the bridge for the native VISTA command. The local audit stores the exact completed logical command sequence, including that four-digit code, with actor, partition, action, and outcome metadata.

The bridge requires the panel to have reported `08XN` Communication On / Automation Interface Available. `08XF` immediately blocks new control and discards queued requests. `08OK` is treated as flow-control acknowledgement only. Native arm/disarm is followed by a fresh arming-status query and compared with the requested mode.

The compact semantic command topic at `vista128/control/execute` accepts actions including `arm`, `disarm`, `bypass_zones`, `quick_bypass`, `group_bypass`, `chime`, `goto_partition`, `output_control`, `system_command`, and `keypad_command`. PINs must be exactly four digits and zones are normalized to exactly three digits. Semantic results omit PINs and raw sequences. Raw `sequence` overrides are reserved for explicit logical-keypad or interactive commands. `system_command` compiles its validated `#nn` namespace without an arbitrary raw override. `output_control` and `instant_activation` require complete menu-exit sequences, not just their `#70`/`#77` prefixes; #77 also requires an action-specific operand before confirmation and quit. GOTO accepts target `0` to return to the original partition.

## Event journal and historical panel log

The event journal is a core feature and is enabled internally. The App stores decoded events in `/data/vista128_events.sqlite3` using SQLite WAL mode. Live `1Bnq` notifications are written immediately. The journal survives App upgrades and restarts.

The same database contains the bounded keypad-interaction audit. Because that audit contains sensitive panel security information such as completed PIN-bearing commands, protect the App data directory.

`event_history_max_age_days` controls retention and defaults to 90 days when omitted. An internal 10000-row cap prevents unbounded database growth. The Home Assistant **Event Journal** sensor mirrors only the most recent 20 rows in attributes so Recorder does not repeatedly persist the complete journal.

`event_history_startup_dump_enabled` defaults to `false`. When enabled, a successful startup synchronization is followed by the documented historical-log request:

```text
08LD00A8
```

Historical entries are decoded from `ld` packets and the transaction completes on `08lc0069`. The query uses the same serialized transaction lock as keypad and state synchronization. Historical rows are merged with matching live occurrences, and repeated identical events within one panel minute are preserved with stable occurrence numbers. Imported historical entries never call the live event state machine and therefore cannot create alarm/chime/printer/keypad side effects.

The protocol parser also recognizes `08XF` (Communication Off) and `10DC` (Display Changed). `08XF` drives the **Automation Interface Available** diagnostic. `10DC` is logged passively until it is observed and validated on the current panel.

## Automation availability and control gating

Each new panel TCP session starts with control availability unknown. An explicit `08XN` marks the automation interface available with source `explicit`. A successful control transaction may infer availability from its transaction-owned `08OK`; an `08OK` from synchronization, keypad, event-history, or otherwise unowned traffic does not. If `08XF` Communication Off is received, control is blocked for the remainder of that TCP session and pending control requests are discarded. Ordinary `08OK` replies do not override an `08XF` block. A new TCP session clears the block and begins again at unknown.

Home Assistant exposes both **Automation Interface Available** and **Automation Availability Source** diagnostics. The latter can be `unknown`, `inferred`, `explicit`, `communication_off`, or `offline`.

The keypad entity exposes both semantic `trouble` and `trouble_led_raw`. The raw value is the literal KD lamp bit from the currently displayed page. The semantic value also considers authoritative zone Check/Trouble state and validated event-derived trouble families because the VISTA rotates display pages and can report a raw TROUBLE bit of zero while another trouble page remains active.

POWER is conservative. `1B` and explicit AC-loss display text establish AC loss; `1C` establishes AC restore. A quiet KD page is not treated as positive AC evidence. After a communication gap POWER may therefore remain unknown until fresh AC evidence is received.

## Startup synchronization

A new TCP session requests:

```text
08as0064    arming status
08zs004B    zone status
08ZP008E    zone-to-partition map
08ZD009A    zone descriptors
```

`AS`, `ZS`, and `ZP` complete on `08OK`. `ZD` completes on the panel's `zd000""` terminator.

Every packet is checked against its declared length and checksum before it can change Home Assistant state. Invalid packets do not apply their payload. Because a corrupt frame could have been an unsolicited state transition, the bridge immediately marks the dynamic panel snapshot stale and schedules a debounced full resynchronization. Corruption detected while startup or programming owns the panel is deferred until recovery can run safely. A failed recovery resync forces a clean TCP reconnect.

## Periodic reconciliation

The bridge repeats only the Arming Status query every 300 seconds by default:

```text
08as0064    arming status
```

Honeywell documents the Zone Status request as an initial-synchronization operation rather than a routine polling command. After the startup snapshot, valid unsolicited `nq` System Notification events maintain zone transitions. `08zs004B` is issued again only as part of an explicit full recovery snapshot, such as after detected receive corruption, panel power-up, or program-mode exit.

After repeated failed periodic arming reconciliations, the bridge closes the panel TCP session and lets the normal reconnect path establish a clean session. A failed full recovery snapshot reconnects immediately because the bridge already knows its state is not authoritative.

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

Keypad display packets do not carry a separate transaction identifier. Vista Turbo RS232 associates a `kd` response with the one pending serialized keypad query and checks the partition marker in the display against that query. A response for another partition is ignored, so a delayed response cannot overwrite a different partition. A valid keypad display response and the following valid `08OK` are both required for a successful keypad transaction.

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
power: true
fire_alarm: false
silenced: false
supervisory: false
burglary_alarm: false
auxiliary_alarm: false
sound_mode: none
chime_sequence: 0
chime_zone: null
chime_descriptor: ""
backlight: true
led_status: "1"
updated_at: "2026-08-16T13:22:28-04:00"
```

The bridge classifies continuous keypad sound state separately from the generic partition `triggered` state. `31/32`, `41/42`, and `51/52` drive audible burglary state; `B1/B2` drive 24-hour auxiliary state. Silent alarm and duress events do not drive the burglary sound classifier. `sound_mode` is `fire`, `burglary`, `auxiliary`, `none`, or `unknown`.

Burglary and auxiliary sound state is event-derived. A panel TCP disconnect invalidates it to unknown, and the frontend stops continuous sound while the keypad entity is unavailable. A subsequent normal READY keypad display can reconcile those states false.

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

The per-zone binary sensors and aggregate sensors are initialized from `49ZS` during startup and full recovery snapshots. Relevant unsolicited events update them immediately between those snapshots.

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
- `vista128/raw/last_metadata` (retained diagnostic metadata; raw content is not retained)
- `vista128/protocol/last_message_type`
- `vista128/stats/rx_frames`
- `vista128/stats/rx_bytes`
- `vista128/stats/tx_frames`
- `vista128/stats/tx_bytes`
- `vista128/stats/invalid_frames`
- `vista128/sync/last_success`
- `vista128/sync/consecutive_failures`
- `vista128/panel/clock_offset_seconds`

When `raw_mqtt_enabled` is explicitly enabled, valid raw frames are additionally published to the non-retained `vista128/raw/frame` diagnostic topic. Raw frame logging is separately controlled by `raw_logging`, and both settings are false by default.

The observed `69ZS` packet is recognized and validated for diagnostics but does not update zone state. `49ZS` block reports are used for zone state.

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

The printer endpoint is trusted-network-only unless the configured endpoint genuinely provides authenticated TLS. An unauthenticated HTTP response confirms only the endpoint response, not end-to-end physical printing. The pending spool is internally bounded at 5000 jobs; terminal completed, failed, and uncertain spool records are capped without deleting pending work.

## Raw transmit

`debug_raw_tx_enabled` is false by default. When enabled, the bridge accepts privileged administrative test traffic on `vista128/admin/raw_tx`.

```json
{"ascii":"..."}
```

The topic is intentionally separate from normal Home Assistant/keypad operation so broker ACLs can deny raw transmit to ordinary automation users. The bridge validates ASCII or hex encoding, limits payloads to 512 bytes, uses a bounded low-priority raw queue, and cannot starve synchronization/control traffic. Raw MQTT frame publication and raw payload logging are both off by default; opt-in diagnostics prefer message type, length, validity, checksum status, and timestamps and do not retain raw ASCII.

## Design constraints

- The VISTA is authoritative.
- Invalid packets never apply their payload and immediately invalidate dynamic-state freshness.
- Zone Status is startup/recovery-only, not a routine polling source.
- Failed recovery snapshots force a clean reconnect.
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
