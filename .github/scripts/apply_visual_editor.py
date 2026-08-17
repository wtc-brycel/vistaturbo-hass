from pathlib import Path


def replace_once(path: str, old: str, new: str, label: str) -> None:
    p = Path(path)
    text = p.read_text()
    if old not in text:
        raise SystemExit(f"missing anchor: {label}")
    p.write_text(text.replace(old, new, 1))


CARD = "frontend/vista-keypad-card.js"
p = Path(CARD)
s = p.read_text()
s = s.replace('const VISTA_KEYPAD_CARD_VERSION = "0.3.17";', 'const VISTA_KEYPAD_CARD_VERSION = "0.3.18";', 1)

editor_code = r'''
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
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  setConfig(config) {
    this._config = cloneEditorConfig(config ?? {});
    this._render();
  }

  _emit(config) {
    this._config = cloneEditorConfig(config);
    this.dispatchEvent(new CustomEvent("config-changed", {
      detail: { config: this._config },
      bubbles: true,
      composed: true,
    }));
    this._render();
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
    const caseColor = String(this._config.case_color ?? "auto").toLowerCase();
    const soundInput = this._config.sound && typeof this._config.sound === "object" ? this._config.sound : {};
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
    const hapticInput = this._config.haptic && typeof this._config.haptic === "object" ? this._config.haptic : {};
    const haptic = { enabled: false, keypress_ms: 10, ...hapticInput };
    const defaultFunctions = MODEL_PROFILES[model]?.compactFunctionKeys ?? DEFAULT_FUNCTION_KEYS[model] ?? ["A", "B", "C", "D"];
    const sensorIds = Object.keys(this._hass?.states ?? {}).filter((entityId) => entityId.startsWith("sensor.")).sort();
    const entityOptions = sensorIds.map((entityId) => `<option value="${escapeHtml(entityId)}"></option>`).join("");
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
      input[type=text],input[type=number],select{width:100%;min-height:40px;padding:7px 9px;border:1px solid var(--divider-color,#aaa);border-radius:7px;background:var(--card-background-color,#fff);color:var(--primary-text-color,#111);font:inherit}
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
          <div class="field full"><label for="entity">Keypad entity</label><input id="entity" data-top="entity" type="text" list="keypad-entities" value="${escapeHtml(this._config.entity ?? "")}" placeholder="sensor.vista_partition_1_keypad"><datalist id="keypad-entities">${entityOptions}</datalist></div>
          <div class="field"><label for="model">Style</label><select id="model" data-top="model">${this._option("6160cr2", "6160CR-2", model)}${this._option("6160", "6160", model)}${this._option("firstalert", "First Alert", model)}</select></div>
          <div class="field"><label for="layout">Layout</label><select id="layout" data-top="layout">${this._option("auto", "Auto", layout)}${this._option("physical", "Physical", layout)}${this._option("compact", "Compact", layout)}</select></div>
          <div class="field full"><label for="title">Title</label><input id="title" data-top="title" type="text" value="${escapeHtml(this._config.title ?? "")}" placeholder="Optional"></div>
          <div class="toggle field full"><span><span class="label">Card background</span></span><input data-top="show_card_background" type="checkbox" ${checked(Boolean(this._config.show_card_background))}></div>
        </div>
        <div class="readonly">Monitoring remains read-only. The editor does not expose a panel-control toggle.</div>
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
          <div class="field"><label>Burglary entity override</label><input data-sound="alarm_entity" type="text" value="${escapeHtml(sound.alarm_entity ?? "")}" placeholder="Optional"></div>
          <div class="field"><label>Auxiliary entity override</label><input data-sound="aux_entity" type="text" value="${escapeHtml(sound.aux_entity ?? "")}" placeholder="Optional"></div>
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
  }
}
'''

anchor = 'class VistaKeypadCard extends HTMLElement {'
if anchor not in s:
    raise SystemExit("missing anchor: card class")
s = s.replace(anchor, editor_code + "\n" + anchor, 1)

anchor = '''  static getStubConfig() {
'''
replacement = '''  static async getConfigElement() {
    return document.createElement("vista-keypad-card-editor");
  }

  static getStubConfig() {
'''
if anchor not in s:
    raise SystemExit("missing anchor: getStubConfig")
s = s.replace(anchor, replacement, 1)

anchor = '''if (!customElements.get("vista-keypad-card")) {
  customElements.define("vista-keypad-card", VistaKeypadCard);
}
'''
replacement = '''if (!customElements.get("vista-keypad-card-editor")) {
  customElements.define("vista-keypad-card-editor", VistaKeypadCardEditor);
}

if (!customElements.get("vista-keypad-card")) {
  customElements.define("vista-keypad-card", VistaKeypadCard);
}
'''
if anchor not in s:
    raise SystemExit("missing anchor: custom element registration")
s = s.replace(anchor, replacement, 1)
p.write_text(s)

