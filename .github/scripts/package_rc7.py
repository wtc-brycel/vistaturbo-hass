from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text()
    if old not in text:
        raise RuntimeError(f"anchor not found in {path}: {old[:120]!r}")
    path.write_text(text.replace(old, new, 1))


# Runtime and App manifest version.
version = ROOT / "vista128_bridge/app/vista_bridge/version.py"
replace_once(version, 'VERSION = "0.2.6-rc.6"', 'VERSION = "0.2.6-rc.7"')

manifest = ROOT / "vista128_bridge/config.yaml"
replace_once(manifest, 'version: "0.2.6-rc.6"', 'version: "0.2.6-rc.7"')

# Changelog.
changelog = ROOT / "vista128_bridge/CHANGELOG.md"
text = changelog.read_text()
section = '''## 0.2.6-rc.7

- Add the first opt-in VISTA panel write path while keeping all control disabled by default.
- Add a serialized `VistaControlCoordinator` sharing the existing protocol transaction lock with synchronization and keypad polling.
- Add typed VISTA `KS` keypad commands for `0-9`, `*`, and `#`, with exact frame/checksum regression tests.
- Add typed native VISTA arm/disarm commands for Away, Home/Stay, Instant/Night, Maximum, Force Away, Force Home, and Disarm.
- Enable standard Home Assistant Away, Home, Night, and Disarm through MQTT remote-code validation when native alarm control is explicitly enabled.
- Require `08XN` Automation Interface Available before any control request can be queued and stop/discard requests on `08XF`.
- Treat `08OK` only as protocol flow-control acknowledgement and verify native alarm results with a fresh arming-status query.
- Never replay queued commands across a panel TCP reconnect; queued requests are tied to one connection generation and expire quickly.
- Reject retained MQTT control messages so broker reconnects cannot replay old keypad or alarm commands.
- Redact all control TX payloads from bridge logs and never echo alarm PINs or keypad digits in control result telemetry.
- Keep keypad code entry responsive by waiting for `08OK` per stroke and requesting a coalesced keypad refresh instead of blocking every digit on a KD transaction.
- Keep the A-D visual function keys and panic encodings unavailable through the normal RC7 keypad control path pending explicit action and hold-to-activate semantics.
- Add card `0.3.20` with an opt-in visual-editor keypad-input toggle and direct non-retained Home Assistant MQTT publishing.
- Preserve the RC6 SQLite event journal, historical event-log import, event-journal card, audio, chime, and First Alert keypad features.

'''
if section not in text:
    text = text.replace("# Changelog\n\n", "# Changelog\n\n" + section, 1)
changelog.write_text(text)

# Root README current-release/install details.
root_readme = ROOT / "README.md"
text = root_readme.read_text()
old_status = "> **Current status:** 0.2.6-rc.6 release candidate. Read-only. Tested on a VISTA-128BPT. Keypad display polling is enabled. Arm, disarm, and keypad control commands are not sent to the panel."
new_status = "> **Current status:** 0.2.6-rc.7 release candidate. Tested on a VISTA-128BPT. Monitoring remains enabled by default; experimental keypad and native alarm control are available only when explicitly enabled in the App."
if old_status not in text:
    raise RuntimeError("root README status anchor missing")
text = text.replace(old_status, new_status, 1)
text = text.replace("Includes adaptive read-only 6160CR-2, 6160, and First Alert-inspired Home Assistant dashboard cards", "Includes adaptive 6160CR-2, 6160, and First Alert-inspired Home Assistant dashboard cards")
text = text.replace("0.2.6-rc.6", "0.2.6-rc.7")
text = text.replace("0.3.19", "0.3.20")
root_readme.write_text(text)

# App README.
bridge_readme = ROOT / "vista128_bridge/README.md"
text = bridge_readme.read_text()
old_status = "> **Release candidate status:** 0.2.6-rc.6 is read-only. It has been developed and tested on a VISTA-128BPT. Keypad display polling is enabled. Arm, disarm, and keypad-control commands are not sent to the panel."
new_status = "> **Release candidate status:** 0.2.6-rc.7 adds an experimental opt-in write path. It has been developed and tested for monitoring on a VISTA-128BPT; the new keypad and native arm/disarm commands are ready for their first physical panel validation. All control gates default to off."
if old_status not in text:
    raise RuntimeError("bridge README status anchor missing")
