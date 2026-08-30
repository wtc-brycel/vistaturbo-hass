# Vista Turbo HASS

Vista Turbo HASS is a local Home Assistant integration for the native RS-232 automation interface on Honeywell/Resideo VISTA Turbo alarm panels.

> **Current status:** 0.2.6-rc.14 release candidate. Tested on a VISTA-128BPT. Monitoring remains enabled by default; experimental keypad and native alarm control are available only when explicitly enabled in the App.

## What it does

- Publishes partition state through MQTT Discovery
- Tracks assigned zones as separate **Fault, Alarm, Check, and Bypass** binary sensors
- Publishes aggregate counts for those four zone conditions
- Decodes real-time VISTA automation events
- Imports programmed zone alpha descriptors
- Reads the exact 2 x 16 partition keypad display over RS-232
- Publishes keypad Ready, Trouble, Armed, backlight, and CR-2 annunciator state
- Includes adaptive 6160CR-2, 6160, and First Alert-inspired Home Assistant dashboard cards
- Supports optional low-latency keypad chirps, alarm/chime sounds, and browser haptics
- Includes a Home Assistant visual card editor for common keypad, appearance, sound, haptic, and function-key settings
- Supports a centralized configurable dashboard chime-zone list
- Maintains a persistent SQLite event journal from live panel events, with optional historical panel-log import
- Includes a responsive Home Assistant event-journal card for recent panel history
- Reconciles arming state periodically while live System Notification events maintain zone changes
- Uses full Zone Status snapshots only for startup and explicit recovery, not routine polling
- Provides a canonical `VistaCommand` semantic command model with serialized execution, verification, and bounded local audit
- Distinguishes auxiliary, burglary, audible panic, silent, duress, fire, and supervisory alarm evidence where authoritative protocol semantics exist
- Optionally prints event receipts through TransPort
- Fail-safe panel-wide alarm aggregation and explicit state-freshness availability
- Bounded event retention, control queues, and privileged raw diagnostics

The panel remains authoritative. Home Assistant is not required for normal alarm operation.

## Connection

The current release talks to the VISTA through a transparent serial-to-IP server and publishes Home Assistant state through MQTT:

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

## State synchronization

A normal new panel TCP session performs the authoritative startup snapshot: arming status, Zone Status, zone-to-partition mapping, and zone descriptors. Honeywell documents Zone Status as an initial-synchronization request rather than a routine polling command, so the normal periodic reconciliation sends only the arming-status query. Valid unsolicited `nq` System Notification events maintain zone transitions between full snapshots.

A detected invalid panel frame is treated as possible lost state. The bridge immediately marks panel state stale, invalidates the Zone Status portion of the authoritative snapshot, and schedules one debounced full resynchronization. If corruption is detected while startup or programming already owns the panel, recovery is deferred until that operation can safely finish. If the recovery snapshot itself fails, the bridge forces a TCP reconnect so a new session can establish clean state.

`startup_sync_enabled` should remain enabled for normal operation. Disabling startup synchronization intentionally prevents the bridge from establishing its complete authoritative zone/partition snapshot on a new session.

## Accepted Home Assistant architecture

The long-term product architecture is now explicitly Home Assistant-native. The existing App remains the sole VISTA protocol/domain engine. A companion `custom_components/vistaturbo` integration will become the primary Home Assistant-facing layer using native entities, actions, Home Assistant identity/permissions, Repairs, diagnostics, and a push-first private App API/WebSocket. A Supervisor ingress application will provide the authenticated alarm-system management console, beginning with panel user management and expanding deliberately into other supported administration.

MQTT remains supported during migration, but is now compatibility infrastructure rather than the permanent architectural contract for new functionality. New VISTA protocol logic belongs only in the App; Home Assistant integration code consumes semantic bridge APIs and must not duplicate panel byte/protocol behavior.

The complete accepted decision, security boundaries, identity/credential rules, entity-model rules, management-console scope, roadmap tracks, and PR-review invariants are recorded in [`docs/architecture/0001-home-assistant-native-suite.md`](docs/architecture/0001-home-assistant-native-suite.md).

## Repository and release security

The production add-on image is built from the Home Assistant base `3.24` multi-architecture image pinned by digest in `vista128_bridge/Dockerfile`. The bridge's Python dependency is hash-checked, and frontend browser tests use the locked Playwright `1.62.1` release.

Normal CI is explicitly read-only and uses immutable GitHub Action commit pins. Release-candidate publication validates `release/rc.json`, waits for the required checks on the exact release commit, verifies tag/release identity and asset digests, and grants repository write access only to the final publication job. See [`docs/security/historical-actions-audit.md`](docs/security/historical-actions-audit.md) for the historical Actions audit and its threat-model conclusion.

The release workflow and its metadata are intended for repository maintainers. Broker/repository ACLs remain required; a successful CI or release publication does not authenticate the panel transport.

## Install the Home Assistant App

Add this repository to the Home Assistant App Store:

```text
https://github.com/wtc-brycel/vistaturbo-hass
```

Install or update **Vista Turbo RS232** to `0.2.6-rc.14`, then configure the TCP address and port of the serial server. Partition 1 keypad polling is enabled by default every 7 seconds.

The current App release requires the Home Assistant MQTT service. The accepted native-integration architecture will remove MQTT as a required Home Assistant transport once native feature parity is sufficient.

## Install the keypad card

The matching `vista-keypad-card.js` is attached to the `v0.2.6-rc.14` GitHub release and is also kept in `frontend/` in this repository.

From the Home Assistant Terminal or SSH add-on:

