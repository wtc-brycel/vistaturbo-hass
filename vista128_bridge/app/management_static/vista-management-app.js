(() => {
  const AUTH = {
    master: "Master",
    manager: "Manager",
    operator_a: "Operator A",
    operator_b: "Operator B",
    operator_c: "Operator C",
    duress: "Duress",
  };
  const AUTH_KEYS = Object.keys(AUTH);
  const esc = (v) => String(v ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
  const pad = (v) => String(v ?? "").padStart(3, "0");
  const yn = (v) => v === true ? "On" : v === false ? "Off" : "Unknown";
  const svg = {
    search: '<svg viewBox="0 0 24 24"><path d="M9.5 3a6.5 6.5 0 1 0 4 11.6l6.3 6.3 1.2-1.2-6.4-6.3A6.5 6.5 0 0 0 9.5 3Zm0 2a4.5 4.5 0 1 1 0 9 4.5 4.5 0 0 1 0-9Z"/></svg>',
    plus: '<svg viewBox="0 0 24 24"><path d="M11 5h2v6h6v2h-6v6h-2v-6H5v-2h6V5Z"/></svg>',
    chev: '<svg viewBox="0 0 24 24"><path d="m9 5 7 7-7 7 1.4 1.4L18.8 12 10.4 3.6 9 5Z"/></svg>',
  };

  const tpl = document.createElement("template");
  tpl.innerHTML = `
    <style>${window.VISTA_MANAGEMENT_STYLES || ""}</style>
    <style>
      .workspace { display:block; max-width:none; margin:0; }
      .users-area { grid-area:auto; }
    </style>
    <div class="workspace">
      <section class="surface users-surface users-area">
        <div class="surface-head">
          <h2>Users</h2>
          <span class="count" id="count"></span>
          <button class="ha-button filled add" id="add">${svg.plus}<span class="label">Add user</span></button>
        </div>
        <div class="users-layout">
          <div class="user-browser">
            <div class="users-toolbar">
              <label class="search-box">${svg.search}<input id="search" type="search" placeholder="Search users" aria-label="Search users"></label>
            </div>
            <div class="filter-row" id="filters"></div>
            <div class="user-list" id="users"></div>
          </div>
          <aside class="detail-panel" id="detail"></aside>
        </div>
      </section>
    </div>
    <dialog id="dialog"><div class="dialog-shell" id="dialog-shell"></div></dialog>
  `;

  class VistaManagementApp extends HTMLElement {
    constructor() {
      super();
      this.attachShadow({ mode: "open" }).append(tpl.content.cloneNode(true));
      this._d = { panel: null, users: [], operations: [] };
      this._selected = null;
      this._q = "";
      this._filter = "all";
      this._hass = null;
      this._handler = null;
      this._bind();
    }

    set data(v) {
      v = v || {};
      this._d = {
        panel: v.panel || null,
        users: Array.isArray(v.users) ? v.users : [],
        operations: Array.isArray(v.operations) ? v.operations : [],
        max_users: Number(v.max_users || v.panel?.max_users || 0) || null,
      };
      if (!this._d.users.some((u) => u.user_number === this._selected)) {
        this._selected = this._d.users[0]?.user_number ?? null;
      }
      this._render();
    }
    get data() { return this._d; }

    set hass(v) {
      this._hass = v || null;
      this.toggleAttribute("dark", !!v?.themes?.darkMode);
    }
    get hass() { return this._hass; }

    set operationHandler(v) { this._handler = typeof v === "function" ? v : null; }
    get operationHandler() { return this._handler; }

    _bind() {
      const r = this.shadowRoot;
      r.getElementById("search").oninput = (e) => {
        this._q = e.target.value;
        this._renderUsers();
      };
      r.getElementById("filters").onclick = (e) => {
        const b = e.target.closest("[data-filter]");
        if (!b) return;
        this._filter = b.dataset.filter;
        this._renderFilters();
        this._renderUsers();
      };
      r.getElementById("users").onclick = (e) => {
        const b = e.target.closest("[data-user]");
        if (!b) return;
        this._selected = Number(b.dataset.user);
        this._renderUsers();
        this._renderDetail();
      };
      r.getElementById("add").onclick = () => this._addDialog();
      r.getElementById("detail").onclick = (e) => {
        const action = e.target.closest("[data-action]")?.dataset.action;
        const user = this._user();
        if (!action || !user) return;
        if (action === "code") this._codeDialog(user);
        if (action === "access") this._accessDialog(user);
        if (action === "label") this._labelDialog(user);
        if (action === "delete" || action === "retry") this._deleteDialog(user);
      };
      r.getElementById("dialog").onclick = (e) => {
        if (e.target === r.getElementById("dialog")) r.getElementById("dialog").close();
      };
    }

    _parts() { return Array.isArray(this._d.panel?.partitions) ? this._d.panel.partitions : []; }
    _part(n) {
      const p = this._parts().find((x) => Number(x.partition) === Number(n));
      return p ? `P${n} ${p.name || ""}`.trim() : `P${n}`;
    }
    _op(n) { return [...this._d.operations].reverse().find((x) => Number(x.user_number) === Number(n)); }
    _user() { return this._d.users.find((x) => Number(x.user_number) === Number(this._selected)); }

    _render() {
      this._renderFilters();
      this._renderUsers();
      this._renderDetail();
      this.shadowRoot.getElementById("count").textContent = this._d.max_users
        ? `${this._d.users.length} of ${this._d.max_users}`
        : String(this._d.users.length);
    }

    _renderFilters() {
      this.shadowRoot.getElementById("filters").innerHTML = [
        ["all", "All"],
        ...this._parts().map((p) => [`p${p.partition}`, `P${p.partition} ${p.name || ""}`.trim()]),
      ].map(([id, text]) => `<button class="filter-chip${this._filter === id ? " active" : ""}" data-filter="${id}" aria-pressed="${this._filter === id}">${esc(text)}</button>`).join("");
    }

    _primary(u) {
      if (!Array.isArray(u.partitions) || !u.partitions.length) return "Unknown";
      const a = u.partitions.find((p) => Number(p.partition) === Number(u.origin_partition)) || u.partitions[0];
      return AUTH[a.authority] || a.authority || "Unknown";
    }

    _renderUsers() {
      const q = this._q.trim().toLowerCase();
      const list = this._d.users.filter((u) => {
        if (this._filter.startsWith("p") && (!Array.isArray(u.partitions) || !u.partitions.some((p) => `p${p.partition}` === this._filter))) return false;
        return !q || [pad(u.user_number), u.local_name || "", this._primary(u), ...(u.partitions || []).map((p) => `p${p.partition}`)]
          .join(" ").toLowerCase().includes(q);
      });
      const el = this.shadowRoot.getElementById("users");
      el.innerHTML = list.length ? list.map((u) => {
        const op = this._op(u.user_number);
        const unavailable = u.data_status === "unavailable" || op?.state === "unavailable";
        let pill = "";
        if (unavailable) pill = '<span class="mini-pill unavailable">Unavailable</span>';
        else if (op?.state === "pending") pill = '<span class="mini-pill pending">Pending</span>';
        else if (op?.state === "failed") pill = '<span class="mini-pill failed">Failed</span>';
        else if (op?.state === "confirmed") pill = '<span class="mini-pill confirmed">Confirmed</span>';
        else if (u.partitions?.some((p) => p.authority === "duress")) pill = '<span class="mini-pill duress">Duress</span>';
        const parts = Array.isArray(u.partitions) ? u.partitions.map((p) => `P${p.partition}`).join(" ") : "—";
        return `<button class="user-row${u.user_number === this._selected ? " selected" : ""}" data-user="${u.user_number}">
          <span class="user-number">${pad(u.user_number)}</span>
          <span class="user-main"><span class="user-name"><span class="label">${esc(u.local_name || `User ${pad(u.user_number)}`)}</span></span><span class="user-secondary">${esc(unavailable ? "Panel data unavailable" : `${this._primary(u)} · ${parts}`)}</span></span>
          <span class="row-status">${pill}</span>${svg.chev}
        </button>`;
      }).join("") : '<div class="empty">No users match</div>';
    }

    _renderDetail() {
      const el = this.shadowRoot.getElementById("detail");
      const u = this._user();
      if (!u) { el.innerHTML = '<div class="empty">Select a user</div>'; return; }
      const op = this._op(u.user_number);
      const unavailable = u.data_status === "unavailable" || op?.state === "unavailable";
      let alert = "";
      if (unavailable) {
        alert = '<div class="alert warning"><div class="alert-main"><div class="alert-title">User data unavailable</div><div class="alert-detail">Panel fields remain unknown until an authoritative read succeeds.</div></div></div>';
      } else if (op?.state === "pending") {
        alert = '<div class="alert info"><div class="alert-main"><div class="alert-title">Operation pending</div></div></div>';
      } else if (op?.state === "failed") {
        alert = `<div class="alert error"><div class="alert-main"><div class="alert-title">${op.kind === "delete_user" ? "Delete user" : "Operation"} failed</div><div class="alert-detail">${esc(op.message || "Panel rejected the operation.")}</div></div>${op.kind === "delete_user" ? '<button class="alert-action" data-action="retry">Retry</button>' : ""}</div>`;
      }
      const table = !unavailable && Array.isArray(u.partitions)
        ? `<div class="section-label">Partition authority</div><table class="authority-table"><thead><tr><th>Partition</th><th>Authority</th><th>Global Arm</th></tr></thead><tbody>${u.partitions.map((a) => `<tr><td>${esc(this._part(a.partition))}${a.partition === u.origin_partition ? '<div class="origin-mark">Origin</div>' : ""}</td><td>${esc(AUTH[a.authority] || a.authority || "Unknown")}</td><td>${yn(a.global_arm)}</td></tr>`).join("")}</tbody></table>`
        : "";
      const disabled = unavailable ? "disabled" : "";
      el.innerHTML = `<div class="detail-head"><h2>User ${pad(u.user_number)}</h2><div class="detail-identity">${esc(u.local_name || "Unnamed")}</div></div>${alert}<div class="detail-body"><dl class="kv"><dt>Security code</dt><dd>${unavailable || u.code_status === "unknown" ? "Unknown" : u.code_status === "set" ? "Set" : esc(u.code_status || "Unknown")}</dd><dt>Origin partition</dt><dd>${unavailable || u.origin_partition == null ? "Unknown" : esc(this._part(u.origin_partition))}</dd><dt>Group bypass</dt><dd>${yn(unavailable ? null : u.group_bypass)}</dd><dt>Access group</dt><dd>${unavailable || u.access_group == null ? "Unknown" : u.access_group === 0 ? "0 · None" : u.access_group}</dd><dt>RF button zone</dt><dd>${unavailable ? "Unknown" : u.rf_button_zone == null ? "None" : u.rf_button_zone}</dd></dl>${table}</div><div class="detail-actions"><button class="ha-button" data-action="code" ${disabled}>Change code</button><button class="ha-button" data-action="access" ${disabled}>Change access</button><button class="ha-button" data-action="label">Edit label</button><button class="ha-button danger" data-action="delete" ${disabled}>Delete user</button></div>`;
    }

    _dialog(title, body, primary, onSubmit, danger = false) {
      const dialog = this.shadowRoot.getElementById("dialog");
      let old = this.shadowRoot.getElementById("dialog-shell");
      const shell = old.cloneNode(false);
      old.replaceWith(shell);
      shell.innerHTML = `<div class="dialog-head"><h3>${esc(title)}</h3><button class="icon-button" data-close aria-label="Close">✕</button></div><div class="dialog-scroll">${body}</div><div class="dialog-actions"><button class="ha-button" data-close>Cancel</button><button class="ha-button ${danger ? "danger filled" : "filled"}" data-primary>${esc(primary)}</button></div>`;
      shell.querySelectorAll("[data-close]").forEach((b) => b.onclick = () => dialog.close());
      shell.onchange = (e) => {
        if (e.target.matches("[data-access]")) e.target.closest(".partition-edit")?.classList.toggle("assigned", e.target.checked || e.target.disabled);
      };
      shell.querySelector("[data-primary]").onclick = () => {
        if (onSubmit(shell) !== false) {
          shell.querySelectorAll("[data-code]").forEach((x) => x.value = "");
          dialog.close();
        }
      };
      dialog.showModal();
      return shell;
    }

    _codeFields() {
      return `<div class="field-row"><div class="field"><label>New 4-digit code</label><input class="input" data-code="new" type="password" inputmode="numeric" maxlength="4" autocomplete="new-password"></div><div class="field"><label>Re-enter code</label><input class="input" data-code="confirm" type="password" inputmode="numeric" maxlength="4" autocomplete="new-password"><div class="field-error" data-code-error></div></div></div>`;
    }

    _readCode(shell) {
      const a = shell.querySelector('[data-code="new"]').value.replace(/\D/g, "");
      const b = shell.querySelector('[data-code="confirm"]').value.replace(/\D/g, "");
      if (!/^\d{4}$/.test(a)) { shell.querySelector("[data-code-error]").textContent = "Enter exactly four digits."; return null; }
      if (a !== b) { shell.querySelector("[data-code-error]").textContent = "Codes do not match."; return null; }
      return a;
    }

    _codeDialog(u) {
      this._dialog(`Change code · User ${pad(u.user_number)}`, this._codeFields(), "Set code", (s) => {
        const code = this._readCode(s);
        if (!code) return false;
        this._submit({ type: "change_code", user_number: u.user_number, code });
        return true;
      });
    }

    _labelDialog(u) {
      this._dialog(`Edit label · User ${pad(u.user_number)}`, `<div class="field"><label>Local label</label><input class="input" data-label maxlength="80" value="${esc(u.local_name || "")}" placeholder="Optional"></div>`, "Save", (s) => {
        this._submit({ type: "update_local_label", user_number: u.user_number, local_name: s.querySelector("[data-label]").value.trim() || null });
        return true;
      });
    }

    _deleteDialog(u) {
      this._dialog(`Delete user ${pad(u.user_number)}?`, `<p>This removes the security code and authorization from every assigned partition.</p><p class="help">${esc(u.local_name || `User ${pad(u.user_number)}`)}${u.origin_partition ? ` · Origin ${esc(this._part(u.origin_partition))}` : ""}</p>`, "Delete", () => {
        this._submit({ type: "delete_user", user_number: u.user_number, origin_partition: u.origin_partition });
        return true;
      }, true);
    }

    _accessRows(assignments, origin) {
      const map = new Map((assignments || []).map((a) => [Number(a.partition), a]));
      return this._parts().map((p) => {
        const a = map.get(Number(p.partition));
        const checked = !!a;
        return `<div class="partition-edit${checked ? " assigned" : ""}" data-access-row="${p.partition}"><div class="partition-edit-head"><input type="checkbox" data-access ${checked ? "checked" : ""} ${Number(p.partition) === Number(origin) ? "disabled" : ""}><strong>${esc(this._part(p.partition))}</strong>${Number(p.partition) === Number(origin) ? '<span class="origin-pill">Origin</span>' : ""}</div><div class="partition-edit-body"><div class="field" style="margin:0"><label>Authority</label><select class="select" data-auth>${AUTH_KEYS.map((k) => `<option value="${k}" ${a?.authority === k ? "selected" : ""}>${AUTH[k]}</option>`).join("")}</select></div><label class="switch-row">Global Arm <input type="checkbox" data-global ${a?.global_arm ? "checked" : ""}></label></div></div>`;
      }).join("");
    }

    _attrs(u) {
      return `<div class="field-row"><label class="switch-row">Group bypass <input type="checkbox" data-bypass ${u?.group_bypass ? "checked" : ""}></label><div class="field"><label>Access group</label><select class="select" data-group>${Array.from({ length: 9 }, (_, i) => `<option value="${i}" ${Number(u?.access_group || 0) === i ? "selected" : ""}>${i}${i === 0 ? " · None" : ""}</option>`).join("")}</select></div></div><div class="field"><label>RF button zone</label><input class="input" data-rf inputmode="numeric" maxlength="3" value="${u?.rf_button_zone ?? ""}" placeholder="None"></div>`;
    }

    _readAccess(s) {
      return [...s.querySelectorAll("[data-access-row]")]
        .filter((r) => r.querySelector("[data-access]").checked || r.querySelector("[data-access]").disabled)
        .map((r) => ({
          partition: Number(r.dataset.accessRow),
          authority: r.querySelector("[data-auth]").value,
          global_arm: r.querySelector("[data-global]").checked,
        }));
    }

    _accessDialog(u) {
      const body = `<div class="inline-note">Changing authority or partition access requires deleting the user from the origin partition and re-adding it. A new 4-digit code is required.</div>${this._codeFields()}${this._attrs(u)}<div class="section-label">Partition access</div><div class="partition-editor">${this._accessRows(u.partitions, u.origin_partition)}</div>`;
      this._dialog(`Change access · User ${pad(u.user_number)}`, body, "Replace user", (s) => {
        const code = this._readCode(s);
        if (!code) return false;
        this._submit({
          type: "replace_user",
          user_number: u.user_number,
          origin_partition: u.origin_partition,
          code,
          group_bypass: s.querySelector("[data-bypass]").checked,
          access_group: Number(s.querySelector("[data-group]").value),
          rf_button_zone: Number(s.querySelector("[data-rf]").value) || null,
          partitions: this._readAccess(s),
        });
        return true;
      });
    }

    _addDialog() {
      const origin = this._parts()[0]?.partition ?? 1;
      const body = `<div class="field-row"><div class="field"><label>User number</label><input class="input" data-number inputmode="numeric" maxlength="3"></div><div class="field"><label>Local label</label><input class="input" data-label maxlength="80" placeholder="Optional"></div></div>${this._codeFields()}<div class="field"><label>Origin partition</label><select class="select" data-origin>${this._parts().map((p) => `<option value="${p.partition}">${esc(this._part(p.partition))}</option>`).join("")}</select></div>${this._attrs({})}<div class="section-label">Partition access</div><div class="partition-editor">${this._accessRows([{ partition: origin, authority: "operator_a", global_arm: false }], origin)}</div>`;
      const s = this._dialog("Add user", body, "Add user", (sh) => {
        const n = Number(sh.querySelector("[data-number]").value);
        const code = this._readCode(sh);
        if (!Number.isInteger(n) || n < 1 || (this._d.max_users && n > this._d.max_users) || !code) return false;
        this._submit({
          type: "add_user",
          user_number: n,
          local_name: sh.querySelector("[data-label]").value.trim() || null,
          code,
          origin_partition: Number(sh.querySelector("[data-origin]").value),
          group_bypass: sh.querySelector("[data-bypass]").checked,
          access_group: Number(sh.querySelector("[data-group]").value),
          rf_button_zone: Number(sh.querySelector("[data-rf]").value) || null,
          partitions: this._readAccess(sh),
        });
        return true;
      });
      s.querySelector("[data-origin]").onchange = (e) => {
        const n = Number(e.target.value);
        s.querySelectorAll("[data-access-row]").forEach((r) => {
          const c = r.querySelector("[data-access]");
          c.disabled = Number(r.dataset.accessRow) === n;
          if (c.disabled) c.checked = true;
        });
      };
    }

    _submit(op) {
      if (this._handler) this._handler({ ...op });
      else {
        const safe = { ...op };
        if ("code" in safe) delete safe.code;
        this.dispatchEvent(new CustomEvent("vista-management-operation", { detail: safe, bubbles: true, composed: true }));
      }
    }
  }

  if (!customElements.get("vista-management-app")) customElements.define("vista-management-app", VistaManagementApp);
})();
