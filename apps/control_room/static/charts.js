/*
 * Control Room — the derived chart set (facelift a1).
 *
 * The passed brief (docs/research/control_room_direction.md §7) accepts charts only when each
 * one states its operator question, the decision it changes, its comparison baseline and time
 * scope, its completeness/sampling rule, a textual/table equivalent, and its fallback. It also
 * bars default charts from the resting screen. So this module does NOT touch the resting
 * regions: it renders inside a deliberate DRILL-DOWN lens opened from the persistent bar, and
 * every mark is a small SVG built from the catalog forms:
 *
 *   spend        ch-time-series (support 4, dataviz) + svg-micro  — line/area on one scale
 *   throughput   ch-time-series + ch-table   (support 8)          — step lines + a table
 *   failure      ch-time-series + ch-timeline (support 3, agentops) — step line + events
 *   dependency   ch-gauge [P] + ch-status-grid [P] + svg-micro    — bounded bars + status cells
 *
 * The catalogs say charts are authored as SVG+CSS with `viewBox` + `currentColor`/custom
 * properties (svg-theme), tiny repeated marks avoid a chart runtime (svg-micro), and only one
 * grammar is used per surface (ch-grammar). This file obeys all three: no library, no canvas,
 * theme-aware custom properties, and one SVG grammar throughout.
 *
 * Honesty rules carried from the brief:
 *   - a missing value (e.g. `cost: "unknown"`) is a GAP, never a zero;
 *   - fewer than two samples renders an explicit EMPTY state, never a blank panel;
 *   - a failed projection renders an explicit ERROR state, never an empty chart;
 *   - the retained window is the browser session, stated on the lens.
 *
 * No build step; loaded as a classic script after app.js and before first paint of the lens.
 */
"use strict";

