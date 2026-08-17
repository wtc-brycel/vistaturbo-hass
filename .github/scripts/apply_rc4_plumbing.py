from pathlib import Path


def replace_once(path: str, old: str, new: str, label: str) -> None:
    p = Path(path)
    text = p.read_text()
    if old not in text:
        raise SystemExit(f"missing anchor: {label}")
    p.write_text(text.replace(old, new, 1))


# Explicit audible alarm families. Generic ALARM_START_CODES intentionally also
# contains silent, duress, fire, supervisory and auxiliary conditions, so it is
# not safe to drive a burglary speaker from the generic partition trigger.
p = Path("vista128_bridge/app/vista_bridge/event_codes.py")
s = p.read_text()
anchor = '''ALARM_START_CODES = set(ALARM_RESTORE_TO_START.values())

ZONE_EVENT_TRANSITIONS'''
replacement = '''ALARM_START_CODES = set(ALARM_RESTORE_TO_START.values())

BURGLARY_RESTORE_TO_START = {
    "32": "31",  # audible alarm
    "42": "41",  # perimeter alarm
    "52": "51",  # interior alarm
}
BURGLARY_START_CODES = set(BURGLARY_RESTORE_TO_START.values())

AUXILIARY_RESTORE_TO_START = {
    "B2": "B1",  # 24 hour auxiliary alarm
}
AUXILIARY_START_CODES = set(AUXILIARY_RESTORE_TO_START.values())

ZONE_EVENT_TRANSITIONS'''
if anchor not in s:
    raise SystemExit("missing anchor: audible event families")
p.write_text(s.replace(anchor, replacement, 1))