```sh
mkdir -p /config/www
curl -fL "https://github.com/wtc-brycel/vistaturbo-hass/releases/download/v0.2.6-rc.14/vista-keypad-card.js" \
  -o /config/www/vista-keypad-card.js
```

Then add a JavaScript module resource in **Settings -> Dashboards -> Resources**:

```text
/local/vista-keypad-card.js?v=0.3.26
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

A First Alert-inspired card is:

```yaml
type: custom:vista-keypad-card
entity: sensor.vista_partition_1_keypad
model: firstalert
```

`case_color: auto` and `layout: auto` are the defaults for all three models.

AUTO case mappings are:

```text
6160CR-2: red in light mode, dark in dark mode
6160:     white in light mode, dark in dark mode
First Alert style: white in light mode, dark in dark mode
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

The keypad entity also publishes Ready, Trouble, Armed, backlight, Power, Fire Alarm, Silenced, Supervisory, Burglary Alarm, Auxiliary Alarm, Audible Panic Alarm, and a normalized `sound_mode`. The native KD packet supplies Ready, Trouble, and Armed directly. Supplemental states are reconstructed from validated VISTA events plus keypad reconciliation. Unknown reconstructed state remains `null` rather than being guessed.

Configured dashboard chime events are published through `chime_sequence`, `chime_zone`, `chime_descriptor`, and `chime_at`. Event-derived states are invalidated after a panel TCP gap, and panel entities require both the bridge process and panel TCP session to be available before Home Assistant shows them as available.

## Persistent event journal

Vista Turbo RS232 can preserve VISTA system events in `/data/vista128_events.sqlite3`. Live `nq` notifications are journaled as they arrive. An optional startup import can request the panel's historical event log using the documented `08LD00A8` transaction and merge `ld` records into the same database without replaying live alarm, chime, keypad-refresh, or printer side effects.

The full journal stays in SQLite. Home Assistant receives only a configurable recent window so Recorder is not forced to store the entire panel history on every sensor update. The matching frontend resource also registers `custom:vista-event-log-card` for a responsive recent-history view.

The historical startup import is disabled by default in the first test release because the `LD/ld/lc` transaction has not yet been physically validated against this VISTA-128BPT. Live SQLite journaling is enabled by default.

## Adaptive Lovelace layout

Card `0.3.18` includes the adaptive Lovelace layout system plus a native visual editor for normal card configuration.

```yaml
layout: auto
```

is the default:

- above 520 px card-container width, the approved physical keypad facsimile is shown
- at 520 px and below, the card switches to a touchscreen-first compact layout with a larger LCD, compact annunciator strip, and usable 4 x 4 touch grid
- `layout: physical` forces the facsimile
- `layout: compact` forces the touchscreen layout

The compact layout applies to the 6160CR-2, standard 6160, and First Alert-inspired model. The First Alert style uses a horizontal composition when wide and a portrait composition at the compact breakpoint. Model-specific behavior is declared through `MODEL_PROFILES`, so future keypad models can reuse the same responsive framework instead of requiring a separate mobile UI.

At narrow widths, touch targets remain approximately 50 px tall. Numeric legends are hidden below 320 px before the primary key labels are allowed to become too small.

The card also retains the mobile hardening from RC2: ResizeObserver-driven LCD redraws, pointer-cancel handling, render filtering for unrelated Home Assistant updates, and automatic light/dark case updates.

Browser regression tests now render the real custom element in Chromium and verify wide/compact switching, touch-target dimensions, model-specific annunciator counts, forced layout modes, theme-aware case colors, and the four-column Lovelace grid contract.

## Optional keypad audio and haptics

Card `0.3.17` can synthesize keypad feedback locally with Web Audio. No audio files are downloaded. Sound and haptics remain disabled unless explicitly enabled.

```yaml
sound:
  enabled: true
  keypress: true
  state_sounds: true
haptic:
  enabled: true
  keypress_ms: 10
```

The bridge classifies unsilenced fire, audible panic, burglary, and 24-hour auxiliary alarms using distinct semantic evidence. Trouble, supervisory, and configured chime events also drive one-shot keypad sounds. External Home Assistant alarm/aux entity mappings remain optional overrides rather than normal requirements.

When sound is enabled, the card uses the first pointer or keyboard interaction anywhere on the Lovelace page to unlock browser audio. A small `AUDIO` flag remains visible only while the browser still blocks playback. Haptic feedback depends on browser support and may be unavailable on iPhone.

The App-level `chime_zones` setting accepts comma-separated VISTA zones and ranges, for example `"1,2,5-8,27"`. A listed zone chimes only on a new fault transition while its partition is known to be disarmed.

## Compatibility

Only **VISTA-128BPT** has been tested. Other VISTA Turbo panels may use the same automation protocol, but they are not currently claimed as supported.

This is not intended as a general integration for non-Turbo VISTA panels.

## More information

- [`docs/architecture/0001-home-assistant-native-suite.md`](docs/architecture/0001-home-assistant-native-suite.md) - accepted Home Assistant-native product architecture
- [`vista128_bridge/DOCS.md`](vista128_bridge/DOCS.md) - configuration, wiring, MQTT topics, and protocol behavior
- [`vista128_bridge/CHANGELOG.md`](vista128_bridge/CHANGELOG.md) - version history
- [`frontend/README.md`](frontend/README.md) - keypad card installation and configuration

## AI disclosure

This App was made with the use of AI - ChatGPT Codex, specifically - during protocol research and development. VISTA Turbo automation documentation is fragmented, and Crestron integration documentation was particularly useful in understanding parts of the interface.

The implementation has been tested against real panel traffic. Review the source before relying on it in your own installation.
