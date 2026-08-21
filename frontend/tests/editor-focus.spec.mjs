import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { test, expect } from "@playwright/test";

const here = dirname(fileURLToPath(import.meta.url));
const cardSource = readFileSync(join(here, "..", "vista-keypad-card.js"), "utf8");

async function loadEditors(page) {
  await page.setContent(`<!doctype html><html><body>
    <vista-keypad-card-editor id="keypad-editor"></vista-keypad-card-editor>
    <vista-event-log-card-editor id="event-editor"></vista-event-log-card-editor>
  </body></html>`);
  await page.evaluate(() => {
    if (!customElements.get("ha-card")) customElements.define("ha-card", class extends HTMLElement {});
  });
  await page.addScriptTag({ content: cardSource });
  await page.evaluate(() => {
    const keypad = document.getElementById("keypad-editor");
    keypad.setConfig({
      entity: "sensor.vista_partition_1_keypad",
      model: "6160cr2",
      layout: "auto",
      title: "",
    });
    keypad.hass = {
      states: {
        "sensor.vista_partition_1_keypad": { state: "ready", attributes: {} },
      },
    };

    const eventEditor = document.getElementById("event-editor");
    eventEditor.setConfig({
      entity: "sensor.vista_event_journal",
      rows: 20,
      partition: 0,
    });
    eventEditor.hass = {
      states: {
        "sensor.vista_event_journal": { state: "10", attributes: {} },
      },
    };
  });
}

test("keypad editor keeps text focus and draft value across hass refreshes", async ({ page }) => {
  await loadEditors(page);

  await page.evaluate(() => {
    document.getElementById("keypad-editor").shadowRoot.querySelector("#title").focus();
  });
  await page.keyboard.type("Garage keypad");

  await page.evaluate(() => {
    const editor = document.getElementById("keypad-editor");
    for (let i = 0; i < 5; i += 1) {
      editor.hass = {
        states: {
          "sensor.vista_partition_1_keypad": { state: `update-${i}`, attributes: { sequence: i } },
        },
      };
    }
  });

  const result = await page.evaluate(() => {
    const editor = document.getElementById("keypad-editor");
    const input = editor.shadowRoot.querySelector("#title");
    return {
      value: input.value,
      focused: editor.shadowRoot.activeElement === input,
    };
  });
  expect(result.value).toBe("Garage keypad");
  expect(result.focused).toBe(true);
});

test("keypad editor does not replace a control when Home Assistant echoes emitted config", async ({ page }) => {
  await loadEditors(page);

  const result = await page.evaluate(() => {
    const editor = document.getElementById("keypad-editor");
    const input = editor.shadowRoot.querySelector("#title");
    let emitted = null;
    editor.addEventListener("config-changed", (event) => { emitted = event.detail.config; }, { once: true });
    input.focus();
    input.value = "Office keypad";
    input.dispatchEvent(new Event("change", { bubbles: true }));
    const afterEmit = editor.shadowRoot.querySelector("#title");
    editor.setConfig(emitted);
    const afterEcho = editor.shadowRoot.querySelector("#title");
    return {
      sameAfterEmit: input === afterEmit,
      sameAfterEcho: input === afterEcho,
      focused: editor.shadowRoot.activeElement === input,
      value: afterEcho.value,
    };
  });

  expect(result.sameAfterEmit).toBe(true);
  expect(result.sameAfterEcho).toBe(true);
  expect(result.focused).toBe(true);
  expect(result.value).toBe("Office keypad");
});

test("event journal editor also keeps focus across hass refreshes", async ({ page }) => {
  await loadEditors(page);

  const result = await page.evaluate(() => {
    const editor = document.getElementById("event-editor");
    const input = editor.shadowRoot.querySelector('[data-field="title"]');
    input.focus();
    input.value = "Alarm history";
    for (let i = 0; i < 5; i += 1) {
      editor.hass = {
        states: {
          "sensor.vista_event_journal": { state: String(20 + i), attributes: { sequence: i } },
        },
      };
    }
    return {
      value: editor.shadowRoot.querySelector('[data-field="title"]').value,
      sameNode: input === editor.shadowRoot.querySelector('[data-field="title"]'),
      focused: editor.shadowRoot.activeElement === input,
    };
  });

  expect(result.value).toBe("Alarm history");
  expect(result.sameNode).toBe(true);
  expect(result.focused).toBe(true);
});
