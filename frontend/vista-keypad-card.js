const VISTA_KEYPAD_CARD_VERSION = "0.3.0";

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
  "/":[0x20,0x10,0x08,0x04,0x02], "?":[0x02,0x01,0x51,0x09,0x06], "=":[0x14,0x14,0x14,0x14,0x14],
  "<":[0x08,0x14,0x22,0x41,0], ">":[0,0x41,0x22,0x14,0x08], "'":[0,0x05,0x03,0,0],
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
  const v = value.trim();
  if (!v || /[;{}]/.test(v)) return fallback;
  return v;
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
      read_only: true,
    };
  }

  setConfig(config) {
    if (!config?.entity) throw new Error("vista-keypad-card requires an entity");
    const model = MODEL_ALIASES[String(config.model ?? "6160cr2").toLowerCase()];
    if (!model) throw new Error("model must be 6160cr2 or 6160");
    this._config = {
      title: "",
      model,
      read_only: true,
      show_card_background: false,
      function_keys: {},
      indicators: {},
      sound: { enabled: false },
      ...config,
      model,
    };
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  getCardSize() { return 7; }

  _entityState(entityId) {
    return entityId && this._hass?.states ? this._hass.states[entityId] ?? null : null;
  }

  _indicatorState(name, fallback = null) {
    const entity = this._entityState(this._config?.indicators?.[name]);
    if (!entity || ["unknown", "unavailable"].includes(entity.state)) return fallback;
    return boolValue(entity.state, fallback ?? false);
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
    const a = state.attributes ?? {};
    const unavailable = ["unknown", "unavailable"].includes(state.state);
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
      ?? this._config?.function_keys?.[String(index + 1)];
    if (typeof raw === "string") return { text: raw, background: "", color: "" };
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
      <span class="number-main">${escapeHtml(key)}</span>${legend ? `<span class="number-legend">${escapeHtml(legend)}</span>` : ""}
    </button>`;
  }

  _controls(model) {
    const functions = FUNCTION_IDS.map((_, i) => `<div class="grid-slot function-slot slot-r${i + 1}">${this._functionKey(i, model)}</div>`).join("");
    const numeric = NUMBER_KEYS.map(([key, legend], i) => {
      const row = Math.floor(i / 3) + 1;
      const col = (i % 3) + 2;
      return `<div class="grid-slot numeric-slot slot-r${row} slot-c${col}">${this._numberKey(key, legend)}</div>`;
    }).join("");
    return `<div class="key-grid">${functions}${numeric}</div>`;
  }

  _led(label, state, className = "") {
    const status = state === null ? "unknown" : state ? "on" : "off";
    return `<div class="led-row ${className}">
      <span class="led-label">${escapeHtml(label)}</span><span class="led ${status}"></span>
    </div>`;
  }

  _statusCR2(display) {
    return `<div class="status-cr2">
      <div class="burg-sticker">
        ${this._led("ARMED", display.armed, "armed")}
        ${this._led("READY", display.ready, "ready")}
        <svg class="burg-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M12 2 20 5v6c0 5.4-3.5 9.3-8 11-4.5-1.7-8-5.6-8-11V5l8-3Z" fill="none" stroke="currentColor" stroke-width="2"/></svg>
      </div>
      <div class="fire-annunciators">
        ${this._led("POWER", display.power, "power")}
        ${this._led("FIRE ALARM", display.fireAlarm, "fire-alarm")}
        ${this._led("SILENCED", display.silenced, "silenced")}
        ${this._led("SUPERVISORY", display.supervisory, "supervisory")}
        ${this._led("TROUBLE", display.fireTrouble, "fire-trouble")}
        <span class="fire-bracket"></span>
        <svg class="fire-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M13.7 2.2c.6 3.4-1.4 5-3.1 6.8-1.3 1.4-2.5 2.8-2.5 5 0 2.7 1.9 4.9 4.7 5.6-1.2-1.1-1.8-2.3-1.8-3.7 0-1.7 1-3 2-4.3.9-1.1 1.7-2.2 1.7-3.6 2.7 2.3 4.3 5 4.3 8 0 4.1-3 7-7 7s-7-3-7-7c0-3.4 1.8-5.8 3.8-8 1.8-2 3.8-3.9 4.9-5.8Z" fill="currentColor"/></svg>
      </div>
    </div>`;
  }

  _status6160(display) {
    return `<div class="status-6160">${this._led("ARMED", display.armed, "armed")}${this._led("READY", display.ready, "ready")}</div>`;
  }

  _renderPhysical(model, display) {
    const isCR2 = model === "6160cr2";
    const brand = isCR2 ? "FIRST ALERT" : "Honeywell";
    return `<div class="keypad-shell ${isCR2 ? "cr2" : "k6160"}" data-model="${model}">
      <div class="microtexture"></div>
      <div class="top-lip"></div>
      <div class="speaker" aria-hidden="true"><i></i><i></i><i></i><i></i></div>
      <div class="display-hood">
        <div class="hood-highlight"></div>
        <div class="lcd-frame"><canvas class="matrix-lcd" data-line1="${escapeHtml(display.line1)}" data-line2="${escapeHtml(display.line2)}" data-lit="${display.backlight && display.available ? "1" : "0"}"></canvas></div>
      </div>
      ${isCR2 ? this._statusCR2(display) : this._status6160(display)}
      <div class="controls-well">${this._controls(model)}</div>
      <div class="brand-emboss ${isCR2 ? "brand-firstalert" : "brand-honeywell"}">${escapeHtml(brand)}</div>
      <div class="case-notch"></div>
    </div>`;
  }

  _styles() {
    const cardBackground = this._config?.show_card_background
      ? "var(--ha-card-background, var(--card-background-color))"
      : "transparent";
    const cardShadow = this._config?.show_card_background ? "var(--ha-card-box-shadow, none)" : "none";
    return `
      :host { display:block; }
      ha-card {
        background:${cardBackground}; box-shadow:${cardShadow};
        border:${this._config?.show_card_background ? "var(--ha-card-border-width,0) solid var(--ha-card-border-color,transparent)" : "0"};
        padding:${this._config?.show_card_background ? "20px" : "0"}; overflow:visible;
      }
      .wrap { container-type:inline-size; width:100%; display:grid; justify-items:center; gap:8px; }
      .card-title { width:min(100%,940px); font:500 16px/1.3 sans-serif; color:var(--primary-text-color); }
      .keypad-shell, .keypad-shell * { box-sizing:border-box; }
      .keypad-shell {
        --case-red:#d71f26; --case-red-hi:#ef3a41; --case-red-lo:#b90f17;
        --case-white:#f0f0ed; --case-white-hi:#fff; --case-white-lo:#d4d4cf;
        --key-w:9.55cqw; --key-h:5.2cqw; --gap-x:1.72cqw; --gap-y:1.35cqw;
        position:relative; width:min(100%,940px); aspect-ratio:1.405/1; min-height:410px;
        overflow:hidden; user-select:none; -webkit-tap-highlight-color:transparent;
        filter:drop-shadow(0 1.05cqw .95cqw rgba(0,0,0,.31));
        border-radius:1.25cqw 1.25cqw .46cqw .46cqw; border:.14cqw solid;
      }
      .cr2 {
        background:
          radial-gradient(125% 75% at 50% -10%, rgba(255,255,255,.22), transparent 54%),
          linear-gradient(92deg, var(--case-red-hi) 0%, #df252c 17%, var(--case-red) 55%, #ce1921 82%, var(--case-red-lo) 100%);
        border-color:#a90d13;
        box-shadow:inset 0 .42cqw .34cqw rgba(255,255,255,.23), inset 0 -.48cqw .54cqw rgba(75,0,0,.19), inset .2cqw 0 .25cqw rgba(255,255,255,.08), inset -.2cqw 0 .25cqw rgba(70,0,0,.08);
      }
      .k6160 {
        background:
          radial-gradient(110% 70% at 48% -12%, rgba(255,255,255,.98), transparent 58%),
          linear-gradient(92deg, #fafafa 0%, var(--case-white) 57%, #e8e8e4 82%, var(--case-white-lo) 100%);
        border-color:#c4c4bf;
        box-shadow:inset 0 .42cqw .34cqw rgba(255,255,255,.92), inset 0 -.48cqw .54cqw rgba(70,70,65,.12), inset .2cqw 0 .25cqw rgba(255,255,255,.7), inset -.2cqw 0 .25cqw rgba(80,80,75,.05);
      }
      .microtexture {
        position:absolute; inset:0; pointer-events:none; opacity:.16;
        background:
          repeating-radial-gradient(circle at 0 0, rgba(255,255,255,.55) 0 .04cqw, transparent .05cqw .19cqw),
          repeating-radial-gradient(circle at 100% 100%, rgba(0,0,0,.18) 0 .025cqw, transparent .035cqw .22cqw);
        mix-blend-mode:soft-light;
      }
      .top-lip { position:absolute; left:1.4%; right:1.2%; top:1.25%; height:.7%; border-top:.13cqw solid rgba(255,255,255,.34); border-radius:50%; opacity:.78; }
      .speaker { position:absolute; left:6.6%; top:12.6%; width:17.5%; height:23%; display:flex; flex-direction:column; justify-content:center; gap:2.05cqw; }
      .speaker i { width:13.2cqw; height:.56cqw; display:block; background:#151515; border-radius:48% 52% 44% 56%; box-shadow:inset 0 .11cqw .08cqw rgba(255,255,255,.16), 0 .08cqw .08cqw rgba(255,255,255,.12); clip-path:ellipse(50% 46% at 50% 50%); }
      .display-hood {
        position:absolute; left:28.2%; top:3.3%; width:70.2%; height:43.2%; z-index:2;
        border-radius:.28cqw .42cqw .12cqw .12cqw;
        box-shadow:0 .9cqw .75cqw rgba(0,0,0,.24), inset 0 .35cqw .25cqw rgba(255,255,255,.21), inset 0 -.23cqw .23cqw rgba(0,0,0,.12);
      }
      .cr2 .display-hood { background:linear-gradient(96deg,#e52b32 0%,#db2028 55%,#c91820 100%); border:.13cqw solid #be151c; }
      .k6160 .display-hood { background:linear-gradient(96deg,#fff 0%,#f1f1ee 57%,#dadad5 100%); border:.13cqw solid #cfcfca; }
      .hood-highlight { position:absolute; inset:2% 1% auto 1%; height:1%; border-top:.11cqw solid rgba(255,255,255,.35); border-radius:50%; }
      .lcd-frame {
        position:absolute; left:11.3%; right:10.8%; top:23.2%; height:45.4%; padding:.52cqw;
        background:linear-gradient(180deg,#60625d,#282b27 14%,#111 100%); border-radius:.12cqw;
        box-shadow:inset 0 .16cqw .23cqw rgba(0,0,0,.9), 0 .12cqw .12cqw rgba(255,255,255,.18);
      }
      .matrix-lcd { width:100%; height:100%; display:block; image-rendering:pixelated; background:#95d641; }
      .controls-well { position:absolute; left:41.2%; top:49.1%; width:52.6%; height:43.5%; }
      .key-grid { display:grid; grid-template-columns:repeat(4,var(--key-w)); grid-template-rows:repeat(4,var(--key-h)); column-gap:var(--gap-x); row-gap:var(--gap-y); width:max-content; height:max-content; }
      .grid-slot { width:var(--key-w); height:var(--key-h); }
      .slot-r1{grid-row:1}.slot-r2{grid-row:2}.slot-r3{grid-row:3}.slot-r4{grid-row:4}
      .function-slot{grid-column:1}.slot-c2{grid-column:2}.slot-c3{grid-column:3}.slot-c4{grid-column:4}
      .physical-key {
        width:100%; height:100%; margin:0; padding:0 .55cqw; position:relative; overflow:hidden;
        border:.14cqw solid #595955; border-radius:.36cqw; color:var(--key-custom-color,#171717);
        background:var(--key-custom-bg,linear-gradient(180deg,#faf9f7 0%,#e9e7e3 18%,#d2cfca 72%,#bbb8b3 100%));
        box-shadow:0 .35cqw .25cqw rgba(0,0,0,.27), inset 0 .16cqw .13cqw rgba(255,255,255,.98), inset 0 -.16cqw .17cqw rgba(0,0,0,.13), inset .12cqw 0 .12cqw rgba(255,255,255,.55);
        cursor:pointer; touch-action:manipulation; transition:transform .045s ease,box-shadow .045s ease,filter .08s ease;
        font-family:"Arial Narrow","Roboto Condensed",Arial,sans-serif;
      }
      .physical-key::after { content:""; position:absolute; inset:.16cqw .19cqw auto .19cqw; height:.14cqw; border-top:.08cqw solid rgba(255,255,255,.7); border-radius:50%; }
      .physical-key:active,.physical-key.pressed { transform:translateY(.22cqw); box-shadow:0 .07cqw .08cqw rgba(0,0,0,.27),inset 0 .19cqw .21cqw rgba(0,0,0,.15); filter:brightness(.97); }
      .function-label { font-size:clamp(8px,1.42cqw,16px); line-height:1; font-weight:800; letter-spacing:-.02em; white-space:nowrap; }
      .number-key { display:flex; align-items:center; justify-content:center; gap:.55cqw; }
      .number-main { font-family:"Arial Narrow","Roboto Condensed",Arial,sans-serif; font-stretch:condensed; font-size:clamp(19px,3.05cqw,34px); font-weight:400; line-height:.9; transform:scaleX(.76); transform-origin:center; }
      .number-legend { font-family:"Arial Narrow","Roboto Condensed",Arial,sans-serif; font-size:clamp(7px,1.22cqw,13px); font-weight:700; font-style:italic; line-height:1; white-space:nowrap; }
      .status-cr2 { position:absolute; left:5.2%; top:53.1%; width:27.4%; height:39.8%; color:#f1e7e7; font-family:"Arial Narrow",Arial,sans-serif; }
      .burg-sticker { position:absolute; left:2%; top:0; width:69%; height:31%; padding:1.05cqw 1.55cqw; background:linear-gradient(180deg,#1974ad,#135c92); border-radius:.85cqw; box-shadow:inset 0 .12cqw .16cqw rgba(255,255,255,.17),0 .08cqw .12cqw rgba(0,0,0,.12); color:#edf2f4; }
      .burg-icon { position:absolute; right:4%; top:16%; width:18%; height:68%; color:#f0f6f8; opacity:.9; }
      .fire-annunciators { position:absolute; left:0; top:33%; width:78%; height:67%; padding-left:1.6cqw; }
      .fire-bracket { position:absolute; right:-7%; top:2%; bottom:3%; width:26%; border-right:.15cqw solid #f3e7e7; border-top:.15cqw solid #f3e7e7; border-bottom:.15cqw solid #f3e7e7; border-radius:0 .7cqw .7cqw 0; opacity:.86; }
      .fire-icon { position:absolute; right:-25%; top:31%; width:18%; height:32%; color:#f5eeee; }
      .led-row { display:grid; grid-template-columns:1fr 3.25cqw; align-items:center; column-gap:.45cqw; min-height:3.25cqw; font-size:clamp(9px,1.75cqw,19px); font-weight:700; line-height:1; }
      .burg-sticker .led-row { grid-template-columns:1fr 3cqw; min-height:3.15cqw; font-size:clamp(9px,1.55cqw,17px); }
      .led-label { white-space:nowrap; text-shadow:0 .05cqw .04cqw rgba(0,0,0,.14); }
      .led { display:block; width:2.7cqw; height:1.18cqw; border-radius:50%; background:linear-gradient(180deg,#585752,#2d2e2a); box-shadow:inset .18cqw .12cqw .23cqw rgba(0,0,0,.8),inset -.09cqw -.07cqw .1cqw rgba(255,255,255,.2),0 .04cqw .04cqw rgba(255,255,255,.11); }
      .led.on { background:radial-gradient(ellipse at 36% 28%,#f4ffad 0%,#b7eb39 35%,#79a92b 71%,#496b1e 100%); box-shadow:0 0 .65cqw rgba(180,237,53,.85),inset .12cqw .08cqw .15cqw rgba(255,255,255,.72); }
      .led.unknown { opacity:.86; }
      .status-6160 { position:absolute; left:6.5%; top:55.7%; width:23.2%; color:#171717; font-family:"Arial Narrow",Arial,sans-serif; }
      .status-6160 .led-row { grid-template-columns:1fr 3.2cqw; min-height:6.6cqw; font-size:clamp(8px,1.35cqw,15px); font-weight:500; }
      .status-6160 .led { width:2.65cqw; height:1.08cqw; }
      .brand-emboss { position:absolute; right:8.6%; bottom:3.35%; height:5%; display:flex; align-items:center; justify-content:center; user-select:none; }
      .brand-firstalert { padding:.25cqw 1.25cqw; border:.12cqw solid rgba(255,255,255,.12); color:rgba(255,255,255,.16); font:700 clamp(11px,1.75cqw,20px)/1 Georgia,serif; text-shadow:0 -.08cqw .1cqw rgba(93,0,0,.48),0 .08cqw .08cqw rgba(255,255,255,.08); }
      .brand-honeywell { color:rgba(92,92,88,.19); font:700 clamp(12px,1.85cqw,21px)/1 Georgia,serif; text-shadow:0 1px rgba(255,255,255,.62),0 -.05cqw .06cqw rgba(80,80,75,.12); }
      .case-notch { position:absolute; left:28.4%; bottom:-.1%; width:2.15%; height:5.5%; background:var(--ha-card-background,#fff); border-radius:.18cqw .18cqw 0 0; box-shadow:inset 0 .08cqw .13cqw rgba(0,0,0,.19); }
      .read-only-note { min-height:18px; opacity:0; color:var(--secondary-text-color); font:500 12px/18px sans-serif; transition:opacity .18s ease; }
      .read-only-note.show{opacity:1}
      @media(max-width:650px){.keypad-shell{min-height:300px}.wrap{gap:4px}}
      @media(prefers-reduced-motion:reduce){.physical-key,.read-only-note{transition:none}}
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
    if (lit) { bg.addColorStop(0, "#b2ed54"); bg.addColorStop(.5, "#9ee247"); bg.addColorStop(1, "#88cb38"); }
    else { bg.addColorStop(0, "#7f9570"); bg.addColorStop(1, "#687a5e"); }
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
        const char = rawChar.toUpperCase();
        const glyph = MATRIX_5X7[char] ?? MATRIX_5X7["?"];
        const baseX = marginX + charIndex * charW + (charW - dot * 5) / 2;
        const baseY = marginY + rowIndex * lineH + (lineH - dot * 7) / 2;
        for (let gx = 0; gx < 5; gx++) {
          const bits = glyph[gx] || 0;
          for (let gy = 0; gy < 7; gy++) {
            if (bits & (1 << gy)) {
              ctx.fillRect(Math.round(baseX + gx * dot), Math.round(baseY + gy * dot), Math.max(1, Math.ceil(px)), Math.max(1, Math.ceil(px)));
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
    this.shadowRoot.querySelectorAll("button[data-key]").forEach(button => {
      button.addEventListener("pointerdown", () => button.classList.add("pressed"));
      button.addEventListener("pointerup", () => button.classList.remove("pressed"));
      button.addEventListener("pointerleave", () => button.classList.remove("pressed"));
      button.addEventListener("click", event => this._handleKey(event.currentTarget));
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
      bubbles:true,
      composed:true,
      detail:{ key, entity:this._config.entity, model:this._config.model },
    }));
  }
}

if (!customElements.get("vista-keypad-card")) customElements.define("vista-keypad-card", VistaKeypadCard);
window.customCards = window.customCards || [];
window.customCards.push({
  type:"vista-keypad-card",
  name:"Vista Keypad",
  description:"Physical VISTA keypad card with 6160CR-2 and 6160 skins.",
  preview:false,
  documentationURL:"https://github.com/wtc-brycel/vistaturbo-hass/tree/main/frontend",
});
console.info(`%c VISTA-KEYPAD-CARD %c v${VISTA_KEYPAD_CARD_VERSION} `,"color:#fff;background:#b40f18;font-weight:700","color:#111;background:#e6e6e2");
