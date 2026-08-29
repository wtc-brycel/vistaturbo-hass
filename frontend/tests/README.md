# Frontend browser tests

The Playwright suite renders the real `vista-keypad-card` custom element in Chromium.

- `render.spec.mjs` covers responsive Lovelace layout, model profiles, touch-target sizing, forced layouts, theme-aware case colors, and grid sizing.
- `audio.spec.mjs` covers optional feedback defaults, configured-zone chime sequence transitions, stale retained chime suppression, fire/silence loop behavior, burglary and auxiliary loop selection, trouble/supervisory one-shot sounds, and pointer-down keypress/haptic dispatch.
- `security.spec.mjs` covers unavailable-source rendering, stale attribute suppression, disabled controls, CSS color validation, and bounded entity-editor suggestions with a large synthetic registry.

Run locally from `frontend/` with:

```sh
npm ci
npx playwright install chromium
npm run test:render
```
