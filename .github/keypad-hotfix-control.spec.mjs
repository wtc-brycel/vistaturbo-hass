import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { test, expect } from "@playwright/test";

const here = dirname(fileURLToPath(import.meta.url));
const cardSource = readFileSync(join(here, "..", "vista-keypad-card.js"), "utf8");
const ENTITY = "sensor.vista_partition_1_keypad";

async function mount(page, { readOnly = false, controlEnabled = true, user = null } = {}) {
  await page.setContent('<!doctype html><html><body><vista-keypad-card id="card"></vista-keypad-card></body></html>');
  await page.evaluate(() => {
    if (!customElements.get("ha-card")) customElements.define("ha-card", class extends HTMLElement {});
    window.controlCalls = [];
  });
  await page.addScriptTag({ content: cardSource });
  await page.evaluate(({ entity, readOnly, controlEnabled, user }) => {
    const card = document.getElementById("card");
    card.setConfig({ entity, model: "6160", layout: "physical", read_only: readOnly });
    card.hass = {
      themes: { darkMode: false },
      user,
      callService: async (...args) => { window.controlCalls.push(args); },
      states: {
        [entity]: {
          state: "P1 DISARMED | READY TO ARM",
          attributes: {
            line_1: "P1   DISARMED   ",
            line_2: "READY TO ARM    ",
            ready: true,
            armed: false,
            trouble: false,
            backlight: true,
            control_enabled: controlEnabled,
            command_topic: controlEnabled ? "vista128/keypad/1/command" : null,
          },
        },
      },
    };
  }, { entity: ENTITY, readOnly, controlEnabled, user });
  await page.evaluate(() => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve))));
}

async function clickKey(page, key) {
  await page.evaluate((keyValue) => {
    const card = document.getElementById("card");
    const button = card.shadowRoot.querySelector(`.layout-physical-view button[data-key="${keyValue}"]`);
    button.click();
  }, key);
  await page.waitForTimeout(20);
}

test("enabled keypad publishes each physical keypress immediately through Home Assistant", async ({ page }) => {
  await mount(page);
  await clickKey(page, "1");
  const calls = await page.evaluate(() => window.controlCalls);
  expect(calls).toHaveLength(1);
  expect(calls[0][0]).toBe("mqtt");
  expect(calls[0][1]).toBe("publish");
  expect(JSON.parse(calls[0][2].payload)).toMatchObject({
    keys: "1",
    partition: 1,
    source: "ha_frontend",
    action: "keypad_sequence",
    complete: true,
  });
  expect(calls[0][2].transaction_id).toBeUndefined();
  expect(JSON.parse(calls[0][2].payload).transaction_id).toEqual(expect.any(String));
  expect(calls[0][2].qos).toBe(1);
  expect(calls[0][2].retain).toBe(false);
});

test("keypad has no synthetic SEND or finish-command control", async ({ page }) => {
  await mount(page);
  const result = await page.evaluate(() => {
    const root = document.getElementById("card").shadowRoot;
    return {
      sendButton: Boolean(root.querySelector("#keypad-complete")),
      text: root.textContent,
    };
  });
  expect(result.sendButton).toBe(false);
  expect(result.text).not.toContain("Press SEND");
  expect(result.text).not.toContain("finish the command");
});

test("signed-in actor metadata travels with each immediate keypad keypress", async ({ page }) => {
  await mount(page, { user: { id: "alice-id", name: "Alice" } });
  await clickKey(page, "1");
  const payload = await page.evaluate(() => JSON.parse(window.controlCalls[0][2].payload));
  expect(payload).toMatchObject({
    actor_id: "alice-id",
    actor_name: "Alice",
    partition: 1,
    source: "ha_frontend",
    action: "keypad_sequence",
    keys: "1",
    complete: true,
  });
  expect(payload.transaction_id).toEqual(expect.any(String));
});

