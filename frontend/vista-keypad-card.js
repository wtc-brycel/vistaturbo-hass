const VISTA_KEYPAD_CARD_VERSION = "0.3.28";
const KEYPAD_AUDIT_IDLE_MS = 5000;

const MODEL_ALIASES = {
  "6160cr2": "6160cr2",
  "6160cr-2": "6160cr2",
  "cr2": "6160cr2",
  "6160": "6160",
  "firstalert": "firstalert",
  "first-alert": "firstalert",
  "first_alert": "firstalert",
  "fa": "firstalert",
};

const CASE_COLORS = new Set(["red", "white", "dark"]);
const AUTO_CASE_DEFAULTS = {
  "6160cr2": { day: "red", night: "dark" },
  "6160": { day: "white", night: "dark" },
  "firstalert": { day: "white", night: "dark" },
};

const NUMBER_KEYS = [
  ["1", "OFF"], ["2", "AWAY"], ["3", "STAY"],
  ["4", "MAX"], ["5", "TEST"], ["6", "BYPASS"],
  ["7", "INSTANT"], ["8", "CODE"], ["9", "CHIME"],
  ["*", "READY"], ["0", ""], ["#", ""],
];

const FIRST_ALERT_NUMBER_KEYS = [
  ["1", "OFF"], ["2", "SELECT"], ["3", "SCROLL"],
  ["4", "MAX"], ["5", "TEST"], ["6", "BYPASS"],
  ["7", "INSTANT"], ["8", "CODE"], ["9", "CHIME"],
  ["*", "READY"], ["0", ""], ["#", ""],
];

const FUNCTION_IDS = ["a", "b", "c", "d"];
const DEFAULT_FUNCTION_KEYS = {
  "6160cr2": ["A", "B", "C", "D"],
  "6160": ["A", "B", "C", "D"],
  "firstalert": ["A", "B", "C", "D"],
};

/*
 * Layout metadata lives with the model instead of inside the mobile renderer.
 * Future keypad models can opt into the compact layout by defining their
 * annunciators here without cloning the responsive UI.
 */
const MODEL_PROFILES = {
  "6160cr2": {
    compactFunctionKeys: ["A", "B", "C", "D"],
    compactIndicators: [
      { label: "READY", state: "ready", className: "ready", flash: "ready" },
      { label: "ARMED", state: "armed", className: "armed", flash: "armed" },
      { label: "PWR", state: "power", className: "power", flash: "power" },
      { label: "FIRE", state: "fireAlarm", className: "fire-alarm", flash: "fire_alarm" },
      { label: "SIL", state: "silenced", className: "silenced", flash: "silenced" },
      { label: "SUPV", state: "supervisory", className: "supervisory", flash: "supervisory" },
      { label: "TRBL", state: "trouble", className: "trouble", flash: null },
    ],
  },
  "6160": {
    compactFunctionKeys: ["A", "B", "C", "D"],
    compactIndicators: [
      { label: "READY", state: "ready", className: "ready", flash: "ready" },
      { label: "ARMED", state: "armed", className: "armed", flash: "armed" },
    ],
  },
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

};

const LAYOUT_MODES = new Set(["auto", "physical", "compact"]);

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
  const named = new Set([
    "black", "silver", "gray", "white", "maroon", "red", "purple", "fuchsia",
    "green", "lime", "olive", "yellow", "navy", "blue", "teal", "aqua",
    "orange", "transparent", "rebeccapurple",
  ]);
  const number = "(?:\\d{1,3}%?|(?:0|1)?\\.\\d+)";
  const alpha = "(?:0|1|0?\\.\\d+|1(?:\\.0+)?)";
  const rgb = new RegExp(
    `^rgba?\\(\\s*${number}\\s*,\\s*${number}\\s*,\\s*${number}(?:\\s*,\\s*${alpha})?\\s*\\)$`,
    "i",
  );
  const hsl = /^hsla?\(\s*-?\d+(?:\.\d+)?(?:deg)?\s*,\s*\d{1,3}%\s*,\s*\d{1,3}%(?:\s*,\s*(?:0|1|0?\.\d+|1(?:\.0+)?))?\s*\)$/i;
  const hex = /^#[0-9a-f]{3,4}(?:[0-9a-f]{2})?$/i;
  if (named.has(text.toLowerCase()) || hex.test(text) || rgb.test(text) || hsl.test(text)) {
    return text;
  }
  return fallback;
}

function editorEntityOptions(hass, currentValue = "", domains = null, allowEmpty = false) {
  const states = hass?.states ?? {};
  const allowedDomains = Array.isArray(domains) && domains.length ? new Set(domains) : null;
  const current = String(currentValue ?? "");
  const entityIds = Object.keys(states).filter((entityId) => {
    const dot = entityId.indexOf(".");
    const domain = dot === -1 ? "" : entityId.slice(0, dot);
    return !allowedDomains || allowedDomains.has(domain);
  });

  // Bound the candidate IDs before touching friendly-name metadata. This
  // keeps editor work proportional to the small suggestion list even when HA
  // exposes thousands of unrelated entities.
  entityIds.sort((left, right) => left.localeCompare(right));
  const bounded = entityIds.slice(0, 100);
  if (current && !bounded.includes(current)) bounded.unshift(current);
  if (allowEmpty) bounded.unshift("");
  return bounded.map((entityId) => {
    if (!entityId) return '<option value="" label="None"></option>';
    const friendlyName = String(states[entityId]?.attributes?.friendly_name ?? "").trim();
    const label = friendlyName && friendlyName !== entityId
      ? `${friendlyName} (${entityId})`
      : entityId;
    return `<option value="${escapeHtml(entityId)}" label="${escapeHtml(label)}"></option>`;
  }).join("");
}

/*
 * Synthesized keypad feedback. Cadences are intentionally modeled after
 * conventional VISTA keypad behavior, but exact factory piezo frequencies are
 * not published. Keeping the profiles synthesized avoids fetch/decode latency.
 */
const KEYPAD_SOUND_PROFILES = {
  keypress: { steps: [[1450, 38, 0]] },
  chime: { steps: [[1200, 75, 70], [1200, 75, 70], [1200, 90, 0]] },
  trouble: { steps: [[1000, 110, 85], [1000, 110, 0]] },
  supervisory: { steps: [[900, 120, 75], [700, 120, 0]] },
  auxiliary: { loop: true, steps: [[900, 250, 35], [650, 250, 35]] },
  fire: { loop: true, steps: [[1000, 500, 500], [1000, 500, 500], [1000, 500, 1500]] },
  burglary: { loop: true, continuous: true, frequency: 950 },
};

class VistaKeypadAudio {
  constructor() {
    this.ctx = null;
    this._loopName = null;
    this._loopSignature = "";
    this._loopTimer = null;
    this._loopNodes = new Set();
    this._desiredLoop = null;
    this._desiredConfig = null;
  }

  _context() {
    if (this.ctx) return this.ctx;
    const AudioCtx = window.AudioContext || window.webkitAudioContext;
    if (!AudioCtx) return null;
    try {
      this.ctx = new AudioCtx({ latencyHint: "interactive" });
    } catch (_) {
      this.ctx = new AudioCtx();
    }
    return this.ctx;
  }

  async unlock() {
    const ctx = this._context();
    if (!ctx) return false;
    if (ctx.state === "suspended") {
      try { await ctx.resume(); } catch (_) { return false; }
    }
    const ready = ctx.state === "running";
    if (ready && this._desiredLoop && this._loopName !== this._desiredLoop) {
      this._startLoopNow(this._desiredLoop, this._desiredConfig ?? {});
    }
    return ready;
  }

  _volume(config, profileName) {
    if (profileName === "keypress") {
      return Math.max(0, Math.min(1, Number(config.keypress_volume ?? config.volume ?? 0.035)));
    }
    return Math.max(0, Math.min(1, Number(config.alarm_volume ?? 0.065)));
  }

  _scheduleTone(frequency, durationMs, volume, startAt, targetSet = null) {
    const ctx = this._context();
    if (!ctx || ctx.state !== "running") return null;

    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    const start = Math.max(ctx.currentTime, startAt ?? ctx.currentTime);
    const duration = Math.max(0.015, Number(durationMs || 0) / 1000);
    const stop = start + duration;

    osc.type = "square";
    osc.frequency.setValueAtTime(Math.max(80, Number(frequency) || 1000), start);
    gain.gain.setValueAtTime(0.0001, start);
    gain.gain.exponentialRampToValueAtTime(Math.max(volume, 0.0002), start + 0.002);
    gain.gain.setValueAtTime(Math.max(volume, 0.0002), Math.max(start + 0.003, stop - 0.004));
    gain.gain.exponentialRampToValueAtTime(0.0001, stop);

    osc.connect(gain).connect(ctx.destination);
    if (targetSet) targetSet.add(osc);
    osc.addEventListener?.("ended", () => targetSet?.delete(osc), { once: true });
    osc.start(start);
    osc.stop(stop + 0.004);
    return osc;
  }

