# Vista Keypad Card

Home Assistant dashboard card for the keypad-display entities published by Vista Turbo RS232.

The card currently implements two physical keypad skins:

- `6160cr2`, modeled after the commercial fire/burglary keypad
- `6160`, modeled after the standard alpha keypad

Both skins use the same live VISTA data. The LCD is rendered from the exact 16-character `line_1` and `line_2` attributes from `sensor.vista_partition_1_keypad`.

The card is **read-only** while Vista Turbo RS232 remains read-only. The keys depress visually, but no panel command is sent.

## Install for development

Copy `vista-keypad-card.js` to Home Assistant's `/config/www/` directory and add it as a Lovelace JavaScript module:

```text
/local/vista-keypad-card.js
```

Then add the card:

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

## Case colors and theme following

Both `6160cr2` and `6160` support the same enclosure colors:

- `red`
- `white`
- `dark` — charcoal/dark gray
- `auto` — chooses a day or night case color from Home Assistant's current theme

`case_color: auto` is the default for **both** keypad models, so it may be omitted.

Default AUTO mappings are model-specific:

| Model | Day/light | Night/dark |
| --- | --- | --- |
| `6160cr2` | `red` | `dark` |
| `6160` | `white` | `dark` |

The day and night colors are independently optional and may be overridden with `day_case_color` and `night_case_color`:

```yaml
type: custom:vista-keypad-card
entity: sensor.vista_partition_1_keypad
model: 6160cr2
case_color: auto
day_case_color: red
night_case_color: dark
```

For example, this deliberately uses a white CR-2 during the day and a red CR-2 at night:

```yaml
type: custom:vista-keypad-card
entity: sensor.vista_partition_1_keypad
model: 6160cr2
day_case_color: white
night_case_color: red
```

Explicit `case_color` always wins over day/night AUTO settings:

```yaml
type: custom:vista-keypad-card
entity: sensor.vista_partition_1_keypad
model: 6160
case_color: red
```

AUTO first uses Home Assistant's `hass.themes.darkMode`. If that flag is unavailable, the card falls back to the browser's `prefers-color-scheme` setting.

## Responsive sizing

The physical keypad keeps its fixed enclosure aspect ratio as the Lovelace column narrows. There is no forced minimum height that can stretch the enclosure vertically. Button, legend, annunciator-label, border, and spacing dimensions scale from the card container width, with additional narrow-container adjustments below 520 px and 360 px.

## 6160CR-2 annunciators

Vista Turbo RS232 publishes the CR-2 annunciator state directly on the keypad entity:

- `armed` — native KD LED bit
- `ready` — native KD LED bit
- `trouble` — native KD LED bit
- `power` — reconstructed from AC-loss/restore events and keypad reconciliation
- `fire_alarm` — latched fire/smoke/waterflow state, cleared after keypad reset/normalization
- `silenced` — reconstructed from the keypad display while a fire alarm is latched
- `supervisory` — reconstructed from supervisory start/restore events and keypad display reconciliation

Unknown reconstructed states are published as JSON `null` until the bridge has authoritative evidence. The card renders those lamps as unknown rather than inventing a state.

Optional `indicators:` entity mappings remain supported as per-card overrides for experimentation, but are no longer required with a current bridge.

## Function-key labels

The four left-side keys can be relabeled and styled without changing the card layout:

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
