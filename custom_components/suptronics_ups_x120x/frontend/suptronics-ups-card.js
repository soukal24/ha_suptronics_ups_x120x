/**
 * Suptronics UPS card.
 *
 * A self-contained Lovelace card for the Suptronics X120x UPS, served and
 * registered by the integration itself, so no dashboard resource has to be
 * added by hand.
 *
 * Derived from the X120X UPS card by mesgas (MIT), see THIRD_PARTY_NOTICES.md.
 *
 * Configuration is optional: with nothing given the card finds the UPS and
 * recognises each entity by the `ups_role` attribute the integration puts on
 * it, so renames and other languages do not matter.
 *
 *   type: custom:suptronics-ups-card
 *   variant: full | compact | slim | gauge   (default: full)
 *   name: optional title override
 *   hours: how far back the sparkline looks (default 24)
 *   language: en | cs (default: the language Home Assistant is set to)
 *   show_flow / show_sparkline / show_chips / show_button:
 *       force a single block on or off, whatever the variant decided
 *   entities: optional explicit overrides, keyed by the roles below
 */

const CARD_VERSION = "3.0.0";
const PLATFORM = "suptronics_ups_x120x";
const CARD_TYPE = "suptronics-ups-card";

const REDUCED_MOTION = window.matchMedia("(prefers-reduced-motion: reduce)");

/** Count a number element up or down to its new value. */
function tweenNumber(element, to, format, duration = 650) {
  const previous = Number(element.dataset.value);
  element.dataset.value = String(to);

  if (element._tween) {
    cancelAnimationFrame(element._tween);
    element._tween = null;
  }
  if (REDUCED_MOTION.matches || !Number.isFinite(previous) || previous === to) {
    element.textContent = format(to);
    return;
  }

  const start = performance.now();
  const step = (now) => {
    const progress = Math.min(1, (now - start) / duration);
    const eased = 1 - Math.pow(1 - progress, 3);
    element.textContent = format(previous + (to - previous) * eased);
    element._tween = progress < 1 ? requestAnimationFrame(step) : null;
  };
  element._tween = requestAnimationFrame(step);
}

console.info(
  `%c SUPTRONICS-UPS-CARD %c ${CARD_VERSION} `,
  "color:#0b1020;background:#4fd1c5;font-weight:700;border-radius:3px 0 0 3px",
  "color:#4fd1c5;background:#0b1020;border-radius:0 3px 3px 0"
);

/**
 * The role of every entity is the `ups_role` attribute the integration sets,
 * which is the entity's translation key. These are the ones the card uses.
 */
const ROLES = {
  status: "ups_status",
  level: "battery_state",
  capacity: "battery",
  voltage: "battery_voltage",
  ac: "ac_power",
  charging: "battery_charging",
  low: "battery_low",
  charge_switch: "charging",
  runtime: "runtime_estimate",
  on_battery: "time_on_battery",
  countdown: "shutdown_countdown",
  shutdown_switch: "auto_shutdown",
};

const STATUS_THEME = {
  online: { tint: "#3ddc97" },
  charging: { tint: "#4fd1c5" },
  on_battery: { tint: "#f6c445" },
  low_battery: { tint: "#ff5c5c" },
  shutting_down: { tint: "#ff5c5c" },
  unknown: { tint: "#8a94a6" },
};

/**
 * The card's own texts. Entity states come already translated from the
 * frontend; these are the labels the card adds around them.
 */
const STRINGS = {
  en: {
    status_online: "On line",
    status_charging: "Charging",
    status_on_battery: "On battery",
    status_low_battery: "Battery low",
    status_shutting_down: "Shutting down",
    status_unknown: "Unknown",
    countdown: "Shutdown in {seconds} s",
    mains: "Mains",
    ups: "UPS",
    pi: "Pi",
    mains_ok: "Mains OK",
    mains_lost: "Mains lost",
    charging: "Charging",
    not_charging: "Not charging",
    discharging: "Discharging",
    battery_low: "Battery low",
    battery_healthy: "Battery healthy",
    hold: "Hold {min}-{max}%",
    runtime: "~{time} left",
    on_battery_for: "On battery {time}",
    auto_shutdown: "Auto shutdown on",
    minutes_short: "min",
    hours_short: "h",
    charging_enabled: "Charging enabled",
    charging_paused: "Charging paused",
    empty:
      "No Suptronics UPS found yet. If the integration is set up, reload the dashboard; otherwise name the entities explicitly in the card config.",
  },
  cs: {
    status_online: "Na síti",
    status_charging: "Nabíjí se",
    status_on_battery: "Na baterii",
    status_low_battery: "Slabá baterie",
    status_shutting_down: "Vypíná se",
    status_unknown: "Neznámý",
    countdown: "Vypnutí za {seconds} s",
    mains: "Síť",
    ups: "UPS",
    pi: "Pi",
    mains_ok: "Síť OK",
    mains_lost: "Výpadek sítě",
    charging: "Nabíjí se",
    not_charging: "Nenabíjí se",
    discharging: "Vybíjí se",
    battery_low: "Slabá baterie",
    battery_healthy: "Baterie v pořádku",
    hold: "Držet {min}–{max} %",
    runtime: "Výdrž ~{time}",
    on_battery_for: "Na baterii {time}",
    auto_shutdown: "Auto vypnutí zapnuto",
    minutes_short: "min",
    hours_short: "h",
    charging_enabled: "Nabíjení povoleno",
    charging_paused: "Nabíjení pozastaveno",
    empty:
      "Zařízení Suptronics UPS zatím nebylo nalezeno. Pokud je integrace nastavená, obnovte dashboard; jinak zadejte entity v konfiguraci karty ručně.",
  },
};

