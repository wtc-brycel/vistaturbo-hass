import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { test, expect } from "@playwright/test";

const here = dirname(fileURLToPath(import.meta.url));
const stylesSource = readFileSync(join(here, "..", "vista-management-styles.js"), "utf8");
const materialSource = readFileSync(join(here, "..", "vista-management-material.js"), "utf8");
const keypadSource = readFileSync(join(here, "..", "vista-keypad-card.js"), "utf8");
const shellSource = readFileSync(join(here, "..", "vista-management-shell.js"), "utf8");
const ENTITY_1 = "sensor.vista_partition_1_keypad";
const ENTITY_2 = "sensor.vista_partition_2_keypad";

async function mount(page, admin = { unlock_configured: true, elevated: true }) {
  await page.setContent('<!doctype html><html><body><vista-management-shell id="shell"></vista-management-shell></body></html>');
  await page.evaluate(() => {
    if (!customElements.get("ha-card")) customElements.define("ha-card", class extends HTMLElement {});
    for (const tag of ["vista-management-app", "vista-partitions-app", "vista-event-log-app"]) {
      if (!customElements.get(tag)) customElements.define(tag, class extends HTMLElement {
        set data(v) { this._data = v; }
        set hass(v) { this._hass = v; }
        set operationHandler(v) { this._handler = v; }
        set adminState(v) { this._admin = v; }
        set activePartition(v) { this._partition = v; }
      });
    }
    window.controlCalls = [];
  });
  await page.addScriptTag({ content: stylesSource });
  await page.addScriptTag({ content: materialSource });
  await page.addScriptTag({ content: keypadSource });
  await page.addScriptTag({ content: shellSource });
  await page.evaluate(({ entity1, entity2, adminState }) => {
    const shell = document.getElementById("shell");
    shell.data = {
      panel: {
        active_partition: 1,
        max_users: 150,
        partitions: [
          { partition: 1, name: "Home", arming_state: "disarmed", ready: true },
          { partition: 2, name: "Garage", arming_state: "disarmed", ready: false },
        ],
      },
      users: [{ user_number: 2 }],
      zones: [{ zone: 1, partition: 1, descriptor: "FRONT DOOR" }],
      admin: adminState,
      keypad: {
        entity: entity1,
        entities: { 1: entity1, 2: entity2 },
        model: "6160cr2",
        layout: "auto",
        read_only: false,
      },
    };
    shell.hass = {
      themes: { darkMode: false },
      user: { id: "admin-id", name: "Administrator" },
      callService: async (...args) => window.controlCalls.push(args),
      states: {
        [entity1]: {
          state: "P1 DISARMED | READY TO ARM",
          attributes: {
            line_1: "DISARMED        ",
            line_2: "READY TO ARM    ",
            ready: true,
            armed: false,
            power: true,
            backlight: true,
            control_enabled: true,
            command_topic: "management-ingress/keypad/1/command",
          },
        },
        [entity2]: {
          state: "P2 DISARMED | NOT READY",
          attributes: {
            line_1: "DISARMED        ",
            line_2: "NOT READY       ",
            ready: false,
            armed: false,
            power: true,
            backlight: true,
            control_enabled: true,
            command_topic: "management-ingress/keypad/2/command",
          },
        },
      },
    };
  }, { entity1: ENTITY_1, entity2: ENTITY_2, adminState: admin });
  await page.evaluate(() => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve))));
}

test("locked shell hides keypad, partitions, tabs, and management content", async ({ page }) => {
  await mount(page, { unlock_configured: true, elevated: false });
  const state = await page.evaluate(() => {
    const shell = document.getElementById("shell");
    const root = shell.shadowRoot;
    return {
      locked: shell.hasAttribute("admin-locked"),
      lockedVisible: getComputedStyle(root.getElementById("locked")).display,
      railVisible: getComputedStyle(root.querySelector(".rail")).display,
      toolbarVisible: getComputedStyle(root.querySelector(".management-bar")).display,
      panelsVisible: getComputedStyle(root.querySelector(".panels")).display,
    };
  });
  expect(state).toEqual({
    locked: true,
    lockedVisible: "flex",
    railVisible: "none",
    toolbarVisible: "none",
    panelsVisible: "none",
  });
});

