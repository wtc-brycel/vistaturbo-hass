from pathlib import Path

RC = "0.2.6-rc.5"
CARD = "0.3.18"


def replace_required(path: str, old: str, new: str, label: str) -> None:
    p = Path(path)
    text = p.read_text()
    if old not in text:
        raise SystemExit(f"missing anchor: {label}")
    p.write_text(text.replace(old, new, 1))


replace_required(
    "vista128_bridge/app/vista_bridge/version.py",
    'VERSION = "0.2.6-rc.4"',
    f'VERSION = "{RC}"',
    "runtime version",
)
replace_required(
    "vista128_bridge/config.yaml",
    'version: "0.2.6-rc.4"',
    f'version: "{RC}"',
    "manifest version",
)

p = Path("README.md")
s = p.read_text()
s = s.replace("0.2.6-rc.4", RC)
s = s.replace("v0.2.6-rc.4", f"v{RC}")
s = s.replace("/local/vista-keypad-card.js?v=0.3.17", f"/local/vista-keypad-card.js?v={CARD}")
s = s.replace("Card `0.3.17` adds a model-agnostic adaptive layout system designed for Home Assistant dashboards.", "Card `0.3.18` includes the adaptive Lovelace layout system plus a native visual editor for normal card configuration.")
needle = "- Supports optional low-latency keypad chirps, alarm/chime sounds, and browser haptics\n"
if needle in s and "visual card editor" not in s:
    s = s.replace(needle, needle + "- Includes a Home Assistant visual card editor for common keypad, appearance, sound, haptic, and function-key settings\n", 1)
p.write_text(s)

p = Path("frontend/README.md")
s = p.read_text()
s = s.replace(
    "The current development card is `0.3.18`; the most recent published release may lag until the next RC is cut.",
    f"Release `v{RC}` attaches card `{CARD}` as `vista-keypad-card.js`.",
)
s = s.replace("v0.2.6-rc.4", f"v{RC}")
s = s.replace("The RC4 release also attaches", "The RC5 release also attaches")
s = s.replace("Card `0.3.17` includes a model-agnostic adaptive layout system for Lovelace dashboards.", "Card `0.3.18` includes the model-agnostic adaptive layout system for Lovelace dashboards.")
p.write_text(s)

p = Path("vista128_bridge/README.md")
s = p.read_text()
s = s.replace("0.2.6-rc.4", RC)
s = s.replace("Card `0.3.17` supports 6160CR-2, standard 6160, and First Alert-inspired skins plus optional synthesized audio and haptics.", "Card `0.3.18` supports 6160CR-2, standard 6160, and First Alert-inspired skins, optional synthesized audio/haptics, and a Home Assistant visual editor for common card settings.")
p.write_text(s)

p = Path("vista128_bridge/CHANGELOG.md")
s = p.read_text()
entry = f'''# Changelog\n\n## {RC}\n\n- Add card `{CARD}` with a Home Assistant visual editor exposed through the custom-card `getConfigElement()` contract.\n- Configure keypad entity, model, layout, title, card background, case color, and day/night case overrides without hand-editing YAML.\n- Configure sound enablement, key chirp, panel-state sounds, chime/trouble/supervisory toggles, key/alarm volume, and optional burglary/AUX entity overrides in the editor.\n- Configure best-effort haptic enablement and keypress duration in the editor.\n- Configure A/B/C/D function-key labels while preserving model defaults when fields are blank.\n- Preserve advanced indicator/flashing maps and per-function-key colors as YAML-only options.\n- Keep the visual editor read-only with no panel-control toggle.\n- Preserve compatibility with `sound: true` and `haptic: true` shorthand configurations.\n- Add Chromium regression coverage for editor discovery, rendered values, nested `config-changed` events, and shorthand compatibility.\n- Keep the bridge protocol/state behavior unchanged from RC4.\n\n'''
if not s.startswith("# Changelog\n\n## 0.2.6-rc.4"):
    raise SystemExit("unexpected changelog head")
s = entry + s[len("# Changelog\n\n"):]
p.write_text(s)

notes = f'''# Vista Turbo RS232 0.2.6 RC5\n\nRC5 is a frontend-focused release. The VISTA bridge protocol and audible-state plumbing are unchanged from RC4; the matching keypad card is now `{CARD}` and adds a Home Assistant visual editor.\n\n## Visual editor\n\nAfter installing the updated JavaScript resource, Home Assistant can edit the card visually instead of showing `Visual editor not supported`.\n\nThe editor covers:\n\n- keypad entity\n- `6160cr2`, `6160`, and `firstalert` styles\n- AUTO, physical, and compact layout modes\n- case color plus optional day/night overrides\n- optional card title and card background\n- sound, key chirp, state sounds, zone chime, trouble/check, supervisory, and volume settings\n- optional burglary/AUX Home Assistant entity overrides\n- haptic enablement and keypress duration\n- A/B/C/D function-key labels\n\nAdvanced indicator/flashing entity mappings and per-function-key colors remain available through YAML. The editor does not expose any alarm-panel control option.\n\n## Install\n\nUpdate **Vista Turbo RS232** to `{RC}` and replace the frontend file with the release asset:\n\n```text\nvista-keypad-card.js\n```\n\nRegister or update the Lovelace resource to:\n\n```text\n/local/vista-keypad-card.js?v={CARD}\n```\n\nExisting YAML remains valid. `sound: true` and `haptic: true` shorthand values are recognized by the visual editor.\n\nRC5 also continues to attach `vista-keypad-simulator.html` for standalone UI/audio testing.\n\nThe bridge remains read-only. Arm, disarm, and keypad-control commands are not sent to the VISTA.\n'''
Path(f"release/{RC}.md").write_text(notes)
