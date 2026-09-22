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


function systemCondition(snapshot) {
  if (!snapshot.panel.connected) {
    return { kind: "offline", title: "PANEL OFFLINE", detail: "Panel TCP connection unavailable", icon: "#i-alert" };
  }

  const partitions = Object.values(snapshot.partitions || {});
  if (partitions.some((partition) => partition.fire_alarm_active)) {
    return { kind: "fire", title: "FIRE ALARM", detail: "One or more partitions report an active fire alarm", icon: "#i-alert" };
  }
  if (partitions.some((partition) =>
    partition.burglary_alarm_active ||
    partition.auxiliary_alarm_active ||
    partition.panic_audible_alarm_active ||
    partition.silent_alarm_active ||
    partition.duress_alarm_active
  )) {
    return { kind: "security", title: "SECURITY ALARM", detail: "One or more partitions report an active security alarm", icon: "#i-alert" };
  }
  if (partitions.some((partition) => partition.supervisory_active)) {
    return { kind: "supervisory", title: "SUPERVISORY", detail: "A supervisory condition is active", icon: "#i-alert" };
  }
  if (
    Number(snapshot.system.active_global_trouble_count || 0) > 0 ||
    snapshot.system.ac_power === false ||
    snapshot.system.battery_low === true
  ) {
    return { kind: "trouble", title: "SYSTEM TROUBLE", detail: "A system trouble condition is active", icon: "#i-alert" };
  }
  if (!snapshot.panel.state_fresh) {
    return { kind: "syncing", title: "SYNCHRONIZING", detail: "Panel connected; waiting for an authoritative state snapshot", icon: "#i-alert" };
  }
  return { kind: "normal", title: "SYSTEM NORMAL", detail: "No active alarm, supervisory, or trouble conditions", icon: "#i-check" };
}

function renderSystemBanner(snapshot) {
  const condition = systemCondition(snapshot);
  const banner = byId("system-banner");
  banner.className = "system-banner state-" + condition.kind;
  byId("system-state-title").textContent = condition.title;
  byId("system-state-detail").textContent = condition.detail;
  byId("system-icon-use").setAttribute("href", condition.icon);

  byId("context-panel").textContent = snapshot.panel.connected ? "ONLINE" : "OFFLINE";
  byId("context-automation").textContent = snapshot.panel.automation_available ? "AVAILABLE" : "UNAVAILABLE";
  byId("context-power").textContent =
    snapshot.system.ac_power === true ? "NORMAL" :
    snapshot.system.ac_power === false ? "LOSS" :
    "UNKNOWN";
  byId("context-freshness").textContent =
    !snapshot.panel.connected ? "UNAVAILABLE" :
    snapshot.panel.state_fresh ? "CURRENT" :
    "SYNCING";
}

function setIndicator(name, className, label) {
  byId("indicator-" + name).className = "indicator-lamp " + className;
  byId("indicator-" + name + "-text").textContent = label;
}

function conditionRow(kind, title, detail, state) {
  const row = node("div", "condition-row " + kind);
  const copy = node("div", "condition-copy");
  copy.append(
    node("div", "condition-title", title),
    node("div", "condition-detail", detail),
  );
  row.append(
    node("span", "condition-accent"),
    copy,
    node("div", "condition-state", state || "ACTIVE"),
  );
  return row;
}

function partitionCondition(partition) {
  if (partition.fire_alarm_active) return { kind: "fire", text: "FIRE ALARM" };
  if (partition.supervisory_active) return { kind: "supervisory", text: "SUPERVISORY" };
  if (
    partition.burglary_alarm_active ||
    partition.auxiliary_alarm_active ||
    partition.panic_audible_alarm_active ||
    partition.silent_alarm_active ||
    partition.duress_alarm_active
  ) {
    return { kind: "security", text: "ALARM" };
  }
  return { kind: "normal", text: "NORMAL" };
}

function eventKind(event) {
  const description = String(event?.description || "").toLowerCase();
  if (/(restore|restoral|normal|cleared)/.test(description)) return "restore";
  if (/(fire|smoke|waterflow|heat alarm)/.test(description)) return "fire";
  if (/(supervis)/.test(description)) return "supervisory";
  if (/(burgl|duress|panic|hold.?up|silent alarm|auxiliary alarm)/.test(description)) return "security";
  if (/(trouble|fail|loss|low bat|battery|tamper|check)/.test(description)) return "trouble";
  return "neutral";
}

