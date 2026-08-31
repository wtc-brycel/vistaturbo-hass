(() => {
  const esc = (v) => String(v ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");

  const template = document.createElement("template");
  template.innerHTML = `<style>${window.VISTA_MANAGEMENT_STYLES || ""}
    .partition-app{overflow:hidden}.partition-layout{display:grid;grid-template-columns:minmax(220px,286px) minmax(0,1fr);min-height:560px}.partition-browser{border-right:1px solid var(--vt-divider);min-width:0;background:var(--vt-card)}.partition-select{width:100%;border:0;border-bottom:1px solid var(--vt-divider);background:transparent;display:grid;grid-template-columns:42px minmax(0,1fr) auto;gap:8px;align-items:center;padding:11px 12px;text-align:left;cursor:pointer;color:inherit;position:relative}.partition-select:hover{background:var(--vt-hover)}.partition-select.selected{background:var(--vt-selected)}.partition-select.selected::before{content:"";position:absolute;inset-block:8px;inset-inline-start:0;width:3px;border-radius:0 3px 3px 0;background:var(--vt-primary)}.partition-select.selected .partition-select-number{color:var(--vt-primary)}.partition-select-number{font-weight:700;color:var(--vt-secondary);font-variant-numeric:tabular-nums}.partition-select-main{min-width:0}.partition-select-main strong,.partition-select-main small{display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.partition-select-main strong{font-weight:500}.partition-select-main small{color:var(--vt-secondary);margin-top:2px}.abnormal-count{min-width:22px;height:22px;border-radius:11px;display:grid;place-items:center;padding:0 6px;background:color-mix(in srgb,var(--vt-warning) 14%,transparent);color:var(--vt-warning);font-size:11px;font-weight:700}.partition-detail{min-width:0}.partition-detail-head{padding:14px 16px;border-bottom:1px solid var(--vt-divider);background:var(--vt-surface-header,var(--vt-card))}.partition-detail-head h2{margin:0;font-size:18px;font-weight:500}.partition-detail-head span{display:block;color:var(--vt-secondary);font-size:12px;margin-top:2px}.partition-status{border-bottom:1px solid var(--vt-divider);background:var(--vt-card)}.partition-kv{display:grid;grid-template-columns:repeat(auto-fit,minmax(108px,1fr));gap:0;margin:0;padding:8px 10px}.partition-kv div{padding:7px 8px;min-width:0}.partition-kv span{display:block;color:var(--vt-secondary);font-size:11px}.partition-kv strong{display:block;margin-top:2px;font-weight:600;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.partition-kv strong.good{color:var(--vt-success)}.partition-kv strong.warn{color:var(--vt-warning)}.partition-kv strong.alert{color:var(--vt-error)}.partition-kv strong.unknown{color:var(--vt-secondary)}.zones-head{display:flex;align-items:center;min-height:48px;padding:0 14px;border-bottom:1px solid var(--vt-divider);background:var(--vt-card)}.zones-head h3{margin:0;font-size:14px;font-weight:500}.zones-head .zone-count{margin-left:8px;color:var(--vt-secondary);font-size:12px}.table-toolbar{display:flex;gap:8px;align-items:end;padding:10px 12px;flex-wrap:wrap;background:var(--vt-card)}.compact-field{display:grid;gap:3px;color:var(--vt-secondary);font-size:11px}.compact-field select{height:40px;min-width:150px;border:0;border-radius:8px;background:var(--vt-form);color:var(--vt-text);padding:0 10px}.clear-filter{margin-left:auto;align-self:center}.table-scroll{overflow:auto;border-top:1px solid var(--vt-divider)}.data-table{width:100%;border-collapse:collapse;font-size:13px}.data-table th{position:sticky;top:0;background:var(--vt-surface-header,var(--vt-card));z-index:1;text-align:left;color:var(--vt-secondary);font-weight:500;border-bottom:1px solid var(--vt-divider);white-space:nowrap}.data-table th,.data-table td{padding:9px 10px;border-bottom:1px solid var(--vt-divider)}.data-table th button{border:0;background:transparent;color:inherit;padding:0;cursor:pointer;font-weight:inherit}.data-table tbody tr:hover{background:var(--vt-hover)}.data-table tbody tr.abnormal{background:color-mix(in srgb,var(--vt-warning) 5%,transparent)}.data-table tbody tr.abnormal:hover{background:color-mix(in srgb,var(--vt-warning) 10%,var(--vt-hover))}.mono{font-variant-numeric:tabular-nums;font-family:var(--code-font-family,ui-monospace,SFMono-Regular,Consolas,monospace)}.state-pill,.condition-pill{display:inline-flex;align-items:center;min-height:22px;padding:1px 7px;border-radius:11px;font-size:11px;font-weight:600;white-space:nowrap}.state-pill{background:var(--vt-chip);color:var(--vt-secondary)}.state-pill.abnormal{background:color-mix(in srgb,var(--vt-warning) 14%,transparent);color:var(--vt-warning)}.state-pill.alarm{background:color-mix(in srgb,var(--vt-error) 12%,transparent);color:var(--vt-error)}.conditions{display:flex;gap:4px;flex-wrap:wrap}.condition-pill{background:var(--vt-form);color:var(--vt-secondary)}.condition-pill.alarm{background:color-mix(in srgb,var(--vt-error) 12%,transparent);color:var(--vt-error)}.condition-pill.warning{background:color-mix(in srgb,var(--vt-warning) 12%,transparent);color:var(--vt-warning)}.no-conditions{color:var(--vt-secondary)}@media(max-width:900px){.partition-layout{grid-template-columns:1fr}.partition-browser{display:flex;overflow:auto;border-right:0;border-bottom:1px solid var(--vt-divider)}.partition-select{min-width:210px;border-bottom:0;border-right:1px solid var(--vt-divider)}}@media(max-width:600px){.partition-kv{grid-template-columns:repeat(2,1fr)}.table-toolbar{align-items:stretch}.search-box{min-width:100%}.compact-field{flex:1}.compact-field select{width:100%;min-width:0}.clear-filter{margin-left:0}.zones-table th:nth-child(3),.zones-table td:nth-child(3){display:none}}
  </style>
  <section class="surface partition-app">
    <div class="surface-head"><h2>Partitions</h2><span class="count" id="summary"></span></div>
    <div class="partition-layout">
      <nav class="partition-browser" id="partition-browser" aria-label="Partitions"></nav>
      <section class="partition-detail">
        <div class="partition-detail-head" id="partition-head"></div>
        <div class="partition-status" id="partition-status"></div>
        <div class="zones-head"><h3>Zones</h3><span class="zone-count" id="zone-count"></span></div>
        <div class="table-toolbar">
          <label class="search-box"><span aria-hidden="true">⌕</span><input id="zone-search" type="search" placeholder="Search zones" aria-label="Search zones"></label>
          <label class="compact-field">State<select id="zone-filter"><option value="all">All states</option><option value="abnormal">Abnormal only</option><option value="faulted">Faulted</option><option value="bypassed">Bypassed</option><option value="trouble">Trouble</option><option value="alarm">Alarm</option><option value="low_battery">Low battery</option><option value="tamper">Tamper</option></select></label>
          <button class="ha-button clear-filter" id="clear-zone-filter" type="button" hidden>Clear</button>
        </div>
        <div class="table-scroll"><table class="data-table zones-table"><thead><tr><th><button data-sort="zone">Zone</button></th><th><button data-sort="descriptor">Descriptor</button></th><th><button data-sort="state">State</button></th><th>Conditions</th></tr></thead><tbody id="zones"></tbody></table></div>
      </section>
    </div>
  </section>`;

  class VistaPartitionsApp extends HTMLElement {
    constructor() {
      super();
      this.attachShadow({ mode: "open" }).append(template.content.cloneNode(true));
      this._d = {};
      this._selected = 1;
      this._q = "";
      this._filter = "all";
      this._sort = "zone";
      this._dir = 1;
      this._bind();
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

    _bind() {
      const r = this.shadowRoot;
      r.getElementById("partition-browser").addEventListener("click", (e) => {
        const b = e.target.closest("[data-partition]");
        if (!b) return;
        this._selected = Number(b.dataset.partition);
        this._q = "";
        this._filter = "all";
        r.getElementById("zone-search").value = "";
        r.getElementById("zone-filter").value = "all";
        this._render();
      });
      r.getElementById("zone-search").addEventListener("input", (e) => { this._q = e.target.value.toLowerCase().trim(); this._renderZones(); });
      r.getElementById("zone-filter").addEventListener("change", (e) => { this._filter = e.target.value; this._renderZones(); });
      r.getElementById("clear-zone-filter").addEventListener("click", () => {
        this._q = "";
        this._filter = "all";
        r.getElementById("zone-search").value = "";
        r.getElementById("zone-filter").value = "all";
        this._renderZones();
      });
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

    _render() {
      const ps = this._parts();
      this.shadowRoot.getElementById("summary").textContent = `${ps.length} configured`;
      this.shadowRoot.getElementById("partition-browser").innerHTML = ps.map((p) => {
        const zones = this._zones().filter((z) => Number(z.partition) === Number(p.partition));
        const abnormal = zones.filter((z) => this._abnormal(z)).length;
        let state = String(p.arming_state || "").replaceAll("_", " ");
        if (!state) state = p.ready === true ? "ready" : p.ready === false ? "not ready" : "unknown";
        return `<button class="partition-select${Number(p.partition) === this._selected ? " selected" : ""}" data-partition="${p.partition}"><span class="partition-select-number">P${p.partition}</span><span class="partition-select-main"><strong>${esc(p.name || `Partition ${p.partition}`)}</strong><small>${esc(state)} · ${zones.length} zones</small></span>${abnormal ? `<span class="abnormal-count" title="${abnormal} abnormal zones">${abnormal}</span>` : ""}</button>`;
      }).join("") || '<div class="empty">Partition data unavailable</div>';

      const p = this._part();
      const zones = this._partZones();
      const fresh = this._d.panel?.authoritative !== false;
      this.shadowRoot.getElementById("partition-head").innerHTML = p
        ? `<h2>Partition ${p.partition} · ${esc(p.name || `Partition ${p.partition}`)}</h2><span>${zones.length} assigned zones${fresh ? "" : " · panel state not yet authoritative"}</span>`
        : '<h2>Partition unavailable</h2>';
      const counts = { faulted: 0, bypassed: 0, trouble: 0, alarm: 0 };
      for (const z of zones) for (const k of Object.keys(counts)) if (z[k]) counts[k]++;
      const security = p ? this._security(p) : "Unknown";
      const securityClass = security === "Normal" ? "good" : security === "Unknown" ? "unknown" : "alert";
      const arming = fresh && p ? String(p.arming_state || "Unknown").replaceAll("_", " ") : "Unknown";
      const ready = fresh && p ? (p.ready === true ? "Ready" : p.ready === false ? "Not ready" : "Unknown") : "Unknown";
      this.shadowRoot.getElementById("partition-status").innerHTML = p
        ? `<div class="partition-kv"><div><span>Arming</span><strong class="${arming === "Unknown" ? "unknown" : ""}">${esc(arming)}</strong></div><div><span>Ready</span><strong class="${ready === "Ready" ? "good" : ready === "Unknown" ? "unknown" : "warn"}">${esc(ready)}</strong></div><div><span>Security</span><strong class="${securityClass}">${esc(security)}</strong></div><div><span>Faulted</span><strong class="${counts.faulted ? "warn" : ""}">${counts.faulted}</strong></div><div><span>Bypassed</span><strong class="${counts.bypassed ? "warn" : ""}">${counts.bypassed}</strong></div><div><span>Trouble</span><strong class="${counts.trouble ? "warn" : ""}">${counts.trouble}</strong></div><div><span>Alarm</span><strong class="${counts.alarm ? "alert" : ""}">${counts.alarm}</strong></div></div>`
        : "";
      this._renderZones();
    }

    _conditionPills(z) {
      const values = [];
      if (z.alarm) values.push(["Alarm", "alarm"]);
      if (z.trouble) values.push(["Trouble", "warning"]);
      if (z.faulted) values.push(["Fault", "warning"]);
      if (z.bypassed) values.push(["Bypass", ""]);
      if (z.low_battery) values.push(["Low battery", "warning"]);
      if (z.tamper) values.push(["Tamper", "warning"]);
      if (!values.length) return '<span class="no-conditions">—</span>';
      return `<span class="conditions">${values.map(([label, cls]) => `<span class="condition-pill ${cls}">${label}</span>`).join("")}</span>`;
    }

    _renderZones() {
      let rows = this._partZones();
      const total = rows.length;
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
      this.shadowRoot.getElementById("zone-count").textContent = rows.length === total ? `${total}` : `${rows.length} of ${total}`;
      this.shadowRoot.getElementById("clear-zone-filter").hidden = !this._q && this._filter === "all";
      this.shadowRoot.getElementById("zones").innerHTML = rows.map((z) => {
        const state = this._state(z);
        const cls = state === "Alarm" ? "alarm" : state === "Normal" ? "" : "abnormal";
        return `<tr class="${this._abnormal(z) ? "abnormal" : ""}"><td class="mono">${String(z.zone).padStart(3, "0")}</td><td>${esc(z.descriptor || `Zone ${String(z.zone).padStart(3, "0")}`)}</td><td><span class="state-pill ${cls}">${esc(state)}</span></td><td>${this._conditionPills(z)}</td></tr>`;
      }).join("") || '<tr><td colspan="4" class="empty">No zones match the current filters</td></tr>';
    }
  }

  if (!customElements.get("vista-partitions-app")) customElements.define("vista-partitions-app", VistaPartitionsApp);
})();
