# Vista Keypad Card

Home Assistant dashboard card for keypad-display entities published by Vista Turbo RS232.

The card currently implements three keypad models:

- `6160cr2`, modeled after the commercial fire/burglary keypad
- `6160`, modeled after the standard alpha keypad
- `firstalert`, a First Alert-inspired adaptive skin that uses a horizontal composition when wide and a portrait composition when narrow

All three models use the same live VISTA data. The LCD is rendered from the exact 16-character `line_1` and `line_2` attributes from `sensor.vista_partition_1_keypad`.

The card is **read-only** while Vista Turbo RS232 remains read-only. Keys depress visually, but no panel command is sent.

## Install in Home Assistant

Release `v0.2.6-rc.5` attaches card `0.3.18` as `vista-keypad-card.js`.

From the Home Assistant Terminal or SSH add-on:

```sh
mkdir -p /config/www
curl -fL "https://github.com/wtc-brycel/vistaturbo-hass/releases/download/v0.2.6-rc.5/vista-keypad-card.js" \
  -o /config/www/vista-keypad-card.js
```

Then add the card as a Lovelace JavaScript module under **Settings -> Dashboards -> Resources**:

```text
/local/vista-keypad-card.js?v=0.3.18
```

The version suffix is intentional. Change it whenever the JavaScript file is replaced so Home Assistant and mobile browsers do not reuse a stale cached copy.

A minimal 6160CR-2 card is:

```yaml
type: custom:vista-keypad-card
entity: sensor.vista_partition_1_keypad
model: 6160cr2
```

For the standard 6160 skin:

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

The RC5 release also attaches `vista-keypad-simulator.html`. Place it beside the card in `/config/www` and open `/local/vista-keypad-simulator.html` to exercise all three layouts, widths, annunciators, chime/alarm states, and audio behavior without changing the real panel.


## Visual editor

Card `0.3.18` implements Home Assistant's custom-card visual editor contract through `getConfigElement()`. The dashboard editor can configure the normal installation without hand-editing YAML:

- keypad entity
- 6160CR-2, 6160, or First Alert style
- AUTO, physical, or compact layout
- case color plus optional day/night overrides
- title and Home Assistant card background
- sound enablement, key chirp, panel-state sounds, chime/trouble/supervisory toggles, and volume levels
- optional burglary/AUX Home Assistant entity overrides
- haptic enablement and keypress duration
- A/B/C/D function-key labels

The visual editor intentionally keeps the bridge read-only. Advanced indicator/flashing entity mappings and per-function-key colors remain YAML-only.

## Adaptive layout

Card `0.3.18` includes the model-agnostic adaptive layout system for Lovelace dashboards.

```yaml
layout: auto
```

is the default. The supported values are:

- `auto` - physical facsimile when the card is wide enough, touchscreen compact layout when the card container is 520 px or narrower
- `physical` - always render the full physical keypad facsimile
- `compact` - always render the touchscreen-first layout

Example:

```yaml
type: custom:vista-keypad-card
entity: sensor.vista_partition_1_keypad
model: 6160cr2
layout: auto
```

The compact layout is not a scaled-down photograph of the keypad. It reallocates the available area to the LCD, status annunciators, and usable touch targets. Decorative speaker slots, molded-plastic spacing, brackets, and fire/burg icons are omitted.

At narrow widths, keypad targets remain approximately 50 px tall. Numeric legends are removed only at the very narrowest breakpoint, below 320 px, so the primary digit remains readable.

The standard 6160 uses the same compact renderer. Its compact function keys are labeled A/B/C/D even though the physical skin leaves them unlabeled.

### Future keypad models

Compact behavior is declared in `MODEL_PROFILES` rather than hard-coded into the CR-2 renderer. A future model supplies:

- its compact function-key labels
- the annunciators it exposes
- the state field and LED class for each annunciator

The generic compact renderer then provides the LCD, status strip, touch-grid geometry, case theme, responsive breakpoints, and input handling. A future panel therefore does not need a separate mobile UI implementation.

Home Assistant grid hints allow the card to shrink to four grid columns because compact mode remains usable at that width.


## First Alert-inspired skin

`model: firstalert` is intentionally inspired by the supplied First Alert keypad examples rather than being a pixel-for-pixel reproduction. AUTO layout uses a low, horizontal keypad on wider Lovelace cards and a tall portrait keypad at the compact breakpoint. Both forms keep the same 16-key VISTA input surface: the numeric keys use First Alert-style secondary legends and the A/B/C/D function keys are presented as separate round function buttons. The same seven available CR-2 status fields are adapted into a compact First Alert-style indicator rail.

```yaml
type: custom:vista-keypad-card
entity: sensor.vista_partition_1_keypad
model: firstalert
layout: auto
```

The default AUTO enclosure mapping is white in light mode and dark in dark mode. Red remains available as an explicit case color.

## Case colors and theme following

All three models support the same enclosure colors:

- `red`
- `white`
- `dark` for charcoal/dark gray
- `auto` to choose a day or night case color from Home Assistant's current theme

`case_color: auto` is the default for all keypad models.

