(() => {
  const esc = (v) => String(v ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");

  const template = document.createElement("template");
  template.innerHTML = `<style>${window.VISTA_MANAGEMENT_STYLES || ""}
    .partition-app{overflow:hidden}.partition-layout{display:grid;grid-template-columns:minmax(210px,280px) minmax(0,1fr);min-height:560px}.partition-browser{border-right:1px solid var(--vt-divider);min-width:0}.partition-select{width:100%;border:0;border-bottom:1px solid var(--vt-divider);background:transparent;display:grid;grid-template-columns:42px minmax(0,1fr);gap:8px;padding:11px 12px;text-align:left;cursor:pointer;color:inherit}.partition-select:hover{background:var(--vt-hover)}.partition-select.selected{background:var(--vt-selected)}.partition-select-number{font-weight:700;color:var(--vt-secondary)}.partition-select-main{min-width:0}.partition-select-main strong,.partition-select-main small{display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.partition-select-main strong{font-weight:500}.partition-select-main small{color:var(--vt-secondary);margin-top:2px}.partition-detail{min-width:0}.partition-detail-head{padding:14px 16px;border-bottom:1px solid var(--vt-divider);background:color-mix(in srgb,var(--vt-card) 97%,var(--vt-text))}.partition-detail-head h2{margin:0;font-size:18px;font-weight:500}.partition-detail-head span{display:block;color:var(--vt-secondary);font-size:12px;margin-top:2px}.partition-status{border-bottom:1px solid var(--vt-divider)}.partition-kv{display:grid;grid-template-columns:repeat(auto-fit,minmax(88px,1fr));gap:0;margin:0;padding:8px 12px}.partition-kv div{padding:6px}.partition-kv span{display:block;color:var(--vt-secondary);font-size:11px}.partition-kv strong{display:block;margin-top:2px;font-weight:600;overflow-wrap:anywhere}.detail-tabs{display:flex;align-items:center;min-height:48px;padding:0 10px;border-bottom:1px solid var(--vt-divider);background:var(--vt-card)}.detail-tab{position:relative;min-height:48px;padding:0 14px;border:0;background:transparent;color:var(--vt-secondary);font:inherit;font-weight:500;cursor:pointer}.detail-tab:hover{background:var(--vt-hover);color:var(--vt-text)}.detail-tab[aria-selected="true"]{color:var(--vt-primary)}.detail-tab[aria-selected="true"]::after{content:"";position:absolute;left:10px;right:10px;bottom:0;height:3px;border-radius:3px 3px 0 0;background:var(--vt-primary)}.detail-tab:focus-visible{outline:2px solid var(--vt-primary);outline-offset:-3px}.detail-view[hidden]{display:none}.table-toolbar,.log-toolbar{display:flex;gap:8px;align-items:end;padding:10px 12px;flex-wrap:wrap}.compact-field{display:grid;gap:3px;color:var(--vt-secondary);font-size:11px}.compact-field select{height:40px;min-width:130px;border:0;border-radius:8px;background:var(--vt-form);color:var(--vt-text);padding:0 10px}.table-scroll{overflow:auto;border-top:1px solid var(--vt-divider)}.data-table{width:100%;border-collapse:collapse;font-size:13px}.data-table th{position:sticky;top:0;background:var(--vt-card);z-index:1;text-align:left;color:var(--vt-secondary);font-weight:500;border-bottom:1px solid var(--vt-divider);white-space:nowrap}.data-table th,.data-table td{padding:9px 10px;border-bottom:1px solid var(--vt-divider)}.data-table th button{border:0;background:transparent;color:inherit;padding:0;cursor:pointer;font-weight:inherit}.data-table tbody tr:hover{background:var(--vt-hover)}.data-table tbody tr.abnormal{background:color-mix(in srgb,var(--vt-warning) 5%,transparent)}.mono{font-variant-numeric:tabular-nums;font-family:var(--code-font-family,ui-monospace,SFMono-Regular,Consolas,monospace)}.condition{color:var(--vt-secondary)}.condition.on{color:var(--vt-warning);font-weight:600}.keypad-detail{padding:16px;display:grid;gap:16px}.keypad-preview{border:1px solid var(--vt-divider);border-radius:12px;overflow:hidden;background:var(--vt-card)}.keypad-preview-head{display:flex;align-items:center;gap:10px;padding:10px 12px;border-bottom:1px solid var(--vt-divider);background:var(--vt-surface-header,var(--vt-card))}.keypad-preview-head strong{font-weight:500}.keypad-preview-head span{margin-left:auto;color:var(--vt-secondary);font-size:12px}.lcd{margin:14px;padding:14px 16px;border-radius:8px;background:#b8e75a;color:#152000;font:20px/1.2 var(--code-font-family,ui-monospace,SFMono-Regular,Consolas,monospace);letter-spacing:.04em;box-shadow:inset 0 0 0 2px rgba(0,0,0,.22);white-space:pre;overflow:auto}.keypad-led-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(110px,1fr));gap:8px;padding:0 14px 14px}.keypad-led{display:flex;align-items:center;gap:8px;min-height:36px;padding:7px 9px;border-radius:8px;background:var(--vt-form);color:var(--vt-secondary)}.keypad-led::before{content:"";width:8px;height:8px;border-radius:50%;background:currentColor;opacity:.45}.keypad-led.on{color:var(--vt-success)}.keypad-led.alert{color:var(--vt-error)}.keypad-led.unknown{color:var(--vt-disabled)}.keypad-meta{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:0;border:1px solid var(--vt-divider);border-radius:12px;overflow:hidden}.keypad-meta div{display:grid;grid-template-columns:minmax(110px,.7fr) minmax(0,1fr);gap:12px;padding:10px 12px;border-bottom:1px solid var(--vt-divider)}.keypad-meta div:nth-last-child(-n+2){border-bottom:0}.keypad-meta div:nth-child(odd){border-right:1px solid var(--vt-divider)}.keypad-meta dt{color:var(--vt-secondary)}.keypad-meta dd{margin:0;font-weight:500;overflow-wrap:anywhere}.keypad-empty{padding:28px;color:var(--vt-secondary);text-align:center}@media(max-width:900px){.partition-layout{grid-template-columns:1fr}.partition-browser{display:flex;overflow:auto;border-right:0;border-bottom:1px solid var(--vt-divider)}.partition-select{min-width:190px;border-bottom:0;border-right:1px solid var(--vt-divider)}}@media(max-width:700px){.keypad-meta{grid-template-columns:1fr}.keypad-meta div:nth-child(odd){border-right:0}.keypad-meta div:nth-last-child(-n+2){border-bottom:1px solid var(--vt-divider)}.keypad-meta div:last-child{border-bottom:0}}@media(max-width:600px){.partition-kv{grid-template-columns:repeat(2,1fr)}.table-toolbar{align-items:stretch}.search-box{min-width:100%}.compact-field{flex:1}.compact-field select{width:100%;min-width:0}.lcd{font-size:17px}.keypad-detail{padding:10px}}
  </style>
  <section class="surface partition-app">
    <div class="surface-head"><h2>Partitions</h2><span class="count" id="summary"></span></div>
    <div class="partition-layout">
      <nav class="partition-browser" id="partition-browser" aria-label="Partitions"></nav>
      <section class="partition-detail">
        <div class="partition-detail-head" id="partition-head"></div>
        <div class="partition-status" id="partition-status"></div>
        <nav class="detail-tabs" role="tablist" aria-label="Partition details">
          <button class="detail-tab" type="button" role="tab" data-view="zones">Zones</button>
          <button class="detail-tab" type="button" role="tab" data-view="keypad">Keypad</button>
        </nav>
        <section class="detail-view" data-detail-view="zones">
          <div class="table-toolbar">
            <label class="search-box"><span aria-hidden="true">⌕</span><input id="zone-search" type="search" placeholder="Search zones" aria-label="Search zones"></label>
            <label class="compact-field">State<select id="zone-filter"><option value="all">All</option><option value="abnormal">Abnormal only</option><option value="faulted">Faulted</option><option value="bypassed">Bypassed</option><option value="trouble">Trouble</option><option value="alarm">Alarm</option><option value="low_battery">Low battery</option><option value="tamper">Tamper</option></select></label>
          </div>
          <div class="table-scroll"><table class="data-table zones-table"><thead><tr><th><button data-sort="zone">Zone</button></th><th><button data-sort="descriptor">Descriptor</button></th><th><button data-sort="state">State</button></th><th>Fault</th><th>Bypass</th><th>Trouble</th><th>Alarm</th><th>Battery</th><th>Tamper</th></tr></thead><tbody id="zones"></tbody></table></div>
        </section>
        <section class="detail-view" data-detail-view="keypad" hidden><div id="keypad-detail"></div></section>
      </section>
    </div>
  </section>`;

  class VistaPartitionsApp extends HTMLElement {
    constructor() {
      super();
      this.attachShadow({ mode: "open" }).append(template.content.cloneNode(true));
      this._d = {};
      this._selected = 1;
      this._view = "zones";
      this._q = "";
      this._filter = "all";
      this._sort = "zone";
      this._dir = 1;
      this._bind();
      this._renderViews();
    }

    set data(v) {
      this._d = v || {};
      const ps = this._parts();
      if (!ps.some((p) => Number(p.partition) === Number(this._selected))) this._selected = Number(ps[0]?.partition || 1);
      this._render();
    }
    get data() { return this._d; }
    set hass(v) { this.toggleAttribute("dark", !!v?.themes?.darkMode); }
    set activePartition(v) { if (Number.isInteger(Number(v))) { this._selected = Number(v); this._render(); } }
    get activePartition() { return this._selected; }
    get activeView() { return this._view; }

    _bind() {
      const r = this.shadowRoot;
      r.getElementById("partition-browser").addEventListener("click", (e) => {
        const b = e.target.closest("[data-partition]");
        if (!b) return;
        this._selected = Number(b.dataset.partition);
        this._render();
      });
      r.querySelector(".detail-tabs").addEventListener("click", (e) => {
        const b = e.target.closest("[data-view]");
        if (!b) return;
        this._view = b.dataset.view;
        this._renderViews();
      });
      r.getElementById("zone-search").addEventListener("input", (e) => { this._q = e.target.value.toLowerCase().trim(); this._renderZones(); });
      r.getElementById("zone-filter").addEventListener("change", (e) => { this._filter = e.target.value; this._renderZones(); });
      r.querySelector(".zones-table thead").addEventListener("click", (e) => {
        const b = e.target.closest("[data-sort]");
        if (!b) return;
        const key = b.dataset.sort;
        if (this._sort === key) this._dir *= -1;
        else { this._sort = key; this._dir = 1; }
        this._renderZones();
      });
    }

    _parts() { return Array.isArray(this._d.panel?.partitions) ? this._d.panel.partitions : []; }
    _zones() { return Array.isArray(this._d.zones) ? this._d.zones : []; }
    _part() { return this._parts().find((p) => Number(p.partition) === this._selected) || null; }
    _partZones() { return this._zones().filter((z) => Number(z.partition) === this._selected); }
    _abnormal(z) { return Boolean(z.faulted || z.bypassed || z.trouble || z.alarm || z.low_battery || z.tamper); }
    _state(z) { if (z.alarm) return "Alarm"; if (z.trouble) return "Trouble"; if (z.faulted) return "Fault"; if (z.bypassed) return "Bypassed"; if (z.low_battery) return "Low battery"; if (z.tamper) return "Tamper"; return "Normal"; }
    _security(p) {
      const types = [["Fire", p.fire_alarm_active], ["Supervisory", p.supervisory_active], ["Burglary", p.burglary_alarm_active], ["Auxiliary", p.auxiliary_alarm_active], ["Audible panic", p.panic_audible_alarm_active], ["Silent", p.silent_alarm_active], ["Duress", p.duress_alarm_active]].filter(([, on]) => on === true).map(([label]) => label);
      if (types.length) return types.join(", ");
      return this._d.panel?.authoritative === false ? "Unknown" : "Normal";
    }
    _bool(v) { return v === true ? "On" : v === false ? "Off" : "Unknown"; }

    _renderViews() {
      const r = this.shadowRoot;
      r.querySelectorAll("[data-view]").forEach((b) => b.setAttribute("aria-selected", String(b.dataset.view === this._view)));
      r.querySelectorAll("[data-detail-view]").forEach((v) => { v.hidden = v.dataset.detailView !== this._view; });
    }

    _render() {
      const ps = this._parts();
      this.shadowRoot.getElementById("summary").textContent = `${ps.length} configured`;
      this.shadowRoot.getElementById("partition-browser").innerHTML = ps.map((p) => {
        const zones = this._zones().filter((z) => Number(z.partition) === Number(p.partition));
        const abnormal = zones.filter((z) => this._abnormal(z)).length;
        let state = String(p.arming_state || "").replaceAll("_", " ");
        if (!state) state = p.ready === true ? "ready" : p.ready === false ? "not ready" : "unknown";
        return `<button class="partition-select${Number(p.partition) === this._selected ? " selected" : ""}" data-partition="${p.partition}"><span class="partition-select-number">P${p.partition}</span><span class="partition-select-main"><strong>${esc(p.name || `Partition ${p.partition}`)}</strong><small>${esc(state)} · ${zones.length} zones${abnormal ? ` · ${abnormal} abnormal` : ""}</small></span></button>`;
      }).join("") || '<div class="empty">Partition data unavailable</div>';

      const p = this._part();
      const zones = this._partZones();
      const fresh = this._d.panel?.authoritative !== false;
      this.shadowRoot.getElementById("partition-head").innerHTML = p
        ? `<h2>Partition ${p.partition} · ${esc(p.name || `Partition ${p.partition}`)}</h2><span>${zones.length} assigned zones${fresh ? "" : " · panel state not yet authoritative"}</span>`
        : '<h2>Partition unavailable</h2>';
      const counts = { faulted: 0, bypassed: 0, trouble: 0, alarm: 0 };
      for (const z of zones) for (const k of Object.keys(counts)) if (z[k]) counts[k]++;
      this.shadowRoot.getElementById("partition-status").innerHTML = p
        ? `<div class="partition-kv"><div><span>Arming</span><strong>${esc(fresh ? String(p.arming_state || "Unknown").replaceAll("_", " ") : "Unknown")}</strong></div><div><span>Ready</span><strong>${fresh ? (p.ready === true ? "Yes" : p.ready === false ? "No" : "Unknown") : "Unknown"}</strong></div><div><span>Security</span><strong>${esc(this._security(p))}</strong></div><div><span>Faulted</span><strong>${counts.faulted}</strong></div><div><span>Bypassed</span><strong>${counts.bypassed}</strong></div><div><span>Trouble</span><strong>${counts.trouble}</strong></div><div><span>Alarm</span><strong>${counts.alarm}</strong></div></div>`
        : "";
      this._renderZones();
      this._renderKeypad();
      this._renderViews();
    }

    _renderZones() {
      let rows = this._partZones();
      const q = this._q;
      if (q) rows = rows.filter((z) => [String(z.zone).padStart(3, "0"), z.descriptor || "", this._state(z)].join(" ").toLowerCase().includes(q));
      if (this._filter === "abnormal") rows = rows.filter((z) => this._abnormal(z));
      else if (this._filter !== "all") rows = rows.filter((z) => Boolean(z[this._filter]));
      const dir = this._dir, key = this._sort;
      rows = [...rows].sort((a, b) => {
        const av = key === "state" ? this._state(a) : a[key], bv = key === "state" ? this._state(b) : b[key];
        if (key === "zone") return (Number(av) - Number(bv)) * dir;
        return String(av || "").localeCompare(String(bv || ""), undefined, { numeric: true, sensitivity: "base" }) * dir;
      });
      const mark = (v) => v ? '<span class="condition on">Yes</span>' : '<span class="condition">—</span>';
      this.shadowRoot.getElementById("zones").innerHTML = rows.map((z) => `<tr class="${this._abnormal(z) ? "abnormal" : ""}"><td class="mono">${String(z.zone).padStart(3, "0")}</td><td>${esc(z.descriptor || `Zone ${String(z.zone).padStart(3, "0")}`)}</td><td>${esc(this._state(z))}</td><td>${mark(z.faulted)}</td><td>${mark(z.bypassed)}</td><td>${mark(z.trouble)}</td><td>${mark(z.alarm)}</td><td>${mark(z.low_battery)}</td><td>${mark(z.tamper)}</td></tr>`).join("") || '<tr><td colspan="9" class="empty">No zones match</td></tr>';
    }

    _renderKeypad() {
      const p = this._part();
      const target = this.shadowRoot.getElementById("keypad-detail");
      const keypad = p?.keypad?.attributes;
      if (!p || !keypad) {
        target.innerHTML = '<div class="keypad-empty">Keypad data unavailable for this partition</div>';
        return;
      }
      const led = (label, value, alert = false) => `<div class="keypad-led ${value === true ? (alert ? "alert" : "on") : value == null ? "unknown" : ""}">${esc(label)} · ${this._bool(value)}</div>`;
      const line1 = String(keypad.line_1 || "").padEnd(16, " ").slice(0, 16);
      const line2 = String(keypad.line_2 || "").padEnd(16, " ").slice(0, 16);
      target.innerHTML = `<div class="keypad-detail"><section class="keypad-preview"><div class="keypad-preview-head"><strong>Partition ${p.partition} keypad</strong><span>${keypad.session_fresh === true ? "Fresh" : "Stale / unknown"}</span></div><div class="lcd">${esc(line1)}\n${esc(line2)}</div><div class="keypad-led-grid">${led("Ready", keypad.ready)}${led("Armed", keypad.armed, true)}${led("Power", keypad.power)}${led("Trouble", keypad.trouble, true)}${led("Fire", keypad.fire_alarm, true)}${led("Supervisory", keypad.supervisory, true)}${led("Burglary", keypad.burglary_alarm, true)}${led("Auxiliary", keypad.auxiliary_alarm, true)}</div></section><dl class="keypad-meta"><div><dt>Sound mode</dt><dd>${esc(keypad.sound_mode || "Unknown")}</dd></div><div><dt>Backlight</dt><dd>${this._bool(keypad.backlight)}</dd></div><div><dt>Audible panic</dt><dd>${this._bool(keypad.panic_audible_alarm)}</dd></div><div><dt>Silenced</dt><dd>${this._bool(keypad.silenced)}</dd></div><div><dt>Last chime zone</dt><dd>${keypad.chime_zone == null ? "None" : `${String(keypad.chime_zone).padStart(3, "0")}${keypad.chime_descriptor ? ` · ${esc(keypad.chime_descriptor)}` : ""}`}</dd></div><div><dt>Updated</dt><dd>${esc(keypad.updated_at || "Unknown")}</dd></div></dl></div>`;
    }
  }

  if (!customElements.get("vista-partitions-app")) customElements.define("vista-partitions-app", VistaPartitionsApp);
})();