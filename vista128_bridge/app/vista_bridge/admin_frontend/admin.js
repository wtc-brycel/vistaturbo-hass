"use strict";

const appState = {
  snapshot: null, socket: null, live: false, lastUpdate: 0, epoch: 0,
  view: "overview", keypadPartition: null, keypadSignature: "",
  eventPage: 0, pageCursors: [""], eventRows: [], eventCursor: "", eventLoaded: false, eventLoading: false,
  eventRequest: 0, eventAbort: null, appliedFilters: {}, eventError: "",
  diagnosticRows: [], diagnosticCursor: "", diagnosticIncidents: [], diagnosticStats: null,
  diagnosticLoaded: false, diagnosticLoading: false, diagnosticRequest: 0, diagnosticAbort: null,
  diagnosticFilters: {}, diagnosticError: "",
  lastTransaction: "", lastResult: null, commandTimer: null,
};
const byId = (id) => document.getElementById(id);
const endpoint = (path) => new URL(path, document.baseURI);
const text = (value, fallback = "Unknown") => value === null || value === undefined || value === "" ? fallback : String(value);
const yesNo = (value) => value === true ? "Yes" : value === false ? "No" : "Unknown";
const number = (value) => new Intl.NumberFormat().format(Number(value || 0));
const clear = (element) => element.replaceChildren();
function setText(id, value) { if (byId(id).textContent !== value) byId(id).textContent = value; }
function node(tag, className, value) {
  const element = document.createElement(tag);
  if (className) element.className = className;
  if (value !== undefined) element.textContent = value;
  return element;
}
function dateTime(value) {
  if (!value) return "Not recorded";
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? String(value) : parsed.toLocaleString(undefined, {
    timeZone: appState.snapshot?.panel?.timezone || "UTC",
  });
}
function panelDateTime(value) {
  const m = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})/.exec(String(value || ""));
  return m ? `${m[2]}/${m[3]}/${m[1]} ${m[4]}:${m[5]}` : "Time unavailable";
}
function eventKind(event) {
  return ["fire", "security", "supervisory", "trouble", "restore", "bypass", "fault"].includes(event.kind) ? event.kind : "neutral";
}
function eventMeta(event) {
  return [event.partition ? `P${event.partition}` : "System",
    event.zone ? `Z${String(event.zone).padStart(3, "0")}` : "",
    event.user ? `U${String(event.user).padStart(3, "0")}` : ""].filter(Boolean).join(" · ");
}
function displaySnapshot() {
  const s = appState.snapshot;
  if (!s || appState.live) return s;
  // A cached snapshot is not a live display, even when its last packet was normal.
  return { ...s, panel: { ...s.panel, connected: null, automation_available: null, state_fresh: false },
    system: { ...s.system, ac_power: null, battery_low: null, complete: false,
      condition: { kind: "unknown", title: "STATUS UNAVAILABLE", detail: "" }, conditions: [],
      alarm_states: { complete: false } },
    control: { ...s.control, keypad_available: false },
    partitions: Object.fromEntries(Object.entries(s.partitions).map(([id, p]) => [id, {
      ...p, vista_mode: null, ready: null, condition: { kind: "unknown", text: "UNKNOWN" },
    }])),
    keypads: Object.fromEntries(Object.entries(s.keypads).map(([id, k]) => [id, {
      ...k, available: false, control_enabled: false,
    }])),
  };
}
function renderBanner(s) {
  const c = s.system.condition;
  byId("system-banner").className = `system-banner state-${c.kind}`;
  setText("system-state-title", c.title);
  setText("system-state-detail", c.detail || "");
  byId("system-icon-use").setAttribute("href", c.kind === "normal" ? "#i-check" : "#i-alert");
  setText("context-panel", s.panel.connected === null ? "UNKNOWN" : s.panel.connected ? "ONLINE" : "OFFLINE");
  setText("context-automation", s.panel.automation_available === null ? "UNKNOWN" : s.panel.automation_available ? "AVAILABLE" : "UNAVAILABLE");
  setText("context-power", s.system.ac_power === true ? "NORMAL" : s.system.ac_power === false ? "LOSS" : "UNKNOWN");
  setText("context-freshness", s.panel.state_fresh ? "CURRENT" : s.panel.connected ? "NOT CURRENT" : "UNAVAILABLE");
}
function indicator(name, state, label) {
  byId(`indicator-${name}`).className = `indicator-lamp ${state}`;
  setText(`indicator-${name}-text`, label);
}
function renderOverview(s) {
  setText("overview-sync", s.synchronizer.last_success_at ? `Reconciled ${dateTime(s.synchronizer.last_success_at)}` : "");
  indicator("power", s.system.ac_power === true ? "ok" : s.system.ac_power === false ? "warning" : "unknown",
    s.system.ac_power === true ? "Normal" : s.system.ac_power === false ? "AC loss" : "Unknown");
  indicator("battery", s.system.battery_low === false ? "ok" : s.system.battery_low === true ? "warning" : "unknown",
    s.system.battery_low === false ? "Normal" : s.system.battery_low === true ? "Low" : "Unknown");
  indicator("automation", s.panel.automation_available ? "ok" : "unknown", s.panel.automation_available ? "Available" : "Unavailable");
  indicator("snapshot", s.system.alarm_states.complete ? "ok" : "unknown", s.system.alarm_states.complete ? "Known" : "Incomplete");
  const list = byId("active-conditions"); clear(list);
  const conditions = s.system.conditions;
  setText("condition-summary", conditions.length ? `${conditions.length} REPORTED` : s.system.complete ? "NORMAL" : "UNKNOWN");
  const rows = conditions.length ? conditions : [{
    kind: s.system.complete ? "normal" : "unknown",
    title: s.system.complete ? "No active conditions" : "Status incomplete",
    detail: s.system.complete ? "" : s.system.condition.detail,
    state: "", partition: null,
  }];
  for (const c of rows) {
    const row = node("div", `condition-row ${c.kind}`);
    const copy = node("div", "condition-copy");
    const scope = c.partition === null ? "" : c.partition === 0 ? "System" : `Partition ${c.partition}`;
    copy.append(node("div", "condition-title", c.title), node("div", "condition-detail", [scope, c.detail].filter(Boolean).join(" · ")));
    row.append(node("span", "condition-accent"), copy, node("div", "condition-state", c.state));
    list.append(row);
  }
  const latest = byId("latest-event"); clear(latest);
  const e = s.last_event;
  byId("latest-event-code").textContent = e ? e.event_code : "--";
  latest.className = `latest-event ${e ? eventKind(e) : "empty-state"}`;
  if (!e) latest.textContent = "No events received.";
  else {
    latest.append(node("div", "latest-event-title", e.description));
    if (e.descriptor) latest.append(node("div", "latest-event-descriptor", e.descriptor));
    latest.append(node("div", "latest-event-meta", `${panelDateTime(e.panel_timestamp)} · ${eventMeta(e)}`));
    latest.title = e.received_at ? `Received ${dateTime(e.received_at)}` : "";
  }
  const partitions = byId("partition-grid"); clear(partitions);
  for (const [id, p] of Object.entries(s.partitions)) {
    const row = node("div", "table-row"); row.setAttribute("role", "row");
    const cells = [node("div", "partition-number", `Partition ${id}`),
      node("div", "partition-mode", text(p.vista_mode).replaceAll("_", " ")),
      node("div", "", yesNo(p.ready).toUpperCase()),
      node("div", `state-label ${p.condition.kind}`, p.condition.text)];
    cells.forEach((cell) => cell.setAttribute("role", "cell"));
    row.append(...cells); partitions.append(row);
  }
}
function diagnosticCard(title, entries) {
  const card = node("div", "diagnostic-card");
  card.append(node("div", "diagnostic-title", title));
  entries.forEach(([key, value]) => {
    const row = node("div", "kv-row");
    row.append(node("div", "kv-key", key), node("div", "kv-value", text(value)));
    card.append(row);
  });
  return card;
}

