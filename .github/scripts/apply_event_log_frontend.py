from pathlib import Path


def replace_once(path: str, old: str, new: str, label: str) -> None:
    p = Path(path)
    text = p.read_text()
    if old not in text:
        raise SystemExit(f"missing anchor {label} in {path}")
    p.write_text(text.replace(old, new, 1))


path = "frontend/vista-keypad-card.js"
p = Path(path)
s = p.read_text()
s = s.replace('const VISTA_KEYPAD_CARD_VERSION = "0.3.18";', 'const VISTA_KEYPAD_CARD_VERSION = "0.3.19";', 1)

code = r'''
class VistaEventLogCardEditor extends HTMLElement {
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
    this._config = { ...(config ?? {}) };
    this._render();
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
    this._render();
  }

  _render() {
    if (!this.shadowRoot) return;
    const sensorIds = Object.keys(this._hass?.states ?? {})
      .filter((entityId) => entityId.startsWith("sensor."))
      .sort();
    const options = sensorIds.map((entityId) => `<option value="${escapeHtml(entityId)}"></option>`).join("");
    const rows = Math.max(1, Math.min(100, Number(this._config.rows ?? 20) || 20));
    const partition = Math.max(0, Math.min(8, Number(this._config.partition ?? 0) || 0));
    const checked = (value) => value ? "checked" : "";

    this.shadowRoot.innerHTML = `<style>
      :host{display:block;color:var(--primary-text-color);font-family:system-ui,sans-serif}
      *{box-sizing:border-box}.editor{display:grid;gap:12px}.field{display:grid;gap:5px}.grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}
      label,.label{font-size:12px;color:var(--secondary-text-color)}input,select{width:100%;min-height:40px;padding:7px 9px;border:1px solid var(--divider-color,#aaa);border-radius:7px;background:var(--card-background-color,#fff);color:var(--primary-text-color,#111);font:inherit}.toggle{display:flex;align-items:center;justify-content:space-between;gap:10px;min-height:36px}.toggle input{width:20px;height:20px}@media(max-width:520px){.grid{grid-template-columns:1fr}}
    </style><div class="editor">
      <div class="field"><label>Event journal entity</label><input data-field="entity" list="event-journal-entities" value="${escapeHtml(this._config.entity ?? "")}" placeholder="sensor.vista_128bpt_event_journal"><datalist id="event-journal-entities">${options}</datalist></div>
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
      entity: "sensor.vista_128bpt_event_journal",
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
'''

anchor = 'if (!customElements.get("vista-keypad-card-editor")) {'
if anchor not in s:
    raise SystemExit("missing custom element registration anchor")
s = s.replace(anchor, code + "\n" + anchor, 1)

registration = '''if (!customElements.get("vista-event-log-card-editor")) {
  customElements.define("vista-event-log-card-editor", VistaEventLogCardEditor);
}

if (!customElements.get("vista-event-log-card")) {
  customElements.define("vista-event-log-card", VistaEventLogCard);
}

'''
s = s.replace('if (!customElements.get("vista-keypad-card-editor")) {', registration + 'if (!customElements.get("vista-keypad-card-editor")) {', 1)

anchor = '''window.customCards.push({
  type: "vista-keypad-card",
  name: "Vista Keypad",
  description: "Adaptive VISTA keypad card with 6160CR-2, 6160, and First Alert-inspired skins.",
  preview: false,
  documentationURL: "https://github.com/wtc-brycel/vistaturbo-hass/tree/main/frontend",
});
'''
if anchor not in s:
    raise SystemExit("missing customCards anchor")
s = s.replace(anchor, anchor + '''window.customCards.push({
  type: "vista-event-log-card",
  name: "VISTA Event Journal",
  description: "Responsive recent-event view backed by the Vista Turbo RS232 SQLite journal.",
  preview: false,
  documentationURL: "https://github.com/wtc-brycel/vistaturbo-hass/tree/main/frontend",
});
''', 1)

p.write_text(s)

# README
path = "frontend/README.md"
p = Path(path)
s = p.read_text()
section = r'''

## Event journal card

Card `0.3.19` also registers `custom:vista-event-log-card`. It renders the recent window exposed by the App's persistent SQLite event journal while the complete journal remains in `/data/vista128_events.sqlite3`.

```yaml
type: custom:vista-event-log-card
entity: sensor.vista_128bpt_event_journal
rows: 20
partition: 0
```

`partition: 0` shows all partitions; values 1 through 8 filter the displayed recent window. The card shows panel time, event code, description, programmed zone descriptor, partition/zone/user metadata, and whether the row came from the live event stream, the historical panel dump, or both. A visual editor is included.

The App intentionally publishes only a small configurable recent window to Home Assistant. The full historical journal is not repeated in sensor attributes, which avoids bloating Home Assistant Recorder as the panel history grows.
'''
if "## Event journal card" not in s:
    s += section
p.write_text(s)
