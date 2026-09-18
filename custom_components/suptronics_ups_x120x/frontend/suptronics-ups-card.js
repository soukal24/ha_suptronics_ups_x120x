/**
 * Suptronics UPS card.
 *
 * A self-contained Lovelace card for the Suptronics X120x UPS, served and
 * registered by the integration itself. It finds the UPS entities on its own
 * through the `ups_role` attribute the integration puts on each of them.
 *
 *   type: custom:suptronics-ups-card
 *   variant: full | compact | gauge      (default: full)
 *   name: optional title override
 *   hours: how far back the history looks (default 24)
 *   language: en | cs                     (default: the Home Assistant language)
 *   show_stats / show_history / show_extras / show_actions:
 *       force a single block on or off, whatever the variant decided
 *   extras: system_monitor                finds the System Monitor entities
 *       (CPU temperature, CPU, memory, disk) on its own; or a list:
 *     - entity: sensor.processor_temperature
 *       name: CPU
 *       min: 0
 *       max: 100
 *       severity: { green: 0, yellow: 65, red: 80 }
 *   entities:                             optional explicit overrides by role
 *
 * The resource-registration approach and the entity lookup follow the X120X
 * card by mesgas (MIT), see THIRD_PARTY_NOTICES.md.
 */

const CARD_VERSION = "3.0.0";
const PLATFORM = "suptronics_ups_x120x";
const CARD_TYPE = "suptronics-ups-card";

const REDUCED_MOTION = window.matchMedia("(prefers-reduced-motion: reduce)");

console.info(
  `%c SUPTRONICS-UPS-CARD %c ${CARD_VERSION} `,
  "color:#fff;background:#2e7d32;font-weight:700;border-radius:3px 0 0 3px",
  "color:#2e7d32;background:#e8f5e9;border-radius:0 3px 3px 0"
);

/** The role attribute value of each entity the card uses. */
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
  last_loss: "last_power_loss",
  outages: "power_outages",
  countdown: "shutdown_countdown",
  shutdown_switch: "auto_shutdown",
};

/** Which theme colour each status uses. */
const STATUS_COLOR = {
  online: "good",
  charging: "info",
  on_battery: "warn",
  low_battery: "bad",
  shutting_down: "bad",
  unknown: "muted",
};

const STRINGS = {
  en: {
    status_online: "On line",
    status_charging: "Charging",
    status_on_battery: "On battery",
    status_low_battery: "Battery low",
    status_shutting_down: "Shutting down",
    status_unknown: "Unknown",
    countdown: "Shutdown in {seconds} s",
    runtime: "Runtime",
    runtime_hint: "estimated",
    on_battery: "On battery",
    last_loss: "Last outage",
    outages: "Outages",
    voltage: "Voltage",
    never: "never",
    unknown: "--",
    battery_history: "Battery",
    mains_history: "Mains",
    now: "now",
    hours_ago: "-{hours} h",
    window: "Window {min}-{max} %",
    charging_enabled: "Charging on",
    charging_paused: "Charging paused",
    shutdown_on: "Auto shutdown on",
    shutdown_off: "Auto shutdown off",
    minutes_short: "min",
    hours_short: "h",
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
    runtime: "Výdrž",
    runtime_hint: "odhad",
    on_battery: "Na baterii",
    last_loss: "Poslední výpadek",
    outages: "Výpadků",
    voltage: "Napětí",
    never: "zatím žádný",
    unknown: "--",
    battery_history: "Baterie",
    mains_history: "Síť",
    now: "teď",
    hours_ago: "-{hours} h",
    window: "Okno {min}–{max} %",
    charging_enabled: "Nabíjení zapnuto",
    charging_paused: "Nabíjení pozastaveno",
    shutdown_on: "Auto vypnutí zapnuto",
    shutdown_off: "Auto vypnutí vypnuto",
    minutes_short: "min",
    hours_short: "h",
    empty:
      "Zařízení Suptronics UPS zatím nebylo nalezeno. Pokud je integrace nastavená, obnovte dashboard; jinak zadejte entity v konfiguraci karty ručně.",
  },
};

const VARIANTS = {
  full: { stats: true, history: true, extras: true, actions: true },
  compact: { stats: true, history: false, extras: false, actions: true },
  gauge: { stats: false, history: false, extras: false, actions: false },
};

// Main gauge: a 240-degree arc, like a dashboard dial.
const ARC_SWEEP = 240;
const ARC_RADIUS = 80;
const ARC_LENGTH = (2 * Math.PI * ARC_RADIUS * ARC_SWEEP) / 360;
// Mini gauges in the extras row.
const MINI_RADIUS = 26;
const MINI_LENGTH = (2 * Math.PI * MINI_RADIUS * ARC_SWEEP) / 360;

const HISTORY_POINTS = 96;
const DEFAULT_HISTORY_HOURS = 24;
const HISTORY_REFRESH_MS = 5 * 60 * 1000;

/** Battery bands, for the colour of the main dial. */
const BATTERY_SEVERITY = { green: 50, yellow: 25, red: 0 };

