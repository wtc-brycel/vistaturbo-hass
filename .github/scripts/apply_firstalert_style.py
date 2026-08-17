from pathlib import Path

CARD = Path("frontend/vista-keypad-card.js")
text = CARD.read_text()


def replace_once(old: str, new: str, label: str) -> None:
    global text
    if old not in text:
        raise SystemExit(f"missing anchor: {label}")
    text = text.replace(old, new, 1)


replace_once(
    'const VISTA_KEYPAD_CARD_VERSION = "0.3.16";',
    'const VISTA_KEYPAD_CARD_VERSION = "0.3.17";',
    "card version",
)

replace_once(
    '  "6160": "6160",\n};',
    '  "6160": "6160",\n  "firstalert": "firstalert",\n  "first-alert": "firstalert",\n  "first_alert": "firstalert",\n  "fa": "firstalert",\n};',
    "model aliases",
)

replace_once(
    '  "6160": { day: "white", night: "dark" },\n};',
    '  "6160": { day: "white", night: "dark" },\n  "firstalert": { day: "white", night: "dark" },\n};',
    "auto case defaults",
)

number_anchor = '''const NUMBER_KEYS = [
  ["1", "OFF"], ["2", "AWAY"], ["3", "STAY"],
  ["4", "MAX"], ["5", "TEST"], ["6", "BYPASS"],
  ["7", "INSTANT"], ["8", "CODE"], ["9", "CHIME"],
  ["*", "READY"], ["0", ""], ["#", ""],
];
'''
firstalert_keys = number_anchor + '''
const FIRST_ALERT_NUMBER_KEYS = [
  ["1", "OFF"], ["2", "SELECT"], ["3", "SCROLL"],
  ["4", "MAX"], ["5", "TEST"], ["6", "BYPASS"],
  ["7", "INSTANT"], ["8", "CODE"], ["9", "CHIME"],
  ["*", "READY"], ["0", ""], ["#", ""],
];
'''
replace_once(number_anchor, firstalert_keys, "First Alert numeric legends")

replace_once(
    '  "6160": ["", "", "", ""],\n};',
    '  "6160": ["", "", "", ""],\n  "firstalert": ["A", "B", "C", "D"],\n};',
    "First Alert function keys",
)

profile_marker = '\n};\n\nconst LAYOUT_MODES = new Set(["auto", "physical", "compact"]);'
if profile_marker not in text:
    raise SystemExit("missing anchor: model profiles end")
firstalert_profile = '''
  "firstalert": {
    compactFunctionKeys: ["A", "B", "C", "D"],
    numberKeys: FIRST_ALERT_NUMBER_KEYS,
    compactIndicators: [
      { label: "PWR", state: "power", className: "power", flash: "power" },
      { label: "READY", state: "ready", className: "ready", flash: "ready" },
      { label: "ARMED", state: "armed", className: "armed", flash: "armed" },
      { label: "FIRE", state: "fireAlarm", className: "fire-alarm", flash: "fire_alarm" },
      { label: "SIL", state: "silenced", className: "silenced", flash: "silenced" },
      { label: "SUPV", state: "supervisory", className: "supervisory", flash: "supervisory" },
      { label: "TRBL", state: "trouble", className: "trouble", flash: null },
    ],
  },
'''
text = text.replace(profile_marker, firstalert_profile + profile_marker, 1)

replace_once(
    '    this._feedbackSnapshot = null;\n  }',
    '    this._feedbackSnapshot = null;\n    this._audioUnlockHandler = null;\n  }',
    "audio unlock field",
)

replace_once(
    '  connectedCallback() {\n    this._installThemeListener();\n  }',
    '  connectedCallback() {\n    this._installThemeListener();\n    this._syncAudioUnlockListener();\n  }',
    "connected audio unlock",
)

