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

All sixteen physical keys use the same dimensions in both legacy keypad skins.

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

The card includes an optional Web Audio square-wave key beep. It is disabled by default because the 6160 frequency and timing have not yet been measured from hardware.

```yaml
sound: true
sound_frequency_hz: 1400
sound_duration_ms: 65
sound_volume: 0.035
```

Those values are tuning parameters, not a claim that the current defaults match a physical 6160.

## Current visual pass

Version 0.2.0 removes the 6160 drop-down door from the rendered view, shares exact key geometry across both skins, adds configurable A-D key styling, uses a drawn 5x7 dot-matrix LCD, and increases plastic, bezel, key, LED and shadow detail.