(function () {
  // ── Tunables ───────────────────────────────────────────────────────────────────────────

  //: The browser-session retained window. A bounded ring, so a long-lived tab cannot grow
  //: without limit; charts label it explicitly rather than implying a server history.
  var HISTORY_MAX = 60;

  //: The four catalog-derived charts. `id` is the stable `[data-chart]` key the gate greps.
  var CHARTS = [
    {
      id: "spend",
      title: "SPEND",
      question: "Is spend trending toward the cap?",
      decision: "throttle a provider, raise a cap, or let it run",
      baseline: "first sample in this session window",
      scope: "browser session · one sample per control epoch",
      fallback: "the five ON-G4 values and the Money ledger",
    },
    {
      id: "throughput",
      title: "THROUGHPUT",
      question: "Is the fleet moving work or backing up?",
      decision: "add workers, re-interleave the queue, or investigate a stall",
      baseline: "the session's first running/queued/live counts",
      scope: "browser session · one sample per control epoch",
      fallback: "the exact ON-G2 counts and the run ledger",
    },
    {
      id: "failure",
      title: "FAILURE",
      question: "Are failures accumulating or clearing?",
      decision: "inspect the failing run, cancel, or quarantine",
      baseline: "zero failures",
      scope: "browser session · one sample per control epoch",
      fallback: "the ON-G3 risk answer and the failed-run roster",
    },
    {
      id: "dependency",
      title: "DEPENDENCY HEALTH",
      question: "Are the dependencies the room trusts healthy?",
      decision: "pause promotion, re-run a projector, or check a worker",
      baseline: "all dimensions up · projection lag 0",
      scope: "current snapshot (gauge) + session status grid",
      fallback: "the R0 ON-G1/ON-G6 answers and R3b detail",
    },
  ];

  //: Per-chart status carried on the card so CSS can size/label the empty/error states.
  var state = { glance: null, history: [], error: false, open: false };

  // ── Value parsing (an unknown is null, never 0) ─────────────────────────────────────────

  /**
   * Parse a display value into a number, or `null` when it is not a measured quantity.
   *
   * The glance projection renders unknown costs as the literal string "unknown" (its null-not-
   * zero discipline). Returning `null` here is what lets a line actually break at that point
   * instead of drawing a false zero, which is the whole point of the contract.
   */
  function toNumber(value) {
    if (typeof value === "number") return isFinite(value) ? value : null;
    if (typeof value === "string") {
      var match = value.replace(/[$,%\s]/g, "").match(/-?\d+(?:\.\d+)?/);
      return match ? parseFloat(match[0]) : null;
    }
    return null;
  }

  /** The consecutive non-null runs of a series, as `[index, value]` pairs. */
  function runs(values) {
    var out = [];
    var current = null;
    values.forEach(function (value, index) {
      if (value === null || value === undefined || !isFinite(value)) {
        current = null;
        return;
      }
      if (!current) {
        current = [];
        out.push(current);
      }
      current.push([index, value]);
    });
    return out;
  }

  function extent(values) {
    var clean = values.filter(function (v) { return typeof v === "number" && isFinite(v); });
    if (!clean.length) return { min: 0, max: 1 };
    var min = Math.min.apply(null, clean);
    var max = Math.max.apply(null, clean);
    if (min === max) {
      // A flat series still needs a visible band; pad by 1 (or 10% when the value is large).
      var pad = Math.abs(min) > 4 ? Math.abs(min) * 0.1 : 1;
      return { min: min - pad, max: max + pad };
    }
    return { min: min, max: max };
  }

  // ── SVG builders (viewBox + currentColor; no runtime) ───────────────────────────────────

  /** Create an SVG element in the SVG namespace (createElement alone would make an HTML node). */
  function svgEl(tag, attrs) {
    var node = document.createElementNS("http://www.w3.org/2000/svg", tag);
    if (attrs) {
      Object.keys(attrs).forEach(function (key) { node.setAttribute(key, attrs[key]); });
    }
    return node;
  }

  /** Map a series to `x y` point strings inside a `0..100` × `0..40` viewBox. */
  function toPoints(entries, count, min, max) {
    var span = max - min || 1;
    return entries.map(function (entry) {
      var x = count <= 1 ? 0 : (entry[0] / (count - 1)) * 100;
      var y = 38 - ((entry[1] - min) / span) * 34;
      return x.toFixed(2) + "," + y.toFixed(2);
    }).join(" ");
  }

  /**
   * Build a time-series chart body: a baseline grid line plus one polyline per contiguous run.
   * A run break is where an unknown sat, so the gap is visible rather than interpolated.
   */
  function timeSeries(chartId, series, labels) {
    var all = [];
    series.forEach(function (s) { all = all.concat(s.values); });
    var range = extent(all);
    var svg = svgEl("svg", {
      class: "chart-svg",
      viewBox: "0 0 100 40",
      preserveAspectRatio: "none",
      role: "img",
      "aria-label": chartAria(chartId),
    });
    var title = svgEl("title");
    title.textContent = chartTitle(chartId);
    svg.appendChild(title);
    var grid = svgEl("line", { class: "chart-gridline", x1: "0", y1: "38", x2: "100", y2: "38" });
    svg.appendChild(grid);
    var marks = 0;
    series.forEach(function (s, seriesIndex) {
      runs(s.values).forEach(function (run) {
        if (run.length < 1) return;
        var points = toPoints(run, s.values.length, range.min, range.max);
        if (run.length === 1) {
          // A single sample of a run has no line to draw; anchor it as a dot so it is not lost.
          var lone = svgEl("circle", {
            class: "chart-dot chart-series-" + seriesIndex,
            cx: points.split(",")[0], cy: points.split(",")[1], r: "1.4",
          });
          svg.appendChild(lone);
        } else {
          svg.appendChild(svgEl("polyline", {
            class: "chart-line chart-series-" + seriesIndex, points: points,
          }));
        }
        marks += 1;
      });
    });
    return { svg: svg, marks: marks, range: range, labels: labels };
  }

  function chartTitle(id) {
    for (var i = 0; i < CHARTS.length; i += 1) {
      if (CHARTS[i].id === id) return CHARTS[i].title.toLowerCase() + " over the retained window";
    }
    return "chart";
  }

  function chartAria(id) {
    for (var i = 0; i < CHARTS.length; i += 1) {
      if (CHARTS[i].id === id) return CHARTS[i].title + ": " + CHARTS[i].question;
    }
    return "chart";
  }

  /** A bounded gauge bar (0..100% of a known maximum) + its value label. */
  function gauge(label, value, maximum, unit) {
    var wrap = document.createElement("div");
    wrap.className = "chart-gauge";
    var head = document.createElement("div");
    head.className = "chart-gauge-head";
    var name = document.createElement("span");
    name.className = "chart-gauge-label";
    name.textContent = label;
    var reading = document.createElement("span");
    reading.className = "chart-gauge-value";
    if (value === null || value === undefined) {
      reading.textContent = "unknown";
      reading.setAttribute("data-unknown", "1");
    } else {
      reading.textContent = value + (unit || "");
    }
    head.appendChild(name);
    head.appendChild(reading);
    var track = document.createElement("div");
    track.className = "chart-gauge-track";
    var fill = document.createElement("div");
    fill.className = "chart-gauge-fill";
    var pct = value === null || maximum == null || maximum <= 0
      ? 0 : Math.max(0, Math.min(100, (value / maximum) * 100));
    fill.style.width = pct + "%";
    track.appendChild(fill);
    wrap.appendChild(head);
    wrap.appendChild(track);
    return wrap;
  }

  /** A status cell: a shape + a word, never colour alone. */
  function statusCell(name, state, age) {
    var cell = document.createElement("div");
    cell.className = "chart-status-cell";
    cell.setAttribute("data-status", state);
    var glyph = document.createElement("span");
    glyph.className = "chart-status-glyph";
    glyph.setAttribute("aria-hidden", "true");
    glyph.textContent = state === "up" ? "●" : state === "degraded" ? "▲"
      : state === "down" ? "✕" : "?";
    var word = document.createElement("span");
    word.className = "chart-status-word";
    word.textContent = state + (age === null || age === undefined ? "" : " · " + age + "s");
    cell.appendChild(glyph);
    cell.appendChild(word);
    return cell;
  }

  // ── Per-chart series extraction ─────────────────────────────────────────────────────────

  /** The spend series: cumulative-or-reported spend, and burn, per sample (nulls kept). */
  function spendSeries() {
    var spend = state.history.map(function (sample) {
      return sample.cost ? toNumber(sample.cost.spend) : null;
    });
    var burn = state.history.map(function (sample) {
      return sample.cost ? toNumber(sample.cost.burn) : null;
    });
    return [{ values: spend }, { values: burn }];
  }

  function throughputSeries() {
    return ["running", "queued", "live"].map(function (key) {
      return {
        values: state.history.map(function (sample) {
          return sample.run_counts ? Number(sample.run_counts[key] || 0) : null;
        }),
      };
    });
  }

  function failureSeries() {
    return [{
      values: state.history.map(function (sample) {
        return sample.run_counts ? Number(sample.run_counts.failed || 0) : null;
      }),
    }];
  }

  // ── Card rendering ──────────────────────────────────────────────────────────────────────

  /** Build one chart card skeleton (static structure, filled by `fillCard`). */
  function buildCard(chart) {
    var card = document.createElement("section");
    card.className = "chart-card";
    card.setAttribute("data-chart", chart.id);

    var head = document.createElement("header");
    head.className = "chart-head";
    var title = document.createElement("h3");
    title.className = "chart-title";
    title.textContent = chart.title;
    var question = document.createElement("p");
    question.className = "chart-question";
    question.textContent = chart.question;
    head.appendChild(title);
    head.appendChild(question);

    var body = document.createElement("div");
    body.className = "chart-body";
    body.setAttribute("data-chart-body", "");

    var table = document.createElement("table");
    table.className = "chart-table";
    table.setAttribute("data-chart-table", "");
    table.setAttribute("aria-label", chart.title + " textual equivalent");

    var meta = document.createElement("p");
    meta.className = "chart-meta";
    meta.textContent = "decision: " + chart.decision + " · baseline: " + chart.baseline
      + " · scope: " + chart.scope + " · fallback: " + chart.fallback;

    card.appendChild(head);
    card.appendChild(body);
    card.appendChild(table);
    card.appendChild(meta);
    return card;
  }

  /** Replace a body's content with one state (chart marks, empty, or error). */
  function setBody(body, node) {
    while (body.firstChild) body.removeChild(body.firstChild);
    body.appendChild(node);
  }

  function emptyNode(message) {
    var p = document.createElement("p");
    p.className = "chart-empty";
    p.setAttribute("data-chart-empty", "");
    p.textContent = message;
    return p;
  }

  function errorNode(message) {
    var p = document.createElement("p");
    p.className = "chart-error";
    p.setAttribute("data-chart-error", "");
    p.textContent = message;
    return p;
  }

  /**
   * Read one named value out of a history sample.
   *
   * A history sample is a slim slice of the glance payload (`{observed_at, cost, run_counts,
   * system, trust}`), not a flat row, so the textual equivalent resolves each column through
   * this one accessor. An absent value is an em dash, never an empty cell or a zero.
   */
  function sampleValue(sample, key) {
    if (!sample) return "—";
    if (key === "observed_at") return sample.observed_at || "—";
    if (key === "spend" || key === "burn" || key === "quota") {
      var cost = sample.cost || {};
      return cost[key] === undefined || cost[key] === null ? "—" : String(cost[key]);
    }
    if (key === "running" || key === "queued" || key === "live" || key === "failed") {
      var counts = sample.run_counts || {};
      return counts[key] === undefined || counts[key] === null ? "—" : String(counts[key]);
    }
    if (key === "projections") {
      var projections = (sample.system || {}).projections || {};
      return projections.state || "—";
    }
    if (key === "worst_age") {
      var trust = sample.trust || {};
      return trust.worst_age === undefined || trust.worst_age === null
        ? "—" : String(trust.worst_age);
    }
    return "—";
  }

  /** The textual equivalent: the last six samples, so the chart is never the only carrier. */
  function fillTable(table, columns) {
    while (table.firstChild) table.removeChild(table.firstChild);
    var thead = document.createElement("thead");
    var headRow = document.createElement("tr");
    columns.forEach(function (column) {
      var th = document.createElement("th");
      th.textContent = column;
      headRow.appendChild(th);
    });
    thead.appendChild(headRow);
    table.appendChild(thead);
    var tbody = document.createElement("tbody");
    state.history.slice(-6).forEach(function (sample) {
      var tr = document.createElement("tr");
      columns.forEach(function (column) {
        var td = document.createElement("td");
        td.textContent = sampleValue(sample, column);
        tr.appendChild(td);
      });
      tbody.appendChild(tr);
    });
    table.appendChild(tbody);
  }

  /** Render (or re-render) every card from the current state. */
  function render() {
    var grid = document.getElementById("chart-grid");
    if (!grid) return;
    if (!grid.childElementCount) {
      CHARTS.forEach(function (chart) { grid.appendChild(buildCard(chart)); });
    }
    var note = document.getElementById("lens-scope");
    if (note) {
      note.textContent = "retained window: this browser session · " + state.history.length
        + " sample" + (state.history.length === 1 ? "" : "s") + " · max " + HISTORY_MAX;
    }
    CHARTS.forEach(function (chart) {
      var card = grid.querySelector('[data-chart="' + chart.id + '"]');
      if (!card) return;
      var body = card.querySelector("[data-chart-body]");
      var table = card.querySelector("[data-chart-table]");
      var hasHistory = state.history.length >= 2;

      if (state.error) {
        setBody(body, errorNode("Projection unavailable — " + chart.fallback + "."));
        fillTable(table, ["observed_at"]);
        return;
      }
      if (!hasHistory) {
        setBody(body, emptyNode("No samples yet — waiting for the second control epoch."));
        fillTable(table, ["observed_at"]);
        return;
      }

      if (chart.id === "dependency") {
        renderDependency(body);
        fillTable(table, ["observed_at", "projections", "worst_age"]);
        return;
      }
      var series = chart.id === "spend" ? spendSeries()
        : chart.id === "throughput" ? throughputSeries() : failureSeries();
      var built = timeSeries(chart.id, series);
      if (!built.marks) {
        setBody(body, emptyNode("No measured " + chart.title.toLowerCase()
          + " in this window (values were unknown, not zero)."));
        fillTable(table, ["observed_at"]);
        return;
      }
      setBody(body, built.svg);
      fillTable(table, chart.id === "spend" ? ["observed_at", "spend", "burn"]
        : chart.id === "throughput" ? ["observed_at", "running", "queued", "live"]
        : ["observed_at", "failed"]);
    });
  }

  /** Dependency health: bounded gauges + a never-colour-alone status grid. */
  function renderDependency(body) {
    var wrap = document.createElement("div");
    wrap.className = "chart-dependency";
    var latest = state.history[state.history.length - 1] || {};
    var trust = latest.trust || {};
    var system = latest.system || {};
    var worstAge = toNumber(trust.worst_age);
    // The threshold is the p3 stale-after default (900s); a gauge needs a real maximum.
    wrap.appendChild(gauge("worst projection age", worstAge, 900, "s"));
    var projections = system.projections || {};
    wrap.appendChild(gauge("projection age", toNumber(projections.age_seconds), 900, "s"));
    var grid = document.createElement("div");
    grid.className = "chart-status-grid";
    ["browser", "control", "workers", "projections"].forEach(function (name) {
      var dim = system[name] || { state: "unknown", age_seconds: null };
      grid.appendChild(statusCell(name, String(dim.state || "unknown"),
        toNumber(dim.age_seconds)));
    });
    wrap.appendChild(grid);
    setBody(body, wrap);
  }

  // ── The lens (drill-down; hidden at rest) ───────────────────────────────────────────────

  function open(kind) {
    var lens = document.getElementById("chart-lens");
    if (!lens) return;
    state.open = true;
    state.focus = kind || null;
    lens.hidden = false;
    var trigger = document.getElementById("lens-open");
    if (trigger) trigger.setAttribute("aria-expanded", "true");
    render();
    if (kind) {
      var card = document.querySelector('[data-chart="' + kind + '"]');
      if (card) card.setAttribute("data-focus", "1");
    }
    var close = document.getElementById("lens-close");
    if (close) close.focus();
  }

  function close() {
    var lens = document.getElementById("chart-lens");
    if (!lens) return;
    state.open = false;
    lens.hidden = true;
    var trigger = document.getElementById("lens-open");
    if (trigger) {
      trigger.setAttribute("aria-expanded", "false");
      trigger.focus();
    }
  }

  /**
   * The public seam app.js calls after every successful render.
   *
   * `history` is the client's bounded ring of glance slices; `error` names a failed projection
   * so the lens can render its explicit error state instead of a stale chart.
   */
  function update(glance, history, error) {
    state.glance = glance || null;
    state.history = Array.isArray(history) ? history : [];
    state.error = Boolean(error);
    if (state.open) render();
  }

  function wire() {
    var lens = document.getElementById("chart-lens");
    if (lens) {
      var params = new URLSearchParams(window.location.search);
      if (params.get("lens")) open(params.get("lens"));
    }
    var trigger = document.getElementById("lens-open");
    if (trigger) trigger.addEventListener("click", function () { open(null); });
    var closeButton = document.getElementById("lens-close");
    if (closeButton) closeButton.addEventListener("click", close);
    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape" && state.open) close();
    });
    var grid = document.getElementById("chart-grid");
    if (grid) {
      grid.addEventListener("click", function (event) {
        var card = event.target.closest && event.target.closest("[data-chart]");
        if (card) {
          var previous = grid.querySelector('[data-focus="1"]');
          if (previous) previous.removeAttribute("data-focus");
          card.setAttribute("data-focus", "1");
        }
      });
    }
  }

  // Expose the seam. app.js calls `update`; the gate calls `open`/`close` through the button.
  window.ControlRoomCharts = {
    update: update,
    open: open,
    close: close,
    getState: function () {
      return { history: state.history.length, open: state.open, error: state.error };
    },
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", wire);
  } else {
    wire();
  }
})();
