from pathlib import Path


def replace_once(path: str, old: str, new: str, label: str) -> None:
    p = Path(path)
    text = p.read_text()
    if old not in text:
        raise SystemExit(f"missing anchor: {label}")
    p.write_text(text.replace(old, new, 1))


# Frontend README: document optional local feedback and bridge-owned chime policy.
path = "frontend/README.md"
old = '''## 6160CR-2 annunciators\n'''
new = '''## Optional audio and haptic feedback\n\nCard `0.3.16` adds optional synthesized keypad feedback. It is disabled by default and does not require audio files or network requests. Web Audio tones are created locally with an interactive-latency context.\n\nExample:\n\n```yaml\ntype: custom:vista-keypad-card\nentity: sensor.vista_partition_1_keypad\nmodel: 6160cr2\nsound:\n  enabled: true\n  keypress: true\n  state_sounds: true\n  volume: 0.035\n  alarm_volume: 0.065\n  alarm_entity: alarm_control_panel.your_partition\n  aux_entity: binary_sensor.your_aux_alarm\nhaptic:\n  enabled: true\n  keypress_ms: 10\n```\n\nSet `alarm_entity` and `aux_entity` only when those Home Assistant entities should drive the corresponding continuous sound profiles. Do not use the example entity IDs literally.\n\nSupported synthesized profiles are:\n\n- immediate short keypress chirp\n- three-beep zone chime\n- two-beep trouble/check alert\n- supervisory alert\n- repeating fire alarm cadence\n- continuous burglary alarm\n- repeating high/low auxiliary alarm\n\nContinuous sound priority is unsilenced fire, then `alarm_entity`, then `aux_entity`. A silenced fire condition keeps the fire/silenced annunciators but stops the local fire tone. Trouble, supervisory, and chime are one-shot transition sounds.\n\nThe tones model conventional keypad behavior; exact Honeywell/Resideo piezo frequencies are not claimed.\n\n### Chime zones\n\nThe card does not guess panel ECP chime programming and does not watch individual zone entities. Vista Turbo RS232 maintains its own centralized list of zones that should generate a dashboard chime. Configure the App with VISTA zone numbers and optional ranges:\n\n```yaml\nchime_zones: "1,2,5-8,27"\n```\n\nAn empty value disables bridge-generated chimes. When a configured zone produces the validated real-time `F5` Fault event, the bridge increments `chime_sequence` on the affected partition keypad entity and publishes `chime_zone`, `chime_descriptor`, and `chime_at`. Every card using that keypad entity can then react to the same authoritative chime event without maintaining a separate list.\n\nAudio autoplay restrictions still apply. A browser may require one user interaction before Web Audio can start; pressing a keypad key or explicitly unlocking audio satisfies that requirement in supported browsers. Haptic feedback is best-effort and only runs when the browser exposes `navigator.vibrate()`.\n\n## 6160CR-2 annunciators\n'''
replace_once(path, old, new, "frontend audio docs")

# Bridge operator docs: expose the centralized chime list in App configuration.
path = "vista128_bridge/DOCS.md"
replace_once(
    path,
    '''keypad_event_refresh_delay_ms: 250\ntransport_print_enabled: false\n''',
    '''keypad_event_refresh_delay_ms: 250\nchime_zones: ""\ntransport_print_enabled: false\n''',
    "DOCS config chime option",
)
replace_once(
    path,
    '''The keypad display is queried every 7 seconds by default. Valid unsolicited system events also request a debounced keypad refresh for the affected configured partition. All keypad queries share the same serialized transaction lock as startup and periodic synchronization.\n''',
    '''The keypad display is queried every 7 seconds by default. Valid unsolicited system events also request a debounced keypad refresh for the affected configured partition. All keypad queries share the same serialized transaction lock as startup and periodic synchronization.\n\n`chime_zones` is Vista Turbo RS232's own centralized dashboard-chime policy. It is intentionally separate from any chime programming transported on the VISTA ECP bus. Supply comma-separated VISTA zone numbers and ascending ranges, for example `"1,2,5-8,27"`. Valid zones are 1 through 128. An empty string disables bridge-generated chime events. When a listed zone produces the validated `F5` Fault event, the affected keypad entity increments `chime_sequence` and exposes `chime_zone`, `chime_descriptor`, and `chime_at`. The frontend can use that sequence change to play one chime without polling or subscribing to every zone entity.\n''',
    "DOCS chime explanation",
)