# State machine: retain distinct native audible classes and publish them on the
# keypad entity. They are connection-derived and therefore invalidated after a
# TCP gap just like FIRE/SUPERVISORY/POWER.
p = Path("vista128_bridge/app/vista_bridge/state.py")
s = p.read_text()
s = s.replace(
    '''    ALARM_RESTORE_TO_START,
    ALARM_START_CODES,
    DISARM_EVENT_CODES,
''',
    '''    ALARM_RESTORE_TO_START,
    ALARM_START_CODES,
    AUXILIARY_RESTORE_TO_START,
    AUXILIARY_START_CODES,
    BURGLARY_RESTORE_TO_START,
    BURGLARY_START_CODES,
    DISARM_EVENT_CODES,
''',
    1,
)
s = s.replace(
    '''    active_supervisory_tokens: set[str] = field(default_factory=set)
    fire_silenced: bool = False
''',
    '''    active_supervisory_tokens: set[str] = field(default_factory=set)
    active_burglary_tokens: set[str] = field(default_factory=set)
    active_auxiliary_tokens: set[str] = field(default_factory=set)
    fire_silenced: bool = False
''',
    1,
)
s = s.replace(
    '''    def supervisory_active(self) -> bool:
        return bool(self.active_supervisory_tokens)

    def attributes(self) -> dict:
''',
    '''    def supervisory_active(self) -> bool:
        return bool(self.active_supervisory_tokens)

    @property
    def burglary_alarm_active(self) -> bool:
        return bool(self.active_burglary_tokens)

    @property
    def auxiliary_alarm_active(self) -> bool:
        return bool(self.active_auxiliary_tokens)

    def attributes(self) -> dict:
''',
    1,
)
s = s.replace(
    '''            "supervisory_active": self.supervisory_active,
            "control_enabled": False,
''',
    '''            "supervisory_active": self.supervisory_active,
            "burglary_alarm_active": self.burglary_alarm_active,
            "auxiliary_alarm_active": self.auxiliary_alarm_active,
            "control_enabled": False,
''',
    1,
)
s = s.replace(
    '''    supervisory_led: bool | None = None
    chime_sequence: int = 0
''',
    '''    supervisory_led: bool | None = None
    burglary_alarm_led: bool | None = None
    auxiliary_alarm_led: bool | None = None
    chime_sequence: int = 0
''',
    1,
)
s = s.replace(
    '''    @property
    def ha_state(self) -> str:
        lines = [line.rstrip() for line in (self.line_1, self.line_2)]
        return " | ".join(line for line in lines if line) or "blank"

    def attributes(self) -> dict:
''',
    '''    @property
    def ha_state(self) -> str:
        lines = [line.rstrip() for line in (self.line_1, self.line_2)]
        return " | ".join(line for line in lines if line) or "blank"

    @property
    def sound_mode(self) -> str:
        if self.fire_alarm_led is True and self.silenced_led is not True:
            return "fire"
        if self.burglary_alarm_led is True:
            return "burglary"
        if self.auxiliary_alarm_led is True:
            return "auxiliary"
        if any(
            value is None
            for value in (
                self.fire_alarm_led,
                self.burglary_alarm_led,
                self.auxiliary_alarm_led,
            )
        ):
            return "unknown"
        return "none"

    def attributes(self) -> dict:
''',
    1,
)
s = s.replace(
    '''            "supervisory": self.supervisory_led,
            "chime_sequence": self.chime_sequence,
''',
    '''            "supervisory": self.supervisory_led,
            "burglary_alarm": self.burglary_alarm_led,
            "auxiliary_alarm": self.auxiliary_alarm_led,
            "sound_mode": self.sound_mode,
            "chime_sequence": self.chime_sequence,
''',
    1,
)
s = s.replace(
    '''            partition.active_supervisory_tokens.clear()
            partition.fire_silenced = False
''',
    '''            partition.active_supervisory_tokens.clear()
            partition.active_burglary_tokens.clear()
            partition.active_auxiliary_tokens.clear()
            partition.fire_silenced = False
''',
    1,
)
s = s.replace(
    '''            keypad.silenced_led = None
            keypad.supervisory_led = None
''',
    '''            keypad.silenced_led = None
            keypad.supervisory_led = None
            keypad.burglary_alarm_led = None
            keypad.auxiliary_alarm_led = None
''',
    1,
)
# Normal READY is authoritative evidence that no local burglary or auxiliary
# alarm is sounding, and safely reconciles unknown state after reconnect.
s = s.replace(
    '''        if partition_state.supervisory_active or explicit_supervisory:
            keypad.supervisory_led = True
        elif normal_ready:
            keypad.supervisory_led = False

        return keypad
''',
    '''        if partition_state.supervisory_active or explicit_supervisory:
            keypad.supervisory_led = True
        elif normal_ready:
            keypad.supervisory_led = False

        if partition_state.burglary_alarm_active:
            keypad.burglary_alarm_led = True
        elif normal_ready:
            keypad.burglary_alarm_led = False

        if partition_state.auxiliary_alarm_active:
            keypad.auxiliary_alarm_led = True
        elif normal_ready:
            keypad.auxiliary_alarm_led = False

        return keypad
''',
    1,
)
s = s.replace(
    '''        self._apply_partition_event(event, changed_zones, changed_partitions)
        self._apply_cr2_annunciator_event(event, changed_partitions)
        return changed_zones, changed_partitions
''',
    '''        self._apply_partition_event(event, changed_zones, changed_partitions)
        self._apply_cr2_annunciator_event(event, changed_partitions)
        self._apply_audible_alarm_event(event, changed_partitions)
        return changed_zones, changed_partitions
''',
    1,
)
method_anchor = '''    def _set_ac_power(self, value: bool) -> None:
'''
method = '''    def _apply_audible_alarm_event(
        self,
        event: SystemEvent,
        changed_partitions: set[int],
    ) -> None:
        partition = self.partitions.get(event.partition)
        keypad = self.keypads.get(event.partition)
        if partition is None:
            return

        token_prefix = f"{event.zone:03d}:"

        if event.code in BURGLARY_START_CODES:
            token = token_prefix + event.code
            if token not in partition.active_burglary_tokens:
                partition.active_burglary_tokens.add(token)
                changed_partitions.add(event.partition)
            if keypad is not None:
                keypad.burglary_alarm_led = True

        burglary_start = BURGLARY_RESTORE_TO_START.get(event.code)
        if burglary_start is not None:
            token = token_prefix + burglary_start
            if token in partition.active_burglary_tokens:
                partition.active_burglary_tokens.remove(token)
                changed_partitions.add(event.partition)
            if keypad is not None and not partition.active_burglary_tokens:
                keypad.burglary_alarm_led = False

        if event.code in AUXILIARY_START_CODES:
            token = token_prefix + event.code
            if token not in partition.active_auxiliary_tokens:
                partition.active_auxiliary_tokens.add(token)
                changed_partitions.add(event.partition)
            if keypad is not None:
                keypad.auxiliary_alarm_led = True

        auxiliary_start = AUXILIARY_RESTORE_TO_START.get(event.code)
        if auxiliary_start is not None:
            token = token_prefix + auxiliary_start
            if token in partition.active_auxiliary_tokens:
                partition.active_auxiliary_tokens.remove(token)
                changed_partitions.add(event.partition)
            if keypad is not None and not partition.active_auxiliary_tokens:
                keypad.auxiliary_alarm_led = False

        if event.code in DISARM_EVENT_CODES:
            if partition.active_burglary_tokens:
                partition.active_burglary_tokens.clear()
                changed_partitions.add(event.partition)
            if keypad is not None:
                keypad.burglary_alarm_led = False

'''
if method_anchor not in s:
    raise SystemExit("missing anchor: audible state method")
