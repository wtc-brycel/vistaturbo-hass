# Vista Turbo RS232

Home Assistant App for the native RS-232 automation interface on Honeywell/Resideo VISTA Turbo alarm panels.

> **Release candidate status:** 0.2.6-rc.3 is read-only. It has been developed and tested on a VISTA-128BPT. Keypad display polling is enabled. Arm, disarm, and keypad-control commands are not sent to the panel.

## What you get in Home Assistant

- Partition alarm state
- Exact 2 x 16 partition keypad display
- Keypad Ready, Trouble, Armed, and backlight state
- 6160CR-2 Power, Fire Alarm, Silenced, and Supervisory annunciator state on the keypad entity
- Four binary sensors per assigned zone: **Fault, Alarm, Check, Bypass**
- Aggregate Fault Zones, Alarm Zones, Check Zones, and Bypass Zones sensors
- Programmed zone alpha descriptors
- Real-time VISTA system events
- Five-minute state reconciliation by default
- Optional TransPort event receipts

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

Home Assistant receives a **Partition 1 Keypad** sensor. Its attributes preserve the exact two 16-character lines plus Ready, Trouble, Armed, Power, Fire Alarm, Silenced, Supervisory, backlight, raw LED state, raw display bytes, and the last update time.

The dedicated Power, Fire Alarm, Silenced, and Supervisory attributes are reconstructed from validated VISTA real-time events plus keypad-display reconciliation. Unknown reconstructed state is published as JSON `null` rather than guessed.

Event-derived CR-2 states are invalidated across a panel TCP disconnect so stale fire, supervisory, or AC information is not carried across a communication gap. Fresh KD and event traffic reconstructs them after reconnect.

## MQTT availability

Panel entities require both conditions to be healthy:

- the Vista Turbo RS232 process is online on `bridge/availability`
- the panel TCP session is connected on `panel/connected`

Home Assistant MQTT Discovery uses `availability_mode: all` for partitions, keypad sensors, zone condition entities, and zone summaries. This prevents a stale retained panel-connected value from making entities look available after an unclean App or MQTT failure.

## Dashboard keypad card

The matching read-only 6160CR-2 and 6160 Lovelace card ships with this release as `vista-keypad-card.js`. Card `0.3.15` adds the adaptive layout used for mobile and narrow Home Assistant dashboards.

`layout: auto` is the default. The card keeps the approved physical facsimile above 520 px card-container width and switches to a touchscreen-first compact layout at 520 px and below. `layout: physical` and `layout: compact` can force either presentation.

Both models use the same adaptive framework, and future keypad models can declare their compact annunciators and function-key labels in `MODEL_PROFILES` without implementing a new mobile renderer.

The card supports red, white, and dark enclosure colors for either model. `case_color: auto` is the default. AUTO follows the Home Assistant light/dark theme and defaults to:

```text
6160CR-2: red by day, dark at night
6160:     white by day, dark at night
```

Optional `day_case_color` and `night_case_color` settings can override either side of AUTO mode. See `frontend/README.md` for full card installation and configuration.

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
```

Full configuration and MQTT details are in `DOCS.md`.

## Compatibility

Only **VISTA-128BPT** is currently tested. Other VISTA Turbo models are not yet claimed as supported. This App is not intended as a general integration for non-Turbo VISTA panels.

## AI disclosure

This App was made with the use of AI - ChatGPT Codex, specifically - during protocol research and development. VISTA Turbo automation documentation is fragmented, and Crestron integration documentation was particularly useful in understanding parts of the interface.

The implementation has been tested against real panel traffic. Review the source before relying on it in your own installation.