  _scheduleProfile(name, config = {}, targetSet = null) {
    const ctx = this._context();
    const profile = KEYPAD_SOUND_PROFILES[name];
    if (!ctx || ctx.state !== "running" || !profile) return 0;

    const volume = this._volume(config, name);
    let at = ctx.currentTime + 0.002;
    let totalMs = 0;
    const steps = name === "keypress" && (config.frequency || config.duration_ms)
      ? [[Number(config.frequency ?? 1450), Number(config.duration_ms ?? 38), 0]]
      : profile.steps ?? [];

    for (const [frequency, durationMs, gapMs] of steps) {
      this._scheduleTone(frequency, durationMs, volume, at, targetSet);
      const stepMs = Number(durationMs || 0) + Number(gapMs || 0);
      totalMs += stepMs;
      at += stepMs / 1000;
    }
    return totalMs;
  }

  async keypress(config = {}) {
    if (!config.enabled || config.keypress === false) return false;
    if (!(await this.unlock())) return false;
    this._scheduleProfile("keypress", config);
    return true;
  }

  async play(name, config = {}) {
    if (!config.enabled) return false;
    if (!(await this.unlock())) return false;
    if (!KEYPAD_SOUND_PROFILES[name] || KEYPAD_SOUND_PROFILES[name].loop) return false;
    this._scheduleProfile(name, config);
    return true;
  }

  setLoop(name, config = {}) {
    const enabled = Boolean(config.enabled && config.state_sounds);
    const next = enabled && name && KEYPAD_SOUND_PROFILES[name]?.loop ? name : null;
    this._desiredLoop = next;
    this._desiredConfig = config;

    if (!next) {
      this.stopLoop();
      return;
    }

    const signature = JSON.stringify([next, this._volume(config, next)]);
    if (this._loopName === next && this._loopSignature === signature) return;

    const ctx = this._context();
    if (ctx?.state === "running") this._startLoopNow(next, config);
  }

  _startLoopNow(name, config = {}) {
    this.stopLoop(false);
    const ctx = this._context();
    const profile = KEYPAD_SOUND_PROFILES[name];
    if (!ctx || ctx.state !== "running" || !profile?.loop) return;

    this._loopName = name;
    this._loopSignature = JSON.stringify([name, this._volume(config, name)]);

    if (profile.continuous) {
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      const now = ctx.currentTime;
      const volume = this._volume(config, name);
      osc.type = "square";
      osc.frequency.setValueAtTime(profile.frequency ?? 950, now);
      gain.gain.setValueAtTime(0.0001, now);
      gain.gain.exponentialRampToValueAtTime(Math.max(volume, 0.0002), now + 0.008);
      osc.connect(gain).connect(ctx.destination);
      this._loopNodes.add(osc);
      osc.start(now);
      return;
    }

    const scheduleCycle = () => {
      if (this._loopName !== name || this._desiredLoop !== name) return;
      const cycleMs = this._scheduleProfile(name, config, this._loopNodes);
      this._loopTimer = setTimeout(scheduleCycle, Math.max(50, cycleMs - 15));
    };
    scheduleCycle();
  }

  stopLoop(clearDesired = true) {
    clearTimeout(this._loopTimer);
    this._loopTimer = null;
    for (const node of this._loopNodes) {
      try { node.stop(); } catch (_) {}
    }
    this._loopNodes.clear();
    this._loopName = null;
    this._loopSignature = "";
    if (clearDesired) {
      this._desiredLoop = null;
      this._desiredConfig = null;
    }
  }

  stopAll() {
    this.stopLoop();
  }
}

class VistaKeypadHaptics {
  pulse(config = {}) {
    if (!config.enabled || typeof navigator === "undefined" || typeof navigator.vibrate !== "function") {
      return false;
    }
    try {
      return navigator.vibrate(Math.max(1, Math.min(100, Number(config.keypress_ms ?? 10))));
    } catch (_) {
      return false;
    }
  }

  stop() {
    try { navigator.vibrate?.(0); } catch (_) {}
  }
}

function cloneEditorConfig(config = {}) {
  const clone = { ...config };
  if (config.sound && typeof config.sound === "object") clone.sound = { ...config.sound };
  if (config.haptic && typeof config.haptic === "object") clone.haptic = { ...config.haptic };
  if (config.function_keys && typeof config.function_keys === "object") {
    clone.function_keys = {};
    for (const [key, value] of Object.entries(config.function_keys)) {
      clone.function_keys[key] = value && typeof value === "object" ? { ...value } : value;
    }
  }
  return clone;
}

