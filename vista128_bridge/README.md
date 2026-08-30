# Vista Turbo RS232

Home Assistant App for the native RS-232 automation interface on Honeywell/Resideo VISTA Turbo alarm panels.

> **Release candidate status:** 0.2.6-rc.14 is the current release candidate. It has been developed and tested for monitoring on a VISTA-128BPT; experimental control gates default to off.

## What you get in Home Assistant

- Partition alarm state
- Exact 2 x 16 partition keypad display
- Keypad Ready, Trouble, Armed, and backlight state
- Power, Fire Alarm, Silenced, Supervisory, Burglary Alarm, Auxiliary Alarm, and normalized sound-mode state on the keypad entity
- Centralized configurable dashboard chime-zone events
- Four binary sensors per assigned zone: **Fault, Alarm, Check, Bypass**
- Aggregate Fault Zones, Alarm Zones, Check Zones, and Bypass Zones sensors
- Programmed zone alpha descriptors
- Real-time VISTA system events
- Five-minute state reconciliation by default
- Optional TransPort event receipts
- Persistent SQLite event journal with optional historical panel event-log import

The VISTA remains authoritative. Home Assistant is a monitoring client and is not part of the panel's life-safety path.

## Connection

Vista Turbo RS232 expects a transparent TCP connection to the panel's RS-232 automation port:

```text
VISTA Turbo -> RS-232 -> serial-to-IP server -> raw TCP -> App -> MQTT -> Home Assistant
```

Use:

```text
9600 baud
8 data bits
no parity
1 stop bit
no flow control
```

The current test installation uses a **StarTech NETRS2321POE** in raw TCP Server mode. Lantronix UDS-series devices and equivalent transparent serial servers should also work.

See `DOCS.md` for VISTA-128BPT TB4/J9 wiring and panel-side details.

## Keypad polling

The VISTA Turbo automation interface can return the same 32-character text shown on an alpha keypad. Partition 1 is polled every 7 seconds by default, with an additional debounced refresh after valid partition events.

A captured response from the test panel decodes to:

```text
P1   DISARMED
BYPAS-RDY TO ARM
```

Home Assistant receives a **Partition 1 Keypad** sensor. Its attributes preserve the exact two 16-character lines plus Ready, Trouble, Armed, Power, Fire Alarm, Silenced, Supervisory, Burglary Alarm, Auxiliary Alarm, normalized sound mode, configured chime metadata, backlight, raw LED state, raw display bytes, and the last update time.

The dedicated Power, Fire Alarm, Silenced, and Supervisory attributes are reconstructed from validated VISTA real-time events plus keypad-display reconciliation. Unknown reconstructed state is published as JSON `null` rather than guessed.

Event-derived states are invalidated across a panel TCP disconnect so stale fire, supervisory, AC, burglary, or auxiliary information is not carried across a communication gap. Fresh KD and event traffic reconstructs them after reconnect. Panel-wide alarm OFF is unavailable until arming, both zone blocks, both zone-partition blocks, and all eight keypad displays are fresh. Positive alarm evidence is still published immediately, including silent and duress alarms.

## MQTT availability

Panel entities require all three conditions to be healthy:

- the Vista Turbo RS232 process is online on `bridge/availability`
- the panel TCP session is connected on `panel/connected`
- the panel security snapshot is complete on `panel/state_fresh`

Home Assistant MQTT Discovery uses `availability_mode: all` for partitions, keypad sensors, zone condition entities, and zone summaries. This prevents a stale retained panel-connected value from making entities look available after an unclean App or MQTT failure. Alarm entities use their own fail-safe availability topic: positive alarm evidence is available immediately, while incomplete/ambiguous alarm knowledge stays unavailable instead of being shown as OFF.

## Dashboard keypad card

The matching Lovelace card ships with this release as `vista-keypad-card.js`. Card `0.3.26` includes the keypad models, bounded searchable visual editors, explicit offline rendering, immediate physical-keypad-style key delivery when input is enabled, and the responsive `custom:vista-event-log-card` for the SQLite-backed recent event window.

`layout: auto` is the default. The card keeps the approved physical facsimile above 520 px card-container width and switches to a touchscreen-first compact layout at 520 px and below. `layout: physical` and `layout: compact` can force either presentation.

All three models use the same adaptive framework. The First Alert-inspired skin is horizontal when wide and portrait at the compact breakpoint. Future keypad models can declare their responsive behavior without implementing a separate mobile renderer.

The card supports red, white, and dark enclosure colors for either model. `case_color: auto` is the default. AUTO follows the Home Assistant light/dark theme and defaults to:

```text
6160CR-2: red by day, dark at night
6160:     white by day, dark at night
First Alert style: white by day, dark at night
```

Optional `day_case_color` and `night_case_color` settings can override either side of AUTO mode. See `frontend/README.md` for full card installation and configuration.

## Persistent event journal

Every decoded live system event is persisted in `/data/vista128_events.sqlite3`. The journal keeps event code, panel timestamp, partition, zone, user number, descriptor, and whether the row was observed live, in the historical panel log, or both. Repeated identical events within the same panel minute remain separate occurrences.