const GAUGE_RADIUS = 78;
const GAUGE_CIRCUMFERENCE = 2 * Math.PI * GAUGE_RADIUS;
const WINDOW_RADIUS = 92;
const WINDOW_CIRCUMFERENCE = 2 * Math.PI * WINDOW_RADIUS;
const HISTORY_POINTS = 48;

const DEFAULT_HISTORY_HOURS = 24;
const HISTORY_REFRESH_MS = 5 * 60 * 1000;

const VARIANTS = {
  full: { flow: true, sparkline: true, chips: true, button: true },
  compact: { flow: false, sparkline: false, chips: true, button: true },
  slim: { flow: false, sparkline: false, chips: true, button: false },
  gauge: { flow: false, sparkline: false, chips: false, button: false },
};

const CELL_TOP = 21.5;
const CELL_HEIGHT = 57;

class SuptronicsUpsCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._config = {};
    this._entities = null;
    this._history = [];
    this._recorded = null;
    this._historyAt = 0;
    this._fetching = false;
    this._built = false;
  }

  static getStubConfig() {
    return { type: `custom:${CARD_TYPE}` };
  }

  setConfig(config) {
    const variant = config.variant || "full";
    if (!VARIANTS[variant]) {
      throw new Error(
        `${CARD_TYPE}: unknown variant "${variant}". ` +
          `Use one of: ${Object.keys(VARIANTS).join(", ")}`
      );
    }
    this._config = { ...config, variant };
    this._entities = null;
    this._built = false;
    this.shadowRoot.innerHTML = "";
  }

  _parts() {
    const defaults = VARIANTS[this._config.variant];
    const resolve = (key) => {
      const override = this._config[`show_${key}`];
      return override === undefined ? defaults[key] : Boolean(override);
    };
    return {
      flow: resolve("flow"),
      sparkline: resolve("sparkline"),
      chips: resolve("chips"),
      button: resolve("button"),
    };
  }

  getCardSize() {
    const parts = VARIANTS[this._config.variant] || VARIANTS.full;
    return parts.flow ? 5 : parts.chips ? 3 : 2;
  }

  set hass(hass) {
    this._hass = hass;
    if (!this._built) {
      this._build();
    }
    this._update();
    if (
      this._shown &&
      this._shown.sparkline &&
      Date.now() - this._historyAt > HISTORY_REFRESH_MS
    ) {
      this._fetchHistory();
    }
  }

  /* ---------------------------------------------------------------- i18n */

  _language() {
    const configured = this._config.language;
    const hass = this._hass || {};
    const raw =
      configured || (hass.locale && hass.locale.language) || hass.language || "en";
    const code = String(raw).toLowerCase().split(/[-_]/)[0];
    return STRINGS[code] ? code : "en";
  }

  _t(key, values = {}) {
    const table = STRINGS[this._language()];
    let text = (table && table[key]) || STRINGS.en[key] || key;
    for (const [name, value] of Object.entries(values)) {
      text = text.replace(`{${name}}`, value);
    }
    return text;
  }

  /** "45 min" or "2 h 10 min", from minutes. */
  _duration(minutes) {
    const total = Math.max(0, Math.round(minutes));
    const h = Math.floor(total / 60);
    const m = total % 60;
    if (h === 0) return `${m} ${this._t("minutes_short")}`;
    if (m === 0) return `${h} ${this._t("hours_short")}`;
    return `${h} ${this._t("hours_short")} ${m} ${this._t("minutes_short")}`;
  }

  /* ------------------------------------------------------------- history */

  async _fetchHistory() {
    const entityId = this._entities && this._entities.capacity;
    if (this._fetching || !this._hass || !entityId) return;
    this._fetching = true;
    this._historyAt = Date.now();
    try {
      const hours = Number(this._config.hours) || DEFAULT_HISTORY_HOURS;
      const end = new Date();
      const start = new Date(end.getTime() - hours * 3600 * 1000);
      const response = await this._hass.callWS({
        type: "history/history_during_period",
        start_time: start.toISOString(),
        end_time: end.toISOString(),
        entity_ids: [entityId],
        minimal_response: true,
        no_attributes: true,
      });
      this._recorded = this._bucket(
        response?.[entityId] || [],
        start.getTime(),
        end.getTime()
      );
      if (this._built) this._drawSparkline();
    } catch (err) {
      console.warn(`${CARD_TYPE}: could not read history`, err);
      this._recorded = null;
    } finally {
      this._fetching = false;
    }
  }

  _bucket(raw, startMs, endMs) {
    const span = Math.max(endMs - startMs, 1);
    const sums = new Array(HISTORY_POINTS).fill(0);
    const counts = new Array(HISTORY_POINTS).fill(0);

    for (const entry of raw) {
      const value = Number(entry.s ?? entry.state);
      if (!Number.isFinite(value)) continue;
      const seconds = entry.lu ?? entry.lc;
      const stamp =
        typeof seconds === "number"
          ? seconds * 1000
          : Date.parse(entry.last_updated ?? entry.last_changed);
      if (!Number.isFinite(stamp)) continue;
      const index = Math.min(
        HISTORY_POINTS - 1,
        Math.max(0, Math.floor(((stamp - startMs) / span) * HISTORY_POINTS))
      );
      sums[index] += value;
      counts[index] += 1;
    }

    const series = [];
    let last = null;
    for (let i = 0; i < HISTORY_POINTS; i += 1) {
      if (counts[i]) last = sums[i] / counts[i];
      if (last !== null) series.push(last);
    }
    return series;
  }

  /* --------------------------------------------------------------- lookup */

  _resolveEntities() {
    const resolved = { ...(this._config.entities || {}) };
    const missing = Object.keys(ROLES).filter((role) => !resolved[role]);
    if (missing.length === 0) {
      return resolved;
    }

    const registry = this._hass.entities;
    if (!registry) {
      return Object.keys(resolved).length ? resolved : null;
    }

    const ours = [];
    for (const [entityId, entry] of Object.entries(registry)) {
      if (entry.platform !== PLATFORM) continue;
      if (this._config.device_id && entry.device_id !== this._config.device_id) {
        continue;
      }
      ours.push(entityId);
      if (entry.device_id && !this._deviceId) this._deviceId = entry.device_id;
    }
    if (ours.length === 0) return null;

    for (const entityId of ours) {
      const state = this._hass.states[entityId];
      if (!state) continue;
      const role = state.attributes.ups_role;
      for (const key of missing) {
        if (!resolved[key] && ROLES[key] === role) {
          resolved[key] = entityId;
          break;
        }
      }
    }
    return resolved;
  }

  _state(role) {
    const entityId = this._entities && this._entities[role];
    if (!entityId) return null;
    return this._hass.states[entityId] || null;
  }

  _number(role, fallback = null) {
    const state = this._state(role);
    if (!state) return fallback;
    const value = Number(state.state);
    return Number.isFinite(value) ? value : fallback;
  }

  _isOn(role) {
    const state = this._state(role);
    return state ? state.state === "on" : false;
  }

  /* ---------------------------------------------------------------- build */

  _build() {
    this._entities = this._resolveEntities();

    const style = document.createElement("style");
    style.textContent = STYLES;
    const card = document.createElement("ha-card");
    card.className = "ups";
    this.shadowRoot.innerHTML = "";
    this.shadowRoot.append(style, card);

    if (!this._entities || !this._entities.capacity) {
      card.innerHTML = `<div class="empty">
        <div class="empty-title">Suptronics UPS</div>
        <p>${this._t("empty")}</p>
      </div>`;
      return;
    }

    card.innerHTML = TEMPLATE;

    this._el = {};
    for (const node of card.querySelectorAll("[data-ref]")) {
      this._el[node.dataset.ref] = node;
    }

    this._el.mainsLabel.textContent = this._t("mains");
    this._el.upsLabel.textContent = this._t("ups");
    this._el.piLabel.textContent = this._t("pi");

    this._el.gaugeValue.setAttribute(
      "stroke-dasharray",
      `${GAUGE_CIRCUMFERENCE} ${GAUGE_CIRCUMFERENCE}`
    );
    this._el.gaugeValue.setAttribute("stroke-dashoffset", GAUGE_CIRCUMFERENCE);

    this._shown = this._parts();
    card.dataset.variant = this._config.variant;
    this._el.flow.toggleAttribute("hidden", !this._shown.flow);
    this._el.sparkSvg.toggleAttribute("hidden", !this._shown.sparkline);
    this._el.chips.toggleAttribute("hidden", !this._shown.chips);

    for (const node of card.querySelectorAll("[data-role]")) {
      node.addEventListener("click", () => {
        const entityId = this._entities[node.dataset.role];
        if (!entityId) return;
        const event = new Event("hass-more-info", {
          bubbles: true,
          composed: true,
        });
        event.detail = { entityId };
        this.dispatchEvent(event);
      });
    }

    this._el.chargeToggle.addEventListener("click", (ev) => {
      ev.stopPropagation();
      const entityId = this._entities.charge_switch;
      if (!entityId) return;
      this._hass.callService("switch", "toggle", { entity_id: entityId });
    });

    this._built = true;
  }

  /* --------------------------------------------------------------- update */

  _update() {
    if (!this._built || !this._el) return;

    const capacity = this._number("capacity", 0);
    const voltage = this._number("voltage");
    const acOn = this._isOn("ac");
    const charging = this._isOn("charging");
    const low = this._isOn("low");
    const statusState = this._state("status");
    const statusKey =
      statusState && STATUS_THEME[statusState.state] ? statusState.state : "unknown";
    const theme = STATUS_THEME[statusKey];
    const countdown = this._number("countdown");

    this.style.setProperty("--x-tint", theme.tint);

    // --- headline ---------------------------------------------------------
    this._el.title.textContent =
      this._config.name || this._deviceName() || "Suptronics UPS";
    if (statusKey === "shutting_down" && countdown !== null) {
      this._el.statusText.textContent = this._t("countdown", {
        seconds: Math.round(countdown),
      });
    } else {
      this._el.statusText.textContent = statusState
        ? this._displayState(statusState)
        : this._t(`status_${statusKey}`);
    }

    // --- gauge ------------------------------------------------------------
    const clamped = Math.max(0, Math.min(100, capacity));
    this._el.gaugeValue.setAttribute(
      "stroke-dashoffset",
      GAUGE_CIRCUMFERENCE * (1 - clamped / 100)
    );
    const decimals = Math.round(clamped * 10) % 10 === 0 ? 0 : 1;
    tweenNumber(this._el.percent, clamped, (value) => value.toFixed(decimals));
    this._el.voltage.textContent =
      voltage === null ? "--" : `${voltage.toFixed(2)} V`;

    const levelState = this._state("level");
    this._el.levelText.textContent = levelState
      ? this._displayState(levelState)
      : "";

    this._renderChargeWindow();

    // --- battery cell -----------------------------------------------------
    const fill = (CELL_HEIGHT * clamped) / 100;
    this._el.cellFill.setAttribute("y", CELL_TOP + CELL_HEIGHT - fill);
    this._el.cellFill.setAttribute("height", Math.max(fill, 0.5));

    this.classList.toggle("is-charging", charging);
    this.classList.toggle(
      "is-alert",
      low || statusKey === "low_battery" || statusKey === "shutting_down"
    );

    // --- flow lane --------------------------------------------------------
    this._el.flow.dataset.direction = acOn ? "in" : "out";
    this._el.mains.classList.toggle("off", !acOn);

    // --- chips ------------------------------------------------------------
    this._setChip("chipAc", this._t(acOn ? "mains_ok" : "mains_lost"), acOn);
    this._setChip(
      "chipCharge",
      this._t(charging ? "charging" : acOn ? "not_charging" : "discharging"),
      charging || acOn
    );
    this._setChip("chipLow", this._t(low ? "battery_low" : "battery_healthy"), !low);

    // Runtime estimate: always shown when the integration has one.
    const runtime = this._number("runtime");
    this._setChip(
      "chipRuntime",
      runtime === null ? null : this._t("runtime", { time: this._duration(runtime) }),
      runtime === null || runtime > 30
    );
    // Time on battery: only while the mains are gone.
    const onBattery = this._number("on_battery");
    this._setChip(
      "chipOnBattery",
      !acOn && onBattery !== null
        ? this._t("on_battery_for", { time: this._duration(onBattery) })
        : null,
      false
    );
    // Automatic shutdown armed.
    this._setChip(
      "chipShutdown",
      this._isOn("shutdown_switch") ? this._t("auto_shutdown") : null,
      true
    );

    const chargeSwitch = this._state("charge_switch");
    if (chargeSwitch && this._shown.button) {
      const on = chargeSwitch.state === "on";
      this._el.chargeToggle.hidden = false;
      this._el.chargeToggle.dataset.on = String(on);
      this._el.chargeToggle.textContent = this._t(
        on ? "charging_enabled" : "charging_paused"
      );
    } else {
      this._el.chargeToggle.hidden = true;
    }

    if (this._shown.sparkline) {
      this._pushHistory(clamped);
      this._drawSparkline();
    }
  }

  _renderChargeWindow() {
    const arc = this._el.gaugeWindow;
    const chip = this._el.chipWindow;
    const attrs = (this._state("charge_switch") || {}).attributes || {};
    const min = Number(attrs.charge_limit_min);
    const max = Number(attrs.charge_limit_max);

    const limited =
      Number.isFinite(min) && Number.isFinite(max) && max < 100 && max > min;

    if (!limited) {
      if (arc) arc.style.opacity = "0";
      if (chip) chip.hidden = true;
      return;
    }

    const length = (WINDOW_CIRCUMFERENCE * (max - min)) / 100;
    arc.setAttribute("stroke-dasharray", `${length} ${WINDOW_CIRCUMFERENCE - length}`);
    arc.setAttribute("stroke-dashoffset", -(WINDOW_CIRCUMFERENCE * min) / 100);
    arc.style.opacity = "1";

    chip.hidden = false;
    chip.querySelector(".chip-text").textContent = this._t("hold", {
      min: Math.round(min),
      max: Math.round(max),
    });
  }

  /** Text null hides the chip. */
  _setChip(ref, text, good) {
    const chip = this._el[ref];
    if (!chip) return;
    if (text === null) {
      chip.hidden = true;
      return;
    }
    chip.hidden = false;
    chip.querySelector(".chip-text").textContent = text;
    chip.dataset.good = String(Boolean(good));
  }

  _displayState(state) {
    if (this._hass.formatEntityState) {
      try {
        return this._hass.formatEntityState(state);
      } catch (err) {
        /* fall through to the raw state */
      }
    }
    return state.state.replace(/_/g, " ");
  }

  _deviceName() {
    const device =
      this._hass.devices && this._deviceId
        ? this._hass.devices[this._deviceId]
        : null;
    return device ? device.name_by_user || device.name : null;
  }

  /* ------------------------------------------------------------ sparkline */

  _pushHistory(capacity) {
    const last = this._history[this._history.length - 1];
    if (last === capacity) return;
    this._history.push(capacity);
    if (this._history.length > HISTORY_POINTS) this._history.shift();
  }

  _drawSparkline() {
    const line = this._el.spark;
    const area = this._el.sparkArea;
    if (!line) return;

    const series =
      this._recorded && this._recorded.length >= 2 ? this._recorded : this._history;

    if (series.length < 2) {
      line.setAttribute("points", "0,11 100,11");
      line.classList.add("empty");
      if (area) area.setAttribute("d", "");
      return;
    }
    line.classList.remove("empty");

    const min = Math.min(...series);
    const max = Math.max(...series);
    const span = Math.max(max - min, 1);
    const stepX = 100 / (series.length - 1);
    const coords = series.map((value, index) => {
      const x = index * stepX;
      const y = 19 - ((value - min) / span) * 16;
      return `${x.toFixed(2)},${y.toFixed(2)}`;
    });

    line.setAttribute("points", coords.join(" "));
    if (area) {
      area.setAttribute("d", `M0,22 L${coords.join(" L")} L100,22 Z`);
    }
  }
}

