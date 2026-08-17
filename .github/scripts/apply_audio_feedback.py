from pathlib import Path

p = Path("frontend/vista-keypad-card.js")
s = p.read_text()

s = s.replace('const VISTA_KEYPAD_CARD_VERSION = "0.3.15";', 'const VISTA_KEYPAD_CARD_VERSION = "0.3.16";', 1)

start = s.index("class VistaKeypadAudio {")
end = s.index("class VistaKeypadCard extends HTMLElement {")
audio_classes = r'''/*
 * Synthesized keypad feedback. Cadences are intentionally modeled after
 * conventional VISTA keypad behavior, but exact factory piezo frequencies are
 * not published. Keeping the profiles synthesized avoids fetch/decode latency.
 */
const KEYPAD_SOUND_PROFILES = {
  keypress: { steps: [[1450, 38, 0]] },
  chime: { steps: [[1200, 75, 70], [1200, 75, 70], [1200, 90, 0]] },
  trouble: { steps: [[1000, 110, 85], [1000, 110, 0]] },
  supervisory: { steps: [[900, 120, 75], [700, 120, 0]] },
  auxiliary: { loop: true, steps: [[900, 250, 35], [650, 250, 35]] },
  fire: { loop: true, steps: [[1000, 500, 500], [1000, 500, 500], [1000, 500, 1500]] },
  burglary: { loop: true, continuous: true, frequency: 950 },
};

class VistaKeypadAudio {
  constructor() {
    this.ctx = null;
    this._loopName = null;
    this._loopSignature = "";
    this._loopTimer = null;
    this._loopNodes = new Set();
    this._desiredLoop = null;
    this._desiredConfig = null;
  }

  _context() {
    if (this.ctx) return this.ctx;
    const AudioCtx = window.AudioContext || window.webkitAudioContext;
    if (!AudioCtx) return null;
    try {
      this.ctx = new AudioCtx({ latencyHint: "interactive" });
    } catch (_) {
      this.ctx = new AudioCtx();
    }
    return this.ctx;
  }

  async unlock() {
    const ctx = this._context();
    if (!ctx) return false;
    if (ctx.state === "suspended") {
      try { await ctx.resume(); } catch (_) { return false; }
    }
    const ready = ctx.state === "running";
    if (ready && this._desiredLoop && this._loopName !== this._desiredLoop) {
      this._startLoopNow(this._desiredLoop, this._desiredConfig ?? {});
    }
    return ready;
  }

  _volume(config, profileName) {
    if (profileName === "keypress") {
      return Math.max(0, Math.min(1, Number(config.keypress_volume ?? config.volume ?? 0.035)));
    }
    return Math.max(0, Math.min(1, Number(config.alarm_volume ?? 0.065)));
  }

  _scheduleTone(frequency, durationMs, volume, startAt, targetSet = null) {
    const ctx = this._context();
    if (!ctx || ctx.state !== "running") return null;

    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    const start = Math.max(ctx.currentTime, startAt ?? ctx.currentTime);
    const duration = Math.max(0.015, Number(durationMs || 0) / 1000);
    const stop = start + duration;

    osc.type = "square";
    osc.frequency.setValueAtTime(Math.max(80, Number(frequency) || 1000), start);
    gain.gain.setValueAtTime(0.0001, start);
    gain.gain.exponentialRampToValueAtTime(Math.max(volume, 0.0002), start + 0.002);
    gain.gain.setValueAtTime(Math.max(volume, 0.0002), Math.max(start + 0.003, stop - 0.004));
    gain.gain.exponentialRampToValueAtTime(0.0001, stop);

    osc.connect(gain).connect(ctx.destination);
    if (targetSet) targetSet.add(osc);
    osc.addEventListener?.("ended", () => targetSet?.delete(osc), { once: true });
    osc.start(start);
    osc.stop(stop + 0.004);
    return osc;
  }

  _scheduleProfile(name, config = {}, targetSet = null) {
    const ctx = this._context();
    const profile = KEYPAD_SOUND_PROFILES[name];
    if (!ctx || ctx.state !== "running" || !profile) return 0;

    const volume = this._volume(config, name);
    let at = ctx.currentTime + 0.002;
    let totalMs = 0;
    const steps = name === "keypress" && (config.frequency || config.duration_ms)
      ? [[Number(config.frequency ?? 1450), Number(config.duration_ms ?? 38), 0]]
      : profile.steps ?? [];

    for (const [frequency, durationMs, gapMs] of steps) {
      this._scheduleTone(frequency, durationMs, volume, at, targetSet);
      const stepMs = Number(durationMs || 0) + Number(gapMs || 0);
      totalMs += stepMs;
      at += stepMs / 1000;
    }
    return totalMs;
  }

  async keypress(config = {}) {
    if (!config.enabled || config.keypress === false) return false;
    if (!(await this.unlock())) return false;
    this._scheduleProfile("keypress", config);
    return true;
  }

  async play(name, config = {}) {
    if (!config.enabled) return false;
    if (!(await this.unlock())) return false;
    if (!KEYPAD_SOUND_PROFILES[name] || KEYPAD_SOUND_PROFILES[name].loop) return false;
    this._scheduleProfile(name, config);
    return true;
  }

  setLoop(name, config = {}) {
    const enabled = Boolean(config.enabled && config.state_sounds);
    const next = enabled && name && KEYPAD_SOUND_PROFILES[name]?.loop ? name : null;
    this._desiredLoop = next;
    this._desiredConfig = config;

    if (!next) {
      this.stopLoop();
      return;
    }

    const signature = JSON.stringify([next, this._volume(config, next)]);
    if (this._loopName === next && this._loopSignature === signature) return;

    const ctx = this._context();
    if (ctx?.state === "running") this._startLoopNow(next, config);
  }

  _startLoopNow(name, config = {}) {
    this.stopLoop(false);
    const ctx = this._context();
    const profile = KEYPAD_SOUND_PROFILES[name];
    if (!ctx || ctx.state !== "running" || !profile?.loop) return;

    this._loopName = name;
    this._loopSignature = JSON.stringify([name, this._volume(config, name)]);

    if (profile.continuous) {
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      const now = ctx.currentTime;
      const volume = this._volume(config, name);
      osc.type = "square";
      osc.frequency.setValueAtTime(profile.frequency ?? 950, now);
      gain.gain.setValueAtTime(0.0001, now);
      gain.gain.exponentialRampToValueAtTime(Math.max(volume, 0.0002), now + 0.008);
      osc.connect(gain).connect(ctx.destination);
      this._loopNodes.add(osc);
      osc.start(now);
      return;
    }

    const scheduleCycle = () => {
      if (this._loopName !== name || this._desiredLoop !== name) return;
      const cycleMs = this._scheduleProfile(name, config, this._loopNodes);
      this._loopTimer = setTimeout(scheduleCycle, Math.max(50, cycleMs - 15));
    };
    scheduleCycle();
  }

  stopLoop(clearDesired = true) {
    clearTimeout(this._loopTimer);
    this._loopTimer = null;
    for (const node of this._loopNodes) {
      try { node.stop(); } catch (_) {}
    }
    this._loopNodes.clear();
    this._loopName = null;
    this._loopSignature = "";
    if (clearDesired) {
      this._desiredLoop = null;
      this._desiredConfig = null;
    }
  }

  stopAll() {
    this.stopLoop();
  }
}

class VistaKeypadHaptics {
  pulse(config = {}) {
    if (!config.enabled || typeof navigator === "undefined" || typeof navigator.vibrate !== "function") {
      return false;
    }
    try {
      return navigator.vibrate(Math.max(1, Math.min(100, Number(config.keypress_ms ?? 10))));
    } catch (_) {
      return false;
    }
  }

  stop() {
    try { navigator.vibrate?.(0); } catch (_) {}
  }
}
'''
s = s[:start] + audio_classes + s[end:]

