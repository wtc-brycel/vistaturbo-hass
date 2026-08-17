from pathlib import Path


def replace_required(path: str, old: str, new: str, label: str, count: int = 1) -> None:
    p = Path(path)
    text = p.read_text()
    if old not in text:
        raise SystemExit(f"missing anchor: {label}")
    p.write_text(text.replace(old, new, count))


# Runtime and Home Assistant App version.
replace_required(
    "vista128_bridge/config.yaml",
    'version: "0.2.6-rc.3"',
    'version: "0.2.6-rc.4"',
    "manifest version",
)
replace_required(
    "vista128_bridge/app/vista_bridge/version.py",
    'VERSION = "0.2.6-rc.3"',
    'VERSION = "0.2.6-rc.4"',
    "runtime version",
)

# Root README release/install references and current capabilities.
p = Path("README.md")
s = p.read_text().replace("0.2.6-rc.3", "0.2.6-rc.4").replace("0.3.15", "0.3.17")
s = s.replace(
    "- Includes adaptive read-only 6160CR-2 and 6160 Home Assistant dashboard cards\n",
    "- Includes adaptive read-only 6160CR-2, 6160, and First Alert-inspired Home Assistant dashboard cards\n- Supports optional low-latency keypad chirps, alarm/chime sounds, and browser haptics\n- Supports a centralized configurable dashboard chime-zone list\n",
)
s = s.replace(
    '''A minimal 6160 card is:

```yaml
type: custom:vista-keypad-card
entity: sensor.vista_partition_1_keypad
model: 6160
```

`case_color: auto` and `layout: auto` are the defaults for both models.
''',
    '''A minimal 6160 card is:

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
''',
)
s = s.replace(
    '''6160CR-2: red in light mode, dark in dark mode
6160:     white in light mode, dark in dark mode
''',
    '''6160CR-2: red in light mode, dark in dark mode
6160:     white in light mode, dark in dark mode
First Alert style: white in light mode, dark in dark mode
''',
)
s = s.replace(
    '''The keypad entity also publishes Ready, Trouble, Armed, backlight, Power, Fire Alarm, Silenced, and Supervisory state. The native KD packet supplies Ready, Trouble, and Armed directly. The additional CR-2 annunciators are reconstructed from validated VISTA events plus keypad reconciliation. Unknown reconstructed state remains `null` rather than being guessed.

Event-derived CR-2 states are invalidated after a panel TCP gap, and panel entities require both the bridge process and panel TCP session to be available before Home Assistant shows them as available.
''',
    '''The keypad entity also publishes Ready, Trouble, Armed, backlight, Power, Fire Alarm, Silenced, Supervisory, Burglary Alarm, Auxiliary Alarm, and a normalized `sound_mode`. The native KD packet supplies Ready, Trouble, and Armed directly. Supplemental states are reconstructed from validated VISTA events plus keypad reconciliation. Unknown reconstructed state remains `null` rather than being guessed.

Configured dashboard chime events are published through `chime_sequence`, `chime_zone`, `chime_descriptor`, and `chime_at`. Event-derived states are invalidated after a panel TCP gap, and panel entities require both the bridge process and panel TCP session to be available before Home Assistant shows them as available.
''',
)
s = s.replace(
    '''The compact layout applies to both the 6160CR-2 and standard 6160. Model-specific compact behavior is declared through `MODEL_PROFILES`, so future keypad models can reuse the same responsive renderer instead of requiring a separate mobile UI.
''',
    '''The compact layout applies to the 6160CR-2, standard 6160, and First Alert-inspired model. The First Alert style uses a horizontal composition when wide and a portrait composition at the compact breakpoint. Model-specific behavior is declared through `MODEL_PROFILES`, so future keypad models can reuse the same responsive framework instead of requiring a separate mobile UI.
''',
)
compat_anchor = "## Compatibility\n"
feedback = '''## Optional keypad audio and haptics

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

The bridge classifies unsilenced fire, audible burglary, and 24-hour auxiliary alarms directly on the keypad entity. Trouble, supervisory, and configured chime events also drive one-shot keypad sounds. External Home Assistant alarm/aux entity mappings remain optional overrides rather than normal requirements.

When sound is enabled, the card uses the first pointer or keyboard interaction anywhere on the Lovelace page to unlock browser audio. A small `AUDIO` flag remains visible only while the browser still blocks playback. Haptic feedback depends on browser support and may be unavailable on iPhone.

The App-level `chime_zones` setting accepts comma-separated VISTA zones and ranges, for example `"1,2,5-8,27"`. A listed zone chimes only on a new fault transition while its partition is known to be disarmed.

'''
if compat_anchor not in s:
    raise SystemExit("missing anchor: root compatibility")
