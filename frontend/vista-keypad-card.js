const VISTA_KEYPAD_CARD_VERSION = "0.2.0";

const MODEL_ALIASES = {
  "6160cr2": "6160cr2",
  "6160cr-2": "6160cr2",
  cr2: "6160cr2",
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
  "6160": ["", "", "", ""],
};

const FUNCTION_IDS = ["a", "b", "c", "d"];

const LCD_FONT = {
  " ": ["00000","00000","00000","00000","00000","00000","00000"],
  "A": ["01110","10001","10001","11111","10001","10001","10001"],
  "B": ["11110","10001","10001","11110","10001","10001","11110"],
  "C": ["01111","10000","10000","10000","10000","10000","01111"],
  "D": ["11110","10001","10001","10001","10001","10001","11110"],
  "E": ["11111","10000","10000","11110","10000","10000","11111"],
  "F": ["11111","10000","10000","11110","10000","10000","10000"],
  "G": ["01111","10000","10000","10111","10001","10001","01111"],
  "H": ["10001","10001","10001","11111","10001","10001","10001"],
  "I": ["11111","00100","00100","00100","00100","00100","11111"],
  "J": ["00111","00010","00010","00010","10010","10010","01100"],
  "K": ["10001","10010","10100","11000","10100","10010","10001"],
  "L": ["10000","10000","10000","10000","10000","10000","11111"],
  "M": ["10001","11011","10101","10101","10001","10001","10001"],
  "N": ["10001","11001","10101","10011","10001","10001","10001"],
  "O": ["01110","10001","10001","10001","10001","10001","01110"],
  "P": ["11110","10001","10001","11110","10000","10000","10000"],
  "Q": ["01110","10001","10001","10001","10101","10010","01101"],
  "R": ["11110","10001","10001","11110","10100","10010","10001"],
  "S": ["01111","10000","10000","01110","00001","00001","11110"],
  "T": ["11111","00100","00100","00100","00100","00100","00100"],
  "U": ["10001","10001","10001","10001","10001","10001","01110"],
  "V": ["10001","10001","10001","10001","10001","01010","00100"],
  "W": ["10001","10001","10001","10101","10101","11011","10001"],
  "X": ["10001","10001","01010","00100","01010","10001","10001"],
  "Y": ["10001","10001","01010","00100","00100","00100","00100"],
  "Z": ["11111","00001","00010","00100","01000","10000","11111"],
  "0": ["01110","10001","10011","10101","11001","10001","01110"],
  "1": ["00100","01100","00100","00100","00100","00100","01110"],
  "2": ["01110","10001","00001","00010","00100","01000","11111"],
  "3": ["11110","00001","00001","01110","00001","00001","11110"],
  "4": ["00010","00110","01010","10010","11111","00010","00010"],
  "5": ["11111","10000","10000","11110","00001","00001","11110"],
  "6": ["01110","10000","10000","11110","10001","10001","01110"],
  "7": ["11111","00001","00010","00100","01000","01000","01000"],
  "8": ["01110","10001","10001","01110","10001","10001","01110"],
  "9": ["01110","10001","10001","01111","00001","00001","01110"],
  "-": ["00000","00000","00000","11111","00000","00000","00000"],
  "*": ["00000","10101","01110","11111","01110","10101","00000"],
  "/": ["00001","00010","00100","01000","10000","00000","00000"],
  ":": ["00000","00100","00100","00000","00100","00100","00000"],
  ".": ["00000","00000","00000","00000","00000","00110","00110"],
  "+": ["00000","00100","00100","11111","00100","00100","00000"],
  "#": ["01010","01010","11111","01010","11111","01010","01010"],
  "?": ["01110","10001","00001","00010","00100","00000","00100"],
};

function boolValue(value, fallback = false) {
  if (value === true || value === "on" || value === "ON" || value === "true") return true;
  if (value === false || value === "off" || value === "OFF" || value === "false") return false;
  return fallback;
}