replace_once(
    '    clearTimeout(this._pressTimer);\n    this._audio.stopAll();',
    '    clearTimeout(this._pressTimer);\n    this._removeAudioUnlockListener();\n    this._audio.stopAll();',
    "disconnect audio unlock cleanup",
)

audio_methods_anchor = '''  static getStubConfig() {
'''
audio_methods = '''  _audioUnlocked() {
    return this._audio.ctx?.state === "running";
  }

  _removeAudioUnlockListener() {
    if (!this._audioUnlockHandler || typeof window === "undefined") return;
    window.removeEventListener("pointerdown", this._audioUnlockHandler, true);
    window.removeEventListener("keydown", this._audioUnlockHandler, true);
    this._audioUnlockHandler = null;
  }

  _updateAudioFlag() {
    const flag = this.shadowRoot?.getElementById("audio-lock-flag");
    if (!flag) return;
    flag.hidden = !this._config?.sound?.enabled || this._audioUnlocked();
  }

  _syncAudioUnlockListener() {
    if (!this._config?.sound?.enabled || this._audioUnlocked()) {
      this._removeAudioUnlockListener();
      this._updateAudioFlag();
      return;
    }
    if (!this._audioUnlockHandler && typeof window !== "undefined") {
      this._audioUnlockHandler = () => {
        this._audio.unlock().then(() => {
          if (this._audioUnlocked()) this._removeAudioUnlockListener();
          this._updateAudioFlag();
        }).catch(() => {});
      };
      window.addEventListener("pointerdown", this._audioUnlockHandler, true);
      window.addEventListener("keydown", this._audioUnlockHandler, true);
    }
    this._updateAudioFlag();
  }

'''
replace_once(audio_methods_anchor, audio_methods + audio_methods_anchor, "audio unlock methods")

replace_once(
    '    if (!model) throw new Error("model must be 6160cr2 or 6160");',
    '    if (!model) throw new Error("model must be 6160cr2, 6160, or firstalert");',
    "model validation message",
)

replace_once(
    '    if (this._hass) this._syncFeedback(true);\n    this._render();',
    '    if (this._hass) this._syncFeedback(true);\n    this._syncAudioUnlockListener();\n    this._render();',
    "setConfig audio unlock",
)

replace_once(
    '    const sound = this._config?.sound ?? {};\n    const display = this._config ? this._displayState() : null;',
    '    const sound = this._config?.sound ?? {};\n    this._syncAudioUnlockListener();\n    const display = this._config ? this._displayState() : null;',
    "feedback audio unlock",
)

replace_once(
    '    const numeric = NUMBER_KEYS.map(([key, legend], i) => {',
    '    const numberKeys = MODEL_PROFILES[model]?.numberKeys ?? NUMBER_KEYS;\n    const numeric = numberKeys.map(([key, legend], i) => {',
    "model-specific numeric keys",
)

firstalert_methods_anchor = '''  _renderCompact(model, display) {
'''
firstalert_methods = '''  _firstAlertStatus(display) {
    const indicators = MODEL_PROFILES.firstalert.compactIndicators;
    return `<div class="fa-status" aria-label="Keypad status">
      ${indicators.map((item) => this._compactIndicator(item, display)).join("")}
    </div>`;
  }

  _firstAlertControls(portrait = false) {
    const functions = FUNCTION_IDS.map(
      (_, i) => `<div class="fa-function-slot">${this._functionKey(i, "firstalert", true)}</div>`
    ).join("");
    const numeric = FIRST_ALERT_NUMBER_KEYS.map(
      ([key, legend]) => `<div class="fa-number-slot">${this._numberKey(key, legend)}</div>`
    ).join("");
    return `<div class="fa-control-layout ${portrait ? "fa-controls-portrait" : "fa-controls-wide"}">
      <div class="fa-function-bank">${functions}</div>
      <div class="fa-numeric-grid">${numeric}</div>
    </div>`;
  }

  _renderFirstAlert(display, portrait = false) {
    const resolvedCaseColor = this._resolvedCaseColor("firstalert");
    const caseClass = `case-${resolvedCaseColor}`;
    const orientation = portrait ? "firstalert-portrait" : "firstalert-wide";
    return `<div class="firstalert-shell ${orientation} ${caseClass}" data-model="firstalert" data-case-color="${escapeHtml(resolvedCaseColor)}">
      <div class="fa-lcd-panel">
        <canvas class="matrix-lcd"
          data-lcd-style="firstalert"
          data-line1="${escapeHtml(display.line1)}"
          data-line2="${escapeHtml(display.line2)}"
          data-lit="${display.backlight && display.available ? "1" : "0"}"></canvas>
      </div>
      ${this._firstAlertStatus(display)}
      ${this._firstAlertControls(portrait)}
      <div class="fa-brand" aria-hidden="true">FIRST ALERT STYLE</div>
    </div>`;
  }

'''
replace_once(firstalert_methods_anchor, firstalert_methods + firstalert_methods_anchor, "First Alert render methods")