# Browser regression coverage for Home Assistant visual editor contract.
p = Path("frontend/tests/render.spec.mjs")
s = p.read_text()
extra = r'''

test("custom card exposes a Home Assistant visual editor", async ({ page }) => {
  await page.setContent(`<!doctype html><html><body></body></html>`);
  await page.evaluate(() => {
    if (!customElements.get("ha-card")) customElements.define("ha-card", class extends HTMLElement {});
  });
  await page.addScriptTag({ content: cardSource });

  const result = await page.evaluate(async ({ entity }) => {
    const ctor = customElements.get("vista-keypad-card");
    const editor = await ctor.getConfigElement();
    document.body.append(editor);
    editor.hass = {
      states: {
        [entity]: { state: "ready", attributes: { friendly_name: "Partition 1 Keypad" } },
      },
    };
    editor.setConfig({
      type: "custom:vista-keypad-card",
      entity,
      model: "firstalert",
      layout: "auto",
      case_color: "auto",
      sound: { enabled: true, state_sounds: true },
      haptic: { enabled: true, keypress_ms: 10 },
    });
    return {
      tag: editor.tagName.toLowerCase(),
      model: editor.shadowRoot.querySelector("[data-top=model]").value,
      layout: editor.shadowRoot.querySelector("[data-top=layout]").value,
      sound: editor.shadowRoot.querySelector("[data-sound=enabled]").checked,
      haptic: editor.shadowRoot.querySelector("[data-haptic=enabled]").checked,
      entity: editor.shadowRoot.querySelector("[data-top=entity]").value,
    };
  }, { entity: ENTITY });

  expect(result).toEqual({
    tag: "vista-keypad-card-editor",
    model: "firstalert",
    layout: "auto",
    sound: true,
    haptic: true,
    entity: ENTITY,
  });
});

test("visual editor emits clean nested config changes", async ({ page }) => {
  await page.setContent(`<!doctype html><html><body></body></html>`);
  await page.evaluate(() => {
    if (!customElements.get("ha-card")) customElements.define("ha-card", class extends HTMLElement {});
  });
  await page.addScriptTag({ content: cardSource });

  const changes = await page.evaluate(async ({ entity }) => {
    const ctor = customElements.get("vista-keypad-card");
    const editor = await ctor.getConfigElement();
    document.body.append(editor);
    editor.setConfig({ type: "custom:vista-keypad-card", entity, model: "6160cr2" });
    const emitted = [];
    editor.addEventListener("config-changed", (event) => emitted.push(JSON.parse(JSON.stringify(event.detail.config))));

    const model = editor.shadowRoot.querySelector("[data-top=model]");
    model.value = "firstalert";
    model.dispatchEvent(new Event("change", { bubbles: true }));

    const sound = editor.shadowRoot.querySelector("[data-sound=enabled]");
    sound.checked = true;
    sound.dispatchEvent(new Event("change", { bubbles: true }));

    const stateSounds = editor.shadowRoot.querySelector("[data-sound=state_sounds]");
    stateSounds.checked = true;
    stateSounds.dispatchEvent(new Event("change", { bubbles: true }));

    const haptic = editor.shadowRoot.querySelector("[data-haptic=enabled]");
    haptic.checked = true;
    haptic.dispatchEvent(new Event("change", { bubbles: true }));

    const functionA = editor.shadowRoot.querySelector("[data-function=a]");
    functionA.value = "PANIC";
    functionA.dispatchEvent(new Event("change", { bubbles: true }));

    return emitted;
  }, { entity: ENTITY });

  const last = changes.at(-1);
  expect(last.model).toBe("firstalert");
  expect(last.sound.enabled).toBe(true);
  expect(last.sound.state_sounds).toBe(true);
  expect(last.haptic.enabled).toBe(true);
  expect(last.function_keys.a).toBe("PANIC");
  expect(last.entity).toBe(ENTITY);
});
'''
s += extra
p.write_text(s)

# Documentation: change current card version and add visual editor section.
p = Path("frontend/README.md")
s = p.read_text()
s = s.replace('Release `v0.2.6-rc.4` attaches card `0.3.17` as `vista-keypad-card.js`.', 'The current development card is `0.3.18`; the most recent published release may lag until the next RC is cut.', 1) if 'Release `v0.2.6-rc.4` attaches card `0.3.17` as `vista-keypad-card.js`.' in s else s
s = s.replace('/local/vista-keypad-card.js?v=0.3.17', '/local/vista-keypad-card.js?v=0.3.18')
visual_section = r'''

## Visual editor

Card `0.3.18` implements Home Assistant's custom-card visual editor contract through `getConfigElement()`. The dashboard editor can configure the normal installation without hand-editing YAML:

- keypad entity
- 6160CR-2, 6160, or First Alert style
- AUTO, physical, or compact layout
- case color plus optional day/night overrides
- title and Home Assistant card background
- sound enablement, key chirp, panel-state sounds, chime/trouble/supervisory toggles, and volume levels
- optional burglary/AUX Home Assistant entity overrides
- haptic enablement and keypress duration
- A/B/C/D function-key labels

The visual editor intentionally keeps the bridge read-only. Advanced indicator/flashing entity mappings and per-function-key colors remain YAML-only.
'''
marker = '\n## Adaptive layout\n'
if marker not in s:
    raise SystemExit("missing anchor: frontend README adaptive layout")
s = s.replace(marker, visual_section + marker, 1)
p.write_text(s)