function renderDiagnostics(snapshot) {
  const grid = byId("diagnostics-grid");
  clear(grid);
  grid.append(
    diagnosticCard("Application", [
      ["Version", snapshot.app.version],
      ["Started", dateTime(snapshot.app.started_at)],
      ["Uptime", `${number(snapshot.app.uptime_seconds)} s`],
      ["Browser connection", appState.live ? "Live" : "Unavailable"],
      ["Ingress user", snapshot.user.display_name || snapshot.user.name || snapshot.user.id],
    ]),
    diagnosticCard("Panel transport", [
      ["Endpoint", `${snapshot.panel.host}:${snapshot.panel.port}`],
      ["Connected", yesNo(snapshot.panel.connected)],
      ["Telnet active", yesNo(snapshot.transport.telnet_active)],
      ["RX frames", number(snapshot.transport.rx_frames)],
      ["RX bytes", number(snapshot.transport.rx_bytes)],
      ["TX frames", number(snapshot.transport.tx_frames)],
      ["TX bytes", number(snapshot.transport.tx_bytes)],
      ["Invalid frames", number(snapshot.transport.invalid_frames)],
    ]),
    diagnosticCard("Synchronization", [
      ["Active", yesNo(snapshot.synchronizer.active)],
      ["Pending transaction", text(snapshot.synchronizer.pending_transaction, "None")],
      ["Last success", dateTime(snapshot.synchronizer.last_success_at)],
      ["Consecutive failures", number(snapshot.synchronizer.failures_consecutive)],
      ["Total failures", number(snapshot.synchronizer.failures_total)],
      ["State fresh", yesNo(snapshot.panel.state_fresh)],
      ["Alarm knowledge complete", yesNo(snapshot.panel.alarm_knowledge_complete)],
    ]),
    diagnosticCard("Control", [
      ["Control enabled", yesNo(snapshot.control.enabled)],
      ["Keypad enabled", yesNo(snapshot.control.keypad_enabled)],
      ["Native alarm enabled", yesNo(snapshot.control.native_alarm_enabled)],
      ["Keypad available now", yesNo(snapshot.control.keypad_available)],
      ["Automation available", yesNo(snapshot.panel.automation_available)],
      ["TX queue", number(snapshot.transport.tx_queue_depth)],
      ["Raw TX queue", number(snapshot.transport.raw_tx_queue_depth)],
    ]),
    diagnosticCard("Event journal", [
      ["Enabled", yesNo(snapshot.journal.enabled)],
      ["Rows", number(snapshot.journal.count)],
      ["Retention", `${number(snapshot.journal.retention_days)} days`],
      ["Maximum rows", number(snapshot.journal.max_rows)],
      ["Last dump", dateTime(snapshot.journal.last_dump_at)],
      ["Last dump seen", number(snapshot.journal.last_dump_seen)],
      ["Last dump inserted", number(snapshot.journal.last_dump_inserted)],
    ]),
    diagnosticCard("Interfaces", [
      ["MQTT connected", yesNo(snapshot.mqtt.connected)],
      ["MQTT TLS", yesNo(snapshot.mqtt.tls_enabled)],
      ["MQTT publish errors", number(snapshot.mqtt.publish_errors)],
      ["Printer enabled", yesNo(snapshot.printer.enabled)],
      ["Printer status", snapshot.printer.status],
      ["Printer queue", number(snapshot.printer.queue_depth)],
      ["Printer failures", number(snapshot.printer.failed)],
      ["Printer last error", text(snapshot.printer.last_error, "None")],
    ]),
    diagnosticCard("Diagnostic journal", [
      ["Available", yesNo(snapshot.diagnostics?.available)],
      ["Writer", snapshot.diagnostics?.writer_alive ? "Running" : "Unavailable"],
      ["Pending writes", number(snapshot.diagnostics?.pending_writes)],
      ["Dropped events", number(snapshot.diagnostics?.dropped_events)],
      ["Write errors", number(snapshot.diagnostics?.write_errors)],
      ["Retention", `${number(snapshot.diagnostics?.retention_days)} days`],
      ["Maximum rows", number(snapshot.diagnostics?.max_rows)],
    ]),
  );
  renderDiagnosticJournal();
}

