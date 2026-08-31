(() => {
  const esc = (value) => String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");

  const TYPE_TABS = [
    ["all", "All"],
    ["panel", "Panel events"],
    ["audit", "Control audit"],
  ];
  const CLOSE_ICON = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M18.3 5.71 12 12l6.3 6.29-1.41 1.42L10.59 13.41 4.29 19.71 2.88 18.3 9.17 12 2.88 5.71 4.29 4.29 10.59 10.59 16.89 4.29z"></path></svg>';

  const template = document.createElement("template");
  template.innerHTML = `<style>${window.VISTA_MANAGEMENT_STYLES || ""}
    .log-app{overflow:hidden}.record-tabs{display:flex;min-height:48px;padding:0 10px;border-bottom:1px solid var(--vt-divider);background:var(--vt-card);overflow-x:auto}.record-tab{position:relative;min-height:48px;padding:0 14px;border:0;background:transparent;color:var(--vt-secondary);font:inherit;font-weight:500;cursor:pointer;white-space:nowrap}.record-tab:hover{background:var(--vt-hover);color:var(--vt-text)}.record-tab[aria-selected="true"]{color:var(--vt-primary)}.record-tab[aria-selected="true"]::after{content:"";position:absolute;left:10px;right:10px;bottom:0;height:3px;border-radius:3px 3px 0 0;background:var(--vt-primary)}.record-tab:focus-visible{outline:2px solid var(--vt-primary);outline-offset:-3px}.log-toolbar{display:flex;gap:8px;align-items:end;padding:10px 12px;flex-wrap:wrap;background:var(--vt-card)}.compact-field{display:grid;gap:3px;color:var(--vt-secondary);font-size:11px}.compact-field select,.compact-field input{height:40px;min-width:128px;border:0;border-radius:8px;background:var(--vt-form);color:var(--vt-text);padding:0 10px}.filter-actions{display:flex;align-items:center;gap:6px;margin-left:auto;min-height:40px}.filter-count,.summary-count{display:inline-flex;align-items:center;min-height:22px;border-radius:11px;padding:1px 8px;background:var(--vt-selected);color:var(--vt-primary);font-size:11px;font-weight:600;white-space:nowrap}.advanced{border-top:1px solid var(--vt-divider);background:var(--vt-card)}.advanced summary{cursor:pointer;padding:10px 12px;color:var(--vt-primary);font-weight:500;list-style:none;display:flex;align-items:center;gap:8px;min-height:42px}.advanced summary::-webkit-details-marker{display:none}.advanced summary::before{content:"›";display:inline-block;transform:rotate(0deg);transition:transform .12s ease}.advanced[open] summary::before{transform:rotate(90deg)}.advanced-fields{display:grid;grid-template-columns:repeat(6,minmax(110px,1fr));gap:8px;padding:0 12px 12px}.table-scroll{overflow:auto;border-top:1px solid var(--vt-divider);max-height:650px}.data-table{width:100%;border-collapse:collapse;font-size:13px}.data-table th{position:sticky;top:0;background:var(--vt-surface-header,var(--vt-card));z-index:1;color:var(--vt-secondary);font-weight:500;text-align:left;white-space:nowrap;border-bottom:1px solid var(--vt-divider)}.data-table th,.data-table td{padding:9px 10px;border-bottom:1px solid var(--vt-divider)}.data-table th button{border:0;background:transparent;color:inherit;padding:0;cursor:pointer;font-weight:inherit}.data-table th.sorted{color:var(--vt-text)}.data-table th.sorted button::after{content:" ↓";color:var(--vt-primary)}.data-table th.sorted[data-dir="asc"] button::after{content:" ↑"}.data-table tbody tr{cursor:pointer}.data-table tbody tr:hover,.data-table tbody tr:focus-visible{background:var(--vt-hover);outline:none}.record-type{display:inline-flex;padding:2px 7px;border-radius:11px;font-size:11px;font-weight:600;background:var(--vt-chip);color:var(--vt-secondary)}.record-type.audit{color:var(--vt-primary);background:var(--vt-selected)}.mono{font-variant-numeric:tabular-nums;font-family:var(--code-font-family,ui-monospace,SFMono-Regular,Consolas,monospace)}.table-footer{display:flex;align-items:center;justify-content:flex-end;gap:8px;padding:8px 12px;color:var(--vt-secondary);font-size:12px;background:var(--vt-card)}.table-footer label{display:flex;align-items:center;gap:5px}.table-footer select{height:32px;border:0;border-radius:6px;background:var(--vt-form);color:var(--vt-text)}.detail-kv{display:grid;grid-template-columns:150px minmax(0,1fr);gap:8px 14px;margin:0}.detail-kv dt{color:var(--vt-secondary)}.detail-kv dd{margin:0;overflow-wrap:anywhere}.loading{padding:28px 12px!important;color:var(--vt-secondary);text-align:center}.loading::before{content:"";display:inline-block;width:16px;height:16px;margin-right:8px;border:2px solid var(--vt-divider);border-top-color:var(--vt-primary);border-radius:50%;vertical-align:-3px;animation:vt-spin .8s linear infinite}.empty-log{padding:30px 12px!important;color:var(--vt-secondary);text-align:center}@keyframes vt-spin{to{transform:rotate(360deg)}}#detail-dialog .dialog-head .icon-button svg{width:22px;height:22px;fill:currentColor}@media(max-width:900px){.advanced-fields{grid-template-columns:repeat(3,1fr)}}@media(max-width:700px){.log-toolbar{align-items:stretch}.search-box{min-width:100%}.compact-field{flex:1}.compact-field select,.compact-field input{width:100%;min-width:0}.filter-actions{width:100%;margin-left:0;justify-content:flex-end}.advanced-fields{grid-template-columns:1fr 1fr}.table-footer{flex-wrap:wrap}.log-table th:nth-child(2),.log-table td:nth-child(2){display:none}.detail-kv{grid-template-columns:1fr}.detail-kv dd{margin-bottom:8px}}@media(max-width:480px){.record-tab{padding-inline:11px}.advanced-fields{grid-template-columns:1fr}}
  </style>
  <section class="surface log-app">
    <div class="surface-head"><h2>Event Log</h2><span class="count" id="count"></span></div>
    <nav class="record-tabs" role="tablist" aria-label="Event record type"></nav>
    <div class="log-toolbar">
      <label class="search-box"><span aria-hidden="true">⌕</span><input id="search" type="search" placeholder="Search events and audit" aria-label="Search events and audit"></label>
      <label class="compact-field">Partition<select id="partition"><option value="all">All partitions</option></select></label>
      <label class="compact-field">Source / result<select id="source"><option value="all">All sources / results</option><option value="live">Live</option><option value="history">History</option><option value="both">Live + history</option><option value="queued">Queued</option><option value="accepted">Accepted</option><option value="confirmed">Confirmed</option><option value="acknowledged_unverified">Acknowledged unverified</option><option value="unverified">Unverified</option><option value="failed">Failed</option><option value="verification_mismatch">Verification mismatch</option><option value="rejected">Rejected</option><option value="timeout">Timeout</option></select></label>
      <div class="filter-actions"><span class="filter-count" id="filter-count" hidden></span><button class="ha-button" id="clear-filters" type="button" hidden>Clear filters</button></div>
    </div>
    <details class="advanced" id="advanced"><summary><span>More filters</span><span class="summary-count" id="advanced-count" hidden></span></summary><div class="advanced-fields">
      <label class="compact-field">Zone<input id="zone" inputmode="numeric" maxlength="3" placeholder="Any"></label>
      <label class="compact-field">VISTA user<input id="user" inputmode="numeric" maxlength="3" placeholder="Any"></label>
      <label class="compact-field">HA actor<input id="actor" placeholder="Any"></label>
      <label class="compact-field">Outcome<input id="status" placeholder="Any"></label>
      <label class="compact-field">From<input id="start" type="datetime-local"></label>
      <label class="compact-field">To<input id="end" type="datetime-local"></label>
    </div></details>
    <div class="table-scroll"><table class="data-table log-table"><thead><tr>
      <th><button data-sort="time">Time</button></th>
      <th><button data-sort="type">Type</button></th>
      <th><button data-sort="event">Event / action</button></th>
      <th><button data-sort="partition">Partition</button></th>
      <th><button data-sort="subject">Subject</button></th>
      <th><button data-sort="source">Source / result</button></th>
    </tr></thead><tbody id="rows"></tbody></table></div>
    <div class="table-footer"><label>Rows <select id="page-size"><option>25</option><option>50</option><option>100</option></select></label><span id="range"></span><button class="ha-button" id="prev" type="button">Previous</button><button class="ha-button" id="next" type="button">Next</button></div>
  </section>
  <dialog id="detail-dialog"><div class="dialog-shell"><div class="dialog-head"><h3 id="detail-title"></h3><button class="icon-button" data-close type="button" aria-label="Close">${CLOSE_ICON}</button></div><div class="dialog-scroll" id="detail-body"></div><div class="dialog-actions"><button class="ha-button" data-close type="button">Close</button></div></div></dialog>`;

  class VistaEventLogApp extends HTMLElement {
    constructor() {
      super();
      this.attachShadow({ mode: "open" }).append(template.content.cloneNode(true));
      this._d = {};
      this._filters = { q: "", type: "all", partition: "all", source: "all", zone: "", user: "", actor: "", status: "", start: "", end: "" };
      this._sort = "time";
      this._dir = "desc";
      this._page = 1;
      this._pageSize = 25;
      this._admin = {};
      this._provider = null;
      this._detailProvider = null;
      this._remoteRecords = [];
      this._remoteTotal = 0;
      this._loadToken = 0;
      this._filterTimer = null;
      this._renderTypeTabs();
      this._bind();
      this._updateSortHeaders();
      this._updateFilterUi();
    }

    set data(value) { this._d = value || {}; this._populateFilters(); this._refresh(); }
    get data() { return this._d; }
    set hass(value) { this.toggleAttribute("dark", !!value?.themes?.darkMode); }
    set adminState(value) { this._admin = value || {}; }
    get adminState() { return this._admin; }
    set logProvider(value) { this._provider = typeof value === "function" ? value : null; this._populateFilters(); this._refresh(); }
    get logProvider() { return this._provider; }
    set auditDetailProvider(value) { this._detailProvider = typeof value === "function" ? value : null; }
    get recordType() { return this._filters.type; }

    _renderTypeTabs() {
      const host = this.shadowRoot.querySelector(".record-tabs");
      host.innerHTML = TYPE_TABS.map(([id, label]) => `<button class="record-tab" type="button" role="tab" data-record-type="${id}" aria-selected="${id === this._filters.type}">${label}</button>`).join("");
    }

    _setType(type) {
      if (!TYPE_TABS.some(([id]) => id === type)) return;
      this._filters.type = type;
      this._page = 1;
      this._renderTypeTabs();
      this._refresh();
    }

    _activeFilterCount() {
      return [this._filters.q, this._filters.partition !== "all" ? this._filters.partition : "", this._filters.source !== "all" ? this._filters.source : "", this._filters.zone, this._filters.user, this._filters.actor, this._filters.status, this._filters.start, this._filters.end].filter(Boolean).length;
    }

    _advancedFilterCount() {
      return [this._filters.zone, this._filters.user, this._filters.actor, this._filters.status, this._filters.start, this._filters.end].filter(Boolean).length;
    }

    _updateFilterUi() {
      const active = this._activeFilterCount();
      const advanced = this._advancedFilterCount();
      const count = this.shadowRoot.getElementById("filter-count");
      const clear = this.shadowRoot.getElementById("clear-filters");
      const advancedCount = this.shadowRoot.getElementById("advanced-count");
      count.hidden = active === 0;
      count.textContent = active ? `${active} active` : "";
      clear.hidden = active === 0;
      advancedCount.hidden = advanced === 0;
      advancedCount.textContent = advanced ? String(advanced) : "";
    }

    _clearFilters() {
      const type = this._filters.type;
      this._filters = { q: "", type, partition: "all", source: "all", zone: "", user: "", actor: "", status: "", start: "", end: "" };
      this._page = 1;
      const root = this.shadowRoot;
      root.getElementById("search").value = "";
      root.getElementById("partition").value = "all";
      root.getElementById("source").value = "all";
      for (const id of ["zone", "user", "actor", "status", "start", "end"]) root.getElementById(id).value = "";
      this._updateFilterUi();
      this._refresh();
    }

    _bind() {
      const root = this.shadowRoot;
      const schedule = () => { this._page = 1; this._updateFilterUi(); this._refresh(); };
      const debounce = () => { this._updateFilterUi(); clearTimeout(this._filterTimer); this._filterTimer = setTimeout(schedule, 180); };
      root.querySelector(".record-tabs").addEventListener("click", (event) => {
        const button = event.target.closest("[data-record-type]");
        if (button) this._setType(button.dataset.recordType);
      });
      root.getElementById("search").addEventListener("input", (event) => { this._filters.q = event.target.value.trim(); debounce(); });
      for (const id of ["partition", "source", "zone", "user", "actor", "status", "start", "end"]) {
        root.getElementById(id).addEventListener("change", (event) => { this._filters[id] = event.target.value; schedule(); });
        if (["zone", "user", "actor", "status"].includes(id)) root.getElementById(id).addEventListener("input", (event) => { this._filters[id] = event.target.value; debounce(); });
      }
      root.getElementById("clear-filters").addEventListener("click", () => this._clearFilters());
      root.getElementById("page-size").addEventListener("change", (event) => { this._pageSize = Number(event.target.value) || 25; this._page = 1; this._refresh(); });
      root.getElementById("prev").addEventListener("click", () => { if (this._page > 1) { this._page--; this._refresh(); } });
      root.getElementById("next").addEventListener("click", () => { this._page++; this._refresh(); });
      root.querySelector("thead").addEventListener("click", (event) => {
        const button = event.target.closest("[data-sort]");
        if (!button) return;
        const key = button.dataset.sort;
        if (this._sort === key) this._dir = this._dir === "asc" ? "desc" : "asc";
        else { this._sort = key; this._dir = key === "time" ? "desc" : "asc"; }
        this._page = 1;
        this._updateSortHeaders();
        this._refresh();
      });
      root.getElementById("rows").addEventListener("click", (event) => {
        const row = event.target.closest("[data-record-id]");
        if (row) this._openDetail(row.dataset.recordId);
      });
      root.getElementById("rows").addEventListener("keydown", (event) => {
        if (event.key !== "Enter" && event.key !== " ") return;
        const row = event.target.closest("[data-record-id]");
        if (!row) return;
        event.preventDefault();
        this._openDetail(row.dataset.recordId);
      });
      root.querySelectorAll("[data-close]").forEach((button) => button.addEventListener("click", () => root.getElementById("detail-dialog").close()));
    }

    _updateSortHeaders() {
      this.shadowRoot.querySelectorAll("thead th").forEach((th) => {
        th.classList.remove("sorted");
        th.removeAttribute("data-dir");
        th.removeAttribute("aria-sort");
        const button = th.querySelector("[data-sort]");
        if (button?.dataset.sort === this._sort) {
          th.classList.add("sorted");
          th.dataset.dir = this._dir;
          th.setAttribute("aria-sort", this._dir === "asc" ? "ascending" : "descending");
        }
      });
    }

    _localRecords() {
      const panel = (Array.isArray(this._d.events) ? this._d.events : []).map((event) => ({
        id: `panel:${event.id}`,
        record_type: "panel",
        time: event.panel_timestamp || event.received_at || "",
        event_action: event.description || event.event_code || "Event",
        partition: Number(event.partition) || 0,
        subject: event.zone ? `Z${String(event.zone).padStart(3, "0")}${event.descriptor ? ` · ${event.descriptor}` : ""}` : event.user ? `User ${String(event.user).padStart(3, "0")}` : event.descriptor || "—",
        source_result: event.source || "panel",
        zone: event.zone || 0,
        user_number: event.user || 0,
        actor_name: "",
        actor_id: "",
        event_code: event.event_code || "",
        status: "",
        raw: event,
      }));
      const audit = (Array.isArray(this._d.audit) ? this._d.audit : []).map((item) => ({
        id: `audit:${item.interaction_id || item.id}`,
        record_type: "audit",
        time: item.completed_at || item.last_seen_at || item.started_at || "",
        event_action: (item.action || item.command_type || "Control").replaceAll("_", " "),
        partition: Number(item.partition || item.partition_number) || 0,
        subject: item.actor_name || item.actor_id || "Home Assistant",
        source_result: item.status || item.verification || item.source || "audit",
        zone: 0,
        user_number: 0,
        actor_name: item.actor_name || "",
        actor_id: item.actor_id || "",
        event_code: "",
        status: item.status || "",
        raw: item,
      }));
      return [...panel, ...audit];
    }

    _populateFilters() {
      const root = this.shadowRoot;
      const parts = Array.isArray(this._d.panel?.partitions) ? this._d.panel.partitions : [];
      const partition = root.getElementById("partition");
      const current = this._filters.partition;
      partition.innerHTML = '<option value="all">All partitions</option>' + parts.map((item) => `<option value="${item.partition}">P${item.partition} ${esc(item.name || "")}</option>`).join("");
      partition.value = [...partition.options].some((option) => option.value === current) ? current : "all";
      this._filters.partition = partition.value;
      if (!this._provider) {
        const sources = [...new Set(this._localRecords().map((item) => item.source_result).filter(Boolean))].sort((a, b) => String(a).localeCompare(String(b)));
        const source = root.getElementById("source");
        const currentSource = this._filters.source;
        source.innerHTML = '<option value="all">All sources / results</option>' + sources.map((item) => `<option value="${esc(item)}">${esc(String(item).replaceAll("_", " "))}</option>`).join("");
        source.value = [...source.options].some((option) => option.value === currentSource) ? currentSource : "all";
        this._filters.source = source.value;
      } else {
        const source = root.getElementById("source");
        if ([...source.options].some((option) => option.value === this._filters.source)) source.value = this._filters.source;
        else { this._filters.source = "all"; source.value = "all"; }
      }
      this._updateFilterUi();
    }

    _refresh() { if (this._provider) this._loadRemote(); else this._renderLocal(); }

    async _loadRemote() {
      const token = ++this._loadToken;
      this.shadowRoot.getElementById("rows").innerHTML = '<tr><td colspan="6" class="loading">Loading records</td></tr>';
      this.shadowRoot.getElementById("count").textContent = "Loading…";
      try {
        const result = await this._provider({
          q: this._filters.q,
          type: this._filters.type,
          partition: this._filters.partition === "all" ? "" : this._filters.partition,
          source: this._filters.source === "all" ? "" : this._filters.source,
          zone: this._filters.zone,
          user: this._filters.user,
          actor: this._filters.actor,
          status: this._filters.status,
          start: this._filters.start,
          end: this._filters.end,
          sort: this._sort,
          direction: this._dir,
          page: this._page,
          page_size: this._pageSize,
        });
        if (token !== this._loadToken) return;
        this._remoteRecords = (result?.records || []).map((record) => ({ ...record, id: `${record.record_type}:${record.id}` }));
        this._remoteTotal = Number(result?.total || 0);
        this._renderRows(this._remoteRecords, this._remoteTotal);
      } catch (error) {
        if (token !== this._loadToken) return;
        this.shadowRoot.getElementById("rows").innerHTML = `<tr><td colspan="6" class="empty-log">${esc(error?.message || "Event log unavailable")}</td></tr>`;
        this.shadowRoot.getElementById("count").textContent = "Unavailable";
      }
    }

    _renderLocal() {
      let rows = this._localRecords();
      const filter = this._filters;
      const query = filter.q.toLowerCase();
      if (filter.type !== "all") rows = rows.filter((item) => item.record_type === filter.type);
      if (filter.partition !== "all") rows = rows.filter((item) => String(item.partition) === filter.partition);
      if (filter.source !== "all") rows = rows.filter((item) => String(item.source_result) === filter.source);
      if (filter.zone) rows = rows.filter((item) => String(item.zone) === String(Number(filter.zone)));
      if (filter.user) rows = rows.filter((item) => String(item.user_number) === String(Number(filter.user)));
      if (filter.actor) rows = rows.filter((item) => `${item.actor_name} ${item.actor_id}`.toLowerCase().includes(filter.actor.toLowerCase()));
      if (filter.status) rows = rows.filter((item) => String(item.status).toLowerCase().includes(filter.status.toLowerCase()));
      if (filter.start) rows = rows.filter((item) => Date.parse(item.time) >= Date.parse(filter.start));
      if (filter.end) rows = rows.filter((item) => Date.parse(item.time) <= Date.parse(filter.end));
      if (query) rows = rows.filter((item) => [item.time, item.record_type, item.event_action, item.partition, item.subject, item.source_result, item.event_code, item.zone, item.user_number, item.actor_name, item.actor_id, item.status].join(" ").toLowerCase().includes(query));
      const key = this._sort;
      const direction = this._dir === "asc" ? 1 : -1;
      rows.sort((a, b) => {
        const aliases = { type: "record_type", event: "event_action", source: "source_result" };
        const av = a[key] ?? a[aliases[key]], bv = b[key] ?? b[aliases[key]];
        if (key === "time") return ((Date.parse(av) || 0) - (Date.parse(bv) || 0)) * direction;
        if (key === "partition") return (Number(av) - Number(bv)) * direction;
        return String(av || "").localeCompare(String(bv || ""), undefined, { numeric: true, sensitivity: "base" }) * direction;
      });
      const total = rows.length;
      const pages = Math.max(1, Math.ceil(total / this._pageSize));
      this._page = Math.min(this._page, pages);
      const start = (this._page - 1) * this._pageSize;
      this._renderRows(rows.slice(start, start + this._pageSize), total);
    }

    _fmtTime(value) {
      if (!value) return "Unknown";
      const date = new Date(value);
      if (Number.isNaN(date.getTime())) return value;
      return new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" }).format(date);
    }

    _renderRows(view, total) {
      const start = (this._page - 1) * this._pageSize;
      const end = Math.min(total, start + view.length);
      this.shadowRoot.getElementById("count").textContent = `${total} records`;
      this.shadowRoot.getElementById("rows").innerHTML = view.map((item) => `<tr data-record-id="${esc(item.id)}" tabindex="0"><td class="mono">${esc(this._fmtTime(item.time))}</td><td><span class="record-type ${item.record_type}">${item.record_type === "panel" ? "Panel" : "Audit"}</span></td><td>${esc(String(item.event_action || "").replaceAll("_", " "))}</td><td>${item.partition ? `P${item.partition}` : "—"}</td><td>${esc(item.subject || "—")}</td><td>${esc(String(item.source_result || "—").replaceAll("_", " "))}</td></tr>`).join("") || '<tr><td colspan="6" class="empty-log">No records match the current filters</td></tr>';
      this.shadowRoot.getElementById("range").textContent = total ? `${start + 1}–${end} of ${total}` : "0 records";
      this.shadowRoot.getElementById("prev").disabled = this._page <= 1;
      this.shadowRoot.getElementById("next").disabled = end >= total;
    }

    async _openDetail(id) {
      const [kind, ...rest] = id.split(":");
      const rawId = rest.join(":");
      let record = (this._provider ? this._remoteRecords : this._localRecords()).find((item) => item.id === id || String(item.id) === rawId && item.record_type === kind);
      if (!record) return;
      let raw = record.raw || record;
      if (kind === "audit" && this._detailProvider) {
        try { raw = await this._detailProvider(rawId); record = { ...record, raw }; }
        catch (error) { raw = { ...raw, detail_error: error?.message || "Audit detail unavailable" }; }
      }
      const root = this.shadowRoot;
      root.getElementById("detail-title").textContent = kind === "panel" ? String(record.event_action || "Panel event") : `Audit · ${String(record.event_action || "Control").replaceAll("_", " ")}`;
      let rows = [];
      if (kind === "panel") {
        rows = [["Time", this._fmtTime(record.time)], ["Event code", raw.event_code || record.event_code || "—"], ["Partition", record.partition ? `P${record.partition}` : "—"], ["Zone", raw.zone || record.zone ? String(raw.zone || record.zone).padStart(3, "0") : "—"], ["User", raw.user || record.user_number ? String(raw.user || record.user_number).padStart(3, "0") : "—"], ["Descriptor", raw.descriptor || record.subject || "—"], ["Source", raw.source || record.source_result || "—"], ["Received", raw.received_at || "—"]];
      } else {
        rows = [["Started", raw.started_at || record.time || "—"], ["Completed", raw.completed_at || "—"], ["Actor", raw.actor_name || record.subject || raw.actor_id || "—"], ["Partition", record.partition ? `P${record.partition}` : "—"], ["Source", raw.source || "—"], ["Action", raw.action || record.event_action || "—"], ["Command type", raw.command_type || "—"], ["Status", raw.status || record.source_result || "—"], ["Verification", raw.verification || "—"], ["Execution", raw.execution_mechanism || "—"]];
        if (raw.sensitive_included === true || (!this._detailProvider && this._admin.elevated === true)) {
          if (raw.operands) rows.push(["Operands", typeof raw.operands === "string" ? raw.operands : JSON.stringify(raw.operands)]);
          if (raw.command_sequence) rows.push(["Command sequence", raw.command_sequence]);
          if (raw.code) rows.push(["Stored code", raw.code]);
        } else rows.push(["Sensitive command details", "Administrative unlock required"]);
        if (raw.detail_error) rows.push(["Detail", raw.detail_error]);
      }
      root.getElementById("detail-body").innerHTML = `<dl class="detail-kv">${rows.map(([key, value]) => `<dt>${esc(key)}</dt><dd class="${/command|code/i.test(key) ? "mono" : ""}">${esc(value)}</dd>`).join("")}</dl>`;
      root.getElementById("detail-dialog").showModal();
    }
  }

  if (!customElements.get("vista-event-log-app")) customElements.define("vista-event-log-app", VistaEventLogApp);
})();
