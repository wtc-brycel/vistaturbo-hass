import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { test, expect } from "@playwright/test";

const here = dirname(fileURLToPath(import.meta.url));
const cardSource = readFileSync(join(here, "..", "vista-keypad-card.js"), "utf8");
const ENTITY = "sensor.vista_partition_1_keypad";

async function mountCard(page, { width, model = "6160cr2", layout = "auto", dark = false } = {}) {
  await page.setViewportSize({ width: Math.max(360, width + 40), height: 1000 });
  await page.setContent(`<!doctype html><html><head><meta charset="utf-8"><style>
    html,body{margin:0;padding:0;background:#eee}
    #stage{width:${width}px;margin:0 auto}
    vista-keypad-card{display:block;width:100%}
  </style></head><body><div id="stage"><vista-keypad-card id="card"></vista-keypad-card></div></body></html>`);

  await page.evaluate(() => {
    if (!customElements.get("ha-card")) customElements.define("ha-card", class extends HTMLElement {});
  });
  await page.addScriptTag({ content: cardSource });

  await page.evaluate(({ entity, model, layout, dark }) => {
    const card = document.getElementById("card");
    card.setConfig({
      entity,
      model,
      layout,
      case_color: "auto",
      read_only: true,
    });
    card.hass = {
      themes: { darkMode: dark },
      states: {
        [entity]: {
          state: "P1 DISARMED / READY TO ARM",
          attributes: {
            line_1: "P1   DISARMED   ",
            line_2: "READY TO ARM    ",
            ready: true,
            armed: false,
            trouble: false,
            backlight: true,
            power: true,
            fire_alarm: false,
            silenced: false,
            supervisory: false,
          },
        },
      },
    };
  }, { entity: ENTITY, model, layout, dark });

  await page.evaluate(() => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve))));
}

async function renderedState(page) {
  return page.evaluate(() => {
    const card = document.getElementById("card");
    const root = card.shadowRoot;
    const physicalView = root.querySelector(".layout-physical-view");
    const compactView = root.querySelector(".layout-compact-view");
    const physicalShell = root.querySelector(".keypad-shell");
    const compactShell = root.querySelector(".compact-shell");
    const visible = (el) => el && getComputedStyle(el).display !== "none" && el.getBoundingClientRect().width > 0;
    const buttons = [...root.querySelectorAll(".layout-compact-view button.physical-key")];
    const buttonRects = buttons.map((button) => {
      const r = button.getBoundingClientRect();
      return { width: r.width, height: r.height };
    });
    return {
      physicalVisible: visible(physicalView),
      compactVisible: visible(compactView),
      physicalCase: physicalShell?.dataset.caseColor ?? null,
      compactCase: compactShell?.dataset.caseColor ?? null,
      compactIndicators: root.querySelectorAll(".layout-compact-view .compact-indicator").length,
      buttonRects,
      grid: card.getGridOptions(),
    };
  });
}

test("AUTO keeps physical facsimile on a wide Lovelace card", async ({ page }) => {
  await mountCard(page, { width: 700, model: "6160cr2" });
  const state = await renderedState(page);
  expect(state.physicalVisible).toBe(true);
  expect(state.compactVisible).toBe(false);
});

test("AUTO switches CR-2 to compact layout at phone width", async ({ page }) => {
  await mountCard(page, { width: 390, model: "6160cr2" });
  const state = await renderedState(page);
  expect(state.physicalVisible).toBe(false);
  expect(state.compactVisible).toBe(true);
  expect(state.compactIndicators).toBe(7);
  expect(state.buttonRects).toHaveLength(16);
  for (const rect of state.buttonRects) {
    expect(rect.width).toBeGreaterThanOrEqual(75);
    expect(rect.height).toBeGreaterThanOrEqual(48);
  }
});

test("AUTO remains touchable at a 320px card width", async ({ page }) => {
  await mountCard(page, { width: 320, model: "6160cr2" });
  const state = await renderedState(page);
  expect(state.compactVisible).toBe(true);
  for (const rect of state.buttonRects) {
    expect(rect.width).toBeGreaterThanOrEqual(60);
    expect(rect.height).toBeGreaterThanOrEqual(48);
  }
});

test("standard 6160 uses the same compact framework with its own profile", async ({ page }) => {
  await mountCard(page, { width: 390, model: "6160" });
  const state = await renderedState(page);
  expect(state.compactVisible).toBe(true);
  expect(state.compactIndicators).toBe(2);
  expect(state.buttonRects).toHaveLength(16);
});

