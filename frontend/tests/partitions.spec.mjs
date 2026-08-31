import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { test, expect } from "@playwright/test";

const here = dirname(fileURLToPath(import.meta.url));
const stylesSource = readFileSync(join(here, "..", "vista-management-styles.js"), "utf8");
const source = readFileSync(join(here, "..", "vista-partitions-app.js"), "utf8");

async function mount(page) {
  await page.setContent('<!doctype html><html><body><vista-partitions-app id="app"></vista-partitions-app></body></html>');
  await page.addScriptTag({ content: stylesSource });
  await page.addScriptTag({ content: source });
  await page.evaluate(() => {
    const app = document.getElementById("app");
    app.data = {
      panel: { authoritative: true, partitions: [
        {
          partition: 1,
          name: "Home",
          arming_state: "disarmed",
          ready: true,
          fire_alarm_active: false,
          supervisory_active: false,
          burglary_alarm_active: false,
          auxiliary_alarm_active: false,
          panic_audible_alarm_active: false,
          silent_alarm_active: false,
          duress_alarm_active: false,
          keypad: { state: "DISARMED | READY TO ARM", attributes: { line_1: "DISARMED        ", line_2: "READY TO ARM    " } },
        },
        {
          partition: 2,
          name: "Garage",
          arming_state: "armed_stay",
          ready: true,
          fire_alarm_active: false,
          supervisory_active: false,
          burglary_alarm_active: false,
          auxiliary_alarm_active: true,
          panic_audible_alarm_active: false,
          silent_alarm_active: false,
          duress_alarm_active: false,
          keypad: { state: "ARMED ***STAY***", attributes: { line_1: "ARMED ***STAY***", line_2: "GARAGE          " } },
        },
      ] },
      zones: [
        { zone: 1, partition: 1, descriptor: "FRONT DOOR", faulted: false, bypassed: false, trouble: false, alarm: false, low_battery: false, tamper: false },
        { zone: 2, partition: 1, descriptor: "BACK DOOR", faulted: true, bypassed: false, trouble: false, alarm: false, low_battery: false, tamper: false },
        { zone: 17, partition: 2, descriptor: "GARAGE MOTION", faulted: false, bypassed: true, trouble: false, alarm: false, low_battery: false, tamper: false },
      ],
    };
  });
}

test("partition detail lists assigned zones and real conditions", async ({ page }) => {
  await mount(page);
  const state = await page.evaluate(() => {
    const r = document.getElementById("app").shadowRoot;
    return {
      heading: r.getElementById("partition-head").innerText,
      rows: [...r.querySelectorAll("#zones tr")].map((row) => row.innerText),
      status: r.getElementById("partition-status").innerText,
      columns: [...r.querySelectorAll(".zones-table th")].map((th) => th.innerText.trim()),
    };
  });
  expect(state.heading).toContain("Partition 1 · Home");
  expect(state.rows).toHaveLength(2);
  expect(state.rows.join("\n")).toContain("FRONT DOOR");
  expect(state.rows.join("\n")).toContain("BACK DOOR");
  expect(state.rows.join("\n")).toContain("Fault");
  expect(state.status).toContain("Faulted\n1");
  expect(state.status).toContain("Security\nNormal");
  expect(state.columns).toEqual(["Zone", "Descriptor", "State", "Conditions"]);
});

test("partition security state keeps auxiliary distinct", async ({ page }) => {
  await mount(page);
  await page.evaluate(() => document.getElementById("app").shadowRoot.querySelector('[data-partition="2"]').click());
  const status = await page.evaluate(() => document.getElementById("app").shadowRoot.getElementById("partition-status").innerText);
  expect(status).toContain("Security\nAuxiliary");
  expect(status).not.toContain("Security\nBurglary");
});

test("incomplete snapshot is shown as unknown instead of known-normal", async ({ page }) => {
  await mount(page);
  await page.evaluate(() => {
    const app = document.getElementById("app");
    app.data = { ...app.data, panel: { ...app.data.panel, authoritative: false } };
  });
  const state = await page.evaluate(() => {
    const r = document.getElementById("app").shadowRoot;
    return { heading: r.getElementById("partition-head").innerText, status: r.getElementById("partition-status").innerText };
  });
  expect(state.heading).toContain("panel state not yet authoritative");
  expect(state.status).toContain("Arming\nUnknown");
  expect(state.status).toContain("Ready\nUnknown");
  expect(state.status).toContain("Security\nUnknown");
});

