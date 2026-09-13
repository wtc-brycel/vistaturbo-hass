# Vista Turbo HASS

Vista Turbo HASS is a local Home Assistant integration for the native RS-232 automation interface on Honeywell/Resideo VISTA Turbo alarm panels.

> **Current status:** `0.2.6-rc.27`. Tested on a VISTA-128BPT. Monitoring is enabled by default. Keypad and native alarm control remain opt-in.

## Highlights

- Publishes partition, zone, alarm, keypad, and diagnostic state through MQTT Discovery
- Tracks assigned zones as separate Fault, Alarm, Check, and Bypass binary sensors
- Decodes real-time VISTA automation events and programmed zone alpha descriptors
- Reads the exact 2 x 16 partition keypad display over RS-232
- Publishes Ready, Trouble, Armed, backlight, CR-2 annunciators, and alarm state
- Includes adaptive 6160CR-2, 6160, and First Alert-inspired Home Assistant keypad cards
- Supports optional keypad audio, haptics, and configured dashboard chimes
- Maintains a persistent SQLite event journal with optional historical-log import support
- Reconciles panel state without replacing live VISTA event updates with routine full polling
- Provides semantic command execution, serialized panel transactions, verification, and bounded local audit
- Includes fail-safe alarm aggregation, state-freshness handling, bounded queues, and privileged diagnostics
- Optionally prints event receipts through TransPort

The panel remains authoritative. Home Assistant is not required for normal alarm operation.

## Connection

Vista Turbo RS232 talks to the panel through a serial-to-IP server.

```text
VISTA Turbo panel
      |
    RS-232
      |
serial-to-IP server
      |
      +-- raw TCP ---------------------------+
      |                                      |
      +-- Telnet + BINARY + RFC2217 --------+
                                             |
                                   Vista Turbo RS232
                                             |
                                            MQTT
                                             |
                                      Home Assistant
```

Serial settings are **9600 baud, 8 data bits, no parity, 1 stop bit, no flow control**.

### Confirmed transport modes

**Raw TCP**

Tested with a StarTech NETRS2321POE in transparent TCP Server mode. Other transparent serial servers should work when they pass the serial byte stream without modification.

**Lantronix Telnet / RFC2217**

Tested successfully with a Lantronix configuration used through Com Port Redirector (CPR). Vista Turbo automatically detects Telnet control traffic and negotiates the transport required for a transparent serial stream:

1. Telnet control negotiation
2. BINARY mode in both directions
3. RFC2217 `COM-PORT-OPTION` when supported
4. Remote serial configuration at 9600/8N1 with no flow control
5. VISTA RS-232 protocol traffic

No special Home Assistant option is required. Raw TCP behavior is unchanged when no Telnet control traffic is present.

For VISTA-128BPT wiring, panel programming, protocol details, and TB4/J9 connection notes, see [`vista128_bridge/DOCS.md`](vista128_bridge/DOCS.md).

## State synchronization

A new panel session performs the authoritative startup snapshot: arming status, Zone Status, zone-to-partition mapping, and zone descriptors. Routine reconciliation polls arming status only. Valid unsolicited `nq` System Notification events maintain zone transitions between full snapshots.

Invalid panel frames mark the current snapshot stale and schedule one full recovery synchronization. If recovery itself fails, the bridge reconnects and establishes a clean session.

## Control and safety

Panel control is disabled unless explicitly enabled in the App.

Normal keypad control supports `0-9`, `*`, and `#`. Native alarm control and semantic command execution share the same serialized transaction coordinator used by synchronization and keypad polling.

Vista Turbo includes a **non-configurable installer-programming safety interlock**. The bridge blocks keypad sequences matching any four numeric digits followed by `800` before the triggering frame can reach the panel. This covers VISTA-20P-style `code + 800` and stops Turbo `code + 8000` before programming entry.

The interlock applies to individual keypresses, multi-key transactions, semantic keypad fallback, and privileged raw `KS` transmission. The four-digit code is never logged by the safety interlock. Installer programming remains available from a physical keypad.

`08XF` is treated as Home/Facility Automation Communication Off, not automatically as installer programming. While communication is suspended, panel state is marked stale and automation traffic is quiesced until communication returns and a full resynchronization succeeds.