replace_once(
    '  _renderCompact(model, display) {\n    const resolvedCaseColor = this._resolvedCaseColor(model);',
    '  _renderCompact(model, display) {\n    if (model === "firstalert") return this._renderFirstAlert(display, true);\n    const resolvedCaseColor = this._resolvedCaseColor(model);',
    "First Alert compact renderer",
)

replace_once(
    '  _renderPhysical(model, display) {\n    const isCR2 = model === "6160cr2";',
    '  _renderPhysical(model, display) {\n    if (model === "firstalert") return this._renderFirstAlert(display, false);\n    const isCR2 = model === "6160cr2";',
    "First Alert physical renderer",
)

replace_once(
    '      .keypad-shell, .keypad-shell *, .compact-shell, .compact-shell * { box-sizing:border-box; }',
    '      .keypad-shell, .keypad-shell *, .compact-shell, .compact-shell *, .firstalert-shell, .firstalert-shell * { box-sizing:border-box; }',
    "First Alert box sizing",
)

css_anchor = '''      .read-only-note {
'''
firstalert_css = '''      /* First Alert-inspired skin: horizontal when wide, portrait when compact. */
      .firstalert-shell {
        position:relative;
        width:100%;
        max-width:940px;
        min-width:0;
        overflow:hidden;
        user-select:none;
        -webkit-tap-highlight-color:transparent;
        border:1px solid;
        filter:drop-shadow(0 7px 10px rgba(0,0,0,.22));
        font-family:"Arial Narrow","Roboto Condensed",Arial,sans-serif;
      }

      .firstalert-wide {
        aspect-ratio:1.68/1;
        padding:clamp(16px,2.6cqw,28px) clamp(18px,3.4cqw,34px) clamp(13px,2.0cqw,22px);
        border-radius:clamp(18px,3.0cqw,30px);
      }

      .firstalert-portrait {
        width:min(100%,520px);
        padding:14px 14px 12px;
        border-radius:24px;
      }

      .fa-lcd-panel {
        padding:5px;
        background:linear-gradient(180deg,#343a40,#11161b 15%,#080b0e 100%);
        border-radius:12px;
        box-shadow:inset 0 2px 4px rgba(0,0,0,.78),0 1px 1px rgba(255,255,255,.2);
      }

      .firstalert-wide .fa-lcd-panel {
        width:74%;
        height:25%;
        margin:0 auto;
      }

      .firstalert-portrait .fa-lcd-panel {
        width:100%;
        height:96px;
      }

      .fa-lcd-panel .matrix-lcd {
        border-radius:6px;
      }

      .fa-status {
        display:grid;
        align-items:center;
        gap:6px;
      }

      .firstalert-wide .fa-status {
        width:82%;
        grid-template-columns:repeat(7,minmax(0,1fr));
        margin:clamp(7px,1.15cqw,12px) auto clamp(8px,1.3cqw,14px);
      }

      .firstalert-portrait .fa-status {
        grid-template-columns:repeat(4,minmax(0,1fr));
        margin:9px 0 10px;
      }

      .fa-status .compact-indicator.led-row {
        min-height:28px;
        min-width:0;
        display:flex;
        align-items:center;
        justify-content:center;
        gap:5px;
        padding:3px 4px;
        border:0;
        border-radius:8px;
        background:rgba(0,0,0,.045);
      }

      .firstalert-shell.case-dark .fa-status .compact-indicator.led-row,
      .firstalert-shell.case-red .fa-status .compact-indicator.led-row {
        background:rgba(0,0,0,.14);
      }

      .fa-status .compact-indicator .led {
        width:11px;
        height:11px;
        border-radius:50%;
        outline-width:1px;
        outline-offset:1px;
      }

      .fa-status .compact-indicator-label {
        font-size:clamp(8px,1.45cqw,11px);
        font-weight:700;
      }

      .fa-control-layout {
        width:100%;
        min-width:0;
      }

      .fa-controls-wide {
        display:grid;
        grid-template-columns:minmax(62px,16%) minmax(0,1fr);
        align-items:stretch;
        gap:clamp(12px,2.1cqw,22px);
        width:68%;
        margin:0 auto;
      }

      .fa-controls-wide .fa-function-bank {
        display:grid;
        grid-template-rows:repeat(4,1fr);
        gap:clamp(5px,.8cqw,9px);
      }

      .fa-controls-wide .fa-numeric-grid {
        display:grid;
        grid-template-columns:repeat(3,minmax(0,1fr));
        grid-template-rows:repeat(4,clamp(38px,5.25cqw,52px));
        gap:clamp(5px,.8cqw,9px) clamp(7px,1.2cqw,12px);
      }

      .fa-controls-portrait {
        display:flex;
        flex-direction:column;
      }

      .fa-controls-portrait .fa-numeric-grid {
        order:1;
        display:grid;
        grid-template-columns:repeat(3,minmax(0,1fr));
        grid-template-rows:repeat(4,52px);
        gap:8px;
      }

      .fa-controls-portrait .fa-function-bank {
        order:2;
        display:grid;
        grid-template-columns:repeat(4,minmax(0,1fr));
        gap:8px;
        margin-top:10px;
      }

      .firstalert-shell .physical-key {
        width:100%;
        height:100%;
        min-height:44px;
        padding:0 5px;
        border:1px solid #7d7f80;
        border-radius:999px;
        background:linear-gradient(180deg,#fff 0%,#f0f0ef 28%,#d8d9d8 100%);
        color:#404345;
        box-shadow:0 2px 3px rgba(0,0,0,.20),inset 0 1px 1px rgba(255,255,255,.88);
      }

      .firstalert-shell.case-dark .physical-key {
        border-color:#64696d;
        background:linear-gradient(180deg,#6b7074 0%,#4d5256 30%,#34383b 100%);
        color:#f5f6f6;
      }

      .firstalert-shell.case-red .physical-key {
        border-color:#992027;
        background:linear-gradient(180deg,#fff 0%,#f2e9e8 28%,#dcc6c5 100%);
        color:#421a1d;
      }

      .firstalert-shell .fa-function-bank .physical-key {
        aspect-ratio:1/1;
        width:min(100%,54px);
        min-width:44px;
        justify-self:center;
        border-radius:50%;
      }

      .firstalert-shell .function-label {
        font-size:clamp(12px,2.0cqw,18px);
        font-weight:800;
      }

      .firstalert-shell .number-main {
        font-size:clamp(20px,3.8cqw,31px);
        transform:none;
        font-weight:600;
      }

      .firstalert-shell .number-legend {
        font-size:clamp(7px,1.15cqw,10px);
        font-style:normal;
        font-weight:600;
      }

      .firstalert-portrait .number-main {
        font-size:26px;
      }

      .firstalert-portrait .number-legend {
        font-size:9px;
      }

      .firstalert-portrait .fa-function-bank .physical-key {
        width:min(100%,52px);
        height:52px;
      }

      .fa-brand {
        margin-top:clamp(7px,1.1cqw,12px);
        text-align:center;
        font:800 clamp(9px,1.5cqw,13px)/1 sans-serif;
        letter-spacing:.06em;
        opacity:.28;
      }

      .audio-lock-flag {
        position:absolute;
        z-index:30;
        top:5px;
        right:5px;
        min-height:24px;
        padding:3px 7px;
        border:1px solid rgba(150,108,0,.45);
        border-radius:999px;
        background:rgba(255,202,40,.94);
        color:#332700;
        box-shadow:0 1px 3px rgba(0,0,0,.18);
        font:800 9px/1 sans-serif;
        letter-spacing:.03em;
        cursor:pointer;
      }

      .audio-lock-flag[hidden] { display:none !important; }

'''
replace_once(css_anchor, firstalert_css + css_anchor, "First Alert CSS")