s = s.replace(compat_anchor, feedback + compat_anchor, 1)
p.write_text(s)

# Frontend README current release, First Alert, native sound plumbing, simulator.
p = Path("frontend/README.md")
s = p.read_text().replace("v0.2.6-rc.3", "v0.2.6-rc.4").replace("0.3.15", "0.3.17").replace("0.3.16", "0.3.17")
s = s.replace("Both models use the same live VISTA data.", "All three models use the same live VISTA data.")
s = s.replace("Both `6160cr2` and `6160` support the same enclosure colors:", "All three models support the same enclosure colors:")
s = s.replace("`case_color: auto` is the default for both keypad models.", "`case_color: auto` is the default for all keypad models.")
s = s.replace(
    '''| `6160cr2` | `red` | `dark` |
| `6160` | `white` | `dark` |
''',
    '''| `6160cr2` | `red` | `dark` |
| `6160` | `white` | `dark` |
| `firstalert` | `white` | `dark` |
''',
)
s = s.replace(
    '''For the standard 6160 skin:

```yaml
type: custom:vista-keypad-card
entity: sensor.vista_partition_1_keypad
model: 6160
```

## Adaptive layout
''',
    '''For the standard 6160 skin:

```yaml
type: custom:vista-keypad-card
entity: sensor.vista_partition_1_keypad
model: 6160
```

For the First Alert-inspired skin:

```yaml
type: custom:vista-keypad-card
entity: sensor.vista_partition_1_keypad
model: firstalert
```

The RC4 release also attaches `vista-keypad-simulator.html`. Place it beside the card in `/config/www` and open `/local/vista-keypad-simulator.html` to exercise all three layouts, widths, annunciators, chime/alarm states, and audio behavior without changing the real panel.

## Adaptive layout
''',
)
s = s.replace(
    '''  alarm_volume: 0.065
  alarm_entity: alarm_control_panel.your_partition
  aux_entity: binary_sensor.your_aux_alarm
haptic:
''',
    '''  alarm_volume: 0.065
haptic:
''',
)
s = s.replace(
    '''Set `alarm_entity` and `aux_entity` only when those Home Assistant entities should drive the corresponding continuous sound profiles. Do not use the example entity IDs literally.
''',
    '''The bridge publishes native `burglary_alarm`, `auxiliary_alarm`, and `sound_mode` attributes, so extra Home Assistant entities are not required for normal alarm audio. Optional `alarm_entity` and `aux_entity` mappings remain available as advanced overrides.
''',
)
s = s.replace(
    '''Continuous sound priority is unsilenced fire, then `alarm_entity`, then `aux_entity`. A silenced fire condition keeps the fire/silenced annunciators but stops the local fire tone. Trouble, supervisory, and chime are one-shot transition sounds.
''',
    '''Continuous sound priority is unsilenced fire, then audible burglary, then 24-hour auxiliary. A silenced fire condition keeps the fire/silenced annunciators but stops the local fire tone. Trouble, supervisory, and chime are one-shot transition sounds. Continuous sound stops when the keypad entity becomes unavailable.
''',
)
s = s.replace(
    '''An empty value disables bridge-generated chimes. When a configured zone produces the validated real-time `F5` Fault event, the bridge increments `chime_sequence` on the affected partition keypad entity and publishes `chime_zone`, `chime_descriptor`, and `chime_at`. Every card using that keypad entity can then react to the same authoritative chime event without maintaining a separate list.
''',
    '''An empty value disables bridge-generated chimes. A listed zone increments `chime_sequence` only when a validated `F5` event represents a new false-to-faulted transition, the partition arming state has been initialized, and that partition is disarmed. Duplicate `F5` reports and faults while armed do not chime. The keypad entity also publishes `chime_zone`, `chime_descriptor`, and `chime_at`.
''',
)
s = s.replace(
    '''- `supervisory` reconstructed from supervisory start/restore events and keypad display reconciliation
''',
    '''- `supervisory` reconstructed from supervisory start/restore events and keypad display reconciliation
- `burglary_alarm` reconstructed only from audible/perimeter/interior burglary families, not silent or duress events
- `auxiliary_alarm` reconstructed from the 24-hour auxiliary alarm family
- `sound_mode` normalized to `none`, `fire`, `burglary`, `auxiliary`, or `unknown`
''',
)
p.write_text(s)

