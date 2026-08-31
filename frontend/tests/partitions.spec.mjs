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
        { partition: 1, name: "Home", arming_state: "disarmed", ready: true, fire_alarm_active: false, supervisory_active: false, burglary_alarm_active: false, auxiliary_alarm_active: false, panic_audible_alarm_active: false, silent_alarm_active: false, duress_alarm_active: false },
        { partition: 2, name: "Garage", arming_state: "armed_stay", ready: true, fire_alarm_active: false, supervisory_active: false, burglary_alarm_active: false, auxiliary_alarm_active: true, panic_audible_alarm_active: false, silent_alarm_active: false, duress_alarm_active: false },
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
    };
  });
  expect(state.heading).toContain("Partition 1 · Home");
  expect(state.rows).toHaveLength(2);
  expect(state.rows.join("\n")).toContain("FRONT DOOR");
  expect(state.rows.join("\n")).toContain("BACK DOOR");
  expect(state.status).toContain("Faulted\n1");
  expect(state.status).toContain("Security\nNormal");
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
    app.data = {
      ...app.data,
      panel: { ...app.data.panel, authoritative: false },
    };
  });
  const state = await page.evaluate(() => {
    const r = document.getElementById("app").shadowRoot;
    return {
      heading: r.getElementById("partition-head").innerText,
      status: r.getElementById("partition-status").innerText,
    };
  });
  expect(state.heading).toContain("panel state not yet authoritative");
  expect(state.status).toContain("Arming\nUnknown");
  expect(state.status).toContain("Ready\nUnknown");
  expect(state.status).toContain("Security\nUnknown");
});

test("zone search and abnormal filtering are immediate", async ({ page }) => {
  await mount(page);
  await page.evaluate(() => {
    const r = document.getElementById("app").shadowRoot;
    const filter = r.getElementById("zone-filter");
    filter.value = "abnormal";
    filter.dispatchEvent(new Event("change"));
  });
  let text = await page.evaluate(() => document.getElementById("app").shadowRoot.getElementById("zones").innerText);
  expect(text).toContain("BACK DOOR");
  expect(text).not.toContain("FRONT DOOR");

  await page.evaluate(() => {
    const r = document.getElementById("app").shadowRoot;
    const filter = r.getElementById("zone-filter");
    filter.value = "all";
    filter.dispatchEvent(new Event("change"));
    const search = r.getElementById("zone-search");
    search.value = "front";
    search.dispatchEvent(new Event("input"));
  });
  text = await page.evaluate(() => document.getElementById("app").shadowRoot.getElementById("zones").innerText);
  expect(text).toContain("FRONT DOOR");
  expect(text).not.toContain("BACK DOOR");
});

test("selecting a different partition replaces only the partition detail", async ({ page }) => {
  await mount(page);
  await page.evaluate(() => document.getElementById("app").shadowRoot.querySelector('[data-partition="2"]').click());
  const state = await page.evaluate(() => {
    const r = document.getElementById("app").shadowRoot;
    return { heading: r.getElementById("partition-head").innerText, zones: r.getElementById("zones").innerText };
  });
  expect(state.heading).toContain("Partition 2 · Garage");
  expect(state.zones).toContain("GARAGE MOTION");
  expect(state.zones).not.toContain("FRONT DOOR");
});
