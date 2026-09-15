import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { test, expect } from "@playwright/test";

const here = dirname(fileURLToPath(import.meta.url));
const stylesSource = readFileSync(join(here, "..", "vista-management-styles.js"), "utf8");
const appSource = readFileSync(join(here, "..", "vista-management-app.js"), "utf8");

const panel = {
  max_users: 150,
  partitions: [
    { partition: 1, name: "Home", arming_state: "disarmed", ready: true },
    { partition: 2, name: "Garage", arming_state: "disarmed", ready: false },
    { partition: 3, name: "Office", arming_state: "armed_stay", ready: true },
    { partition: 4, name: "Workshop", arming_state: "disarmed", ready: true },
  ],
};
const users = [
  { user_number: 2, local_name: "Primary Master", code_status: "set", origin_partition: 1, group_bypass: true, access_group: 0, rf_button_zone: null, partitions: [
    { partition: 1, authority: "master", global_arm: true },
    { partition: 2, authority: "master", global_arm: true },
    { partition: 3, authority: "manager", global_arm: false },
  ]},
  { user_number: 12, local_name: "Cleaner", code_status: "set", origin_partition: 1, group_bypass: false, access_group: 3, rf_button_zone: null, partitions: [
    { partition: 1, authority: "operator_c", global_arm: false },
  ]},
  { user_number: 21, local_name: "Security", code_status: "set", origin_partition: 1, group_bypass: true, access_group: 1, rf_button_zone: 117, partitions: [
    { partition: 1, authority: "operator_a", global_arm: true },
    { partition: 2, authority: "operator_a", global_arm: true },
    { partition: 3, authority: "operator_b", global_arm: false },
    { partition: 4, authority: "operator_b", global_arm: false },
  ]},
  { user_number: 44, local_name: null, code_status: "set", origin_partition: 4, group_bypass: false, access_group: 0, rf_button_zone: null, partitions: [
    { partition: 4, authority: "operator_a", global_arm: false },
  ]},
  { user_number: 73, local_name: "State unavailable example", code_status: "unknown", origin_partition: null, group_bypass: null, access_group: null, rf_button_zone: null, partitions: null, data_status: "unavailable" },
];
const operations = [
  { kind: "change_code", user_number: 12, state: "pending" },
  { kind: "delete_user", user_number: 44, state: "failed", message: "Panel rejected the operation." },
  { kind: "read_user", user_number: 73, state: "unavailable" },
];

async function mount(page, { width = 1000, dark = false, handler = true } = {}) {
  await page.setViewportSize({ width, height: width < 600 ? 844 : 900 });
  await page.setContent('<!doctype html><html><body><vista-management-app id="app"></vista-management-app></body></html>');
  await page.evaluate(() => { window.managementOps = []; window.safeEvents = []; });
  await page.addScriptTag({ content: stylesSource });
  await page.addScriptTag({ content: appSource });
  await page.evaluate(({ panelData, usersData, operationsData, darkMode, withHandler }) => {
    const app = document.getElementById("app");
    app.data = { panel: panelData, users: usersData, operations: operationsData, max_users: 150 };
    app.hass = { themes: { darkMode } };
    if (withHandler) app.operationHandler = (operation) => window.managementOps.push(operation);
    app.addEventListener("vista-management-operation", (event) => window.safeEvents.push(event.detail));
  }, { panelData: panel, usersData: users, operationsData: operations, darkMode: dark, withHandler: handler });
  await page.evaluate(() => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve))));
}

async function selectUser(page, n) {
  await page.evaluate((number) => document.getElementById("app").shadowRoot.querySelector(`[data-user="${number}"]`).click(), n);
}
async function action(page, a) {
  await page.evaluate((name) => document.getElementById("app").shadowRoot.querySelector(`[data-action="${name}"]`).click(), a);
}