s = s.replace(
    '''    this._audio = new VistaKeypadAudio();\n  }''',
    '''    this._audio = new VistaKeypadAudio();\n    this._haptics = new VistaKeypadHaptics();\n    this._feedbackSnapshot = null;\n  }''',
    1,
)
s = s.replace(
    '''    clearTimeout(this._pressTimer);\n  }''',
    '''    clearTimeout(this._pressTimer);\n    this._audio.stopAll();\n    this._haptics.stop();\n  }''',
    1,
)
s = s.replace(
    '''      layout: "auto",\n      read_only: true,\n    };''',
    '''      layout: "auto",\n      read_only: true,\n      sound: { enabled: false },\n      haptic: { enabled: false },\n    };''',
    1,
)

anchor = '''    const dayCaseColor = normalizeOptionalCaseColor(config.day_case_color, "day_case_color");\n    const nightCaseColor = normalizeOptionalCaseColor(config.night_case_color, "night_case_color");\n'''
sound_setup = anchor + '''\n    const soundInput = config.sound === true\n      ? { enabled: true }\n      : config.sound && typeof config.sound === "object"\n        ? config.sound\n        : {};\n    const sound = {\n      enabled: false,\n      keypress: true,\n      state_sounds: false,\n      volume: 0.035,\n      alarm_volume: 0.065,\n      trouble: true,\n      supervisory: true,\n      chime: true,\n      alarm_entity: null,\n      aux_entity: null,\n      ...soundInput,\n    };\n    const hapticInput = config.haptic === true\n      ? { enabled: true }\n      : config.haptic && typeof config.haptic === "object"\n        ? config.haptic\n        : {};\n    const haptic = { enabled: false, keypress_ms: 10, ...hapticInput };\n'''
if anchor not in s:
    raise SystemExit("missing sound config anchor")
