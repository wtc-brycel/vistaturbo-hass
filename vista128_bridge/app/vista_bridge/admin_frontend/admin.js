"use strict";

const appState = {
  snapshot: null,
  socket: null,
  eventRows: [],
  eventCursor: "",
  keypadPartition: null,
  keypadConfigSignature: "",
};

const byId = (id) => document.getElementById(id);
const endpoint = (path) => new URL(path, document.baseURI);

function text(value, fallback = "Unknown") {
  if (value === null || value === undefined || value === "") return fallback;
  return String(value);
}

function yesNo(value) {
  if (value === null || value === undefined) return "Unknown";
  return value ? "Yes" : "No";
}

function dateTime(value) {
  if (!value) return "Never";
  const parsed = new Date(value);
  if (!Number.isNaN(parsed.getTime())) return parsed.toLocaleString();
  return String(value).replace("T", " ");
}

function panelDateTime(value) {
  const match = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})/.exec(String(value || ""));
  if (!match) return text(value, "Unknown");
  return `${match[2]}/${match[3]}/${match[1]} ${match[4]}:${match[5]}`;
}

function number(value) {
  return new Intl.NumberFormat().format(Number(value || 0));
}

function setStatusPill(element, label, className) {
  element.textContent = label;
  element.className = `status-pill ${className}`;
}

function clear(element) {
  while (element.firstChild) element.removeChild(element.firstChild);
}

function node(tag, className, value) {
  const element = document.createElement(tag);
  if (className) element.className = className;
  if (value !== undefined) element.textContent = value;
  return element;
}

function summaryCard(label, value, detail = "") {
  const card = node("div", "summary-card");
  card.append(
    node("div", "summary-label", label),
    node("div", "summary-value", value),
  );
  if (detail) card.append(node("div", "summary-detail", detail));
  return card;
}

function renderOverview(snapshot) {
  const summary = byId("overview-summary");
  clear(summary);
  summary.append(
    summaryCard(
      "Panel",
      snapshot.panel.connected ? "Online" : "Offline",
      snapshot.panel.state_fresh ? "State snapshot current" : "State snapshot incomplete",
    ),
    summaryCard(
      "Automation",
      snapshot.panel.automation_available ? "Available" : "Unavailable",
      text(snapshot.panel.automation_availability_source, "Unknown source"),
    ),
    summaryCard(
      "Journal",
      snapshot.journal.enabled ? number(snapshot.journal.count) : "Disabled",
      snapshot.journal.last_dump_at
        ? `Last panel dump ${dateTime(snapshot.journal.last_dump_at)}`
        : "No panel history dump recorded",
    ),
    summaryCard(
      "System",
      snapshot.system.active_global_alarm_count ? "Alarm" : "Normal",
      `AC: ${yesNo(snapshot.system.ac_power)} | Battery low: ${yesNo(snapshot.system.battery_low)}`,
    ),
  );

  const grid = byId("partition-grid");
  clear(grid);
  Object.entries(snapshot.partitions || {}).forEach(([partitionNumber, partition]) => {
    const card = node("div", "partition-card");
    const top = node("div", "partition-top");
    top.append(
      node("div", "partition-name", `Partition ${partitionNumber}`),
      node("div", "partition-mode", text(partition.vista_mode)),
    );
    const flags = node("div", "partition-flags");
    const ready = node("span", `flag ${partition.ready ? "ready" : ""}`, partition.ready ? "READY" : "NOT READY");
    flags.append(ready);
    if (partition.fire_alarm_active) flags.append(node("span", "flag alarm", "FIRE"));
    if (partition.supervisory_active) flags.append(node("span", "flag alarm", "SUPERVISORY"));
    if (partition.burglary_alarm_active) flags.append(node("span", "flag alarm", "BURGLARY"));
    if (partition.auxiliary_alarm_active) flags.append(node("span", "flag alarm", "AUX"));
    if (!partition.has_active_alarm) flags.append(node("span", "flag", "NO ACTIVE ALARM"));
    card.append(top, flags);
    grid.append(card);
  });

  const latest = byId("latest-event");
  clear(latest);
  const event = snapshot.last_event;
  if (!event) {
    latest.className = "surface empty-state";
    latest.textContent = "No event received.";
  } else {
    latest.className = "surface";
    const descriptor = event.descriptor ? ` - ${event.descriptor}` : "";
    latest.append(
      node("div", "latest-title", `${event.description} [${event.event_code}]${descriptor}`),
      node(
        "div",
        "latest-meta",
        [
          event.panel_timestamp ? panelDateTime(event.panel_timestamp) : null,
          event.partition ? `Partition ${event.partition}` : null,
          event.zone ? `Zone ${String(event.zone).padStart(3, "0")}` : null,
          event.user ? `User ${String(event.user).padStart(3, "0")}` : null,
        ].filter(Boolean).join(" | "),
      ),
    );
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
  );
}