test("Users component contains management content only", async ({ page }) => {
  await mount(page);
  const state = await page.evaluate(() => {
    const r = document.getElementById("app").shadowRoot;
    return {
      users: Boolean(r.querySelector(".users-surface")),
      keypad: Boolean(r.querySelector("vista-keypad-card,.keypad-surface")),
      partitions: Boolean(r.querySelector(".partition-list")),
      fakeShell: Boolean(r.querySelector(".sidebar,.ha-sidebar,.header,[role=tablist]")),
    };
  });
  expect(state).toEqual({ users: true, keypad: false, partitions: false, fakeShell: false });
});

test("authority and Global Arm remain partition-specific", async ({ page }) => {
  await mount(page);
  const rows = await page.evaluate(() => [...document.getElementById("app").shadowRoot.querySelectorAll(".authority-table tbody tr")].map((row) => [...row.cells].map((cell) => cell.innerText.trim())));
  expect(rows).toEqual([
    ["P1 Home\nOrigin", "Master", "On"],
    ["P2 Garage", "Master", "On"],
    ["P3 Office", "Manager", "Off"],
  ]);
});

test("unavailable user stays unknown and blocks panel mutations", async ({ page }) => {
  await mount(page);
  await selectUser(page, 73);
  const state = await page.evaluate(() => {
    const r = document.getElementById("app").shadowRoot;
    return {
      text: r.getElementById("detail").innerText,
      code: r.querySelector("[data-action=code]").disabled,
      access: r.querySelector("[data-action=access]").disabled,
      label: r.querySelector("[data-action=label]").disabled,
    };
  });
  expect(state.text).toContain("User data unavailable");
  expect((state.text.match(/Unknown/g) || []).length).toBeGreaterThanOrEqual(5);
  expect(state).toMatchObject({ code: true, access: true, label: false });
});

test("code change requires exactly four digits and write-only fallback strips it", async ({ page }) => {
  await mount(page, { handler: false });
  await selectUser(page, 12);
  await action(page, "code");
  await page.evaluate(() => {
    const r = document.getElementById("app").shadowRoot;
    r.querySelector('[data-code="new"]').value = "8642";
    r.querySelector('[data-code="confirm"]').value = "8642";
    r.querySelector("[data-primary]").click();
  });
  expect(await page.evaluate(() => window.safeEvents)).toEqual([{ type: "change_code", user_number: 12 }]);
});

test("access changes use replace-user semantics with a new code", async ({ page }) => {
  await mount(page);
  await selectUser(page, 21);
  await action(page, "access");
  expect(await page.evaluate(() => document.getElementById("app").shadowRoot.getElementById("dialog-shell").innerText)).toContain("new 4-digit code is required");
  await page.evaluate(() => {
    const r = document.getElementById("app").shadowRoot;
    r.querySelector('[data-code="new"]').value = "2468";
    r.querySelector('[data-code="confirm"]').value = "2468";
    r.querySelector('[data-access-row="4"] [data-access]').click();
    r.querySelector("[data-primary]").click();
  });
  const op = (await page.evaluate(() => window.managementOps))[0];
  expect(op.type).toBe("replace_user");
  expect(op.code).toBe("2468");
  expect(op.partitions.map((p) => p.partition)).toEqual([1, 2, 3]);
});

test("failed delete retries through confirmation", async ({ page }) => {
  await mount(page);
  await selectUser(page, 44);
  await action(page, "retry");
  expect(await page.evaluate(() => document.getElementById("app").shadowRoot.querySelector(".dialog-head h3").textContent)).toBe("Delete user 044?");
});

test("responsive dark mode remains usable", async ({ page }) => {
  await mount(page, { width: 390, dark: true });
  expect(await page.evaluate(() => document.getElementById("app").hasAttribute("dark"))).toBe(true);
  expect(await page.evaluate(() => Boolean(document.getElementById("app").shadowRoot.querySelector(".users-surface")))).toBe(true);
});
