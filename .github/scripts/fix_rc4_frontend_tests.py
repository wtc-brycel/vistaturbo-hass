from pathlib import Path

p = Path("frontend/tests/audio.spec.mjs")
s = p.read_text()
s = s.replace(
    '''  await updateStates(page, { keypad: { fire_alarm: true, silenced: false, trouble: true, ready: false } });
  await updateStates(page, { keypad: { fire_alarm: true, silenced: true, trouble: true, ready: false } });
''',
    '''  await updateStates(page, { keypad: { fire_alarm: true, silenced: false, trouble: true, ready: false, sound_mode: "fire" } });
  await updateStates(page, { keypad: { fire_alarm: true, silenced: true, trouble: true, ready: false, sound_mode: "none" } });
''',
    1,
)
p.write_text(s)