function buildIngressHass(snapshot, partition) {
  const entityId = "sensor.vista_ingress_keypad";
  const keypad = snapshot.keypads?.[String(partition)] || null;
  const available = Boolean(keypad?.available);
  const state = available ? text(keypad.state, "blank") : "unavailable";
  const attributes = keypad
    ? {
        ...keypad,
        control_enabled: Boolean(snapshot.control.keypad_available),
        command_topic: `vista/ingress/keypad/${partition}/command`,
      }
    : {};

  return {
    states: {
      [entityId]: { state, attributes },
    },
    themes: {
      darkMode: window.matchMedia?.("(prefers-color-scheme: dark)")?.matches ?? false,
    },
    user: {
      id: snapshot.user?.id || "",
      name: snapshot.user?.display_name || snapshot.user?.name || "",
      display_name: snapshot.user?.display_name || snapshot.user?.name || "",
    },
    callService: async (domain, service, serviceData) => {
      if (domain !== "mqtt" || service !== "publish") {
        throw new Error("Unsupported ingress keypad service");
      }
      const payload = JSON.parse(String(serviceData?.payload || "{}"));
      const response = await fetch(endpoint("api/keypad"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          partition,
          key: payload.keys,
          transaction_id: payload.transaction_id,
          audit_interaction_id: payload.audit_interaction_id,
        }),
      });
      const result = await response.json();
      if (!response.ok || !result.accepted) {
        throw new Error(result.status || "Keypad request rejected");
      }
      return result;
    },
  };
}

function renderKeypad(snapshot) {
  const select = byId("keypad-partition");
  const partitions = Object.keys(snapshot.keypads || {}).map(Number).sort((a, b) => a - b);
  if (!partitions.length) {
    clear(select);
    select.disabled = true;
    byId("keypad-warning").hidden = false;
    byId("keypad-warning").textContent = "No keypad partitions are configured.";
    return;
  }

  if (!appState.keypadPartition || !partitions.includes(appState.keypadPartition)) {
    appState.keypadPartition = partitions[0];
  }

  const existing = Array.from(select.options).map((option) => Number(option.value));
  if (JSON.stringify(existing) !== JSON.stringify(partitions)) {
    clear(select);
    partitions.forEach((partition) => {
      const option = document.createElement("option");
      option.value = String(partition);
      option.textContent = `Partition ${partition}`;
      select.append(option);
    });
  }
  select.disabled = false;
  select.value = String(appState.keypadPartition);

  const keypad = snapshot.keypads[String(appState.keypadPartition)];
  const warning = byId("keypad-warning");
  if (!snapshot.control.keypad_available) {
    warning.hidden = false;
    warning.textContent = snapshot.control.keypad_enabled
      ? "Keypad input is currently unavailable. The display remains read-only until the panel automation interface is available."
      : "Keypad control is disabled in the Vista Turbo App options. The display is read-only.";
  } else if (!keypad?.available) {
    warning.hidden = false;
    warning.textContent = "The keypad display is not current. Input is disabled until a fresh display is available.";
  } else {
    warning.hidden = true;
  }

  const card = byId("ingress-keypad");
  const configurationSignature = JSON.stringify([
    appState.keypadPartition,
    Boolean(snapshot.control.keypad_available),
  ]);
  if (configurationSignature !== appState.keypadConfigSignature) {
    appState.keypadConfigSignature = configurationSignature;
    card.setConfig({
      entity: "sensor.vista_ingress_keypad",
      model: "6160cr2",
      layout: "auto",
      case_color: "auto",
      show_card_background: false,
      read_only: !snapshot.control.keypad_available,
      sound: { enabled: false },
      haptic: { enabled: false },
    });
  }
  card.hass = buildIngressHass(snapshot, appState.keypadPartition);
}

function renderHeader(snapshot) {
  const summary = snapshot.panel.connected
    ? `${snapshot.panel.host}:${snapshot.panel.port} | ${snapshot.panel.state_fresh ? "state current" : "state synchronizing"}`
    : `${snapshot.panel.host}:${snapshot.panel.port} | disconnected`;
  byId("panel-summary").textContent = summary;
  byId("user-name").textContent =
    snapshot.user?.display_name || snapshot.user?.name || snapshot.user?.id || "";

  if (!snapshot.panel.connected) {
    setStatusPill(byId("live-state"), "Offline", "offline");
  } else if (!snapshot.panel.state_fresh) {
    setStatusPill(byId("live-state"), "Synchronizing", "warning");
  } else {
    setStatusPill(byId("live-state"), "Online", "online");
  }
}

function applySnapshot(snapshot) {
  appState.snapshot = snapshot;
  renderHeader(snapshot);
  renderOverview(snapshot);
  renderDiagnostics(snapshot);
  renderKeypad(snapshot);
}

