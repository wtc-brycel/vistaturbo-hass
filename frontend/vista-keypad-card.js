const VISTA_KEYPAD_CARD_VERSION = "0.3.13";

const MODEL_ALIASES = {
  "6160cr2": "6160cr2",
  "6160cr-2": "6160cr2",
  "cr2": "6160cr2",
  "6160": "6160",
};

const CASE_COLORS = new Set(["red", "white", "dark"]);
const AUTO_CASE_DEFAULTS = {
  "6160cr2": { day: "red", night: "dark" },
  "6160": { day: "white", night: "dark" },
};

const NUMBER_KEYS = [
  ["1", "OFF"], ["2", "AWAY"], ["3", "STAY"],
  ["4", "MAX"], ["5", "TEST"], ["6", "BYPASS"],
  ["7", "INSTANT"], ["8", "CODE"], ["9", "CHIME"],
  ["*", "READY"], ["0", ""], ["#", ""],
];

const FUNCTION_IDS = ["a", "b", "c", "d"];
const DEFAULT_FUNCTION_KEYS = {
  "6160cr2": ["AWAY", "STAY", "POLICE", "PAGE"],
  "6160": ["", "", "", ""],
};

const MATRIX_5X7 = {
  " ":[0,0,0,0,0], "A":[0x7e,0x11,0x11,0x11,0x7e], "B":[0x7f,0x49,0x49,0x49,0x36],
  "C":[0x3e,0x41,0x41,0x41,0x22], "D":[0x7f,0x41,0x41,0x22,0x1c], "E":[0x7f,0x49,0x49,0x49,0x41],
  "F":[0x7f,0x09,0x09,0x09,0x01], "G":[0x3e,0x41,0x49,0x49,0x7a], "H":[0x7f,0x08,0x08,0x08,0x7f],
  "I":[0x00,0x41,0x7f,0x41,0x00], "J":[0x20,0x40,0x41,0x3f,0x01], "K":[0x7f,0x08,0x14,0x22,0x41],
  "L":[0x7f,0x40,0x40,0x40,0x40], "M":[0x7f,0x02,0x0c,0x02,0x7f], "N":[0x7f,0x04,0x08,0x10,0x7f],
  "O":[0x3e,0x41,0x41,0x41,0x3e], "P":[0x7f,0x09,0x09,0x09,0x06], "Q":[0x3e,0x41,0x51,0x21,0x5e],
  "R":[0x7f,0x09,0x19,0x29,0x46], "S":[0x46,0x49,0x49,0x49,0x31], "T":[0x01,0x01,0x7f,0x01,0x01],
  "U":[0x3f,0x40,0x40,0x40,0x3f], "V":[0x1f,0x20,0x40,0x20,0x1f], "W":[0x3f,0x40,0x38,0x40,0x3f],
  "X":[0x63,0x14,0x08,0x14,0x63], "Y":[0x07,0x08,0x70,0x08,0x07], "Z":[0x61,0x51,0x49,0x45,0x43],
  "0":[0x3e,0x51,0x49,0x45,0x3e], "1":[0x00,0x42,0x7f,0x40,0x00], "2":[0x42,0x61,0x51,0x49,0x46],
  "3":[0x21,0x41,0x45,0x4b,0x31], "4":[0x18,0x14,0x12,0x7f,0x10], "5":[0x27,0x45,0x45,0x45,0x39],
  "6":[0x3c,0x4a,0x49,0x49,0x30], "7":[0x01,0x71,0x09,0x05,0x03], "8":[0x36,0x49,0x49,0x49,0x36],
  "9":[0x06,0x49,0x49,0x29,0x1e], "-":[0x08,0x08,0x08,0x08,0x08], "*":[0x14,0x08,0x3e,0x08,0x14],
  "#":[0x14,0x7f,0x14,0x7f,0x14], ".":[0,0x60,0x60,0,0], ":":[0,0x36,0x36,0,0],
  "/":[0x20,0x10,0x08,0x04,0x02], "?":[0x02,0x01,0x51,0x09,0x06],
};

function exactLine(value) {
  return String(value ?? "").slice(0, 16).padEnd(16, " ");
}

function boolValue(value, fallback = false) {
  if ([true, "on", "ON", "true", "1"].includes(value)) return true;
  if ([false, "off", "OFF", "false", "0"].includes(value)) return false;
  return fallback;
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
  if (!text || /[;{}]/.test(text)) return fallback;
  return text;
}

class VistaKeypadAudio {
  constructor() {
    this.ctx = null;
  }

