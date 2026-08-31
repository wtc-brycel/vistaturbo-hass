(() => {
  const app = document.getElementById("app");
  const candidateBase = new URL(".", window.location.href).pathname;
  const ingressBase = /^\/api\/hassio_ingress\/[A-Za-z0-9._~-]{8,128}\/$/.test(candidateBase)
    ? candidateBase
    : "";

  const api = async (path, options = {}) => {
    const response = await fetch(`.${path}`, {
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
        ...(ingressBase ? { "X-Vista-Ingress-Base": ingressBase } : {}),
        ...(options.headers || {}),
      },
      ...options,
    });
    let body = {};
    try { body = await response.json(); } catch (_) {}
    if (!response.ok) {
      const error = new Error(body.error || `Request failed (${response.status})`);
      error.status = response.status;
      throw error;
    }
    return body;
  };

  const keypadEntity = (partition) => `sensor.vista_partition_${partition}_keypad`;
  let partitionPayload = { authoritative: false, partitions: [], zones: [] };
  let session = { unlock_configured: false, elevated: false };

  const hass = {
    themes: { darkMode: matchMedia("(prefers-color-scheme: dark)").matches },
    user: { id: "", name: "" },
    states: {},
    callService: async (domain, service, data) => {
      if (domain !== "mqtt" || service !== "publish") {
        throw new Error("Unsupported service");
      }
      if (!session.elevated) {
        throw new Error("Vista administrator unlock required");
      }
      const payload = JSON.parse(data.payload || "{}");
      const key = String(payload.keys || "");
      if (key.length !== 1) {
        throw new Error("Only immediate keypad strokes are supported");
      }
      return api("/api/keypad", {
        method: "POST",
        body: JSON.stringify({
          key,
          partition: Number(payload.partition || 1),
          transaction_id: payload.transaction_id || "",
          audit_interaction_id: payload.audit_interaction_id || "",
          complete: payload.complete !== false,
        }),
      });
    },
  };

  const panelFromPayload = (value) => ({
    connection: "connected",
    panel_model: "VISTA-128BPT",
    panel_name: "Vista Turbo",
    active_partition: Number(value.partitions?.[0]?.partition || 1),
    max_users: 150,
    authoritative: value.authoritative === true,
    security_snapshot_complete: value.authoritative === true,
    partitions: value.partitions.map((partition) => ({
      ...partition,
      partition: Number(partition.partition),
      name: partition.name || `Partition ${partition.partition}`,
      arming_state: partition.arming_state || partition.vista_mode,
    })),
  });

  const updateKeypadStates = () => {
    if (!session.elevated) {
      hass.states = {};
      app.hass = hass;
      return;
    }
    const states = {};
    for (const partition of partitionPayload.partitions) {
      const number = Number(partition.partition);
      if (!Number.isInteger(number) || number < 1 || number > 8) continue;
      const keypad = partition?.keypad?.attributes || {};
      states[keypadEntity(number)] = {
        state: partition?.keypad?.state || "Unavailable",
        attributes: {
          ...keypad,
          control_enabled: Boolean(partition?.keypad),
          command_topic: `management-ingress/keypad/${number}/command`,
        },
      };
    }
    hass.states = states;
    app.hass = hass;
  };

  const bindLogProviders = () => {
    const log = app.shadowRoot?.querySelector("vista-event-log-app");
    if (!log) return;
    log.logProvider = (params) => {
      const query = new URLSearchParams(
        Object.entries(params).filter(([, value]) => value !== "" && value != null),
      );
      return api(`/api/logs?${query}`);
    };
    log.auditDetailProvider = (id) => api(`/api/audit/${encodeURIComponent(id)}`);
    log.adminState = session;
  };

  const applyLockedState = () => {
    partitionPayload = { authoritative: false, partitions: [], zones: [] };
    hass.states = {};
    app.data = {
      panel: {
        connection: "connected",
        panel_model: "VISTA-128BPT",
        panel_name: "Vista Turbo",
        active_partition: 1,
        max_users: 150,
        authoritative: false,
        security_snapshot_complete: false,
        partitions: [],
      },
      zones: [],
      users: [],
      operations: [],
      admin: session,
      keypad: {
        entity: keypadEntity(1),
        entities: {},
        model: "6160cr2",
        layout: "auto",
        read_only: true,
      },
    };
    app.hass = hass;
  };

  const applyElevatedState = async () => {
    partitionPayload = await api("/api/partitions");
    const entities = Object.fromEntries(
      partitionPayload.partitions.map((partition) => [
        Number(partition.partition),
        keypadEntity(Number(partition.partition)),
      ]),
    );
    app.data = {
      panel: panelFromPayload(partitionPayload),
      zones: partitionPayload.zones,
      users: [],
      operations: [],
      admin: session,
      keypad: {
        entity: keypadEntity(1),
        entities,
        model: "6160cr2",
        layout: "auto",
        read_only: false,
      },
    };
    updateKeypadStates();
    bindLogProviders();
  };

  const refreshSession = async () => {
    session = await api("/api/session");
    hass.user = {
      id: session.user_id || "",
      name: session.user_name || "",
    };
    if (session.elevated) {
      await applyElevatedState();
    } else {
      applyLockedState();
    }
    return session;
  };

  app.adminHandler = async (action, secret) => {
    if (!ingressBase) {
      throw new Error("Vista management must be opened through Home Assistant ingress");
    }
    if (action === "lock") {
      await api("/api/admin/lock", { method: "POST", body: "{}" });
    } else if (action === "setup") {
      await api("/api/admin/setup", {
        method: "POST",
        body: JSON.stringify({ secret }),
      });
    } else if (action === "unlock") {
      await api("/api/admin/unlock", {
        method: "POST",
        body: JSON.stringify({ secret }),
      });
    } else {
      throw new Error("Unsupported administrator action");
    }
    return refreshSession();
  };

  const handleExpiredElevation = async (error) => {
    if (error?.status !== 403) throw error;
    await refreshSession();
  };

  refreshSession().catch((error) => {
    const banner = document.createElement("div");
    banner.style.padding = "12px";
    banner.style.color = "var(--error-color)";
    banner.textContent = error.message;
    document.body.prepend(banner);
  });

  setInterval(() => {
    if (!session.elevated) return;
    api("/api/partitions")
      .then((value) => {
        partitionPayload = value;
        app.data = {
          ...app.data,
          panel: panelFromPayload(value),
          zones: value.zones,
          admin: session,
        };
        updateKeypadStates();
      })
      .catch(handleExpiredElevation)
      .catch(() => {});
  }, 7000);
})();
