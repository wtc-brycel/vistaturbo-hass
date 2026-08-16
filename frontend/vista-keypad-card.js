const VISTA_KEYPAD_CARD_VERSION = "0.1.0";

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

const FUNCTION_KEYS = ["AWAY", "STAY", "POLICE", "PAGE"];

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
      title: "",
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
    return this._config?.model === "6160" ? 9 : 7;
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
        power: false,
        fireAlarm: null,
        silenced: null,
        supervisory: null,
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
      power: this._indicatorState("power", !unavailable),
      fireAlarm: this._indicatorState("fire_alarm", null),
      silenced: this._indicatorState("silenced", null),
      supervisory: this._indicatorState("supervisory", null),
    };
  }

  _keyButton(key, legend = "", extraClass = "") {
    return `
      <button class="key ${extraClass}" data-key="${escapeHtml(key)}" aria-label="${escapeHtml(key + (legend ? ` ${legend}` : ""))}">
        <span class="key-main">${escapeHtml(key)}</span>
        ${legend ? `<span class="key-legend">${escapeHtml(legend)}</span>` : ""}
      </button>`;
  }

  _functionKey(label, index) {
    const configured = this._config?.function_keys?.[String(index + 1)] ||
      this._config?.function_keys?.[label.toLowerCase()] || label;
    return `
      <button class="function-key" data-key="F${index + 1}" aria-label="${escapeHtml(configured)}">
        <span>${escapeHtml(configured)}</span>
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
      <div class="lcd-bezel">
        <div class="lcd ${backlight}" role="status" aria-live="polite">
          <div>${escapeHtml(display.line1)}</div>
          <div>${escapeHtml(display.line2)}</div>
        </div>
      </div>`;
  }

  _numericPad() {
    return `<div class="numeric-pad">${NUMBER_KEYS.map(([key, legend]) => this._keyButton(key, legend)).join("")}</div>`;
  }

  _speaker() {
    return `
      <div class="speaker" aria-hidden="true">
        <span></span><span></span><span></span><span></span>
      </div>`;
  }

  _render6160CR2(display) {
    const fireTrouble = this._indicatorState("fire_trouble", display.trouble);
    return `
      <div class="keypad-shell cr2" data-model="6160cr2">
        <div class="cr2-top">
          ${this._speaker()}
          ${this._lcd(display)}
        </div>

        <div class="cr2-lower">
          <div class="cr2-status">
            <div class="status-blue">
              ${this._led("ARMED", display.armed, "armed")}
              ${this._led("READY", display.ready, "ready")}
            </div>
            <div class="status-fire">
              ${this._led("POWER", display.power, "power")}
              ${this._led("FIRE ALARM", display.fireAlarm, "fire-alarm")}
              ${this._led("SILENCED", display.silenced, "silenced")}
              ${this._led("SUPERVISORY", display.supervisory, "supervisory")}
              ${this._led("TROUBLE", fireTrouble, "fire-trouble")}
              <span class="fire-glyph" aria-hidden="true">◆</span>
            </div>
          </div>

          <div class="cr2-functions">
            ${FUNCTION_KEYS.map((label, index) => this._functionKey(label, index)).join("")}
          </div>

          ${this._numericPad()}
        </div>
        <div class="case-mark">VISTA TURBO</div>
      </div>`;
  }

  _render6160(display) {
    return `
      <div class="keypad-shell k6160" data-model="6160">
        <div class="k6160-top">
          ${this._speaker()}
          ${this._lcd(display)}
        </div>

        <div class="k6160-lower">
          <div class="k6160-status">
            ${this._led("ARMED", display.armed, "armed")}
            ${this._led("READY", display.ready, "ready")}
          </div>
          <div class="k6160-controls">
            <div class="k6160-functions">
              ${["STAY", "AWAY", "POLICE", "PAGE"].map((label, index) => this._functionKey(label, index)).join("")}
            </div>
            ${this._numericPad()}
          </div>
        </div>
        <div class="door open" aria-hidden="true"><div class="door-panel"></div></div>
        <div class="case-mark">VISTA TURBO</div>
      </div>`;
  }

  _styles() {
    return `
      :host {
        display: block;
        --vista-card-bg: transparent;
        --lcd-on: #9bd83c;
        --lcd-on-deep: #83bd2f;
        --lcd-off: #64715d;
        --lcd-ink: #173017;
        --plastic-white: #efefeb;
        --plastic-white-shadow: #c8c8c2;
        --plastic-red: #d91c23;
        --plastic-red-dark: #a90f16;
        --key-face: #e5e3df;
        --key-edge: #8d8b88;
        --text-dark: #181818;
        --led-green: #a8e439;
        --led-red: #f4473e;
        --led-amber: #f3b33a;
      }

      ha-card {
        overflow: visible;
        background: ${this._config?.show_card_background ? "var(--ha-card-background, var(--card-background-color))" : "transparent"};
        box-shadow: ${this._config?.show_card_background ? "var(--ha-card-box-shadow, none)" : "none"};
        border: ${this._config?.show_card_background ? "var(--ha-card-border-width, 0) solid var(--ha-card-border-color, transparent)" : "0"};
        padding: ${this._config?.show_card_background ? "18px" : "0"};
      }

      .wrap {
        container-type: inline-size;
        display: grid;
        gap: 10px;
        width: 100%;
        justify-items: center;
      }

      .card-title {
        width: min(100%, 860px);
        font: 500 16px/1.3 var(--paper-font-body1_-_font-family, sans-serif);
        color: var(--primary-text-color);
      }

      .keypad-shell {
        box-sizing: border-box;
        position: relative;
        user-select: none;
        -webkit-tap-highlight-color: transparent;
        color: var(--text-dark);
        filter: drop-shadow(0 12px 14px rgba(0, 0, 0, .23));
      }

      .keypad-shell * { box-sizing: border-box; }

      .cr2 {
        width: min(100%, 860px);
        aspect-ratio: 1.46 / 1;
        min-height: 360px;
        padding: 5.4% 6% 4.2%;
        border-radius: 2.4cqw;
        background:
          linear-gradient(135deg, rgba(255,255,255,.16), transparent 28%),
          linear-gradient(180deg, #ee3238 0%, var(--plastic-red) 45%, #c8171d 100%);
        border: .45cqw solid #b4161b;
        box-shadow:
          inset 0 .55cqw .45cqw rgba(255,255,255,.22),
          inset 0 -.7cqw .8cqw rgba(95,0,0,.18),
          inset .55cqw 0 .6cqw rgba(255,255,255,.08);
      }

      .cr2::after {
        content: "";
        position: absolute;
        inset: 2.2% 2% auto 2%;
        height: 1.1%;
        border-top: .18cqw solid rgba(255,255,255,.26);
        border-radius: 50%;
      }

      .cr2-top {
        display: grid;
        grid-template-columns: 23% 1fr;
        gap: 4.5%;
        align-items: center;
        height: 42%;
      }

      .speaker {
        display: grid;
        gap: 1.35cqw;
        place-content: center;
        height: 100%;
      }

      .speaker span {
        display: block;
        width: 11cqw;
        height: .5cqw;
        border-radius: 60% 40%;
        background: #161616;
        box-shadow: inset 0 .1cqw .15cqw rgba(255,255,255,.22);
      }

      .lcd-bezel {
        width: 100%;
        padding: 2.6% 3.2%;
        background: linear-gradient(180deg, rgba(255,255,255,.16), rgba(125,0,0,.05));
        box-shadow:
          inset 0 .4cqw .4cqw rgba(255,255,255,.15),
          0 .7cqw .8cqw rgba(91,0,0,.25);
      }

      .lcd {
        display: grid;
        align-content: center;
        min-height: 9.3cqw;
        padding: .7cqw 1.1cqw;
        border: .33cqw solid rgba(26,44,20,.82);
        box-shadow:
          inset 0 .6cqw .8cqw rgba(25,50,15,.26),
          0 .22cqw .3cqw rgba(255,255,255,.25);
        font-family: "Courier New", "Lucida Console", monospace;
        font-weight: 700;
        font-size: clamp(18px, 4.15cqw, 38px);
        line-height: 1.03;
        letter-spacing: -.16cqw;
        white-space: pre;
        overflow: hidden;
        text-shadow: .06cqw 0 0 currentColor;
        transition: filter .18s ease, background .18s ease;
      }

      .lcd.lit {
        color: var(--lcd-ink);
        background:
          repeating-linear-gradient(90deg, rgba(30,65,18,.04) 0 .08cqw, transparent .08cqw .42cqw),
          linear-gradient(180deg, #a9e34b, #8fca34);
        filter: saturate(1.05) brightness(1.02);
      }

      .lcd.dim {
        color: #293529;
        background: linear-gradient(180deg, #829079, #6d7967);
        filter: saturate(.45) brightness(.88);
      }

      .cr2-lower {
        display: grid;
        grid-template-columns: 31% 17% 1fr;
        gap: 4.5%;
        height: 49%;
        align-items: center;
      }

      .cr2-status {
        align-self: stretch;
        display: grid;
        align-content: center;
        gap: 2.1cqw;
      }

      .status-blue {
        position: relative;
        padding: 1.2cqw 1.3cqw 1.15cqw 1.7cqw;
        border-radius: .9cqw;
        background: linear-gradient(180deg, #176aa1, #135c91);
        color: #eceff2;
        box-shadow: inset 0 .2cqw .2cqw rgba(255,255,255,.14);
      }

      .status-fire {
        position: relative;
        padding-left: 1.7cqw;
        color: #f0dddd;
      }

      .status-fire::after {
        content: "";
        position: absolute;
        right: 8%;
        top: 3%;
        bottom: 3%;
        width: 22%;
        border-right: .18cqw solid #ece3e3;
        border-top: .18cqw solid #ece3e3;
        border-bottom: .18cqw solid #ece3e3;
        border-radius: 0 .8cqw .8cqw 0;
        opacity: .85;
      }

      .fire-glyph {
        position: absolute;
        right: -3%;
        top: 43%;
        font-size: 2.2cqw;
        color: #fff3f3;
        transform: rotate(45deg);
      }

      .led-row {
        display: grid;
        grid-template-columns: 1fr 2.7cqw;
        gap: .6cqw;
        align-items: center;
        min-height: 2.5cqw;
        font-family: Arial, sans-serif;
        font-size: clamp(9px, 1.9cqw, 16px);
        font-weight: 700;
        line-height: 1;
      }

      .status-blue .led-row { grid-template-columns: 1fr 3cqw; }

      .led-label { white-space: nowrap; }

      .led {
        width: 2.45cqw;
        height: 1.15cqw;
        justify-self: center;
        border-radius: 50%;
        background: #4a4a44;
        box-shadow:
          inset .2cqw .18cqw .28cqw rgba(0,0,0,.75),
          inset -.13cqw -.1cqw .16cqw rgba(255,255,255,.18);
        transition: all .16s ease;
      }

      .led.on {
        background: radial-gradient(circle at 35% 30%, #efffb6 0%, var(--led-green) 35%, #5f8c22 75%);
        box-shadow:
          0 0 .6cqw rgba(170,239,61,.95),
          inset .12cqw .1cqw .2cqw rgba(255,255,255,.7);
      }

      .fire-alarm .led.on,
      .silenced .led.on,
      .supervisory .led.on,
      .fire-trouble .led.on {
        background: radial-gradient(circle at 35% 30%, #ffd0c8 0%, var(--led-red) 42%, #8e1612 76%);
        box-shadow: 0 0 .62cqw rgba(244,71,62,.9);
      }

      .power .led.on {
        background: radial-gradient(circle at 35% 30%, #fff3b3 0%, var(--led-amber) 44%, #8b5d16 78%);
        box-shadow: 0 0 .55cqw rgba(243,179,58,.85);
      }

      .led.unknown {
        background: #403f3d;
        opacity: .55;
      }

      .cr2-functions,
      .k6160-functions {
        display: grid;
        gap: 1.9cqw;
        align-content: center;
      }

      button {
        font: inherit;
        color: var(--text-dark);
        cursor: pointer;
        touch-action: manipulation;
      }

      .function-key,
      .key {
        position: relative;
        border: .16cqw solid #6e6b67;
        background: linear-gradient(180deg, #f2f0ed 0%, #dedbd7 62%, #c8c5c1 100%);
        box-shadow:
          0 .35cqw .28cqw rgba(64,0,0,.24),
          inset 0 .2cqw .2cqw rgba(255,255,255,.92),
          inset 0 -.16cqw .18cqw rgba(0,0,0,.13);
        transition: transform .06s ease, box-shadow .06s ease, filter .12s ease;
      }

      .function-key:active,
      .key:active,
      .function-key.pressed,
      .key.pressed {
        transform: translateY(.22cqw);
        box-shadow:
          0 .08cqw .08cqw rgba(64,0,0,.22),
          inset 0 .16cqw .22cqw rgba(0,0,0,.14);
        filter: brightness(.96);
      }

      .function-key {
        min-height: 5.1cqw;
        border-radius: .5cqw;
        font-family: Arial, sans-serif;
        font-weight: 800;
        font-size: clamp(8px, 1.55cqw, 14px);
      }

      .numeric-pad {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 1.65cqw 2cqw;
        align-content: center;
      }

      .key {
        min-height: 5.2cqw;
        display: flex;
        align-items: center;
        justify-content: center;
        gap: .8cqw;
        border-radius: .48cqw;
        font-family: Arial, sans-serif;
      }

      .key-main {
        font-size: clamp(16px, 3.2cqw, 28px);
        font-weight: 500;
        line-height: 1;
      }

      .key-legend {
        font-size: clamp(7px, 1.28cqw, 12px);
        font-weight: 700;
        font-style: italic;
        line-height: 1;
      }

      .case-mark {
        position: absolute;
        right: 10%;
        bottom: 3.5%;
        padding: .35cqw 1cqw;
        border: .16cqw solid rgba(255,255,255,.14);
        color: rgba(255,255,255,.18);
        font: 700 clamp(9px, 1.45cqw, 13px)/1 Arial, sans-serif;
        letter-spacing: .07em;
        text-shadow: 0 -.1cqw .1cqw rgba(86,0,0,.4);
      }

      .k6160 {
        width: min(100%, 650px);
        aspect-ratio: 1.05 / 1;
        min-height: 430px;
        padding: 5.5% 6% 10%;
        border-radius: 1.7cqw 1.7cqw .6cqw .6cqw;
        background:
          linear-gradient(135deg, rgba(255,255,255,.9), transparent 35%),
          linear-gradient(180deg, #f8f8f5 0%, var(--plastic-white) 50%, #dadad5 100%);
        border: .3cqw solid #d0d0ca;
        box-shadow:
          inset 0 .5cqw .7cqw rgba(255,255,255,.9),
          inset 0 -.5cqw .7cqw rgba(95,95,90,.12);
      }

      .k6160-top {
        display: grid;
        grid-template-columns: 24% 1fr;
        gap: 5%;
        height: 32%;
        align-items: center;
      }

      .k6160 .speaker span {
        width: 10cqw;
        height: .42cqw;
      }

      .k6160 .lcd-bezel {
        background: linear-gradient(180deg, #ffffff, #e2e2de);
        box-shadow: 0 .5cqw .8cqw rgba(0,0,0,.11);
      }

      .k6160 .lcd { min-height: 8.3cqw; }

      .k6160-lower {
        display: grid;
        grid-template-columns: 22% 1fr;
        gap: 4%;
        height: 56%;
        align-items: center;
      }

      .k6160-status {
        display: grid;
        gap: 2.2cqw;
        align-content: start;
        padding-top: 3cqw;
      }

      .k6160-status .led-row {
        grid-template-columns: 1fr 2.5cqw;
        font-size: clamp(8px, 1.45cqw, 13px);
      }

      .k6160-controls {
        display: grid;
        grid-template-columns: 23% 1fr;
        gap: 4.3%;
        align-items: center;
      }

      .k6160 .function-key,
      .k6160 .key {
        box-shadow:
          0 .27cqw .3cqw rgba(0,0,0,.17),
          inset 0 .17cqw .2cqw rgba(255,255,255,.95),
          inset 0 -.15cqw .2cqw rgba(0,0,0,.12);
      }

      .k6160 .function-key {
        min-height: 4.3cqw;
        font-size: clamp(7px, 1.25cqw, 11px);
      }

      .k6160 .key {
        min-height: 4.35cqw;
        gap: .5cqw;
      }

      .k6160 .key-main { font-size: clamp(14px, 2.55cqw, 23px); }
      .k6160 .key-legend { font-size: clamp(6px, 1cqw, 9px); }

      .k6160 .case-mark {
        color: rgba(110,110,105,.17);
        border-color: transparent;
        text-shadow: 0 1px rgba(255,255,255,.65);
      }

      .door {
        position: absolute;
        left: 14%;
        right: 5%;
        bottom: -25%;
        height: 28%;
        transform-origin: top center;
        perspective: 800px;
      }

      .door-panel {
        width: 100%;
        height: 100%;
        border-radius: 0 0 1.3cqw 1.3cqw;
        background: linear-gradient(180deg, #e2e2de, #f1f1ed 25%, #deded9);
        border: .25cqw solid #c9c9c3;
        box-shadow:
          inset 0 .3cqw .4cqw rgba(255,255,255,.85),
          0 .7cqw .8cqw rgba(0,0,0,.15);
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
        .wrap { gap: 6px; }
        .cr2 { min-height: 260px; }
        .k6160 { min-height: 350px; }
        .door { bottom: -22%; }
      }

      @media (prefers-reduced-motion: reduce) {
        .function-key, .key, .led, .lcd, .read-only-note { transition: none; }
      }
    `;
  }

  _render() {
    if (!this.shadowRoot || !this._config) return;
    const display = this._displayState();
    const modelHtml = this._config.model === "6160" ? this._render6160(display) : this._render6160CR2(display);
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
window.customCards.push({
  type: "vista-keypad-card",
  name: "Vista Keypad",
  description: "Physical keypad-style card for Vista Turbo HASS keypad display entities.",
  preview: false,
  documentationURL: "https://github.com/wtc-brycel/vistaturbo-hass/tree/main/frontend",
});

console.info(`%c VISTA-KEYPAD-CARD %c v${VISTA_KEYPAD_CARD_VERSION} `, "color:#fff;background:#a91016;font-weight:700", "color:#111;background:#e6e6e2");