test("first-run administrator setup is password-only and uses the standard dialog hierarchy", async ({ page }) => {
  await mount(page, { unlock_configured: false, elevated: false });
  await page.evaluate(() => {
    const root = document.getElementById("shell").shadowRoot;
    root.getElementById("locked-unlock").click();
  });
  const state = await page.evaluate(() => {
    const root = document.getElementById("shell").shadowRoot;
    const dialog = root.getElementById("admin-dialog");
    return {
      open: dialog.open,
      title: root.getElementById("admin-title").textContent,
      subtitle: root.getElementById("admin-subtitle").textContent,
      confirmHidden: root.getElementById("admin-confirm-wrap").hidden,
      submit: root.getElementById("admin-submit").textContent,
      bootstrapExists: Boolean(root.getElementById("admin-bootstrap")),
      borderStyle: getComputedStyle(dialog).borderTopStyle,
      radius: parseFloat(getComputedStyle(dialog).borderTopLeftRadius),
    };
  });
  expect(state.open).toBe(true);
  expect(state.title).toBe("Set administrator password");
  expect(state.subtitle).toContain("protects Vista management access");
  expect(state.confirmHidden).toBe(false);
  expect(state.submit).toBe("Save and unlock");
  expect(state.bootstrapExists).toBe(false);
  expect(state.borderStyle).toBe("none");
  expect(state.radius).toBeGreaterThanOrEqual(24);
});

test("persistent rail stays outside Users, Partitions, and Event Log tabs", async ({ page }) => {
  await mount(page);
  const state = await page.evaluate(() => {
    const shell = document.getElementById("shell");
    const r = shell.shadowRoot;
    const keypad = r.getElementById("keypad");
    const panels = [...r.querySelectorAll('[role="tabpanel"]')];
    return {
      locked: shell.hasAttribute("admin-locked"),
      tabs: [...r.querySelectorAll('[role="tab"]')].map((tab) => tab.textContent.trim()),
      selected: r.querySelector('[role="tab"][data-tab="users"]').getAttribute("aria-selected"),
      keypadInRail: r.querySelector(".rail").contains(keypad),
      keypadInAnyPanel: panels.some((panel) => panel.contains(keypad)),
      partitionText: r.getElementById("rail-partitions").innerText,
      userNumber: r.querySelector('[data-tab-panel="users"] vista-management-app')._data.users[0].user_number,
    };
  });
  expect(state).toEqual({
    locked: false,
    tabs: ["Users", "Partitions", "Event Log"],
    selected: "true",
    keypadInRail: true,
    keypadInAnyPanel: false,
    partitionText: expect.stringContaining("Home"),
    userNumber: 2,
  });
});

test("collapsing the rail preserves the same keypad instance and tab switching never remounts it", async ({ page }) => {
  await mount(page);
  const state = await page.evaluate(() => {
    const shell = document.getElementById("shell");
    const r = shell.shadowRoot;
    const before = r.getElementById("keypad");
    const marker = {};
    before.__marker = marker;
    r.querySelector(".collapse").click();
    const collapsed = shell.hasAttribute("rail-collapsed");
    const aria = r.querySelector(".collapse").getAttribute("aria-expanded");
    shell.selectTab("partitions");
    shell.selectTab("event-log");
    shell.selectTab("users");
    const after = r.getElementById("keypad");
    return { collapsed, aria, same: after === before && after.__marker === marker };
  });
  expect(state).toEqual({ collapsed: true, aria: "false", same: true });
});

test("keypad partition selector retargets the same production keypad instance", async ({ page }) => {
  await mount(page);
  const state = await page.evaluate(() => {
    const shell = document.getElementById("shell");
    const root = shell.shadowRoot;
    const keypad = root.getElementById("keypad");
    const marker = {};
    keypad.__marker = marker;
    const select = root.getElementById("keypad-partition");
    select.value = "2";
    select.dispatchEvent(new Event("change", { bubbles: true }));
    return {
      same: root.getElementById("keypad") === keypad && keypad.__marker === marker,
      partition: shell.keypadPartition,
      entity: keypad._config?.entity,
      activeRows: [...root.querySelectorAll(".partition-row.active")].map((row) => row.innerText),
      partitionPanel: root.querySelector('[data-tab-panel="partitions"] vista-partitions-app')._partition,
    };
  });
  expect(state.same).toBe(true);
  expect(state.partition).toBe(2);
  expect(state.entity).toBe(ENTITY_2);
  expect(state.activeRows.join("\n")).toContain("Garage");
  expect(state.partitionPanel).toBe(2);
});

test("selected partition keypad sends immediately to that partition and has no SEND workflow", async ({ page }) => {
  await mount(page);
  await page.evaluate(() => {
    const root = document.getElementById("shell").shadowRoot;
    const select = root.getElementById("keypad-partition");
    select.value = "2";
    select.dispatchEvent(new Event("change", { bubbles: true }));
    const keypad = root.getElementById("keypad").shadowRoot;
    [...keypad.querySelectorAll('button[data-key="1"]')].find((button) => button.offsetParent !== null).click();
  });
  await page.waitForTimeout(50);
  const calls = await page.evaluate(() => window.controlCalls);
  expect(calls).toHaveLength(1);
  expect(JSON.parse(calls[0][2].payload)).toMatchObject({ keys: "1", partition: 2, complete: true });
  expect(await page.evaluate(() => Boolean(document.getElementById("shell").shadowRoot.getElementById("keypad").shadowRoot.querySelector("#keypad-complete")))).toBe(false);
});