replace_once(
    '    const lit = canvas.dataset.lit === "1";\n\n    const bg = ctx.createLinearGradient(0, 0, 0, h);\n    if (lit) {\n      bg.addColorStop(0, "#b2ed54");\n      bg.addColorStop(.5, "#9ee247");\n      bg.addColorStop(1, "#88cb38");\n    } else {\n      bg.addColorStop(0, "#7f9570");\n      bg.addColorStop(1, "#687a5e");\n    }',
    '    const lit = canvas.dataset.lit === "1";\n    const firstAlertLcd = canvas.dataset.lcdStyle === "firstalert";\n\n    const bg = ctx.createLinearGradient(0, 0, 0, h);\n    if (firstAlertLcd && lit) {\n      bg.addColorStop(0, "#e7eff6");\n      bg.addColorStop(.5, "#d7e3ed");\n      bg.addColorStop(1, "#c7d5e0");\n    } else if (firstAlertLcd) {\n      bg.addColorStop(0, "#9ca8b0");\n      bg.addColorStop(1, "#808b92");\n    } else if (lit) {\n      bg.addColorStop(0, "#b2ed54");\n      bg.addColorStop(.5, "#9ee247");\n      bg.addColorStop(1, "#88cb38");\n    } else {\n      bg.addColorStop(0, "#7f9570");\n      bg.addColorStop(1, "#687a5e");\n    }',
    "First Alert LCD background",
)