function renderOverview(snapshot) {
  byId("overview-sync").textContent = snapshot.synchronizer.last_success_at
    ? "Last reconciliation " + dateTime(snapshot.synchronizer.last_success_at)
    : "No reconciliation recorded";

  setIndicator(
    "power",
    snapshot.system.ac_power === true ? "ok" : snapshot.system.ac_power === false ? "warning" : "unknown",
    snapshot.system.ac_power === true ? "Normal" : snapshot.system.ac_power === false ? "AC loss" : "Unknown",
  );
  setIndicator(
    "battery",
    snapshot.system.battery_low === false ? "ok" : snapshot.system.battery_low === true ? "warning" : "unknown",
    snapshot.system.battery_low === false ? "Normal" : snapshot.system.battery_low === true ? "Low" : "Unknown",
  );
  setIndicator(
    "automation",
    snapshot.panel.automation_available ? "ok" : "off",
    snapshot.panel.automation_available ? "Available" : "Unavailable",
  );
  setIndicator(
    "snapshot",
    snapshot.panel.state_fresh ? "ok" : "warning",
    snapshot.panel.state_fresh ? "Current" : "Synchronizing",
  );

  const conditions = byId("active-conditions");
  clear(conditions);
  let activeCount = 0;

  if (snapshot.system.ac_power === false) {
    conditions.append(conditionRow("trouble", "AC POWER LOSS", "Panel AC power is not present"));
    activeCount += 1;
  }
  if (snapshot.system.battery_low === true) {
    conditions.append(conditionRow("trouble", "SYSTEM BATTERY LOW", "Panel battery condition is active"));
    activeCount += 1;
  }
  if (Number(snapshot.system.active_global_trouble_count || 0) > 0) {
    const count = Number(snapshot.system.active_global_trouble_count || 0);
    conditions.append(conditionRow("trouble", "SYSTEM TROUBLE", count + " active trouble condition" + (count === 1 ? "" : "s")));
    activeCount += 1;
  }

  Object.entries(snapshot.partitions || {}).forEach(([partitionNumber, partition]) => {
    const detail = "Partition " + partitionNumber;
    if (partition.fire_alarm_active) {
      conditions.append(conditionRow("fire", "FIRE ALARM", detail));
      activeCount += 1;
    }
    if (partition.supervisory_active) {
      conditions.append(conditionRow("supervisory", "SUPERVISORY", detail));
      activeCount += 1;
    }
    if (partition.burglary_alarm_active) {
      conditions.append(conditionRow("security", "BURGLARY ALARM", detail));
      activeCount += 1;
    }
    if (partition.auxiliary_alarm_active) {
      conditions.append(conditionRow("security", "AUXILIARY ALARM", detail));
      activeCount += 1;
    }
    if (partition.panic_audible_alarm_active) {
      conditions.append(conditionRow("security", "AUDIBLE PANIC", detail));
      activeCount += 1;
    }
    if (partition.silent_alarm_active) {
      conditions.append(conditionRow("security", "SILENT ALARM", detail));
      activeCount += 1;
    }
    if (partition.duress_alarm_active) {
      conditions.append(conditionRow("security", "DURESS", detail));
      activeCount += 1;
    }
  });

  if (!activeCount) {
    const current = snapshot.panel.state_fresh;
    conditions.append(
      conditionRow(
        current ? "normal" : "trouble",
        current ? "SYSTEM NORMAL" : "STATE NOT CURRENT",
        current ? "No active conditions" : "Authoritative panel snapshot is not complete",
        current ? "NORMAL" : "PENDING",
      ),
    );
  }
  byId("condition-summary").textContent = activeCount ? activeCount + " ACTIVE" : "NORMAL";

  const latest = byId("latest-event");
  clear(latest);
  const event = snapshot.last_event;
  if (!event) {
    latest.className = "latest-event empty-state";
    latest.textContent = "No event received.";
    byId("latest-event-code").textContent = "--";
  } else {
    latest.className = "latest-event " + eventKind(event);
    byId("latest-event-code").textContent = text(event.event_code, "--");
    latest.append(node("div", "latest-event-title", text(event.description, "Unknown event")));
    if (event.descriptor) latest.append(node("div", "latest-event-descriptor", event.descriptor));

    const meta = [
      event.panel_timestamp ? panelDateTime(event.panel_timestamp) : null,
      event.partition ? "PARTITION " + event.partition : null,
      event.zone ? "ZONE " + String(event.zone).padStart(3, "0") : null,
      event.user ? "USER " + String(event.user).padStart(3, "0") : null,
    ].filter(Boolean).join("  ·  ");
    latest.append(node("div", "latest-event-meta", meta));
  }

  const partitions = byId("partition-grid");
  clear(partitions);
  Object.entries(snapshot.partitions || {}).forEach(([partitionNumber, partition]) => {
    const condition = snapshot.panel.state_fresh
      ? partitionCondition(partition)
      : { kind: "unknown", text: "STATE STALE" };

    const row = node("div", "table-row");
    row.append(
      node("div", "partition-number", "Partition " + partitionNumber),
      node("div", "partition-mode", text(partition.vista_mode).replaceAll("_", " ")),
      node("div", "", partition.ready ? "YES" : "NO"),
      node("div", "state-label " + condition.kind, condition.text),
    );
    partitions.append(row);
  });
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
  byId("user-name").textContent =
    snapshot.user?.display_name || snapshot.user?.name || snapshot.user?.id || "";
}