test("layout override can force physical or compact mode", async ({ page }) => {
  await mountCard(page, { width: 390, model: "6160cr2", layout: "physical" });
  let state = await renderedState(page);
  expect(state.physicalVisible).toBe(true);
  expect(state.compactVisible).toBe(false);

  await mountCard(page, { width: 700, model: "6160cr2", layout: "compact" });
  state = await renderedState(page);
  expect(state.physicalVisible).toBe(false);
  expect(state.compactVisible).toBe(true);
});

test("AUTO case colors follow model and Home Assistant theme", async ({ page }) => {
  await mountCard(page, { width: 390, model: "6160cr2", dark: false });
  let state = await renderedState(page);
  expect(state.compactCase).toBe("red");

  await mountCard(page, { width: 390, model: "6160cr2", dark: true });
  state = await renderedState(page);
  expect(state.compactCase).toBe("dark");

  await mountCard(page, { width: 390, model: "6160", dark: false });
  state = await renderedState(page);
  expect(state.compactCase).toBe("white");

  await mountCard(page, { width: 390, model: "6160", dark: true });
  state = await renderedState(page);
  expect(state.compactCase).toBe("dark");
});

test("Lovelace grid contract permits four-column compact placement", async ({ page }) => {
  await mountCard(page, { width: 390, model: "6160cr2" });
  const state = await renderedState(page);
  expect(state.grid).toEqual({ columns: 12, min_columns: 4, max_columns: 12 });
});


test("First Alert AUTO uses horizontal wide and portrait narrow compositions", async ({ page }) => {
  await mountCard(page, { width: 760, model: "firstalert" });
  let state = await page.evaluate(() => {
    const root = document.getElementById("card").shadowRoot;
    const wide = root.querySelector(".layout-physical-view .firstalert-wide");
    const portrait = root.querySelector(".layout-compact-view .firstalert-portrait");
    const wr = wide.getBoundingClientRect();
    return {
      wideVisible: getComputedStyle(root.querySelector(".layout-physical-view")).display !== "none",
      portraitVisible: getComputedStyle(root.querySelector(".layout-compact-view")).display !== "none",
      wideRatio: wr.width / wr.height,
      statusCount: wide.querySelectorAll(".fa-status .compact-indicator").length,
      functionLabels: [...wide.querySelectorAll(".fa-function-bank .function-label")].map((el) => el.textContent.trim()),
      legends: [...wide.querySelectorAll(".fa-numeric-grid .number-legend")].map((el) => el.textContent.trim()),
    };
  });
  expect(state.wideVisible).toBe(true);
  expect(state.portraitVisible).toBe(false);
  expect(state.wideRatio).toBeGreaterThan(1.5);
  expect(state.statusCount).toBe(7);
  expect(state.functionLabels).toEqual(["A", "B", "C", "D"]);
  expect(state.legends).toContain("SELECT");
  expect(state.legends).toContain("SCROLL");

  await mountCard(page, { width: 390, model: "firstalert" });
  state = await page.evaluate(() => {
    const root = document.getElementById("card").shadowRoot;
    const portrait = root.querySelector(".layout-compact-view .firstalert-portrait");
    const pr = portrait.getBoundingClientRect();
    return {
      physicalVisible: getComputedStyle(root.querySelector(".layout-physical-view")).display !== "none",
      compactVisible: getComputedStyle(root.querySelector(".layout-compact-view")).display !== "none",
      portraitRatio: pr.height / pr.width,
      statusCount: portrait.querySelectorAll(".fa-status .compact-indicator").length,
      functionLabels: [...portrait.querySelectorAll(".fa-function-bank .function-label")].map((el) => el.textContent.trim()),
      keyCount: portrait.querySelectorAll("button[data-key]").length,
    };
  });
  expect(state.physicalVisible).toBe(false);
  expect(state.compactVisible).toBe(true);
  expect(state.portraitRatio).toBeGreaterThan(1.0);
  expect(state.statusCount).toBe(7);
  expect(state.functionLabels).toEqual(["A", "B", "C", "D"]);
  expect(state.keyCount).toBe(16);
});

test("First Alert AUTO case follows white day and dark night defaults", async ({ page }) => {
  await mountCard(page, { width: 390, model: "firstalert", dark: false });
  let caseColor = await page.evaluate(() => document.getElementById("card").shadowRoot.querySelector(".firstalert-portrait").dataset.caseColor);
  expect(caseColor).toBe("white");
  await mountCard(page, { width: 390, model: "firstalert", dark: true });
  caseColor = await page.evaluate(() => document.getElementById("card").shadowRoot.querySelector(".firstalert-portrait").dataset.caseColor);
  expect(caseColor).toBe("dark");
});