replace_once(
    '    ctx.fillStyle = lit ? "rgba(33,80,23,.055)" : "rgba(25,42,24,.065)";',
    '    ctx.fillStyle = firstAlertLcd\n      ? (lit ? "rgba(34,54,70,.035)" : "rgba(30,42,50,.05)")\n      : (lit ? "rgba(33,80,23,.055)" : "rgba(25,42,24,.065)");',
    "First Alert LCD grid",
)

replace_once(
    '    ctx.fillStyle = lit ? "#17341a" : "#253126";',
    '    ctx.fillStyle = firstAlertLcd\n      ? (lit ? "#2d3944" : "#29343b")\n      : (lit ? "#17341a" : "#253126");',
    "First Alert LCD text",
)

render_anchor = '''      <div class="layout-host ${layoutClass}">
'''
replace_once(
    render_anchor,
    '''      <div class="layout-host ${layoutClass}">
        ${this._config.sound?.enabled ? `<button id="audio-lock-flag" class="audio-lock-flag" type="button" aria-label="Keypad audio is locked. Tap to enable audio." ${this._audioUnlocked() ? "hidden" : ""}>AUDIO</button>` : ""}
''',
    "audio flag markup",
)

replace_once(
    '    requestAnimationFrame(() => {\n      this._drawLCD();\n      this._observeResize();\n    });',
    '    requestAnimationFrame(() => {\n      this._drawLCD();\n      this._observeResize();\n      this._updateAudioFlag();\n    });',
    "audio flag render update",
)

