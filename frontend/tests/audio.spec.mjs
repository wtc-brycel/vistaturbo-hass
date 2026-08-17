import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { test, expect } from "@playwright/test";

const here = dirname(fileURLToPath(import.meta.url));
const cardSource = readFileSync(join(here, "..", "vista-keypad-card.js"), "utf8");
const ENTITY = "sensor.vista_partition_1_keypad";
const ALARM = "alarm_control_panel.test_alarm";
const AUX = "binary_sensor.test_aux";

function keypadState(overrides = {}) {
  return {
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
      chime_sequence: 0,
      chime_zone: null,
      chime_descriptor: "",
      ...overrides,
    },
  };
}

async function mountAudioCard(page, { haptic = false } = {}) {
  await page.setViewportSize({ width: 430, height: 900 });
  await page.setContent(`<!doctype html><html><head><style>
    html,body{margin:0}#stage{width:390px;margin:auto}vista-keypad-card{display:block;width:100%}
  </style></head><body><div id="stage"><vista-keypad-card id="card"></vista-keypad-card></div></body></html>`);
  await page.evaluate(() => {
    if (!customElements.get("ha-card")) customElements.define("ha-card", class extends HTMLElement {});
  });
  await page.addScriptTag({ content: cardSource });

  await page.evaluate(({ entity, alarm, aux, haptic }) => {
    const card = document.getElementById("card");
    card.setConfig({
      entity,
      model: "6160cr2",
      layout: "compact",
      read_only: true,
      sound: {
        enabled: true,
        keypress: true,
        state_sounds: true,
        chime: true,
        trouble: true,
        supervisory: true,
        alarm_entity: alarm,
        aux_entity: aux,
      },
      haptic: { enabled: haptic, keypress_ms: 10 },
    });
    card.hass = {
      themes: { darkMode: false },
      states: {
        [entity]: {
          state: "P1 DISARMED / READY TO ARM",
          attributes: {
            line_1: "P1   DISARMED   ", line_2: "READY TO ARM    ",
            ready: true, armed: false, trouble: false, backlight: true,
            power: true, fire_alarm: false, silenced: false, supervisory: false,
            chime_sequence: 0, chime_zone: null, chime_descriptor: "",
          },
        },
        [alarm]: { state: "disarmed", attributes: {} },
        [aux]: { state: "off", attributes: {} },
      },
    };
  }, { entity: ENTITY, alarm: ALARM, aux: AUX, haptic });

  await page.evaluate(() => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve))));
}

async function installAudioSpies(page) {
  await page.evaluate(() => {
    const card = document.getElementById("card");
    window.__audioCalls = { play: [], loops: [], keypress: 0, haptic: 0 };
    card._audio.play = async (name) => { window.__audioCalls.play.push(name); return true; };
    card._audio.setLoop = (name) => { window.__audioCalls.loops.push(name); };
    card._audio.keypress = async () => { window.__audioCalls.keypress += 1; return true; };
    card._haptics.pulse = () => { window.__audioCalls.haptic += 1; return true; };
  });
}

async function updateStates(page, { keypad = {}, alarm = "disarmed", aux = "off" } = {}) {
  await page.evaluate(({ entity, alarmEntity, auxEntity, keypad, alarm, aux }) => {
    const card = document.getElementById("card");
    const previous = card._hass.states[entity];
    card.hass = {
      themes: { darkMode: false },
      states: {
        [entity]: {
          state: previous.state,
          attributes: { ...previous.attributes, ...keypad },
        },
        [alarmEntity]: { state: alarm, attributes: {} },
        [auxEntity]: { state: aux, attributes: {} },
      },
    };
  }, { entity: ENTITY, alarmEntity: ALARM, auxEntity: AUX, keypad, alarm, aux });
}

test("retained chime sequence establishes a baseline without replaying a stale chime", async ({ page }) => {
  await mountAudioCard(page);
  await installAudioSpies(page);
  await page.evaluate(({ entity, alarmEntity, auxEntity }) => {
    const card = document.getElementById("card");
    card._feedbackSnapshot = null;
    card.hass = {
      themes: { darkMode: false },
      states: {
        [entity]: {
          state: "FAULT 027 / FRONT DOOR",
          attributes: {
            ...card._hass.states[entity].attributes,
            ready: false,
            chime_sequence: 9,
            chime_zone: 27,
            chime_descriptor: "FRONT DOOR",
          },
        },
        [alarmEntity]: { state: "disarmed", attributes: {} },
        [auxEntity]: { state: "off", attributes: {} },
      },
    };
  }, { entity: ENTITY, alarmEntity: ALARM, auxEntity: AUX });
  const calls = await page.evaluate(() => window.__audioCalls.play);
  expect(calls).toEqual([]);
});