test("zone search and abnormal filtering are immediate and clearable", async ({ page }) => {
  await mount(page);
  await page.evaluate(() => {
    const r = document.getElementById("app").shadowRoot;
    const filter = r.getElementById("zone-filter");
    filter.value = "abnormal";
    filter.dispatchEvent(new Event("change"));
  });
  let state = await page.evaluate(() => {
    const r = document.getElementById("app").shadowRoot;
    return { text: r.getElementById("zones").innerText, clearHidden: r.getElementById("clear-zone-filter").hidden, count: r.getElementById("zone-count").innerText };
  });
  expect(state.text).toContain("BACK DOOR");
  expect(state.text).not.toContain("FRONT DOOR");
  expect(state.clearHidden).toBe(false);
  expect(state.count).toBe("1 of 2");

  await page.evaluate(() => document.getElementById("app").shadowRoot.getElementById("clear-zone-filter").click());
  state = await page.evaluate(() => {
    const r = document.getElementById("app").shadowRoot;
    return { text: r.getElementById("zones").innerText, clearHidden: r.getElementById("clear-zone-filter").hidden, filter: r.getElementById("zone-filter").value };
  });
  expect(state.text).toContain("FRONT DOOR");
  expect(state.text).toContain("BACK DOOR");
  expect(state.clearHidden).toBe(true);
  expect(state.filter).toBe("all");
});

test("selecting a different partition replaces only the partition detail", async ({ page }) => {
  await mount(page);
  await page.evaluate(() => document.getElementById("app").shadowRoot.querySelector('[data-partition="2"]').click());
  const state = await page.evaluate(() => {
    const r = document.getElementById("app").shadowRoot;
    return { heading: r.getElementById("partition-head").innerText, zones: r.getElementById("zones").innerText, active: document.getElementById("app").activePartition };
  });
  expect(state.active).toBe(2);
  expect(state.heading).toContain("Partition 2 · Garage");
  expect(state.zones).toContain("GARAGE MOTION");
  expect(state.zones).not.toContain("FRONT DOOR");
});

test("partition management never renders a second keypad or fake LCD", async ({ page }) => {
  await mount(page);
  const state = await page.evaluate(() => {
    const r = document.getElementById("app").shadowRoot;
    return {
      keypadCards: r.querySelectorAll("vista-keypad-card").length,
      lcd: r.querySelectorAll(".lcd").length,
      keypadDetail: Boolean(r.getElementById("keypad-detail")),
      detailTabs: r.querySelectorAll('[role="tab"]').length,
      text: r.querySelector(".partition-app").innerText,
    };
  });
  expect(state.keypadCards).toBe(0);
  expect(state.lcd).toBe(0);
  expect(state.keypadDetail).toBe(false);
  expect(state.detailTabs).toBe(0);
  expect(state.text).not.toContain("Sound mode");
});

test("abnormal partition and zone states use compact visual indicators", async ({ page }) => {
  await mount(page);
  const state = await page.evaluate(() => {
    const r = document.getElementById("app").shadowRoot;
    const p1 = r.querySelector('[data-partition="1"]');
    const abnormalRow = [...r.querySelectorAll("#zones tr")].find((row) => row.innerText.includes("BACK DOOR"));
    return {
      badge: p1.querySelector(".abnormal-count")?.textContent,
      selectedHasAccent: getComputedStyle(p1, "::before").backgroundColor !== "rgba(0, 0, 0, 0)",
      conditions: abnormalRow?.querySelector("td:last-child")?.innerText,
      state: abnormalRow?.querySelector(".state-pill")?.innerText,
    };
  });
  expect(state.badge).toBe("1");
  expect(state.selectedHasAccent).toBe(true);
  expect(state.conditions).toContain("Fault");
  expect(state.state).toBe("Fault");
});