  async beep(config = {}) {
    if (!config.enabled) return;
    const AudioCtx = window.AudioContext || window.webkitAudioContext;
    if (!AudioCtx) return;
    this.ctx ??= new AudioCtx();
    if (this.ctx.state === "suspended") await this.ctx.resume();

    const frequency = Number(config.frequency ?? 1400);
    const duration = Number(config.duration_ms ?? 45) / 1000;
    const volume = Math.max(0, Math.min(1, Number(config.volume ?? 0.035)));
    const now = this.ctx.currentTime;
    const osc = this.ctx.createOscillator();
    const gain = this.ctx.createGain();

    osc.type = "square";
    osc.frequency.setValueAtTime(frequency, now);
    gain.gain.setValueAtTime(0.0001, now);
    gain.gain.exponentialRampToValueAtTime(Math.max(volume, 0.0002), now + 0.002);
    gain.gain.setValueAtTime(Math.max(volume, 0.0002), now + Math.max(0.003, duration - 0.003));
    gain.gain.exponentialRampToValueAtTime(0.0001, now + duration);

    osc.connect(gain).connect(this.ctx.destination);
    osc.start(now);
    osc.stop(now + duration + 0.003);
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
      case_color: "auto",
      read_only: true,
    };
  }

  setConfig(config) {
    if (!config?.entity) throw new Error("vista-keypad-card requires an entity");

    const model = MODEL_ALIASES[String(config.model ?? "6160cr2").toLowerCase()];
    if (!model) throw new Error("model must be 6160cr2 or 6160");

    const caseColor = String(config.case_color ?? "auto").toLowerCase();
    if (caseColor !== "auto" && !CASE_COLORS.has(caseColor)) {
      throw new Error("case_color must be auto, red, white, or dark");
    }

    const normalizeOptionalCaseColor = (value, name) => {
      if (value === undefined || value === null || value === "") return null;
      const normalized = String(value).toLowerCase();
      if (!CASE_COLORS.has(normalized)) {
        throw new Error(`${name} must be red, white, or dark`);
      }
      return normalized;
    };

    const dayCaseColor = normalizeOptionalCaseColor(config.day_case_color, "day_case_color");
    const nightCaseColor = normalizeOptionalCaseColor(config.night_case_color, "night_case_color");

    this._config = {
      title: "",
      model,
      case_color: "auto",
      day_case_color: null,
      night_case_color: null,
      read_only: true,
      show_card_background: false,
      function_keys: {},
      indicators: {},
      indicator_flashing: {},
      led_flash_period_ms: 1000,
      sound: { enabled: false },
      ...config,
      model,
      case_color: caseColor,
      day_case_color: dayCaseColor,
      night_case_color: nightCaseColor,
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
    return entityId && this._hass?.states ? this._hass.states[entityId] ?? null : null;
  }

  _indicatorState(name, fallback = null) {
    const entity = this._entityState(this._config?.indicators?.[name]);
    if (!entity || ["unknown", "unavailable"].includes(entity.state)) return fallback;
    return boolValue(entity.state, fallback ?? false);
  }

  _indicatorFlashing(name) {
    const raw = this._config?.indicator_flashing?.[name];

    if (typeof raw === "boolean") return raw;

    if (typeof raw === "string") {
      const entity = this._entityState(raw);
      if (!entity || ["unknown", "unavailable"].includes(entity.state)) return false;
      return boolValue(entity.state, false);
    }

    if (raw && typeof raw === "object") {
      if (typeof raw.enabled === "boolean") return raw.enabled;
      const entity = this._entityState(raw.entity);
      if (!entity || ["unknown", "unavailable"].includes(entity.state)) return false;
      return boolValue(entity.state, false);
    }

    return false;
  }

  _resolvedCaseColor(model) {
    const configured = this._config?.case_color ?? "auto";
    if (configured !== "auto") return configured;

    const defaults = AUTO_CASE_DEFAULTS[model] ?? AUTO_CASE_DEFAULTS["6160cr2"];
    const dayColor = this._config?.day_case_color ?? defaults.day;
    const nightColor = this._config?.night_case_color ?? defaults.night;

    const hassDarkMode = this._hass?.themes?.darkMode;
    const systemDarkMode = typeof window !== "undefined" && window.matchMedia
      ? window.matchMedia("(prefers-color-scheme: dark)").matches
      : false;
    const darkMode = typeof hassDarkMode === "boolean" ? hassDarkMode : systemDarkMode;
    return darkMode ? nightColor : dayColor;
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
        flashing: {
          armed: false,
          ready: false,
          power: false,
          fire_alarm: false,
          silenced: false,
          supervisory: false,
        },
      };
    }

    const a = state.attributes ?? {};
    const unavailable = ["unknown", "unavailable"].includes(state.state);
    const indicator = (name, attribute, fallback = null) => {
      if (this._config?.indicators?.[name]) {
        return this._indicatorState(name, fallback);
      }
      if (a[attribute] === null || a[attribute] === undefined) return fallback;
      return boolValue(a[attribute], fallback ?? false);
    };

    return {
      available: !unavailable,
      line1: exactLine(a.line_1 ?? (unavailable ? "VISTA OFFLINE" : state.state)),
      line2: exactLine(a.line_2 ?? ""),
      ready: boolValue(a.ready),
      armed: boolValue(a.armed),
      trouble: boolValue(a.trouble),
      backlight: boolValue(a.backlight, true),
      power: indicator("power", "power", null),
      fireAlarm: indicator("fire_alarm", "fire_alarm", null),
      silenced: indicator("silenced", "silenced", null),
      supervisory: indicator("supervisory", "supervisory", null),
      flashing: {
        armed: this._indicatorFlashing("armed"),
        ready: this._indicatorFlashing("ready"),
        power: this._indicatorFlashing("power"),
        fire_alarm: this._indicatorFlashing("fire_alarm"),
        silenced: this._indicatorFlashing("silenced"),
        supervisory: this._indicatorFlashing("supervisory"),
      },
    };
  }

  _functionDefinition(index, fallbackText) {
    const id = FUNCTION_IDS[index];
    const raw =
      this._config?.function_keys?.[id] ??
      this._config?.function_keys?.[id.toUpperCase()] ??
      this._config?.function_keys?.[String(index + 1)];

    if (typeof raw === "string") {
      return { text: raw, background: "", color: "" };
    }

    if (raw && typeof raw === "object") {
      return {
        text: String(raw.text ?? raw.label ?? fallbackText),
        background: safeCssColor(raw.background ?? raw.background_color),
        color: safeCssColor(raw.color ?? raw.text_color),
      };
    }

    return { text: fallbackText, background: "", color: "" };
  }

  _functionKey(index, model) {
    const def = this._functionDefinition(index, DEFAULT_FUNCTION_KEYS[model][index]);
    const style = [
      def.background ? `--key-custom-bg:${def.background}` : "",
      def.color ? `--key-custom-color:${def.color}` : "",
    ].filter(Boolean).join(";");

    return `<button class="physical-key function-key" data-key="${FUNCTION_IDS[index].toUpperCase()}" style="${escapeHtml(style)}" aria-label="${escapeHtml(def.text || FUNCTION_IDS[index].toUpperCase())}">
      <span class="function-label">${escapeHtml(def.text)}</span>
    </button>`;
  }

  _numberKey(key, legend) {
    return `<button class="physical-key number-key" data-key="${escapeHtml(key)}" aria-label="${escapeHtml(`${key} ${legend}`.trim())}">
      <span class="number-main">${escapeHtml(key)}</span>
      ${legend ? `<span class="number-legend">${escapeHtml(legend)}</span>` : ""}
    </button>`;
  }

  _controls(model) {
    const functions = FUNCTION_IDS.map(
      (_, i) => `<div class="grid-slot function-slot slot-r${i + 1}">${this._functionKey(i, model)}</div>`
    ).join("");

    const numeric = NUMBER_KEYS.map(([key, legend], i) => {
      const row = Math.floor(i / 3) + 1;
      const col = (i % 3) + 2;
      return `<div class="grid-slot numeric-slot slot-r${row} slot-c${col}">${this._numberKey(key, legend)}</div>`;
    }).join("");

    return `<div class="key-grid">${functions}${numeric}</div>`;
  }

  _led(label, state, className = "", flashing = false) {
    const status = state === null ? "unknown" : state ? "on" : "off";
    const flashClass = state === true && flashing ? " flashing" : "";
    const spoken = `${label} ${status}${flashClass ? " flashing" : ""}`;
    return `<div class="led-row ${className}">
      <span class="led-label">${escapeHtml(label)}</span>
      <span class="led ${status}${flashClass}" aria-label="${escapeHtml(spoken)}"></span>
    </div>`;
  }

  _statusCR2(display) {
    return `<div class="status-cr2">
      <div class="burg-panel">
        <div class="burg-rows">
          ${this._led("ARMED", display.armed, "armed", display.flashing.armed)}
          ${this._led("READY", display.ready, "ready", display.flashing.ready)}
        </div>
        <span class="burg-bracket" aria-hidden="true"></span>
        <svg class="burg-icon" viewBox="0 0 40 48" aria-hidden="true">
          <path d="M20 3 34 8v12c0 10.2-5.7 18.1-14 23-8.3-4.9-14-12.8-14-23V8L20 3Z" fill="currentColor"/>
          <path d="M20 10 28 13v7c0 6.2-3.2 11.1-8 14.4-4.8-3.3-8-8.2-8-14.4v-7L20 10Z" fill="rgba(24,75,119,.32)"/>
        </svg>
      </div>

      <div class="fire-panel">
        <div class="fire-rows">
          ${this._led("POWER", display.power, "power", display.flashing.power)}
          ${this._led("FIRE ALARM", display.fireAlarm, "fire-alarm", display.flashing.fire_alarm)}
          ${this._led("SILENCED", display.silenced, "silenced", display.flashing.silenced)}
          ${this._led("SUPERVISORY", display.supervisory, "supervisory", display.flashing.supervisory)}
          ${this._led("TROUBLE", display.trouble, "trouble", false)}
        </div>
        <span class="fire-bracket" aria-hidden="true"></span>
        <svg class="fire-icon" viewBox="0 0 40 48" aria-hidden="true">
          <path d="M23 2c1 6-3 9-6 13-2 2-4 5-4 9 0 5 3 9 8 11-2-2-3-4-3-6 0-3 2-5 4-7 2-2 3-4 3-7 5 4 8 9 8 15 0 9-6 15-14 15S5 39 5 30c0-8 4-13 8-18 4-4 8-8 10-10Z" fill="currentColor"/>
        </svg>
      </div>
    </div>`;
  }

  _status6160(display) {
    return `<div class="status-6160">
      ${this._led("ARMED", display.armed, "armed", display.flashing.armed)}
      ${this._led("READY", display.ready, "ready", display.flashing.ready)}
    </div>`;
  }

  _renderPhysical(model, display) {
    const isCR2 = model === "6160cr2";
    const resolvedCaseColor = this._resolvedCaseColor(model);
    const caseClass = `case-${resolvedCaseColor}`;

    return `<div class="keypad-shell ${isCR2 ? "cr2" : "k6160"} ${caseClass}" data-model="${model}" data-case-color="${escapeHtml(resolvedCaseColor)}">
      <div class="microtexture" aria-hidden="true"></div>
      <div class="top-lip" aria-hidden="true"></div>
      <div class="speaker" aria-hidden="true"><i></i><i></i><i></i><i></i></div>

      <div class="display-hood">
        <div class="hood-highlight" aria-hidden="true"></div>
        <div class="lcd-frame">
          <canvas class="matrix-lcd"
            data-line1="${escapeHtml(display.line1)}"
            data-line2="${escapeHtml(display.line2)}"
            data-lit="${display.backlight && display.available ? "1" : "0"}"></canvas>
        </div>
      </div>

      ${isCR2 ? this._statusCR2(display) : this._status6160(display)}
      <div class="controls-well">${this._controls(model)}</div>
    </div>`;
  }

  _styles() {
    const cardBackground = this._config?.show_card_background
      ? "var(--ha-card-background, var(--card-background-color))"
      : "transparent";
    const cardShadow = this._config?.show_card_background
      ? "var(--ha-card-box-shadow, none)"
      : "none";

    const flashPeriod = Math.max(150, Math.min(5000, Number(this._config?.led_flash_period_ms ?? 1000) || 1000));

    return `
      :host {
        display:block;
        --led-flash-period:${flashPeriod}ms;
      }

      ha-card {
        background:${cardBackground};
        box-shadow:${cardShadow};
        border:${this._config?.show_card_background ? "var(--ha-card-border-width,0) solid var(--ha-card-border-color,transparent)" : "0"};
        padding:${this._config?.show_card_background ? "20px" : "0"};
        overflow:visible;
      }

      .wrap {
        container-type:inline-size;
        width:100%;
        display:grid;
        justify-items:center;
        gap:8px;
      }

      .card-title {
        width:min(100%,940px);
        font:500 16px/1.3 sans-serif;
        color:var(--primary-text-color);
      }

      .keypad-shell, .keypad-shell * { box-sizing:border-box; }

      .keypad-shell {
        --case-red:#d71f26;
        --case-red-hi:#ef3a41;
        --case-red-lo:#b90f17;
        --case-white:#f0f0ed;
        --case-white-lo:#d4d4cf;
        --case-dark:#34373a;
        --case-dark-hi:#4a4e52;
        --case-dark-lo:#202225;
        --key-w:9.45cqw;
        --key-h:5.0cqw;
        --gap-x:3.0cqw;
        --gap-y:2.45cqw;

        position:relative;
        width:min(100%,940px);
        aspect-ratio:1.405/1;
        min-width:0;
        overflow:hidden;
        user-select:none;
        -webkit-tap-highlight-color:transparent;
        filter:drop-shadow(0 1.05cqw .95cqw rgba(0,0,0,.31));
        border-radius:1.25cqw 1.25cqw .46cqw .46cqw;
        border:.14cqw solid;
      }

      .case-red {
        background:
          radial-gradient(125% 75% at 50% -10%, rgba(255,255,255,.22), transparent 54%),
          linear-gradient(92deg, var(--case-red-hi) 0%, #df252c 17%, var(--case-red) 55%, #ce1921 82%, var(--case-red-lo) 100%);
        border-color:#a90d13;
        box-shadow:
          inset 0 .42cqw .34cqw rgba(255,255,255,.23),
          inset 0 -.48cqw .54cqw rgba(75,0,0,.19),
          inset .2cqw 0 .25cqw rgba(255,255,255,.08),
          inset -.2cqw 0 .25cqw rgba(70,0,0,.08);
      }

      .case-white {
        background:
          radial-gradient(110% 70% at 48% -12%, rgba(255,255,255,.98), transparent 58%),
          linear-gradient(92deg, #fafafa 0%, var(--case-white) 57%, #e8e8e4 82%, var(--case-white-lo) 100%);
        border-color:#c4c4bf;
        box-shadow:
          inset 0 .42cqw .34cqw rgba(255,255,255,.92),
          inset 0 -.48cqw .54cqw rgba(70,70,65,.12),
          inset .2cqw 0 .25cqw rgba(255,255,255,.7),
          inset -.2cqw 0 .25cqw rgba(80,80,75,.05);
      }

      .case-dark {
        background:
          radial-gradient(125% 75% at 50% -10%, rgba(255,255,255,.11), transparent 54%),
          linear-gradient(92deg, var(--case-dark-hi) 0%, #3d4145 18%, var(--case-dark) 55%, #2b2e31 82%, var(--case-dark-lo) 100%);
        border-color:#17191b;
        box-shadow:
          inset 0 .42cqw .34cqw rgba(255,255,255,.12),
          inset 0 -.48cqw .54cqw rgba(0,0,0,.30),
          inset .2cqw 0 .25cqw rgba(255,255,255,.045),
          inset -.2cqw 0 .25cqw rgba(0,0,0,.16);
      }

      .microtexture {
        position:absolute;
        inset:0;
        pointer-events:none;
        opacity:.15;
        background:
          repeating-radial-gradient(circle at 0 0, rgba(255,255,255,.55) 0 .04cqw, transparent .05cqw .19cqw),
          repeating-radial-gradient(circle at 100% 100%, rgba(0,0,0,.18) 0 .025cqw, transparent .035cqw .22cqw);
        mix-blend-mode:soft-light;
      }

      .top-lip {
        position:absolute;
        left:1.4%;
        right:1.2%;
        top:1.25%;
        height:.7%;
        border-top:.13cqw solid rgba(255,255,255,.34);
        border-radius:50%;
        opacity:.78;
      }

      .speaker {
        position:absolute;
        left:6.6%;
        top:12.6%;
        width:17.5%;
        height:23%;
        display:flex;
        flex-direction:column;
        justify-content:center;
        gap:2.05cqw;
      }

      .speaker i {
        width:13.2cqw;
        height:.56cqw;
        display:block;
        background:#151515;
        border-radius:48% 52% 44% 56%;
        box-shadow:
          inset 0 .11cqw .08cqw rgba(255,255,255,.16),
          0 .08cqw .08cqw rgba(255,255,255,.12);
        clip-path:ellipse(50% 46% at 50% 50%);
      }

      .display-hood {
        position:absolute;
        left:28.2%;
        top:3.3%;
        width:70.2%;
        height:39.6%;
        z-index:2;
        border-radius:.28cqw .42cqw .12cqw .12cqw;
        box-shadow:
          0 .9cqw .75cqw rgba(0,0,0,.24),
          inset 0 .35cqw .25cqw rgba(255,255,255,.21),
          inset 0 -.23cqw .23cqw rgba(0,0,0,.12);
      }

      .case-red .display-hood {
        background:linear-gradient(96deg,#e52b32 0%,#db2028 55%,#c91820 100%);
        border:.13cqw solid #be151c;
      }

      .case-white .display-hood {
        background:linear-gradient(96deg,#fff 0%,#f1f1ee 57%,#dadad5 100%);
        border:.13cqw solid #cfcfca;
      }

      .case-dark .display-hood {
        background:linear-gradient(96deg,#474b4f 0%,#35393d 57%,#25282b 100%);
        border:.13cqw solid #1d1f21;
      }

      .k6160 .display-hood {
        left:24.8%;
        width:73.5%;
      }

      .hood-highlight {
        position:absolute;
        inset:2% 1% auto 1%;
        height:1%;
        border-top:.11cqw solid rgba(255,255,255,.35);
        border-radius:50%;
      }

      .lcd-frame {
        position:absolute;
        left:11.3%;
        right:10.8%;
        top:20.8%;
        height:52.0%;
        padding:.52cqw;
        background:linear-gradient(180deg,#60625d,#282b27 14%,#111 100%);
        border-radius:.12cqw;
        box-shadow:
          inset 0 .16cqw .23cqw rgba(0,0,0,.9),
          0 .12cqw .12cqw rgba(255,255,255,.18);
      }

      .matrix-lcd {
        width:100%;
        height:100%;
        display:block;
        image-rendering:pixelated;
        background:#95d641;
      }

      .controls-well {
        position:absolute;
        left:40%;
        top:52.4%;
        width:56%;
        height:43.5%;
      }

      .key-grid {
        display:grid;
        grid-template-columns:repeat(4,var(--key-w));
        grid-template-rows:repeat(4,var(--key-h));
        column-gap:var(--gap-x);
        row-gap:var(--gap-y);
        width:max-content;
        height:max-content;
      }

      .grid-slot { width:var(--key-w); height:var(--key-h); }
      .slot-r1{grid-row:1}.slot-r2{grid-row:2}.slot-r3{grid-row:3}.slot-r4{grid-row:4}
      .function-slot{grid-column:1;transform:translateX(-1.4cqw)}
      .slot-c2{grid-column:2}.slot-c3{grid-column:3}.slot-c4{grid-column:4}

      .physical-key {
        width:100%;
        height:100%;
        margin:0;
        padding:0 .55cqw;
        position:relative;
        overflow:hidden;
        border:.14cqw solid #595955;
        border-radius:.36cqw;
        color:var(--key-custom-color,#171717);
        background:var(--key-custom-bg,linear-gradient(180deg,#faf9f7 0%,#e9e7e3 18%,#d2cfca 72%,#bbb8b3 100%));
        box-shadow:none;
        cursor:pointer;
        touch-action:manipulation;
        transition:none;
        font-family:"Arial Narrow","Roboto Condensed",Arial,sans-serif;
      }

      .physical-key::after {
        content:"";
        position:absolute;
        inset:.16cqw .19cqw auto .19cqw;
        height:.14cqw;
        border-top:.08cqw solid rgba(255,255,255,.7);
        border-radius:50%;
      }

      .physical-key:active,
      .physical-key.pressed {
        transform:translateY(.10cqw);
        filter:brightness(.94);
      }

      .function-label {
        font-size:clamp(5px,1.42cqw,16px);
        line-height:1;
        font-weight:800;
        letter-spacing:-.02em;
        white-space:nowrap;
      }

      .number-key {
        display:flex;
        align-items:center;
        justify-content:center;
        gap:.55cqw;
      }

      .number-main {
        font-family:"Arial Narrow","Roboto Condensed",Arial,sans-serif;
        font-size:clamp(9px,3.05cqw,34px);
        font-weight:400;
        line-height:.9;
        transform:scaleX(.76);
        transform-origin:center;
      }

      .number-legend {
        font-family:"Arial Narrow","Roboto Condensed",Arial,sans-serif;
        font-size:clamp(4px,1.22cqw,13px);
        font-weight:700;
        font-style:italic;
        line-height:1;
        white-space:nowrap;
      }

      .status-cr2 {
        --ann-row-width:18.35cqw;
        --ann-led-width:2.78cqw;
        position:absolute;
        left:5.0%;
        top:47.8%;
        width:29.0cqw;
        height:39.8%;
        color:#f1e7e7;
        font-family:"Arial Narrow","Roboto Condensed",Arial,sans-serif;
      }

      .cr2.case-white .status-cr2 {
        color:#30302e;
      }

      .cr2.case-dark .status-cr2 {
        color:#eceeed;
      }

      .burg-panel {
        position:absolute;
        left:0;
        top:0;
        width:25.5cqw;
        height:10.25cqw;
        border-radius:.82cqw;
        color:#30302e;
        background:transparent;
        box-shadow:none;
      }

      .cr2.case-red .burg-panel {
        color:#f1f7fa;
        background:linear-gradient(180deg,#1b75ad 0%,#155f95 100%);
        box-shadow:
          inset 0 .12cqw .16cqw rgba(255,255,255,.17),
          inset 0 -.12cqw .14cqw rgba(5,35,60,.18),
          0 .08cqw .12cqw rgba(0,0,0,.12);
      }

      .cr2.case-dark .burg-panel {
        color:#edf5fa;
        background:linear-gradient(180deg,#31536b 0%,#253f52 100%);
        box-shadow:
          inset 0 .12cqw .16cqw rgba(255,255,255,.10),
          inset 0 -.12cqw .14cqw rgba(0,0,0,.24),
          0 .08cqw .12cqw rgba(0,0,0,.20);
      }

      .burg-rows {
        position:absolute;
        left:1.45cqw;
        top:.74cqw;
        width:var(--ann-row-width);
      }

      .fire-panel {
        position:absolute;
        left:0;
        top:10.9cqw;
        width:25.5cqw;
        height:22.9cqw;
      }

      .fire-rows {
        position:absolute;
        left:1.45cqw;
        top:0;
        width:var(--ann-row-width);
      }

      .led-row {
        display:grid;
        grid-template-columns:1fr var(--ann-led-width);
        align-items:center;
        column-gap:.38cqw;
        min-height:4.18cqw;
        font-size:clamp(6px,1.72cqw,18px);
        font-weight:700;
        line-height:1;
      }

      .burg-rows .led-row {
        min-height:4.18cqw;
        font-size:clamp(6px,1.48cqw,16px);
      }

      .led-label {
        white-space:nowrap;
        text-shadow:0 .05cqw .04cqw rgba(0,0,0,.14);
      }

      .led {
        position:relative;
        display:block;
        justify-self:center;
        width:3.05cqw;
        height:1.42cqw;
        border-radius:50% 50% 46% 54% / 60% 57% 43% 40%;
        overflow:visible;
        border:.085cqw solid rgba(8,8,7,.94);
        outline:.15cqw solid rgba(20,20,18,.96);
        outline-offset:.045cqw;
        background:
          radial-gradient(ellipse at 36% 22%,rgba(255,255,255,.20) 0 8%,transparent 27%),
          linear-gradient(180deg,#4b4a46 0%,#292a27 43%,#151614 100%);
        box-shadow:
          0 0 0 .07cqw rgba(255,255,255,.20),
          0 .11cqw .12cqw rgba(0,0,0,.55),
          inset .19cqw .16cqw .26cqw rgba(0,0,0,.88),
          inset -.10cqw -.08cqw .13cqw rgba(255,255,255,.13),
          0 .06cqw .08cqw rgba(255,255,255,.13),
          0 -.055cqw .07cqw rgba(0,0,0,.44);
      }

      .led::before {
        content:"";
        position:absolute;
        inset:.09cqw .14cqw .16cqw .16cqw;
        border-radius:50%;
        pointer-events:none;
        background:linear-gradient(155deg,rgba(255,255,255,.20),rgba(255,255,255,0) 45%);
        opacity:.68;
      }

      .led::after {
        content:"";
        position:absolute;
        left:17%;
        top:10%;
        width:35%;
        height:24%;
        border-radius:50%;
        pointer-events:none;
        background:radial-gradient(ellipse,rgba(255,255,255,.40),rgba(255,255,255,0) 72%);
        filter:blur(.03cqw);
        opacity:.42;
      }

      .led.on {
        outline:none;
        outline-offset:0;
        background:
          radial-gradient(ellipse at 30% 20%,#ffffff 0 9%,#f8ffd5 13%,#e5ff78 24%,rgba(219,255,90,.56) 36%,transparent 48%),
          radial-gradient(ellipse at 50% 54%,#e4ff72 0%,#baf52e 45%,#72b80d 76%,#2f5004 100%);
        border-color:rgba(150,205,43,.78);
        filter:saturate(1.48) brightness(1.42);
        box-shadow:
          0 0 .15cqw rgba(255,255,235,1),
          0 0 .42cqw rgba(235,255,126,1),
          0 0 .88cqw rgba(190,255,52,.98),
          0 0 1.55cqw rgba(139,235,22,.82),
          0 0 2.45cqw rgba(104,205,10,.46),
          inset .08cqw .07cqw .14cqw rgba(255,255,255,.98),
          inset -.12cqw -.1cqw .14cqw rgba(37,68,3,.30),
          0 -.045cqw .06cqw rgba(0,0,0,.24);
      }

      /* 6160CR-2 physical lamp colors:
         ARMED/FIRE ALARM red; READY/POWER green; SILENCED/SUPERVISORY/TROUBLE yellow. */
      .led-row.armed .led.on,
      .led-row.fire-alarm .led.on {
        background:
          radial-gradient(ellipse at 29% 19%,#ffffff 0 10%,#fff0ec 14%,#ff9a88 23%,rgba(255,72,48,.62) 37%,transparent 49%),
          radial-gradient(ellipse at 50% 54%,#ff6b58 0%,#ff2818 43%,#c70e08 73%,#690400 100%);
        border-color:rgba(255,137,121,.72);
        filter:saturate(1.55) brightness(1.48);
        box-shadow:
          0 0 .16cqw rgba(255,255,248,1),
          0 0 .44cqw rgba(255,187,171,1),
          0 0 .92cqw rgba(255,75,50,1),
          0 0 1.6cqw rgba(255,37,22,.92),
          0 0 2.55cqw rgba(231,19,9,.58),
          inset .08cqw .07cqw .14cqw rgba(255,255,255,.98),
          inset -.12cqw -.1cqw .14cqw rgba(85,2,0,.28),
          0 -.045cqw .06cqw rgba(0,0,0,.20);
      }

      .led-row.silenced .led.on,
      .led-row.supervisory .led.on,
      .led-row.trouble .led.on {
        background:
          radial-gradient(ellipse at 29% 19%,#ffffff 0 10%,#fffde0 14%,#fff18a 24%,rgba(255,222,61,.62) 37%,transparent 49%),
          radial-gradient(ellipse at 50% 54%,#ffec62 0%,#ffc91e 44%,#d58a04 74%,#704400 100%);
        border-color:rgba(255,226,118,.72);
        filter:saturate(1.48) brightness(1.43);
        box-shadow:
          0 0 .16cqw rgba(255,255,246,1),
          0 0 .44cqw rgba(255,249,167,1),
          0 0 .92cqw rgba(255,218,55,1),
          0 0 1.6cqw rgba(255,184,14,.86),
          0 0 2.45cqw rgba(217,137,0,.48),
          inset .08cqw .07cqw .14cqw rgba(255,255,255,.98),
          inset -.12cqw -.1cqw .14cqw rgba(92,53,0,.25),
          0 -.045cqw .06cqw rgba(0,0,0,.20);
      }

      .led.on::before {
        background:
          linear-gradient(155deg,rgba(255,255,255,.82),rgba(255,255,255,.08) 46%,transparent 62%);
        opacity:.9;
        box-shadow:
          inset 0 0 .10cqw rgba(255,255,255,.34);
      }

      .led.on::after {
        left:11%;
        top:5%;
        width:48%;
        height:34%;
        background:radial-gradient(ellipse,rgba(255,255,255,1),rgba(255,255,255,.72) 38%,rgba(255,255,255,.18) 62%,transparent 78%);
        filter:blur(.025cqw);
        opacity:1;
      }

      .led.on.flashing {
        animation:led-flash var(--led-flash-period) steps(1,end) infinite;
      }

      @keyframes led-flash {
        0%, 49.999% {
          opacity:1;
          filter:saturate(1.28) brightness(1.14);
        }
        50%, 100% {
          opacity:.42;
          filter:saturate(.42) brightness(.48);
          box-shadow:
            inset .17cqw .14cqw .23cqw rgba(0,0,0,.72),
            inset -.10cqw -.07cqw .12cqw rgba(255,255,255,.10),
            0 .06cqw .08cqw rgba(255,255,255,.10),
            0 -.055cqw .07cqw rgba(0,0,0,.38);
        }
      }

      .led.unknown {
        filter:saturate(.5) brightness(.90);
        opacity:.94;
      }

      .burg-bracket,
      .fire-bracket {
        position:absolute;
        left:20.18cqw;
        width:2.0cqw;
        border-right:.15cqw solid rgba(247,248,248,.92);
        border-top:.15cqw solid rgba(247,248,248,.92);
        border-bottom:.15cqw solid rgba(247,248,248,.92);
        border-radius:0 .6cqw .6cqw 0;
        box-shadow:.04cqw 0 .03cqw rgba(0,0,0,.16);
      }

      .burg-bracket {
        top:.63cqw;
        bottom:.63cqw;
      }

      .fire-bracket {
        top:.15cqw;
        bottom:.2cqw;
      }

      .cr2.case-white .fire-bracket {
        border-right-color:rgba(48,48,46,.84);
        border-top-color:rgba(48,48,46,.84);
        border-bottom-color:rgba(48,48,46,.84);
        box-shadow:.04cqw 0 .03cqw rgba(255,255,255,.35);
      }

      .cr2.case-dark .fire-bracket,
      .cr2.case-dark .burg-bracket {
        border-right-color:rgba(238,241,242,.88);
        border-top-color:rgba(238,241,242,.88);
        border-bottom-color:rgba(238,241,242,.88);
        box-shadow:.04cqw 0 .04cqw rgba(0,0,0,.28);
      }

      .burg-icon {
        position:absolute;
        left:22.63cqw;
        top:2.35cqw;
        width:2.25cqw;
        height:5.45cqw;
        color:#f5f8fa;
        filter:drop-shadow(0 .06cqw .04cqw rgba(0,0,0,.18));
      }

      .cr2.case-white .burg-bracket {
        border-right-color:rgba(48,48,46,.84);
        border-top-color:rgba(48,48,46,.84);
        border-bottom-color:rgba(48,48,46,.84);
        box-shadow:none;
      }

      .cr2.case-white .burg-icon {
        color:#343432;
        filter:none;
      }

      .fire-icon {
        position:absolute;
        left:22.83cqw;
        top:8.95cqw;
        width:2.28cqw;
        height:4.55cqw;
        color:#f7eeee;
        filter:drop-shadow(0 .06cqw .04cqw rgba(0,0,0,.18));
      }

      .cr2.case-white .fire-icon {
        color:#343432;
        filter:drop-shadow(0 .05cqw .035cqw rgba(255,255,255,.45));
      }

      .status-6160 {
        position:absolute;
        left:6.5%;
        top:59.1%;
        width:23.2%;
        color:#171717;
        font-family:"Arial Narrow","Roboto Condensed",Arial,sans-serif;
      }

      .k6160.case-red .status-6160,
      .k6160.case-dark .status-6160 {
        color:#f0f1ef;
      }

      .k6160.case-white .status-6160 {
        color:#171717;
      }

      .status-6160 .led-row {
        --ann-led-width:2.7cqw;
        grid-template-columns:1fr var(--ann-led-width);
        min-height:6.6cqw;
        font-size:clamp(5px,1.35cqw,15px);
        font-weight:500;
      }

      .read-only-note {
        min-height:18px;
        opacity:0;
        color:var(--secondary-text-color);
        font:500 12px/18px sans-serif;
        transition:opacity .18s ease;
      }

      .read-only-note.show { opacity:1; }

      @media(max-width:650px) {
        .wrap { gap:4px; }
      }

      @container (max-width:520px) {
        .physical-key { padding:0 .28cqw; }
        .number-key { gap:.26cqw; }
        .function-slot { transform:translateX(-1.0cqw); }
      }

      @container (max-width:360px) {
        .physical-key { padding:0 .12cqw; }
        .number-key { gap:.12cqw; }
        .function-slot { transform:translateX(-.72cqw); }
      }

      @media(prefers-reduced-motion:reduce) {
        .physical-key, .read-only-note { transition:none; }
        .led.on.flashing { animation:none; }
      }
    `;
  }

  _drawLCD() {
    const canvas = this.shadowRoot?.querySelector(".matrix-lcd");
    if (!canvas) return;

    const rect = canvas.getBoundingClientRect();
    const scale = Math.max(1, window.devicePixelRatio || 1);
    canvas.width = Math.max(1, Math.round(rect.width * scale));
    canvas.height = Math.max(1, Math.round(rect.height * scale));

    const ctx = canvas.getContext("2d");
    ctx.scale(scale, scale);

    const w = rect.width;
    const h = rect.height;
    const lit = canvas.dataset.lit === "1";

    const bg = ctx.createLinearGradient(0, 0, 0, h);
    if (lit) {
      bg.addColorStop(0, "#b2ed54");
      bg.addColorStop(.5, "#9ee247");
      bg.addColorStop(1, "#88cb38");
    } else {
      bg.addColorStop(0, "#7f9570");
      bg.addColorStop(1, "#687a5e");
    }

    ctx.fillStyle = bg;
    ctx.fillRect(0, 0, w, h);

    ctx.fillStyle = lit ? "rgba(33,80,23,.055)" : "rgba(25,42,24,.065)";
    const grid = Math.max(2.5, w / 120);
    for (let x = 0; x < w; x += grid) ctx.fillRect(x, 0, 1, h);
    for (let y = 0; y < h; y += grid) ctx.fillRect(0, y, w, 1);

    const lines = [exactLine(canvas.dataset.line1), exactLine(canvas.dataset.line2)];
    const marginX = w * .018;
    const marginY = h * .105;
    const charW = (w - marginX * 2) / 16;
    const lineH = (h - marginY * 2) / 2;
    const dot = Math.min(charW / 6.45, lineH / 8.05);
    const gap = dot * .19;
    const px = dot - gap;

    ctx.fillStyle = lit ? "#17341a" : "#253126";

    lines.forEach((line, rowIndex) => {
      [...line].forEach((rawChar, charIndex) => {
        const glyph = MATRIX_5X7[rawChar.toUpperCase()] ?? MATRIX_5X7["?"];
        const baseX = marginX + charIndex * charW + (charW - dot * 5) / 2;
        const baseY = marginY + rowIndex * lineH + (lineH - dot * 7) / 2;

        for (let gx = 0; gx < 5; gx++) {
          const bits = glyph[gx] || 0;
          for (let gy = 0; gy < 7; gy++) {
            if (bits & (1 << gy)) {
              ctx.fillRect(
                Math.round(baseX + gx * dot),
                Math.round(baseY + gy * dot),
                Math.max(1, Math.ceil(px)),
                Math.max(1, Math.ceil(px))
              );
            }
          }
        }
      });
    });

    const glare = ctx.createLinearGradient(0, 0, w, h);
    glare.addColorStop(0, "rgba(255,255,255,.10)");
    glare.addColorStop(.32, "rgba(255,255,255,.015)");
    glare.addColorStop(1, "rgba(255,255,255,0)");
    ctx.fillStyle = glare;
    ctx.fillRect(0, 0, w, h * .42);
  }

  _render() {
    if (!this.shadowRoot || !this._config) return;

    const display = this._displayState();
    this.shadowRoot.innerHTML = `<style>${this._styles()}</style><ha-card><div class="wrap">
      ${this._config.title ? `<div class="card-title">${escapeHtml(this._config.title)}</div>` : ""}
      ${this._renderPhysical(this._config.model, display)}
      <div class="read-only-note" id="read-only-note">Read-only monitoring. Keypad control is not enabled.</div>
    </div></ha-card>`;

    requestAnimationFrame(() => this._drawLCD());

    this.shadowRoot.querySelectorAll("button[data-key]").forEach((button) => {
      button.addEventListener("pointerdown", () => button.classList.add("pressed"));
      button.addEventListener("pointerup", () => button.classList.remove("pressed"));
      button.addEventListener("pointerleave", () => button.classList.remove("pressed"));
      button.addEventListener("click", (event) => this._handleKey(event.currentTarget));
    });
  }

  _handleKey(button) {
    const key = button?.dataset?.key;
    if (!key) return;

    this._audio.beep(this._config?.sound ?? {}).catch(() => {});

    if (this._config.read_only !== false) {
      const note = this.shadowRoot.getElementById("read-only-note");
      if (note) {
        note.classList.add("show");
        clearTimeout(this._pressTimer);
        this._pressTimer = setTimeout(() => note.classList.remove("show"), 1200);
      }
      return;
    }

    this.dispatchEvent(new CustomEvent("vista-keypad-key", {
      bubbles: true,
      composed: true,
      detail: {
        key,
        entity: this._config.entity,
        model: this._config.model,
      },
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
  description: "Physical VISTA keypad card with 6160CR-2 and 6160 skins.",
  preview: false,
  documentationURL: "https://github.com/wtc-brycel/vistaturbo-hass/tree/main/frontend",
});

console.info(
  `%c VISTA-KEYPAD-CARD %c v${VISTA_KEYPAD_CARD_VERSION} `,
  "color:#fff;background:#b40f18;font-weight:700",
  "color:#111;background:#e6e6e2"
);
