import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { test, expect } from "@playwright/test";

const here = dirname(fileURLToPath(import.meta.url));
const cardSource = readFileSync(join(here, "..", "vista-keypad-card.js"), "utf8");

async function loadCardSource(page) {
  await page.setContent("<!doctype html><html><body></body></html>");
  await page.addScriptTag({ content: cardSource });
}

test("keypad visual editor keeps focused text input across hass updates", async ({ page }) => {
  await loadCardSource(page);
  const result = await page.evaluate(() => {
    const editor = document.createElement("vista-keypad-card-editor");
    document.body.append(editor);
    editor.setConfig({ entity: "sensor.vista_partition_1_keypad", title: "" });
    editor.hass = { states: { "sensor.vista_partition_1_keypad": { state: "ok" } } };

    const title = editor.shadowRoot.querySelector('[data-top="title"]');
    title.focus();
    title.value = "Office";
    title.setSelectionRange(3, 3);

    for (let i = 0; i < 5; i += 1) {
      editor.hass = {
        states: {
          "sensor.vista_partition_1_keypad": { state: `tick-${i}` },
          [`sensor.extra_${i}`]: { state: "ok" },
        },
      };
    }

    return {
      sameNode: editor.shadowRoot.querySelector('[data-top="title"]') === title,
      focused: editor.shadowRoot.activeElement === title,
      value: title.value,
      caret: title.selectionStart,
    };
  });

  expect(result).toEqual({ sameNode: true, focused: true, value: "Office", caret: 3 });
});

test("keypad visual editor keeps focus when Home Assistant echoes config-changed", async ({ page }) => {
  await loadCardSource(page);
  const result = await page.evaluate(() => {
    const editor = document.createElement("vista-keypad-card-editor");
    document.body.append(editor);
    editor.setConfig({ entity: "sensor.vista_partition_1_keypad", title: "Old" });
    editor.hass = { states: {} };
    editor.addEventListener("config-changed", (event) => editor.setConfig(event.detail.config));

    const title = editor.shadowRoot.querySelector('[data-top="title"]');
    title.focus();
    title.value = "New title";
    title.setSelectionRange(4, 4);
    title.dispatchEvent(new Event("change", { bubbles: true }));

    return {
      sameNode: editor.shadowRoot.querySelector('[data-top="title"]') === title,
      focused: editor.shadowRoot.activeElement === title,
      value: title.value,
      caret: title.selectionStart,
    };
  });

  expect(result).toEqual({ sameNode: true, focused: true, value: "New title", caret: 4 });
});

test("keypad editor syncs config in place when hass arrives before setConfig", async ({ page }) => {
  await loadCardSource(page);
  const result = await page.evaluate(() => {
    const editor = document.createElement("vista-keypad-card-editor");
    document.body.append(editor);
    editor.hass = { states: { "sensor.vista_partition_1_keypad": { state: "ok" } } };
    const originalModel = editor.shadowRoot.querySelector('[data-top="model"]');
    editor.setConfig({
      entity: "sensor.vista_partition_1_keypad",
      model: "firstalert",
      sound: { enabled: true },
      haptic: { enabled: true },
    });
    return {
      sameModelNode: editor.shadowRoot.querySelector('[data-top="model"]') === originalModel,
      model: originalModel.value,
      entity: editor.shadowRoot.querySelector('[data-top="entity"]').value,
      sound: editor.shadowRoot.querySelector('[data-sound="enabled"]').checked,
      haptic: editor.shadowRoot.querySelector('[data-haptic="enabled"]').checked,
    };
  });
  expect(result).toEqual({
    sameModelNode: true,
    model: "firstalert",
    entity: "sensor.vista_partition_1_keypad",
    sound: true,
    haptic: true,
  });
});

test("event journal visual editor also preserves focus across hass and config echoes", async ({ page }) => {
  await loadCardSource(page);
  const result = await page.evaluate(() => {
    const editor = document.createElement("vista-event-log-card-editor");
    document.body.append(editor);
    editor.setConfig({ entity: "sensor.vista_event_journal", title: "Journal" });
    editor.hass = { states: { "sensor.vista_event_journal": { state: "1" } } };
    editor.addEventListener("config-changed", (event) => editor.setConfig(event.detail.config));

    const title = editor.shadowRoot.querySelector('[data-field="title"]');
    title.focus();
    title.value = "Event history";
    title.setSelectionRange(5, 5);
    editor.hass = { states: { "sensor.vista_event_journal": { state: "2" } } };
    title.dispatchEvent(new Event("change", { bubbles: true }));

    return {
      sameNode: editor.shadowRoot.querySelector('[data-field="title"]') === title,
      focused: editor.shadowRoot.activeElement === title,
      value: title.value,
      caret: title.selectionStart,
    };
  });

  expect(result).toEqual({ sameNode: true, focused: true, value: "Event history", caret: 5 });
});
