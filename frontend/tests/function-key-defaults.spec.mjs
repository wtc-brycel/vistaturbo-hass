import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { test, expect } from "@playwright/test";

const here = dirname(fileURLToPath(import.meta.url));
const cardSource = readFileSync(join(here, "..", "vista-keypad-card.js"), "utf8");

async function mount(page, model) {
  await page.setContent('<vista-keypad-card id="card"></vista-keypad-card>');
  await page.evaluate(() => {
    if (!customElements.get("ha-card")) customElements.define("ha-card", class extends HTMLElement {});
  });
  await page.addScriptTag({ content: cardSource });
  await page.evaluate((selectedModel) => {
    const entity = "sensor.vista_partition_1_keypad";
    const card = document.getElementById("card");
    card.setConfig({ entity, model: selectedModel, layout: "auto" });
    card.hass = {
      states: {
        [entity]: {
          state: "ready",
          attributes: {
            line_1: "DISARMED READY",
            line_2: "TO ARM",
            ready: true,
            armed: false,
            trouble: false,
            backlight: true,
          },
        },
      },
    };
  }, model);
}

for (const model of ["6160cr2", "6160", "firstalert"]) {
  test(`${model} defaults A-D function keys to literal A B C D`, async ({ page }) => {
    await mount(page, model);
    const labels = await page.evaluate(() => {
      const root = document.getElementById("card").shadowRoot;
      const physical = [...root.querySelectorAll(".layout-physical-view .function-label")].map((el) => el.textContent.trim());
      const compact = [...root.querySelectorAll(".layout-compact-view .function-label")].map((el) => el.textContent.trim());
      return { physical, compact };
    });

    expect(labels.physical).toEqual(["A", "B", "C", "D"]);
    expect(labels.compact).toEqual(["A", "B", "C", "D"]);
  });
}