text = text.replace(old_status, new_status, 1)
text = text.replace("The matching read-only Lovelace card ships with this release as `vista-keypad-card.js`. Card `0.3.19` includes", "The matching Lovelace card ships with this release as `vista-keypad-card.js`. Card `0.3.20` includes")
text = text.replace("The next release candidate adds a gated native write path.", "RC7 adds a gated native write path.")
config_anchor = '''keypad_event_refresh_delay_ms: 250
chime_zones: ""
'''
config_replacement = '''keypad_event_refresh_delay_ms: 250
chime_zones: ""
control_enabled: false
keypad_control_enabled: false
native_alarm_control_enabled: false
'''
if config_anchor not in text:
    raise RuntimeError("bridge README config anchor missing")
text = text.replace(config_anchor, config_replacement, 1)
bridge_readme.write_text(text)

# Operator docs.
docs = ROOT / "vista128_bridge/DOCS.md"
text = docs.read_text()
config_anchor = '''chime_zones: ""
event_history_enabled: true
'''
config_replacement = '''chime_zones: ""
control_enabled: false
keypad_control_enabled: false
native_alarm_control_enabled: false
control_response_timeout_seconds: 3
control_verify_delay_ms: 400
event_history_enabled: true
'''
if config_anchor not in text:
    raise RuntimeError("DOCS control config anchor missing")
text = text.replace(config_anchor, config_replacement, 1)
section_anchor = "## Event journal and historical panel log\n"
control_section = '''## Experimental keypad and native alarm control

RC7 contains the first panel write path, but it remains disabled by default. Enabling one feature requires the global gate plus that feature gate:

```yaml
control_enabled: true
keypad_control_enabled: true
native_alarm_control_enabled: true
```

`keypad_control_enabled` permits only ordinary `0-9`, `*`, and `#` keypad strokes. A-D function buttons and panic encodings are not exposed through the normal RC7 command topic. The browser publishes each keypad stroke as a non-retained MQTT command. The bridge rejects retained control messages and ties queued commands to one panel TCP session so a reconnect cannot replay a stale key or alarm request.

`native_alarm_control_enabled` adds Home Assistant Away, Home/Stay, Night/Instant, and Disarm actions to the MQTT alarm-control-panel entity. Home Assistant uses remote-code validation and passes the entered four-digit code to the bridge for the native VISTA command. The code is never stored in MQTT discovery, written to bridge logs, or included in control-result telemetry. Control TX ASCII and hex payloads are redacted from the bridge log.

Every control transaction shares the same serialization lock used by state synchronization. The bridge requires the panel to have reported `08XN` Communication On / Automation Interface Available. `08XF` immediately blocks new control and discards queued requests. `08OK` is treated as flow-control acknowledgement only. Native arm/disarm is followed by a fresh arming-status query and compared with the requested mode.

Keypad strokes do not perform a blocking KD query after every digit. After `08OK`, the normal keypad-refresh path is requested so rapid code entry stays responsive while the display catches up asynchronously.

`control_response_timeout_seconds` defaults to 3. `control_verify_delay_ms` defaults to 400 and applies to native alarm verification.

'''
if section_anchor not in text:
    raise RuntimeError("DOCS event section anchor missing")
text = text.replace(section_anchor, control_section + section_anchor, 1)
docs.write_text(text)

# Frontend README current install/control language.
front_readme = ROOT / "frontend/README.md"
text = front_readme.read_text()
text = text.replace("The card is **read-only** while Vista Turbo RS232 remains read-only. Keys depress visually, but no panel command is sent.", "The card remains read-only by default. Card `0.3.20` can send ordinary keypad input only when bridge control is explicitly enabled and **Keypad input** is enabled in the card editor.")
text = text.replace("Release `v0.2.6-rc.5` attaches card `0.3.18` as `vista-keypad-card.js`.", "Release `v0.2.6-rc.7` attaches card `0.3.20` as `vista-keypad-card.js`.")
text = text.replace("v0.2.6-rc.6/vista-keypad-card.js", "v0.2.6-rc.7/vista-keypad-card.js")
text = text.replace("/local/vista-keypad-card.js?v=0.3.19", "/local/vista-keypad-card.js?v=0.3.20")
text = text.replace("The RC5 release also attaches `vista-keypad-simulator.html`.", "The RC7 release also attaches `vista-keypad-simulator.html`.")
text = text.replace("Card `0.3.18` implements Home Assistant's custom-card visual editor contract", "Card `0.3.20` implements Home Assistant's custom-card visual editor contract")
text = text.replace("The visual editor intentionally keeps the bridge read-only. Advanced indicator/flashing entity mappings", "The visual editor includes an opt-in **Keypad input** toggle; the bridge-side control gates must also be enabled. Advanced indicator/flashing entity mappings")
text = text.replace("Card `0.3.18` includes the model-agnostic adaptive layout system", "Card `0.3.20` includes the model-agnostic adaptive layout system")
front_readme.write_text(text)

