import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { test, expect } from "@playwright/test";

const here = dirname(fileURLToPath(import.meta.url));
const cardSource = readFileSync(join(here, "..", "vista-keypad-card.js"), "utf8");
const ENTITY = "sensor.vista_128bpt_event_journal";

async function mount(page, { width = 720, partition = 0, rows = 20 } = {}) {
  await page.setViewportSize({ width: Math.max(360, width + 40), height: 900 });
  await page.setContent(`<!doctype html><html><head><style>html,body{margin:0}#stage{width:${width}px;margin:auto}</style></head><body><div id="stage"><vista-event-log-card id="card"></vista-event-log-card></div></body></html>`);
  await page.evaluate(() => {
    if (!customElements.get("ha-card")) customElements.define("ha-card", class extends HTMLElement {});
  });
  await page.addScriptTag({ content: cardSource });
  await page.evaluate(({ entity, partition, rows }) => {
    const card = document.getElementById("card");
    card.setConfig({ entity, partition, rows });
    card.hass = {
      states: {
        [entity]: {
          state: "512",
          attributes: {
            count: 512,
            last_dump_at: "2026-08-17T10:05:00-04:00",
            last_dump_seen: 512,
            last_dump_inserted: 417,
            events: [
              {
                id: 2,
                event_code: "F5",
                description: "Fault",
                zone: 27,
                user: 0,
                partition: 1,
                panel_timestamp: "2026-08-17T10:10",
                descriptor: "FRONT DOOR",
                source: "live",
                received_at: "2026-08-17T10:10:02-04:00",
              },
              {
                id: 1,
                event_code: "B7",
                description: "Arm STAY",
                zone: 0,
                user: 2,
                partition: 2,
                panel_timestamp: "2026-08-15T03:21",
                descriptor: "",
                source: "both",
                received_at: "2026-08-17T10:05:00-04:00",
              },
            ],
          },
        },
      },
    };
  }, { entity: ENTITY, partition, rows });
  await page.evaluate(() => new Promise((resolve) => requestAnimationFrame(resolve)));
}

test("event journal renders recent rows and metadata", async ({ page }) => {
  await mount(page);
  const state = await page.evaluate(() => {
    const root = document.getElementById("card").shadowRoot;
    return {
      rowCount: root.querySelectorAll(".event-row").length,
      text: root.textContent,
      source: root.querySelector(".event-row .source").textContent.trim(),
    };
  });
  expect(state.rowCount).toBe(2);
  expect(state.text).toContain("512 events");
  expect(state.text).toContain("FRONT DOOR");
  expect(state.text).toContain("P1");
  expect(state.text).toContain("Z027");
  expect(state.source).toBe("LIVE");
});

test("event journal can filter by partition", async ({ page }) => {
  await mount(page, { partition: 1 });
  const rows = await page.evaluate(() => document.getElementById("card").shadowRoot.querySelectorAll(".event-row").length);
  expect(rows).toBe(1);
  const text = await page.evaluate(() => document.getElementById("card").shadowRoot.textContent);
  expect(text).toContain("FRONT DOOR");
  expect(text).not.toContain("Arm STAY");
});

test("event journal remains contained at phone width", async ({ page }) => {
  await mount(page, { width: 360 });
  const overflow = await page.evaluate(() => {
    const card = document.getElementById("card");
    const rect = card.getBoundingClientRect();
    const root = card.shadowRoot;
    return [...root.querySelectorAll(".event-row")].some((row) => row.getBoundingClientRect().right > rect.right + 1);
  });
  expect(overflow).toBe(false);
});

test("event journal exposes a visual editor and emits config changes", async ({ page }) => {
  await page.setContent(`<!doctype html><html><body></body></html>`);
  await page.addScriptTag({ content: cardSource });
  const result = await page.evaluate(() => {
    const editor = document.createElement("vista-event-log-card-editor");
    document.body.append(editor);
    editor.hass = { states: { "sensor.vista_128bpt_event_journal": { state: "1", attributes: {} } } };
    editor.setConfig({ entity: "sensor.vista_128bpt_event_journal", rows: 20 });
    return new Promise((resolve) => {
      editor.addEventListener("config-changed", (event) => resolve(event.detail.config), { once: true });
      const input = editor.shadowRoot.querySelector('[data-field="rows"]');
      input.value = "30";
      input.dispatchEvent(new Event("change"));
    });
  });
  expect(result.rows).toBe(30);
});