class VistaKeypadCardEditor extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._config = {};
    this._hass = null;
    this._rendered = false;
    this._hasHass = false;
  }

  set hass(hass) {
    const shouldRender = !this._rendered || !this._hasHass;
    this._hass = hass;
    this._hasHass = true;
    if (shouldRender) this._render();
  }

  setConfig(config) {
    const next = cloneEditorConfig(config ?? {});
    const changed = JSON.stringify(next) !== JSON.stringify(this._config);
    this._config = next;
    if (!this._rendered || changed) this._render();
  }

  _emit(config) {
    this._config = cloneEditorConfig(config);
    this.dispatchEvent(new CustomEvent("config-changed", {
      detail: { config: this._config },
      bubbles: true,
      composed: true,
    }));
  }

  _topLevel(name, value) {
    const next = cloneEditorConfig(this._config);
    if (["title", "day_case_color", "night_case_color"].includes(name) && value === "") {
      delete next[name];
    } else {
      next[name] = value;
    }
    this._emit(next);
  }

  _nested(section, name, value) {
    const next = cloneEditorConfig(this._config);
    const current = next[section] && typeof next[section] === "object" ? next[section] : {};
    next[section] = { ...current, [name]: value };
    this._emit(next);
  }

  _functionLabel(id, value) {
    const next = cloneEditorConfig(this._config);
    const functions = { ...(next.function_keys ?? {}) };
    const existing = functions[id];
    const trimmed = String(value ?? "").trim();

    if (existing && typeof existing === "object") {
      const updated = { ...existing };
      delete updated.label;
      if (trimmed) updated.text = trimmed;
      else delete updated.text;
      if (Object.keys(updated).length) functions[id] = updated;
      else delete functions[id];
    } else if (trimmed) {
      functions[id] = trimmed;
    } else {
      delete functions[id];
    }

    if (Object.keys(functions).length) next.function_keys = functions;
    else delete next.function_keys;
    this._emit(next);
  }

  _functionText(id) {
    const raw = this._config?.function_keys?.[id] ?? this._config?.function_keys?.[id.toUpperCase()];
    if (typeof raw === "string") return raw;
    if (raw && typeof raw === "object") return String(raw.text ?? raw.label ?? "");
    return "";
  }

  _option(value, label, current) {
    return `<option value="${escapeHtml(value)}" ${value === current ? "selected" : ""}>${escapeHtml(label)}</option>`;
  }

  _render() {
    if (!this.shadowRoot) return;

    const model = MODEL_ALIASES[String(this._config.model ?? "6160cr2").toLowerCase()] ?? "6160cr2";
    const layout = LAYOUT_MODES.has(String(this._config.layout ?? "auto").toLowerCase())
      ? String(this._config.layout ?? "auto").toLowerCase()
      : "auto";
    const requestedCaseColor = String(this._config.case_color ?? "auto").toLowerCase();
    const caseColor = requestedCaseColor === "auto" || CASE_COLORS.has(requestedCaseColor) ? requestedCaseColor : "auto";
    const soundInput = this._config.sound === true
      ? { enabled: true }
      : this._config.sound && typeof this._config.sound === "object" ? this._config.sound : {};
    const sound = {
      enabled: false,
      keypress: true,
      state_sounds: false,
      volume: 0.035,
      alarm_volume: 0.065,
      chime: true,
      trouble: true,
      supervisory: true,
      alarm_entity: "",
      aux_entity: "",
      ...soundInput,
    };
    const hapticInput = this._config.haptic === true
      ? { enabled: true }
      : this._config.haptic && typeof this._config.haptic === "object" ? this._config.haptic : {};
    const haptic = { enabled: false, keypress_ms: 10, ...hapticInput };
    const defaultFunctions = MODEL_PROFILES[model]?.compactFunctionKeys ?? DEFAULT_FUNCTION_KEYS[model] ?? ["A", "B", "C", "D"];
    const keypadEntityOptions = editorEntityOptions(this._hass, this._config.entity, ["sensor"]);
    const alarmEntityOptions = editorEntityOptions(this._hass, sound.alarm_entity, null, true);
    const auxEntityOptions = editorEntityOptions(this._hass, sound.aux_entity, null, true);
    const checked = (value) => value ? "checked" : "";

    this.shadowRoot.innerHTML = `<style>
      :host{display:block;color:var(--primary-text-color);font-family:var(--paper-font-body1_-_font-family,system-ui,sans-serif)}
      *{box-sizing:border-box}
      .editor{display:grid;gap:14px;padding:4px 0 12px}
      .section{display:grid;gap:10px;padding:12px;border:1px solid var(--divider-color,#d7d7d7);border-radius:10px;background:var(--card-background-color,transparent)}
      h3{margin:0;font-size:14px;line-height:1.2}
      .grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}
      .field{display:grid;gap:5px;min-width:0}
      .field.full{grid-column:1/-1}
      label,.label{font-size:12px;color:var(--secondary-text-color)}
      input[type=text],input[type=search],input[type=number],select{width:100%;min-height:40px;padding:7px 9px;border:1px solid var(--divider-color,#aaa);border-radius:7px;background:var(--card-background-color,#fff);color:var(--primary-text-color,#111);font:inherit}
      input[type=range]{width:100%}
      .toggle{display:flex;align-items:center;justify-content:space-between;gap:10px;min-height:34px}
      .toggle input{width:20px;height:20px}
      .range-row{display:grid;grid-template-columns:1fr 54px;gap:8px;align-items:center}
      .value{font:11px/1 ui-monospace,SFMono-Regular,Menlo,monospace;color:var(--secondary-text-color);text-align:right}
      .functions{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px}
      .note{font-size:11px;line-height:1.4;color:var(--secondary-text-color)}
      .readonly{padding:8px 10px;border-radius:7px;background:var(--secondary-background-color,rgba(127,127,127,.08));font-size:11px;line-height:1.4}
      @media(max-width:520px){.grid{grid-template-columns:1fr}.functions{grid-template-columns:repeat(2,minmax(0,1fr))}.field.full{grid-column:auto}}
    </style>
    <div class="editor">
      <section class="section">
        <h3>Keypad</h3>
        <div class="grid">
          <div class="field full"><label for="entity">Keypad entity</label><input id="entity" data-top="entity" type="search" list="keypad-entity-list" autocomplete="off" value="${escapeHtml(this._config.entity ?? "")}" placeholder="Search sensor entities"><datalist id="keypad-entity-list">${keypadEntityOptions}</datalist></div>
          <div class="field"><label for="model">Style</label><select id="model" data-top="model">${this._option("6160cr2", "6160CR-2", model)}${this._option("6160", "6160", model)}${this._option("firstalert", "First Alert", model)}</select></div>
          <div class="field"><label for="layout">Layout</label><select id="layout" data-top="layout">${this._option("auto", "Auto", layout)}${this._option("physical", "Physical", layout)}${this._option("compact", "Compact", layout)}</select></div>
          <div class="field full"><label for="title">Title</label><input id="title" data-top="title" type="text" value="${escapeHtml(this._config.title ?? "")}" placeholder="Optional"></div>
          <div class="toggle field full"><span><span class="label">Card background</span></span><input data-top="show_card_background" type="checkbox" ${checked(Boolean(this._config.show_card_background))}></div>
        </div>
        <div class="toggle"><span class="label">Enable keypad input</span><input data-control-toggle type="checkbox" ${checked(this._config.read_only === false)}></div>
        <div class="readonly">Requires bridge <code>control_enabled</code> and <code>keypad_control_enabled</code>. A-D function buttons remain inert until explicitly mapped.</div>
      </section>

      <section class="section">
        <h3>Appearance</h3>
        <div class="grid">
          <div class="field"><label for="case">Case color</label><select id="case" data-top="case_color">${this._option("auto", "Auto", caseColor)}${this._option("red", "Red", caseColor)}${this._option("white", "White", caseColor)}${this._option("dark", "Dark", caseColor)}</select></div>
          <div></div>
          <div class="field"><label for="day-case">Day case override</label><select id="day-case" data-top="day_case_color">${this._option("", "Model default", this._config.day_case_color ?? "")}${this._option("red", "Red", this._config.day_case_color ?? "")}${this._option("white", "White", this._config.day_case_color ?? "")}${this._option("dark", "Dark", this._config.day_case_color ?? "")}</select></div>
          <div class="field"><label for="night-case">Night case override</label><select id="night-case" data-top="night_case_color">${this._option("", "Model default", this._config.night_case_color ?? "")}${this._option("red", "Red", this._config.night_case_color ?? "")}${this._option("white", "White", this._config.night_case_color ?? "")}${this._option("dark", "Dark", this._config.night_case_color ?? "")}</select></div>
        </div>
      </section>

      <section class="section">
        <h3>Sound</h3>
        <div class="grid">
          <div class="toggle"><span class="label">Enable sound</span><input data-sound="enabled" type="checkbox" ${checked(Boolean(sound.enabled))}></div>
          <div class="toggle"><span class="label">Key chirp</span><input data-sound="keypress" type="checkbox" ${checked(sound.keypress !== false)}></div>
          <div class="toggle"><span class="label">Panel state sounds</span><input data-sound="state_sounds" type="checkbox" ${checked(Boolean(sound.state_sounds))}></div>
          <div class="toggle"><span class="label">Zone chime</span><input data-sound="chime" type="checkbox" ${checked(sound.chime !== false)}></div>
          <div class="toggle"><span class="label">Trouble / check</span><input data-sound="trouble" type="checkbox" ${checked(sound.trouble !== false)}></div>
          <div class="toggle"><span class="label">Supervisory</span><input data-sound="supervisory" type="checkbox" ${checked(sound.supervisory !== false)}></div>
          <div class="field"><label>Key chirp volume</label><div class="range-row"><input data-sound="volume" data-number="1" type="range" min="0" max="0.20" step="0.005" value="${escapeHtml(sound.volume)}"><span class="value">${Number(sound.volume).toFixed(3)}</span></div></div>
          <div class="field"><label>Alarm volume</label><div class="range-row"><input data-sound="alarm_volume" data-number="1" type="range" min="0" max="0.20" step="0.005" value="${escapeHtml(sound.alarm_volume)}"><span class="value">${Number(sound.alarm_volume).toFixed(3)}</span></div></div>
          <div class="field"><label for="alarm-entity">Burglary entity override</label><input id="alarm-entity" data-sound="alarm_entity" type="search" list="alarm-entity-list" autocomplete="off" value="${escapeHtml(sound.alarm_entity ?? "")}" placeholder="Optional"><datalist id="alarm-entity-list">${alarmEntityOptions}</datalist></div>
          <div class="field"><label for="aux-entity">Auxiliary entity override</label><input id="aux-entity" data-sound="aux_entity" type="search" list="aux-entity-list" autocomplete="off" value="${escapeHtml(sound.aux_entity ?? "")}" placeholder="Optional"><datalist id="aux-entity-list">${auxEntityOptions}</datalist></div>
        </div>
        <div class="note">The bridge-native <code>sound_mode</code> remains preferred. Entity overrides are only for installations that need an alternate Home Assistant source.</div>
      </section>

      <section class="section">
        <h3>Haptic feedback</h3>
        <div class="grid">
          <div class="toggle"><span class="label">Enable haptics</span><input data-haptic="enabled" type="checkbox" ${checked(Boolean(haptic.enabled))}></div>
          <div class="field"><label for="haptic-ms">Keypress duration (ms)</label><input id="haptic-ms" data-haptic="keypress_ms" data-number="1" type="number" min="1" max="100" step="1" value="${escapeHtml(haptic.keypress_ms)}"></div>
        </div>
        <div class="note">Haptics are best-effort and only work when the browser exposes vibration support.</div>
      </section>

      <section class="section">
        <h3>Function key labels</h3>
        <div class="functions">
          ${FUNCTION_IDS.map((id, index) => `<div class="field"><label>${id.toUpperCase()}</label><input data-function="${id}" type="text" value="${escapeHtml(this._functionText(id))}" placeholder="${escapeHtml(defaultFunctions[index] ?? id.toUpperCase())}"></div>`).join("")}
        </div>
        <div class="note">Leave a label blank to use the selected model's default. Per-key colors and advanced indicator/flashing entity mappings remain available in YAML.</div>
      </section>
    </div>`;

    this.shadowRoot.querySelector("[data-control-toggle]")?.addEventListener("change", (event) => {
      this._topLevel("read_only", !event.currentTarget.checked);
    });
    this.shadowRoot.querySelectorAll("[data-top]").forEach((el) => {
      el.addEventListener("change", () => {
        const value = el.type === "checkbox" ? el.checked : el.value;
        this._topLevel(el.dataset.top, value);
      });
    });
    this.shadowRoot.querySelectorAll("[data-sound]").forEach((el) => {
      el.addEventListener("change", () => {
        const value = el.type === "checkbox" ? el.checked : el.dataset.number ? Number(el.value) : el.value || null;
        this._nested("sound", el.dataset.sound, value);
      });
    });
    this.shadowRoot.querySelectorAll("[data-haptic]").forEach((el) => {
      el.addEventListener("change", () => {
        const value = el.type === "checkbox" ? el.checked : el.dataset.number ? Number(el.value) : el.value;
        this._nested("haptic", el.dataset.haptic, value);
      });
    });
    this.shadowRoot.querySelectorAll("[data-function]").forEach((el) => {
      el.addEventListener("change", () => this._functionLabel(el.dataset.function, el.value));
    });
    this._rendered = true;
  }
}

class VistaKeypadCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._config = null;
    this._hass = null;
    this._pressTimer = null;
    this._lastRenderSignature = null;
    this._resizeObserver = null;
    this._resizeFrame = 0;
    this._themeMedia = null;
    this._themeMediaHandler = null;
    this._audio = new VistaKeypadAudio();
    this._haptics = new VistaKeypadHaptics();
    this._feedbackSnapshot = null;
    this._audioUnlockHandler = null;
    this._keyPressSend = Promise.resolve();
    this._auditInteractionId = null;
    this._auditInteractionTimer = null;
    this._lifecycleGeneration = 0;
  }

  connectedCallback() {
    this._lifecycleGeneration += 1;
    this._installThemeListener();
    this._syncAudioUnlockListener();
  }

  disconnectedCallback() {
    this._lifecycleGeneration += 1;
    this._resizeObserver?.disconnect();
    this._resizeObserver = null;
    if (this._resizeFrame) {
      cancelAnimationFrame(this._resizeFrame);
      this._resizeFrame = 0;
    }
    if (this._themeMedia && this._themeMediaHandler) {
      if (this._themeMedia.removeEventListener) {
        this._themeMedia.removeEventListener("change", this._themeMediaHandler);
      } else {
        this._themeMedia.removeListener?.(this._themeMediaHandler);
      }
    }
    this._themeMedia = null;
    this._themeMediaHandler = null;
    clearTimeout(this._pressTimer);
    clearTimeout(this._auditInteractionTimer);
    this._auditInteractionTimer = null;
    this._auditInteractionId = null;
    this._removeAudioUnlockListener();
    this._audio.stopAll();
    this._haptics.stop();
  }

  _installThemeListener() {
    if (this._themeMedia || typeof window === "undefined" || !window.matchMedia) return;
    this._themeMedia = window.matchMedia("(prefers-color-scheme: dark)");
    this._themeMediaHandler = () => {
      if (
        this._config?.case_color === "auto" &&
        typeof this._hass?.themes?.darkMode !== "boolean"
      ) {
        this._lastRenderSignature = null;
        this._render();
      }
    };
    if (this._themeMedia.addEventListener) {
      this._themeMedia.addEventListener("change", this._themeMediaHandler);
    } else {
      this._themeMedia.addListener?.(this._themeMediaHandler);
    }
  }

  _audioUnlocked() {
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

  static async getConfigElement() {
    return document.createElement("vista-keypad-card-editor");
  }

  static getStubConfig() {
    return {
      entity: "sensor.vista_partition_1_keypad",
      model: "6160cr2",
      case_color: "auto",
      layout: "auto",
      read_only: true,
      sound: { enabled: false },
      haptic: { enabled: false },
    };
  }

  setConfig(config) {
    if (!config?.entity) throw new Error("vista-keypad-card requires an entity");

    const model = MODEL_ALIASES[String(config.model ?? "6160cr2").toLowerCase()];
    if (!model) throw new Error("model must be 6160cr2, 6160, or firstalert");

    const caseColor = String(config.case_color ?? "auto").toLowerCase();
    if (caseColor !== "auto" && !CASE_COLORS.has(caseColor)) {
      throw new Error("case_color must be auto, red, white, or dark");
    }

    const layout = String(config.layout ?? "auto").toLowerCase();
    if (!LAYOUT_MODES.has(layout)) {
      throw new Error("layout must be auto, physical, or compact");
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

    const soundInput = config.sound === true
      ? { enabled: true }
      : config.sound && typeof config.sound === "object"
        ? config.sound
        : {};
    const sound = {
      enabled: false,
      keypress: true,
      state_sounds: false,
      volume: 0.035,
      alarm_volume: 0.065,
      trouble: true,
      supervisory: true,
      chime: true,
      alarm_entity: null,
      aux_entity: null,
      ...soundInput,
    };
    const hapticInput = config.haptic === true
      ? { enabled: true }
      : config.haptic && typeof config.haptic === "object"
        ? config.haptic
        : {};
    const haptic = { enabled: false, keypress_ms: 10, ...hapticInput };

    this._config = {
      title: "",
      model,
      case_color: "auto",
      layout: "auto",
      day_case_color: null,
      night_case_color: null,
      read_only: true,
      show_card_background: false,
      function_keys: {},
      indicators: {},
      indicator_flashing: {},
      led_flash_period_ms: 1000,
      sound,
      haptic,
      ...config,
      model,
      case_color: caseColor,
      layout,
      day_case_color: dayCaseColor,
      night_case_color: nightCaseColor,
      sound,
      haptic,
    };
    this._feedbackSnapshot = null;
    this._lastRenderSignature = null;
    if (this._hass) this._syncFeedback(true);
    this._syncAudioUnlockListener();
    this._render();
    this._lastRenderSignature = this._renderSignature(this._hass);
  }

  set hass(hass) {
    this._hass = hass;
    this._syncFeedback();
    const signature = this._renderSignature(hass);
    if (signature === this._lastRenderSignature) return;
    this._lastRenderSignature = signature;
    this._render();
  }

  getCardSize() {
    return 7;
  }

  getGridOptions() {
    return {
      columns: 12,
      min_columns: 4,
      max_columns: 12,
    };
  }

  _renderSignature(hass) {
    const state = this._config?.entity ? hass?.states?.[this._config.entity] : null;
    const a = state?.attributes ?? {};
    const externalIndicators = Object.entries(this._config?.indicators ?? {}).map(
      ([name, entityId]) => [name, entityId, hass?.states?.[entityId]?.state ?? null]
    );
    const externalFlashing = Object.entries(this._config?.indicator_flashing ?? {}).map(
      ([name, raw]) => {
        const entityId =
          typeof raw === "string"
            ? raw
            : raw && typeof raw === "object" && typeof raw.entity === "string"
              ? raw.entity
              : null;
        return [name, entityId, entityId ? hass?.states?.[entityId]?.state ?? null : raw];
      }
    );

    return JSON.stringify([
      state?.state ?? null,
      a.line_1 ?? null,
      a.line_2 ?? null,
      a.ready ?? null,
      a.armed ?? null,
      a.trouble ?? null,
      a.backlight ?? null,
      a.power ?? null,
      a.fire_alarm ?? null,
      a.silenced ?? null,
      a.supervisory ?? null,
      a.burglary_alarm ?? null,
      a.auxiliary_alarm ?? null,
      a.sound_mode ?? null,
      a.chime_sequence ?? null,
      a.chime_zone ?? null,
      a.chime_descriptor ?? null,
      a.control_enabled ?? null,
      a.command_topic ?? null,
      hass?.themes?.darkMode ?? null,
      externalIndicators,
      externalFlashing,
    ]);
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

  _entityActive(entityId, activeStates = ["on", "triggered", "alarm", "active"]) {
    const entity = this._entityState(entityId);
    if (!entity) return false;
    return activeStates.includes(String(entity.state ?? "").toLowerCase());
  }

  _feedbackState(display) {
    return {
      ready: display.ready,
      armed: display.armed,
      trouble: display.trouble,
      fireAlarm: display.fireAlarm,
      silenced: display.silenced,
      supervisory: display.supervisory,
      burglaryAlarm: display.burglaryAlarm,
      auxiliaryAlarm: display.auxiliaryAlarm,
      soundMode: display.soundMode,
      chimeSequence: display.chimeSequence,
    };
  }

  _syncFeedback(suppressOneShots = false) {
    const sound = this._config?.sound ?? {};
    this._syncAudioUnlockListener();
    const display = this._config ? this._displayState() : null;
    if (!display) return;

    let loop = null;
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
    this._audio.setLoop(loop, sound);

    const current = this._feedbackState(display);
    const previous = this._feedbackSnapshot;
    this._feedbackSnapshot = current;
    if (suppressOneShots || !previous || !sound.enabled || !sound.state_sounds || loop) return;

    if (sound.chime !== false && current.chimeSequence > previous.chimeSequence) {
      this._audio.play("chime", sound).catch(() => {});
      return;
    }
    if (sound.supervisory !== false && !previous.supervisory && current.supervisory) {
      this._audio.play("supervisory", sound).catch(() => {});
      return;
    }
    if (sound.trouble !== false && !previous.trouble && current.trouble) {
      this._audio.play("trouble", sound).catch(() => {});
    }
  }

  async _keyPressFeedback() {
    const sound = this._config?.sound ?? {};
    const haptic = this._config?.haptic ?? {};
    this._haptics.pulse(haptic);
    await this._audio.keypress(sound).catch(() => false);
    this._syncFeedback();
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

    const unavailableDisplay = (line2) => ({
        available: false,
        line1: exactLine("VISTA OFFLINE"),
        line2: exactLine(line2),
        ready: false,
        armed: false,
        trouble: false,
        backlight: false,
        power: null,
        fireAlarm: null,
        silenced: null,
        supervisory: null,
        burglaryAlarm: null,
        auxiliaryAlarm: null,
        soundMode: "unknown",
        chimeSequence: 0,
        chimeZone: null,
        chimeDescriptor: "",
        controlEnabled: false,
        commandTopic: "",
        flashing: {
          armed: false,
          ready: false,
          power: false,
          fire_alarm: false,
          silenced: false,
          supervisory: false,
        },
      });

    if (!state) return unavailableDisplay("ENTITY MISSING");

    const a = state.attributes ?? {};
    const unavailable = ["unknown", "unavailable"].includes(String(state.state ?? "").toLowerCase());
    if (unavailable) return unavailableDisplay("STATE OFFLINE");
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
      burglaryAlarm: a.burglary_alarm === null || a.burglary_alarm === undefined ? null : boolValue(a.burglary_alarm),
      auxiliaryAlarm: a.auxiliary_alarm === null || a.auxiliary_alarm === undefined ? null : boolValue(a.auxiliary_alarm),
      soundMode: ["none", "fire", "burglary", "auxiliary", "unknown"].includes(String(a.sound_mode ?? "").toLowerCase())
        ? String(a.sound_mode).toLowerCase()
        : null,
      chimeSequence: Number(a.chime_sequence ?? 0) || 0,
      chimeZone: a.chime_zone ?? null,
      chimeDescriptor: String(a.chime_descriptor ?? ""),
      controlEnabled: boolValue(a.control_enabled, false),
      commandTopic: String(a.command_topic ?? ""),
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

  _functionKey(index, model, compact = false, disabled = false) {
    const profile = MODEL_PROFILES[model];
    const fallbackText = compact
      ? profile?.compactFunctionKeys?.[index] ?? DEFAULT_FUNCTION_KEYS[model][index]
      : DEFAULT_FUNCTION_KEYS[model][index];
    const def = this._functionDefinition(index, fallbackText);
    const style = [
      def.background ? `--key-custom-bg:${def.background}` : "",
      def.color ? `--key-custom-color:${def.color}` : "",
    ].filter(Boolean).join(";");

    return `<button class="physical-key function-key" data-key="${FUNCTION_IDS[index].toUpperCase()}" ${disabled ? "disabled" : ""} style="${escapeHtml(style)}" aria-label="${escapeHtml(def.text || FUNCTION_IDS[index].toUpperCase())}">
      <span class="function-label">${escapeHtml(def.text)}</span>
    </button>`;
  }

  _numberKey(key, legend, disabled = false) {
    return `<button class="physical-key number-key" data-key="${escapeHtml(key)}" ${disabled ? "disabled" : ""} aria-label="${escapeHtml(`${key} ${legend}`.trim())}">
      <span class="number-main">${escapeHtml(key)}</span>
      ${legend ? `<span class="number-legend">${escapeHtml(legend)}</span>` : ""}
    </button>`;
  }

  _controls(model, compact = false, disabled = false) {
    const functions = FUNCTION_IDS.map(
      (_, i) => `<div class="grid-slot function-slot slot-r${i + 1}">${this._functionKey(i, model, compact, disabled)}</div>`
    ).join("");

    const numberKeys = MODEL_PROFILES[model]?.numberKeys ?? NUMBER_KEYS;
    const numeric = numberKeys.map(([key, legend], i) => {
      const row = Math.floor(i / 3) + 1;
      const col = (i % 3) + 2;
      return `<div class="grid-slot numeric-slot slot-r${row} slot-c${col}">${this._numberKey(key, legend, disabled)}</div>`;
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

  _compactIndicator(item, display) {
    const state = display[item.state] ?? null;
    const flashing = item.flash ? Boolean(display.flashing?.[item.flash]) : false;
    const status = state === null ? "unknown" : state ? "on" : "off";
    const flashClass = state === true && flashing ? " flashing" : "";
    const spoken = `${item.label} ${status}${flashClass ? " flashing" : ""}`;

    return `<div class="compact-indicator led-row ${escapeHtml(item.className)}">
      <span class="led ${status}${flashClass}" aria-label="${escapeHtml(spoken)}"></span>
      <span class="compact-indicator-label">${escapeHtml(item.label)}</span>
    </div>`;
  }

  _compactStatus(model, display) {
    const profile = MODEL_PROFILES[model];
    const indicators = profile?.compactIndicators ?? [];
    if (!indicators.length) return "";
    return `<div class="compact-status" aria-label="Keypad status">
      ${indicators.map((item) => this._compactIndicator(item, display)).join("")}
    </div>`;
  }

  _firstAlertStatus(display) {
    const indicators = MODEL_PROFILES.firstalert.compactIndicators;
    return `<div class="fa-status" aria-label="Keypad status">
      ${indicators.map((item) => this._compactIndicator(item, display)).join("")}
    </div>`;
  }

  _firstAlertControls(portrait = false, disabled = false) {
    const functions = FUNCTION_IDS.map(
      (_, i) => `<div class="fa-function-slot">${this._functionKey(i, "firstalert", true, disabled)}</div>`
    ).join("");
    const numeric = FIRST_ALERT_NUMBER_KEYS.map(
      ([key, legend]) => `<div class="fa-number-slot">${this._numberKey(key, legend, disabled)}</div>`
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
      ${this._firstAlertControls(portrait, !display.available)}
      <div class="fa-brand" aria-hidden="true">FIRST ALERT STYLE</div>
    </div>`;
  }

  _renderCompact(model, display) {
    if (model === "firstalert") return this._renderFirstAlert(display, true);
    const resolvedCaseColor = this._resolvedCaseColor(model);
    const caseClass = `case-${resolvedCaseColor}`;

    return `<div class="compact-shell compact-${model} ${caseClass}" data-model="${model}" data-case-color="${escapeHtml(resolvedCaseColor)}">
      <div class="compact-lcd-frame">
        <canvas class="matrix-lcd"
          data-line1="${escapeHtml(display.line1)}"
          data-line2="${escapeHtml(display.line2)}"
          data-lit="${display.backlight && display.available ? "1" : "0"}"></canvas>
      </div>
      ${this._compactStatus(model, display)}
      <div class="compact-controls">${this._controls(model, true, !display.available)}</div>
    </div>`;
  }

  _renderPhysical(model, display) {
    if (model === "firstalert") return this._renderFirstAlert(display, false);
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
      <div class="controls-well">${this._controls(model, false, !display.available)}</div>
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
        --vista-keypad-font:"Arial Narrow","Roboto Condensed","Liberation Sans Narrow","Nimbus Sans Narrow",Arial,sans-serif;
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

      .keypad-shell, .keypad-shell *, .compact-shell, .compact-shell *, .firstalert-shell, .firstalert-shell * { box-sizing:border-box; }

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
        background:#82bd37;
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
        font-family:var(--vista-keypad-font);
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
        font-weight:700;
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
        font-family:var(--vista-keypad-font);
        font-size:clamp(9px,3.05cqw,34px);
        font-weight:400;
        line-height:.9;
        transform:none;
      }

      .number-legend {
        font-family:var(--vista-keypad-font);
        font-size:clamp(4px,1.22cqw,13px);
        font-weight:600;
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
        font-family:var(--vista-keypad-font);
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
        font-weight:600;
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
        font-family:var(--vista-keypad-font);
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

      /*
       * Adaptive layout framework. AUTO preserves the physical facsimile when
       * space is available and swaps to a touchscreen-first composition in
       * narrow Lovelace cards. The compact renderer itself is model-agnostic;
       * model-specific annunciators come from MODEL_PROFILES.
       */
      .layout-host {
        width:100%;
        max-width:940px;
      }

      .layout-physical-view,
      .layout-compact-view {
        width:100%;
      }

      .layout-mode-physical .layout-compact-view,
      .layout-mode-compact .layout-physical-view,
      .layout-mode-auto .layout-compact-view {
        display:none;
      }

      .compact-shell {
        --case-red:#d71f26;
        --case-red-hi:#ef3a41;
        --case-red-lo:#b90f17;
        --case-white:#f0f0ed;
        --case-white-lo:#d4d4cf;
        --case-dark:#34373a;
        --case-dark-hi:#4a4e52;
        --case-dark-lo:#202225;

        width:100%;
        min-width:0;
        padding:12px;
        border:1px solid;
        border-radius:18px;
        overflow:hidden;
        user-select:none;
        -webkit-tap-highlight-color:transparent;
        filter:drop-shadow(0 6px 8px rgba(0,0,0,.24));
      }

      .compact-shell.case-red,
      .compact-shell.case-dark {
        color:#f3f4f4;
      }

      .compact-shell.case-white {
        color:#1f2020;
      }

      .compact-lcd-frame {
        width:100%;
        height:clamp(82px,23cqw,108px);
        padding:5px;
        border-radius:8px;
        background:linear-gradient(180deg,#565953,#222520 16%,#0f100f 100%);
        box-shadow:
          inset 0 2px 4px rgba(0,0,0,.88),
          0 1px 1px rgba(255,255,255,.18);
      }

      .compact-lcd-frame .matrix-lcd {
        border-radius:3px;
      }

      .compact-status {
        display:grid;
        grid-template-columns:repeat(auto-fit,minmax(64px,1fr));
        gap:6px;
        margin-top:10px;
      }

      .compact-6160cr2 .compact-status {
        grid-template-columns:repeat(4,minmax(0,1fr));
      }

      .compact-6160 .compact-status {
        grid-template-columns:repeat(2,minmax(0,1fr));
      }

      .compact-indicator.led-row {
        min-width:0;
        min-height:30px;
        display:flex;
        align-items:center;
        justify-content:center;
        gap:6px;
        padding:4px 5px;
        border:1px solid rgba(255,255,255,.16);
        border-radius:7px;
        background:rgba(0,0,0,.12);
        font-size:10px;
        line-height:1;
      }

      .compact-shell.case-white .compact-indicator.led-row {
        border-color:rgba(0,0,0,.14);
        background:rgba(0,0,0,.045);
      }

      .compact-indicator .led {
        flex:0 0 auto;
        width:18px;
        height:8px;
      }

      .compact-indicator-label {
        min-width:0;
        overflow:hidden;
        text-overflow:clip;
        white-space:nowrap;
        font:700 10px/1 var(--vista-keypad-font);
        letter-spacing:.01em;
      }

      .compact-controls {
        width:100%;
        margin-top:10px;
      }

      .compact-shell .key-grid {
        width:100%;
        height:auto;
        display:grid;
        grid-template-columns:repeat(4,minmax(0,1fr));
        grid-template-rows:repeat(4,clamp(50px,14cqw,58px));
        column-gap:8px;
        row-gap:8px;
      }

      .compact-shell .grid-slot {
        width:auto;
        height:auto;
        min-width:0;
        min-height:0;
      }

      .compact-shell .function-slot {
        transform:none;
      }

      .compact-shell .physical-key {
        min-width:0;
        min-height:48px;
        padding:0 4px;
        border-width:1px;
        border-radius:7px;
      }

      .compact-shell .physical-key:active,
      .compact-shell .physical-key.pressed {
        transform:translateY(1px);
      }

      .compact-shell .function-label {
        font-size:clamp(9px,3.0cqw,13px);
        letter-spacing:-.02em;
      }

      .compact-shell .number-key {
        gap:clamp(2px,1.2cqw,6px);
      }

      .compact-shell .number-main {
        font-size:clamp(22px,7.4cqw,32px);
      }

      .compact-shell .number-legend {
        font-size:clamp(7px,2.35cqw,11px);
      }

      @container (max-width:520px) {
        .layout-mode-auto .layout-physical-view { display:none; }
        .layout-mode-auto .layout-compact-view { display:block; }
      }

      @container (max-width:320px) {
        .compact-shell {
          padding:9px;
          border-radius:14px;
        }

        .compact-status {
          gap:4px;
          margin-top:8px;
        }

        .compact-indicator.led-row {
          min-height:27px;
          gap:4px;
          padding:3px;
        }

        .compact-indicator .led {
          width:15px;
          height:7px;
        }

        .compact-indicator-label {
          font-size:9px;
        }

        .compact-controls {
          margin-top:8px;
        }

        .compact-shell .key-grid {
          grid-template-rows:repeat(4,50px);
          column-gap:5px;
          row-gap:5px;
        }

        .compact-shell .number-legend {
          display:none;
        }
      }

      /* First Alert-inspired skin: horizontal when wide, portrait when compact. */
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
        font-family:var(--vista-keypad-font);
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
    const canvases = this.shadowRoot?.querySelectorAll(".matrix-lcd") ?? [];
    canvases.forEach((canvas) => this._drawLCDCanvas(canvas));
  }

  _drawLCDCanvas(canvas) {
    const rect = canvas.getBoundingClientRect();
    if (!rect.width || !rect.height) return;
    const scale = Math.max(1, window.devicePixelRatio || 1);
    canvas.width = Math.max(1, Math.round(rect.width * scale));
    canvas.height = Math.max(1, Math.round(rect.height * scale));

    const ctx = canvas.getContext("2d");
    ctx.scale(scale, scale);

    const w = rect.width;
    const h = rect.height;
    const lit = canvas.dataset.lit === "1";
    const firstAlertLcd = canvas.dataset.lcdStyle === "firstalert";

    const bg = ctx.createLinearGradient(0, 0, 0, h);
    if (firstAlertLcd && lit) {
      bg.addColorStop(0, "#e7eff6");
      bg.addColorStop(.5, "#d7e3ed");
      bg.addColorStop(1, "#c7d5e0");
    } else if (firstAlertLcd) {
      bg.addColorStop(0, "#9ca8b0");
      bg.addColorStop(1, "#808b92");
    } else if (lit) {
      bg.addColorStop(0, "#96ce40");
      bg.addColorStop(.5, "#85be37");
      bg.addColorStop(1, "#73aa30");
    } else {
      bg.addColorStop(0, "#7f9570");
      bg.addColorStop(1, "#687a5e");
    }

    ctx.fillStyle = bg;
    ctx.fillRect(0, 0, w, h);

    ctx.fillStyle = firstAlertLcd
      ? (lit ? "rgba(34,54,70,.035)" : "rgba(30,42,50,.05)")
      : (lit ? "rgba(33,80,23,.055)" : "rgba(25,42,24,.065)");
    const grid = Math.max(2.5, w / 120);
    for (let x = 0; x < w; x += grid) ctx.fillRect(x, 0, 1, h);
    for (let y = 0; y < h; y += grid) ctx.fillRect(0, y, w, 1);

    const lines = [exactLine(canvas.dataset.line1), exactLine(canvas.dataset.line2)];
    const marginX = w * .018;
    const marginY = h * .105;
    const charW = (w - marginX * 2) / 16;
    const lineH = (h - marginY * 2) / 2;
    // The physical alpha display is a 5x7 matrix in a 6x8 character
    // cell. Preserve that pitch and snap to device pixels so small
    // compact cards keep visible separation between LCD elements.
    const dot = Math.min(charW / 6, lineH / 8);
    const gap = dot * .18;
    const px = dot - gap;
    const snap = (value) => Math.round(value * scale) / scale;
    const pixelSize = Math.max(1 / scale, snap(px));

    ctx.fillStyle = firstAlertLcd
      ? (lit ? "#2d3944" : "#29343b")
      : (lit ? "#102512" : "#253126");

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
                snap(baseX + gx * dot),
                snap(baseY + gy * dot),
                pixelSize,
                pixelSize
              );
            }
          }
        }
      });
    });

    const glare = ctx.createLinearGradient(0, 0, w, h);
    glare.addColorStop(0, "rgba(255,255,255,.055)");
    glare.addColorStop(.32, "rgba(255,255,255,.015)");
    glare.addColorStop(1, "rgba(255,255,255,0)");
    ctx.fillStyle = glare;
    ctx.fillRect(0, 0, w, h * .42);
  }

  _observeResize() {
    const shell = this.shadowRoot?.querySelector(".layout-host");
    if (!shell || typeof ResizeObserver === "undefined") return;

    this._resizeObserver ??= new ResizeObserver(() => {
      if (this._resizeFrame) cancelAnimationFrame(this._resizeFrame);
      this._resizeFrame = requestAnimationFrame(() => {
        this._resizeFrame = 0;
        this._drawLCD();
      });
    });
    this._resizeObserver.disconnect();
    this._resizeObserver.observe(shell);
  }

  _render() {
    if (!this.shadowRoot || !this._config) return;

    const display = this._displayState();
    const layoutClass = `layout-mode-${this._config.layout ?? "auto"}`;
    const controlNote = display.available
      ? "Keypad control is not enabled."
      : "Panel state is unavailable; keypad controls are disabled.";
    const keypadControlEnabled = this._config.read_only === false
      && display.available
      && display.controlEnabled
      && Boolean(display.commandTopic);
    this.shadowRoot.innerHTML = `<style>${this._styles()}</style><ha-card><div class="wrap">
      ${this._config.title ? `<div class="card-title">${escapeHtml(this._config.title)}</div>` : ""}
      <div class="layout-host ${layoutClass}">
        ${this._config.sound?.enabled ? `<button id="audio-lock-flag" class="audio-lock-flag" type="button" aria-label="Keypad audio is locked. Tap to enable audio." ${this._audioUnlocked() ? "hidden" : ""}>AUDIO</button>` : ""}
        <div class="layout-physical-view">${this._renderPhysical(this._config.model, display)}</div>
        <div class="layout-compact-view">${this._renderCompact(this._config.model, display)}</div>
      </div>
      <div class="read-only-note" id="read-only-note">${escapeHtml(controlNote)}</div>
    </div></ha-card>`;

    requestAnimationFrame(() => {
      this._drawLCD();
      this._observeResize();
      this._updateAudioFlag();
    });

    const audioFlag = this.shadowRoot.getElementById("audio-lock-flag");
    audioFlag?.addEventListener("click", async (event) => {
      event.stopPropagation();
      await this._audio.unlock().catch(() => false);
      this._syncAudioUnlockListener();
      this._updateAudioFlag();
    });

    this.shadowRoot.querySelectorAll("button[data-key]").forEach((button) => {
      const release = () => button.classList.remove("pressed");
      button.addEventListener("pointerdown", () => {
        button.classList.add("pressed");
        this._keyPressFeedback();
      });
      button.addEventListener("pointerup", release);
      button.addEventListener("pointerleave", release);
      button.addEventListener("pointercancel", release);
      button.addEventListener("lostpointercapture", release);
      button.addEventListener("click", (event) => this._handleKey(event.currentTarget));
    });
  }

  _showControlNote(message) {
    const note = this.shadowRoot?.getElementById("read-only-note");
    if (!note) return;
    note.textContent = message;
    note.classList.add("show");
    clearTimeout(this._pressTimer);
    this._pressTimer = setTimeout(() => note.classList.remove("show"), 1600);
  }

  _handleKey(button) {
    const key = button?.dataset?.key;
    if (!key) return;

    if (this._config.read_only !== false) {
      this._showControlNote("Enable keypad input in the card editor first.");
      return;
    }

    if (![..."0123456789", "*", "#"].includes(key)) {
      this._showControlNote("A-D function keys are not mapped yet.");
      return;
    }

    const display = this._displayState();
    if (!display.available) {
      this._showControlNote("Panel is offline.");
      return;
    }
    if (!display.controlEnabled || !display.commandTopic) {
      this._showControlNote("Bridge keypad control is disabled or unavailable.");
      return;
    }
    if (!this._hass?.callService) {
      this._showControlNote("Home Assistant MQTT publish action is unavailable.");
      return;
    }

    const makeInteractionId = () => typeof globalThis.crypto?.randomUUID === "function"
      ? globalThis.crypto.randomUUID()
      : `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`;
    const transactionId = makeInteractionId();
    if (!this._auditInteractionId) this._auditInteractionId = makeInteractionId();
    const auditInteractionId = this._auditInteractionId;
    clearTimeout(this._auditInteractionTimer);
    this._auditInteractionTimer = setTimeout(() => {
      if (this._auditInteractionId === auditInteractionId) this._auditInteractionId = null;
    }, KEYPAD_AUDIT_IDLE_MS);
    const partition = Number(String(display.commandTopic).match(/\/keypad\/([1-8])\/command$/)?.[1] ?? 0);
    const actorId = typeof this._hass?.user?.id === "string" ? this._hass.user.id.slice(0, 128) : "";
    const actorName = typeof (this._hass?.user?.name ?? this._hass?.user?.display_name) === "string"
      ? (this._hass.user.name ?? this._hass.user.display_name).slice(0, 128)
      : "";
    const lifecycleGeneration = this._lifecycleGeneration;

    // A virtual keypad press is delivered when the user presses the key, just
    // like a physical VISTA keypad. The promise chain preserves press order in
    // this card instance; bridge-side serialization remains responsible for
    // coordinating panel traffic. There is deliberately no browser-side
    // command composer or synthetic SEND/finish boundary.
    this._keyPressSend = this._keyPressSend.then(async () => {
      if (lifecycleGeneration !== this._lifecycleGeneration) return;
      const currentDisplay = this._displayState();
      if (!currentDisplay.available || !currentDisplay.controlEnabled || !currentDisplay.commandTopic) {
        this._showControlNote("Panel state is unavailable; keypad key was not sent.");
        return;
      }
      try {
        await this._hass.callService("mqtt", "publish", {
          topic: currentDisplay.commandTopic,
          payload: JSON.stringify({
            keys: key,
            transaction_id: transactionId,
            audit_interaction_id: auditInteractionId,
            partition,
            source: "ha_frontend",
            actor_id: actorId,
            actor_name: actorName,
            action: "keypad_sequence",
            complete: true,
          }),
          qos: 1,
          retain: false,
        });
        if (lifecycleGeneration !== this._lifecycleGeneration) return;
      } catch (_) {
        this._showControlNote("Keypad key could not be published.");
        return;
      }

      this.dispatchEvent(new CustomEvent("vista-keypad-key", {
        bubbles: true,
        composed: true,
        detail: {
          action: "keypress",
          entity: this._config.entity,
          model: this._config.model,
        },
      }));
    }).catch(() => {
      this._showControlNote("Keypad key could not be published.");
    });
  }

}


class VistaEventLogCardEditor extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._config = {};
    this._hass = null;
    this._rendered = false;
    this._hasHass = false;
  }

  set hass(hass) {
    const shouldRender = !this._rendered || !this._hasHass;
    this._hass = hass;
    this._hasHass = true;
    if (shouldRender) this._render();
  }

  setConfig(config) {
    const next = { ...(config ?? {}) };
    const changed = JSON.stringify(next) !== JSON.stringify(this._config);
    this._config = next;
    if (!this._rendered || changed) this._render();
  }

  _emit(name, value) {
    const next = { ...this._config, [name]: value };
    if ((name === "title" || name === "partition") && (value === "" || value === 0)) {
      if (name === "title") delete next.title;
      if (name === "partition") next.partition = 0;
    }
    this._config = next;
    this.dispatchEvent(new CustomEvent("config-changed", {
      detail: { config: next },
      bubbles: true,
      composed: true,
    }));
  }

  _render() {
    if (!this.shadowRoot) return;
    const entityOptions = editorEntityOptions(this._hass, this._config.entity, ["sensor"]);
    const rows = Math.max(1, Math.min(100, Number(this._config.rows ?? 20) || 20));
    const partition = Math.max(0, Math.min(8, Number(this._config.partition ?? 0) || 0));
    const checked = (value) => value ? "checked" : "";

    this.shadowRoot.innerHTML = `<style>
      :host{display:block;color:var(--primary-text-color);font-family:system-ui,sans-serif}
      *{box-sizing:border-box}.editor{display:grid;gap:12px}.field{display:grid;gap:5px}.grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}
      label,.label{font-size:12px;color:var(--secondary-text-color)}input,select{width:100%;min-height:40px;padding:7px 9px;border:1px solid var(--divider-color,#aaa);border-radius:7px;background:var(--card-background-color,#fff);color:var(--primary-text-color,#111);font:inherit}.toggle{display:flex;align-items:center;justify-content:space-between;gap:10px;min-height:36px}.toggle input{width:20px;height:20px}@media(max-width:520px){.grid{grid-template-columns:1fr}}
    </style><div class="editor">
      <div class="field"><label for="event-entity">Event journal entity</label><input id="event-entity" data-field="entity" type="search" list="event-entity-list" autocomplete="off" value="${escapeHtml(this._config.entity ?? "")}" placeholder="Search sensor entities"><datalist id="event-entity-list">${entityOptions}</datalist></div>
      <div class="field"><label>Title</label><input data-field="title" value="${escapeHtml(this._config.title ?? "")}" placeholder="VISTA Event Journal"></div>
      <div class="grid">
        <div class="field"><label>Rows</label><input data-field="rows" data-number="1" type="number" min="1" max="100" value="${rows}"></div>
        <div class="field"><label>Partition filter</label><select data-field="partition">${[0,1,2,3,4,5,6,7,8].map((value) => `<option value="${value}" ${value === partition ? "selected" : ""}>${value === 0 ? "All partitions" : `Partition ${value}`}</option>`).join("")}</select></div>
        <div class="toggle"><span class="label">Show source</span><input data-field="show_source" type="checkbox" ${checked(this._config.show_source !== false)}></div>
        <div class="toggle"><span class="label">Show user</span><input data-field="show_user" type="checkbox" ${checked(this._config.show_user !== false)}></div>
      </div>
    </div>`;

    this.shadowRoot.querySelectorAll("[data-field]").forEach((el) => {
      el.addEventListener("change", () => {
        let value;
        if (el.type === "checkbox") value = el.checked;
        else if (el.dataset.number) value = Number(el.value);
        else if (el.dataset.field === "partition") value = Number(el.value);
        else value = el.value;
        this._emit(el.dataset.field, value);
      });
    });
    this._rendered = true;
  }
}

class VistaEventLogCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._config = null;
    this._hass = null;
    this._signature = null;
  }

  static getStubConfig() {
    return {
      entity: "sensor.event_journal",
      rows: 20,
      partition: 0,
      show_source: true,
      show_user: true,
    };
  }

  static getConfigElement() {
    return document.createElement("vista-event-log-card-editor");
  }

  setConfig(config) {
    if (!config?.entity) throw new Error("vista-event-log-card requires an entity");
    this._config = {
      title: "VISTA Event Journal",
      rows: 20,
      partition: 0,
      show_source: true,
      show_user: true,
      ...config,
      rows: Math.max(1, Math.min(100, Number(config.rows ?? 20) || 20)),
      partition: Math.max(0, Math.min(8, Number(config.partition ?? 0) || 0)),
    };
    this._signature = null;
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    const state = this._config?.entity ? hass?.states?.[this._config.entity] : null;
    const attrs = state?.attributes ?? {};
    const signature = JSON.stringify([
      state?.state ?? null,
      attrs.count ?? null,
      attrs.last_dump_at ?? null,
      attrs.last_dump_seen ?? null,
      attrs.last_dump_inserted ?? null,
      attrs.events ?? null,
      this._config,
    ]);
    if (signature === this._signature) return;
    this._signature = signature;
    this._render();
  }

  getCardSize() {
    return Math.max(3, Math.ceil((this._config?.rows ?? 20) / 4));
  }

  getGridOptions() {
    return { columns: 12, min_columns: 4, max_columns: 12 };
  }

  _formatPanelTimestamp(value) {
    const text = String(value ?? "");
    const match = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})/.exec(text);
    if (!match) return text || "—";
    return `${match[2]}/${match[3]} ${match[4]}:${match[5]}`;
  }

  _eventMeta(event) {
    const pieces = [];
    const partition = Number(event.partition ?? 0);
    const zone = Number(event.zone ?? 0);
    const user = Number(event.user ?? 0);
    if (partition) pieces.push(`P${partition}`);
    if (zone) pieces.push(`Z${String(zone).padStart(3, "0")}`);
    if (this._config.show_user !== false && user) pieces.push(`U${String(user).padStart(3, "0")}`);
    return pieces.join(" · ");
  }

  _render() {
    if (!this.shadowRoot || !this._config) return;
    const state = this._hass?.states?.[this._config.entity] ?? null;
    const attrs = state?.attributes ?? {};
    const available = state && !["unknown", "unavailable"].includes(state.state);
    const allEvents = Array.isArray(attrs.events) ? attrs.events : [];
    const filtered = allEvents
      .filter((event) => !this._config.partition || Number(event.partition) === this._config.partition)
      .slice(0, this._config.rows);
    const count = Number(attrs.count ?? state?.state ?? 0) || 0;
    const dumpAt = attrs.last_dump_at ? this._formatPanelTimestamp(attrs.last_dump_at) : "not yet";
    const dumpSeen = Number(attrs.last_dump_seen ?? 0) || 0;
    const dumpInserted = Number(attrs.last_dump_inserted ?? 0) || 0;

    const rows = filtered.map((event) => {
      const descriptor = String(event.descriptor ?? "").trim();
      const description = String(event.description ?? `Event ${event.event_code ?? ""}`).trim();
      const meta = this._eventMeta(event);
      const source = String(event.source ?? "").toUpperCase();
      return `<div class="event-row">
        <div class="time">${escapeHtml(this._formatPanelTimestamp(event.panel_timestamp ?? event.received_at))}</div>
        <div class="code">${escapeHtml(event.event_code ?? "??")}</div>
        <div class="detail">
          <div class="description">${escapeHtml(description)}${descriptor ? ` <span class="descriptor">${escapeHtml(descriptor)}</span>` : ""}</div>
          ${meta ? `<div class="meta">${escapeHtml(meta)}</div>` : ""}
        </div>
        ${this._config.show_source !== false ? `<div class="source source-${escapeHtml(String(event.source ?? "unknown"))}">${escapeHtml(source || "UNKNOWN")}</div>` : ""}
      </div>`;
    }).join("");

    this.shadowRoot.innerHTML = `<style>
      :host{display:block}*{box-sizing:border-box}ha-card{overflow:hidden}.wrap{padding:14px}.header{display:flex;align-items:flex-start;justify-content:space-between;gap:12px;margin-bottom:10px}.title{font:600 16px/1.25 sans-serif;color:var(--primary-text-color)}.summary{margin-top:3px;font:12px/1.35 sans-serif;color:var(--secondary-text-color)}.dump{text-align:right;font:11px/1.35 ui-monospace,SFMono-Regular,Menlo,monospace;color:var(--secondary-text-color);white-space:nowrap}.events{display:grid;border-top:1px solid var(--divider-color)}.event-row{display:grid;grid-template-columns:86px 38px minmax(0,1fr) auto;gap:8px;align-items:center;min-width:0;padding:8px 0;border-bottom:1px solid var(--divider-color);font-family:system-ui,sans-serif}.time{font:11px/1.2 ui-monospace,SFMono-Regular,Menlo,monospace;color:var(--secondary-text-color);white-space:nowrap}.code{font:700 11px/1 ui-monospace,SFMono-Regular,Menlo,monospace;color:var(--primary-text-color)}.detail{min-width:0}.description{font-size:13px;line-height:1.25;color:var(--primary-text-color);overflow-wrap:anywhere}.descriptor{font-weight:600}.meta{margin-top:2px;font:10px/1.2 ui-monospace,SFMono-Regular,Menlo,monospace;color:var(--secondary-text-color)}.source{padding:3px 5px;border:1px solid var(--divider-color);border-radius:999px;font:700 8px/1 sans-serif;letter-spacing:.04em;color:var(--secondary-text-color);white-space:nowrap}.source-live{color:var(--primary-color)}.empty{padding:20px 0;text-align:center;color:var(--secondary-text-color);font:13px/1.4 sans-serif}.offline{padding:8px 10px;margin-bottom:10px;border-radius:7px;background:var(--secondary-background-color);color:var(--secondary-text-color);font-size:12px}@container (max-width:520px){.wrap{padding:12px}.header{display:block}.dump{text-align:left;margin-top:5px}.event-row{grid-template-columns:70px 32px minmax(0,1fr);gap:6px}.source{grid-column:3;justify-self:start;margin-top:-3px}.time{font-size:10px}.description{font-size:12px}}@container (max-width:360px){.event-row{grid-template-columns:1fr auto}.time{grid-column:1}.code{grid-column:2;grid-row:1}.detail{grid-column:1/-1}.source{grid-column:1/-1}.meta{font-size:9px}}
      .wrap{container-type:inline-size}
    </style><ha-card><div class="wrap">
      <div class="header"><div><div class="title">${escapeHtml(this._config.title)}</div><div class="summary">${count} events${this._config.partition ? ` · partition ${this._config.partition}` : ""}</div></div><div class="dump">dump ${escapeHtml(dumpAt)}<br>${dumpSeen} seen / ${dumpInserted} new</div></div>
      ${available ? "" : `<div class="offline">Event journal entity unavailable.</div>`}
      <div class="events">${rows || `<div class="empty">No journal events in the current window.</div>`}</div>
    </div></ha-card>`;
  }
}

if (!customElements.get("vista-event-log-card-editor")) {
  customElements.define("vista-event-log-card-editor", VistaEventLogCardEditor);
}

if (!customElements.get("vista-event-log-card")) {
  customElements.define("vista-event-log-card", VistaEventLogCard);
}

if (!customElements.get("vista-keypad-card-editor")) {
  customElements.define("vista-keypad-card-editor", VistaKeypadCardEditor);
}

if (!customElements.get("vista-keypad-card")) {
  customElements.define("vista-keypad-card", VistaKeypadCard);
}

window.customCards = window.customCards || [];
window.customCards.push({
  type: "vista-keypad-card",
  name: "Vista Keypad",
  description: "Adaptive VISTA keypad card with 6160CR-2, 6160, and First Alert-inspired skins.",
  preview: false,
  documentationURL: "https://github.com/wtc-brycel/vistaturbo-hass/tree/main/frontend",
});
window.customCards.push({
  type: "vista-event-log-card",
  name: "VISTA Event Journal",
  description: "Responsive recent-event view backed by the Vista Turbo RS232 SQLite journal.",
  preview: false,
  documentationURL: "https://github.com/wtc-brycel/vistaturbo-hass/tree/main/frontend",
});

console.info(
  `%c VISTA-KEYPAD-CARD %c v${VISTA_KEYPAD_CARD_VERSION} `,
  "color:#fff;background:#b40f18;font-weight:700",
  "color:#111;background:#e6e6e2"
);