test("custom card exposes a Home Assistant visual editor", async ({ page }) => {
  await page.setContent(`<!doctype html><html><body></body></html>`);
  await page.evaluate(() => {
    if (!customElements.get("ha-card")) customElements.define("ha-card", class extends HTMLElement {});
  });
  await page.addScriptTag({ content: cardSource });

  const result = await page.evaluate(async ({ entity }) => {
    const ctor = customElements.get("vista-keypad-card");
    const editor = await ctor.getConfigElement();
    document.body.append(editor);
    editor.hass = {
      states: {
        [entity]: { state: "ready", attributes: { friendly_name: "Partition 1 Keypad" } },
      },
    };
    editor.setConfig({
      type: "custom:vista-keypad-card",
      entity,
      model: "firstalert",
      layout: "auto",
      case_color: "auto",
      sound: { enabled: true, state_sounds: true },
      haptic: { enabled: true, keypress_ms: 10 },
    });
    return {
      tag: editor.tagName.toLowerCase(),
      model: editor.shadowRoot.querySelector("[data-top=model]").value,
      layout: editor.shadowRoot.querySelector("[data-top=layout]").value,
      sound: editor.shadowRoot.querySelector("[data-sound=enabled]").checked,
      haptic: editor.shadowRoot.querySelector("[data-haptic=enabled]").checked,
      entity: editor.shadowRoot.querySelector("[data-top=entity]").value,
    };
  }, { entity: ENTITY });

  expect(result).toEqual({
    tag: "vista-keypad-card-editor",
    model: "firstalert",
    layout: "auto",
    sound: true,
    haptic: true,
    entity: ENTITY,
  });
});

test("visual editor emits clean nested config changes", async ({ page }) => {
  await page.setContent(`<!doctype html><html><body></body></html>`);
  await page.evaluate(() => {
    if (!customElements.get("ha-card")) customElements.define("ha-card", class extends HTMLElement {});
  });
  await page.addScriptTag({ content: cardSource });

  const changes = await page.evaluate(async ({ entity }) => {
    const ctor = customElements.get("vista-keypad-card");
    const editor = await ctor.getConfigElement();
    document.body.append(editor);
    editor.setConfig({ type: "custom:vista-keypad-card", entity, model: "6160cr2" });
    const emitted = [];
    editor.addEventListener("config-changed", (event) => emitted.push(JSON.parse(JSON.stringify(event.detail.config))));

    const model = editor.shadowRoot.querySelector("[data-top=model]");
    model.value = "firstalert";
    model.dispatchEvent(new Event("change", { bubbles: true }));

    const sound = editor.shadowRoot.querySelector("[data-sound=enabled]");
    sound.checked = true;
    sound.dispatchEvent(new Event("change", { bubbles: true }));

    const stateSounds = editor.shadowRoot.querySelector("[data-sound=state_sounds]");
    stateSounds.checked = true;
    stateSounds.dispatchEvent(new Event("change", { bubbles: true }));

    const haptic = editor.shadowRoot.querySelector("[data-haptic=enabled]");
    haptic.checked = true;
    haptic.dispatchEvent(new Event("change", { bubbles: true }));

    const functionA = editor.shadowRoot.querySelector("[data-function=a]");
    functionA.value = "PANIC";
    functionA.dispatchEvent(new Event("change", { bubbles: true }));

    return emitted;
  }, { entity: ENTITY });

  const last = changes.at(-1);
  expect(last.model).toBe("firstalert");
  expect(last.sound.enabled).toBe(true);
  expect(last.sound.state_sounds).toBe(true);
  expect(last.haptic.enabled).toBe(true);
  expect(last.function_keys.a).toBe("PANIC");
  expect(last.entity).toBe(ENTITY);
});


test("visual editor understands boolean sound and haptic shorthand", async ({ page }) => {
  await page.setContent(`<!doctype html><html><body></body></html>`);
  await page.evaluate(() => {
    if (!customElements.get("ha-card")) customElements.define("ha-card", class extends HTMLElement {});
  });
  await page.addScriptTag({ content: cardSource });

  const result = await page.evaluate(async ({ entity }) => {
    const ctor = customElements.get("vista-keypad-card");
    const editor = await ctor.getConfigElement();
    document.body.append(editor);
    editor.setConfig({
      type: "custom:vista-keypad-card",
      entity,
      sound: true,
      haptic: true,
    });
    return {
      sound: editor.shadowRoot.querySelector("[data-sound=enabled]").checked,
      haptic: editor.shadowRoot.querySelector("[data-haptic=enabled]").checked,
    };
  }, { entity: ENTITY });

  expect(result).toEqual({ sound: true, haptic: true });
});