Default AUTO mappings are model-specific:

| Model | Day/light | Night/dark |
| --- | --- | --- |
| `6160cr2` | `red` | `dark` |
| `6160` | `white` | `dark` |
| `firstalert` | `white` | `dark` |

The day and night colors are independently optional:

```yaml
type: custom:vista-keypad-card
entity: sensor.vista_partition_1_keypad
model: 6160cr2
case_color: auto
day_case_color: red
night_case_color: dark
```

Explicit `case_color` always wins over day/night AUTO settings.

AUTO first uses Home Assistant's `hass.themes.darkMode`. If that flag is unavailable, the card falls back to the browser's `prefers-color-scheme` setting.

## Mobile rendering protections

The adaptive layout retains the mobile hardening introduced in card 0.3.14:

- LCD canvases redraw with `ResizeObserver` after orientation and card-width changes
- `pointercancel` and lost pointer capture clear pressed-key feedback when a touch becomes a page scroll or gesture
- unrelated Home Assistant state changes do not rebuild the full card
- browser light/dark changes are observed when Home Assistant does not expose an explicit theme mode

Version 0.3.17 renders both physical and compact LCD canvases from the same state and redraws whichever layout becomes visible after a container breakpoint change.

The repository CI also runs Chromium browser regression tests for wide/compact switching, touch-target dimensions, both model profiles, forced layout modes, theme-aware case colors, and Lovelace grid sizing.

## Optional audio and haptic feedback

Card `0.3.17` adds optional synthesized keypad feedback. It is disabled by default and does not require audio files or network requests. Web Audio tones are created locally with an interactive-latency context.

Example:

```yaml
type: custom:vista-keypad-card
entity: sensor.vista_partition_1_keypad
model: 6160cr2
sound:
  enabled: true
  keypress: true
  state_sounds: true
  volume: 0.035
  alarm_volume: 0.065
haptic:
  enabled: true
  keypress_ms: 10
```

The bridge publishes native `burglary_alarm`, `auxiliary_alarm`, and `sound_mode` attributes, so extra Home Assistant entities are not required for normal alarm audio. Optional `alarm_entity` and `aux_entity` mappings remain available as advanced overrides.

Supported synthesized profiles are:

- immediate short keypress chirp
- three-beep zone chime
- two-beep trouble/check alert
- supervisory alert
- repeating fire alarm cadence
- continuous burglary alarm
- repeating high/low auxiliary alarm

Continuous sound priority is unsilenced fire, then audible burglary, then 24-hour auxiliary. A silenced fire condition keeps the fire/silenced annunciators but stops the local fire tone. Trouble, supervisory, and chime are one-shot transition sounds. Continuous sound stops when the keypad entity becomes unavailable.

The tones model conventional keypad behavior; exact Honeywell/Resideo piezo frequencies are not claimed.

### Chime zones

The card does not guess panel ECP chime programming and does not watch individual zone entities. Vista Turbo RS232 maintains its own centralized list of zones that should generate a dashboard chime. Configure the App with VISTA zone numbers and optional ranges:

```yaml
chime_zones: "1,2,5-8,27"
```

An empty value disables bridge-generated chimes. A listed zone increments `chime_sequence` only when a validated `F5` event represents a new false-to-faulted transition, the partition arming state has been initialized, and that partition is disarmed. Duplicate `F5` reports and faults while armed do not chime. The keypad entity also publishes `chime_zone`, `chime_descriptor`, and `chime_at`.

Audio autoplay restrictions still apply. When sound is enabled, the card listens for the first pointer or keyboard interaction anywhere on the Lovelace page and uses that user gesture to unlock its AudioContext. A small `AUDIO` flag remains visible only while audio is still blocked and can be tapped as an explicit fallback. Haptic feedback is best-effort and only runs when the browser exposes `navigator.vibrate()`.

## 6160CR-2 annunciators

Vista Turbo RS232 publishes the CR-2 annunciator state directly on the keypad entity:

- `armed` from the native KD LED bit
- `ready` from the native KD LED bit
- `trouble` from the native KD LED bit
- `power` reconstructed from AC-loss/restore events and keypad reconciliation
- `fire_alarm` latched from fire/smoke/waterflow state and cleared after keypad reset/normalization
- `silenced` reconstructed from the keypad display while a fire alarm is latched
- `supervisory` reconstructed from supervisory start/restore events and keypad display reconciliation
- `burglary_alarm` reconstructed only from audible/perimeter/interior burglary families, not silent or duress events
- `auxiliary_alarm` reconstructed from the 24-hour auxiliary alarm family
- `sound_mode` normalized to `none`, `fire`, `burglary`, `auxiliary`, or `unknown`

Unknown reconstructed states are JSON `null`; the card renders those lamps as unknown rather than inventing a state.

Optional `indicators:` entity mappings remain supported as per-card overrides.

## Function-key labels

The four left-side keys can be relabeled and styled without changing either layout:

```yaml
function_keys:
  a:
    text: AWAY
  b:
    text: STAY
  c:
    text: POLICE
  d:
    text: PAGE
```
