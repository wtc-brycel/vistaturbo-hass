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
        power: null,
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
      power: this._indicatorState("power", null),
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
    const fireTrouble = this._indicatorState("fire_trouble", null);
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
              <span class="fire-glyph" aria-hidden="true">‚óÜ</span>
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
      <div class="keypad-shell kf160" data-model="6160">
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
        --pmÆÈ‹j◊ù~ä€≠Î‚∑