import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { test, expect } from "@playwright/test";

const here = dirname(fileURLToPath(import.meta.url));
const cardSource = readFileSync(join(here, "..", "vista-keypad-card.js"), "utf8");
const ENTITY = "sensor.vista_partition_1_keypad";

async function mount(page, state, attributes = {}) {
  await page.setContent('<!doctype html><html><body><vista-keypad-card id="card"></vista-keypad-card></body></html>');
  await page.evaluate(() => {
    if (!customElements.get("ha-card")) customElements.define("ha-card", class extends HTMLElement {});
  });
  await page.addScriptTag({ content: cardSource });
  await page.evaluate(({ entity, state, attributes }) => {
    const card = document.getElementById("card");
    card.setConfig({ entity, model: "6160cr2", layout: "physical", read_only: false });
    card.hass = {
      states: { [entity]: { state, attributes } },
      callService: async () => {},
    };
  }, { entity: ENTITY, state, attributes });
  await page.evaluate(() => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve))));
}

test("unavailable source ignores retained security attributes and disables controls", async ({ page }) => {
  await mount(page, "unavailable", {
    line_1: "P1   READY       ",
    line_2: "DISARMED        ",
    ready: true,
    armed: false,
    fire_alarm: false,
    control_enabled: true,
    command_topic: "vista128/keypad/1/command",
  });
  const state = await page.evaluate(() => {
    const root = document.getElementById("card").shadowRoot;
    const canvas = root.querySelector("canvas");
    return {
      line1: canvas.dataset.line1,
      line2: canvas.dataset.line2,
      disabled: root.querySelectorAll("button[data-key]:disabled").length,
      buttons: root.querySelectorAll("button[data-key]").length,
      note: root.querySelector("#read-only-note").textContent,
      display: document.getElementById("card")._displayState(),
    };
  });
  expect(state.line1.trim()).toBe("VISTA OFFLINE");
  expect(state.line2.trim()).toBe("STATE OFFLINE");
  expect(state.disabled).toBe(state.buttons);
  expect(state.note).toContain("controls are disabled");
  expect(state.display.ready).toBe(false);
  expect(state.display.controlEnabled).toBe(false);
});

test("custom function-key colors accept normal colors and reject CSS expressions", async ({ page }) => {
  await mount(page, "ready", {
    line_1: "P1   READY       ", line_2: "READY TO ARM    ", ready: true,
  });
  await page.evaluate(() => {
    const card = document.getElementById("card");
    card.setConfig({
      entity: "sensor.vista_partition_1_keypad",
      layout: "physical",
      function_keys: {
        a: { background: "url(https://example.invalid/x)", color: "calc(1px)" },
        b: { background: "#123456", color: "rgb(1, 2, 3)" },
        c: { background: "hsl(20, 30%, 40%)" },
      },
    });
  });
  const styles = await page.evaluate(() => [...document.getElementById("card").shadowRoot.querySelectorAll(".layout-physical-view button.function-key")].map((button) => button.getAttribute("style")));
  expect(styles[0]).not.toContain("url(");
  expect(styles[0]).not.toContain("calc(");
  expect(styles[1]).toContain("#123456");
  expect(styles[1]).toContain("rgb(1, 2, 3)");
  expect(styles[2]).toContain("hsl(20, 30%, 40%)");
});

test("large registries are domain-filtered and bounded in the editor DOM", async ({ page }) => {
  await page.setContent('<!doctype html><html><body><vista-keypad-card-editor id="editor"></vista-keypad-card-editor></body></html>');
  await page.addScriptTag({ content: cardSource });
  const result = await page.evaluate(({ entity }) => {
    const states = {};
    for (let index = 0; index < 5000; index += 1) {
      states[`binary_sensor.unrelated_${index}`] = { state: "off", attributes: { friendly_name: `Unrelated ${index}` } };
    }
    for (let index = 0; index < 250; index += 1) {
      states[`sensor.keypad_${index}`] = { state: "ready", attributes: { friendly_name: `Keypad ${index}` } };
    }
    states[entity] = { state: "ready", attributes: { friendly_name: "Current keypad" } };
    const editor = document.getElementById("editor");
    editor.hass = { states };
    editor.setConfig({ entity });
    const root = editor.shadowRoot;
    return {
      keypadOptions: root.querySelector("#keypad-entity-list").options.length,
      unrelatedIncluded: [...root.querySelector("#keypad-entity-list").options].some((option) => option.value.startsWith("binary_sensor.")),
      htmlLength: root.innerHTML.length,
    };
  }, { entity: ENTITY });
  expect(result.keypadOptions).toBeLessThanOrEqual(101);
  expect(result.unrelatedIncluded).toBe(false);
  expect(result.htmlLength).toBeLessThan(50000);
});