async function loadInitialSnapshot() {
  const response = await fetch(endpoint("api/snapshot"), { cache: "no-store" });
  if (!response.ok) throw new Error("Could not load Vista Turbo status");
  applySnapshot(await response.json());
}

function switchView(view) {
  document.querySelectorAll(".view").forEach((element) => {
    element.classList.toggle("active", element.id === `view-${view}`);
  });
  document.querySelectorAll(".tab").forEach((element) => {
    element.classList.toggle("active", element.dataset.view === view);
  });
  if (view === "events" && !appState.eventRows.length) {
    loadEvents(true).catch(showEventError);
  }
}

function eventMeta(event) {
  const pieces = [];
  if (event.partition) pieces.push(`P${event.partition}`);
  if (event.zone) pieces.push(`Z${String(event.zone).padStart(3, "0")}`);
  if (event.user) pieces.push(`U${String(event.user).padStart(3, "0")}`);
  return pieces.join(" | ");
}

function renderEvents() {
  const list = byId("event-list");
  clear(list);
  if (!appState.eventRows.length) {
    list.append(node("div", "event-empty", "No events match the current filters."));
  } else {
    appState.eventRows.forEach((event) => {
      const row = node("div", "event-row");
      const timeNode = node("div", "event-time", event.panel_timestamp ? panelDateTime(event.panel_timestamp) : dateTime(event.received_at));
      const codeNode = node("div", "event-code", text(event.event_code, "??"));
      const detail = node("div", "");
      const description = node("div", "event-description", text(event.description, "Unknown event"));
      if (event.descriptor) {
        description.append(" ", node("span", "event-descriptor", event.descriptor));
      }
      detail.append(description);
      const meta = eventMeta(event);
      if (meta) detail.append(node("div", "event-meta", meta));
      row.append(
        timeNode,
        codeNode,
        detail,
        node("div", "event-source", text(event.source, "unknown")),
      );
      list.append(row);
    });
  }

  byId("event-summary").textContent = appState.snapshot?.journal?.enabled
    ? `${number(appState.snapshot.journal.count)} rows retained | showing ${number(appState.eventRows.length)}`
    : "Event journal is disabled.";
  byId("event-more").hidden = !appState.eventCursor;
}

async function loadEvents(reset) {
  const params = new URLSearchParams();
  params.set("limit", "50");
  const query = byId("event-search").value.trim();
  const partition = byId("event-partition").value;
  const source = byId("event-source").value;
  if (query) params.set("q", query);
  if (partition && partition !== "0") params.set("partition", partition);
  if (source) params.set("source", source);
  if (!reset && appState.eventCursor) params.set("cursor", appState.eventCursor);

  const response = await fetch(endpoint(`api/events?${params.toString()}`), { cache: "no-store" });
  if (!response.ok) throw new Error("Could not load event journal");
  const payload = await response.json();

  if (reset) appState.eventRows = [];
  appState.eventRows.push(...(Array.isArray(payload.events) ? payload.events : []));
  appState.eventCursor = payload.next_cursor || "";
  renderEvents();
}

function showEventError(error) {
  byId("event-summary").textContent = error?.message || "Could not load event journal.";
}

function connectSocket() {
  const url = endpoint("ws");
  url.protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const socket = new WebSocket(url);
  appState.socket = socket;

  socket.addEventListener("open", () => {
    if (!appState.snapshot) setStatusPill(byId("live-state"), "Connected", "unknown");
  });

  socket.addEventListener("message", (event) => {
    try {
      const message = JSON.parse(event.data);
      if (message.type === "snapshot" && message.data) applySnapshot(message.data);
    } catch (_) {
      // Invalid server messages are ignored; the next snapshot can recover.
    }
  });

  socket.addEventListener("close", () => {
    if (appState.socket === socket) appState.socket = null;
    setStatusPill(byId("live-state"), "Reconnecting", "warning");
    window.setTimeout(connectSocket, 3000);
  });
}

document.querySelectorAll(".tab").forEach((button) => {
  button.addEventListener("click", () => switchView(button.dataset.view));
});

byId("keypad-partition").addEventListener("change", (event) => {
  appState.keypadPartition = Number(event.currentTarget.value);
  appState.keypadConfigSignature = "";
  if (appState.snapshot) renderKeypad(appState.snapshot);
});

byId("event-filters").addEventListener("submit", (event) => {
  event.preventDefault();
  loadEvents(true).catch(showEventError);
});
byId("events-refresh").addEventListener("click", () => loadEvents(true).catch(showEventError));
byId("event-more").addEventListener("click", () => loadEvents(false).catch(showEventError));

loadInitialSnapshot()
  .catch(() => setStatusPill(byId("live-state"), "Unavailable", "offline"))
  .finally(connectSocket);
