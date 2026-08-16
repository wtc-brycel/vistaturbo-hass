# Vista Keypad Card

Experimental Home Assistant dashboard card for the keypad-display entities published by Vista Turbo RS232.

The first pass implements two physical keypad skins:

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

Optional title and card background:

```yaml
type: custom:vista-keypad-card
entity: sensor.vista_partition_1_keypad
model: 6160cr2
title: Partition 1
show_card_background: true
```

## 6160CR-2 annunciators

The RS-232 keypad-display packet currently gives us Armed, Ready, Trouble and LCD backlight data. The 6160CR-2 also has dedicated Power, Fire Alarm, Silenced, Supervisory and Trouble annunciators. Those are deliberately **not guessed**.

Additional authoritative Home Assistant entities can be mapped when we have them:

```yaml
type: custom:vista-keypad-card
entity: sensor.vista_partition_1_keypad
model: 6160cr2
indicators:
  power: binary_sensor.vista_power
  fire_alarm: binary_sensor.vista_fire_alarm
  silenced: binary_sensor.vista_fire_silenced
  supervisory: binary_sensor.vista_fire_supervisory
  fire_trouble: binary_sensor.vista_fire_trouble
```

Unmapped annunciators remain visibly unlit/unknown.

## Function-key labels

The four left-side keys can be relabeled without changing the card layout:

```yaml
function_keys:
  "1": AWAY
  "2": STAY
  "3": POLICE
  "4": PAGE
```

## Next models

The next skins planned are the newer First Alert/Resideo physical keypads shown during development, followed by a purpose-built touch UI influenced by the newer keypad and Tuxedo-family interfaces rather than trying to mimic a historical physical unit.