# App README.
p = Path("vista128_bridge/README.md")
s = p.read_text().replace("0.2.6-rc.3", "0.2.6-rc.4").replace("0.3.15", "0.3.17")
s = s.replace(
    "- 6160CR-2 Power, Fire Alarm, Silenced, and Supervisory annunciator state on the keypad entity\n",
    "- Power, Fire Alarm, Silenced, Supervisory, Burglary Alarm, Auxiliary Alarm, and normalized sound-mode state on the keypad entity\n- Centralized configurable dashboard chime-zone events\n",
)
s = s.replace(
    '''Home Assistant receives a **Partition 1 Keypad** sensor. Its attributes preserve the exact two 16-character lines plus Ready, Trouble, Armed, Power, Fire Alarm, Silenced, Supervisory, backlight, raw LED state, raw display bytes, and the last update time.
''',
    '''Home Assistant receives a **Partition 1 Keypad** sensor. Its attributes preserve the exact two 16-character lines plus Ready, Trouble, Armed, Power, Fire Alarm, Silenced, Supervisory, Burglary Alarm, Auxiliary Alarm, normalized sound mode, configured chime metadata, backlight, raw LED state, raw display bytes, and the last update time.
''',
)
s = s.replace(
    '''Event-derived CR-2 states are invalidated across a panel TCP disconnect so stale fire, supervisory, or AC information is not carried across a communication gap. Fresh KD and event traffic reconstructs them after reconnect.
''',
    '''Event-derived states are invalidated across a panel TCP disconnect so stale fire, supervisory, AC, burglary, or auxiliary information is not carried across a communication gap. Fresh KD and event traffic reconstructs them after reconnect.
''',
)
s = s.replace(
    '''The matching read-only 6160CR-2 and 6160 Lovelace card ships with this release as `vista-keypad-card.js`. Card `0.3.17` adds the adaptive layout used for mobile and narrow Home Assistant dashboards.
''',
    '''The matching read-only Lovelace card ships with this release as `vista-keypad-card.js`. Card `0.3.17` supports 6160CR-2, standard 6160, and First Alert-inspired skins plus optional synthesized audio and haptics.
''',
)
s = s.replace(
    '''Both models use the same adaptive framework, and future keypad models can declare their compact annunciators and function-key labels in `MODEL_PROFILES` without implementing a new mobile renderer.
''',
    '''All three models use the same adaptive framework. The First Alert-inspired skin is horizontal when wide and portrait at the compact breakpoint. Future keypad models can declare their responsive behavior without implementing a separate mobile renderer.
''',
)
s = s.replace(
    '''6160CR-2: red by day, dark at night
6160:     white by day, dark at night
''',
    '''6160CR-2: red by day, dark at night
6160:     white by day, dark at night
First Alert style: white by day, dark at night
''',
)
s = s.replace(
    '''keypad_event_refresh_delay_ms: 250
```
''',
    '''keypad_event_refresh_delay_ms: 250
chime_zones: ""
```

`chime_zones` is the bridge-owned dashboard chime policy, independent of ECP keypad programming. It accepts comma-separated zone numbers and ascending ranges such as `"1,2,5-8,27"`. Listed zones chime only on a new fault transition while the resolved partition is known to be disarmed.
''',
    1,
)
p.write_text(s)

