# Vista Turbo HASS

Vista Turbo HASS is a local Home Assistant integration for the native RS-232 automation interface on Honeywell/Resideo VISTA Turbo alarm panels.

> **Current status:** 0.2.6-rc.1 release candidate. Read-only. Tested on a VISTA-128BPT. Keypad display polling is enabled. Arm, disarm, and keypad control commands are not sent to the panel.

## What it does

- Publishes partition state through MQTT Discovery
- Tracks assigned zones as separate **Fault, Alarm, Check, and Bypass** binary sensors
- Publishes aggregate counts for those four zone conditions
- Decodes real-time VISTA automation events
- Imports programmed zone alpha descriptors
- Reads the exact 2 x 16 partition keypad display over RS-232
- Publishes keypad Ready, Trouble, Armed, backlight, and CR-2 fire annunciator state
- Includes responsive read-only 6160CR-2 and 6160 Home Assistant dashboard cards
- Reconciles panel state periodically in case an event is missed
- Optionally prints event receipts through TransPort

The panel remains authoritative. Home Assistant is not required for normal alarm operation.

## Connection

The App talks to the VISTA through a transparent serial-to-IP server:

```text
VISTA Turbo panel
      |
    RS-232
      |
serial-to-IP server
      |
   raw TCP
      |
Vista Turbo RS232
      |
     MQTT
      |
Home Assistant
```

Development is currently using a **StarTech NETRS2321POE** in raw TCP Server mode. Lantronix UDS-series devices and equivalent transparent serial servers should also be suitable.

Serial settings are **9600 baud, 8 data bits, no parity, 1 stop bit, no flow control**.

For VISTA-128BPT wiring, panel programming, protocol details, and the TB4/J9 connection notes, see [`vista128_bridge/DOCS.md`](vista128_bridge/DOCS.md).

## Install the Home Assistant App

Add this repository to the Home Assistant App Store:

```text
https://github.com/wtc-brycel/vistaturbo-hass
```

Install **Vista Turbo RS232**, then configure the TCP address and port of the serial server. Partition 1 keypad polling is enabled by default every 7 seconds.

The App requires the Home Assistant MQTT service.

## Install the keypad card

The matching `vista-keypad-card.js` is attached to the 0.2.6-rc.1 GitHub release and is also kept in `frontend/` in this repository.

From the Home Assistant Terminal or SSH add-on:

```sh
mkdir -p /config/www
curl -fL "https://github.com/wtc-brycel/vistaturbo-hass/releases/download/v0.2.6-rc.1/vista-keypad-card.js" \
  -o /config/www/vista-keypad-card.js
```

Then add a JavaScript module resource in **Settings -> Dashboards -> Resources**:

```text
/local/vista-keypad-card.js?v=0.3.13
```

A minimal 6160CR-2 card is:

```yaml
type: custom:vista-keypad-card
entity: sensor.vista_partition_1_keypad
model: 6160cr2
```

A minimal 6160 card is:

```yaml
type: custom:vista-keypad-card
entity: sensor.vista_partition_1_keypad
model: 6160
```

`case_color: auto` is the default for both models. The default AUTO mappings are:

```text
6160CR-2: red in light mode, dark in dark mode
6160:     white in light mode, dark in dark mode
```

Day and night enclosure colors can be set independently:

```yaml
type: custom:vista-keypad-card
entity: sensor.vista_partition_1_keypad
model: 6160cr2
case_color: auto
day_case_color: red
night_case_color: dark
```

See [`frontend/README.md`](frontend/README.md) for all card options.

## Keypad display and annunciators

The Turbo RS-232 interface can return the same 32-character display shown by an alpha keypad. The App exposes that as a Home Assistant sensor while preserving both exact 16-character lines in its attributes.

Example captured from the test system:

```text
P1   DISARMED
BYPAS-RDY TO ARM
```

The keypad entity also publishes Ready, Trouble, Armed, backlight, Power, Fire Alarm, Silenced, and Supervisory state. The native KD packet supplies Ready, Trouble, and Armed directly. The additional CR-2 annunciators are reconstructed from validated VISTA events plus keypad reconciliation. Unknown reconstructed state remains `null` rather than being guessed.

## Compatibility

Only **VISTA-128BPT** has been tested. Other VISTA Turbo panels may use the same automation protocol, but they are not currently claimed as supported.

This is not intended as a general integration for non-Turbo VISTA panels.

## More information

- [`vista128_bridge/DOCS.md`](vista128_bridge/DOCS.md) - configuration, wiring, MQTT topics, and protocol behavior
- [`vista128_bridge/CHANGELOG.md`](vista128_bridge/CHANGELOG.md) - version history
- [`frontend/README.md`](frontend/README.md) - keypad card installation and configuration

## AI disclosure

This App was made with the use of AI - ChatGPT Codex, specifically - during protocol research and development. VISTA Turbo automation documentation is fragmented, and Crestron integration documentation was particularly useful in understanding parts of the interface.

The implementation has been tested against real panel traffic. Review the source before relying on it in your own installation.