s = s.replace(method_anchor, method + method_anchor, 1)
p.write_text(s)

# Chime policy: only a genuine false->faulted transition, on a configured zone,
# after arming state is known, and only while the resolved partition is disarmed.
p = Path("vista128_bridge/app/vista_bridge/message_handler.py")
s = p.read_text()
s = s.replace(
    '''        event = parse_system_event(data)
        if event is None:
            return
        changed_zones, changed_partitions = self.state.apply_system_event(event)
''',
    '''        event = parse_system_event(data)
        if event is None:
            return
        zone_before = self.state.zones.get(event.zone)
        zone_was_faulted = bool(zone_before and zone_before.faulted)
        changed_zones, changed_partitions = self.state.apply_system_event(event)
''',
    1,
)
old = '''        if event.code == "F5" and event.zone in self.settings.keypad.chime_zones:
            keypad = self.state.record_chime(event.partition, event.zone, received_at)
            if keypad is not None:
                LOG.info(
                    "Chime zone fault: zone=%03d partition=%d sequence=%d",
                    event.zone,
                    keypad.partition,
                    keypad.chime_sequence,
                )
'''
new = '''        zone_after = self.state.zones.get(event.zone)
        resolved_partition = event.partition
        if resolved_partition not in self.state.partitions and zone_after is not None:
            resolved_partition = zone_after.partition
        partition_state = self.state.partitions.get(resolved_partition)
        should_chime = (
            event.code == "F5"
            and event.zone in self.settings.keypad.chime_zones
            and not zone_was_faulted
            and zone_after is not None
            and zone_after.faulted
            and self.state.arming_initialized
            and partition_state is not None
            and partition_state.raw_mode in {"D", "N"}
        )
        if should_chime:
            keypad = self.state.record_chime(resolved_partition, event.zone, received_at)
            if keypad is not None:
                LOG.info(
                    "Chime zone fault: zone=%03d partition=%d sequence=%d",
                    event.zone,
                    keypad.partition,
                    keypad.chime_sequence,
                )
'''
if old not in s:
    raise SystemExit("missing anchor: chime gating")
p.write_text(s.replace(old, new, 1))