s = s.replace(anchor, sound_setup, 1)
s = s.replace('''      sound: { enabled: false },\n      ...config,''', '''      sound,\n      haptic,\n      ...config,''', 1)
s = s.replace(
    '''      night_case_color: nightCaseColor,\n    };\n    this._lastRenderSignature = null;\n    this._render();''',
    '''      night_case_color: nightCaseColor,\n      sound,\n      haptic,\n    };\n    this._feedbackSnapshot = null;\n    this._lastRenderSignature = null;\n    this._syncFeedback();\n    this._render();''',
    1,
)
s = s.replace(
    '''  set hass(hass) {\n    this._hass = hass;\n    const signature = this._renderSignature(hass);''',
    '''  set hass(hass) {\n    this._hass = hass;\n    this._syncFeedback();\n    const signature = this._renderSignature(hass);''',
    1,
)
s = s.replace(
    '''      a.supervisory ?? null,\n      hass?.themes?.darkMode ?? null,''',
    '''      a.supervisory ?? null,\n      a.chime_sequence ?? null,\n      a.chime_zone ?? null,\n      a.chime_descriptor ?? null,\n      hass?.themes?.darkMode ?? null,''',
    1,
)

anchor = '''  _resolvedCaseColor(model) {\n'''
feedback_methods = r'''  _entityActive(entityId, activeStates = ["on", "triggered", "alarm", "active"]) {
    const entity = this._entityState(entityId);
    if (!entity) return false;
    return activeStates.includes(String(entity.state ?? "").toLowerCase());
  }

  _feedbackState(display) {
    return {
      ready: display.ready,
      armed: display.armed,
      trouble: display.trouble,
      fireAlarm: display.fireAlarm,
      silenced: display.silenced,
      supervisory: display.supervisory,
      chimeSequence: display.chimeSequence,
    };
  }

  _syncFeedback() {
    const sound = this._config?.sound ?? {};
    const display = this._config ? this._displayState() : null;
    if (!display) return;

    let loop = null;
    if (sound.enabled && sound.state_sounds) {
      if (display.fireAlarm === true && display.silenced !== true) {
        loop = "fire";
      } else if (this._entityActive(sound.alarm_entity, ["triggered", "alarm", "on"])) {
        loop = "burglary";
      } else if (this._entityActive(sound.aux_entity)) {
        loop = "auxiliary";
      }
    }
    this._audio.setLoop(loop, sound);

    const current = this._feedbackState(display);
    const previous = this._feedbackSnapshot;
    this._feedbackSnapshot = current;
    if (!previous || !sound.enabled || !sound.state_sounds || loop) return;

    if (sound.chime !== false && current.chimeSequence !== previous.chimeSequence) {
      this._audio.play("chime", sound).catch(() => {});
      return;
    }
    if (sound.supervisory !== false && !previous.supervisory && current.supervisory) {
      this._audio.play("supervisory", sound).catch(() => {});
      return;
    }
    if (sound.trouble !== false && !previous.trouble && current.trouble) {
      this._audio.play("trouble", sound).catch(() => {});
    }
  }

  async _keyPressFeedback() {
    const sound = this._config?.sound ?? {};
    const haptic = this._config?.haptic ?? {};
    this._haptics.pulse(haptic);
    await this._audio.keypress(sound).catch(() => false);
    this._syncFeedback();
  }

'''
if anchor not in s:
    raise SystemExit("missing feedback method anchor")
s = s.replace(anchor, feedback_methods + anchor, 1)

s = s.replace(
    '''        supervisory: null,\n        flashing: {''',
    '''        supervisory: null,\n        chimeSequence: 0,\n        chimeZone: null,\n        chimeDescriptor: "",\n        flashing: {''',
    1,
)
s = s.replace(
    '''      supervisory: indicator("supervisory", "supervisory", null),\n      flashing: {''',
    '''      supervisory: indicator("supervisory", "supervisory", null),\n      chimeSequence: Number(a.chime_sequence ?? 0) || 0,\n      chimeZone: a.chime_zone ?? null,\n      chimeDescriptor: String(a.chime_descriptor ?? ""),\n      flashing: {''',
    1,
)
s = s.replace(
    '''      button.addEventListener("pointerdown", () => button.classList.add("pressed"));''',
    '''      button.addEventListener("pointerdown", () => {\n        button.classList.add("pressed");\n        this._keyPressFeedback();\n      });''',
    1,
)
s = s.replace('''\n    this._audio.beep(this._config?.sound ?? {}).catch(() => {});\n''', '\n', 1)

p.write_text(s)
