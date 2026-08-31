# Vista Turbo HASS

Home Assistant support for Honeywell/Resideo VISTA Turbo panels using the native RS-232 automation interface.

**Current release:** `0.2.6-rc.16`  
**Tested panel:** VISTA-128BPT

Vista Turbo HASS runs as a Home Assistant App, talks to the panel through a transparent serial-to-IP server, and publishes panel state to Home Assistant. Monitoring is enabled by default. Keypad and alarm control are opt-in.

## Features

- Partition and zone state through Home Assistant
- Exact 2 x 16 keypad display and annunciator state
- 6160CR-2, 6160, and First Alert-inspired dashboard keypads
- Persistent local event journal with a recent-history card
- Zone descriptors and partition mapping from the panel
- Fire, burglary, auxiliary, panic, supervisory, trouble, and bypass state where the protocol provides authoritative data
- Semantic VISTA command handling with serialized keypad fallback and local audit history
- Optional keypad sounds, haptics, chime zones, and TransPort event printing

The VISTA panel remains authoritative and continues to operate normally if Home Assistant is unavailable.

## Connection

```text
VISTA Turbo -> RS-232 -> serial-to-IP server -> Vista Turbo RS232 -> MQTT -> Home Assistant
```

Development uses a **StarTech NETRS2321POE** in raw TCP Server mode. Other transparent serial servers, including Lantronix UDS-series devices, should also work.

Serial settings:

```text
9600 baud
8 data bits
no parity
1 stop bit
no flow control
```

See [`vista128_bridge/DOCS.md`](vista128_bridge/DOCS.md) for VISTA-128BPT wiring, panel programming, MQTT topics, and protocol details.

## Install

Add this repository to the Home Assistant App Store:

```text
https://github.com/wtc-brycel/vistaturbo-hass
```

Install **Vista Turbo RS232**, then configure the serial server address and port.

The current App requires Home Assistant's MQTT service. The project is moving toward a native Home Assistant integration while keeping the App as the VISTA protocol engine.

## Keypad card

The matching `vista-keypad-card.js` is attached to each release.

For RC16:

```sh
mkdir -p /config/www
curl -fL "https://github.com/wtc-brycel/vistaturbo-hass/releases/download/v0.2.6-rc.16/vista-keypad-card.js" \
  -o /config/www/vista-keypad-card.js
```

Add it as a JavaScript module under **Settings -> Dashboards -> Resources**:

```text
/local/vista-keypad-card.js?v=0.3.26
```

After the resource is installed, add and configure the keypad card through the Home Assistant dashboard UI.

See [`frontend/README.md`](frontend/README.md) for card installation and configuration details.

## Control

Panel writes are disabled by default. Keypad control and native alarm control must be explicitly enabled in the App.

The bridge supports normal alarm operations plus a semantic VISTA command layer for functions that require keypad emulation. Commands are serialized against panel traffic and recorded in a bounded local audit journal.

Raw serial transmission remains a separate administrative/debug feature and is not used for normal Home Assistant control.

## Compatibility

Only **VISTA-128BPT** has been physically tested so far. Other VISTA Turbo panels may share the same automation protocol, but they are not currently claimed as supported.

This project is not intended for non-Turbo VISTA panels that lack the supported RS-232 automation interface.

## Documentation

- [`vista128_bridge/DOCS.md`](vista128_bridge/DOCS.md) - installation, wiring, configuration, MQTT, and protocol notes
- [`frontend/README.md`](frontend/README.md) - keypad and event-journal cards
- [`vista128_bridge/CHANGELOG.md`](vista128_bridge/CHANGELOG.md) - release history
- [`docs/architecture/0001-home-assistant-native-suite.md`](docs/architecture/0001-home-assistant-native-suite.md) - planned Home Assistant-native architecture

## AI disclosure

ChatGPT Codex has been used during development, testing, and protocol research. VISTA Turbo automation documentation is fragmented, so implementations are validated against available Honeywell/Resideo documentation and the physical test panel where possible.