function exactLine(value) {
  return String(value ?? "").slice(0, 16).padEnd(16, " ");
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function safeCssColor(value, fallback = "") {
  if (typeof value !== "string") return fallback;
  const text = value.trim();
  if (!text || text.length > 80 || /[;{}<>]/.test(text)) return fallback;
  return text;
}

class VistaKeypadAudio {
  constructor() {
    this.ctx = null;
  }

  async beep(config) {
    if (!config?.enabled) return;
    const AudioContextClass = window.AudioContext || window.webkitAudioContext;
    if (!AudioContextClass) return;
    if (!this.ctx) this.ctx = new AudioContextClass();
    if (this.ctx.state === "suspended") await this.ctx.resume();

    const now = this.ctx.currentTime;
    const duration = Math.max(0.02, Number(config.duration_ms ?? 65) / 1000);
    const frequency = Math.max(100, Number(config.frequency_hz ?? 1400));
    const volume = Math.min(0.2, Math.max(0, Number(config.volume ?? 0.035)));

    const osc = new OscillatorNode(this.ctx, { type: "square", frequency });
    const gain = new GainNode(this.ctx, { gain: 0 });
    osc.connect(gain);
    gain.connect(this.ctx.destination);
    gain.gain.setValueAtTime(0, now);
    gain.gain.linearRampToValueAtTime(volume, now + 0.002);
    gain.gain.setValueAtTime(volume, now + duration - 0.002);
    gain.gain.linearRampToValueAtTime(0, now + duration);
    osc.start(now);
    osc.stop(now + duration);
  }
}

class VistaKeypadCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._config = null;
    this._hass = null;
    this._pressTimer = null;
    this._audio = new VistaKeypadAudio();
  }

  static getStubConfig() {
    return {
      entity: "sensor.vista_partition_1_keypad",
      model: "6160cr2",
      read_only: true,
    };
  }

  setConfig(config) {
    if (!config?.entity) throw new Error("vista-keypad-card requires an entity");
    const model = MODEL_ALIASES[String(config.model || "6160cr2").toLowerCase()];
    if (!model) throw new Error("model must be 6160cr2 or 6160");

    this._config = {
      title: "",
      read_only: true,
      show_card_background: false,
      function_keys: {},
      indicators: {},
      sound: false,
      sound_frequency_hz: 1400,
      sound_duration_ms: 65,
      sound_volume: 0.035,
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
    return entityId && this._hass?.states ? this._hass.states[entityId] || null : null;
  }

  _indicatorState(name, fallback = null) {
    const state = this._entityState(this._config?.indicators?.[name]);
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

  _functionDefinition(index, fallbackText) {
    const id = FUNCTION_IDS[index];
    const raw = this._config?.function_keys?.[id]
      ?? this._config?.function_keys?.[id.toUpperCase()]
      ?? this._config?.function_keys?.[String(index + 1)]
      ?? this._config?.function_keys?.[fallbackText.toLowerCase()];

    if (typeof raw === "string") {
      return { text: raw, background: "", color: "" };
    }
    if (raw && typeof raw === "object") {
      return {
        text: raw.text ?? raw.label ?? fallbackText,
        background: safeCssColor(raw.background ?? raw.background_color),
        color: safeCssColor(raw.color ?? raw.text_color),
      };
    }
    return { text: fallbackText, background: "", color: "" };
  }

  _functionKey(index, fallbackText) {
    const id = FUNCTION_IDS[index];
    const definition = this._functionDefinition(index, fallbackText);
    const style = [
      definition.background ? `--function-bg:${definition.background}` : "",
      definition.color ? `--function-color:${definition.color}` : "",
    ].filter(Boolean).join(";");
    return `
      <button class="physical-key function-key" data-key="${id.toUpperCase()}"${style ? ` style="${escapeHtml(style)}"` : ""}>
        <span class="function-text">${escapeHtml(definition.text)}</span>
      </button>`;
  }

  _numericKey(key, legend) {
    return `
      <button class="physical-key numeric-key" data-key="${escapeHtml(key)}">
        <span class="key-main">${escapeHtml(key)}</span>
        ${legend ? `<span class="key-legend">${escapeHtml(legend)}</span>` : ""}
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
    const stateClass = display.backlight && display.available ? "lit" : "dim";
    return `
      <div class="lcd-hood">
        <div class="lcd-frame">
          <canvas class="lcd ${stateClass}" width="192" height="32" role="img" aria-label="${escapeHtml(`${display.line1.trim()} ${display.line2.trim()}`)}"></canvas>
        </div>
      </div>`;
  }

  _speaker() {
    return `<div class="speaker" aria-hidden="true"><i></i><i></i><i></i><i></i></div>`;
  }

  _status(model, display) {
    if (model === "6160") {
      return `
        <div class="status-stack residential-status">
          ${this._led("ARMED", display.armed, "armed")}
          ${this._led("READY", display.ready, "ready")}
        </div>`;
    }

    return `
      <div class="status-stack cr2-status">
        <div class="status-blue">
          ${this._led("ARMED", display.armed, "armed")}
          ${this._led("READY", display.ready, "ready")}
          <span class="shield-glyph" aria-hidden="true"></span>
        </div>
        <div class="fire-status">
          ${this._led("POWER", display.power, "power")}
          ${this._led("FIRE ALARM", display.fireAlarm, "fire-alarm")}
          ${this._led("SILENCED", display.silenced, "silenced")}
          ${this._led("SUPERVISORY", display.supervisory, "supervisory")}
          ${this._led("TROUBLE", display.fireTrouble, "fire-trouble")}
          <span class="fire-bracket" aria-hidden="true"></span>
          <span class="fire-icon" aria-hidden="true">♦</span>
        </div>
      </div>`;
  }

  _controls(model) {
    const functionKeys = DEFAULT_FUNCTION_KEYS[model]
      .map((text, index) => this._functionKey(index, text))
      .join("");
    const numericKeys = NUMBER_KEYS
      .map(([key, legend]) => this._numericKey(key, legend))
      .join("");

    return `
      <div class="controls">
        <div class="function-pad">${functionKeys}</div>
        <div class="numeric-pad">${numericKeys}</div>
      </div>`;
  }

  _renderLegacy(model, display) {
    return `
      <div class="keypad-shell ${model === "6160cr2" ? "cr2" : "k6160"}" data-model="${model}">
        <div class="plastic-grain" aria-hidden="true"></div>
        <div class="top-deck">
          ${this._speaker()}
          ${this._lcd(display)}
        </div>
        <div class="lower-deck">
          ${this._status(model, display)}
          ${this._controls(model)}
        </div>
        <div class="case-label">${escapeHtml(this._config?.case_label || "")}</div>
      </div>`;
  }

  _styles() {
    const cardBackground = this._config?.show_card_background
      ? "var(--ha-card-background, var(--card-background-color))"
      : "transparent";
    const cardShadow = this._config?.show_card_background
      ? "var(--ha-card-box-shadow, none)"
      : "none";

    return `
      :host {
        display: block;
        --shell-max: 900px;
        --key-w: 9.45cqw;
        --key-h: 5.75cqw;
        --key-gap-x: 1.75cqw;
        --key-gap-y: 1.35cqw;
        --lcd-ink: #172916;
      }

      ha-card {
        overflow: visible;
        background: ${cardBackground};
        box-shadow: ${cardShadow};
        border: ${this._config?.show_card_background ? "var(--ha-card-border-width, 0) solid var(--ha-card-border-color, transparent)" : "0"};
        padding: ${this._config?.show_card_background ? "18px" : "0"};
      }

      .wrap {
        container-type: inline-size;
        display: grid;
        gap: 10px;
        justify-items: center;
        width: 100%;
      }

      .card-title {
        width: min(100%, var(--shell-max));
        font: 500 16px/1.3 var(--paper-font-body1_-_font-family, sans-serif);
        color: var(--primary-text-color);
      }

      .keypad-shell,
      .keypad-shell * { box-sizing: border-box; }

      .keypad-shell {
        container-type: inline-size;
        position: relative;
        width: min(100%, var(--shell-max));
        aspect-ratio: 1.53 / 1;
        min-height: 360px;
        overflow: hidden;
        padding: 4.25% 5.2% 4.1%;
        border: .17cqw solid;
        border-radius: 1.5cqw 1.5cqw .65cqw .65cqw;
        color: #151515;
        user-select: none;
        -webkit-tap-highlight-color: transparent;
        filter: drop-shadow(0 1.45cqw 1.3cqw rgba(0,0,0,.28));
        box-shadow:
          inset 0 .45cqw .58cqw rgba(255,255,255,.28),
          inset 0 -.62cqw .8cqw rgba(0,0,0,.13),
          inset .4cqw 0 .48cqw rgba(255,255,255,.08),
          inset -.35cqw 0 .45cqw rgba(0,0,0,.05);
      }

      .cr2 {
        background:
          linear-gradient(180deg, #ef343c 0%, #dc2028 31%, #d21b23 70%, #bb151b 100%);
        border-color: #a91217;
      }

      .k6160 {
        background:
          linear-gradient(180deg, #ffffff 0%, #f1f1ee 35%, #e6e6e2 70%, #d5d5cf 100%);
        border-color: #c6c6c0;
      }

      .plastic-grain {
        pointer-events: none;
        position: absolute;
        inset: 0;
        opacity: .2;
        background:
          repeating-radial-gradient(circle at 10% 10%, rgba(255,255,255,.52) 0 .045cqw, transparent .055cqw .19cqw),
          linear-gradient(110deg, rgba(255,255,255,.17), transparent 28%, rgba(0,0,0,.045) 72%, transparent);
        mix-blend-mode: soft-light;
      }

      .keypad-shell::before {
        content: "";
        position: absolute;
        left: 1.25%;
        right: 1.25%;
        top: 1.25%;
        height: .45cqw;
        border-top: .12cqw solid rgba(255,255,255,.38);
        border-radius: 50%;
      }

      .top-deck {
        position: relative;
        z-index: 1;
        height: 43%;
        display: grid;
        grid-template-columns: 23.5% 1fr;
        gap: 4.8%;
        align-items: center;
      }

      .speaker {
        display: grid;
        place-content: center;
        gap: 1.16cqw;
        height: 100%;
      }

      .speaker i {
        display: block;
        width: 11.2cqw;
        height: .54cqw;
        border-radius: 55% 45%;
        background: linear-gradient(180deg, #0b0b0b, #252525);
        box-shadow:
          inset 0 .12cqw .12cqw rgba(255,255,255,.22),
          0 -.08cqw .1cqw rgba(255,255,255,.12);
      }

      .lcd-hood {
        position: relative;
        padding: 3.6% 4.5%;
        background: inherit;
        border-radius: .22cqw;
        box-shadow:
          0 .92cqw .9cqw rgba(0,0,0,.20),
          inset 0 .2cqw .25cqw rgba(255,255,255,.2),
          inset 0 -.2cqw .3cqw rgba(0,0,0,.1);
      }

      .cr2 .lcd-hood {
        background: linear-gradient(180deg, #e62a32, #d71920 75%, #c9181f);
      }

      .k6160 .lcd-hood {
        background: linear-gradient(180deg, #fbfbf8, #ecece8 75%, #deded9);
      }

      .lcd-frame {
        padding: .7cqw;
        border: .25cqw solid rgba(39,54,28,.8);
        background: #6b784f;
        box-shadow:
          inset 0 .4cqw .55cqw rgba(0,0,0,.32),
          0 .18cqw .22cqw rgba(255,255,255,.25);
      }

      .lcd {
        display: block;
        width: 100%;
        height: auto;
        aspect-ratio: 6 / 1;
        image-rendering: pixelated;
        background: #9bcf3c;
        transition: filter .15s ease;
      }

      .lcd.dim { filter: saturate(.4) brightness(.72); }

      .lower-deck {
        position: relative;
        z-index: 1;
        height: 49%;
        display: grid;
        grid-template-columns: 31% 1fr;
        gap: 4.5%;
        align-items: center;
      }

      .status-stack {
        align-self: stretch;
        display: grid;
        align-content: center;
      }

      .status-blue {
        position: relative;
        margin: 0 11% 1.55cqw 8%;
        padding: 1.05cqw 1.5cqw 1.05cqw 1.75cqw;
        border-radius: .65cqw;
        color: #ecf0f3;
        background: linear-gradient(180deg, #216fa0, #155a88);
        box-shadow: inset 0 .16cqw .24cqw rgba(255,255,255,.16);
      }

      .shield-glyph {
        position: absolute;
        right: -12%;
        top: 34%;
        width: 1.9cqw;
        height: 2.15cqw;
        border: .26cqw solid #f0f2f4;
        border-radius: 45% 45% 55% 55%;
        clip-path: polygon(50% 0,100% 18%,86% 75%,50% 100%,14% 75%,0 18%);
      }

      .fire-status {
        position: relative;
        margin-left: 3%;
        padding-left: 5%;
        color: rgba(250,232,232,.94);
      }

      .fire-bracket {
        position: absolute;
        right: 12%;
        top: 2%;
        bottom: 2%;
        width: 18%;
        border-right: .18cqw solid rgba(255,246,246,.92);
        border-top: .18cqw solid rgba(255,246,246,.92);
        border-bottom: .18cqw solid rgba(255,246,246,.92);
        border-radius: 0 .7cqw .7cqw 0;
      }

      .fire-icon {
        position: absolute;
        right: 0;
        top: 42%;
        color: #fff;
        font-size: 2.4cqw;
        transform: rotate(45deg);
      }

      .residential-status {
        width: 72%;
        justify-self: center;
        gap: 3.2cqw;
      }

      .led-row {
        display: grid;
        grid-template-columns: 1fr 3cqw;
        align-items: center;
        min-height: 2.55cqw;
        gap: .55cqw;
        font-family: Arial, Helvetica, sans-serif;
        font-weight: 700;
        font-size: clamp(9px, 1.78cqw, 16px);
        line-height: 1;
      }

      .residential-status .led-row {
        font-size: clamp(8px, 1.38cqw, 13px);
        color: #333;
      }

      .led-label { white-space: nowrap; }

      .led {
        width: 2.65cqw;
        height: 1.15cqw;
        justify-self: center;
        border-radius: 50%;
        background: #42423f;
        box-shadow:
          inset .2cqw .16cqw .28cqw rgba(0,0,0,.78),
          inset -.13cqw -.1cqw .15cqw rgba(255,255,255,.16);
      }

      .led.on {
        background: radial-gradient(circle at 35% 30%, #efffb9 0%, #a8e439 34%, #6c982a 72%);
        box-shadow:
          0 0 .55cqw rgba(168,228,57,.95),
          inset .1cqw .08cqw .16cqw rgba(255,255,255,.75);
      }

      .fire-alarm .led.on,
      .silenced .led.on,
      .supervisory .led.on,
      .fire-trouble .led.on {
        background: radial-gradient(circle at 35% 30%, #ffd2cc 0%, #ee4038 40%, #8d1411 77%);
        box-shadow: 0 0 .55cqw rgba(238,64,56,.88);
      }

      .power .led.on {
        background: radial-gradient(circle at 35% 30%, #fff1b2 0%, #e8aa32 43%, #825913 78%);
        box-shadow: 0 0 .5cqw rgba(232,170,50,.84);
      }

      .led.unknown { opacity: .52; }

      .controls {
        display: grid;
        grid-template-columns: var(--key-w) auto;
        gap: 3.25cqw;
        align-items: center;
        justify-content: center;
      }

      .function-pad {
        position: relative;
        display: grid;
        grid-template-rows: repeat(4, var(--key-h));
        gap: var(--key-gap-y);
      }

      .function-pad::before {
        content: "";
        position: absolute;
        inset: -1.05cqw -.72cqw;
        border: .14cqw solid rgba(0,0,0,.13);
        border-radius: .34cqw;
        box-shadow:
          inset 0 .18cqw .24cqw rgba(0,0,0,.14),
          0 .12cqw .16cqw rgba(255,255,255,.18);
        pointer-events: none;
      }

      .cr2 .function-pad::before {
        background: rgba(153,9,16,.08);
        border-color: rgba(120,6,12,.22);
      }

      .k6160 .function-pad::before {
        background: rgba(150,150,145,.06);
        border-color: rgba(90,90,85,.12);
      }

      .numeric-pad {
        display: grid;
        grid-template-columns: repeat(3, var(--key-w));
        grid-template-rows: repeat(4, var(--key-h));
        column-gap: var(--key-gap-x);
        row-gap: var(--key-gap-y);
      }

      .physical-key {
        box-sizing: border-box;
        width: var(--key-w);
        height: var(--key-h);
        min-width: 0;
        min-height: 0;
        padding: 0;
        border: .15cqw solid #6c6965;
        border-radius: .28cqw;
        color: var(--function-color, #151515);
        background:
          linear-gradient(180deg,
            color-mix(in srgb, var(--function-bg, #f3f1ee) 92%, white 8%) 0%,
            var(--function-bg, #e7e4e0) 48%,
            color-mix(in srgb, var(--function-bg, #d0cdc9) 90%, black 10%) 100%);
        box-shadow:
          0 .34cqw .28cqw rgba(0,0,0,.28),
          0 .08cqw .08cqw rgba(255,255,255,.28),
          inset 0 .18cqw .16cqw rgba(255,255,255,.88),
          inset 0 -.16cqw .2cqw rgba(0,0,0,.16),
          inset .12cqw 0 .12cqw rgba(255,255,255,.32),
          inset -.12cqw 0 .12cqw rgba(0,0,0,.08);
        font-family: Arial, Helvetica, sans-serif;
        cursor: pointer;
        touch-action: manipulation;
        transition: transform .055s ease, box-shadow .055s ease, filter .08s ease;
      }

      .physical-key:active,
      .physical-key.pressed {
        transform: translateY(.2cqw);
        box-shadow:
          0 .08cqw .08cqw rgba(0,0,0,.2),
          inset 0 .16cqw .22cqw rgba(0,0,0,.18);
        filter: brightness(.95);
      }

      .numeric-key {
        display: flex;
        align-items: center;
        justify-content: center;
        gap: .68cqw;
      }

      .key-main {
        font-family: Georgia, "Times New Roman", serif;
        font-size: clamp(17px, 3.1cqw, 28px);
        font-weight: 500;
        font-style: italic;
        line-height: 1;
      }

      .key-legend {
        font-size: clamp(7px, 1.16cqw, 11px);
        font-weight: 700;
        font-style: italic;
        line-height: 1;
      }

      .function-key {
        display: grid;
        place-items: center;
        font-size: clamp(8px, 1.35cqw, 13px);
        font-weight: 800;
      }

      .function-text {
        display: block;
        max-width: 94%;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }

      .case-label {
        position: absolute;
        right: 10%;
        bottom: 2.9%;
        padding: .28cqw .85cqw;
        border: .13cqw solid rgba(255,255,255,.13);
        border-radius: .18cqw;
        color: rgba(255,255,255,.18);
        font: 800 clamp(9px, 1.45cqw, 13px)/1 Georgia, serif;
        letter-spacing: .025em;
        text-shadow: 0 -.08cqw .08cqw rgba(0,0,0,.33);
      }

      .k6160 .case-label {
        color: rgba(112,112,106,.24);
        border-color: rgba(112,112,106,.09);
        text-shadow: 0 .08cqw .08cqw rgba(255,255,255,.8);
      }

      .read-only-note {
        min-height: 18px;
        font: 500 12px/18px var(--paper-font-body1_-_font-family, sans-serif);
        color: var(--secondary-text-color);
        opacity: 0;
        transition: opacity .18s ease;
      }

      .read-only-note.show { opacity: 1; }

      @media (max-width: 600px) {
        .keypad-shell { min-height: 260px; }
      }

      @media (prefers-reduced-motion: reduce) {
        .physical-key, .read-only-note { transition: none; }
      }
    `;
  }

  _drawLcd(canvas, display) {
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    const lit = display.backlight && display.available;
    const bgTop = lit ? "#aee34b" : "#7d8d69";
    const bgBottom = lit ? "#91c936" : "#6d7b60";
    const ink = lit ? "#173017" : "#273226";

    const gradient = ctx.createLinearGradient(0, 0, 0, canvas.height);
    gradient.addColorStop(0, bgTop);
    gradient.addColorStop(1, bgBottom);
    ctx.fillStyle = gradient;
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    ctx.fillStyle = "rgba(35,75,24,.035)";
    for (let x = 0; x < canvas.width; x += 3) {
      ctx.fillRect(x, 0, 1, canvas.height);
    }

    const lines = [display.line1, display.line2];
    const charW = 12;
    const dotW = 1.7;
    const dotH = 1.35;
    const xPad = 1;
    const yPad = 1.5;

    ctx.fillStyle = ink;
    lines.forEach((line, lineIndex) => {
      [...exactLine(line)].forEach((sourceChar, charIndex) => {
        const char = sourceChar.toUpperCase();
        const glyph = LCD_FONT[char] || LCD_FONT["?"];
        glyph.forEach((row, rowIndex) => {
          [...row].forEach((pixel, colIndex) => {
            if (pixel !== "1") return;
            const x = xPad + charIndex * charW + colIndex * 1.85;
            const y = yPad + lineIndex * 15 + rowIndex * 1.68;
            ctx.fillRect(x, y, dotW, dotH);
          });
        });
      });
    });
  }

  _render() {
    if (!this.shadowRoot || !this._config) return;
    const display = this._displayState();
    this.shadowRoot.innerHTML = `
      <style>${this._styles()}</style>
      <ha-card>
        <div class="wrap">
          ${this._config.title ? `<div class="card-title">${escapeHtml(this._config.title)}</div>` : ""}
          ${this._renderLegacy(this._config.model, display)}
          <div class="read-only-note" id="read-only-note">Read-only monitoring. Keypad control is not enabled.</div>
        </div>
      </ha-card>`;

    this._drawLcd(this.shadowRoot.querySelector("canvas.lcd"), display);

    this.shadowRoot.querySelectorAll("button[data-key]").forEach((button) => {
      button.addEventListener("pointerdown", () => button.classList.add("pressed"));
      button.addEventListener("pointerup", () => button.classList.remove("pressed"));
      button.addEventListener("pointerleave", () => button.classList.remove("pressed"));
      button.addEventListener("click", (event) => this._handleKey(event.currentTarget));
    });
  }

  async _handleKey(button) {
    const key = button?.dataset?.key || "";
    if (!key) return;

    await this._audio.beep({
      enabled: boolValue(this._config.sound),
      frequency_hz: this._config.sound_frequency_hz,
      duration_ms: this._config.sound_duration_ms,
      volume: this._config.sound_volume,
    });

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
window.customCards.push({
  type: "vista-keypad-card",
  name: "Vista Keypad",
  description: "Physical keypad-style card for Vista Turbo HASS keypad display entities.",
  preview: false,
  documentationURL: "https://github.com/wtc-brycel/vistaturbo-hass/tree/main/frontend",
});

console.info(`%c VISTA-KEYPAD-CARD %c v${VISTA_KEYPAD_CARD_VERSION} `, "color:#fff;background:#a91016;font-weight:700", "color:#111;background:#e6e6e2");
