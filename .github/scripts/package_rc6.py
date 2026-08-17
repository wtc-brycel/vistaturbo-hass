from pathlib import Path


def replace_once(path: str, old: str, new: str, label: str) -> None:
    p = Path(path)
    text = p.read_text()
    if old not in text:
        raise SystemExit(f"missing anchor {label} in {path}")
    p.write_text(text.replace(old, new, 1))


replace_once(
    "vista128_bridge/app/vista_bridge/version.py",
    'VERSION = "0.2.6-rc.5"',
    'VERSION = "0.2.6-rc.6"',
    "runtime version",
)
replace_once(
    "vista128_bridge/config.yaml",
    'version: "0.2.6-rc.5"',
    'version: "0.2.6-rc.6"',
    "manifest version",
)

# Root README current-install references only.
p = Path("README.md")
s = p.read_text()
s = s.replace("0.2.6-rc.5", "0.2.6-rc.6")
s = s.replace("v0.2.6-rc.5", "v0.2.6-rc.6")
s = s.replace("/local/vista-keypad-card.js?v=0.3.18", "/local/vista-keypad-card.js?v=0.3.19")
p.write_text(s)

# App README current status/card line.
p = Path("vista128_bridge/README.md")
s = p.read_text()
s = s.replace("0.2.6-rc.5", "0.2.6-rc.6", 1)
s = s.replace(
    "Card `0.3.18` supports 6160CR-2, standard 6160, and First Alert-inspired skins, optional synthesized audio/haptics, and a Home Assistant visual editor for common card settings.",
    "Card `0.3.19` includes the keypad models and visual editor from 0.3.18 plus the responsive `custom:vista-event-log-card` for the SQLite-backed recent event window.",
    1,
)
p.write_text(s)

# Frontend install section: preserve historical feature-introduction version text.
p = Path("frontend/README.md")
s = p.read_text()
s = s.replace(
    "The current development card is `0.3.18`; the most recent published release may lag until the next RC is cut.",
    "Release `v0.2.6-rc.6` ships card `0.3.19`, including both the keypad and event-journal cards.",
    1,
)
s = s.replace("releases/download/v0.2.6-rc.5/vista-keypad-card.js", "releases/download/v0.2.6-rc.6/vista-keypad-card.js", 1)
s = s.replace("/local/vista-keypad-card.js?v=0.3.18", "/local/vista-keypad-card.js?v=0.3.19", 1)
p.write_text(s)

# Changelog.
p = Path("vista128_bridge/CHANGELOG.md")
s = p.read_text()
section = '''## 0.2.6-rc.6\n\n- Add a persistent SQLite VISTA event journal at `/data/vista128_events.sqlite3`.\n- Journal live `nq` system events with event code, panel time, partition, zone, user, descriptor, and source metadata.\n- Add optional startup import of the documented VISTA historical event log using `08LD00A8`, `ld` entries, and the `08lc0069` completion packet.\n- Leave historical startup import disabled by default pending physical VISTA-128BPT validation; live SQLite journaling is enabled by default.\n- Keep imported historical events isolated from live state changes, chimes, sounds, keypad refreshes, and printer receipts.\n- Deduplicate repeated historical imports while preserving multiple identical events that genuinely occur within the same panel minute.\n- Backfill programmed zone descriptors into existing journal rows when descriptors become available.\n- Add the Home Assistant **Event Journal** sensor with a configurable 1-100 row recent window instead of copying the full database into HA state.\n- Keep the Event Journal available while the panel TCP link is down as long as the bridge remains online.\n- Add card `0.3.19` with `custom:vista-event-log-card`, responsive recent-event rows, partition filtering, live/history/both source labels, and a visual editor.\n- Recognize `08XF` Communication Off and expose an **Automation Interface Available** diagnostic.\n- Recognize `10DC` Display Changed passively without assuming refresh behavior until observed on the test panel.\n- Add C7 Fail To Arm and C8 Fail To Disarm event descriptions.\n- Keep all alarm and keypad control read-only.\n\n'''
if "## 0.2.6-rc.6" not in s:
    s = s.replace("# Changelog\n\n", "# Changelog\n\n" + section, 1)
p.write_text(s)

notes = '''# Vista Turbo RS232 0.2.6 RC6\n\nRC6 is the first persistent event-history test release. It keeps the control path read-only while adding a local SQLite journal, an optional VISTA historical event-log import, and a Home Assistant event-journal card.\n\n## Persistent journal\n\nLive decoded VISTA system events are written to:\n\n```text\n/data/vista128_events.sqlite3\n```\n\nThe journal persists across App restarts/upgrades and records event code, panel timestamp, partition, zone, user number, programmed descriptor, and whether an occurrence was seen live, in a historical dump, or both. Multiple identical events within the same panel minute are preserved as distinct occurrences.\n\nThe Home Assistant **Event Journal** sensor mirrors only the most recent configured window (20 rows by default, configurable from 1 through 100). The complete SQLite journal is not copied into Home Assistant state.\n\n## Historical VISTA event-log import\n\nRC6 implements the documented historical transaction:\n\n```text\n08LD00A8\n  -> ld event records\n  -> 08lc0069 completion\n```\n\nFor the first physical VISTA-128BPT test, this is deliberately disabled by default:\n\n```yaml\nevent_history_enabled: true\nevent_history_startup_dump_enabled: false\nevent_history_recent_limit: 20\n```\n\nFirst verify live journaling. Then set `event_history_startup_dump_enabled: true` and restart the App to exercise the panel dump. Historical records never call the live state machine, so an imported alarm/fault cannot generate a chime, alarm sound, keypad refresh, state transition, or printer receipt.\n\nResideo specifies that VISTA-128BPT retains up to 512 events.\n\n## Home Assistant event view\n\nCard `0.3.19` is still delivered in the same `vista-keypad-card.js` resource and additionally registers:\n\n```yaml\ntype: custom:vista-event-log-card\nentity: sensor.event_journal\nrows: 20\npartition: 0\n```\n\nUse the visual editor to select the actually discovered **Event Journal** entity if Home Assistant assigns a different entity ID. `partition: 0` displays all partitions; 1-8 filter the recent window.\n\nRows show panel time, event code, description, zone descriptor, partition/zone/user metadata, and `LIVE`, `HISTORY`, or `BOTH` source status.\n\n## Passive protocol additions\n\n- `08XF` Communication Off is recognized and drives an **Automation Interface Available** diagnostic.\n- `10DC` Display Changed is recognized and logged passively only. No automatic KD refresh is attached to it until it is observed on the current panel.\n- C7 Fail To Arm and C8 Fail To Disarm are decoded by name.\n\n## Frontend installation\n\nReplace the existing JavaScript with the RC6 asset and use the cache-buster:\n\n```text\n/local/vista-keypad-card.js?v=0.3.19\n```\n\nThe bridge remains read-only. Native arm/disarm and keypad keystroke control are separate follow-on work.\n'''
Path("release/0.2.6-rc.6.md").write_text(notes)
