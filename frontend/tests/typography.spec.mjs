import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { test, expect } from "@playwright/test";

const here = dirname(fileURLToPath(import.meta.url));
const cardSource = readFileSync(join(here, "..", "vista-keypad-card.js"), "utf8");
const ENTITY = "sensor.vista_partition_1_keypad";

async function mountCard(page, { width = 390, layout = "auto" } = {}) {
  await page.setViewportSize({ width: Math.max(430, width + 40), height: 900 });
  await page.setContent(`<!doctype html><html><head><meta charset="utf-8"><style>
    html,body{margin:0;padding:0;background:#eee}
    #stage{width:${width}px;margin:0 auto}
    vista-keypad-card{display:block;width:100%}
  </style></head><body><div id="stage"><vista-keypad-card id="card"></vista-keypad-card></div></body></html>`);

  await page.evaluate(() => {
    if (!customElements.get("ha-card")) customElements.define("ha-card", class extends HTMLElement {});
  });
  await page.addScriptTag({ content: cardSource });

  await page.evaluate(({ entity, layout }) => {
    const card = document.getElementById("card");
    card.setConfig({
      entity,
      model: "6160cr2",
      layout,
      case_color: "dark",
      read_only: true,
    });
    card.hass = {
      themes: { darkMode: true },
      states: {
        [entity]: {
          state: "P1 DISARMED / READY TO ARM",
          attributes: {
            line_1: "P1    DISARMED   ",
            line_2: "BYPAS-RDY TO ARM",
            ready: true,
            armed: false,
            trouble: false,
            backlight: true,
            power: false,
            fire_alarm: false,
            silenced: false,
            supervisory: false,
          },
        },
      },
    };
  }, { entity: ENTITY, layout });

  await page.evaluate(() => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve))));
}

test("compact 6160CR-2 does not horizontally crush keypad numerals", async ({ page }) => {
  await mountCard(page, { width: 390 });

  const typography = await page.evaluate(() => {
    const root = document.getElementById("card").shadowRoot;
    const compact = root.querySelector(".layout-compact-view");
    const number = compact.querySelector(".number-main");
    const legend = compact.querySelector(".number-legend");
    const functionLabel = compact.querySelector(".function-label");
    const indicator = compact.querySelector(".compact-indicator-label");
    const numberStyle = getComputedStyle(number);
    const legendStyle = getComputedStyle(legend);
    const functionStyle = getComputedStyle(functionLabel);
    const indicatorStyle = getComputedStyle(indicator);
    return {
      numberTransform: numberStyle.transform,
      numberWeight: numberStyle.fontWeight,
      numberFamily: numberStyle.fontFamily,
      legendWeight: legendStyle.fontWeight,
      legendStyle: legendStyle.fontStyle,
      functionWeight: functionStyle.fontWeight,
      indicatorWeight: indicatorStyle.fontWeight,
    };
  });

  expect(typography.numberTransform).toBe("none");
  expect(typography.numberWeight).toBe("400");
  expect(typography.numberFamily).toContain("Arial Narrow");
  expect(typography.legendWeight).toBe("600");
  expect(typography.legendStyle).toBe("italic");
  expect(typography.functionWeight).toBe("700");
  expect(typography.indicatorWeight).toBe("700");
});

test("physical 6160CR-2 uses the same keypad print typography", async ({ page }) => {
  await mountCard(page, { width: 700, layout: "physical" });

  const typography = await page.evaluate(() => {
    const root = document.getElementById("card").shadowRoot;
    const physical = root.querySelector(".layout-physical-view");
    const numberStyle = getComputedStyle(physical.querySelector(".number-main"));
    const legendStyle = getComputedStyle(physical.querySelector(".number-legend"));
    const statusStyle = getComputedStyle(physical.querySelector(".status-cr2 .led-row"));
    return {
      numberTransform: numberStyle.transform,
      numberFamily: numberStyle.fontFamily,
      legendWeight: legendStyle.fontWeight,
      statusWeight: statusStyle.fontWeight,
    };
  });

  expect(typography.numberTransform).toBe("none");
  expect(typography.numberFamily).toContain("Arial Narrow");
  expect(typography.legendWeight).toBe("600");
  expect(typography.statusWeight).toBe("600");
});

test("LCD renderer keeps a canonical 6x8 cell pitch and device-pixel snapping", () => {
  expect(cardSource).toContain("const dot = Math.min(charW / 6, lineH / 8);");
  expect(cardSource).toContain("const gap = dot * .34;");
  expect(cardSource).toContain("const snap = (value) => Math.round(value * scale) / scale;");
  expect(cardSource).not.toContain("Math.ceil(px)");
});