button_loop_anchor = '''    this.shadowRoot.querySelectorAll("button[data-key]").forEach((button) => {
'''
flag_handler = '''    const audioFlag = this.shadowRoot.getElementById("audio-lock-flag");
    audioFlag?.addEventListener("click", async (event) => {
      event.stopPropagation();
      await this._audio.unlock().catch(() => false);
      this._syncAudioUnlockListener();
      this._updateAudioFlag();
    });

'''
replace_once(button_loop_anchor, flag_handler + button_loop_anchor, "audio flag handler")

replace_once(
    '  description: "Physical VISTA keypad card with 6160CR-2 and 6160 skins.",',
    '  description: "Adaptive VISTA keypad card with 6160CR-2, 6160, and First Alert-inspired skins.",',
    "custom card description",
)

CARD.write_text(text)

# Extend render regression coverage for the third model.
render_test = Path("frontend/tests/render.spec.mjs")
r = render_test.read_text()
r += '''

test("First Alert AUTO uses horizontal wide and portrait narrow compositions", async ({ page }) => {
  await mountCard(page, { width: 760, model: "firstalert" });
  let state = await page.evaluate(() => {
    const root = document.getElementById("card").shadowRoot;
    const wide = root.querySelector(".layout-physical-view .firstalert-wide");
    const portrait = root.querySelector(".layout-compact-view .firstalert-portrait");
    const wr = wide.getBoundingClientRect();
    return {
      wideVisible: getComputedStyle(root.querySelector(".layout-physical-view")).display !== "none",
      portraitVisible: getComputedStyle(root.querySelector(".layout-compact-view")).display !== "none",
      wideRatio: wr.width / wr.height,
      statusCount: wide.querySelectorAll(".fa-status .compact-indicator").length,
      functionLabels: [...wide.querySelectorAll(".fa-function-bank .function-label")].map((el) => el.textContent.trim()),
      legends: [...wide.querySelectorAll(".fa-numeric-grid .number-legend")].map((el) => el.textContent.trim()),
    };
  });
  expect(state.wideVisible).toBe(true);
  expect(state.portraitVisible).toBe(false);
  expect(state.wideRatio).toBeGreaterThan(1.5);
  expect(state.statusCount).toBe(7);
  expect(state.functionLabels).toEqual(["A", "B", "C", "D"]);
  expect(state.legends).toContain("SELECT");
  expect(state.legends).toContain("SCROLL");

  await mountCard(page, { width: 390, model: "firstalert" });
  state = await page.evaluate(() => {
    const root = document.getElementById("card").shadowRoot;
    const portrait = root.querySelector(".layout-compact-view .firstalert-portrait");
    const pr = portrait.getBoundingClientRect();
    return {
      physicalVisible: getComputedStyle(root.querySelector(".layout-physical-view")).display !== "none",
      compactVisible: getComputedStyle(root.querySelector(".layout-compact-view")).display !== "none",
      portraitRatio: pr.height / pr.width,
      statusCount: portrait.querySelectorAll(".fa-status .compact-indicator").length,
      functionLabels: [...portrait.querySelectorAll(".fa-function-bank .function-label")].map((el) => el.textContent.trim()),
      keyCount: portrait.querySelectorAll("button[data-key]").length,
    };
  });
  expect(state.physicalVisible).toBe(false);
  expect(state.compactVisible).toBe(true);
  expect(state.portraitRatio).toBeGreaterThan(1.0);
  expect(state.statusCount).toBe(7);
  expect(state.functionLabels).toEqual(["A", "B", "C", "D"]);
  expect(state.keyCount).toBe(16);
});

test("First Alert AUTO case follows white day and dark night defaults", async ({ page }) => {
  await mountCard(page, { width: 390, model: "firstalert", dark: false });
  let caseColor = await page.evaluate(() => document.getElementById("card").shadowRoot.querySelector(".firstalert-portrait").dataset.caseColor);
  expect(caseColor).toBe("white");
  await mountCard(page, { width: 390, model: "firstalert", dark: true });
  caseColor = await page.evaluate(() => document.getElementById("card").shadowRoot.querySelector(".firstalert-portrait").dataset.caseColor);
  expect(caseColor).toBe("dark");
});
'''
render_test.write_text(r)