test("configured chime sequence change produces one chime profile", async ({ page }) => {
  await mountAudioCard(page);
  await installAudioSpies(page);
  await updateStates(page, { keypad: { chime_sequence: 1, chime_zone: 27, chime_descriptor: "FRONT DOOR" } });
  const calls = await page.evaluate(() => window.__audioCalls);
  expect(calls.play).toEqual(["chime"]);
});

test("fire loop has priority and silencing stops it", async ({ page }) => {
  await mountAudioCard(page);
  await installAudioSpies(page);
  await updateStates(page, { keypad: { fire_alarm: true, silenced: false, trouble: true, ready: false } });
  await updateStates(page, { keypad: { fire_alarm: true, silenced: true, trouble: true, ready: false } });
  const loops = await page.evaluate(() => window.__audioCalls.loops);
  expect(loops.at(-2)).toBe("fire");
  expect(loops.at(-1)).toBe(null);
});

test("external burglary and auxiliary entities select their continuous profiles", async ({ page }) => {
  await mountAudioCard(page);
  await installAudioSpies(page);
  await updateStates(page, { alarm: "triggered" });
  await updateStates(page, { aux: "on" });
  const loops = await page.evaluate(() => window.__audioCalls.loops);
  expect(loops).toContain("burglary");
  expect(loops.at(-1)).toBe("auxiliary");
});

test("trouble and supervisory rising edges use one-shot profiles", async ({ page }) => {
  await mountAudioCard(page);
  await installAudioSpies(page);
  await updateStates(page, { keypad: { trouble: true, ready: false } });
  await updateStates(page, { keypad: { trouble: true, supervisory: true, ready: false } });
  const calls = await page.evaluate(() => window.__audioCalls.play);
  expect(calls).toEqual(["trouble", "supervisory"]);
});

test("pointer-down starts key chirp and optional haptic feedback", async ({ page }) => {
  await mountAudioCard(page, { haptic: true });
  await installAudioSpies(page);
  await page.evaluate(() => {
    const card = document.getElementById("card");
    const key = card.shadowRoot.querySelector(".layout-compact-view button.physical-key");
    key.dispatchEvent(new PointerEvent("pointerdown", { bubbles: true, pointerId: 1 }));
  });
  const calls = await page.evaluate(() => window.__audioCalls);
  expect(calls.keypress).toBe(1);
  expect(calls.haptic).toBe(1);
});

test("sound and haptic feedback remain off by default", async ({ page }) => {
  await page.setContent('<vista-keypad-card id="card"></vista-keypad-card>');
  await page.evaluate(() => {
    if (!customElements.get("ha-card")) customElements.define("ha-card", class extends HTMLElement {});
  });
  await page.addScriptTag({ content: cardSource });
  const config = await page.evaluate((entity) => {
    const card = document.getElementById("card");
    card.setConfig({ entity });
    return { sound: card._config.sound, haptic: card._config.haptic };
  }, ENTITY);
  expect(config.sound.enabled).toBe(false);
  expect(config.haptic.enabled).toBe(false);
});


test("sound-enabled card exposes a small audio flag and any dashboard interaction can unlock it", async ({ page }) => {
  await mountAudioCard(page);
  await page.evaluate(() => {
    const card = document.getElementById("card");
    card._audio.ctx = { state: "suspended" };
    card._audio.unlock = async () => {
      card._audio.ctx = { state: "running" };
      return true;
    };
    card._syncAudioUnlockListener();
  });
  let hidden = await page.evaluate(() => document.getElementById("card").shadowRoot.getElementById("audio-lock-flag").hidden);
  expect(hidden).toBe(false);
  await page.dispatchEvent("body", "pointerdown");
  await page.waitForTimeout(20);
  hidden = await page.evaluate(() => document.getElementById("card").shadowRoot.getElementById("audio-lock-flag").hidden);
  expect(hidden).toBe(true);
});