/* ---------------------------------------------------------------- markup */

const TEMPLATE = `
<div class="glow"></div>
<div class="head">
  <div class="title" data-ref="title">Suptronics UPS</div>
  <div class="status" data-ref="status" data-role="status">
    <span class="dot"></span>
    <span data-ref="statusText">--</span>
  </div>
</div>

<div class="body">
  <div class="gauge" data-role="capacity">
    <svg viewBox="0 0 200 200" aria-hidden="true">
      <defs>
        <linearGradient id="x-arc" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stop-color="var(--x-tint)" stop-opacity="0.3"/>
          <stop offset="100%" stop-color="var(--x-tint)"/>
        </linearGradient>
        <linearGradient id="x-liquid" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stop-color="var(--x-tint)"/>
          <stop offset="100%" stop-color="var(--x-tint)" stop-opacity="0.6"/>
        </linearGradient>
        <linearGradient id="x-spark" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stop-color="var(--x-tint)" stop-opacity="0.4"/>
          <stop offset="100%" stop-color="var(--x-tint)" stop-opacity="0"/>
        </linearGradient>
      </defs>
      <circle class="window" data-ref="gaugeWindow" cx="100" cy="100" r="92"
              transform="rotate(-90 100 100)"/>
      <circle class="track" cx="100" cy="100" r="78"/>
      <circle class="value" data-ref="gaugeValue" cx="100" cy="100" r="78"
              transform="rotate(-90 100 100)"/>
      <circle class="sweep" cx="100" cy="100" r="78"/>
    </svg>
    <div class="readout">
      <div class="percent"><span data-ref="percent">--</span><i>%</i></div>
      <div class="volts" data-ref="voltage" data-role="voltage">--</div>
      <div class="level" data-ref="levelText"></div>
    </div>
  </div>

  <div class="side">
    <div class="flow" data-ref="flow" data-direction="in">
      <div class="node mains" data-ref="mains" data-role="ac">
        <svg class="glyph" viewBox="0 0 24 24"><path d="M7 2v6h2V2H7zm8 0v6h2V2h-2zM6 9v4a6 6 0 0 0 5 5.9V22h2v-3.1A6 6 0 0 0 18 13V9H6z"/></svg>
        <span data-ref="mainsLabel">Mains</span>
      </div>
      <div class="lane lane-in"><span class="pulse"></span></div>
      <div class="node ups" data-role="charging">
        <svg class="cell" viewBox="0 0 60 100" aria-hidden="true">
          <rect class="cap" x="24" y="12" width="12" height="6" rx="2"/>
          <rect class="shell" x="14" y="18" width="32" height="64" rx="7"/>
          <clipPath id="x-cell-clip">
            <rect x="17.5" y="21.5" width="25" height="57" rx="5"/>
          </clipPath>
          <g clip-path="url(#x-cell-clip)">
            <rect class="liquid" data-ref="cellFill" x="17.5" y="78" width="25" height="0"/>
            <g class="bubbles">
              <circle cx="24" cy="72" r="2"/>
              <circle cx="34" cy="76" r="1.5"/>
              <circle cx="29" cy="80" r="2.4"/>
            </g>
          </g>
          <path class="bolt" d="M33 32 L25 54 L31 54 L28 70 L38 46 L32 46 Z"/>
        </svg>
        <span data-ref="upsLabel">UPS</span>
      </div>
      <div class="lane lane-out"><span class="pulse"></span></div>
      <div class="node pi">
        <svg class="glyph" viewBox="0 0 24 24"><path d="M8 2v2H6v2H4v12h2v2h2v-2h8v2h2v-2h2V6h-2V4h-2V2h-2v2H10V2H8zm1 6h6v8H9V8z"/></svg>
        <span data-ref="piLabel">Pi</span>
      </div>
    </div>

    <svg class="spark" data-ref="sparkSvg" viewBox="0 0 100 22" preserveAspectRatio="none" aria-hidden="true">
      <path class="spark-area" data-ref="sparkArea" d=""/>
      <polyline data-ref="spark" points=""/>
    </svg>

    <div class="chips" data-ref="chips">
      <div class="chip" data-ref="chipAc" data-role="ac">
        <span class="chip-dot"></span><span class="chip-text">--</span>
      </div>
      <div class="chip" data-ref="chipCharge" data-role="charging">
        <span class="chip-dot"></span><span class="chip-text">--</span>
      </div>
      <div class="chip" data-ref="chipLow" data-role="low">
        <span class="chip-dot"></span><span class="chip-text">--</span>
      </div>
      <div class="chip" data-ref="chipRuntime" data-role="runtime" hidden>
        <span class="chip-dot"></span><span class="chip-text">--</span>
      </div>
      <div class="chip" data-ref="chipOnBattery" data-role="on_battery" hidden>
        <span class="chip-dot"></span><span class="chip-text">--</span>
      </div>
      <div class="chip window-chip" data-ref="chipWindow" data-role="charge_switch" data-good="true" hidden>
        <span class="chip-dot"></span><span class="chip-text">--</span>
      </div>
      <div class="chip" data-ref="chipShutdown" data-role="shutdown_switch" hidden>
        <span class="chip-dot"></span><span class="chip-text">--</span>
      </div>
    </div>

    <button class="charge-toggle" data-ref="chargeToggle" hidden>--</button>
  </div>
</div>
`;

