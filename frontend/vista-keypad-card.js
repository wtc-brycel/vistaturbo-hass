const VISTA_KEYPAD_CARD_VERSION = "0.1.1";

const MODEL_ALIASES = {
  "6160cr2": "6160cr2",
  "6160cr-2": "6160cr2",
  "cr2": "6160cr2",
  "6160": "6160",
};

const NUMBER_KEYS = [
  ["1", "OFF"], ["2", "AWAY"], ["3", "STAY"],
  ["4", "MAX"], ["5", "TEST"], ["6", "BYPASS"],
  ["7", "INSTANT"], ["8", "CODE"], ["9", "CHIME"],
  ["*", "READY"], ["0", ""], ["#", ""],
];

const DEFAULT_FUNCTION_KEYS = {
  "6160cr2": ["AWAY", "STAY", "POLICE", "PAGE"],
  "6160": ["STAY", "AWAY", "POLICE", "PAGE"],
};

const FUNCTION_IDS = ["a", "b", "c", "d"];

function boolValue(value, fallback = false) {
  if (value === true || value === "on" || value === "ON" || value === "true") return true;
  if (value === false || value === "off" || value === "OFF" || value === "false") return false;
  return fallback;
}

function exactLine(value) {
  const text = value == null ? "" : String(value);
  return text.slice(0, 16).padEnd(16, " ");
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function safeCssColor(value, fallback) {
  if (typeof value !== "string") return fallback;
  const text = value.trim();
  if (!text || /[;{}]/.test(text)) return fallback;
  return text;
}

class VistaKeypadCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._config = null;
    this._hass = null;
    this._lastKey = "";
    this._pressTimer = null;
  }

  static getStubConfig() {
    return {
      entity: "sensor.vista_partition_1_keypad",
      model: "6160cr2",
      read_only: true,
    };
  }

  setConfig(config) {
    if (!config || !config.entity) {
      throw new Error("vista-keypad-card requires an entity");
    }
    const model = MODEL_ALIASES[String(config.model || "6160cr2").toLowerCase()];
    if (!model) {
      throw new Error("model must be 6160cr2 or 6160");
    }
    this._config = {
      model,
      title: "",
      read_only: true,
      show_card_background: false,
      function_keys: {},
      indicators: {},
      case_label: model === "6160cr2" ? "FIRST ALERT" : "HONEYWELL",
      ...config,
      model,
    };
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  getCardSize() {
    return 7;
  }

  _entityState(entityId) {
    if (!entityId || !this._hass?.states) return null;
    return this._hass.states[entityId] || null;
  }

  _indicatorState(name, fallback = null) {
    const entityId = this._config?.indicators?.[name];
    const state = this._entityState(entityId);
    if (!state) return fallback;
    if (["unavailable", "unknown"].includes(state.state)) return null;
    return boolValue(state.state, fallback ?? false);
  }

  _displayState() {
    const state = this._entityState(this._config?.entity);
    if (!state) {
      return {
        available: false,
        line1: exactLine("VISTA TURBO"),
        line2: exactLine("ENTITY MISSING"),
        ready: false,
        armed: false,
        trouble: false,
        backlight: false,
        power: null,
        fireAlarm: null,
        silenced: null,
        supervisory: null,
        fireTrouble: null,
      };
    }

    const a = state.attributes || {};
    const unavailable = ["unavailable", "unknown"].includes(state.state);
    return {
      available: !unavailable,
      line1: exactLine(a.line_1 ?? (unavailable ? "VISTA OFFLINE" : state.state)),
      line2: exactLine(a.line_2 ?? ""),
      ready: boolValue(a.ready),
      armed: boolValue(a.armed),
      trouble: boolValue(a.trouble),
      backlight: boolValue(a.backlight, true),
      power: this._indicatorState("power", null),
      fireAlarm: this._indicatorState("fire_alarm", null),
      silenced: this._indicatorState("silenced", null),
      supervisory: this._indicatorState("supervisory", null),
      fireTrouble: this._indicatorState("fire_trouble", null),
    };
  }

  _keyButton(key, legend = "") {
    return `
      <button class="key" data-key="${escapeHtml(key)}" aria-label="${escapeHtml(key + (legend ? ` ${legend}` : ""))}">
        <span class="key-main">${escapeHtml(key)}</span>
        ${legend ? `<span class="key-legend">${escapeHtml(legend)}</span>` : ""}
      </button>`;
  }

  _functionDefinition(index, fallbackText) {
    const id = FUNCTION_IDS[index];
    const raw = this._config?.function_keys?.[id]
      ?? this._config?.function_keys?.[id.toUpperCase()]
      ?? this._config?.function_keys?.[String(index + 1)]
      ?? this._config?.function_keys?.[fallbackText.toLowerCase()];

    if (typeof raw === "string") {
      return { text: raw, background: null, color: null };
    }
    if (raw && typeof raw === "object") {
      return {
        text: raw.text ?? raw.label ?? fallbackText,
        background: raw.background ?? raw.background_color ?? null,
        color: raw.color ?? raw.text_color ?? null,
      };
    }
    return { text: fallbackText, background: null, color: null };
  }

  _functionKey(index, fallbackText) {
    const id = FUNCTION_IDS[index];
    const definition = this._functionDefinition(index, fallbackText);
    const background = safeCssColor(definition.background, "");
    const color = safeCssColor(definition.color, "");
    const styles = [
      background ? `--function-bg:${background}` : "",
      color ? `--function-color:${color}` : "",
    ].filter(Boolean).join(";");
    return `
      <button class="function-key" data-key="${id.toUpperCase()}" aria-label="${escapeHtml(definition.text)}"${styles ? ` style="${escapeHtml(styles)}"` : ""}>
        <span>${escapeHtml(definition.text)}</span>
      </button>`;
  }

  _led(label, state, className = "") {
    const status = state === null ? "unknown" : state ? "on" : "off";
    return `
      <div class="led-row ${className}" title="${escapeHtml(label)}: ${status}">
        <span class="led-label">${escapeHtml(label)}</span>
        <span class="led ${status}" aria-label="${escapeHtml(label)} ${status}"></span>
      </div>`;
  }

  _lcd(display) {
    const backlight = display.backlight && display.available ? "lit" : "dim";
    return `
      <div class="lcd-hood">
        <div class="lcd-bezel">
          <div class="lcd ${backlight}" role="status" aria-live="polite">
            <div>${escapeHtml(display.line1)}</div>
            <div>${escapeHtml(display.line2)}</div>
          </div>
        </div>
      </div>`;
  }

  _numericPad() {
    return `<div class="numeric-pad">${NUMBER_KEYS.map(([key, legend]) => this._keyButton(key, legend)).join("")}</div>`;
  }

  _functionPad(model) {
    const defaults = DEFAULT_FUNCTION_KEYS[model];
    return `<div class="function-pad">${defaults.map((label, index) => this._functionKey(index, label)).join("")}</div>`;
  }

  _speaker() {
    return `
      <div class="speaker" aria-hidden="true">
        <span></span><span></span><span></span><span></span>
      </div>`;
  }

  _renderStatusCR2(display) {
    return `
      <div class="status-stack cr2-status">
        <div class="status-blue">
          ${this._led("ARMED", display.armed, "armed")}
          ${this._led("READY", display.ready, "ready")}
          <span class="burg-glyph">●</span>
        </div>
        <div class="fire-block">
          ${this._led("POWER", display.power, "power")}
          ${this._led("FIRE ALARM", display.fireAlarm, "fire-alarm")}
          ${this._led("SILENCED", display.silenced, "silenced")}
          ${this._led("SUPERVISORY", display.supervisory, "supervisory")}
          ${this._led("TROUBLE", display.fireTrouble, "fire-trouble")}
          <span class="fire-bracket" aria-hidden="true"></span>
          <span class="fire-glyph" aria-hidden="true">♠</span>
        </div>
      </div>`;
  }

  _renderStatus6160(display) {
    return `
      <div class="status-stack residential-status">
        ${this._led("ARMED", display.armed, "armed")}
        ${this._led("READY", display.ready, "ready")}
      </div>`;
  }

  _renderLegacy(model, display) {
    const cr2 = model === "6160cr2";
    return `
      <div class="keypad-shell legacy-shell ${cr2 ? "cr2" : "k6160"}" data-model="${model}">
        <div class="plastic-texture" aria-hidden="true"></div>
        <div class="top-deck">
          ${this._speaker()}
          ${this._lcd(display)}
        </div>
        <div class="lower-deck">
          ${cr2 ? this._renderStatusCR2(display) : this._renderStatus6160(display)}
          <div class="controls">
            ${this._functionPad(model)}
            ${this._numericPad()}
          </div>
        </div>
        <div class="case-mark">${escapeHtml(this._config?.case_label || "")}</div>
      </div>`;
  }

  _styles() {
    const background = this._config?.show_card_background
      ? "var(--ha-card-background, var(--card-background-color))"
      : "transparent";
    const cardShadow = this._config?.show_card_background
      ? "var(--ha-card-box-shadow, none)"
      : "none";
    return `
      :host {
        display: block;
        --lcd-on: #a7db47;
        --lcd-on-deep: #90c83b;
        --lcd-ink: #172916;
        --plastic-red: #dc2028;
        --plastic-red-deep: #bd161d;
        --plastic-white: #f2f2ef;
        --plastic-white-deep: #d8d8d3;
        --key-face-top: #f3f1ee;
        --key-face-bottom: #cbc8c4;
        --key-edge: #6f6c68;
        --key-text: #171717;
        --key-w: 8.55cqw;
        --key-h: 5.05cqw;
        --key-gap-x: 2.05cqw;
        --key-gap-y: 1.45cqw;
      }

      ha-card {
        overflow: visible;
        background: ${background};
        box-shadow: ${cardShadow};
        border: ${this._config?.show_card_background ? "var(--ha-card-border-width, 0) solid var(--ha-card-border-color, transparent)" : "0"};
        padding: ${this._config?.show_card_background ? "18px" : "0"};
      }

      .wrap {
        container-type: inline-size;
        display: grid;
        width: 100%;
        gap: 10px;
        justify-items: center;
      }

      .card-title {
        width: min(100%, 900px);
        font: 500 16px/1.3 var(--paper-font-body1_-_font-family, sans-serif);
        color: var(--primary-text-color);
      }

      .keypad-shell,
      .keypad-shell * {
        box-sizing: border-box;
      }

      .keypad-shell {
        position: relative;
        width: min(100%, 900px);
        aspect-ratio: 1.53 / 1;
        min-height: 380px;
        user-select: none;
        -webkit-tap-highlight-color: transparent;
        color: var(--key-text);
        filter: drop-shadow(0 1.4cqw 1.25cqw rgba(0, 0, 0, .28));
        overflow: hidden;
      }

      .legacy-shell {
        padding: 4.2% 5.2% 4.2%;
        border-radius: 1.45cqw 1.45cqw .55cqw .55cqw;
        border: .18cqw solid;
        box-shadow:
          inset 0 .45cqw .55cqw rgba(255,255,255,.23),
          inset 0 -.55cqw .65cqw rgba(0,0,0,.12),
          inset .35cqw 0 .45cqw rgba(255,255,255,.08),
          inset -.25cqw 0 .38cqw rgba(0,0,0,.05);
      }

      .cr2 {
        background:
          linear-gradient(180deg, #ed333a 0%, var(--plastic-red) 33%, #d21d24 68%, var(--plastic-red-deep) 100%);
        border-color: #ab1318;
      }

      .k6160 {
        background:
          linear-gradient(180deg, #ffffff 0%, var(--plastic-white) 38%, #e7e7e3 70%, var(--plastic-white-deep) 100%);
        border-color: #c7c7c1;
      }

      .plastic-texture {
        pointer-events: none;
        position: absolute;
        inset: 0;
        opacity: .16;
        background:
          repeating-radial-gradient(circle at 0 0, rgba(255,255,255,.46) 0 .055cqw, transparent .065cqw .22cqw),
          linear-gradient(105deg, rgba(255,255,255,.19), transparent 28%, rgba(0,0,0,.045) 70%, transparent);
        mix-blend-mode: soft-light;
      }

      .legacy-shell::before {
        content: "";
        position: absolute;
        left: 1.2%;
        right: 1.2%;
        top: 1.3%;
        height: .5cqw;
        border-top: .13cqw solid rgba(255,255,255,.35);
        border-radius: 50%;
        opacity: .8;
      }

      .top-deck {
        display: grid;
        grid-template-columns: 22% 1fr;
        gap: 4.5%;
        height: 47%;
        align-items: center;
      }

      .speaker {
        display: grid;
        place-content: center;
        gap: 1.1cqw;
        height: 100%;
      }

      .speaker span {
        display: block;
        width: 10.6cqw;
        height: .53cqw;
        border-radius: 50%;
        background: linear-gradient(180deg, #090909, #262626);
        box-shadow:
          inset 0 .12cqw .15cqw rgba(255,255,255,.18),
          0 .12cqw .09cqw rgba(255,255,255,.08);
      }

      .lcd-hood {
        position: relative;
        width: 100%;
        padding: 3.0% 3.6% 3.3%;
        transform: translateY(-.1cqw);
        border-radius: .18cqw;
        box-shadow:
          0 .7cqw .7cqw rgba(70,0,0,.22),
          inset 0 .28cqw .32cqw rgba(255,255,255,.15),
          inset 0 -.24cqw .35cqw rgba(0,0,0,.08);
      }

      .cr2 .lcd-hood {
        background: linear-gradient(180deg, #e62a32, #d71d25);
      }

      .k6160 .lcd-hood {
        background: linear-gradient(180deg, #f8f8f5, #deded9);
        box-shadow:
          0 .68cqw .72cqw rgba(0,0,0,.14),
          inset 0 .28cqw .32cqw rgba(255,255,255,.85),
          inset 0 -.22cqw .3cqw rgba(0,0,0,.06);
      }

      .lcd-bezel {
        padding: .55cqw;
        background: rgba(31,34,26,.18);
        box-shadow:
          inset 0 .4cqw .6cqw rgba(0,0,0,.35),
          0 .16cqw .16cqw rgba(255,255,255,.18);
      }

      .lcd {
        position: relative;
        display: grid;
        align-content: center;
        min-height: 8.7cqw;
        padding: .72cqw 1.0cqw .58cqw;
        border: .1cqw solid rgba(25,45,19,.8);
        overflow: hidden;
        color: var(--lcd-ink);
        font-family: "Lucida Console", "Courier New", ui-monospace, monospace;
        font-size: clamp(17px, 3.8cqw, 36px);
        font-weight: 700;
        line-height: 1.02;
        letter-spacing: -.18cqw;
        white-space: pre;
        text-shadow: .05cqw 0 currentColor;
        box-shadow:
          inset 0 .38cqw .48cqw rgba(34,58,19,.22),
          inset 0 -.2cqw .3cqw rgba(255,255,255,.08);
      }

      .lcd::after {
        content: "";
        pointer-events: none;
        position: absolute;
        inset: 0;
        background:
          repeating-linear-gradient(0deg, rgba(20,55,16,.035) 0 .08cqw, transparent .08cqw .37cqw),
          repeating-linear-gradient(90deg, rgba(20,55,16,.028) 0 .06cqw, transparent .06cqw .39cqw);
        mix-blend-mode: multiply;
      }

      .lcd.lit {
        background:
          radial-gradient(ellipse at 50% 45%, rgba(211,255,115,.30), transparent 68%),
          linear-gradient(180deg, #aee154, var(--lcd-on-deep));
        filter: saturate(1.08) brightness(1.03);
      }

      .lcd.dim {
        color: #2c372b;
        background: linear-gradient(180deg, #84927a, #6e7b67);
        filter: saturate(.5) brightness(.88);
      }

      .lower-deck {
        display: grid;
        grid-template-columns: 31% 1fr;
        gap: 4.8%;
        height: 48%;
        align-items: center;
      }

      .status-stack {
        align-self: stretch;
        display: grid;
        align-content: center;
        position: relative;
      }

      .cr2-status {
        gap: 1.0cqw;
      }

      .status-blue {
        position: relative;
        width: 83%;
        padding: .85cqw 1.25cqw .75cqw 1.45cqw;
        border-radius: .55cqw;
        color: #eff1f2;
        background: linear-gradient(180deg, #2173a7, #155f92);
        box-shadow:
          inset 0 .16cqw .18cqw rgba(255,255,255,.2),
          inset 0 -.12cqw .16cqw rgba(0,0,0,.12);
      }

      .burg-glyph {
        position: absolute;
        right: -11%;
        top: 41%;
        color: rgba(255,255,255,.86);
        font-size: 1.1cqw;
      }

      .fire-block {
        position: relative;
        width: 84%;
        padding: .12cqw 1.3cqw 0 1.45cqw;
        color: rgba(255,235,235,.92);
      }

      .fire-bracket {
        position: absolute;
        right: 5%;
        top: 5%;
        bottom: 4%;
        width: 15%;
        border-right: .15cqw solid rgba(255,240,240,.92);
        border-top: .15cqw solid rgba(255,240,240,.92);
        border-bottom: .15cqw solid rgba(255,240,240,.92);
        border-radius: 0 .65cqw .65cqw 0;
      }

      .fire-glyph {
        position: absolute;
        right: -9%;
        top: 43%;
        transform: rotate(180deg);
        color: rgba(255,240,240,.9);
        font-size: 1.65cqw;
      }

      .residential-status {
        gap: 3.1cqw;
        padding-left: 2.7cqw;
        padding-bottom: 2.2cqw;
      }

      .led-row {
        display: grid;
        grid-template-columns: 1fr 2.6cqw;
        align-items: center;
        gap: .7cqw;
        min-height: 2.25cqw;
        font-family: Arial, Helvetica, sans-serif;
        font-size: clamp(9px, 1.72cqw, 16px);
        font-weight: 700;
        line-height: 1;
      }

      .status-blue .led-row,
      .fire-block .led-row {
        grid-template-columns: 1fr 2.7cqw;
      }

      .residential-status .led-row {
        grid-template-columns: 6.8cqw 2.65cqw;
        width: 11cqw;
        font-size: clamp(8px, 1.45cqw, 13px);
      }

      .led-label {
        white-space: nowrap;
      }

      .led {
        width: 2.35cqw;
        height: 1.0cqw;
        justify-self: center;
        border-radius: 50%;
        background: #4a4843;
        box-shadow:
          inset .2cqw .18cqw .24cqw rgba(0,0,0,.72),
          inset -.13cqw -.1cqw .14cqw rgba(255,255,255,.18),
          0 .08cqw .1cqw rgba(255,255,255,.1);
      }

      .led.on {
        background: radial-gradient(circle at 35% 28%, #f3ffc0 0%, #a9e23b 38%, #6c9626 72%, #465f1b 100%);
        box-shadow:
          0 0 .55cqw rgba(171,233,58,.84),
          inset .1cqw .08cqw .17cqw rgba(255,255,255,.68);
      }

      .fire-alarm .led.on,
      .silenced .led.on,
      .supervisory .led.on,
      .fire-trouble .led.on {
        background: radial-gradient(circle at 35% 28%, #ffd6cf 0%, #ef4a40 42%, #8e1713 78%);
        box-shadow: 0 0 .55cqw rgba(239,74,64,.82);
      }

      .power .led.on {
        background: radial-gradient(circle at 35% 28%, #fff4b8 0%, #efb944 44%, #8b6119 80%);
        box-shadow: 0 0 .5cqw rgba(239,185,68,.8);
      }

      .led.unknown {
        opacity: .5;
      }

      .controls {
        display: grid;
        grid-template-columns: var(--key-w) max-content;
        gap: 4.1cqw;
        align-items: center;
        justify-content: start;
        padding-top: .6cqw;
      }

      .function-pad,
      .numeric-pad {
        display: grid;
        grid-auto-rows: var(--key-h);
        row-gap: var(--key-gap-y);
        align-content: center;
      }

      .function-pad {
        grid-template-columns: var(--key-w);
      }

      .numeric-pad {
        grid-template-columns: repeat(3, var(--key-w));
        column-gap: var(--key-gap-x);
      }

      button {
        appearance: none;
        -webkit-appearance: none;
        margin: 0;
        padding: 0;
        width: var(--key-w);
        height: var(--key-h);
        min-width: var(--key-w);
        min-height: var(--key-h);
        max-width: var(--key-w);
        max-height: var(--key-h);
        border: .14cqw solid var(--key-edge);
        border-radius: .34cqw;
        color: var(--function-color, var(--key-text));
        background:
          linear-gradient(180deg,
            color-mix(in srgb, var(--function-bg, var(--key-face-top)) 92%, white 8%) 0%,
            var(--function-bg, #e9e7e3) 42%,
            color-mix(in srgb, var(--function-bg, var(--key-face-bottom)) 88%, black 12%) 100%);
        box-shadow:
          0 .27cqw .28cqw rgba(0,0,0,.23),
          inset 0 .16cqw .16cqw rgba(255,255,255,.88),
          inset 0 -.16cqw .17cqw rgba(0,0,0,.14),
          inset .12cqw 0 .12cqw rgba(255,255,255,.25);
        cursor: pointer;
        touch-action: manipulation;
        transition: transform .055s ease, box-shadow .055s ease, filter .1s ease;
      }

      .k6160 button {
        box-shadow:
          0 .27cqw .28cqw rgba(0,0,0,.17),
          inset 0 .16cqw .16cqw rgba(255,255,255,.95),
          inset 0 -.16cqw .17cqw rgba(0,0,0,.13),
          inset .12cqw 0 .12cqw rgba(255,255,255,.3);
      }

      button:active,
      button.pressed {
        transform: translateY(.2cqw);
        box-shadow:
          0 .07cqw .07cqw rgba(0,0,0,.18),
          inset 0 .2cqw .25cqw rgba(0,0,0,.18),
          inset 0 -.08cqw .12cqw rgba(255,255,255,.28);
        filter: brightness(.95);
      }

      .function-key {
        font-family: Arial, Helvetica, sans-serif;
        font-size: clamp(7px, 1.25cqw, 12px);
        font-weight: 800;
        line-height: 1;
      }

      .key {
        display: flex;
        align-items: center;
        justify-content: center;
        gap: .72cqw;
        font-family: Arial, Helvetica, sans-serif;
      }

      .key-main {
        font-size: clamp(15px, 2.75cqw, 27px);
        font-weight: 500;
        font-style: italic;
        line-height: 1;
      }

      .key-legend {
        font-size: clamp(6px, 1.05cqw, 10px);
        font-weight: 700;
        font-style: italic;
        line-height: 1;
      }

      .case-mark {
        position: absolute;
        right: 11.5%;
        bottom: 3.3%;
        padding: .36cqw .9cqw;
        border-radius: .28cqw;
        font: 800 clamp(8px, 1.25cqw, 12px)/1 Arial, Helvetica, sans-serif;
        letter-spacing: .045em;
        text-transform: uppercase;
      }

      .cr2 .case-mark {
        color: rgba(110,0,0,.25);
        border: .12cqw solid rgba(255,255,255,.1);
        text-shadow: 0 .1cqw rgba(255,255,255,.12);
        box-shadow: inset 0 .08cqw .11cqw rgba(90,0,0,.12);
      }

      .k6160 .case-mark {
        color: rgba(120,120,115,.25);
        text-shadow: 0 .1cqw rgba(255,255,255,.95);
        box-shadow: inset 0 .08cqw .1cqw rgba(110,110,105,.08);
      }

      .read-only-note {
        min-height: 18px;
        font: 500 12px/18px var(--paper-font-body1_-_font-family, sans-serif);
        color: var(--secondary-text-color);
        opacity: 0;
        transition: opacity .18s ease;
      }

      .read-only-note.show { opacity: 1; }

      @media (max-width: 650px) {
        .keypad-shell { min-height: 275px; }
      }

      @media (prefers-reduced-motion: reduce) {
        button,
        .read-only-note {
          transition: none;
        }
      }
    `;
  }

  _render() {
    if (!this.shadowRoot || !this._config) return;
    const display = this._displayState();
    const modelHtml = this._renderLegacy(this._config.model, display);
    this.shadowRoot.innerHTML = `
      <style>${this._styles()}</style>
      <ha-card>
        <div class="wrap">
          ${this._config.title ? `<div class="card-title">${escapeHtml(this._config.title)}</div>` : ""}
          ${modelHtml}
          <div class="read-only-note" id="read-only-note">Read-only monitoring. Keypad control is not enabled.</div>
        </div>
      </ha-card>`;

    this.shadowRoot.querySelectorAll("button[data-key]").forEach((button) => {
      button.addEventListener("pointerdown", () => button.classList.add("pressed"));
      button.addEventListener("pointerup", () => button.classList.remove("pressed"));
      button.addEventListener("pointercancel", () => button.classList.remove("pressed"));
      button.addEventListener("pointerleave", () => button.classList.remove("pressed"));
      button.addEventListener("click", (event) => this._handleKey(event.currentTarget));
    });
  }

  _handleKey(button) {
    const key = button?.dataset?.key || "";
    if (!key) return;
    this._lastKey = key;

    if (this._config.read_only !== false) {
      const note = this.shadowRoot.getElementById("read-only-note");
      if (note) {
        note.classList.add("show");
        clearTimeout(this._pressTimer);
        this._pressTimer = setTimeout(() => note.classList.remove("show"), 1400);
      }
      return;
    }

    this.dispatchEvent(new CustomEvent("vista-keypad-key", {
      bubbles: true,
      composed: true,
      detail: { key, entity: this._config.entity, model: this._config.model },
    }));
  }
}

if (!customElements.get("vista-keypad-card")) {
  customElements.define("vista-keypad-card", VistaKeypadCard);
}

window.customCards = window.customCards || [];
if (!window.customCards.some((card) => card.type === "vista-keypad-card")) {
  window.customCards.push({
    type: "vista-keypad-card",
    name: "Vista Keypad",
    description: "Physical keypad-style card for Vista Turbo HASS keypad display entities.",
    preview: false,
    documentationURL: "https://github.com/wtc-brycel/vistaturbo-hass/tree/main/frontend",
  });
}

console.info(`%c VISTA-KEYPAD-CARD %c v${VISTA_KEYPAD_CARD_VERSION} `, "color:#fff;background:#a91016;font-weight:700", "color:#111;background:#e6e6e2");