# Backend regression coverage.
p = Path("vista128_bridge/tests/test_message_handler.py")
s = p.read_text()
# Existing configured-chime test must establish authoritative disarmed state.
s = s.replace(
    '''        self.state.zones[27].partition = 1
        self.state.zones[27].descriptor = "GLASS BREAK KITCHEN"
''',
    '''        self.state.zones[27].partition = 1
        self.state.zones[27].descriptor = "GLASS BREAK KITCHEN"
        self.state.arming_initialized = True
        self.state.partitions[1].raw_mode = "D"
''',
    1,
)
marker = '''    def test_unlisted_fault_zone_does_not_chime(self):
'''
extra = '''    def test_duplicate_fault_event_does_not_chime_twice(self):
        handler = ProtocolMessageHandler(
            make_settings(chime_zones=(27,)), self.state, self.mqtt, self.printer, self.sync
        )
        self.state.zones[27].partition = 1
        self.state.arming_initialized = True
        self.state.partitions[1].raw_mode = "D"
        packet = b"1BnqF502700012123150826007B"
        handler.handle("system_event", packet, "2026-08-16T13:23:00-04:00")
        handler.handle("system_event", packet, "2026-08-16T13:23:01-04:00")
        self.assertEqual(self.state.keypads[1].chime_sequence, 1)

    def test_configured_fault_does_not_chime_while_armed(self):
        handler = ProtocolMessageHandler(
            make_settings(chime_zones=(27,)), self.state, self.mqtt, self.printer, self.sync
        )
        self.state.zones[27].partition = 1
        self.state.arming_initialized = True
        self.state.partitions[1].raw_mode = "A"
        handler.handle(
            "system_event",
            b"1BnqF502700012123150826007B",
            "2026-08-16T13:23:00-04:00",
        )
        self.assertEqual(self.state.keypads[1].chime_sequence, 0)

    def test_configured_fault_waits_for_authoritative_arming_state(self):
        handler = ProtocolMessageHandler(
            make_settings(chime_zones=(27,)), self.state, self.mqtt, self.printer, self.sync
        )
        self.state.zones[27].partition = 1
        handler.handle(
            "system_event",
            b"1BnqF502700012123150826007B",
            "2026-08-16T13:23:00-04:00",
        )
        self.assertEqual(self.state.keypads[1].chime_sequence, 0)

'''
if marker not in s:
    raise SystemExit("missing anchor: message handler extra tests")
s = s.replace(marker, extra + marker, 1)
p.write_text(s)

p = Path("vista128_bridge/tests/test_state.py")
s = p.read_text()
marker = '''    def test_supervisory_start_restore_drives_cr2_annunciator(self):
'''
extra = '''    def test_audible_alarm_families_drive_native_keypad_sound_state(self):
        keypad = self.state.keypads[1]
        keypad.initialized = True
        keypad.fire_alarm_led = False
        keypad.silenced_led = False
        keypad.burglary_alarm_led = False
        keypad.auxiliary_alarm_led = False

        self.state.apply_system_event(SystemEvent("31", "Audible Alarm", 10, 0, 1, ""))
        self.assertTrue(keypad.burglary_alarm_led)
        self.assertEqual(keypad.sound_mode, "burglary")
        self.state.apply_system_event(SystemEvent("32", "Audible Alarm Restore", 10, 0, 1, ""))
        self.assertFalse(keypad.burglary_alarm_led)

        self.state.apply_system_event(SystemEvent("B1", "24 Hour Auxiliary Alarm", 11, 0, 1, ""))
        self.assertTrue(keypad.auxiliary_alarm_led)
        self.assertEqual(keypad.sound_mode, "auxiliary")
        self.state.apply_system_event(SystemEvent("B2", "24 Hour Auxiliary Alarm Restore", 11, 0, 1, ""))
        self.assertFalse(keypad.auxiliary_alarm_led)
        self.assertEqual(keypad.sound_mode, "none")

    def test_silent_and_duress_events_do_not_drive_burglary_speaker_state(self):
        keypad = self.state.keypads[1]
        keypad.burglary_alarm_led = False
        keypad.auxiliary_alarm_led = False
        keypad.fire_alarm_led = False
        keypad.silenced_led = False
        self.state.apply_system_event(SystemEvent("21", "Silent Alarm", 12, 0, 1, ""))
        self.state.apply_system_event(SystemEvent("11", "Duress Alarm", 0, 1, 1, ""))
        self.assertFalse(keypad.burglary_alarm_led)
        self.assertEqual(keypad.sound_mode, "none")

'''
if marker not in s:
    raise SystemExit("missing anchor: state audible tests")
s = s.replace(marker, extra + marker, 1)
p.write_text(s)

