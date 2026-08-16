# Vista Keypad Card

Experimental Home Assistant card for Vista Turbo RS232 keypad-display entities.

Current physical skins:

- `6160cr2`: red commercial fire/burglary keypad
- `6160`: white alpha keypad

Both skins use the same live VISTA data and remain read-only while panel control is disabled.

## Install for development

Copy `vista-keypad-card.js` to `/config/www/`, register `/local/vista-keypad-card.js` as a Lovelace JavaScript module, then add:

```yaml
type: custom:vista-keypad-card
entity: sensor.vista_partition_1_keypad
model: 6160cr2
```

Use `model: 6160` for the white keypad.

## Function keys

The four programmable keys are A through D internally. Their text and colors can be configured independently:

```yaml
function_keys:
  a:
    text: AWAY
  b:
    text: STAY
  c:
    text: POLICE
    background: "#168bc3"
    color: "#ffffff"
  d:
    text: PAGE
```

All sixteen physical keys use the same dimensions in both keypad skins.

## Annunciators

Armed, Ready and LCD backlight come from the keypad-display entity. The additional 6160CR-2 fire annunciators are not inferred. Map authoritative entities when available:

```yaml
indicators:
  power: binary_sensor.vista_power
  fire_alarm: binary_sensor.vista_fire_alarm
  silenced: binary_sensor.vista_fire_silenced
  supervisory: binary_sensor.vista_fire_supervisory
  fire_trouble: binary_sensor.vista_fire_trouble
```

Unmapped annunciators remain dark/unknown.

## Key sounds

The card includes optional Web Audio square-wave key feedback. It is disabled by default until the physical keypad frequency and timing are measured.

```yaml
sound:
  enabled: true
  frequency: 1400
  duration_ms: 45
  volume: 0.035
```

Those values are tuning parameters only.

## Current visual pass

Version 0.3.1 keeps the two keypad skins aligned to the supplied physical references while removing decorative branding and the artificial case notch from the rendered graphics.

The 6160 and 6160CR-2 share the same overall face proportions and exact key dimensions, with no rendered drop-down door. The key grid uses four equal-height rows, the separate recessed programmable-key column, and the wider gap between that column and the numeric keypad.

The CR-2 burglary-status block reserves a separate area for the shield graphic so it does not overlap the Armed and Ready LED lenses. The LED lenses now use layered smoked-plastic surfaces, specular highlights, inner reflections, lens rims and multi-stage light bloom when illuminated.

The raised display hood, speaker slots, control placement, keycap proportions, molded-plastic shading and microtexture are drawn separately. The LCD is rendered as a 5x7 dot matrix from the exact 16-character VISTA display lines.

No reference photograph or manufacturer logo is embedded in the card. The physical appearance is produced by CSS, inline SVG and canvas so the keypad remains responsive and interactive.
