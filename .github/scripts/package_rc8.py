from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text()


def write(path: str, text: str) -> None:
    p = ROOT / path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)


def replace(path: str, old: str, new: str, count: int = -1) -> None:
    text = read(path)
    if old not in text:
        raise SystemExit(f"missing RC8 package anchor in {path}: {old[:100]!r}")
    write(path, text.replace(old, new, count))


# Versions.
replace("vista128_bridge/config.yaml", 'version: "0.2.6-rc.7"', 'version: "0.2.6-rc.8"', 1)
replace("vista128_bridge/app/vista_bridge/version.py", 'VERSION = "0.2.6-rc.7"', 'VERSION = "0.2.6-rc.8"', 1)
replace("frontend/vista-keypad-card.js", 'const VISTA_KEYPAD_CARD_VERSION = "0.3.20";', 'const VISTA_KEYPAD_CARD_VERSION = "0.3.21";', 1)
replace("frontend/vista-keypad-simulator.html", "Vista Keypad 0.3.20 simulator", "Vista Keypad 0.3.21 simulator")

# Small state hardening found during the RC8 review. Event-only low battery and
# tamper conditions must participate in the reconnect-invalidated trouble token
# model instead of keeping semantic TROUBLE alive from stale zone attributes.
replace(
    "vista128_bridge/app/vista_bridge/state.py",
    '''    "64": "63",\n    "A2": "A1",\n''',
    '''    "64": "63",\n    "8A": "89",\n    "A2": "A1",\n''',
    1,
)
replace(
    "vista128_bridge/app/vista_bridge/state.py",
    '''    "F4": "F3",\n    "FE": "FD",\n''',
    '''    "F4": "F3",\n    "B4": "B3",\n    "FE": "FD",\n''',
    1,
)
replace(
    "vista128_bridge/app/vista_bridge/state.py",
    '''        return any(\n            zone.partition == partition_number and (zone.trouble or zone.low_battery or zone.tamper)\n            for zone in self.zones.values()\n        )\n''',
    '''        return any(\n            zone.partition == partition_number and zone.trouble\n            for zone in self.zones.values()\n        )\n''',
    1,
)
replace(
    "vista128_bridge/app/vista_bridge/state.py",
    '''        self._reconcile_partition_zone_alarms()\n        return changed\n\n    def set_descriptor''',
    '''        self._reconcile_partition_zone_alarms()\n        self._reconcile_all_keypad_trouble()\n        return changed\n\n    def set_descriptor''',
    1,
)
replace(
    "vista128_bridge/app/vista_bridge/state.py",
    '''        # AC is panel-global. A displayed AC failure is definitive. Conversely, a\n        # keypad with no TROUBLE LED cannot currently be in AC-loss trouble, so it\n        # gives us a safe startup reconciliation path for the POWER annunciator.\n''',
    '''        # AC is panel-global. A displayed AC failure is definitive. Quiet KD\n        # pages are not positive AC evidence because the panel cycles status pages.\n''',
    1,
)

# Shutdown diagnostics should not leave a stale inferred/explicit source.
replace(
    "vista128_bridge/app/vista_bridge/bridge.py",
    '''            self.mqtt.publish("panel/connected", "OFF", retain=True)\n            self.mqtt.publish("panel/automation_available", "OFF", retain=True)\n            self.mqtt.stop()\n''',
    '''            self.mqtt.publish("panel/connected", "OFF", retain=True)\n            self.mqtt.publish("panel/automation_available", "OFF", retain=True)\n            self.mqtt.publish("panel/automation_availability_source", "offline", retain=True)\n            self.mqtt.stop()\n''',
    1,
)

# Regression coverage for reconnect-invalidated event-only trouble state.
replace(
    "vista128_bridge/tests/test_readiness.py",
    '''    def test_fire_latch_clears_after_restore_when_burglary_not_ready(self):\n''',
    '''    def test_reconnect_discards_event_only_low_battery_and_tamper_trouble(self):\n        state = VistaState()\n        state.zones[21].partition = 1\n        keypad = state.apply_keypad_display(\n            1,\n            keypad_report("P1   DISARMED   ", "READY TO ARM    "),\n            "2026-08-17T17:00:00-04:00",\n        )\n        state.apply_system_event(event("89", zone=21))\n        state.apply_system_event(event("B3", zone=21))\n        self.assertTrue(keypad.trouble_led)\n        self.assertTrue(state.partitions[1].active_trouble_tokens)\n\n        state.reset_connection_derived_annunciators()\n        state.apply_keypad_display(\n            1,\n            keypad_report("P1   DISARMED   ", "READY TO ARM    "),\n            "2026-08-17T17:01:00-04:00",\n        )\n        self.assertFalse(state.partitions[1].active_trouble_tokens)\n        self.assertFalse(keypad.trouble_led)\n\n    def test_fire_latch_clears_after_restore_when_burglary_not_ready(self):\n''',
    1,
)

