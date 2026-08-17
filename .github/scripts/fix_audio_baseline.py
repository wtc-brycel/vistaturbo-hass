from pathlib import Path

p = Path("frontend/vista-keypad-card.js")
s = p.read_text()
s = s.replace(
    '''    this._feedbackSnapshot = null;\n    this._lastRenderSignature = null;\n    this._syncFeedback();\n    this._render();''',
    '''    this._feedbackSnapshot = null;\n    this._lastRenderSignature = null;\n    if (this._hass) this._syncFeedback(true);\n    this._render();''',
    1,
)
s = s.replace(
    '''  _syncFeedback() {\n    const sound = this._config?.sound ?? {};''',
    '''  _syncFeedback(suppressOneShots = false) {\n    const sound = this._config?.sound ?? {};''',
    1,
)
s = s.replace(
    '''    this._feedbackSnapshot = current;\n    if (!previous || !sound.enabled || !sound.state_sounds || loop) return;''',
    '''    this._feedbackSnapshot = current;\n    if (suppressOneShots || !previous || !sound.enabled || !sound.state_sounds || loop) return;''',
    1,
)
p.write_text(s)

p = Path("frontend/tests/audio.spec.mjs")
s = p.read_text()
marker = '''test("configured chime sequence change produces one chime profile", async ({ page }) => {\n'''
test = '''test("retained chime sequence establishes a baseline without replaying a stale chime", async ({ page }) => {\n  await mountAudioCard(page);\n  await installAudioSpies(page);\n  await page.evaluate(({ entity, alarmEntity, auxEntity }) => {\n    const card = document.getElementById("card");\n    card._feedbackSnapshot = null;\n    card.hass = {\n      themes: { darkMode: false },\n      states: {\n        [entity]: {\n          state: "FAULT 027 / FRONT DOOR",\n          attributes: {\n            ...card._hass.states[entity].attributes,\n            ready: false,\n            chime_sequence: 9,\n            chime_zone: 27,\n            chime_descriptor: "FRONT DOOR",\n          },\n        },\n        [alarmEntity]: { state: "disarmed", attributes: {} },\n        [auxEntity]: { state: "off", attributes: {} },\n      },\n    };\n  }, { entity: ENTITY, alarmEntity: ALARM, auxEntity: AUX });\n  const calls = await page.evaluate(() => window.__audioCalls.play);\n  expect(calls).toEqual([]);\n});\n\n'''
if marker not in s:
    raise SystemExit("missing audio test anchor")
s = s.replace(marker, test + marker, 1)
p.write_text(s)
