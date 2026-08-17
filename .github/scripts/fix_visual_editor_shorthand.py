from pathlib import Path

p = Path("frontend/vista-keypad-card.js")
s = p.read_text()
s = s.replace(
    '    const caseColor = String(this._config.case_color ?? "auto").toLowerCase();\n    const soundInput = this._config.sound && typeof this._config.sound === "object" ? this._config.sound : {};\n',
    '    const requestedCaseColor = String(this._config.case_color ?? "auto").toLowerCase();\n    const caseColor = requestedCaseColor === "auto" || CASE_COLORS.has(requestedCaseColor) ? requestedCaseColor : "auto";\n    const soundInput = this._config.sound === true\n      ? { enabled: true }\n      : this._config.sound && typeof this._config.sound === "object" ? this._config.sound : {};\n',
    1,
)
s = s.replace(
    '    const hapticInput = this._config.haptic && typeof this._config.haptic === "object" ? this._config.haptic : {};\n',
    '    const hapticInput = this._config.haptic === true\n      ? { enabled: true }\n      : this._config.haptic && typeof this._config.haptic === "object" ? this._config.haptic : {};\n',
    1,
)
p.write_text(s)

p = Path("frontend/tests/render.spec.mjs")
s = p.read_text()
s += r'''

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
'''
p.write_text(s)
