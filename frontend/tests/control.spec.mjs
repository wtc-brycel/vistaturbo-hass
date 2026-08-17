import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { test, expect } from "@playwright/test";

const here = dirname(fileURLToPath(import.meta.url));
const cardSource = readFileSync(join(here, "..", "vista-keypad-card.js"), "utf8");
const ENTITY = "sensor.vista_partition_1_keypad";

async function mount(page, { readOnly = false, controlEnabled = true } = {}) {
  await page.setContent('<!doctype html><html><body><vista-keypad-card id="card"></vista-keypad-card></body></html>');
  await page.evaluate(() => {
    if (!customElements.get("ha-card")) customElements.define("ha-card", class extends HTMLElement {});
    window.controlCalls = [];
  });
  await page.addScriptTag({ content: cardSource });
  await page.evaluate(({ entity, readOnly, controlEnabled }) => {
    const card = document.getElementById("card");
    card.setConfig({ entity, model: "6160", layout: "physical", read_only: readOnly });
    card.hass = {
      themes: { darkMode: false },
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
  }, { entity: ENTITY, readOnly, controlEnabled });
  await page.evaluate(() => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve))));
}

async function clickKey(page, key) {
  await page.evaluate((keyValue) => {
    const card = document.getElementById("card");
    const button = card.shadowRoot.querySelector(`.layout-physical-view button[data-key="${keyValue}"]`);
    button.click();
  }, key);
  await page.waitForTimeout(30);
}

test("enabled keypad publishes non-retained numeric command through Home Assistant", async ({ page }) => {
  await mount(page);
  await clickKey(page, "1");
  const calls = await page.evaluate(() => window.controlCalls);
  expect(calls).toEqual([["mqtt", "publish", {
    topic: "vista128/keypad/1/command",
    payload: "1",
    qos: 0,
    retain: false,
  }]]);
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

test("star and pound publish their literal keypad symbols", async ({ page }) => {
  await mount(page);
  await clickKey(page, "*");
  await clickKey(page, "#");
  const calls = await page.evaluate(() => window.controlCalls.map((entry) => entry[2].payload));
  expect(calls).toEqual(["*", "#"]);
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
