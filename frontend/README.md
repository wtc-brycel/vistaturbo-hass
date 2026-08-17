# Vista Keypad Card

Home Assistant dashboard card for keypad-display entities published by Vista Turbo RS232.

The card currently implements two keypad models:

- `6160cr2`, modeled after the commercial fire/burglary keypad
- `6160`, modeled after the standard alpha keypad

Both models use the same live VISTA data. The LCD is rendered from the exact 16-character `line_1` and `line_2` attributes from `sensor.vista_partition_1_keypad`.

The card is **read-only** while Vista Turbo RS232 remains read-only. Keys depress visually, but no panel command is sent.

## Install in Home Assistant

Release `v0.2.6-rc.3` attaches card `0.3.15` as `vista-keypad-card.js`.

From the Home Assistant Terminal or SSH add-on:

```sh
mkdir -p /config/www
curl -fL "https://github.com/wtc-brycel/vistaturbo-hass/releases/download/v0.2.6-rc.3/vista-keypad-card.js" \
  -o /config/www/vista-keypad-card.js
```

Then add the card as a Lovelace JavaScript module under **Settings -> Dashboards -> Resources**:

```text
/local/vista-keypad-card.js?v=0.3.15
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

## Adaptive layout

Card `0.3.15` includes a model-agnostic adaptive layout system for Lovelace dashboards.

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

## Case colors and theme following

Both `6160cr2` and `6160` support the same enclosure colors:

- `red`
- `white`
- `dark` for charcoal/dark gray
- `auto` to choose a day or night case color from Home Assistant's current theme

`case_color: auto` is the default for both keypad models.

Default AUTO mappings are model-specific:

| Model | Day/light | Night/dark |
| --- | --- | --- |
| `6160cr2` | `red` | `dark` |
| `6160` | `white` | `dark` |

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

Version 0.3.15 renders both physical and compact LCD canvases from the same state and redraws whichever layout becomes visible after a container breakpoint change.

The repository CI also runs Chromium browser regression tests for wide/compact switching, touch-target dimensions, both model profiles, forced layout modes, theme-aware case colors, and Lovelace grid sizing.

## 6160CR-2 annunciators

Vista Turbo RS232 publishes the CR-2 annunciator state directly on the keypad entity:

- `armed` from the native KD LED bit
- `ready` from the native KD LED bit
- `trouble` from the native KD LED bit
- `power` reconstructed from AC-loss/restore events and keypad reconciliation
- `fire_alarm` latched from fire/smoke/waterflow state and cleared after keypad reset/normalization
- `silenced` reconstructed from the keypad display while a fire alarm is latched
- `supervisory` reconstructed from supervisory start/restore events and keypad display reconciliation

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
