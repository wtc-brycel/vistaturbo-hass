import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { test, expect } from "@playwright/test";

const here = dirname(fileURLToPath(import.meta.url));
const stylesSource = readFileSync(join(here, "..", "vista-management-styles.js"), "utf8");
const materialSource = readFileSync(join(here, "..", "vista-management-material.js"), "utf8");
const source = readFileSync(join(here, "..", "vista-event-log-app.js"), "utf8");

async function mount(page) {
  await page.setContent('<!doctype html><html><body><vista-event-log-app id="app"></vista-event-log-app></body></html>');
  await page.addScriptTag({ content: stylesSource });
  await page.addScriptTag({ content: materialSource });
  await page.addScriptTag({ content: source });
  await page.evaluate(() => {
    const app = document.getElementById("app");
    app.data = {
      panel: { partitions: [{ partition: 1, name: "Home" }, { partition: 2, name: "Garage" }] },
      events: [
        { id: 1, event_code: "F5", description: "Fault", zone: 27, user: 0, partition: 1, panel_timestamp: "2026-08-30T20:10:00-04:00", descriptor: "FRONT DOOR", source: "live", received_at: "2026-08-30T20:10:02-04:00" },
        { id: 2, event_code: "B7", description: "Arm STAY", zone: 0, user: 2, partition: 2, panel_timestamp: "2026-08-30T19:45:00-04:00", descriptor: "", source: "history", received_at: "2026-08-30T20:00:00-04:00" },
      ],
      audit: [
        { interaction_id: "a1", started_at: "2026-08-30T20:20:00-04:00", completed_at: "2026-08-30T20:20:02-04:00", actor_id: "ha-1", actor_name: "Bryce", partition: 1, source: "ha_frontend", action: "disarm", status: "confirmed", command_type: "disarm", verification: "confirmed", command_sequence: "24681", code: "2468", operands: { partition: 1 } },
      ],
      admin: { elevated: false },
    };
  });
}

test("event log combines panel records and control audit without flattening record type", async ({ page }) => {
  await mount(page);
  const state = await page.evaluate(() => {
    const r = document.getElementById("app").shadowRoot;
    return {
      rows: [...r.querySelectorAll("#rows tr")].map((row) => row.innerText),
      count: r.getElementById("count").innerText,
      tabs: [...r.querySelectorAll('[role="tab"]')].map((tab) => ({ label: tab.textContent.trim(), selected: tab.getAttribute("aria-selected") })),
    };
  });
  expect(state.count).toBe("3 records");
  expect(state.rows.join("\n")).toContain("Panel");
  expect(state.rows.join("\n")).toContain("Audit");
  expect(state.rows.join("\n")).toContain("FRONT DOOR");
  expect(state.rows.join("\n")).toContain("Bryce");
  expect(state.tabs).toEqual([
    { label: "All", selected: "true" },
    { label: "Panel events", selected: "false" },
    { label: "Control audit", selected: "false" },
  ]);
});

test("record tabs filter panel events and control audit without a redundant type dropdown", async ({ page }) => {
  await mount(page);
  const state = await page.evaluate(() => {
    const app = document.getElementById("app");
    const r = app.shadowRoot;
    const typeSelectExists = Boolean(r.getElementById("type"));
    r.querySelector('[data-record-type="panel"]').click();
    const panelText = r.getElementById("rows").innerText;
    const panelType = app.recordType;
    r.querySelector('[data-record-type="audit"]').click();
    const auditText = r.getElementById("rows").innerText;
    const auditType = app.recordType;
    return { typeSelectExists, panelText, panelType, auditText, auditType };
  });
  expect(state.typeSelectExists).toBe(false);
  expect(state.panelType).toBe("panel");
  expect(state.panelText).toContain("FRONT DOOR");
  expect(state.panelText).not.toContain("Bryce");
  expect(state.auditType).toBe("audit");
  expect(state.auditText).toContain("Bryce");
  expect(state.auditText).not.toContain("FRONT DOOR");
});

test("advanced actor and record-type filters work together", async ({ page }) => {
  await mount(page);
  await page.evaluate(() => {
    const r = document.getElementById("app").shadowRoot;
    r.querySelector('[data-record-type="audit"]').click();
    const actor = r.getElementById("actor");
    actor.value = "bry";
    actor.dispatchEvent(new Event("input"));
  });
  await page.waitForTimeout(220);
  const text = await page.evaluate(() => document.getElementById("app").shadowRoot.getElementById("rows").innerText);
  expect(text).toContain("Audit");
  expect(text).toContain("Bryce");
  expect(text).not.toContain("FRONT DOOR");
});

