import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join, resolve } from "node:path";
import { test, expect } from "@playwright/test";

const here = dirname(fileURLToPath(import.meta.url));
const frontend = resolve(here, "..");
const ingress = resolve(frontend, "..", "vista128_bridge", "app", "management_static");

for (const name of [
  "vista-keypad-card.js",
  "vista-management-styles.js",
  "vista-management-material.js",
  "vista-management-app.js",
  "vista-management-shell.js",
  "vista-partitions-app.js",
  "vista-event-log-app.js",
]) {
  test(`ingress bundle keeps ${name} byte-identical to the production frontend`, async () => {
    expect(readFileSync(join(ingress, name))).toEqual(readFileSync(join(frontend, name)));
  });
}

test("ingress bootstrap parses, scopes elevation, and has no out-of-band setup token", async () => {
  const source = readFileSync(join(ingress, "bootstrap.js"), "utf8");
  expect(() => new Function(source)).not.toThrow();
  expect(source).toContain("X-Vista-Ingress-Base");
  expect(source).toContain("hassio_ingress");
  expect(source).toContain("Vista administrator unlock required");
  expect(source).toContain("management-ingress/keypad/${number}/command");
  expect(source).not.toContain("bootstrap_token");
  expect(source).not.toContain('"Path=/"');
});
