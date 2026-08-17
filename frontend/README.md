# Vista Keypad Card

Home Assistant dashboard card for the keypad-display entities published by Vista Turbo RS232.

The card currently implements two physical keypad skins:

- `6160cr2`, modeled after the commercial fire/burglary keypad
- `6160`, modeled after the standard alpha keypad

Both skins use the same live VISTA data. The LCD is rendered from the exact 16-character `line_1` and `line_2` attributes from `sensor.vista_partition_1_keypad`.

The card is **read-only** while Vista Turbo RS232 remains read-only. The keys depress visually, but no panel command is sent.

## Install in Home Assistant

The release attaches `vista-keypad-card.js` as a standalone asset.

From the Home Assistant Terminal or SSH add-on:

```sh
mkdir -p /config/www
curl -fL "https://github.com/wtc-brycel/vistaturbo-hass/releases/download/v0.2.6-rc.2/vista-keypad-card.js" \
  -o /config/www/vista-keypad-card.js
```

Then add the card as a Lovelace JavaScript module under **Settings -> Dashboards -> Resources**:

```text
/local/vista-keypad-card.js?v=0.3.14
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

## Case colors and theme following

Both `6160cr2` and `6160` support the same enclosure colors:

- `red`
- `white`
- `dark` for charcoal/dark gray
- `auto` to choose a day or night case color from Home Assistant's current theme

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

## Responsive and mobile behavior

Development card `0.3.15` adds a separate Lovelace-oriented compact composition instead of shrinking the physical keypad until its keys become unusable.

`mobile_layout: auto` is the default. At card widths above 480 px, the realistic physical keypad composition is preserved. At 480 px and below, AUTO switches to compact mode.

Compact mode:

- gives the LCD the full card width
- hides decorative speaker, bracket, shield, and flame artwork
- keeps all CR-2 annunciator states in a compact status strip
- uses the full card width for the 4 x 4 keypad
- keeps key rows approximately 52 to 60 px tall instead of scaling them with the physical enclosure
- stacks the small numeric legends under the number
- changes the CR-2 status strip from four columns to three below 320 px

The available modes are:

- `auto` - physical layout when wide, compact at 480 px and below
- `compact` - always use the Lovelace/mobile composition
- `physical` - always preserve the realistic physical composition

Example:

```yaml
type: custom:vista-keypad-card
entity: sensor.vista_partition_1_keypad
model: 6160cr2
mobile_layout: auto
```

The card advertises 12 columns by default with an 8-column minimum in Home Assistant Sections view. LCD resize observation, touch cancellation handling, filtered Home Assistant rerenders, and automatic light/dark case switching apply to both physical and compact layouts.

## 6160CR-2 annunciators

Vista Turbo RS232 publishes the CR-2 annunciator state directly on the keypad entity:

- `armed` from the native KD LED bit
- `ready` from the native KD LED bit
- `trouble` from the native KD LED bit
- `power` reconstructed from AC-loss/restore events and keypad reconciliation
- `fire_alarm` latched from fire/smoke/waterflow state and cleared after keypad reset/normalization
- `silenced` reconstructed from the keypad display while a fire alarm is latched
- `supervisory` reconstructed from supervisory start/restore events and keypad display reconciliation

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