p = Path("vista128_bridge/tests/test_readiness.py")
s = p.read_text()
marker = '''    def test_reconnect_discards_event_derived_cr2_state(self):
'''
# Extend existing reconnect test with native audible state by inserting assertions
# after its reset call if an exact anchor is present; otherwise add a focused test.
focused = '''    def test_reconnect_invalidates_native_audible_state(self):
        keypad = self.state.keypads[1]
        keypad.initialized = True
        keypad.fire_alarm_led = False
        keypad.silenced_led = False
        keypad.burglary_alarm_led = True
        keypad.auxiliary_alarm_led = False
        self.state.partitions[1].active_burglary_tokens.add("010:31")
        self.state.reset_connection_derived_annunciators()
        self.assertIsNone(keypad.burglary_alarm_led)
        self.assertIsNone(keypad.auxiliary_alarm_led)
        self.assertEqual(keypad.sound_mode, "unknown")
        self.assertFalse(self.state.partitions[1].active_burglary_tokens)

'''
if marker not in s:
    raise SystemExit("missing anchor: readiness audible test")
s = s.replace(marker, focused + marker, 1)
p.write_text(s)

# Frontend: native audible state, availability guard, restart-safe chime counter.
p = Path("frontend/vista-keypad-card.js")
s = p.read_text()
s = s.replace(
    '''      a.supervisory ?? null,
      a.chime_sequence ?? null,
''',
    '''      a.supervisory ?? null,
      a.burglary_alarm ?? null,
      a.auxiliary_alarm ?? null,
      a.sound_mode ?? null,
      a.chime_sequence ?? null,
''',
    1,
)
s = s.replace(
    '''      supervisory: display.supervisory,
      chimeSequence: display.chimeSequence,
''',
    '''      supervisory: display.supervisory,
      burglaryAlarm: display.burglaryAlarm,
      auxiliaryAlarm: display.auxiliaryAlarm,
      soundMode: display.soundMode,
      chimeSequence: display.chimeSequence,
''',
    1,
)
old = '''    let loop = null;
    if (sound.enabled && sound.state_sounds) {
      if (display.fireAlarm === true && display.silenced !== true) {
        loop = "fire";
      } else if (this._entityActive(sound.alarm_entity, ["triggered", "alarm", "on"])) {
        loop = "burglary";
      } else if (this._entityActive(sound.aux_entity)) {
        loop = "auxiliary";
      }
    }
'''
new = '''    let loop = null;
    if (sound.enabled && sound.state_sounds && display.available) {
      if (display.soundMode === "fire" || (display.soundMode === null && display.fireAlarm === true && display.silenced !== true)) {
        loop = "fire";
      } else if (display.soundMode === "burglary" || display.burglaryAlarm === true) {
        loop = "burglary";
      } else if (display.soundMode === "auxiliary" || display.auxiliaryAlarm === true) {
        loop = "auxiliary";
      } else if (this._entityActive(sound.alarm_entity, ["triggered", "alarm", "on"])) {
        loop = "burglary";
      } else if (this._entityActive(sound.aux_entity)) {
        loop = "auxiliary";
      }
    }
'''
if old not in s:
    raise SystemExit("missing anchor: frontend loop selection")
s = s.replace(old, new, 1)
s = s.replace(
    '''    if (sound.chime !== false && current.chimeSequence !== previous.chimeSequence) {
''',
    '''    if (sound.chime !== false && current.chimeSequence > previous.chimeSequence) {
''',
    1,
)
s = s.replace(
    '''        supervisory: null,
        chimeSequence: 0,
''',
    '''        supervisory: null,
        burglaryAlarm: null,
        auxiliaryAlarm: null,
        soundMode: "unknown",
        chimeSequence: 0,
''',
    1,
)
s = s.replace(
    '''      supervisory: indicator("supervisory", "supervisory", null),
      chimeSequence: Number(a.chime_sequence ?? 0) || 0,
''',
    '''      supervisory: indicator("supervisory", "supervisory", null),
      burglaryAlarm: a.burglary_alarm === null || a.burglary_alarm === undefined ? null : boolValue(a.burglary_alarm),
      auxiliaryAlarm: a.auxiliary_alarm === null || a.auxiliary_alarm === undefined ? null : boolValue(a.auxiliary_alarm),
      soundMode: ["none", "fire", "burglary", "auxiliary", "unknown"].includes(String(a.sound_mode ?? "").toLowerCase())
        ? String(a.sound_mode).toLowerCase()
        : null,
      chimeSequence: Number(a.chime_sequence ?? 0) || 0,
''',
    1,
)
p.write_text(s)

