# Vista Keypad Card

Home Assistant dashboard card for the keypad-display entities published by Vista Turbo RS232.

The card currently implements two physical keypad skins:

- `6160cr2`, modeled after the commercial fire/burglary keypad
- `6160`, modeled after the standard white alpha keypad

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

## 6160CR-2 case colors and theme following

`case_color` accepts:

- `auto` — follows Home Assistant's current light/dark theme; red in light mode and charcoal/dark gray in dark mode
- `red` — original commercial red enclosure
- `white` — white enclosure
- `dark` — charcoal/dark gray enclosure

The 6160CR-2 defaults to `auto`.

```yaml
type: custom:vista-keypad-card
entity: sensor.vista_partition_1_keypad
model: 6160cr2
case_color: auto
```

To force the dark version regardless of the dashboard theme:

```yaml
type: custom:vista-keypad-card
entity: sensor.vista_partition_1_keypad
model: 6160cr2
case_color: dark
```

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