const RESULT_LABELS = {
  accepted: "Key acknowledged", confirmed: "Operation confirmed", queued: "Queued",
  control_disabled: "Read-only: control disabled", keypad_control_disabled: "Read-only: keypad control disabled",
  automation_interface_unavailable: "Read-only: automation unavailable", panel_offline: "Read-only: panel offline",
  state_not_current: "Read-only: state not current", stale_session: "Panel session changed; key not sent",
  installer_programming_blocked: "Installer programming blocked", no_ready_ack: "No panel acknowledgement; check display",
  request_expired: "Key expired; not sent", transaction_conflict: "Duplicate request rejected",
  control_queue_full: "Keypad queue full; key not sent", request_limit: "Request limit reached; key not sent",
  connection_lost_after_send: "Connection lost; result unknown", result_unknown: "Result unknown; check display",
};
function showCommand(status, ok = false) {
  const element = byId("keypad-result");
  element.hidden = false;
  element.className = `notice ${ok ? "success" : ""}`;
  element.textContent = RESULT_LABELS[status] || `Keypad: ${text(status).replaceAll("_", " ")}`;
}
async function jsonRequest(path, options = {}) {
  const response = await fetch(endpoint(path), { cache: "no-store", ...options });
  if (!response.ok) {
    let result;
    try { result = await response.json(); } catch (_) { /* HTML proxy errors are not API results. */ }
    const error = new Error(result?.status || (response.status === 403 ? "Administrator access required" : `Request failed (${response.status})`));
    error.status = response.status;
    throw error;
  }
  return response.json();
}
function maySend(partition, epoch) {
  return appState.live && performance.now() - appState.lastUpdate < 10000 && appState.epoch === epoch
    && appState.keypadPartition === partition && appState.snapshot?.keypads?.[partition]?.available
    && appState.snapshot?.keypads?.[partition]?.control_enabled;
}
function renderKeypad(s) {
  const select = byId("keypad-partition");
  const ids = Object.keys(s.keypads).map(Number).sort((a, b) => a - b);
  if (!ids.includes(appState.keypadPartition)) appState.keypadPartition = ids[0] || null;
  if (select.dataset.partitions !== ids.join(",")) {
    select.replaceChildren(...ids.map((id) => { const o = node("option", "", `Partition ${id}`); o.value = id; return o; }));
    select.dataset.partitions = ids.join(",");
  }
  select.value = String(appState.keypadPartition || ""); select.disabled = !ids.length;
  const p = appState.keypadPartition, k = s.keypads[p], available = Boolean(k?.available), enabled = Boolean(k?.control_enabled && available && appState.live);
  const warning = byId("keypad-warning");
  warning.hidden = enabled;
  warning.textContent = !ids.length ? "No keypad partitions configured" : !appState.live ? "Read-only: live state unavailable"
    : !s.control.enabled || !s.control.keypad_enabled ? "Read-only: keypad control disabled"
    : !s.panel.connected ? "Read-only: panel offline"
    : !s.panel.automation_available ? "Read-only: automation unavailable" : "Read-only: state not current";
  const signature = JSON.stringify([p, appState.epoch, enabled, available]);
  if (signature !== appState.keypadSignature) {
    appState.keypadSignature = signature;
    // Disconnect the old element to discard queued keys on scope/session changes.
    const replacement = document.createElement("vista-keypad-card"); replacement.id = "ingress-keypad";
    byId("ingress-keypad").replaceWith(replacement);
    replacement.setConfig({ entity: "sensor.vista_ingress_keypad", model: "6160cr2", layout: "auto", case_color: "auto",
      show_card_background: false, read_only: !enabled, sound: { enabled: false }, haptic: { enabled: false } });
  }
  const epoch = appState.epoch;
  byId("ingress-keypad").hass = {
    states: { "sensor.vista_ingress_keypad": { state: available ? text(k.state, "blank") : "unavailable",
      attributes: { ...k, control_enabled: enabled, command_topic: `vista/ingress/keypad/${p}/command` } } },
    themes: { darkMode: window.matchMedia("(prefers-color-scheme: dark)").matches }, user: s.user,
    callService: async (domain, service, data) => {
      if (domain !== "mqtt" || service !== "publish" || !maySend(p, epoch)) throw new Error("Keypad unavailable");
      const payload = JSON.parse(data.payload);
      appState.lastTransaction = payload.transaction_id; appState.lastResult = null;
      const txn = appState.lastTransaction;
      clearTimeout(appState.commandTimer); showCommand("queued", true);
      try {
        const current = appState.snapshot;
        const result = await jsonRequest("api/keypad", { method: "POST", signal: AbortSignal.timeout(6000),
          headers: { "Content-Type": "application/json", "X-Vista-CSRF": current.csrf_token },
          body: JSON.stringify({ partition: p, key: payload.keys, transaction_id: txn,
            audit_interaction_id: payload.audit_interaction_id, instance_id: current.instance_id,
            session_generation: current.panel.session_generation }) });
        if (!result.accepted) throw new Error(result.status);
        if (!appState.lastResult && appState.lastTransaction === txn) {
          appState.commandTimer = setTimeout(() => { if (!appState.lastResult && appState.lastTransaction === txn) showCommand("result_unknown"); }, 7000);
        }
        return result;
      } catch (error) {
        if (appState.lastTransaction === txn) showCommand(RESULT_LABELS[error.message] ? error.message : "result_unknown");
        throw error; // Never retry a key after a transport failure.
      }
    },
  };
}
function renderActive() {
  const s = displaySnapshot(); if (!s) return;
  renderBanner(s);
  if (appState.view === "overview") renderOverview(s);
  if (appState.view === "diagnostics") {
    renderDiagnostics(s); setText("diagnostic-version", `Vista Turbo ${s.app.version}`);
  }
  // Hidden keypads must also lose their input authority immediately.
  renderKeypad(s);
  setText("journal-header-meta", s.journal.enabled ? `${number(s.journal.count)} retained · Panel time: ${s.panel.timezone}` : "Journal disabled");
}
function applySnapshot(s) {
  if (!s?.system?.condition || !s?.panel || !s?.keypads || !Array.isArray(s.system.conditions)) throw new Error("Invalid status snapshot");
  const previous = appState.snapshot;
  if (!appState.live || previous?.instance_id !== s.instance_id || previous?.panel.session_generation !== s.panel.session_generation) appState.epoch++;
  appState.snapshot = s; appState.live = true; appState.lastUpdate = performance.now();
  for (const result of s.control_results || []) {
    if (result.transaction_id === appState.lastTransaction && JSON.stringify(result) !== JSON.stringify(appState.lastResult)) {
      appState.lastResult = result; clearTimeout(appState.commandTimer); showCommand(result.status, result.ok);
    }
  }
  renderActive();
}
function invalidate(label = "STATUS UNAVAILABLE") {
  appState.live = false; appState.epoch++; renderActive();
  byId("system-banner").className = "system-banner state-unknown";
  setText("system-state-title", label); setText("system-state-detail", "");
  if (appState.lastTransaction && !appState.lastResult) { clearTimeout(appState.commandTimer); showCommand("result_unknown"); }
}
function switchView(view) {
  if (!["overview", "keypad", "events", "diagnostics"].includes(view)) view = "overview";
  appState.view = view;
  document.querySelectorAll(".view").forEach((e) => e.classList.toggle("active", e.id === `view-${view}`));
  document.querySelectorAll(".nav-button").forEach((e) => {
    e.classList.toggle("active", e.dataset.view === view);
    if (e.dataset.view === view) e.setAttribute("aria-current", "page"); else e.removeAttribute("aria-current");
  });
  renderActive();
  if (view === "events" && !appState.eventLoaded && !appState.eventLoading) loadEvents(true);
  if (view === "diagnostics" && !appState.diagnosticLoaded && !appState.diagnosticLoading) loadDiagnostics(true);
}
function diagnosticSeverity(value) {
  return ["critical", "error", "warning", "info", "debug"].includes(value) ? value : "info";
}
function renderDiagnosticJournal() {
  const incidents = byId("diagnostic-incidents"); clear(incidents);
  setText("diagnostic-incident-count", appState.diagnosticIncidents.length ? `${appState.diagnosticIncidents.length} SHOWN` : "");
  if (!appState.diagnosticIncidents.length) {
    incidents.append(node("div", "event-empty", appState.diagnosticLoaded ? "No correlated incidents" : "Not loaded"));
  } else {
    for (const incident of appState.diagnosticIncidents) {
      const button = node("button", `diagnostic-incident severity-${diagnosticSeverity(incident.severity)}`);
      button.type = "button";
      const copy = node("span", "diagnostic-incident-copy");
      copy.append(
        node("span", "diagnostic-incident-title", incident.summary || "Diagnostic incident"),
        node("span", "diagnostic-incident-meta", `${dateTime(incident.started_at)} · ${number(incident.event_count)} events · ${incident.categories.join(", ").replaceAll("_", " ")}`)
      );
      button.append(node("span", "diagnostic-incident-severity", incident.severity.toUpperCase()), copy);
      button.addEventListener("click", () => {
        byId("diagnostic-severity").value = "";
        byId("diagnostic-category").value = "";
        loadDiagnostics(true, incident.correlation_id);
      });
      incidents.append(button);
    }
  }

  const list = byId("diagnostic-event-list"); clear(list);
  if (!appState.diagnosticRows.length) {
    list.append(node("div", "event-empty", appState.diagnosticError || (appState.diagnosticLoaded ? "No diagnostic events match" : "Not loaded")));
  }
  for (const record of appState.diagnosticRows) {
    const row = node("div", `table-row diagnostic-event-row severity-${diagnosticSeverity(record.severity)}`);
    row.setAttribute("role", "row");
    const event = node("div", "diagnostic-event-description");
    const details = node("div", "diagnostic-event-details");
    details.hidden = true;
    const detailEntries = Object.entries(record.details || {}).sort(([a], [b]) => a.localeCompare(b));
    if (detailEntries.length) {
      for (const [key, value] of detailEntries) {
        const detailRow = node("div", "diagnostic-detail-row");
        detailRow.append(
          node("span", "diagnostic-detail-key", key.replaceAll("_", " ")),
          node("span", "diagnostic-detail-value", typeof value === "string" ? value : JSON.stringify(value))
        );
        details.append(detailRow);
      }
    }
    event.append(
      node("div", "event-description-main", record.message || record.event_type),
      node("div", "event-description-sub", [
        record.event_type,
        record.correlation_id ? `incident ${record.correlation_id}` : "",
        detailEntries.length ? "details" : "",
      ].filter(Boolean).join(" · ")),
      details
    );
    const cells = [
      node("div", "diagnostic-time", dateTime(record.occurred_at)),
      node("div", `diagnostic-severity severity-${diagnosticSeverity(record.severity)}`, record.severity.toUpperCase()),
      node("div", "diagnostic-category", record.category.replaceAll("_", " ")),
      event,
      node("div", "diagnostic-component", text(record.component, "—")),
    ];
    cells.forEach((cell) => cell.setAttribute("role", "cell"));
    row.append(...cells);
    if (detailEntries.length) {
      row.tabIndex = 0;
      row.setAttribute("aria-expanded", "false");
      const toggle = () => {
        details.hidden = !details.hidden;
        row.setAttribute("aria-expanded", details.hidden ? "false" : "true");
      };
      row.addEventListener("click", toggle);
      row.addEventListener("keydown", (event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault(); toggle();
        }
      });
    }
    list.append(row);
  }
  const stats = appState.diagnosticStats;
  const correlation = appState.diagnosticFilters.correlation_id;
  setText("diagnostic-summary", appState.diagnosticError || (stats
    ? `${number(appState.diagnosticRows.length)} shown · ${number(stats.count)} retained${correlation ? " · Incident selected" : ""}`
    : "Not loaded"));
  byId("diagnostic-more").hidden = !appState.diagnosticCursor;
}
function setDiagnosticLoading(value) {
  appState.diagnosticLoading = value;
  byId("diagnostic-more").disabled = value;
  byId("diagnostics-refresh").disabled = value;
}
async function loadDiagnostics(reset, correlationId = null) {
  if (!reset && (appState.diagnosticLoading || !appState.diagnosticCursor)) return;
  const requestId = ++appState.diagnosticRequest;
  appState.diagnosticAbort?.abort(); appState.diagnosticAbort = new AbortController();
  const filters = reset
    ? correlationId
      ? { severity: "", category: "", correlation_id: correlationId }
      : {
          severity: byId("diagnostic-severity").value,
          category: byId("diagnostic-category").value,
          correlation_id: "",
        }
    : appState.diagnosticFilters;
  const params = new URLSearchParams({ limit: "50" });
  for (const [key, value] of Object.entries(filters)) if (value) params.set(key, value);
  if (!reset && appState.diagnosticCursor) params.set("cursor", appState.diagnosticCursor);
  setDiagnosticLoading(true); appState.diagnosticError = ""; setText("diagnostic-summary", "Loading");
  try {
    const result = await jsonRequest(`api/diagnostics?${params}`, { signal: appState.diagnosticAbort.signal });
    if (requestId !== appState.diagnosticRequest) return;
    appState.diagnosticRows = reset ? result.records : [...appState.diagnosticRows, ...result.records];
    appState.diagnosticCursor = result.next_cursor || "";
    appState.diagnosticIncidents = result.incidents || [];
    appState.diagnosticStats = result.stats || null;
    appState.diagnosticLoaded = true; appState.diagnosticFilters = filters;
    renderDiagnosticJournal();
  } catch (error) {
    if (requestId !== appState.diagnosticRequest || error.name === "AbortError") return;
    appState.diagnosticError = error.message; setText("diagnostic-summary", error.message);
  } finally { if (requestId === appState.diagnosticRequest) setDiagnosticLoading(false); }
}