/**
 * Colour for a value against gauge-style thresholds. Works both ways round:
 * ascending (green 0, yellow 65, red 80: a temperature) and descending
 * (green 3.9, yellow 3.55, red 0: a voltage).
 */
function severityColor(value, severity) {
  if (!severity || !Number.isFinite(value)) return "accent";
  const g = Number(severity.green);
  const y = Number(severity.yellow);
  const r = Number(severity.red);
  if (![g, y, r].every(Number.isFinite)) return "accent";
  if (g >= y) {
    // Descending: high is good.
    if (value >= g) return "good";
    if (value >= y) return "warn";
    return "bad";
  }
  if (value >= r) return "bad";
  if (value >= y) return "warn";
  return "good";
}

function describeArc(cx, cy, r, sweep) {
  // The arc starts at the bottom-left (240° sweep centred on top).
  const start = 90 + (360 - sweep) / 2;
  const toXY = (angle) => {
    const rad = (angle * Math.PI) / 180;
    return `${(cx + r * Math.cos(rad)).toFixed(2)},${(cy + r * Math.sin(rad)).toFixed(2)}`;
  };
  const large = sweep > 180 ? 1 : 0;
  return `M ${toXY(start)} A ${r} ${r} 0 ${large} 1 ${toXY(start + sweep)}`;
}

class SuptronicsUpsCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._config = {};
    this._entities = null;
    this._built = false;
    this._historyAt = 0;
    this._fetching = false;
    this._batteryTrace = null;
    this._mainsTrace = null;
  }

  static getStubConfig() {
    return { type: `custom:${CARD_TYPE}` };
  }

  setConfig(config) {
    const variant = config.variant || "full";
    if (!VARIANTS[variant]) {
      throw new Error(
        `${CARD_TYPE}: unknown variant "${variant}". Use one of: ${Object.keys(VARIANTS).join(", ")}`
      );
    }
    let extras = config.extras;
    if (extras === true || extras === "system_monitor") {
      extras = "system_monitor";
    } else if (Array.isArray(extras)) {
      for (const extra of extras) {
        if (!extra || typeof extra.entity !== "string") {
          throw new Error(`${CARD_TYPE}: every item of "extras" needs an "entity"`);
        }
      }
    } else {
      extras = [];
    }
    this._config = { ...config, variant, extras };
    this._entities = null;
    this._built = false;
    this.shadowRoot.innerHTML = "";
  }

  getCardSize() {
    const parts = this._parts();
    return 3 + (parts.history ? 2 : 0) + (parts.extras && this._config.extras.length ? 2 : 0);
  }

  /**
   * The System Monitor integration's usual readings, found by their
   * translation key (which does not change with the language), with the
   * thresholds of the classic gauge cards. Used by `extras: system_monitor`.
   */
  _systemMonitorExtras() {
    const registry = this._hass.entities || {};
    const wanted = [
      { key: "processor_temperature", name: "CPU °C", severity: { green: 0, yellow: 65, red: 80 } },
      { key: "processor_use", name: "CPU", severity: { green: 0, yellow: 75, red: 90 } },
      { key: "memory_use_percent", name: "RAM", severity: { green: 0, yellow: 75, red: 90 } },
      { key: "disk_use_percent", name: "Disk", severity: { green: 0, yellow: 70, red: 90 } },
    ];
    const extras = [];
    for (const item of wanted) {
      const match = Object.values(registry).find(
        (entry) =>
          entry.platform === "systemmonitor" &&
          (entry.translation_key === item.key ||
            (entry.entity_id || "").includes(item.key)) &&
          this._hass.states[entry.entity_id]
      );
      if (match) {
        extras.push({ entity: match.entity_id, name: item.name, min: 0, max: 100, severity: item.severity });
      }
    }
    return extras;
  }

  _extrasList() {
    return this._config.extras === "system_monitor"
      ? this._systemMonitorExtras()
      : this._config.extras;
  }

  _parts() {
    const defaults = VARIANTS[this._config.variant] || VARIANTS.full;
    const resolve = (key) => {
      const override = this._config[`show_${key}`];
      return override === undefined ? defaults[key] : Boolean(override);
    };
    return {
      stats: resolve("stats"),
      history: resolve("history"),
      extras: resolve("extras"),
      actions: resolve("actions"),
    };
  }

  set hass(hass) {
    this._hass = hass;
    if (!this._built) this._build();
    this._update();
    if (this._shown && this._shown.history && Date.now() - this._historyAt > HISTORY_REFRESH_MS) {
      this._fetchHistory();
    }
  }

  /* ---------------------------------------------------------------- i18n */

  _language() {
    const hass = this._hass || {};
    const raw =
      this._config.language || (hass.locale && hass.locale.language) || hass.language || "en";
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

  _duration(minutes) {
    const total = Math.max(0, Math.round(minutes));
    const h = Math.floor(total / 60);
    const m = total % 60;
    if (h === 0) return `${m} ${this._t("minutes_short")}`;
    if (m === 0) return `${h} ${this._t("hours_short")}`;
    return `${h} ${this._t("hours_short")} ${m} ${this._t("minutes_short")}`;
  }

  _relativeTime(iso) {
    const stamp = Date.parse(iso);
    if (!Number.isFinite(stamp)) return this._t("never");
    const minutes = Math.round((Date.now() - stamp) / 60000);
    if (minutes < 1) return this._t("now");
    if (minutes < 24 * 60) return `-${this._duration(minutes)}`;
    const date = new Date(stamp);
    try {
      return date.toLocaleDateString(this._hass.locale?.language || undefined, {
        day: "numeric",
        month: "numeric",
      });
    } catch (err) {
      return date.toLocaleDateString();
    }
  }

  /* ------------------------------------------------------------- history */

  async _fetchHistory() {
    const capacityId = this._entities && this._entities.capacity;
    const acId = this._entities && this._entities.ac;
    if (this._fetching || !this._hass || !capacityId) return;
    this._fetching = true;
    this._historyAt = Date.now();
    try {
      const hours = Number(this._config.hours) || DEFAULT_HISTORY_HOURS;
      const end = new Date();
      const start = new Date(end.getTime() - hours * 3600 * 1000);
      const ids = acId ? [capacityId, acId] : [capacityId];
      const response = await this._hass.callWS({
        type: "history/history_during_period",
        start_time: start.toISOString(),
        end_time: end.toISOString(),
        entity_ids: ids,
        minimal_response: true,
        no_attributes: true,
      });
      this._batteryTrace = this._bucketNumeric(
        response?.[capacityId] || [],
        start.getTime(),
        end.getTime()
      );
      this._mainsTrace = acId
        ? this._segmentsBinary(response?.[acId] || [], start.getTime(), end.getTime())
        : null;
      if (this._built) this._drawHistory();
    } catch (err) {
      console.warn(`${CARD_TYPE}: could not read history`, err);
      this._batteryTrace = null;
      this._mainsTrace = null;
    } finally {
      this._fetching = false;
    }
  }

  _stampOf(entry) {
    const seconds = entry.lu ?? entry.lc;
    return typeof seconds === "number"
      ? seconds * 1000
      : Date.parse(entry.last_updated ?? entry.last_changed);
  }

  _bucketNumeric(raw, startMs, endMs) {
    const span = Math.max(endMs - startMs, 1);
    const sums = new Array(HISTORY_POINTS).fill(0);
    const counts = new Array(HISTORY_POINTS).fill(0);
    for (const entry of raw) {
      const value = Number(entry.s ?? entry.state);
      const stamp = this._stampOf(entry);
      if (!Number.isFinite(value) || !Number.isFinite(stamp)) continue;
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
      series.push(last);
    }
    return series;
  }

  /** [{from: 0..1, to: 0..1, on: bool}] over the window. */
  _segmentsBinary(raw, startMs, endMs) {
    const span = Math.max(endMs - startMs, 1);
    const points = raw
      .map((entry) => ({ t: this._stampOf(entry), on: (entry.s ?? entry.state) === "on" }))
      .filter((p) => Number.isFinite(p.t))
      .sort((a, b) => a.t - b.t);
    if (points.length === 0) return [];
    const segments = [];
    for (let i = 0; i < points.length; i += 1) {
      const from = Math.max(0, (points[i].t - startMs) / span);
      const to = i + 1 < points.length ? (points[i + 1].t - startMs) / span : 1;
      if (to > from) segments.push({ from, to: Math.min(1, to), on: points[i].on });
    }
    return segments;
  }

  /* --------------------------------------------------------------- lookup */

  _resolveEntities() {
    const resolved = { ...(this._config.entities || {}) };
    const missing = Object.keys(ROLES).filter((role) => !resolved[role]);
    if (missing.length === 0) return resolved;

    const registry = this._hass.entities;
    if (!registry) return Object.keys(resolved).length ? resolved : null;

    const ours = [];
    for (const [entityId, entry] of Object.entries(registry)) {
      if (entry.platform !== PLATFORM) continue;
      if (this._config.device_id && entry.device_id !== this._config.device_id) continue;
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
    return entityId ? this._hass.states[entityId] || null : null;
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

  _displayState(state) {
    if (this._hass.formatEntityState) {
      try {
        return this._hass.formatEntityState(state);
      } catch (err) {
        /* fall through */
      }
    }
    return state.state.replace(/_/g, " ");
  }

  _deviceName() {
    const device =
      this._hass.devices && this._deviceId ? this._hass.devices[this._deviceId] : null;
    return device ? device.name_by_user || device.name : null;
  }

  _openMoreInfo(entityId) {
    if (!entityId) return;
    const event = new Event("hass-more-info", { bubbles: true, composed: true });
    event.detail = { entityId };
    this.dispatchEvent(event);
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
      card.innerHTML = `<div class="empty"><div class="empty-title">Suptronics UPS</div><p>${this._t("empty")}</p></div>`;
      return;
    }

    card.innerHTML = TEMPLATE;
    this._el = {};
    for (const node of card.querySelectorAll("[data-ref]")) {
      this._el[node.dataset.ref] = node;
    }

    // Static geometry of the dial.
    const arc = describeArc(100, 100, ARC_RADIUS, ARC_SWEEP);
    this._el.dialTrack.setAttribute("d", arc);
    this._el.dialValue.setAttribute("d", arc);
    this._el.dialValue.setAttribute("stroke-dasharray", `${ARC_LENGTH} ${ARC_LENGTH}`);
    this._el.dialValue.setAttribute("stroke-dashoffset", ARC_LENGTH);
    // Charge window arc sits just outside the dial.
    this._el.dialWindow.setAttribute("d", describeArc(100, 100, ARC_RADIUS + 12, ARC_SWEEP));

    // Static labels.
    this._el.runtimeLabel.textContent = this._t("runtime");
    this._el.onBatteryLabel.textContent = this._t("on_battery");
    this._el.voltageLabel.textContent = this._t("voltage");
    this._el.outagesLabel.textContent = this._t("outages");
    this._el.historyBattery.textContent = this._t("battery_history");
    this._el.historyMains.textContent = this._t("mains_history");
    this._el.axisNow.textContent = this._t("now");
    this._el.axisStart.textContent = this._t("hours_ago", {
      hours: Number(this._config.hours) || DEFAULT_HISTORY_HOURS,
    });

    this._shown = this._parts();
    card.dataset.variant = this._config.variant;
    this._el.stats.toggleAttribute("hidden", !this._shown.stats);
    this._el.history.toggleAttribute("hidden", !this._shown.history);
    this._el.actions.toggleAttribute("hidden", !this._shown.actions);
    this._buildExtras();

    for (const node of card.querySelectorAll("[data-role]")) {
      node.addEventListener("click", () => this._openMoreInfo(this._entities[node.dataset.role]));
    }
    this._el.chargeToggle.addEventListener("click", (ev) => {
      ev.stopPropagation();
      const entityId = this._entities.charge_switch;
      if (entityId) this._hass.callService("switch", "toggle", { entity_id: entityId });
    });
    this._el.shutdownToggle.addEventListener("click", (ev) => {
      ev.stopPropagation();
      const entityId = this._entities.shutdown_switch;
      if (entityId) this._hass.callService("switch", "toggle", { entity_id: entityId });
    });

    this._built = true;
  }

  _buildExtras() {
    const container = this._el.extras;
    container.innerHTML = "";
    const extras = this._extrasList();
    if (!this._shown.extras || extras.length === 0) {
      container.hidden = true;
      return;
    }
    container.hidden = false;
    this._extraNodes = extras.map((extra) => {
      const node = document.createElement("div");
      node.className = "mini";
      node.innerHTML = `
        <svg viewBox="0 0 64 64" aria-hidden="true">
          <path class="mini-track" d="${describeArc(32, 34, MINI_RADIUS, ARC_SWEEP)}"/>
          <path class="mini-value" d="${describeArc(32, 34, MINI_RADIUS, ARC_SWEEP)}"
                stroke-dasharray="${MINI_LENGTH} ${MINI_LENGTH}" stroke-dashoffset="${MINI_LENGTH}"/>
        </svg>
        <div class="mini-value-text">--</div>
        <div class="mini-name"></div>`;
      node.addEventListener("click", () => this._openMoreInfo(extra.entity));
      container.append(node);
      return {
        extra,
        value: node.querySelector(".mini-value"),
        text: node.querySelector(".mini-value-text"),
        name: node.querySelector(".mini-name"),
        node,
      };
    });
  }

  /* --------------------------------------------------------------- update */

  _update() {
    if (!this._built || !this._el) return;

    const capacity = this._number("capacity", 0);
    const voltage = this._number("voltage");
    const acOn = this._isOn("ac");
    const charging = this._isOn("charging");
    const statusState = this._state("status");
    const statusKey =
      statusState && STATUS_COLOR[statusState.state] ? statusState.state : "unknown";
    const countdown = this._number("countdown");

    // --- banner -------------------------------------------------------------
    this.dataset.status = statusKey;
    this.dataset.color = STATUS_COLOR[statusKey];
    this._el.title.textContent = this._config.name || this._deviceName() || "Suptronics UPS";
    if (statusKey === "shutting_down" && countdown !== null) {
      this._el.status.textContent = this._t("countdown", { seconds: Math.round(countdown) });
    } else {
      this._el.status.textContent = statusState
        ? this._displayState(statusState)
        : this._t(`status_${statusKey}`);
    }
    for (const node of this._el.banner.querySelectorAll(".glyph")) {
      node.hidden = node.dataset.for !== statusKey;
    }
    this.classList.toggle("is-charging", charging);
    this.classList.toggle("is-alert", statusKey === "low_battery" || statusKey === "shutting_down");

    // --- dial ---------------------------------------------------------------
    const clamped = Math.max(0, Math.min(100, capacity));
    this._el.dialValue.setAttribute("stroke-dashoffset", ARC_LENGTH * (1 - clamped / 100));
    this.dataset.band = severityColor(clamped, BATTERY_SEVERITY);
    const decimals = Math.round(clamped * 10) % 10 === 0 ? 0 : 1;
    this._el.percent.textContent = clamped.toFixed(decimals);
    const levelState = this._state("level");
    this._el.level.textContent = levelState ? this._displayState(levelState) : "";
    this._renderWindow();

    // --- stats --------------------------------------------------------------
    const runtime = this._number("runtime");
    this._el.runtimeValue.textContent = runtime === null ? this._t("unknown") : this._duration(runtime);
    this._el.runtimeHint.textContent = runtime === null ? "" : this._t("runtime_hint");

    const onBattery = this._number("on_battery");
    const lastLoss = this._state("last_loss");
    if (!acOn && onBattery !== null) {
      this._el.onBatteryLabel.textContent = this._t("on_battery");
      this._el.onBatteryValue.textContent = this._duration(onBattery);
    } else {
      this._el.onBatteryLabel.textContent = this._t("last_loss");
      this._el.onBatteryValue.textContent =
        lastLoss && lastLoss.state && lastLoss.state !== "unknown"
          ? this._relativeTime(lastLoss.state)
          : this._t("never");
    }
    this._el.voltageValue.textContent = voltage === null ? "--" : `${voltage.toFixed(2)} V`;
    const outages = this._number("outages");
    this._el.outagesValue.textContent = outages === null ? "--" : String(Math.round(outages));

    // --- actions ------------------------------------------------------------
    const chargeSwitch = this._state("charge_switch");
    if (chargeSwitch) {
      const on = chargeSwitch.state === "on";
      this._el.chargeToggle.hidden = false;
      this._el.chargeToggle.dataset.on = String(on);
      this._el.chargeToggle.textContent = this._t(on ? "charging_enabled" : "charging_paused");
    } else {
      this._el.chargeToggle.hidden = true;
    }
    const shutdownSwitch = this._state("shutdown_switch");
    if (shutdownSwitch) {
      const on = shutdownSwitch.state === "on";
      this._el.shutdownToggle.hidden = false;
      this._el.shutdownToggle.dataset.on = String(on);
      this._el.shutdownToggle.textContent = this._t(on ? "shutdown_on" : "shutdown_off");
    } else {
      this._el.shutdownToggle.hidden = true;
    }

    // --- extras -------------------------------------------------------------
    this._updateExtras();

    if (this._shown.history) this._drawHistory();
  }

  _renderWindow() {
    const attrs = (this._state("charge_switch") || {}).attributes || {};
    const min = Number(attrs.charge_limit_min);
    const max = Number(attrs.charge_limit_max);
    const limited = Number.isFinite(min) && Number.isFinite(max) && max < 100 && max > min;
    const arc = this._el.dialWindow;
    const outerLength = (2 * Math.PI * (ARC_RADIUS + 12) * ARC_SWEEP) / 360;
    if (!limited) {
      arc.style.opacity = "0";
      this._el.windowText.hidden = true;
      return;
    }
    const length = (outerLength * (max - min)) / 100;
    arc.setAttribute("stroke-dasharray", `${length} ${outerLength}`);
    arc.setAttribute("stroke-dashoffset", -(outerLength * min) / 100);
    arc.style.opacity = "1";
    this._el.windowText.hidden = false;
    this._el.windowText.textContent = this._t("window", {
      min: Math.round(min),
      max: Math.round(max),
    });
  }

  _updateExtras() {
    if (!this._extraNodes) return;
    for (const item of this._extraNodes) {
      const state = this._hass.states[item.extra.entity];
      const value = state ? Number(state.state) : NaN;
      const min = Number.isFinite(Number(item.extra.min)) ? Number(item.extra.min) : 0;
      const max = Number.isFinite(Number(item.extra.max)) ? Number(item.extra.max) : 100;
      const unit = item.extra.unit ?? (state && state.attributes.unit_of_measurement) ?? "";
      const name =
        item.extra.name ||
        (state && state.attributes.friendly_name) ||
        item.extra.entity;
      item.name.textContent = name;
      if (!Number.isFinite(value)) {
        item.text.textContent = "--";
        item.value.setAttribute("stroke-dashoffset", MINI_LENGTH);
        item.node.dataset.color = "muted";
        continue;
      }
      const fraction = Math.max(0, Math.min(1, (value - min) / Math.max(max - min, 1e-9)));
      item.value.setAttribute("stroke-dashoffset", MINI_LENGTH * (1 - fraction));
      const decimals = Number.isFinite(Number(item.extra.decimals))
        ? Number(item.extra.decimals)
        : Math.abs(value) >= 100
          ? 0
          : 1;
      item.text.textContent = `${value.toFixed(decimals)}${unit ? ` ${unit}` : ""}`;
      item.node.dataset.color = severityColor(value, item.extra.severity);
    }
  }

  /* -------------------------------------------------------------- history */

  _drawHistory() {
    const line = this._el.spark;
    const area = this._el.sparkArea;
    const strip = this._el.mainsStrip;
    if (!line) return;

    const series = this._batteryTrace || [];
    const known = series.filter((v) => v !== null);
    if (known.length < 2) {
      line.setAttribute("points", "");
      area.setAttribute("d", "");
    } else {
      const stepX = 100 / (series.length - 1);
      const coords = [];
      series.forEach((value, index) => {
        if (value === null) return;
        const y = 30 - (value / 100) * 28;
        coords.push(`${(index * stepX).toFixed(2)},${y.toFixed(2)}`);
      });
      line.setAttribute("points", coords.join(" "));
      const first = coords[0].split(",")[0];
      const last = coords[coords.length - 1].split(",")[0];
      area.setAttribute("d", `M${first},32 L${coords.join(" L")} L${last},32 Z`);
    }

    strip.innerHTML = "";
    for (const seg of this._mainsTrace || []) {
      const rect = document.createElementNS("http://www.w3.org/2000/svg", "rect");
      rect.setAttribute("x", (seg.from * 100).toFixed(2));
      rect.setAttribute("y", "0");
      rect.setAttribute("width", ((seg.to - seg.from) * 100).toFixed(2));
      rect.setAttribute("height", "6");
      rect.setAttribute("class", seg.on ? "on" : "off");
      strip.append(rect);
    }
  }
}

/* ---------------------------------------------------------------- markup */

const TEMPLATE = `
<div class="banner" data-ref="banner" data-role="status">
  <svg class="glyph" data-for="online" viewBox="0 0 24 24"><path d="M16 7V3h-2v4h-4V3H8v4H8C6.9 7 6 7.9 6 9v5.5L9.5 18v3h5v-3l3.5-3.5V9c0-1.1-.9-2-2-2z"/></svg>
  <svg class="glyph" data-for="charging" viewBox="0 0 24 24"><path d="M11 21h-1l1-7H7.5c-.58 0-.57-.32-.38-.66.19-.34.05-.08.07-.12C8.48 10.94 10.42 7.54 13 3h1l-1 7h3.5c.49 0 .56.33.47.51l-.07.15C12.96 17.55 11 21 11 21z"/></svg>
  <svg class="glyph" data-for="on_battery" viewBox="0 0 24 24"><path d="M16.67 4H15V2H9v2H7.33C6.6 4 6 4.6 6 5.33v15.33C6 21.4 6.6 22 7.33 22h9.33c.74 0 1.34-.6 1.34-1.33V5.33C18 4.6 17.4 4 16.67 4zM16 20H8v-4h8v4z"/></svg>
  <svg class="glyph" data-for="low_battery" viewBox="0 0 24 24"><path d="M16.67 4H15V2H9v2H7.33C6.6 4 6 4.6 6 5.33v15.33C6 21.4 6.6 22 7.33 22h9.33c.74 0 1.34-.6 1.34-1.33V5.33C18 4.6 17.4 4 16.67 4zM13 18h-2v-2h2v2zm0-4h-2V9h2v5z"/></svg>
  <svg class="glyph" data-for="shutting_down" viewBox="0 0 24 24"><path d="M13 3h-2v10h2V3zm4.83 2.17l-1.42 1.42A6.92 6.92 0 0 1 19 12c0 3.87-3.13 7-7 7s-7-3.13-7-7c0-2.17.98-4.1 2.58-5.42L6.17 5.17A8.93 8.93 0 0 0 3 12a9 9 0 0 0 18 0c0-2.74-1.23-5.18-3.17-6.83z"/></svg>
  <svg class="glyph" data-for="unknown" viewBox="0 0 24 24"><path d="M11 18h2v-2h-2v2zm1-16C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 18c-4.41 0-8-3.59-8-8s3.59-8 8-8 8 3.59 8 8-3.59 8-8 8zm0-14c-2.21 0-4 1.79-4 4h2c0-1.1.9-2 2-2s2 .9 2 2c0 2-3 1.75-3 5h2c0-2.25 3-2.5 3-5 0-2.21-1.79-4-4-4z"/></svg>
  <div class="banner-text">
    <div class="title" data-ref="title">Suptronics UPS</div>
    <div class="status" data-ref="status">--</div>
  </div>
  <div class="window-text" data-ref="windowText" hidden></div>
</div>

<div class="main">
  <div class="dial" data-role="capacity">
    <svg viewBox="0 0 200 180" aria-hidden="true">
      <path class="dial-window" data-ref="dialWindow"/>
      <path class="dial-track" data-ref="dialTrack"/>
      <path class="dial-value" data-ref="dialValue"/>
    </svg>
    <div class="dial-readout">
      <div class="percent"><span data-ref="percent">--</span><i>%</i></div>
      <div class="level" data-ref="level"></div>
    </div>
  </div>

  <div class="stats" data-ref="stats">
    <div class="stat" data-role="runtime">
      <div class="stat-label" data-ref="runtimeLabel"></div>
      <div class="stat-value" data-ref="runtimeValue">--</div>
      <div class="stat-hint" data-ref="runtimeHint"></div>
    </div>
    <div class="stat" data-role="last_loss">
      <div class="stat-label" data-ref="onBatteryLabel"></div>
      <div class="stat-value" data-ref="onBatteryValue">--</div>
    </div>
    <div class="stat" data-role="voltage">
      <div class="stat-label" data-ref="voltageLabel"></div>
      <div class="stat-value" data-ref="voltageValue">--</div>
    </div>
    <div class="stat" data-role="outages">
      <div class="stat-label" data-ref="outagesLabel"></div>
      <div class="stat-value" data-ref="outagesValue">--</div>
    </div>
  </div>
</div>

<div class="history" data-ref="history">
  <div class="history-head">
    <span class="legend legend-battery" data-ref="historyBattery"></span>
    <span class="legend legend-mains" data-ref="historyMains"></span>
  </div>
  <svg class="spark" viewBox="0 0 100 32" preserveAspectRatio="none" aria-hidden="true">
    <path class="spark-area" data-ref="sparkArea" d=""/>
    <polyline data-ref="spark" points=""/>
  </svg>
  <svg class="strip" viewBox="0 0 100 6" preserveAspectRatio="none" aria-hidden="true">
    <rect class="strip-bg" x="0" y="0" width="100" height="6"/>
    <g data-ref="mainsStrip"></g>
  </svg>
  <div class="axis"><span data-ref="axisStart"></span><span data-ref="axisNow"></span></div>
</div>

<div class="extras" data-ref="extras" hidden></div>

<div class="actions" data-ref="actions">
  <button class="toggle" data-ref="chargeToggle" hidden>--</button>
  <button class="toggle" data-ref="shutdownToggle" hidden>--</button>
</div>
`;

/* ----------------------------------------------------------------- styles */

const STYLES = `
:host {
  --u-good: var(--success-color, #43a047);
  --u-warn: var(--warning-color, #ffa600);
  --u-bad: var(--error-color, #db4437);
  --u-info: var(--info-color, #039be5);
  --u-accent: var(--primary-color, #03a9f4);
  --u-muted: var(--secondary-text-color, #8a94a6);
  --u-ink: var(--primary-text-color, #e1e1e1);
  --u-line: var(--divider-color, rgba(127,127,127,.25));
  --u-tile: rgba(127, 127, 127, .10);
  --u-color: var(--u-good);
  display: block;
  container-type: inline-size;
}
:host([data-color="good"]) { --u-color: var(--u-good); }
:host([data-color="info"]) { --u-color: var(--u-info); }
:host([data-color="warn"]) { --u-color: var(--u-warn); }
:host([data-color="bad"]) { --u-color: var(--u-bad); }
:host([data-color="muted"]) { --u-color: var(--u-muted); }
:host([data-band="good"]) { --u-band: var(--u-good); }
:host([data-band="warn"]) { --u-band: var(--u-warn); }
:host([data-band="bad"]) { --u-band: var(--u-bad); }

ha-card.ups {
  display: block;
  overflow: hidden;
  padding: 0 16px 14px;
  border-top: 4px solid var(--u-color);
  transition: border-color 400ms ease;
}

/* --- banner --- */
.banner {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 0 10px;
  border-bottom: 1px solid var(--u-line);
  cursor: pointer;
}
.banner .glyph {
  flex: none;
  width: 32px; height: 32px;
  padding: 6px;
  border-radius: 10px;
  fill: #fff;
  background: var(--u-color);
  transition: background 400ms ease;
}
.banner .glyph[hidden] { display: none; }
:host(.is-alert) .banner .glyph { animation: blink 1.4s ease-in-out infinite; }
.banner-text { min-width: 0; flex: 1; }
.title {
  font-size: .8rem;
  color: var(--u-muted);
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.status {
  font-size: 1.15rem;
  font-weight: 600;
  color: var(--u-ink);
  line-height: 1.2;
}
.window-text {
  flex: none;
  font-size: .72rem;
  padding: 4px 9px;
  border-radius: 6px;
  border: 1px solid var(--u-line);
  color: var(--u-muted);
}
.window-text[hidden] { display: none; }

/* --- main --- */
.main {
  display: grid;
  grid-template-columns: 200px 1fr;
  gap: 14px;
  align-items: center;
  padding-top: 8px;
}
@container (max-width: 440px) {
  .main { grid-template-columns: 1fr; }
}

.dial { position: relative; width: 200px; max-width: 100%; margin: 0 auto; cursor: pointer; }
.dial > svg { width: 100%; display: block; overflow: visible; }
.dial-track { fill: none; stroke: var(--u-tile); stroke-width: 14; stroke-linecap: round; }
.dial-value {
  fill: none;
  stroke: var(--u-band, var(--u-good));
  stroke-width: 14;
  stroke-linecap: round;
  transition: stroke-dashoffset 900ms cubic-bezier(.22,.61,.36,1), stroke 400ms ease;
}
:host(.is-charging) .dial-value { animation: pulse 2.4s ease-in-out infinite; }
.dial-window {
  fill: none;
  stroke: var(--u-accent);
  stroke-width: 3;
  stroke-linecap: round;
  opacity: 0;
  transition: opacity 400ms ease;
}
.dial-readout {
  position: absolute;
  left: 0; right: 0; top: 46%;
  transform: translateY(-50%);
  text-align: center;
  pointer-events: none;
}
.percent {
  font-size: 2.6rem;
  font-weight: 700;
  line-height: 1;
  color: var(--u-ink);
  font-variant-numeric: tabular-nums;
  letter-spacing: -.02em;
}
.percent i { font-size: 1rem; font-style: normal; color: var(--u-muted); margin-left: 2px; }
.level {
  margin-top: 4px;
  font-size: .7rem;
  letter-spacing: .1em;
  text-transform: uppercase;
  font-weight: 600;
  color: var(--u-band, var(--u-muted));
}

/* --- stats --- */
.stats {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
  min-width: 0;
}
.stats[hidden] { display: none; }
.stat {
  background: var(--u-tile);
  border-radius: 10px;
  padding: 9px 11px;
  cursor: pointer;
  min-width: 0;
}
.stat-label { font-size: .7rem; color: var(--u-muted); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.stat-value { font-size: 1.05rem; font-weight: 600; color: var(--u-ink); margin-top: 2px; font-variant-numeric: tabular-nums; white-space: nowrap; }
.stat-hint { font-size: .66rem; color: var(--u-muted); }

/* --- history --- */
.history { margin-top: 12px; }
.history[hidden] { display: none; }
.history-head { display: flex; gap: 12px; font-size: .68rem; color: var(--u-muted); margin-bottom: 4px; }
.legend::before {
  content: "";
  display: inline-block;
  width: 10px; height: 4px;
  border-radius: 2px;
  margin-right: 5px;
  vertical-align: middle;
}
.legend-battery::before { background: var(--u-accent); }
.legend-mains::before { background: var(--u-good); }
.spark { width: 100%; height: 44px; display: block; }
.spark polyline {
  fill: none;
  stroke: var(--u-accent);
  stroke-width: 1.6;
  stroke-linejoin: round;
  vector-effect: non-scaling-stroke;
}
.spark-area { fill: var(--u-accent); opacity: .12; }
.strip { width: 100%; height: 6px; display: block; margin-top: 3px; border-radius: 3px; overflow: hidden; }
.strip-bg { fill: var(--u-tile); }
.strip rect.on { fill: var(--u-good); }
.strip rect.off { fill: var(--u-bad); }
.axis { display: flex; justify-content: space-between; font-size: .64rem; color: var(--u-muted); margin-top: 3px; }

/* --- extras --- */
.extras {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(84px, 1fr));
  gap: 6px;
  margin-top: 12px;
  padding-top: 10px;
  border-top: 1px solid var(--u-line);
}
.extras[hidden] { display: none; }
.mini { position: relative; text-align: center; cursor: pointer; --m-color: var(--u-accent); }
.mini[data-color="good"] { --m-color: var(--u-good); }
.mini[data-color="warn"] { --m-color: var(--u-warn); }
.mini[data-color="bad"] { --m-color: var(--u-bad); }
.mini[data-color="muted"] { --m-color: var(--u-muted); }
.mini svg { width: 64px; height: 64px; display: block; margin: 0 auto; }
.mini-track { fill: none; stroke: var(--u-tile); stroke-width: 6; stroke-linecap: round; }
.mini-value { fill: none; stroke: var(--m-color); stroke-width: 6; stroke-linecap: round; transition: stroke-dashoffset 700ms ease, stroke 400ms ease; }
.mini-value-text {
  position: absolute; left: 0; right: 0; top: 24px;
  font-size: .78rem; font-weight: 600; color: var(--u-ink);
  font-variant-numeric: tabular-nums;
}
.mini-name { font-size: .64rem; color: var(--u-muted); margin-top: -6px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }

/* --- actions --- */
.actions { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 12px; }
.actions[hidden] { display: none; }
.toggle {
  appearance: none;
  flex: 1 1 auto;
  border: 1px solid var(--u-line);
  background: transparent;
  color: var(--u-muted);
  border-radius: 8px;
  padding: 8px 12px;
  font: inherit;
  font-size: .78rem;
  cursor: pointer;
  transition: color 250ms ease, border-color 250ms ease, background 250ms ease;
}
.toggle[hidden] { display: none; }
.toggle[data-on="true"] {
  color: var(--u-good);
  border-color: var(--u-good);
  background: color-mix(in srgb, var(--u-good) 10%, transparent);
}
.toggle:hover { filter: brightness(1.15); }

/* --- variants --- */
[data-variant="compact"] .main { grid-template-columns: 150px 1fr; }
[data-variant="compact"] .dial { width: 150px; }
[data-variant="compact"] .percent { font-size: 2rem; }
[data-variant="gauge"] .main { grid-template-columns: 1fr; }
[data-variant="gauge"] .dial { width: 220px; }

.empty { padding: 14px 4px; color: var(--u-muted); }
.empty-title { font-size: 1.05rem; font-weight: 600; color: var(--u-ink); margin-bottom: 6px; }

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50%      { opacity: .55; }
}
@keyframes blink {
  0%, 100% { opacity: 1; }
  50%      { opacity: .35; }
}
@media (prefers-reduced-motion: reduce) {
  .dial-value, .banner .glyph { animation: none !important; }
  .dial-value, .mini-value { transition: none; }
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
      "Status panel for the Suptronics X120x UPS: battery dial, runtime estimate, outage history, charge and shutdown controls, optional extra gauges.",
    preview: true,
  });
}