# Operator docs: chime semantics and keypad attributes.
p = Path("vista128_bridge/DOCS.md")
s = p.read_text()
s = s.replace(
    '''`chime_zones` is Vista Turbo RS232's own centralized dashboard-chime policy. It is intentionally separate from any chime programming transported on the VISTA ECP bus. Supply comma-separated VISTA zone numbers and ascending ranges, for example `"1,2,5-8,27"`. Valid zones are 1 through 128. An empty string disables bridge-generated chime events. When a listed zone produces the validated `F5` Fault event, the affected keypad entity increments `chime_sequence` and exposes `chime_zone`, `chime_descriptor`, and `chime_at`. The frontend can use that sequence change to play one chime without polling or subscribing to every zone entity.
''',
    '''`chime_zones` is Vista Turbo RS232's own centralized dashboard-chime policy. It is intentionally separate from any chime programming transported on the VISTA ECP bus. Supply comma-separated VISTA zone numbers and ascending ranges, for example `"1,2,5-8,27"`. Valid zones are 1 through 128. An empty string disables bridge-generated chime events. A listed zone increments `chime_sequence` only for a new false-to-faulted `F5` transition after arming state is initialized and while the resolved partition is disarmed. Duplicate fault reports and faults while armed do not chime. The keypad entity also exposes `chime_zone`, `chime_descriptor`, and `chime_at`.
''',
)
s = s.replace(
    '''ready: true
trouble: false
armed: false
backlight: true
led_status: "1"
''',
    '''ready: true
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
''',
    1,
)
zone_anchor = "### Zone conditions\n"
audible_docs = '''The bridge classifies continuous keypad sound state separately from the generic partition `triggered` state. `31/32`, `41/42`, and `51/52` drive audible burglary state; `B1/B2` drive 24-hour auxiliary state. Silent alarm and duress events do not drive the burglary sound classifier. `sound_mode` is `fire`, `burglary`, `auxiliary`, `none`, or `unknown`.

Burglary and auxiliary sound state is event-derived. A panel TCP disconnect invalidates it to unknown, and the frontend stops continuous sound while the keypad entity is unavailable. A subsequent normal READY keypad display can reconcile those states false.

'''
if zone_anchor not in s:
    raise SystemExit("missing anchor: docs zone conditions")
s = s.replace(zone_anchor, audible_docs + zone_anchor, 1)
p.write_text(s)

# Changelog.
p = Path("vista128_bridge/CHANGELOG.md")
s = p.read_text()
entry = '''## 0.2.6-rc.4

- Add card `0.3.17` with optional low-latency synthesized Web Audio keypad feedback and best-effort browser haptics.
- Add immediate keypress chirps plus chime, trouble, supervisory, fire, burglary, and auxiliary sound profiles.
- Add page-level audio unlocking and a small `AUDIO` flag while browser playback remains blocked.
- Add the First Alert-inspired keypad model with horizontal wide and portrait compact compositions.
- Add centralized App-level `chime_zones` configuration with zone/range syntax.
- Generate chimes only for new configured-zone fault transitions while the resolved partition is known to be disarmed; suppress duplicate and armed-state chimes.
- Add native `burglary_alarm`, `auxiliary_alarm`, and normalized `sound_mode` keypad attributes from validated event families.
- Keep silent alarm and duress events out of the audible burglary classifier.
- Invalidate native audible state across panel TCP gaps and stop continuous frontend audio while the keypad entity is unavailable.
- Make chime counters restart-safe so a bridge sequence reset does not replay a stale chime.
- Add checked-in browser audio tests and expand Chromium coverage to all three keypad styles.
- Add an interactive keypad simulator and attach it to release-candidate releases.
- Ignore generated Node and Playwright test artifacts while retaining a deterministic frontend package lock.
- Keep all alarm and keypad control read-only.

'''
if not s.startswith("# Changelog\n\n"):
    raise SystemExit("unexpected changelog header")
s = s.replace("# Changelog\n\n", "# Changelog\n\n" + entry, 1)
p.write_text(s)