function journalHeader(snapshot) {
  if (!snapshot.journal.enabled) return "Journal disabled";
  const dump = snapshot.journal.last_dump_at
    ? " · Last panel dump " + dateTime(snapshot.journal.last_dump_at)
    : "";
  return number(snapshot.journal.count) + " rows retained" + dump;
}

function applySnapshot(snapshot) {
  appState.snapshot = snapshot;
  renderHeader(snapshot);
  renderSystemBanner(snapshot);
  renderOverview(snapshot);
  renderDiagnostics(snapshot);
  renderKeypad(snapshot);
  byId("journal-header-meta").textContent = journalHeader(snapshot);
  if (byId("diagnostic-version")) {
    byId("diagnostic-version").textContent = "Vista Turbo " + snapshot.app.version;
  }
  if (document.querySelector(".nav-button.active")?.dataset.view === "events") {
    renderEvents();
  }
}

async function loadInitialSnapshot() {
  const response = await fetch(endpoint("api/snapshot"), { cache: "no-store" });
  if (!response.ok) throw new Error("Could not load Vista Turbo status");
  applySnapshot(await response.json());
}

function switchView(view) {
  document.querySelectorAll(".view").forEach((element) => {
    element.classList.toggle("active", element.id === "view-" + view);
  });
  document.querySelectorAll(".nav-button").forEach((element) => {
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
      const row = node("div", "event-row " + eventKind(event));
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


function setSocketState(state, label) {
  const element = byId("socket-state");
  element.className = "socket-state " + state;
  const textNode = Array.from(element.childNodes).find((item) => item.nodeType === Node.TEXT_NODE);
  if (textNode) textNode.nodeValue = label;
  else element.append(document.createTextNode(label));
}

function connectSocket() {
  const url = endpoint("ws");
  url.protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const socket = new WebSocket(url);
  appState.socket = socket;

  socket.addEventListener("open", () => {
    setSocketState("online", "Ingress live");
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
    setSocketState("warning", "Reconnecting");
    window.setTimeout(connectSocket, 3000);
  });

  socket.addEventListener("error", () => {
    setSocketState("offline", "Ingress unavailable");
  });
}

document.querySelectorAll(".nav-button").forEach((button) => {
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

byId("events-refresh").addEventListener("click", () => {
  loadEvents(true).catch(showEventError);
});

byId("event-more").addEventListener("click", () => {
  loadEvents(false).catch(showEventError);
});

loadInitialSnapshot()
  .catch(() => {
    setSocketState("offline", "Ingress unavailable");
    byId("system-banner").className = "system-banner state-offline";
    byId("system-state-title").textContent = "STATUS UNAVAILABLE";
    byId("system-state-detail").textContent = "Could not load Vista Turbo runtime state";
  })
  .finally(connectSocket);