# Simulator version label. It still defaults to read-only simulation.
simulator = ROOT / "frontend/vista-keypad-simulator.html"
text = simulator.read_text()
text = text.replace("Vista Keypad 0.3.17 simulator", "Vista Keypad 0.3.20 simulator")
simulator.write_text(text)

# Release notes.
notes = ROOT / "release/0.2.6-rc.7.md"
notes.write_text('''# Vista Turbo RS232 0.2.6 RC7

RC7 is the first experimental panel-control release. The monitor, SQLite event journal, historical event-log import, keypad display, audio/chime, and event-journal features from RC6 remain intact. The new write path is disabled by default and is ready for its first physical VISTA-128BPT validation.

## Safe defaults

Installing RC7 does not enable panel control. The new App options default to:

```yaml
control_enabled: false
keypad_control_enabled: false
native_alarm_control_enabled: false
control_response_timeout_seconds: 3
control_verify_delay_ms: 400
```

Enable only the functions you intend to test.

## Virtual keypad input

Card `0.3.20` can publish ordinary keypad keys when both bridge keypad control and the card's **Keypad input** option are enabled. RC7 sends only:

```text
0 1 2 3 4 5 6 7 8 9 * #
```

The A-D visual function keys remain intentionally inert. Although the low-level protocol parser knows the documented panic encodings, RC7 does not expose them through the normal keypad control topic.

Each stroke is converted to a typed VISTA `KS` frame and waits for the panel's `08OK` before the next queued request proceeds. A keypad display refresh is requested asynchronously instead of blocking every code digit on a full KD transaction.

## Native Home Assistant arm/disarm

When native alarm control is enabled, the MQTT alarm-control-panel entity exposes standard Home Assistant actions:

- Arm Away -> native VISTA Away
- Arm Home -> native VISTA Home/Stay
- Arm Night -> native VISTA Instant
- Disarm -> native VISTA Disarm

Home Assistant uses remote-code validation, so the four-digit VISTA user code is entered at action time and passed to the panel. It is not stored in discovery configuration. Bridge control TX logging is redacted, and PINs are never included in result or rejection telemetry.

The typed protocol layer also implements Maximum, Force Away, and Force Home for future UI/service exposure, but RC7 does not add those modes to the standard Home Assistant alarm card.

## Transaction safety

- All writes share the same serialized protocol lock as synchronization.
- Control is unavailable until the panel reports `08XN` Communication On.
- `08XF` Communication Off immediately blocks control and discards queued requests.
- `08OK` is treated as flow-control acknowledgement, not proof that an arm/disarm succeeded.
- Native arm/disarm is followed by a fresh arming-status request and mode comparison.
- Requests belong to one TCP session and are discarded on reconnect.
- Retained MQTT control messages are rejected, preventing broker reconnect replay.
- Queued requests expire rather than executing after a long synchronization delay.
- Malformed keypad payloads are rejected without echoing their contents.

## Frontend

Replace the JavaScript asset and use:

```text
/local/vista-keypad-card.js?v=0.3.20
```

The visual editor now contains **Enable keypad input**. That card-side switch cannot bypass the bridge-side App gates.

## First physical tests

This release has automated protocol framing, transaction, MQTT, reconnect, credential-redaction, and Chromium coverage. The actual VISTA-128BPT write commands have not yet been exercised against the project panel. Start with a benign keypad `*`/status interaction before entering a user code, then test Home/Stay and Disarm before moving to Away/Night.

The historical `LD` import remains independently controlled by `event_history_startup_dump_enabled`, which still defaults to `false`.
''')