test("rapid keypad entry publishes every key immediately and in order", async ({ page }) => {
  await mount(page);
  await page.evaluate(() => {
    const root = document.getElementById("card").shadowRoot;
    for (const key of ["1", "2", "3", "4", "#"]) {
      root.querySelector(`.layout-physical-view button[data-key="${key}"]`).click();
    }
  });
  await page.waitForTimeout(80);
  const payloads = await page.evaluate(() => window.controlCalls.map((entry) => JSON.parse(entry[2].payload)));
  expect(payloads.map((payload) => payload.keys)).toEqual(["1", "2", "3", "4", "#"]);
  expect(payloads.every((payload) => payload.complete === true)).toBe(true);
  expect(new Set(payloads.map((payload) => payload.transaction_id)).size).toBe(5);
});

test("slow entry never waits for an inactivity boundary", async ({ page }) => {
  await mount(page);
  for (const [index, key] of ["1", "2", "3", "4", "5", "6"].entries()) {
    await clickKey(page, key);
    expect(await page.evaluate(() => window.controlCalls.length)).toBe(index + 1);
    await page.waitForTimeout(700);
  }
  const payloads = await page.evaluate(() => window.controlCalls.map((entry) => JSON.parse(entry[2].payload)));
  expect(payloads.map((payload) => payload.keys)).toEqual(["1", "2", "3", "4", "5", "6"]);
  expect(payloads.every((payload) => payload.complete === true)).toBe(true);
});

test("keypress DOM event does not expose the entered digit", async ({ page }) => {
  await mount(page);
  await page.evaluate(() => {
    window.keyEvents = [];
    document.getElementById("card").addEventListener("vista-keypad-key", (event) => window.keyEvents.push(event.detail));
  });
  await clickKey(page, "7");
  const events = await page.evaluate(() => window.keyEvents);
  expect(events).toHaveLength(1);
  expect(events[0].action).toBe("keypress");
  expect(events[0].key).toBeUndefined();
});

test("star and pound publish their literal keypad symbols immediately", async ({ page }) => {
  await mount(page);
  await clickKey(page, "*");
  await clickKey(page, "#");
  const calls = await page.evaluate(() => window.controlCalls.map((entry) => JSON.parse(entry[2].payload)));
  expect(calls.map((payload) => payload.keys)).toEqual(["*", "#"]);
  expect(calls.every((payload) => payload.action === "keypad_sequence" && payload.complete === true)).toBe(true);
});

test("A-D function keys remain inert instead of colliding with KS encodings", async ({ page }) => {
  await mount(page);
  await clickKey(page, "A");
  const calls = await page.evaluate(() => window.controlCalls);
  expect(calls).toEqual([]);
  const note = await page.evaluate(() => document.getElementById("card").shadowRoot.getElementById("read-only-note").textContent);
  expect(note).toContain("not mapped");
});

test("card stays read-only by default", async ({ page }) => {
  await mount(page, { readOnly: true });
  await clickKey(page, "2");
  expect(await page.evaluate(() => window.controlCalls)).toEqual([]);
});

test("bridge-side control gate prevents publish even if card toggle is enabled", async ({ page }) => {
  await mount(page, { readOnly: false, controlEnabled: false });
  await clickKey(page, "3");
  expect(await page.evaluate(() => window.controlCalls)).toEqual([]);
  const note = await page.evaluate(() => document.getElementById("card").shadowRoot.getElementById("read-only-note").textContent);
  expect(note).toContain("Bridge keypad control");
});

test("visual editor exposes keypad input toggle", async ({ page }) => {
  await page.setContent('<!doctype html><html><body><vista-keypad-card-editor id="editor"></vista-keypad-card-editor></body></html>');
  await page.addScriptTag({ content: cardSource });
  await page.evaluate(() => {
    const editor = document.getElementById("editor");
    editor.setConfig({ entity: "sensor.vista_partition_1_keypad", read_only: true });
    editor.hass = { states: {} };
  });
  const exists = await page.evaluate(() => Boolean(document.getElementById("editor").shadowRoot.querySelector("[data-control-toggle]")));
  expect(exists).toBe(true);
});