The App discovers an **Event Journal** sensor whose state is the total journal row count. Its attributes contain dump metadata and a bounded recent window. The complete database is not copied into Home Assistant state.

Event history and the local keypad-interaction audit contain sensitive panel/security information. The audit keeps one row per logical interaction, including its exact completed keypad command sequence; it is not mirrored into Home Assistant. `event_history_max_age_days` controls retention and defaults to 90 days. A separate internal row cap prevents unbounded database growth.

Set `event_history_startup_dump_enabled: true` to request the VISTA historical log once after successful startup synchronization. The first test release leaves this disabled by default pending physical VISTA-128BPT validation. Historical records are storage-only and do not mutate live panel state or generate chimes, alarm sounds, keypad refreshes, or printer receipts.

## Zone state

Each assigned zone is exposed as four independent binary sensors. For example:

```text
021 FRONT DOOR Fault
021 FRONT DOOR Alarm
021 FRONT DOOR Check
021 FRONT DOOR Bypass
```

These come from the VISTA `49ZS` status bits:

```text
0x1  Fault
0x2  Check
0x4  Alarm
0x8  Bypass
```

RF low-battery and sensor-tamper events are not part of that authoritative snapshot and are not presented as equivalent persistent zone-condition entities.

## Configuration

The Home Assistant Options editor is intentionally limited to deployment choices and user-facing features. Protocol timing, reconnect backoff, synchronization pacing, MQTT queue sizing, verification delays, database row caps, and print retry behavior use supported internal defaults instead of being exposed as tuning knobs.

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
# Optional; defaults to 90 when unset.
event_history_max_age_days: 90

transport_print_enabled: false
transport_host: ""
transport_http_port: 9101
transport_print_width: 32

raw_logging: false
debug_raw_tx_enabled: false
```

`raw_mqtt_enabled` remains available as an optional diagnostic setting but is omitted from defaults so older installations that predate it can save configuration without a missing-option failure.

`keypad_partitions` accepts a comma-separated partition list such as `"1"` or `"1,2"`. `chime_zones` accepts comma-separated zone numbers and ascending ranges such as `"1,2,5-8,27"`; listed zones chime only on a new fault transition while the resolved partition is known to be disarmed.

The MQTT disconnected-QoS queue and in-flight window are bounded internally. Publish overflow is reported rather than retried through an unbounded application queue.

See `DOCS.md` for runtime defaults, optional MQTT security/namespace overrides, and protocol details.

## Compatibility

Only **VISTA-128BPT** is currently tested. Other VISTA Turbo models are not yet claimed as supported. This App is not intended as a general integration for non-Turbo VISTA panels.

## AI disclosure

This App was made with the use of AI - ChatGPT Codex, specifically - during protocol research and development. VISTA Turbo automation documentation is fragmented, and Crestron integration documentation was particularly useful in understanding parts of the interface.

The implementation has been tested against real panel traffic. Review the source before relying on it in your own installation.

## Experimental panel control

Panel write paths remain disabled unless the required App control toggles are explicitly enabled.

```yaml
control_enabled: true
keypad_control_enabled: true
native_alarm_control_enabled: true
```

Keypad input uses typed VISTA `KS` frames for `0-9`, `*`, and `#`. The A-D visual function keys are intentionally not transmitted as literal letters because the VISTA protocol uses those data characters for other keystroke encodings. Card `0.3.26` publishes each physical keypress immediately; there is no synthetic SEND or finish-command step.

Native Home Assistant alarm control uses the documented VISTA arm/disarm command families and Home Assistant MQTT remote-code validation. The bounded local keypad-interaction audit stores the exact completed logical command sequence, including a four-digit PIN when it is part of the command, together with actor and outcome metadata. It is not exposed as an HA entity or MQTT telemetry, and control TX payloads remain redacted from bridge logging.

The compact semantic command topic at `vista128/control/execute` accepts actions such as `arm`, `disarm`, `bypass_zones`, `quick_bypass`, `group_bypass`, `chime`, `goto_partition`, `output_control`, `system_command`, and `keypad_command`. Core arm/disarm requests use native VISTA automation only when that native operation represents the complete command; global partition and subtype-bearing commands use the serialized keypad path. Unsupported deterministic commands compile to the existing serialized keypad path. PINs must be exactly four digits and zones are normalized to exactly three digits. Semantic results omit PINs and raw sequences. The local bounded administrator audit stores one complete logical interaction with its exact sequence and normalized fields. Raw `sequence` overrides are reserved for explicit logical-keypad or interactive commands. `system_command` compiles its validated `#nn` namespace without an arbitrary raw override. `output_control` and `instant_activation` require complete menu-exit sequences, not just their `#70`/`#77` prefixes; #77 also requires an action-specific operand (for example partition(s), relay, zone list, or group) before confirmation and quit. GOTO accepts target `0` to return to the original partition. See `DOCS.md` for the request schema and parser limitations.
