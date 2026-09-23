import { readFileSync, mkdirSync } from "node:fs";
import { execFileSync } from "node:child_process";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { test, expect } from "@playwright/test";

const here = dirname(fileURLToPath(import.meta.url));
const root = join(here, "../..");
const staticRoot = join(root, "vista128_bridge/app/vista_bridge/admin_frontend");
const fixture = JSON.parse(execFileSync("python3", [join(root, "vista128_bridge/tests/export_admin_fixture.py")], { encoding: "utf8" }));
const origin = "http://127.0.0.1:8765";
const prefix = "/api/hassio_ingress/fixture/";

async function mount(page, { state = "normal", width = 1280, dark = false } = {}) {
  await page.setViewportSize({ width, height: 850 });
  await page.emulateMedia({ colorScheme: dark ? "dark" : "light" });
  const errors = [], posts = [], queries = [], diagnosticQueries = [];
  page.on("pageerror", (error) => errors.push(error.message));
  const current = { snapshot: structuredClone(fixture[state]), connected: true, socket: null, timer: null };
  await page.route(origin + "/**", async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname.slice(prefix.length);
    if (path === "api/events") {
      queries.push(Object.fromEntries(url.searchParams));
      let rows = fixture.events.filter((e) => {
        const p = url.searchParams.get("partition"), source = url.searchParams.get("source"), q = url.searchParams.get("q");
        return (!p || p === "0" || e.partition === (p === "system" ? 0 : Number(p))) && (!source || source === e.source)
          && (!q || `${e.description} ${e.descriptor} ${e.event_code}`.toLowerCase().includes(q.toLowerCase()));
      });
      const cursor = Number(url.searchParams.get("cursor") || 0);
      return route.fulfill({ json: { events: rows.slice(cursor, cursor + 50), next_cursor: rows.length > cursor + 50 ? String(cursor + 50) : "", enabled: true } });
    }
    if (path === "api/diagnostics") {
      diagnosticQueries.push(Object.fromEntries(url.searchParams));
      let rows = fixture.diagnostics_api.records.filter((record) => {
        const severity = url.searchParams.get("severity");
        const category = url.searchParams.get("category");
        const correlation = url.searchParams.get("correlation_id");
        return (!severity || record.severity === severity)
          && (!category || record.category === category)
          && (!correlation || record.correlation_id === correlation);
      });
      const cursor = Number(url.searchParams.get("cursor") || 0);
      const records = rows.slice(cursor, cursor + 50);
      return route.fulfill({ json: {
        ...fixture.diagnostics_api,
        records,
        next_cursor: rows.length > cursor + 50 ? String(cursor + 50) : "",
      } });
    }
    if (path === "api/keypad") {
      const body = route.request().postDataJSON(); posts.push(body);
      current.snapshot.control_results = [{ transaction_id: body.transaction_id, partition: body.partition, ok: true, status: "accepted" }];
      return route.fulfill({ status: 202, json: { accepted: true, status: "queued", transaction_id: body.transaction_id } });
    }
    const filename = path || "index.html";
    if (!["index.html", "admin.css", "admin.js", "vista-keypad-card.js"].includes(filename)) return route.abort();
    return route.fulfill({ body: readFileSync(join(staticRoot, filename)), contentType: filename.endsWith(".css") ? "text/css" : filename.endsWith(".js") ? "application/javascript" : "text/html" });
  });
  await page.routeWebSocket("**/ws", (ws) => {
    current.socket = ws;
    const send = () => { if (current.connected) ws.send(JSON.stringify({ type: "snapshot", data: current.snapshot })); };
    send(); current.timer = setInterval(send, 200);
    ws.onClose(() => clearInterval(current.timer));
  });
  await page.goto(origin + prefix);
  await expect(page.locator("#system-state-title")).toHaveText(current.snapshot.system.condition.title);
  return { current, errors, posts, queries, diagnosticQueries, close: () => { current.connected = false; clearInterval(current.timer); current.socket.close({ code: 1001 }); } };
}

test("ingress has no branding bar or redundant overlines", async ({ page }) => {
  const h = await mount(page);
  await expect(page.locator(".app-header, .eyebrow")).toHaveCount(0);
  await expect(page.locator("#system-state-detail")).toBeEmpty();
  await expect(page.locator("#partition-grid .table-row")).toHaveCount(1);
  expect(h.errors).toEqual([]); h.close();
});

test("unknown evidence never appears as system normal", async ({ page }) => {
  const h = await mount(page, { state: "unknown" });
  await expect(page.locator("#system-state-title")).toHaveText("STATUS INCOMPLETE");
  await expect(page.locator("#system-state-detail")).toHaveText("Battery unknown");
  h.close();
});

test("socket loss invalidates the display and keypad immediately", async ({ page }) => {
  const h = await mount(page);
  await page.getByRole("button", { name: "Keypad", exact: true }).click();
  await expect(page.locator("#keypad-warning")).toBeHidden();
  h.close();
  await expect(page.locator("#system-state-title")).toHaveText("STATUS UNAVAILABLE");
  await expect(page.locator("#keypad-warning")).toContainText("live state unavailable");
  expect(await page.locator("#ingress-keypad").evaluate((c) => c._displayState().available)).toBe(false);
  expect(h.posts).toHaveLength(0);
});

test("keypad uses relative ingress API and distinguishes acknowledgement", async ({ page }) => {
  const h = await mount(page);
  await page.getByRole("button", { name: "Keypad", exact: true }).click();
  await page.locator("#ingress-keypad .layout-physical-view button[data-key='7']").click();
  await expect(page.locator("#keypad-result")).toHaveText("Key acknowledged");
  expect(h.posts).toHaveLength(1);
  expect(h.posts[0].instance_id).toBe("fixture-instance");
  expect(h.posts[0].session_generation).toBe(fixture.normal.panel.session_generation);
  expect(h.posts[0].actor_id).toBeUndefined();
  expect(h.errors).toEqual([]); h.close();
});