/* ----------------------------------------------------------------- styles */

const STYLES = `
:host {
  --x-tint: #3ddc97;
  --x-ink: var(--primary-text-color, #e8ecf1);
  --x-muted: var(--secondary-text-color, #93a0b4);
  --x-surface: var(--ha-card-background, var(--card-background-color, #16181d));
  display: block;
  container-type: inline-size;
}

ha-card.ups {
  position: relative;
  display: block;
  overflow: hidden;
  padding: 18px;
  background:
    radial-gradient(130% 100% at 100% 0%, color-mix(in srgb, var(--x-tint) 13%, transparent), transparent 58%),
    var(--x-surface);
}

.glow {
  position: absolute;
  inset: -45% -20% auto -20%;
  height: 75%;
  background: radial-gradient(closest-side, color-mix(in srgb, var(--x-tint) 32%, transparent), transparent);
  filter: blur(30px);
  opacity: .5;
  pointer-events: none;
  transition: opacity 600ms ease;
}
:host(.is-alert) .glow { animation: breathe 2.2s ease-in-out infinite; }

.head {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 10px;
}
.title {
  font-size: 1.05rem;
  font-weight: 600;
  color: var(--x-ink);
}
.status {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  padding: 5px 11px;
  border-radius: 999px;
  cursor: pointer;
  font-size: .76rem;
  font-weight: 600;
  white-space: nowrap;
  color: var(--x-tint);
  background: color-mix(in srgb, var(--x-tint) 14%, transparent);
  border: 1px solid color-mix(in srgb, var(--x-tint) 32%, transparent);
}
.status .dot {
  width: 7px; height: 7px; border-radius: 50%;
  background: var(--x-tint);
  animation: ping 2.4s ease-out infinite;
}

.body {
  position: relative;
  display: grid;
  grid-template-columns: 190px 1fr;
  gap: 18px;
  align-items: center;
}
@container (max-width: 470px) {
  .body { grid-template-columns: 1fr; gap: 10px; }
}

/* --- gauge --- */
.gauge {
  position: relative;
  width: 100%;
  max-width: 190px;
  aspect-ratio: 1;
  margin: 0 auto;
  cursor: pointer;
}
.gauge > svg { width: 100%; height: 100%; display: block; overflow: visible; }
.gauge .track {
  fill: none;
  stroke: color-mix(in srgb, var(--x-ink) 9%, transparent);
  stroke-width: 13;
}
.gauge .value {
  fill: none;
  stroke: url(#x-arc);
  stroke-width: 13;
  stroke-linecap: round;
  filter: drop-shadow(0 0 8px color-mix(in srgb, var(--x-tint) 55%, transparent));
  transition: stroke-dashoffset 900ms cubic-bezier(.22,.61,.36,1);
}
.gauge .window {
  fill: none;
  stroke: color-mix(in srgb, var(--x-tint) 55%, transparent);
  stroke-width: 3;
  stroke-linecap: round;
  opacity: 0;
  transition: opacity 400ms ease, stroke-dashoffset 600ms ease;
}
.gauge .sweep {
  fill: none;
  stroke: color-mix(in srgb, var(--x-tint) 65%, transparent);
  stroke-width: 2.5;
  stroke-linecap: round;
  stroke-dasharray: 16 500;
  transform-origin: 100px 100px;
  opacity: 0;
}
:host(.is-charging) .gauge .sweep { opacity: 1; animation: orbit 3.4s linear infinite; }

.readout {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  pointer-events: none;
}
.percent {
  font-size: 2.4rem;
  font-weight: 700;
  line-height: 1;
  color: var(--x-ink);
  font-variant-numeric: tabular-nums;
  letter-spacing: -.02em;
}
.percent i { font-size: .95rem; font-style: normal; color: var(--x-muted); margin-left: 3px; }
.volts {
  margin-top: 6px;
  font-size: .84rem;
  color: var(--x-muted);
  font-variant-numeric: tabular-nums;
  pointer-events: auto;
  cursor: pointer;
}
.level {
  margin-top: 2px;
  font-size: .64rem;
  letter-spacing: .12em;
  text-transform: uppercase;
  font-weight: 600;
  color: color-mix(in srgb, var(--x-tint) 90%, var(--x-muted));
}

/* --- flow --- */
.side {
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-width: 0;
  max-width: 460px;
}
.flow {
  display: grid;
  grid-template-columns: auto minmax(14px, 1fr) auto minmax(14px, 1fr) auto;
  align-items: center;
  gap: 8px;
}
.node {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  font-size: .6rem;
  letter-spacing: .08em;
  text-transform: uppercase;
  color: var(--x-muted);
}
.node .glyph {
  width: 26px; height: 26px;
  fill: var(--x-ink);
  opacity: .8;
  transition: opacity 300ms ease;
}
.node.mains { cursor: pointer; }
.node.mains.off .glyph { opacity: .25; }
.node.mains.off { color: color-mix(in srgb, #ff5c5c 75%, var(--x-muted)); }
.node.ups { cursor: pointer; color: var(--x-tint); }

.cell { width: 30px; height: 50px; display: block; }
.cell .shell {
  fill: none;
  stroke: color-mix(in srgb, var(--x-ink) 30%, transparent);
  stroke-width: 3;
}
.cell .cap { fill: color-mix(in srgb, var(--x-ink) 30%, transparent); }
.cell .liquid {
  fill: url(#x-liquid);
  transition: y 900ms cubic-bezier(.22,.61,.36,1), height 900ms cubic-bezier(.22,.61,.36,1);
}
.cell .bubbles circle { fill: #fff; opacity: 0; }
:host(.is-charging) .cell .bubbles circle { animation: rise 2.6s ease-in infinite; }
:host(.is-charging) .cell .bubbles circle:nth-child(2) { animation-delay: .8s; }
:host(.is-charging) .cell .bubbles circle:nth-child(3) { animation-delay: 1.6s; }
.cell .bolt {
  fill: #fff;
  opacity: 0;
  transition: opacity 400ms ease;
}
:host(.is-charging) .cell .bolt { opacity: .9; }

.lane {
  position: relative;
  height: 3px;
  border-radius: 2px;
  background: color-mix(in srgb, var(--x-ink) 12%, transparent);
  overflow: hidden;
}
.lane .pulse {
  position: absolute;
  top: 0; bottom: 0;
  width: 45%;
  border-radius: 2px;
  background: linear-gradient(90deg, transparent, var(--x-tint), transparent);
  animation: slide 1.9s linear infinite;
}
.flow[data-direction="out"] .lane-in .pulse { opacity: 0; animation: none; }

/* --- sparkline --- */
.spark { width: 100%; height: 30px; display: block; }
.spark polyline {
  fill: none;
  stroke: var(--x-tint);
  stroke-width: 1.8;
  stroke-linejoin: round;
  stroke-linecap: round;
  vector-effect: non-scaling-stroke;
  filter: drop-shadow(0 0 4px color-mix(in srgb, var(--x-tint) 45%, transparent));
}
.spark .spark-area { fill: url(#x-spark); stroke: none; }
.spark polyline.empty {
  stroke: color-mix(in srgb, var(--x-ink) 22%, transparent);
  stroke-width: 1.2;
  stroke-dasharray: 3 4;
  filter: none;
}

/* --- chips --- */
.chips { display: flex; flex-wrap: wrap; gap: 6px; }
.chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 5px 10px;
  border-radius: 999px;
  cursor: pointer;
  font-size: .73rem;
  color: var(--x-muted);
  background: color-mix(in srgb, var(--x-ink) 7%, transparent);
  transition: background 250ms ease, color 250ms ease;
}
.chip[hidden] { display: none; }
.chip:hover { background: color-mix(in srgb, var(--x-ink) 13%, transparent); }
.chip .chip-dot { width: 6px; height: 6px; border-radius: 50%; background: #ff5c5c; }
.chip[data-good="true"] .chip-dot { background: var(--x-tint); }
.chip[data-good="true"] { color: var(--x-ink); }
.chip.window-chip {
  background: color-mix(in srgb, var(--x-tint) 12%, transparent);
  color: var(--x-tint);
}

.charge-toggle {
  appearance: none;
  border: 1px solid color-mix(in srgb, var(--x-ink) 16%, transparent);
  background: transparent;
  color: var(--x-muted);
  border-radius: 10px;
  padding: 8px 12px;
  font: inherit;
  font-size: .78rem;
  cursor: pointer;
  transition: color 250ms ease, border-color 250ms ease, background 250ms ease, transform 150ms ease;
}
.charge-toggle[data-on="true"] {
  color: var(--x-tint);
  border-color: color-mix(in srgb, var(--x-tint) 45%, transparent);
  background: color-mix(in srgb, var(--x-tint) 10%, transparent);
}
.charge-toggle:hover { transform: translateY(-1px); }

/* --- variants --- */
[hidden] { display: none !important; }

ha-card.ups[data-variant="compact"] { padding: 14px 16px; }
[data-variant="compact"] .body { grid-template-columns: 130px 1fr; gap: 14px; }
[data-variant="compact"] .gauge { max-width: 130px; }
[data-variant="compact"] .percent { font-size: 1.8rem; }
[data-variant="compact"] .volts { margin-top: 4px; font-size: .76rem; }
[data-variant="compact"] .level { display: none; }

ha-card.ups[data-variant="slim"] { padding: 12px 16px; }
[data-variant="slim"] .head { margin-bottom: 4px; }
[data-variant="slim"] .body { grid-template-columns: 84px 1fr; gap: 14px; }
[data-variant="slim"] .gauge { max-width: 84px; }
[data-variant="slim"] .gauge .track,
[data-variant="slim"] .gauge .value { stroke-width: 16; }
[data-variant="slim"] .percent { font-size: 1.25rem; }
[data-variant="slim"] .percent i { font-size: .7rem; }
[data-variant="slim"] .volts,
[data-variant="slim"] .level { display: none; }
[data-variant="slim"] .chips { gap: 5px; }
[data-variant="slim"] .gauge .window { display: none; }
[data-variant="slim"] .flow { gap: 6px; grid-template-columns: auto minmax(10px, 1fr) auto minmax(10px, 1fr) auto; }
[data-variant="slim"] .node { gap: 2px; font-size: .52rem; letter-spacing: .05em; }
[data-variant="slim"] .node .glyph { width: 19px; height: 19px; }
[data-variant="slim"] .cell { width: 21px; height: 35px; }

.head, .body { animation: rise-in 520ms cubic-bezier(.22,.61,.36,1) both; }
.body { animation-delay: 60ms; }

@keyframes rise-in {
  from { opacity: 0; transform: translateY(6px); }
  to   { opacity: 1; transform: none; }
}

ha-card.ups[data-variant="gauge"] { padding: 16px; }
[data-variant="gauge"] .body { grid-template-columns: 1fr; }
[data-variant="gauge"] .side { display: none; }
[data-variant="gauge"] .gauge { max-width: 220px; }

.empty { padding: 8px 4px; color: var(--x-muted); }
.empty-title { font-size: 1.05rem; font-weight: 600; color: var(--x-ink); margin-bottom: 6px; }

@keyframes ping {
  0%   { box-shadow: 0 0 0 0 color-mix(in srgb, var(--x-tint) 70%, transparent); }
  70%  { box-shadow: 0 0 0 7px transparent; }
  100% { box-shadow: 0 0 0 0 transparent; }
}
@keyframes slide {
  from { transform: translateX(-120%); }
  to   { transform: translateX(260%); }
}
@keyframes orbit {
  from { transform: rotate(-90deg); }
  to   { transform: rotate(270deg); }
}
@keyframes rise {
  0%   { opacity: 0; transform: translateY(0) scale(.6); }
  25%  { opacity: .5; }
  100% { opacity: 0; transform: translateY(-46px) scale(1); }
}
@keyframes breathe {
  0%, 100% { opacity: .3; }
  50%      { opacity: .85; }
}

@media (prefers-reduced-motion: reduce) {
  .glow, .status .dot, .lane .pulse, .cell .bubbles circle, .gauge .sweep,
  .head, .body {
    animation: none !important;
  }
  .gauge .value, .cell .liquid { transition: none; }
}
`;

if (!customElements.get(CARD_TYPE)) {
  customElements.define(CARD_TYPE, SuptronicsUpsCard);
}

window.customCards = window.customCards || [];
if (!window.customCards.some((card) => card.type === CARD_TYPE)) {
  window.customCards.push({
    type: CARD_TYPE,
    name: "Suptronics UPS",
    description:
      "Animated status panel for the Suptronics X120x UPS: charge gauge, mains flow, runtime estimate and charge control.",
    preview: true,
  });
}