function renderEvents() {
  const list = byId("event-list"); clear(list);
  if (!appState.eventRows.length) list.append(node("div", "event-empty", appState.snapshot?.journal.enabled === false ? "Journal disabled" : "No events match"));
  for (const e of appState.eventRows) {
    const row = node("div", `event-row ${eventKind(e)}`); row.setAttribute("role", "row");
    const detail = node("div", "event-description");
    detail.append(node("div", "event-description-main", e.description), node("div", "event-meta", [e.descriptor, eventMeta(e)].filter(Boolean).join(" · ")));
    const cells = [node("div", "event-time", panelDateTime(e.panel_timestamp)), node("div", "event-code", e.event_code), detail, node("div", "event-source", e.source)];
    cells.forEach((cell) => cell.setAttribute("role", "cell"));
    row.append(...cells); row.title = `Received ${dateTime(e.received_at)}`; list.append(row);
  }
  setText("event-summary", appState.eventError || `${number(appState.eventRows.length)} events · Page ${appState.eventPage + 1}`);
  byId("event-more").hidden = !appState.eventCursor;
  byId("event-newer").hidden = appState.eventPage === 0;
}
function setEventLoading(value) {
  appState.eventLoading = value;
  byId("event-newer").disabled = value; byId("event-more").disabled = value; byId("events-refresh").disabled = value;
}
async function loadEvents(reset, direction = 1) {
  if (!reset && (appState.eventLoading || (direction === 1 && !appState.eventCursor) || (direction === -1 && appState.eventPage === 0))) return;
  const requestId = ++appState.eventRequest;
  appState.eventAbort?.abort(); appState.eventAbort = new AbortController();
  const filters = reset ? { q: byId("event-search").value.trim(), partition: byId("event-partition").value, source: byId("event-source").value } : appState.appliedFilters;
  const params = new URLSearchParams({ limit: "50", ...filters });
  const page = reset ? 0 : appState.eventPage + direction;
  const cursor = reset ? "" : direction === 1 ? appState.eventCursor : appState.pageCursors[page];
  if (cursor) params.set("cursor", cursor);
  setEventLoading(true); appState.eventError = ""; setText("event-summary", "Loading");
  try {
    const result = await jsonRequest(`api/events?${params}`, { signal: appState.eventAbort.signal });
    if (requestId !== appState.eventRequest) return;
    appState.eventRows = result.events;
    if (reset) appState.pageCursors = [""];
    appState.eventPage = page; appState.pageCursors[page] = cursor;
    appState.eventCursor = result.next_cursor || ""; appState.eventLoaded = true; appState.appliedFilters = filters;
    renderEvents();
  } catch (error) {
    if (requestId !== appState.eventRequest || error.name === "AbortError") return;
    appState.eventError = error.message; setText("event-summary", error.message);
  } finally { if (requestId === appState.eventRequest) setEventLoading(false); }
}
function connectSocket() {
  const url = endpoint("ws"); url.protocol = location.protocol === "https:" ? "wss:" : "ws:";
  const socket = new WebSocket(url); appState.socket = socket;
  socket.addEventListener("message", (event) => {
    if (appState.socket !== socket) return;
    try { const m = JSON.parse(event.data); if (m.type === "snapshot") applySnapshot(m.data); }
    catch (_) { invalidate(); socket.close(); }
  });
  socket.addEventListener("close", (event) => {
    if (appState.socket !== socket) return;
    appState.socket = null; invalidate(event.code === 1008 ? "ACCESS DENIED" : "STATUS UNAVAILABLE");
    if (event.code !== 1008) setTimeout(connectSocket, 3000);
  });
  socket.addEventListener("error", () => { if (appState.socket === socket) invalidate(); });
}
document.querySelectorAll(".nav-button").forEach((b) => b.addEventListener("click", () => switchView(b.dataset.view)));
byId("keypad-partition").addEventListener("change", (event) => {
  appState.epoch++; appState.keypadPartition = Number(event.target.value);
  appState.lastTransaction = ""; appState.lastResult = null; clearTimeout(appState.commandTimer);
  byId("keypad-result").hidden = true; renderActive();
});
byId("event-filters").addEventListener("submit", (event) => { event.preventDefault(); loadEvents(true); });
byId("events-refresh").addEventListener("click", () => loadEvents(true));
byId("event-more").addEventListener("click", () => loadEvents(false));
byId("event-newer").addEventListener("click", () => loadEvents(false, -1));
byId("diagnostic-filters").addEventListener("submit", (event) => { event.preventDefault(); loadDiagnostics(true); });
byId("diagnostics-refresh").addEventListener("click", () => loadDiagnostics(true, appState.diagnosticFilters.correlation_id || ""));
byId("diagnostic-more").addEventListener("click", () => loadDiagnostics(false));
window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", renderActive);
setInterval(() => {
  if (appState.live && performance.now() - appState.lastUpdate > 10000) { invalidate(); appState.socket?.close(); }
}, 1000);
connectSocket();