## Home Assistant architecture

The App remains the sole VISTA protocol and domain engine. The accepted long-term architecture adds a companion `custom_components/vistaturbo` integration as the primary Home Assistant-facing layer and a Supervisor ingress application for authenticated alarm-system management.

MQTT remains supported during migration. New VISTA protocol logic belongs in the App rather than being duplicated in Home Assistant integration code.

See [`docs/architecture/0001-home-assistant-native-suite.md`](docs/architecture/0001-home-assistant-native-suite.md) for the accepted architecture and security boundaries.

## Install the Home Assistant App

Add this repository to the Home Assistant App Store:

```text
https://github.com/wtc-brycel/vistaturbo-hass
```

Install or update **Vista Turbo RS232** to `0.2.6-rc.27`, then configure the TCP address and port of the serial server.

Partition 1 keypad polling is enabled by default every 7 seconds. The current App release requires the Home Assistant MQTT service.

## Install the keypad card

The current keypad card is `0.3.26`. `vista-keypad-card.js` is attached to the RC27 GitHub release and is also kept in `frontend/`.

From the Home Assistant Terminal or SSH App:

```sh
mkdir -p /config/www
curl -fL "https://github.com/wtc-brycel/vistaturbo-hass/releases/download/v0.2.6-rc.27/vista-keypad-card.js" \
  -o /config/www/vista-keypad-card.js
```

Add a JavaScript module resource in **Settings -> Dashboards -> Resources**:

```text
/local/vista-keypad-card.js?v=0.3.26
```

Minimal examples:

```yaml
type: custom:vista-keypad-card
entity: sensor.vista_partition_1_keypad
model: 6160cr2
```

```yaml
type: custom:vista-keypad-card
entity: sensor.vista_partition_1_keypad
model: 6160
```

```yaml
type: custom:vista-keypad-card
entity: sensor.vista_partition_1_keypad
model: firstalert
```

`case_color: auto` and `layout: auto` are the defaults. See [`frontend/README.md`](frontend/README.md) for card configuration.

## Keypad display and annunciators

The Turbo RS-232 interface can return the same 32-character display shown by an alpha keypad. The App preserves both exact 16-character lines and publishes keypad Ready, Trouble, Armed, backlight, Power, Fire Alarm, Silenced, Supervisory, Burglary Alarm, Auxiliary Alarm, Audible Panic Alarm, and normalized sound state where authoritative protocol evidence exists.

Unknown reconstructed state remains unknown rather than being guessed.

## Persistent event journal

Live VISTA system events are stored in `/data/vista128_events.sqlite3`. Home Assistant receives only a configurable recent window so Recorder does not need to duplicate the full journal on every update.

The frontend resource also registers `custom:vista-event-log-card` for recent event history.

Historical panel-log import remains separate from normal live startup synchronization and is not required for ordinary operation.

## Repository and release security

Normal CI is read-only and uses immutable GitHub Action commit pins. Release-candidate publication validates release metadata, waits for required checks on the exact release commit, verifies tag/release identity and asset digests, and grants repository write access only to the publication job.

Broker and network ACLs are still required. CI and release publication do not authenticate the panel transport.

## Compatibility

Only **VISTA-128BPT** is currently claimed as tested. Other VISTA Turbo panels may use the same automation protocol, but they are not yet claimed as supported.

This is not intended as a general integration for non-Turbo VISTA panels.

## More information

- [`docs/architecture/0001-home-assistant-native-suite.md`](docs/architecture/0001-home-assistant-native-suite.md) - accepted Home Assistant-native architecture
- [`vista128_bridge/DOCS.md`](vista128_bridge/DOCS.md) - configuration, wiring, MQTT topics, and protocol behavior
- [`vista128_bridge/CHANGELOG.md`](vista128_bridge/CHANGELOG.md) - version history
- [`frontend/README.md`](frontend/README.md) - keypad card installation and configuration

## AI disclosure

This App was developed with AI assistance, including ChatGPT Codex, during protocol research and implementation. VISTA Turbo automation documentation is fragmented, and Crestron integration documentation was particularly useful in understanding parts of the interface.

The implementation has been tested against real panel traffic. Review the source before relying on it in your own installation.
