# Vista Turbo RS232

Home Assistant App for the native RS-232 automation interface on Honeywell/Resideo VISTA Turbo alarm panels.

> **Release candidate status:** 0.2.6-rc.7 adds an experimental opt-in write path. It has been developed and tested for monitoring on a VISTA-128BPT; the new keypad and native arm/disarm commands are ready for their first physical panel validation. All control gates default to off.

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

Event-derived states are invalidated across a panel TCP disconnect so stale fire, supervisory, AC, burglary, or auxiliary information is not carried across a communication gap. Fresh KD and event traffic reconstructs them after reconnect.

## MQTT availability

Panel entities require both conditions to be healthy:

- the Vista Turbo RS232 process is online on `bridge/availability`
- the panel TCP session is connected on `panel/connected`

Home Assistant MQTT Discovery uses `availability_mode: all` for partitions, keypad sensors, zone condition entities, and zone summaries. This prevents a stale retained panel-connected value from making entities look available after an unclean App or MQTT failure.

## Dashboard keypad card

The matching Lovelace card ships with this release as `vista-keypad-card.js`. Card `0.3.20` includes the keypad models and visual editor from 0.3.18 plus the responsive `custom:vista-event-log-card` for the SQLite-backed recent event window.

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

When `event_history_enabled` is true, every decoded live system event is persisted in `/data/vista128_events.sqlite3`. The journal keeps event code, panel timestamp, partition, zone, user number, descriptor, and whether the row was observed live, in the historical panel log, or both. Repeated identical events within the same panel minute remain separate occurrences.

The App discovers an **Event Journal** sensor whose state is the total journal row count. Its attributes contain dump metadata and only the configured recent window. The complete database is not copied into Home Assistant state.

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

The main settings are the serial server address and TCP port. Keypad polling defaults are:

```yaml
keypad_display_enabled: true
keypad_partitions: "1"
keypad_poll_interval_seconds: 7
keypad_event_refresh_delay_ms: 250
chime_zones: ""
control_enabled: false
keypad_control_enabled: false
native_alarm_control_enabled: false
```

`chime_zones` is the bridge-owned dashboard chime policy, independent of ECP keypad programming. It accepts comma-separated zone numbers and ascending ranges such as `"1,2,5-8,27"`. Listed zones chime only on a new fault transition while the resolved partition is known to be disarmed.

Full configuration and MQTT details are in `DOCS.md`.

## Compatibility

Only **VISTA-128BPT** is currently tested. Other VISTA Turbo models are not yet claimed as supported. This App is not intended as a general integration for non-Turbo VISTA panels.

## AI disclosure

This App was made with the use of AI - ChatGPT Codex, specifically - during protocol research and development. VISTA Turbo automation documentation is fragmented, and Crestron integration documentation was particularly useful in understanding parts of the interface.

The implementation has been tested against real panel traffic. Review the source before relying on it in your own installation.


## Experimental panel control

RC7 adds a gated native write path. Control remains disabled unless all required App toggles are explicitly enabled.

```yaml
control_enabled: true
keypad_control_enabled: true
native_alarm_control_enabled: true
```

Keypad input uses typed VISTA `KS` frames for `0-9`, `*`, and `#`. The A-D visual function keys are intentionally not transmitted as literal letters because the VISTA protocol uses those data characters for other keystroke encodings.

Native Home Assistant alarm control uses the documented VISTA arm/disarm command families and Home Assistant MQTT remote-code validation. PIN values are never retained, written to App logs, or echoed in control telemetry. Control TX payloads are redacted from bridge logging.