# Browser regression tests.
p = Path("frontend/tests/audio.spec.mjs")
s = p.read_text()
s = s.replace(
    '''      supervisory: false,
      chime_sequence: 0,
''',
    '''      supervisory: false,
      burglary_alarm: false,
      auxiliary_alarm: false,
      sound_mode: "none",
      chime_sequence: 0,
''',
    1,
)
# mountAudioCard has a second literal keypad attributes block.
s = s.replace(
    '''            power: true, fire_alarm: false, silenced: false, supervisory: false,
            chime_sequence: 0, chime_zone: null, chime_descriptor: "",
''',
    '''            power: true, fire_alarm: false, silenced: false, supervisory: false,
            burglary_alarm: false, auxiliary_alarm: false, sound_mode: "none",
            chime_sequence: 0, chime_zone: null, chime_descriptor: "",
''',
    1,
)
marker = '''test("fire loop has priority and silencing stops it", async ({ page }) => {
'''
extra = '''test("chime sequence rollback after bridge restart does not replay a chime", async ({ page }) => {
  await mountAudioCard(page);
  await installAudioSpies(page);
  await updateStates(page, { keypad: { chime_sequence: 9 } });
  windowThis: {
  }
  await page.evaluate(() => { window.__audioCalls.play = []; });
  await updateStates(page, { keypad: { chime_sequence: 0 } });
  const calls = await page.evaluate(() => window.__audioCalls.play);
  expect(calls).toEqual([]);
});

test("native burglary and auxiliary keypad attributes select continuous profiles", async ({ page }) => {
  await mountAudioCard(page);
  await installAudioSpies(page);
  await updateStates(page, { keypad: { burglary_alarm: true, sound_mode: "burglary" } });
  await updateStates(page, { keypad: { burglary_alarm: false, auxiliary_alarm: true, sound_mode: "auxiliary" } });
  const loops = await page.evaluate(() => window.__audioCalls.loops);
  expect(loops).toContain("burglary");
  expect(loops.at(-1)).toBe("auxiliary");
});

test("unavailable keypad state stops continuous native audio", async ({ page }) => {
  await mountAudioCard(page);
  await installAudioSpies(page);
  await updateStates(page, { keypad: { fire_alarm: true, silenced: false, sound_mode: "fire" } });
  await page.evaluate((entity) => {
    const card = document.getElementById("card");
    card.hass = {
      ...card._hass,
      states: {
        ...card._hass.states,
        [entity]: { ...card._hass.states[entity], state: "unavailable" },
      },
    };
  }, ENTITY);
  const loops = await page.evaluate(() => window.__audioCalls.loops);
  expect(loops.at(-1)).toBe(null);
});

'''
if marker not in s:
    raise SystemExit("missing anchor: frontend extra audio tests")
s = s.replace(marker, extra + marker, 1)
# Remove an intentionally impossible JS label-like block from the generated test.
s = s.replace('''  windowThis: {\n  }\n''', '')
p.write_text(s)

# Update demo so all three visual models are part of the checked-in package.
p = Path("frontend/demo.html")
s = p.read_text()
s = s.replace("Card 0.3.15 development preview.", "Card 0.3.17 development preview with optional audio feedback and First Alert style.", 1)
s = s.replace(
    '''  <section class="panel"><h2>6160 — AUTO</h2><p>same adaptive renderer; A/B/C/D compact function keys</p><div class="demo-card"><vista-keypad-card id="k6160-auto"></vista-keypad-card></div></section>
''',
    '''  <section class="panel"><h2>6160 — AUTO</h2><p>same adaptive renderer; A/B/C/D compact function keys</p><div class="demo-card"><vista-keypad-card id="k6160-auto"></vista-keypad-card></div></section>
  <section class="panel"><h2>First Alert style — AUTO</h2><p>horizontal wide / portrait narrow</p><div class="demo-card"><vista-keypad-card id="fa-auto"></vista-keypad-card></div></section>
''',
    1,
)
s = s.replace(
    ''' ["k6160-auto",{model:"6160",layout:"auto"}],
''',
    ''' ["k6160-auto",{model:"6160",layout:"auto"}],
 ["fa-auto",{model:"firstalert",layout:"auto"}],
''',
    1,
)
p.write_text(s)

