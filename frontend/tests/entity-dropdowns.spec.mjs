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
  await page.addScriptTag({ content: cardSource });
  await page.evaluate(() => {
    const hass = {
      states: {
        "sensor.vista_partition_1_keypad": {
          state: "ready",
          attributes: { friendly_name: "VISTA Partition 1 Keypad" },
        },
        "sensor.vista_event_journal": {
          state: "1",
          attributes: { friendly_name: "VISTA Event Journal" },
        },
        "sensor.other_sensor": {
          state: "idle",
          attributes: { friendly_name: "Another Sensor" },
        },
        "binary_sensor.house_alarm": {
          state: "off",
          attributes: { friendly_name: "House Alarm" },
        },
        "switch.aux_alarm": {
          state: "off",
          attributes: { friendly_name: "Aux Alarm" },
        },
      },
    };

    const keypad = document.getElementById("keypad-editor");
    keypad.hass = hass;
    keypad.setConfig({
      entity: "sensor.vista_partition_1_keypad",
      model: "6160cr2",
      layout: "auto",
      sound: { alarm_entity: "binary_sensor.house_alarm" },
    });

    const eventEditor = document.getElementById("event-editor");
    eventEditor.hass = hass;
    eventEditor.setConfig({ entity: "sensor.vista_event_journal", rows: 20 });
  });
}

test("visual editors render entity selections as dropdowns", async ({ page }) => {
  await loadEditors(page);

  const state = await page.evaluate(() => {
    const keypad = document.getElementById("keypad-editor").shadowRoot;
    const eventEditor = document.getElementById("event-editor").shadowRoot;
    const keypadEntity = keypad.querySelector('[data-top="entity"]');
    const alarmEntity = keypad.querySelector('[data-sound="alarm_entity"]');
    const auxEntity = keypad.querySelector('[data-sound="aux_entity"]');
    const eventEntity = eventEditor.querySelector('[data-field="entity"]');

    return {
      keypadTag: keypadEntity.tagName,
      alarmTag: alarmEntity.tagName,
      auxTag: auxEntity.tagName,
      eventTag: eventEntity.tagName,
      keypadValue: keypadEntity.value,
      alarmValue: alarmEntity.value,
      eventValue: eventEntity.value,
      keypadOptions: [...keypadEntity.options].map((option) => option.value),
      alarmOptions: [...alarmEntity.options].map((option) => option.value),
      auxOptions: [...auxEntity.options].map((option) => option.value),
      eventOptions: [...eventEntity.options].map((option) => option.value),
      keypadText: keypadEntity.textContent,
    };
  });

  expect(state.keypadTag).toBe("SELECT");
  expect(state.alarmTag).toBe("SELECT");
  expect(state.auxTag).toBe("SELECT");
  expect(state.eventTag).toBe("SELECT");
  expect(state.keypadValue).toBe("sensor.vista_partition_1_keypad");
  expect(state.alarmValue).toBe("binary_sensor.house_alarm");
  expect(state.eventValue).toBe("sensor.vista_event_journal");

  expect(state.keypadOptions).toContain("sensor.other_sensor");
  expect(state.keypadOptions).not.toContain("binary_sensor.house_alarm");
  expect(state.eventOptions).toContain("sensor.other_sensor");
  expect(state.eventOptions).not.toContain("switch.aux_alarm");

  expect(state.alarmOptions).toContain("binary_sensor.house_alarm");
  expect(state.alarmOptions).toContain("switch.aux_alarm");
  expect(state.auxOptions[0]).toBe("");
  expect(state.keypadText).toContain("VISTA Partition 1 Keypad (sensor.vista_partition_1_keypad)");
});

test("changing an entity dropdown emits the selected entity id", async ({ page }) => {
  await loadEditors(page);

  const result = await page.evaluate(() => {
    const keypad = document.getElementById("keypad-editor");
    return new Promise((resolve) => {
      keypad.addEventListener("config-changed", (event) => resolve(event.detail.config), { once: true });
      const select = keypad.shadowRoot.querySelector('[data-top="entity"]');
      select.value = "sensor.other_sensor";
      select.dispatchEvent(new Event("change", { bubbles: true }));
    });
  });

  expect(result.entity).toBe("sensor.other_sensor");
});