# Changelog.
changelog = read("vista128_bridge/CHANGELOG.md")
entry = '''## 0.2.6-rc.8\n\n- Infer Automation Interface Available after a successful structured VISTA transaction when the panel does not emit `08XN` during ordinary operation.\n- Preserve `08XF` Communication Off as an explicit same-session control block that ordinary `08OK` replies cannot override.\n- Add the **Automation Availability Source** diagnostic with `unknown`, `inferred`, `explicit`, `communication_off`, and `offline` states.\n- Stop treating a quiet KD page or a false raw TROUBLE lamp bit as evidence that AC power is present. POWER remains unknown after reconnect until explicit AC evidence is observed.\n- Split semantic keypad `trouble` from `trouble_led_raw`; semantic TROUBLE remains active across the VISTA's rotating display pages while known trouble conditions remain active.\n- Track validated trouble families, system battery, RF low battery, and sensor tamper with reconnect-invalidated trouble state.\n- Treat both `D` and `N` arming snapshots as authoritative disarmed states when clearing stale alarm tokens.\n- Publish individual virtual-keypad presses at MQTT QoS 0 with retain disabled to avoid at-least-once duplicate digits.\n- Remove entered keypad digits from the frontend `vista-keypad-key` DOM event detail.\n- Report the partition `control_enabled` attribute from actual bridge configuration instead of a hard-coded false value.\n- Close every SQLite event-journal connection deterministically and add regression coverage for connection closure.\n- Add card `0.3.21`; keypad function keys A-D remain intentionally unmapped pending explicit action and hold semantics.\n\n'''
if "## 0.2.6-rc.8" not in changelog:
    changelog = changelog.replace("# Changelog\n\n", "# Changelog\n\n" + entry, 1)
write("vista128_bridge/CHANGELOG.md", changelog)

# Version references in user-facing documentation.
for path in ("README.md", "vista128_bridge/README.md", "frontend/README.md"):
    text = read(path)
    text = text.replace("0.2.6-rc.7", "0.2.6-rc.8")
    text = text.replace("v0.2.6-rc.7", "v0.2.6-rc.8")
    text = text.replace("0.3.20", "0.3.21")
    text = text.replace("RC7", "RC8")
    write(path, text)

# Update the stale read-only/status wording where it survived generic version replacement.
for path in ("README.md", "vista128_bridge/README.md"):
    text = read(path)
    text = text.replace(
        "Read-only. Tested on a VISTA-128BPT. Keypad display polling is enabled. Arm, disarm, and keypad control commands are not sent to the panel.",
        "Tested for monitoring on a VISTA-128BPT. Experimental keypad and native alarm control are available only when explicitly enabled; physical write validation is still pending.",
    )
    text = text.replace(
        "is read-only. It has been developed and tested on a VISTA-128BPT. Keypad display polling is enabled. Arm, disarm, and keypad-control commands are not sent to the panel.",
        "has experimental opt-in panel control. Monitoring has been tested on a VISTA-128BPT; physical validation of keypad and native write commands is still pending.",
    )
    write(path, text)

# Frontend README no longer calls the card read-only unconditionally.
text = read("frontend/README.md")
text = text.replace(
    "The card is **read-only** while Vista Turbo RS232 remains read-only. Keys depress visually, but no panel command is sent.",
    "The card remains monitor-only by default. When both bridge keypad control and the card's **Keypad input** option are explicitly enabled, `0-9`, `*`, and `#` are sent through the bridge. A-D remain unmapped.",
)
write("frontend/README.md", text)