test("active filters are visible and can be cleared in one action", async ({ page }) => {
  await mount(page);
  await page.evaluate(() => {
    const r = document.getElementById("app").shadowRoot;
    const search = r.getElementById("search");
    search.value = "door";
    search.dispatchEvent(new Event("input"));
    const partition = r.getElementById("partition");
    partition.value = "1";
    partition.dispatchEvent(new Event("change"));
    const actor = r.getElementById("actor");
    actor.value = "bry";
    actor.dispatchEvent(new Event("input"));
  });
  await page.waitForTimeout(220);
  let state = await page.evaluate(() => {
    const r = document.getElementById("app").shadowRoot;
    return {
      count: r.getElementById("filter-count").innerText,
      countHidden: r.getElementById("filter-count").hidden,
      advanced: r.getElementById("advanced-count").innerText,
      clearHidden: r.getElementById("clear-filters").hidden,
    };
  });
  expect(state.count).toBe("3 active");
  expect(state.countHidden).toBe(false);
  expect(state.advanced).toBe("1");
  expect(state.clearHidden).toBe(false);

  await page.evaluate(() => document.getElementById("app").shadowRoot.getElementById("clear-filters").click());
  state = await page.evaluate(() => {
    const r = document.getElementById("app").shadowRoot;
    return {
      countHidden: r.getElementById("filter-count").hidden,
      clearHidden: r.getElementById("clear-filters").hidden,
      search: r.getElementById("search").value,
      partition: r.getElementById("partition").value,
      actor: r.getElementById("actor").value,
      rows: r.getElementById("rows").innerText,
    };
  });
  expect(state.countHidden).toBe(true);
  expect(state.clearHidden).toBe(true);
  expect(state.search).toBe("");
  expect(state.partition).toBe("all");
  expect(state.actor).toBe("");
  expect(state.rows).toContain("FRONT DOOR");
  expect(state.rows).toContain("Bryce");
});

test("audit row detail keeps PIN-bearing fields hidden without step-up elevation", async ({ page }) => {
  await mount(page);
  await page.evaluate(() => document.getElementById("app").shadowRoot.querySelector('[data-record-id="audit:a1"]').click());
  const text = await page.evaluate(() => document.getElementById("app").shadowRoot.getElementById("detail-body").innerText);
  expect(text).toContain("Administrative unlock required");
  expect(text).not.toContain("2468");
  expect(text).not.toContain("24681");
});

test("elevated local fixture can reveal exact audit command details", async ({ page }) => {
  await mount(page);
  await page.evaluate(() => {
    const app = document.getElementById("app");
    app.adminState = { elevated: true };
    app.shadowRoot.querySelector('[data-record-id="audit:a1"]').click();
  });
  const text = await page.evaluate(() => document.getElementById("app").shadowRoot.getElementById("detail-body").innerText);
  expect(text).toContain("24681");
  expect(text).toContain("2468");
});

test("remote provider receives debounced search, record tab, source filter, sort and pagination state", async ({ page }) => {
  await mount(page);
  await page.evaluate(() => {
    const app = document.getElementById("app");
    window.providerCalls = [];
    app.logProvider = async (params) => {
      window.providerCalls.push(params);
      return { total: 1, records: [{ record_type: "panel", id: "9", time: "2026-08-30T20:30:00-04:00", event_action: "Fault", partition: 1, subject: "Z027 · FRONT DOOR", source_result: "live", zone: 27, user_number: 0, actor_name: "", actor_id: "", event_code: "F5", command_type: "", verification: "", status: "" }] };
    };
  });
  await page.waitForTimeout(20);
  await page.evaluate(() => {
    const r = document.getElementById("app").shadowRoot;
    r.querySelector('[data-record-type="panel"]').click();
    const search = r.getElementById("search");
    search.value = "door";
    search.dispatchEvent(new Event("input"));
    const source = r.getElementById("source");
    source.value = "live";
    source.dispatchEvent(new Event("change"));
    r.querySelector('[data-sort="event"]').click();
    const size = r.getElementById("page-size");
    size.value = "50";
    size.dispatchEvent(new Event("change"));
  });
  await page.waitForTimeout(240);
  const result = await page.evaluate(() => ({ calls: window.providerCalls, text: document.getElementById("app").shadowRoot.getElementById("rows").innerText, sort: document.getElementById("app").shadowRoot.querySelector('th[aria-sort]').getAttribute('aria-sort') }));
  const last = result.calls.at(-1);
  expect(last.q).toBe("door");
  expect(last.type).toBe("panel");
  expect(last.source).toBe("live");
  expect(last.sort).toBe("event");
  expect(last.page_size).toBe(50);
  expect(result.text).toContain("FRONT DOOR");
  expect(result.sort).toBe("ascending");
});

test("log rows open from keyboard", async ({ page }) => {
  await mount(page);
  await page.evaluate(() => {
    const row = document.getElementById("app").shadowRoot.querySelector('[data-record-id="panel:1"]');
    row.focus();
    row.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true }));
  });
  const open = await page.evaluate(() => document.getElementById("app").shadowRoot.getElementById("detail-dialog").open);
  expect(open).toBe(true);
});
