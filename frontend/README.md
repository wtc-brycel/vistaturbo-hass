# Vista Keypad Card

Experimental Home Assistant dashboard card for the keypad-display entities published by Vista Turbo RS232.

The current physical skins are:

- `6160cr2`, modeled after the red commercial fire/burglary keypad
- `6160`, modeled after the standard white alpha keypad

Both skins use the same live VISTA data. The LCD is rendered from the exact 16-character `line_1` and `line_2` attributes from `sensor.vista_partition_1_keypad`; Armed, Ready, and LCD backlight state come from the same entity.

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

Both physical skins use the same chassis proportions and the same exact key dimensions. The 6160 does not render the removable keypad door.

## Programmable A-D keys

The four vertical programmable keys are exposed as A, B, C, and D internally. Their text and colors are configurable without changing the physical layout.

```yaml
type: custom:vista-keypad-card
entity: sensor.vista_partition_1_keypad
model: 6160cr2
function_keys:
  a:
    text: AWAY
  b:
    text: STAY
  c:
    text: POLICE
    background: "#1974ae"
    color: "#ffffff"
  d:
    text: PAGE
```

A plain string is also accepted when only the label needs to change:

```yaml
function_keys:
  a: FIRE
  b: MEDICAL
  c: POLICE
  d: PAGE
```

## 6160CR-2 annunciators

The RS-232 keypad-display packet currently gives us Armed, Ready, Trouble and LCD backlight data. The 6160CR-2 also has dedicated Power, Fire Alarm, Silenced, Supervisory and Trouble annunciators. Those are deliberately **not guessed**.

Additional authoritative Home Assistant entities can be mapped when we have them:

```yaml
indicators:
  power: binary_sensor.vista_power
  fire_alarm: binary_sensor.vista_fire_alarm
  silenced: binary_sensor.vista_fire_silenced
  supervisory: binary_sensor.vista_fire_supervisory
  fire_trouble: binary_sensor.vista_fire_trouble
```

Unmapped fire annunciators remain visibly unlit/unknown.

## Next models

The next physical skins planned are the newer First Alert/Resideo keypads shown during development, followed by a purpose-built touch UI influenced by those units and the Tuxedo-family interfaces.