# Protocol/operator notes.
docs = read("vista128_bridge/DOCS.md")
section = '''\n## Automation availability and control gating\n\nEach new panel TCP session starts with control availability unknown. A valid structured VISTA transaction that completes with `08OK` is sufficient to mark the automation interface available with source `inferred`; an explicit `08XN` changes the source to `explicit`. If `08XF` Communication Off is received, control is blocked for the remainder of that TCP session and pending control requests are discarded. Ordinary `08OK` replies do not override an `08XF` block. A new TCP session clears the block and begins again at unknown.\n\nHome Assistant exposes both **Automation Interface Available** and **Automation Availability Source** diagnostics. The latter can be `unknown`, `inferred`, `explicit`, `communication_off`, or `offline`.\n\nThe keypad entity exposes both semantic `trouble` and `trouble_led_raw`. The raw value is the literal KD lamp bit from the currently displayed page. The semantic value also considers authoritative zone Check/Trouble state and validated event-derived trouble families because the VISTA rotates display pages and can report a raw TROUBLE bit of zero while another trouble page remains active.\n\nPOWER is conservative. `1B` and explicit AC-loss display text establish AC loss; `1C` establishes AC restore. A quiet KD page is not treated as positive AC evidence. After a communication gap POWER may therefore remain unknown until fresh AC evidence is received.\n'''
if "## Automation availability and control gating" not in docs:
    anchor = "## Startup synchronization\n"
    if anchor not in docs:
        raise SystemExit("DOCS startup synchronization anchor missing")
    docs = docs.replace(anchor, section + "\n" + anchor, 1)
write("vista128_bridge/DOCS.md", docs)

# RC8 release notes. Keep release/rc.json on RC7 until final CI passes.
release_notes = '''# Vista Turbo RS232 0.2.6 RC8\n\nRC8 is the control-readiness hardening release based on live VISTA-128BPT observations. Experimental panel control remains disabled by default.\n\n## Automation availability\n\nThe test panel remained fully responsive to AS, ZS, and KD transactions while never surfacing an observed `08XN`. RC8 therefore begins each TCP session at unknown and infers automation availability after a successful structured VISTA transaction completes with `08OK`. The new **Automation Availability Source** diagnostic reports `inferred` in this case.\n\nAn explicit `08XF` Communication Off remains authoritative: it blocks control and discards queued control requests for the rest of that TCP session. Later ordinary `08OK` replies cannot override the block. Explicit `08XN` restores availability and reports source `explicit`; a new TCP session resets the state to unknown.\n\n## Trouble and power semantics\n\nLive captures showed the VISTA rotating between `ZONES IN TROUBLE`, specific `TRBL` pages, and other pages while the raw KD TROUBLE lamp bit changed with the displayed page. RC8 therefore exposes semantic `trouble` separately from `trouble_led_raw`. Semantic TROUBLE remains active while authoritative zone trouble or validated trouble events remain active.\n\nPOWER no longer becomes ON merely because a KD page has a false TROUBLE lamp bit. `1B` or explicit AC-loss display text establishes AC loss; `1C` establishes AC restore. POWER may remain unknown after reconnect until fresh AC evidence is received.\n\n## Control safety\n\n- Virtual keypad presses use MQTT QoS 0 and retain false so an at-least-once MQTT retry cannot duplicate a code digit.\n- The frontend no longer includes the entered digit in the `vista-keypad-key` DOM event detail.\n- Both `D` and `N` authoritative arming snapshots clear stale alarm tokens.\n- Partition `control_enabled` diagnostics now reflect the actual App configuration.\n- Existing session-generation, queue-expiry, retained-message rejection, credential redaction, `08XF` blocking, and native post-command AS verification remain in place.\n\n## Event journal\n\nSQLite event-journal operations now close every connection deterministically. The regression suite verifies connection closure, eliminating the ResourceWarnings found during RC8 validation.\n\n## Frontend\n\nCard `0.3.21` contains the keypad QoS and credential-surface hardening. Use:\n\n```text\n/local/vista-keypad-card.js?v=0.3.21\n```\n\n## Test status\n\nThe complete backend and Chromium regression suites pass. Monitoring behavior has real-panel validation. The documented KS and native arm/disarm write commands are still awaiting their first physical VISTA-128BPT test, so all three control App options continue to default to false.\n'''
write("release/0.2.6-rc.8.md", release_notes)

print("RC8 package metadata applied")
