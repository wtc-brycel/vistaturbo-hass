from pathlib import Path

path = Path("frontend/vista-keypad-card.js")
text = path.read_text(encoding="utf-8")

replacements = [
    (
        'const VISTA_KEYPAD_CARD_VERSION = "0.3.21";',
        'const VISTA_KEYPAD_CARD_VERSION = "0.3.22";',
    ),
    (
        '''    this._config = {};
    this._hass = null;
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  setConfig(config) {
    this._config = cloneEditorConfig(config ?? {});
    this._render();
  }

  _emit(config) {
    this._config = cloneEditorConfig(config);
    this.dispatchEvent(new CustomEvent("config-changed", {
      detail: { config: this._config },
      bubbles: true,
      composed: true,
    }));
    this._render();
  }
''',
        '''    this._config = {};
    this._hass = null;
    this._rendered = false;
    this._hasHass = false;
  }

  set hass(hass) {
    const shouldRender = !this._rendered || !this._hasHass;
    this._hass = hass;
    this._hasHass = true;
    if (shouldRender) this._render();
  }

  setConfig(config) {
    const next = cloneEditorConfig(config ?? {});
    const changed = JSON.stringify(next) !== JSON.stringify(this._config);
    this._config = next;
    if (!this._rendered || changed) this._render();
  }

  _emit(config) {
    this._config = cloneEditorConfig(config);
    this.dispatchEvent(new CustomEvent("config-changed", {
      detail: { config: this._config },
      bubbles: true,
      composed: true,
    }));
  }
''',
    ),
    (
        '''    this.shadowRoot.querySelectorAll("[data-function]").forEach((el) => {
      el.addEventListener("change", () => this._functionLabel(el.dataset.function, el.value));
    });
  }
}

class VistaKeypadCard extends HTMLElement {
''',
        '''    this.shadowRoot.querySelectorAll("[data-function]").forEach((el) => {
      el.addEventListener("change", () => this._functionLabel(el.dataset.function, el.value));
    });
    this._rendered = true;
  }
}

class VistaKeypadCard extends HTMLElement {
''',
    ),
    (
        '''    this._config = {};
    this._hass = null;
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  setConfig(config) {
    this._config = { ...(config ?? {}) };
    this._render();
  }

  _emit(name, value) {
''',
        '''    this._config = {};
    this._hass = null;
    this._rendered = false;
    this._hasHass = false;
  }

  set hass(hass) {
    const shouldRender = !this._rendered || !this._hasHass;
    this._hass = hass;
    this._hasHass = true;
    if (shouldRender) this._render();
  }

  setConfig(config) {
    const next = { ...(config ?? {}) };
    const changed = JSON.stringify(next) !== JSON.stringify(this._config);
    this._config = next;
    if (!this._rendered || changed) this._render();
  }

  _emit(name, value) {
''',
    ),
    (
        '''    this.dispatchEvent(new CustomEvent("config-changed", {
      detail: { config: next },
      bubbles: true,
      composed: true,
    }));
    this._render();
  }

  _render() {
''',
        '''    this.dispatchEvent(new CustomEvent("config-changed", {
      detail: { config: next },
      bubbles: true,
      composed: true,
    }));
  }

  _render() {
''',
    ),
    (
        '''    this.shadowRoot.querySelectorAll("[data-field]").forEach((el) => {
      el.addEventListener("change", () => {
        let value;
        if (el.type === "checkbox") value = el.checked;
        else if (el.dataset.number) value = Number(el.value);
        else if (el.dataset.field === "partition") value = Number(el.value);
        else value = el.value;
        this._emit(el.dataset.field, value);
      });
    });
  }
}

class VistaEventLogCard extends HTMLElement {
''',
        '''    this.shadowRoot.querySelectorAll("[data-field]").forEach((el) => {
      el.addEventListener("change", () => {
        let value;
        if (el.type === "checkbox") value = el.checked;
        else if (el.dataset.number) value = Number(el.value);
        else if (el.dataset.field === "partition") value = Number(el.value);
        else value = el.value;
        this._emit(el.dataset.field, value);
      });
    });
    this._rendered = true;
  }
}

class VistaEventLogCard extends HTMLElement {
''',
    ),
]

for old, new in replacements:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"Expected exactly one patch anchor, found {count}: {old[:100]!r}")
    text = text.replace(old, new, 1)

path.write_text(text, encoding="utf-8")
print("Patched visual editors for focus stability and bumped card to 0.3.22")