# RC4 release notes. rc.json intentionally remains on RC3 until packaged main CI passes.
Path("release/0.2.6-rc.4.md").write_text('''# Vista Turbo RS232 0.2.6 RC4

RC4 packages the adaptive keypad, optional local audio/haptics, centralized chime policy, First Alert-inspired skin, and bridge-side audible-state hardening for real Home Assistant and panel testing.

## Card 0.3.17

Supported models:

- `6160cr2`
- `6160`
- `firstalert`

`layout: auto` remains the default. The 6160 models use the physical facsimile when wide and the touchscreen compact layout at 520 px and below. The First Alert-inspired model uses a horizontal wide composition and a portrait narrow composition.

AUTO enclosure defaults are red/dark for 6160CR-2 and white/dark for 6160 and First Alert style.

## Optional keypad feedback

Sound and haptics remain off by default.

```yaml
sound:
  enabled: true
  keypress: true
  state_sounds: true
haptic:
  enabled: true
  keypress_ms: 10
```

The card synthesizes all tones locally through Web Audio. It supports a short key chirp, three-beep chime, trouble/check alert, supervisory alert, fire cadence, audible burglary tone, and auxiliary high/low tone.

When sound is enabled, the first pointer or keyboard interaction anywhere on the Lovelace page is used to unlock browser audio. A small `AUDIO` flag remains visible only while playback is still blocked. Haptic behavior depends on browser support.

## Centralized chime zones

The App now accepts:

```yaml
chime_zones: "1,2,5-8,27"
```

This policy is independent of ECP keypad chime programming. A listed zone produces a dashboard chime only when a validated `F5` is a new fault transition, the partition arming state is initialized, and the resolved partition is disarmed. Duplicate fault reports and faults while armed do not chime.

The keypad entity publishes `chime_sequence`, `chime_zone`, `chime_descriptor`, and `chime_at`.

## Native audible alarm state

The bridge now publishes:

```text
burglary_alarm
auxiliary_alarm
sound_mode
```

`sound_mode` is `none`, `fire`, `burglary`, `auxiliary`, or `unknown`. Audible/perimeter/interior alarm event families drive burglary sound state. The 24-hour auxiliary family drives auxiliary state. Silent alarm and duress events do not drive the burglary speaker classifier.

Event-derived audible state is invalidated after a panel TCP gap. The frontend stops continuous sound when the keypad entity is unavailable.

## Simulator

This release attaches both:

```text
vista-keypad-card.js
vista-keypad-simulator.html
```

The simulator can exercise all three models, wide/narrow layouts, themes, annunciators, and synthesized sound profiles without changing the real panel.

## Install the Home Assistant App

Add or refresh the custom App repository:

```text
https://github.com/wtc-brycel/vistaturbo-hass
```

Update **Vista Turbo RS232** to `0.2.6-rc.4`.

## Install the keypad card

Download `vista-keypad-card.js` to:

```text
/config/www/vista-keypad-card.js
```

Register the Lovelace resource as:

```text
/local/vista-keypad-card.js?v=0.3.17
```

Minimal First Alert-inspired card:

```yaml
type: custom:vista-keypad-card
entity: sensor.vista_partition_1_keypad
model: firstalert
```

Minimal sound-enabled card:

```yaml
type: custom:vista-keypad-card
entity: sensor.vista_partition_1_keypad
model: 6160cr2
sound:
  enabled: true
  keypress: true
  state_sounds: true
```

## Real test targets

1. All three keypad models in Sections and Masonry dashboards at wide and phone widths.
2. iPhone portrait/landscape and browser audio-unlock behavior.
3. Configured-zone chime while disarmed, duplicate-F5 suppression, and no chime while armed.
4. Trouble/check and supervisory one-shot sounds.
5. AC loss/restore and CR-2 POWER behavior.
6. Audible burglary start/restore and 24-hour auxiliary start/restore.
7. Fire alarm, fire silence, detector restore, and panel reset only under safe test conditions.
8. Panel TCP disconnect/reconnect while event-derived states are active.

The bridge remains read-only. Arm, disarm, and keypad-control commands are not sent to the VISTA.
''')