# Ship the richer interactive simulator as a first-class repository/release artifact.
Path("frontend/simulator.html").write_text(r'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"><title>Vista Keypad Simulator</title>
<style>
:root{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;--bg:#e9ecef;--panel:#fff;--text:#17191b;--muted:#60666b;--border:#c9ced2}body{margin:0;background:var(--bg);color:var(--text)}body.dark{--bg:#111315;--panel:#202326;--text:#f1f3f4;--muted:#aab0b5;--border:#454b50}.bar{position:sticky;top:0;z-index:20;padding:8px;background:var(--panel);border-bottom:1px solid var(--border)}.row{display:flex;gap:5px;overflow:auto;margin:4px 0}.row button{min-height:34px;padding:6px 9px;border:1px solid var(--border);border-radius:7px;background:var(--panel);color:var(--text);white-space:nowrap}.main{padding:10px 4px}.stage{width:min(100%,940px);margin:auto}.status,.panel{width:min(100%,760px);margin:10px auto;padding:9px;border:1px solid var(--border);border-radius:9px;background:var(--panel)}.status{font:11px/1.4 ui-monospace,monospace;color:var(--muted)}.scenarios{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:5px}.scenarios button{min-height:42px;border:1px solid var(--border);border-radius:7px;background:var(--panel);color:var(--text)}@media(max-width:520px){.scenarios{grid-template-columns:repeat(2,minmax(0,1fr))}}
</style><script>if(!customElements.get("ha-card"))customElements.define("ha-card",class extends HTMLElement{});</script><script src="./vista-keypad-card.js"></script></head>
<body><div class="bar"><b>Vista Keypad 0.3.17 simulator</b><div class="row"><button data-model="6160cr2">6160CR-2</button><button data-model="6160">6160</button><button data-model="firstalert">FIRST ALERT</button><button id="day">DAY</button><button id="night">NIGHT</button><button id="audio">ENABLE AUDIO</button><button id="stop">STOP SOUND</button></div><div class="row"><button data-layout="auto">AUTO</button><button data-layout="physical">PHYSICAL</button><button data-layout="compact">COMPACT</button><button data-width="940">940</button><button data-width="520">520</button><button data-width="390">390</button><button data-width="320">320</button></div></div>
<div class="main"><div class="stage" id="stage"><vista-keypad-card id="card"></vista-keypad-card></div><div class="status" id="status"></div><div class="panel"><div class="scenarios"><button data-sim="normal">NORMAL</button><button data-sim="chime">CHIME Z27</button><button data-sim="trouble">TROUBLE</button><button data-sim="supervisory">SUPERVISORY</button><button data-sim="fire">FIRE</button><button data-sim="silenced">FIRE SILENCED</button><button data-sim="burglar">BURGLAR</button><button data-sim="aux">AUX HI-LO</button><button data-sim="acloss">AC LOSS</button></div></div></div>
<script>
const E="sensor.vista_partition_1_keypad",A="alarm_control_panel.test_burglar",X="binary_sensor.test_aux",card=document.getElementById("card"),stage=document.getElementById("stage"),status=document.getElementById("status");let model="firstalert",layout="auto",dark=false,seq=0,alarm="disarmed",aux="off";
const base=()=>({state:"P1 DISARMED | READY TO ARM",attributes:{line_1:"P1   DISARMED   ",line_2:"READY TO ARM    ",ready:true,armed:false,trouble:false,backlight:true,power:true,fire_alarm:false,silenced:false,supervisory:false,burglary_alarm:false,auxiliary_alarm:false,sound_mode:"none",chime_sequence:seq,chime_zone:null,chime_descriptor:""}});let ks=base();
function hass(){return{themes:{darkMode:dark},states:{[E]:ks,[A]:{state:alarm,attributes:{}},[X]:{state:aux,attributes:{}}}}}function cfg(){return{entity:E,model,layout,case_color:"auto",read_only:true,sound:{enabled:true,keypress:true,state_sounds:true,alarm_entity:A,aux_entity:X},haptic:{enabled:true,keypress_ms:10}}}function refresh(reconfig=false){if(reconfig)card.setConfig(cfg());card.hass=hass();setTimeout(()=>{const a=ks.attributes;status.textContent=`model=${model} layout=${layout} audio=${card._audio?.ctx?.state??"not-created"} sound_mode=${a.sound_mode} chime=${a.chime_sequence}`},30)}
function sim(n){alarm="disarmed";aux="off";ks=base();const a=ks.attributes;if(n==="chime"){seq++;ks=base();Object.assign(ks.attributes,{line_1:"FAULT 027       ",line_2:"FRONT DOOR      ",ready:false,chime_sequence:seq,chime_zone:27,chime_descriptor:"FRONT DOOR"})}else if(n==="trouble")Object.assign(a,{line_1:"TROUBLE         ",line_2:"CHECK ZONE 005  ",ready:false,trouble:true});else if(n==="supervisory")Object.assign(a,{line_1:"SUPERVISORY     ",line_2:"SPRINKLER       ",ready:false,trouble:true,supervisory:true});else if(n==="fire")Object.assign(a,{line_1:"FIRE ALARM      ",line_2:"SMOKE DETECTOR  ",ready:false,trouble:true,fire_alarm:true,sound_mode:"fire"});else if(n==="silenced")Object.assign(a,{line_1:"FIRE ALARM      ",line_2:"SILENCED        ",ready:false,trouble:true,fire_alarm:true,silenced:true,sound_mode:"none"});else if(n==="burglar")Object.assign(a,{line_1:"*** ALARM ***   ",line_2:"BURGLARY        ",ready:false,armed:true,burglary_alarm:true,sound_mode:"burglary"});else if(n==="aux")Object.assign(a,{line_1:"AUXILIARY ALARM ",line_2:"                ",ready:false,trouble:true,auxiliary_alarm:true,sound_mode:"auxiliary"});else if(n==="acloss")Object.assign(a,{line_1:"AC LOSS         ",line_2:"CHECK POWER     ",ready:false,trouble:true,power:false});refresh()}
document.querySelectorAll("[data-model]").forEach(b=>b.onclick=()=>{model=b.dataset.model;refresh(true)});document.querySelectorAll("[data-layout]").forEach(b=>b.onclick=()=>{layout=b.dataset.layout;refresh(true)});document.querySelectorAll("[data-width]").forEach(b=>b.onclick=()=>{stage.style.width=`min(100%,${b.dataset.width}px)`;window.dispatchEvent(new Event("resize"))});document.querySelectorAll("[data-sim]").forEach(b=>b.onclick=()=>sim(b.dataset.sim));day.onclick=()=>{dark=false;document.body.classList.remove("dark");refresh()};night.onclick=()=>{dark=true;document.body.classList.add("dark");refresh()};audio.onclick=async()=>{await card._audio.unlock();card._updateAudioFlag?.();refresh()};stop.onclick=()=>{card._audio.stopAll();ks=base();alarm="disarmed";aux="off";refresh()};refresh(true);
</script></body></html>''')

# Release workflow now attaches the interactive simulator alongside the card.
p = Path(".github/workflows/publish-release-candidate.yml")
s = p.read_text()
s = s.replace(
    '''          gh release create "$tag" \\
            frontend/vista-keypad-card.js#vista-keypad-card.js \\
''',
    '''          gh release create "$tag" \\
            frontend/vista-keypad-card.js#vista-keypad-card.js \\
            frontend/simulator.html#vista-keypad-simulator.html \\
''',
    1,
)
p.write_text(s)