test("journal pages use applied filters, not unsubmitted edits", async ({ page }) => {
  const h = await mount(page);
  await page.getByRole("button", { name: "Event Journal", exact: true }).click();
  await expect(page.locator("#event-list .event-row")).toHaveCount(50);
  await page.locator("#event-partition").selectOption("system");
  await page.getByRole("button", { name: "Older", exact: true }).click();
  await expect(page.locator("#event-list .event-row")).toHaveCount(15);
  expect(h.queries.at(-1).partition).toBe("0");
  await page.getByRole("button", { name: "Newer", exact: true }).click();
  await expect(page.locator("#event-list .event-row")).toHaveCount(50);
  await page.getByRole("button", { name: "Apply", exact: true }).click();
  await expect(page.locator("#event-list .event-row")).toHaveCount(fixture.events.filter(e => e.partition === 0).length);
  expect(h.queries.at(-1).cursor).toBeUndefined();
  expect(h.errors).toEqual([]); h.close();
});

test("diagnostics loads categorized journal and correlated incidents", async ({ page }) => {
  const h = await mount(page);
  await page.getByRole("button", { name: "Diagnostics", exact: true }).click();
  await expect(page.locator("#diagnostic-event-list .diagnostic-event-row")).toHaveCount(50);
  await expect(page.locator("#diagnostic-incidents .diagnostic-incident")).toHaveCount(1);
  await expect(page.locator("#diagnostic-summary")).toContainText("65 retained");
  const firstDiagnostic = page.locator("#diagnostic-event-list .diagnostic-event-row").first();
  await firstDiagnostic.click();
  await expect(firstDiagnostic.locator(".diagnostic-event-details")).toBeVisible();
  await expect(firstDiagnostic.locator(".diagnostic-event-details")).toContainText("last puback age seconds");
  await expect(firstDiagnostic.locator(".diagnostic-event-details")).toContainText("61.2");
  await page.waitForTimeout(500);
  await expect(firstDiagnostic.locator(".diagnostic-event-details")).toBeVisible();
  await page.locator("#diagnostic-severity").selectOption("error");
  await page.locator("#diagnostic-category").selectOption("ha_transport");
  await page.getByRole("button", { name: "Apply", exact: true }).click();
  await expect(page.locator("#diagnostic-event-list .diagnostic-event-row")).toHaveCount(
    fixture.diagnostics_api.records.filter((r) => r.severity === "error" && r.category === "ha_transport").length
  );
  expect(h.diagnosticQueries.at(-1).severity).toBe("error");
  expect(h.diagnosticQueries.at(-1).category).toBe("ha_transport");
  expect(h.errors).toEqual([]); h.close();
});

test("diagnostic incident opens its full correlated event sequence", async ({ page }) => {
  const h = await mount(page);
  await page.getByRole("button", { name: "Diagnostics", exact: true }).click();
  await page.locator("#diagnostic-severity").selectOption("error");
  await page.locator("#diagnostic-category").selectOption("ha_transport");
  await page.locator("#diagnostic-incidents .diagnostic-incident").click();
  await expect(page.locator("#diagnostic-summary")).toContainText("Incident selected");
  expect(h.diagnosticQueries.at(-1).correlation_id).toBe("ha_fixture_1");
  expect(h.diagnosticQueries.at(-1).severity).toBeUndefined();
  expect(h.diagnosticQueries.at(-1).category).toBeUndefined();
  await expect(page.locator("#diagnostic-event-list .diagnostic-event-row")).toHaveCount(
    fixture.diagnostics_api.records.filter((r) => r.correlation_id === "ha_fixture_1").length
  );
  expect(h.errors).toEqual([]); h.close();
});

test("diagnostic history uses bounded older paging", async ({ page }) => {
  const h = await mount(page);
  await page.getByRole("button", { name: "Diagnostics", exact: true }).click();
  await expect(page.locator("#diagnostic-event-list .diagnostic-event-row")).toHaveCount(50);
  await expect(page.getByRole("button", { name: "Older", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Older", exact: true }).click();
  await expect(page.locator("#diagnostic-event-list .diagnostic-event-row")).toHaveCount(65);
  expect(h.diagnosticQueries.at(-1).cursor).toBe("50");
  await expect(page.getByRole("button", { name: "Older", exact: true })).toBeHidden();
  expect(h.errors).toEqual([]); h.close();
});

test("mobile pages preserve labels and fit without horizontal overflow", async ({ page }) => {
  const h = await mount(page, { width: 390 });
  for (const view of ["overview", "events", "keypad", "diagnostics"]) {
    await page.locator(`[data-view='${view}']`).click();
    await expect(page.locator(`[data-view='${view}'] span`)).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  }
  expect(h.errors).toEqual([]); h.close();
});

test("capture exact source with deterministic app fixtures", async ({ page }) => {
  const h = await mount(page);
  const output = join(root, "frontend/test-results/ingress-review"); mkdirSync(output, { recursive: true });
  for (const dark of [false, true]) {
    await page.emulateMedia({ colorScheme: dark ? "dark" : "light" });
    for (const view of ["overview", "keypad", "events", "diagnostics"]) {
      await page.locator(`[data-view='${view}']`).click();
      if (view === "events") await expect(page.locator("#event-list .event-row")).toHaveCount(50);
      await page.screenshot({ path: join(output, `${view}-${dark ? "dark" : "light"}.png`), fullPage: true });
    }
  }
  expect(h.errors).toEqual([]); h.close();
});