# Audio test: any dashboard interaction can unlock keypad audio; flag disappears.
audio_test = Path("frontend/tests/audio.spec.mjs")
a = audio_test.read_text()
a += '''

test("sound-enabled card exposes a small audio flag and any dashboard interaction can unlock it", async ({ page }) => {
  await mountAudioCard(page);
  await page.evaluate(() => {
    const card = document.getElementById("card");
    card._audio.ctx = { state: "suspended" };
    card._audio.unlock = async () => {
      card._audio.ctx = { state: "running" };
      return true;
    };
    card._syncAudioUnlockListener();
  });
  let hidden = await page.evaluate(() => document.getElementById("card").shadowRoot.getElementById("audio-lock-flag").hidden);
  expect(hidden).toBe(false);
  await page.dispatchEvent("body", "pointerdown");
  await page.waitForTimeout(20);
  hidden = await page.evaluate(() => document.getElementById("card").shadowRoot.getElementById("audio-lock-flag").hidden);
  expect(hidden).toBe(true);
});
'''
audio_test.write_text(a)

# Frontend docs.
readme = Path("frontend/README.md")
d = readme.read_text()
d = d.replace(
    "The card currently implements two keypad models:\n\n- `6160cr2`, modeled after the commercial fire/burglary keypad\n- `6160`, modeled after the standard alpha keypad",
    "The card currently implements three keypad models:\n\n- `6160cr2`, modeled after the commercial fire/burglary keypad\n- `6160`, modeled after the standard alpha keypad\n- `firstalert`, a First Alert-inspired adaptive skin that uses a horizontal composition when wide and a portrait composition when narrow",
    1,
)
insert = '''

## First Alert-inspired skin

`model: firstalert` is intentionally inspired by the supplied First Alert keypad examples rather than being a pixel-for-pixel reproduction. AUTO layout uses a low, horizontal keypad on wider Lovelace cards and a tall portrait keypad at the compact breakpoint. Both forms keep the same 16-key VISTA input surface: the numeric keys use First Alert-style secondary legends and the A/B/C/D function keys are presented as separate round function buttons. The same seven available CR-2 status fields are adapted into a compact First Alert-style indicator rail.

```yaml
type: custom:vista-keypad-card
entity: sensor.vista_partition_1_keypad
model: firstalert
layout: auto
```

The default AUTO enclosure mapping is white in light mode and dark in dark mode. Red remains available as an explicit case color.
'''
marker = "\n## Case colors and theme following\n"
if marker not in d:
    raise SystemExit("missing README First Alert insertion marker")
d = d.replace(marker, insert + marker, 1)
d = d.replace(
    "Audio autoplay restrictions still apply. A browser may require one user interaction before Web Audio can start; pressing a keypad key or explicitly unlocking audio satisfies that requirement in supported browsers. Haptic feedback is best-effort and only runs when the browser exposes `navigator.vibrate()`.",
    "Audio autoplay restrictions still apply. When sound is enabled, the card listens for the first pointer or keyboard interaction anywhere on the Lovelace page and uses that user gesture to unlock its AudioContext. A small `AUDIO` flag remains visible only while audio is still blocked and can be tapped as an explicit fallback. Haptic feedback is best-effort and only runs when the browser exposes `navigator.vibrate()`.",
    1,
)
readme.write_text(d)
