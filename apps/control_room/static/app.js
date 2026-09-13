/*
 * Control Room — the one resting screen (facelift a0).
 *
 * This client hydrates the region skeleton in index.html from ONE read-only projection
 * (`GET /api/glance`) and follows the bounded `GET /api/events` stream for epoch transitions.
 * It deliberately replaces the former destination-board portal: the resting screen answers
 * every `ON-G1..G7` glance need at once (docs/research/control_room_ia.md §4), so there is no
 * navigation here at all.
 *
 * Contract this file implements (the render gate asserts it; see
 * scripts/verify_control_room_rendering.py):
 *
 *   - Exactly one `[data-region]` per R0/R1/R2/R3a/R3b/R3c and one `[data-answer]` per
 *     ON-G1..ON-G7, each answer inside its canonical region.
 *   - Every required `[data-field]` carries exactly one `[data-label]` + `[data-value]`.
 *   - Required values carry `[data-no-ellipsis]`; identifiers carry `[data-identifier]` and may
 *     middle-elide. No required value is ever clipped.
 *   - Row / item / marginal counts are fixed per viewport (8/7/3 rows; 5/4/3 attention items),
 *     so a screenshot proves the bounded-at-rest promise rather than a DOM-only presence.
 *   - All content is built with `element()`/`textContent`; no string is ever parsed as HTML.
 *
 * The file has no dependencies and no build step; it runs as a classic script after the DOM.
 *
 * ── recognizability (the a5 design-adversary contract) ────────────────────────────────────────
 * The exact selector that carries each stranger-test claim on the RESTING screenshot. Each is
 * built in this file and styled in style.css; the mirror block in index.html documents the DOM.
 *
 *   (a) live CLI agent sessions — `renderRunRow` builds `.session-band[data-agent]` carrying the
 *       `agent-prompt` glyph, the `row-status` rail, and the `session.identity`, `terminal.target`,
 *       `command.current`, `model.provider` and `attempt.number` fields.
 *         selector: `.run-row[data-run-id] .session-band[data-agent]`
 *   (b) a run needs a decision — `renderAttention` builds the DECISION work item under
 *       `[data-answer="ON-G5"]` with `[data-attention-class="decision"]`, the eligibility token,
 *       the `queue-authority`/`queue-action` chips, and `[data-authority="controller"]`.
 *       The reserved decision/risk (and a NEAR CAP slot when the packet's `cost.money_risk`
 *       says so) each carry a REAL `<button data-attention-toggle>` that expands a read-only
 *       `[data-attention-detail]` panel IN PLACE — packet values only, never a mutation.
 *         selector: `[data-answer="ON-G5"] [data-field="decision.eligibility"]`
 *   (c) spend against a hard budget — `renderRunRow` builds `.row-lease[data-budget-state]` (the
 *       headroom bar) with `data-budget-reserved`, `data-budget-settled`, `data-budget-cap`,
 *       `data-budget-headroom` and `data-budget-settlement`, plus the `cost.provenance` pair.
 *         selector: `.run-row[data-run-id] .row-lease[data-budget-state]`
 *   (d) evidence is inspectable — `renderRunRow` builds `.row-evidence [data-evidence-class]`
 *       marks and `decision.receipt`; `openDock` builds the causal ladder, the typed address and
 *       the bounded follow/pause attempt feed.
 *         selector: `.run-row[data-run-id] .row-evidence [data-evidence-class="measured"]`
 *
 * ── state language (s2; synthesis v2 §5.2) ────────────────────────────────────────────────────
 * Every run row renders the packet's lifecycle as glyph + word + colour + a settled timestamp:
 * `LIFECYCLE_TOKENS` maps the RunState enum to an operator token (an unmapped enum degrades to
 * `unknown` — never a guess), `.row-status[data-state]` carries the colour (styled in style.css),
 * and the NON-FIELD `.row-settled` marker carries the last recorded change plus its age
 * (`data-settled-at` / `data-age-seconds`, or the literal `settled unknown`). The per-run
 * `attention.state` is read from the packet and clamped to `active|none` — never derived, never
 * an invented `unknown`. The roster is triage-ranked (failures and blocked work lead, then the
 * in-flight fleet, then settled), and a row whose RECORDED age passes the stale floor carries
 * `data-stale="true"` and dims. Only genuine live transitions animate, and the whole layer
 * collapses under `prefers-reduced-motion`.
 */
"use strict";

(function () {
  // ── Small DOM helpers ──────────────────────────────────────────────────────────────────

  /**
   * Create an element. `attrs` maps attribute names to values; `null`/`undefined` values are
   * skipped, and a bare `""` means "present with an empty value" (used for the data-* contract
   * flags). Text is always assigned through `textContent`; markup is never parsed from a string.
   */
  function element(tag, className, attrs, text) {
    var node = document.createElement(tag);
    if (className) node.className = className;
    if (attrs) {
      Object.keys(attrs).forEach(function (key) {
        var value = attrs[key];
        if (value === null || value === undefined) return;
        node.setAttribute(key, value === true ? "" : String(value));
      });
    }
    if (text !== undefined && text !== null) node.textContent = String(text);
    return node;
  }

  /** Remove every child of `node` (a safe "clear" that never injects markup). */
  function clear(node) {
    while (node.firstChild) node.removeChild(node.firstChild);
  }

  /**
   * Reconcile a keyed list against `host` — write-on-change, not clear-and-rebuild.
   *
   * The no-regression contract (direction §12.2 #3) is that a keyed list performs no write on
   * a no-op poll and preserves the identity (and focus) of an unchanged row across a live
   * update. Each desired node carries a stable key attribute and a `__signature` string of its
   * data; an existing host child with the same key AND signature is reused in place, one with a
   * changed signature is replaced, and a key that disappeared is removed. New nodes are built
   * detached, so reusing an existing child never touches the live DOM.
   */
  function reconcileList(host, nodes, keyAttr) {
    var existing = {};
    Array.prototype.slice.call(host.children).forEach(function (child) {
      var key = child.getAttribute(keyAttr);
      if (key !== null) existing[key] = child;
    });
    var seen = {};
    nodes.forEach(function (node, index) {
      var key = node.getAttribute(keyAttr);
      seen[key] = true;
      var current = existing[key];
      if (current && current.__signature === node.__signature) {
        // Unchanged: keep the live node, only fix its position.
        if (host.children[index] !== current) {
          host.insertBefore(current, host.children[index] || null);
        }
        return;
      }
      if (current) host.replaceChild(node, current);
      else host.insertBefore(node, host.children[index] || null);
    });
    // Drop anything the new view no longer contains.
    Array.prototype.slice.call(host.children).forEach(function (child) {
      var key = child.getAttribute(keyAttr);
      if (key !== null && !seen[key]) host.removeChild(child);
    });
  }

  //: Short field labels for the dense (narrow) row: 16 labelled fields cannot share a 472px
  //: row, so narrow abbreviates the label while desktop keeps the full word. Mobile hides labels
  //: entirely (triage). The `data-field` key is unchanged in every case, so the schema holds.
  var SHORT_ROW_LABELS = {
    "session.identity": "ses",
    "spec.cell": "spec",
    "terminal.target": "tgt",
    "command.current": "cmd",
    "model.provider": "mdl",
    "attempt.number": "att",
    "phase.progress": "ph",
    "lifecycle.state": "life",
    "run.live": "live",
    "source.commit": "cmt",
    "cost.provenance": "cost",
    "attention.state": "attn",
    "evidence.advisory": "said",
    "evidence.measured": "meas",
    "evidence.source": "src",
    "decision.eligibility": "elig",
    "decision.receipt": "rcpt",
  };

  /** The per-viewport at-rest capacities fixed by docs/research/control_room_ia.md §3.2. */
  function capacities() {
    var width = window.innerWidth;
    if (width >= 1200) return { rows: 8, attention: 5 };
    if (width >= 760) return { rows: 7, attention: 4 };
    return { rows: 3, attention: 3 };
  }

  // ── Field construction (the §10.2 label/value contract) ────────────────────────────────

  /**
   * Append one `[data-field]` with its single `[data-label]` and `[data-value]`.
   *
   * `opts.identifier` marks a value that may middle-elide; every other value gets
   * `[data-no-ellipsis]` because the gate rejects a clipped required value. `opts.state` and
   * `opts.age` are the `ON-G1` system-dimension attributes. `opts.evidenceClass` is the
   * ADVISORY/MEASURED/SOURCE material mark. Content is assigned via `textContent` only.
   */
  function appendField(parent, key, label, value, opts) {
    opts = opts || {};
    var field = element("span", "field", { "data-field": key });
    if (opts.maxLines !== undefined) field.setAttribute("data-max-lines", String(opts.maxLines));
    if (opts.microRow) field.setAttribute("data-micro-row", "");
    if (opts.evidenceClass) field.setAttribute("data-evidence-class", opts.evidenceClass);
    // A compact visible label still names the full field for assistive tech.
    if (opts.title) field.setAttribute("title", opts.title);

    field.appendChild(element("span", null, { "data-label": "" }, label));

    var valueNode = element("span", null, { "data-value": "" }, value);
    if (opts.identifier) valueNode.setAttribute("data-identifier", "");
    else valueNode.setAttribute("data-no-ellipsis", "");
    if (opts.state) {
      valueNode.setAttribute("data-state", opts.state);
      valueNode.className = "value-state-" + opts.state;
    }
    if (opts.age !== undefined && opts.age !== null) {
      valueNode.setAttribute("data-age-seconds", String(opts.age));
    }
    field.appendChild(valueNode);
    parent.appendChild(field);
    return field;
  }

  /** A value-only span (health detail / marginal buckets) that still satisfies the value rules. */
  function appendRawValue(parent, text, className) {
    var node = element("span", className || null, { "data-value": "", "data-no-ellipsis": "" }, text);
    parent.appendChild(node);
    return node;
  }

  // ── Region renderers ───────────────────────────────────────────────────────────────────

  /** R0 `ON-G1`: browser / control / workers / projections, each naming its state + worst age. */
  function renderSystem(glance) {
    var host = document.getElementById("system-cells");
    clear(host);
    ["browser", "control", "workers", "projections"].forEach(function (name) {
      var dim = (glance.system && glance.system[name]) || { state: "unknown", age_seconds: 0 };
      var state = String(dim.state || "unknown");
      var age = Number(dim.age_seconds || 0);
      // A compact visible label ("proj") keeps the mobile forcing grid within 72px; the full
      // dimension name stays accessible through the field's title.
      var short = name === "projections" ? "proj" : name;
      appendField(host, "system." + name, short, state + " · " + age + "s", {
        state: state,
        age: age,
        maxLines: 1,
        microRow: true,
        title: "system " + name,
      });
    });
  }

  /** R0 `ON-G6`: the complete trust verdict (epoch, worst age, projection state, four counts). */
  function renderTrust(glance) {
    var host = document.getElementById("trust-cells");
    clear(host);
    var trust = glance.trust || {};
    var rows = [
      ["trust.epoch", "epoch", "epoch", trust.epoch],
      ["trust.worst_age", "age", "worst age", trust.worst_age + "s"],
      ["trust.projection_state", "proj", "projection state", trust.projection_state],
      ["trust.degraded_count", "deg", "degraded count", trust.degraded_count],
      ["trust.stale_count", "stale", "stale count", trust.stale_count],
      ["trust.partial_count", "part", "partial count", trust.partial_count],
      ["trust.unknown_count", "unk", "unknown count", trust.unknown_count],
    ];
    rows.forEach(function (row) {
      appendField(host, row[0], row[1], row[3], { maxLines: 1, title: row[2] });
    });
  }

  // ── R0 scope/truth strip (build step 3) ─────────────────────────────────────────────────
  //
  // The persistent strip: the at-rest summary the operator reads first. Every value here is
  // EMITTED by the glance projection (`glance.truth`) or observed by THIS client (the SSE
  // stream state) — the client never derives a consequential value from raw rows. Each cell
  // carries its own source + age, so a stranger can age a value without hovering it; a value
  // whose signal the packet does not carry (the `done-unseen` acknowledgement watermark, D1)
  // renders an explicit `unknown`, never a fabricated zero.

  //: A packet value older than this is called out as stale in the strip. [H] 15 min — the same
  //: order as the run heartbeat/watchdog floor and the row stale floor in the state language.
  var STRIP_STALE_SECONDS = 900;

  //: The lifecycle groups a count chip filters the roster by: the strip's three count cells map
  //: to the packet `RunState` enums that belong to each group. A count is a FILTER (direction
  //: §3.3; v1 counters-as-filters) — activating it narrows the VISIBLE roster; activating it
  //: again clears the filter. The count itself stays the fleet-wide packet count, never the
  //: size of the filtered sample (that would be a client-derived consequential value).
  var COUNT_FILTERS = {
    running: { running: 1, verifying: 1, projecting: 1 },
    blocked: { awaiting_approval: 1 },
    done_unseen: { merged: 1, published: 1 },
  };

  //: The label, door and accessible title for each count cell. The lens is where the full,
  //: unbounded view of the same number lives — the strip is the door, the lens is the room.
  var COUNT_META = {
    running: { label: "RUN", lens: "fleet", title: "runs executing" },
    blocked: { label: "BLK", lens: "attention", title: "runs awaiting a decision" },
    done_unseen: { label: "DONE", lens: "sessions", title: "done runs not yet acknowledged" },
  };

  /** A compact age label with the unit (`0s` / `12m`), or `unknown` when no age was observed. */
  function ageLabel(age) {
    return typeof age === "number" && age >= 0 ? compactAge(age) : "unknown";
  }

  /** True only when a genuine recorded age crosses the stale floor (an unknown age is not stale). */
  function isStaleAge(age, threshold) {
    return typeof age === "number" && age > threshold;
  }

  /**
   * One strip cell: the provenance carriers (`data-source`, `data-age-seconds`, `data-stale`)
   * plus the visible value/lens/provenance its caller appends. `title` makes the full source
   * available to assistive tech without widening the compact row.
   */
  function stripCell(opts) {
    return element("span", "strip-cell", {
      "data-cell": opts.key,
      "data-source": opts.source,
      "data-age-seconds":
        opts.age === null || opts.age === undefined ? "unknown" : String(opts.age),
      "data-stale": opts.stale ? "true" : "false",
      title: opts.title,
    });
  }

  /** The visible source · age provenance every strip cell carries. */
  function stripProvenance(source, age) {
    var prov = element("span", "strip-prov", { "aria-hidden": "true" });
    // The source and the age are separate spans so the narrow breakpoint can drop the whole
    // provenance line to keep the strip a single row. The source+age are never lost: they stay
    // on the cell's `data-source`/`data-age-seconds` and in its title, and the visible line
    // returns at desktop width.
    prov.appendChild(element("span", "strip-prov-source", null, source));
    prov.appendChild(element("span", "strip-prov-age", null, "\u00b7 " + ageLabel(age)));
    return prov;
  }

  /** The deliberate lens door a strip cell opens (the workbench panel for that value). */
  function stripLens(lens, what) {
    var button = element("button", "strip-lens", {
      type: "button",
      "data-lens": lens,
      "aria-label": "Open the " + lens + " lens for " + what,
      title: "Open the " + lens + " lens",
    }, "\u25B8");
    button.addEventListener("click", function () { openLens(lens, button); });
    return button;
  }

  /**
   * R0 truth strip: the three lifecycle counts (filters), spend vs the window cap, the worst
   * projection lag, and the live stream state. Rebuilt only when the glance payload changes
   * (the signature covers `truth`); the stream cell is refreshed independently by the stream
   * health loop, because the stream state is the client's own observation, not the packet's.
   */
  function renderTruthStrip(glance) {
    var host = document.getElementById("truth-strip");
    if (!host) return;
    clear(host);
    var truth = glance.truth || {};
    var counts = truth.counts || {};
    var countsAge = truth.counts_age_seconds;
    var countsSource = truth.counts_source || "unavailable";

    ["running", "blocked", "done_unseen"].forEach(function (key) {
      var meta = COUNT_META[key];
      var raw = counts[key];
      var value = raw === undefined || raw === null ? "unknown" : Number(raw);
      var stale = isStaleAge(countsAge, STRIP_STALE_SECONDS);
      var cell = stripCell({
        key: key,
        source: countsSource,
        age: countsAge,
        stale: stale,
        title: meta.title + " · source " + countsSource + " · age " + ageLabel(countsAge),
      });
      // The count chip IS the filter: activating it narrows the roster to this lifecycle group.
      var chip = element("button", "strip-count", {
        type: "button",
        "data-filter": key,
        "aria-pressed": AppState.runFilter === key ? "true" : "false",
        title: "Filter the run roster to " + meta.title,
      });
      chip.appendChild(element("span", "strip-label", null, meta.label));
      chip.appendChild(element("span", "strip-value", { "data-value": "", "data-no-ellipsis": "" }, value));
      chip.addEventListener("click", function () { setRunFilter(key); });
      cell.appendChild(chip);
      cell.appendChild(stripLens(meta.lens, meta.title));
      if (stale) cell.appendChild(element("span", "strip-stale", null, "stale"));
      cell.appendChild(stripProvenance(countsSource, countsAge));
      host.appendChild(cell);
    });

    // ── spend vs the window cap ──────────────────────────────────────────────────────────
    var spend = truth.spend || {};
    var spendAge = spend.age_seconds;
    var spendCell = stripCell({
      key: "spend",
      source: spend.source || "unavailable",
      age: spendAge,
      stale: isStaleAge(spendAge, STRIP_STALE_SECONDS),
      title: "Spend against the subscription window cap",
    });
    spendCell.appendChild(element("span", "strip-label", null, "SPEND"));
    spendCell.appendChild(element("span", "strip-value", { "data-value": "", "data-no-ellipsis": "" },
      (spend.value || "unknown") + " / " + (spend.cap || "unknown")));
    spendCell.appendChild(stripLens("money", "spend against the cap"));
    spendCell.appendChild(stripProvenance(spend.source || "unavailable", spendAge));
    host.appendChild(spendCell);

    // ── worst projection lag ─────────────────────────────────────────────────────────────
    var lag = truth.projection_lag || {};
    var lagState = String(lag.value || "unknown");
    var lagStale = lagState === "stale" || lagState === "failing";
    var lagCell = stripCell({
      key: "projection_lag",
      source: lag.source || "projection watermarks",
      age: lag.age_seconds,
      stale: lagStale,
      title: "Worst projector state and lag",
    });
    lagCell.appendChild(element("span", "strip-label", null, "LAG"));
    var lagText = lagState + (lag.lag === null || lag.lag === undefined ? "" : " \u00b7 " + lag.lag);
    lagCell.appendChild(element("span", "strip-value", { "data-value": "", "data-no-ellipsis": "" }, lagText));
    lagCell.appendChild(stripLens("health", "projection lag"));
    if (lagStale) lagCell.appendChild(element("span", "strip-stale", null, "stale"));
    lagCell.appendChild(stripProvenance(lag.source || "projection watermarks", lag.age_seconds));
    host.appendChild(lagCell);

    // ── the live stream state (the client's own observation) ─────────────────────────────
    var streamCell = stripCell({
      key: "stream",
      source: "events stream",
      age: null,
      stale: false,
      title: "Live event stream state and age",
    });
    streamCell.appendChild(element("span", "strip-label", null, "STREAM"));
    streamCell.appendChild(element("span", "strip-value", { "data-value": "", "data-no-ellipsis": "" }, "unknown"));
    streamCell.appendChild(stripLens("operations", "stream state"));
    streamCell.appendChild(stripProvenance("events", null));
    host.appendChild(streamCell);
    renderStreamCell();
  }

  /** Refresh only the stream cell from the client's SSE state (never a glance re-render). */
  function renderStreamCell() {
    var cell = document.querySelector('#truth-strip [data-cell="stream"]');
    if (!cell) return;
    var state = AppState.streamState || "connecting";
    var age = AppState.streamAgeSeconds;
    var stale = state === "stale" || state === "disconnected"
      || isStaleAge(age, STREAM_STALE_SECONDS);
    cell.setAttribute("data-source", "events stream");
    cell.setAttribute("data-age-seconds", age === null || age === undefined ? "unknown" : String(age));
    cell.setAttribute("data-state", state);
    cell.setAttribute("data-stale", stale ? "true" : "false");
    var value = cell.querySelector("[data-value]");
    if (value) value.textContent = state + (age === null || age === undefined ? "" : " \u00b7 " + compactAge(age));
    var provAge = cell.querySelector(".strip-prov-age");
    if (provAge) {
      provAge.textContent = "\u00b7 " + (age === null || age === undefined ? "unknown" : compactAge(age));
    }
  }

  /**
   * Activate (or clear) the roster's lifecycle filter. The chip's own `aria-pressed` names the
   * state, so this is not announced as a state transition; the roster re-ranks the filtered set
   * with the same keyed write-on-change reconciler (no full rebuild).
   */
  function setRunFilter(key) {
    AppState.runFilter = AppState.runFilter === key ? null : key;
    var chips = document.querySelectorAll("#truth-strip [data-filter]");
    Array.prototype.forEach.call(chips, function (chip) {
      chip.setAttribute("aria-pressed",
        chip.getAttribute("data-filter") === AppState.runFilter ? "true" : "false");
    });
    if (AppState.glance) renderRunList(AppState.glance);
  }

  /** Open a workbench lens (the deliberate door a strip cell / count points at). */
  function openLens(lens, origin) {
    if (window.ControlRoomParity && window.ControlRoomParity.openWorkbench) {
      window.ControlRoomParity.openWorkbench(origin || null);
      window.ControlRoomParity.openPanel(lens);
    }
  }

  /** R2 `ON-G2`: the exact running/queued/failed/live counts; a null count is `unknown`. */
  function renderRunCounts(glance) {
    var host = document.getElementById("run-counts");
    clear(host);
    var counts = glance.run_counts || {};
    ["running", "queued", "failed", "live"].forEach(function (key) {
      var value = counts[key];
      var text = value === undefined || value === null ? "unknown" : Number(value);
      appendField(host, "runs." + key, key, text, { maxLines: 1 });
    });
  }

  /** The governed eligibility vocabulary: only these name an acting controller (Move 3). */
  var GOVERNED = { approve: true, promote: true, cancel: true, retire: true };

  /** Take the basename of a path-like token (`wt/control-room` → `control-room`). */
  function basename(value) {
    return String(value === undefined || value === null ? "unknown" : value).split("/").pop();
  }

  // ── State language (one vocabulary, never colour alone) ────────────────────────────────
  //
  // Synthesis v2 §5.2 (the reconciliation of the v1 "state as colour and rhythm" idea): state is
  // glyph + word + colour + a settled timestamp — colour is never the sole carrier and rhythm is
  // not identity. This map is the ONE translation from the packet's RunState enum to the
  // operator-facing token. It is total over the enum the control database enforces
  // (`control_db.py:140-182`); anything the map does not know — an enum a future producer adds —
  // degrades to the explicit `unknown` token rather than a guessed word (openhands O1: degrade on
  // unknown, never throw), and never to a fabricated reassuring state.
  //
  //   token.tone  — the presentation key (`data-state`); CSS supplies the colour, so the state
  //                 survives forced-colors and a colour-blind reader.
  //   token.rank  — the roster's triage order (direction §3.1: failures first, then running/
  //                 queued, then settled). Lower leads.
  var LIFECYCLE_TOKENS = {
    queued:            { word: "queued",     glyph: "\u25CC", tone: "idle",    rank: 2 },
    running:           { word: "working",    glyph: "\u25D0", tone: "live",    rank: 2 },
    verifying:         { word: "verifying",  glyph: "\u25D0", tone: "live",    rank: 2 },
    promoting:         { word: "promoting",  glyph: "\u25D0", tone: "live",    rank: 2 },
    projecting:        { word: "projecting", glyph: "\u25D0", tone: "live",    rank: 2 },
    // `awaiting_approval` is a DESIGNED stop, not a failure: the human owes a decision, so it
    // leads the roster beside a failure rather than waiting in the settled tail.
    awaiting_approval: { word: "blocked",    glyph: "\u00D7", tone: "blocked", rank: 1 },
    promotable:        { word: "ready",      glyph: "\u25B8", tone: "waiting", rank: 1 },
    merged:            { word: "merged",     glyph: "\u2713", tone: "done",    rank: 3 },
    published:         { word: "published",  glyph: "\u2713", tone: "done",    rank: 3 },
    failed:            { word: "failed",     glyph: "\u2715", tone: "failed",  rank: 0 },
    cancelled:         { word: "cancelled",  glyph: "\u2298", tone: "stopped", rank: 4 },
    quarantined:       { word: "quarantined", glyph: "\u2298", tone: "stopped", rank: 4 },
  };

  //: The explicit degradation token — what an unmapped lifecycle renders, never a guess.
  var UNKNOWN_LIFECYCLE = { word: "unknown", glyph: "?", tone: "unknown", rank: 5 };

  //: A row is stale when its last recorded lifecycle change is older than this ([H] 15 min — the
  //: same order as the run heartbeat/watchdog floor). Staleness is only ever asserted from a
  //: RECORDED timestamp; an unknown age is never treated as stale (absence of evidence is not
  //: evidence of age).
  var ROW_STALE_SECONDS = 900;

  /** Resolve one packet lifecycle value to its operator token (unknown degrades, never throws). */
  function lifecycleToken(state) {
    return LIFECYCLE_TOKENS[String(state)] || UNKNOWN_LIFECYCLE;
  }

  /**
   * The packet's per-run attention axis, read VERBATIM and clamped to its closed vocabulary.
   *
   * The projection emits exactly `active` or `none` (`glance.py:568`); this axis is NOT the
   * client's to derive, and `unknown` is deliberately not a member. A value the packet never sent
   * must not make the room claim an attention state it did not observe, so anything that is not
   * the literal `active` renders `none` — the packet's own word for "no attention". (The honest
   * `unknown` lives on the LIFECYCLE axis, which has its own explicit degradation token.)
   */
  function attentionToken(value) {
    return String(value) === "active" ? "active" : "none";
  }

  /**
   * The roster's triage rank: lower leads. Failures first, then the blocked/ready work that needs
   * a human, then the in-flight fleet, then settled runs, then stopped/unknown ones. A live
   * attention mark lifts an otherwise-in-flight row into the decision group. Ties keep the
   * packet's own order (a stable sort), so ranking never reshuffles rows the projection ordered.
   */
  function triageRank(run) {
    var token = lifecycleToken(run["lifecycle.state"]);
    if (run["attention.state"] === "active" && token.rank > 1) return token.rank - 1;
    return token.rank;
  }

  /** A stable copy of the roster in triage order (attention first, then in-flight, then settled). */
  function rankRoster(runs) {
    return runs.slice().sort(function (a, b) {
      return triageRank(a) - triageRank(b);
    });
  }

  /**
   * The most recent RECORDED lifecycle timestamp on a run, in epoch ms, or `null` when none was
   * recorded. The packet's `run.events` is the run's real control-record history (attempts, gate
   * verdicts, approvals, command receipts — `glance.py:473-532`); its newest timestamp is the
   * latest provable state change. A packet-provided `lifecycle.changed_at` is honoured too, so a
   * projection that later stamps the exact transition time wins without a client change.
   */
  function settledMs(run) {
    var latest = timestampMs(run["lifecycle.changed_at"]);
    var events = Array.isArray(run["run.events"]) ? run["run.events"] : [];
    events.forEach(function (event) {
      var ms = timestampMs(event && event.ts);
      if (ms !== null && (latest === null || ms > latest)) latest = ms;
    });
    return latest;
  }

  /** A short, stable age label (`42s` / `12m` / `3h` / `2d`) — never a raw second count. */
  function compactAge(seconds) {
    if (seconds < 60) return seconds + "s";
    if (seconds < 3600) return Math.floor(seconds / 60) + "m";
    if (seconds < 86400) return Math.floor(seconds / 3600) + "h";
    return Math.floor(seconds / 86400) + "d";
  }

  /**
   * The run's settled marker: the last recorded lifecycle change, its age, and whether the row has
   * aged past the stale floor. No recorded timestamp is the literal `unknown` (never a fabricated
   * `0s`), and an unknown age is never stale.
   */
  function settledFacets(run) {
    var ms = settledMs(run);
    if (ms === null) {
      return {
        iso: null,
        age: null,
        stale: false,
        text: "settled unknown",
        title: "no recorded lifecycle change for this run",
      };
    }
    var age = Math.max(0, Math.floor((Date.now() - ms) / 1000));
    var iso = new Date(ms).toISOString();
    return {
      iso: iso,
      age: age,
      stale: age > ROW_STALE_SECONDS,
      text: "settled " + compactAge(age),
      title: "lifecycle last changed " + iso + " (" + compactAge(age) + " ago)",
    };
  }

  //: The most phase segments a tile draws. The packet's `phases_total` is a workflow's declared
  //: phase count and is small in practice; the bound stops an absurd total from minting an
  //: unbounded DOM. Past the cap the bar reports the overflow instead of silently growing.
  var PHASE_SEGMENT_MAX = 24;

  /**
   * Build the segmented phase bar for one run tile (build step 5).
   *
   * An R2 run tile shows progress as a FRACTION (`phase.progress` `n/m`, the required field) AND
   * as a segmented bar, so a stranger reads it as shape and not only as text. Every number comes
   * from the packet's own `phase.progress` value: the client never invents a denominator or a
   * completion count. A progress value that is `unknown`, malformed or non-positive renders ONE
   * explicit `unknown` segment (`data-phase-state="unknown"`), never a fabricated full or empty
   * bar. The bar is a NON-FIELD affordance, so the exact 16-field row schema is untouched.
   */
  function renderPhaseBar(progress) {
    var bar = element("span", "row-phase", { "data-phase-bar": "" });
    var raw = progress === undefined || progress === null ? "" : String(progress);
    var match = /^(\d+)\/(\d+)$/.exec(raw);
    var total = match ? parseInt(match[2], 10) : 0;
    if (!match || total <= 0) {
      bar.setAttribute("data-phase-complete", "unknown");
      bar.setAttribute("data-phase-total", "unknown");
      bar.appendChild(element("span", "row-phase-seg",
        { "data-phase-segment": "", "data-phase-state": "unknown" }));
      return bar;
    }
    var complete = Math.max(0, Math.min(parseInt(match[1], 10), total));
    bar.setAttribute("data-phase-complete", String(complete));
    bar.setAttribute("data-phase-total", String(total));
    var drawn = Math.min(total, PHASE_SEGMENT_MAX);
    for (var index = 0; index < drawn; index += 1) {
      bar.appendChild(element("span", "row-phase-seg", {
        "data-phase-segment": "",
        "data-phase-state": index < complete ? "done" : "pending",
      }));
    }
    if (total > PHASE_SEGMENT_MAX) {
      var overflow = total - PHASE_SEGMENT_MAX;
      bar.setAttribute("data-phase-overflow", String(overflow));
      bar.appendChild(element("span", "row-phase-overflow", null, "+" + overflow));
    }
    return bar;
  }

  /**
   * One agent-run OBJECT (Move 1, Move 4, Move 6): the 16-field schema split across three
   * declared lines with the agent/session identity band first, a paired ADVISORY/MEASURED
   * evidence/decision footer, and an attached lease headroom bar. Non-field affordances (the
   * prompt glyph, the status rail, the settlement/source chips, the lease bar) are added without
   * touching the gate's 16-field row schema.
   *
   * The density ladder is a presentation difference, never a second information model: on the
   * compact (mobile) view each value carries an explicit semantic mark (`wt:`, `cmd:`, `said:`)
   * so the stranger never reconstructs field meaning from order or colour.
   */
  function renderRunRow(run) {
    var compact = window.innerWidth < 760;
    var dense = window.innerWidth < 1200;
    var lab = function (key, full) { return dense ? (SHORT_ROW_LABELS[key] || full) : full; };
    var mark = function (tag, value) {
      return compact ? tag + ":" + (value === undefined || value === null ? "unknown" : value) : value;
    };

    var session = run["session.identity"] || "unknown";
    var advisory = run["evidence.advisory"];
    var measured = run["evidence.measured"];
    var sourceValue = String(run["source.commit"] || run["evidence.source"] || "unknown")
      .replace(/^commit\s+/, "");
    var eligibility = run["decision.eligibility"];
    // Decision consistency (IA adversary a6): when the inbox says no decision is pending, no row
    // may still advertise a governed approval door. The row derives from the same authoritative
    // decision state, so the resting screen never gives two incompatible answers.
    var decisionState = AppState.glance && AppState.glance.attention
      && AppState.glance.attention.decision ? AppState.glance.attention.decision.state : "none";
    if (String(decisionState) === "none" && GOVERNED[eligibility]) eligibility = "none";
    var live = run["run.live"] || "not-live";
    var lifecycle = run["lifecycle.state"] || "unknown";
    var governed = GOVERNED[eligibility] === true;

    // The two-axis state language, read from the packet and never re-derived:
    //   * lifecycle  — the RunState token (glyph + word + tone) and its settled timestamp;
    //   * attention  — the packet's own `attention.state`, clamped to `active|none`.
    var lifecycleState = lifecycleToken(lifecycle);
    var attentionState = attentionToken(run["attention.state"]);
    var settledState = settledFacets(run);

    // Move 6 — lease facets. A missing value is the literal string "unknown", never a zero.
    var reserved = run["budget.reserved"] || "unknown";
    var settled = run["budget.settled"] || "unknown";
    var cap = run["budget.cap"] || "unknown";
    var settlement = run["budget.settlement"] || "unsettled";
    var costSource = run["cost.provenance"] || "unknown";
    var headroom = typeof run["budget.headroom"] === "number" ? run["budget.headroom"] : null;
    var budgetState = "unknown";
    if (headroom !== null) {
      budgetState = headroom <= 0 ? "over" : (headroom <= 25 ? "warn" : "ok");
    }
    var costPair = (reserved === "unknown" ? "?" : reserved) + "/" + (cap === "unknown" ? "?" : cap);

    var row = element("li", "run-row", {
      "data-run-id": session,
      "data-attention": attentionState,
      "data-live": live,
      // The row-level state language: `data-state` is the colour key, `data-lifecycle` the raw
      // packet enum, and `data-stale` the recorded-age verdict that drives the dimmed row.
      "data-state": lifecycleState.tone,
      "data-lifecycle": lifecycle,
      "data-stale": settledState.stale ? "true" : "false",
      "data-decision": governed ? eligibility : "none",
      role: "button",
      tabindex: "0",
      "aria-label": "Agent session " + session + ", " + lifecycleState.word,
    });

    // ── Line 1 · the session identity band (Move 1) ────────────────────────────────────────
    var lineOne = element("div", "row-line session-band",
      { "data-row-line": "", "data-max-lines": "2", "data-agent": session });
    lineOne.appendChild(element("span", "agent-prompt", { "aria-hidden": "true" }, "\u276F"));
    // The status rail IS the state language: the glyph and the word are both visible, and the
    // CSS supplies the colour from `data-state`. The glyph is decorative (`aria-hidden`) so the
    // accessible reading is the plain word, and the state is legible with no colour at all.
    var status = element("span", "row-status", {
      "data-state": lifecycleState.tone,
      "data-lifecycle": lifecycle,
      title: "session state: " + lifecycleState.word + " (" + lifecycle + ")",
    });
    status.appendChild(element("span", "row-status-glyph", { "aria-hidden": "true" },
      lifecycleState.glyph));
    status.appendChild(element("span", "row-status-word", null, lifecycleState.word));
    lineOne.appendChild(status);
    appendField(lineOne, "session.identity", lab("session.identity", "session"), session, {
      identifier: true, maxLines: 1, title: "agent session",
    });
    appendField(lineOne, "terminal.target", lab("terminal.target", "target"),
      compact ? mark("wt", basename(run["terminal.target"])) : run["terminal.target"], {
        identifier: true, maxLines: 1, title: "terminal target (worktree/host)",
      });
    appendField(lineOne, "command.current", lab("command.current", "command"),
      mark("cmd", run["command.current"]), { maxLines: 1 });
    appendField(lineOne, "model.provider", lab("model.provider", "model"),
      compact ? mark("mdl", basename(run["model.provider"])) : run["model.provider"], {
        identifier: true, maxLines: 1,
      });
    appendField(lineOne, "attempt.number", lab("attempt.number", "attempt"),
      mark("att", run["attempt.number"]), { maxLines: 1 });

    // ── Line 2 · lifecycle state + the lease cost pair (Move 6) ────────────────────────────
    var lineTwo = element("div", "row-line run-state", { "data-row-line": "", "data-max-lines": "2" });
    // `spec/cell` names the experiment cell this session belongs to (IA §2 R2 / §10.2): without
    // it the row is a run without its assignment, and the stranger cannot place it in the grid.
    appendField(lineTwo, "spec.cell", lab("spec.cell", "spec"),
      mark("spec", run["spec.cell"]), { maxLines: 1 });
    appendField(lineTwo, "phase.progress", lab("phase.progress", "phase"),
      mark("ph", run["phase.progress"]), { maxLines: 1 });
    // Build step 5 — the same `n/m` value as a segmented bar. Packet-derived only, non-field.
    lineTwo.appendChild(renderPhaseBar(run["phase.progress"]));
    appendField(lineTwo, "lifecycle.state", lab("lifecycle.state", "lifecycle"),
      mark("life", lifecycle), { maxLines: 1 });
    // The settled marker is a NON-FIELD affordance (the row's 16-field schema is exact — the
    // render gate's G-13), so the lifecycle's last recorded change and its age travel beside the
    // state without widening the required field set. No recorded timestamp is the literal
    // `settled unknown`, never a fabricated `0s`; `data-stale` (above) de-emphasises an aged row.
    lineTwo.appendChild(element("span", "row-settled", {
      "data-settled-at": settledState.iso || "unknown",
      "data-age-seconds": settledState.age === null ? null : String(settledState.age),
      title: settledState.title,
    }, settledState.text));
    // Build step 5 — staleness as a WORD, not only a dimmed row (`data-stale` above). It renders
    // only from the recorded-age verdict, never from an unknown age.
    if (settledState.stale) {
      lineTwo.appendChild(element("span", "row-stale",
        { "data-stale-marker": "true", title: settledState.title }, "stale"));
    }
    appendField(lineTwo, "run.live", lab("run.live", "live"), mark("live", live), { maxLines: 1 });
    appendField(lineTwo, "source.commit", lab("source.commit", "commit"),
      mark("cmt", sourceValue), { identifier: true, maxLines: 1 });
    appendField(lineTwo, "cost.provenance", lab("cost.provenance", "cost"), costPair, {
      maxLines: 1, title: "reserved/cap · " + settlement + " · " + costSource,
    });
    appendField(lineTwo, "attention.state", lab("attention.state", "attention"),
      mark("attn", attentionState), { maxLines: 1 });
    // The settlement state and cost_source are non-field chips, so the money meaning travels on
    // the row without widening the required field schema.
    if (!compact) {
      lineTwo.appendChild(element("span", "budget-chip",
        { "data-budget-settlement": settlement, title: "settlement vs platform meter" }, settlement));
      lineTwo.appendChild(element("span", "budget-chip",
        { "data-budget-source": costSource, title: "cost source class" }, costSource));
    }

    // ── Line 3 · the coupled evidence/decision footer (Move 3, Move 4) ─────────────────────
    var lineThree = element("div", "row-line row-evidence row-decision",
      { "data-row-line": "", "data-max-lines": "2" });
    appendField(lineThree, "evidence.advisory", lab("evidence.advisory", "said"),
      mark("said", advisory), { evidenceClass: "advisory", maxLines: 1 });
    appendField(lineThree, "evidence.measured", lab("evidence.measured", "measured"),
      mark("meas", measured), { evidenceClass: "measured", maxLines: 1 });
    appendField(lineThree, "evidence.source", lab("evidence.source", "source"),
      mark("src", sourceValue), { evidenceClass: "source", maxLines: 1 });
    appendField(lineThree, "decision.eligibility", lab("decision.eligibility", "eligible"),
      mark("elig", eligibility), { maxLines: 1 });
    if (!compact && governed) {
      lineThree.appendChild(element("span", "row-authority",
        { "data-authority": "controller", title: "authority: controller" }, "controller"));
    }
    appendField(lineThree, "decision.receipt", lab("decision.receipt", "receipt"),
      mark("rcpt", run["decision.receipt"]), { maxLines: 1 });

    row.appendChild(lineOne);
    row.appendChild(lineTwo);
    row.appendChild(lineThree);

    // ── The attached lease headroom bar (Move 6) ───────────────────────────────────────────
    var lease = element("span", "row-lease", {
      "data-budget-state": budgetState,
      "data-budget-reserved": reserved,
      "data-budget-settled": settled,
      "data-budget-cap": cap,
      "data-budget-headroom": headroom === null ? "unknown" : headroom + "%",
      "data-budget-settlement": settlement,
      "aria-hidden": "true",
      title: "lease: reserved " + reserved + " / cap " + cap + " · "
        + (headroom === null ? "headroom unknown" : headroom + "% headroom")
        + " · " + settlement + " · " + costSource,
    });
    var fill = element("span", "row-lease-fill", null);
    if (headroom !== null) fill.style.width = Math.max(0, Math.min(100, 100 - headroom)) + "%";
    lease.appendChild(fill);
    row.appendChild(lease);
    return row;
  }

  /** R2 body: the bounded, triage-ranked sample (exactly the viewport's capacity).
   *
   *  Ranking is a presentation of the packet's OWN fields (`lifecycle.state`, `attention.state`),
   *  not a re-derived state: failures and blocked work lead, then the in-flight fleet, then
   *  settled runs. The stable sort preserves the projection's order within a rank. The list stays
   *  keyed by run id and write-on-change, so a re-rank reorders identity-preserving nodes and an
   *  unchanged row keeps its identity and focus. */
  function renderRunList(glance) {
    var host = document.getElementById("run-list");
    var sample = Array.isArray(glance.run_sample) ? glance.run_sample : [];
    // A count chip in the R0 truth strip filters the roster to its lifecycle group. The filter
    // is presentation only — it never changes a count the projection emitted, and it is applied
    // before ranking so the visible rows keep the same triage order within the filtered set.
    var filter = AppState.runFilter && COUNT_FILTERS[AppState.runFilter];
    if (filter) {
      sample = sample.filter(function (run) {
        return filter[String(run["lifecycle.state"] || "")] === 1;
      });
    }
    sample = rankRoster(sample).slice(0, capacities().rows);
    var nodes = sample.map(function (run) {
      var row = renderRunRow(run);
      row.__signature = JSON.stringify(run);
      return row;
    });
    reconcileList(host, nodes, "data-run-id");
  }

  /**
   * Build one attention work item (Move 8): a `li` with a state class and a body that carries
   * the answer anchor (when it is one) plus exactly two declared lines. The helper returns both
   * the `li` (the reconciliation unit) and the body (where lines are appended).
   *
   * STEP 4 — expand in place. An item that has read-only detail carries a REAL native `<button>`
   * toggle (`[data-attention-toggle]`) with `aria-expanded`/`aria-controls`; activating it reveals
   * the item's `[data-attention-detail]` panel IN PLACE. The former `role="button"` on the `li`
   * is GONE: it advertised an interaction no handler implemented (the dead button the synthesis
   * named). Because the control is a real button, Enter/Space activation needs no bespoke keydown
   * handler. The detail renders PACKET VALUES ONLY and carries NO mutation control — consequential
   * acts stay behind the confirm bar in the run detail, never here.
   */
  function attentionItem(config) {
    var item = element("li", "attention-item", {
      "data-attention-class": config.kind,
      "data-item-key": config.key,
    });
    var body = item;
    if (config.answer) {
      body = element("div", null, { "data-answer": config.answer });
      item.appendChild(body);
    }
    if (config.expandable) {
      var detailId = "attention-detail-" + config.key;
      item.classList.add("has-detail");
      var toggle = element("button", "attention-toggle", {
        type: "button",
        "data-attention-toggle": "",
        "aria-expanded": "false",
        "aria-controls": detailId,
        "aria-label": config.toggleLabel || config.ariaLabel || "Show detail",
      });
      // The caret is decorative; the accessible name lives on the button itself.
      toggle.appendChild(element("span", "attention-caret",
        { "aria-hidden": "true" }, "\u25B8"));
      item.appendChild(toggle);
      var panel = element("div", "attention-detail", {
        "data-attention-detail": "",
        id: detailId,
        hidden: true,
      });
      item.__toggle = toggle;
      item.__detail = panel;
      item.appendChild(panel);
    }
    return { item: item, body: body };
  }

  /**
   * Fill one item's read-only detail panel. `rows` are `[label, value]` pairs whose values are
   * taken VERBATIM from the glance packet (a value the packet cannot answer renders its own
   * `unknown`, never a client-derived zero). The note names where the governed act lives, so the
   * expansion can never be mistaken for an action surface.
   */
  function fillAttentionDetail(item, spec) {
    var panel = item && item.__detail;
    if (!panel) return;
    clear(panel);
    if (spec.heading) {
      panel.appendChild(element("p", "attention-detail-heading", null, spec.heading));
    }
    if (spec.rows && spec.rows.length) {
      var list = element("dl", "attention-detail-list", null);
      spec.rows.forEach(function (row) {
        list.appendChild(element("dt", "attention-detail-key", null, row[0]));
        list.appendChild(element("dd", "attention-detail-val", null,
          row[1] === undefined || row[1] === null ? "unknown" : row[1]));
      });
      panel.appendChild(list);
    }
    panel.appendChild(element("p", "attention-detail-note", null,
      spec.note || "Read-only. Governed actions are confirmed in the run detail."));
  }

  /**
   * Toggle one attention item's read-only detail in place. One detail is open at a time (an
   * accordion), and opening the detail adds `has-open-detail` to the list so a cramped viewport
   * may scroll the panel into view; at rest the list is unchanged. This is presentation only —
   * it calls no fetch and fires no mutation.
   */
  function toggleAttention(toggle) {
    var item = toggle.closest(".attention-item");
    if (!item) return;
    var panel = item.querySelector("[data-attention-detail]");
    if (!panel) return;
    var open = toggle.getAttribute("aria-expanded") === "true";
    if (!open) {
      // Close every OTHER open detail first.
      Array.prototype.forEach.call(
        document.querySelectorAll(".attention-item.detail-open"),
        function (other) { if (other !== item) closeAttentionItem(other); }
      );
      item.classList.add("detail-open");
      toggle.setAttribute("aria-expanded", "true");
      panel.hidden = false;
      var list = document.getElementById("attention-list");
      if (list) list.classList.add("has-open-detail");
    } else {
      closeAttentionItem(item);
    }
  }

  /** Collapse one item's detail and keep the list's scroll affordance truthful. */
  function closeAttentionItem(item) {
    var toggle = item.querySelector("[data-attention-toggle]");
    var panel = item.querySelector("[data-attention-detail]");
    item.classList.remove("detail-open");
    if (toggle) toggle.setAttribute("aria-expanded", "false");
    if (panel) panel.hidden = true;
    var list = document.getElementById("attention-list");
    if (list && !list.querySelector(".attention-item.detail-open")) {
      list.classList.remove("has-open-detail");
    }
  }

  /**
   * Append one item line: an optional kind label, the answer fields, and non-field chips. The
   * chips name the owner/authority and the next governed action without widening the answer's
   * required field schema (the gate's exact-set check stays green).
   */
  function attentionLine(body, kindLabel, fields, chips) {
    var line = element("div", "item-line", { "data-item-line": "", "data-max-lines": "1" });
    if (kindLabel) line.appendChild(element("span", "item-kind", null, kindLabel));
    fields.forEach(function (spec) {
      appendField(line, spec[0], spec[1], spec[2], {
        identifier: spec[3] === true,
        maxLines: 1,
      });
    });
    (chips || []).forEach(function (chip) {
      line.appendChild(element("span", chip[0], null, chip[1]));
    });
    body.appendChild(line);
    return line;
  }

  //: Severity × actionability ranking for the work queue (IA §2 R1: "ranked by severity ×
  //: actionability"). Higher wins; ties fall back to the collection order (stable sort).
  var SEVERITY_RANK = { critical: 4, high: 3, medium: 2, low: 1 };
  var STATE_RANK = { active: 3, new: 3, stale: 2, snoozed: 1, resolved: 0 };

  /** The numeric rank of one attention entry (severity dominates, then lifecycle state). */
  function severityRank(entry) {
    var severity = String((entry && entry.severity) || "medium").toLowerCase();
    var state = String((entry && entry.state) || "active").toLowerCase();
    return (SEVERITY_RANK[severity] || 2) * 10 + (STATE_RANK[state] || 0);
  }

  /**
   * One ranked (non-reserved) work item: identity, state, authority, the next governed action and
   * a source/age chip. It carries no `[data-field]` and no `[data-answer]`, so the reserved
   * decision/risk answers keep their exact schemas while a saturated inbox is still visible.
   */
  function renderRankedItem(entry, ageSeconds) {
    var identity = entry.identity || entry.id || "unknown";
    var state = entry.state || "active";
    var action = entry.action || "inspect";
    var authority = entry.authority || "review";
    var severity = String(entry.severity || "medium").toUpperCase();
    var item = attentionItem({
      key: "rank-" + (entry.id || identity),
      kind: "next",
      expandable: true,
      toggleLabel: "Show detail for work item " + identity,
    });
    attentionLine(item.body, severity, [], [["queue-id", identity], ["queue-state", state]]);
    attentionLine(item.body, "ACTION", [], [
      ["queue-action", action], ["queue-authority", authority], ["queue-age", "age " + ageSeconds + "s"],
    ]);
    // The detail repeats the ranked entry's own packet fields VERBATIM (no defaults invented):
    // the compact line abbreviates, the expansion names the value the packet actually carries.
    fillAttentionDetail(item.item, {
      heading: "WORK ITEM (read-only)",
      rows: [
        ["identity", entry.identity || entry.id || "unknown"],
        ["state", entry.state],
        ["severity", entry.severity],
        ["authority", entry.authority],
        ["action", entry.action],
        ["age", ageSeconds + "s"],
      ],
    });
    item.item.__signature = JSON.stringify(entry);
    return item.item;
  }

  /** R1 `ON-G5`/`ON-G3`: a ranked, durable work queue of run-linked items, then ONE continuous
   *  clear state. Keyed and write-on-change: reserved rows keep identity across a live update. */
  function renderAttention(glance) {
    var host = document.getElementById("attention-list");
    var attention = glance.attention || {};
    var decision = attention.decision || { state: "unknown", target: "unknown", kind: "unknown",
      epoch: 0, authority: "unknown", eligibility: "unknown" };
    var risk = attention.risk || { identity: "unknown", state: "unknown", action: "unknown" };
    var next = attention.next || { identity: "none", state: "unknown", action: "none" };
    var nodes = [];
    var decisionState = String(decision.state || "unknown");
    var pending = decisionState === "pending";
    var decisionUnknown = decisionState === "unknown";
    var riskUnknown = String(risk.state || "unknown") === "unknown";
    // Only the packet's own `pending` opens the decision door; `unknown` is NOT pending, and the
    // filler below must not claim an all-clear the client never observed.
    var attentionKnown = !decisionUnknown && !riskUnknown;

    // ── DECISION (ON-G5) — a governed door that EXPANDS, not a fake button ─────────────────
    var decisionItem = attentionItem({
      key: "decision",
      kind: "decision",
      answer: "ON-G5",
      expandable: true,
      toggleLabel: pending
        ? "Show pending controller decision detail: " + decision.kind + " " + decision.target
        : (decisionUnknown ? "Show decision state (could not be read)" : "Show decision detail"),
    });
    // Line 1 leads with the state + the two decision tokens a stranger needs (`approve`
    // eligibility); the identifier target moves to line 2 where it may middle-elide without
    // pushing the consequential tokens out of the 300px gutter.
    attentionLine(decisionItem.body, "DECISION", [
      ["decision.state", "state", decision.state, false],
      ["decision.kind", "kind", decision.kind, false],
      ["decision.eligibility", "eligible", decision.eligibility, false],
    ]);
    // The fields already name the authority (`decision.authority`) and the target; no extra chips
    // are needed in the gutter, where they would only crowd the work item.
    attentionLine(decisionItem.body, pending ? "waiting on" : (decisionUnknown ? "unread" : "none pending"), [
      ["decision.epoch", "epoch", decision.epoch, false],
      ["decision.authority", "authority", decision.authority, false],
      ["decision.target", "target", decision.target, true],
    ]);
    // Read-only detail: the SAME packet fields shown un-elided, plus the packet's own provenance.
    fillAttentionDetail(decisionItem.item, {
      heading: "DECISION (read-only)",
      rows: [
        ["state", decision.state],
        ["kind", decision.kind],
        ["target", decision.target],
        ["control epoch", decision.epoch],
        ["authority", decision.authority],
        ["eligibility", decision.eligibility],
        ["observed", (glance.observed_at || "unknown")],
      ],
      note: "Read-only. Approve/promote/cancel is confirmed behind the confirm bar in the run detail.",
    });
    decisionItem.item.__signature = JSON.stringify(decision);
    nodes.push(decisionItem.item);

    // ── RISK (ON-G3) — the reserved highest-severity run problem ───────────────────────────
    var riskItem = attentionItem({
      key: "risk",
      kind: "risk",
      answer: "ON-G3",
      expandable: true,
      toggleLabel: riskUnknown
        ? "Show run risk detail (could not be read)"
        : "Show run risk detail: " + risk.identity,
    });
    attentionLine(riskItem.body, "RISK", [
      ["risk.identity", "target", risk.identity, true],
      ["risk.state", "state", risk.state, false],
    ]);
    attentionLine(riskItem.body, "OWNER", [["risk.action", "action", risk.action, false]]);
    fillAttentionDetail(riskItem.item, {
      heading: "RUN RISK (read-only)",
      rows: [
        ["target", risk.identity],
        ["state", risk.state],
        ["next action", risk.action],
        ["observed", (glance.observed_at || "unknown")],
      ],
      note: "Read-only. Inspecting or recovering the run happens in the run detail.",
    });
    riskItem.item.__signature = JSON.stringify(risk);
    nodes.push(riskItem.item);

    // ── NEAR CAP — the reserved budget-constraint work item (R1, v2 synthesis §4.2) ────────
    // A budget near its hard cap is attention the operator must see in the inbox, not only in the
    // R3 ledger. It exists ONLY when the packet's own cost block says so (`money_risk`), and every
    // value it shows is that block's verbatim value — the client never re-derives a threshold.
    var cost = glance.cost || {};
    if (cost.money_risk) {
      var nearCapQuota = cost.quota === undefined || cost.quota === null ? "unknown" : cost.quota;
      var nearCapItem = attentionItem({
        key: "near-cap",
        kind: "near-cap",
        expandable: true,
        toggleLabel: "Show near-cap budget detail",
      });
      // Two short lines: the quota that tripped the marker, then the spend it applies to.
      attentionLine(nearCapItem.body, "NEAR CAP",
        [["money.quota", "quota", nearCapQuota, false]]);
      attentionLine(nearCapItem.body, "SPEND",
        [["money.spend", "spend", cost.spend, false]]);
      var spendTruth = (glance.truth && glance.truth.spend) || {};
      fillAttentionDetail(nearCapItem.item, {
        heading: "BUDGET CONSTRAINT (read-only)",
        rows: [
          ["spend", cost.spend],
          ["burn", cost.burn],
          ["quota", nearCapQuota],
          ["wallet", cost.wallet],
          ["reserved leases", cost.leases],
          ["source", spendTruth.source],
          ["age", typeof spendTruth.age_seconds === "number"
            ? ageLabel(spendTruth.age_seconds) : undefined],
        ],
        note: "Read-only. Raising the cap or retiring work is confirmed behind the confirm bar.",
      });
      nearCapItem.item.__signature = "near-cap:" + JSON.stringify(cost);
      nodes.push(nearCapItem.item);
    }

    // ── R1c · the globally-ranked remainder (Move 8, IA §2 R1c) ───────────────────────────
    // Decision, risk and (when present) near-cap hold the reserved slots above; the remaining
    // capacity is filled by the ACTUAL ranked collection (`attention.next` plus `attention.items`),
    // so a saturated inbox cannot bury a new critical item and never degenerates into repeated
    // empty cards. With few candidates the surplus collapses into ONE continuous `QUEUE CLEAR`.
    var cap = capacities().attention;
    var fillSlots = Math.max(0, cap - nodes.length);
    var ageSeconds = (glance.trust && glance.trust.worst_age) || 0;
    var candidates = [];
    if (next && next.identity && next.identity !== "none") candidates.push(next);
    if (Array.isArray(attention.items)) {
      attention.items.forEach(function (entry) { candidates.push(entry); });
    }
    candidates.sort(function (a, b) { return severityRank(b) - severityRank(a); });
    var ranked = candidates.slice(0, fillSlots);
    ranked.forEach(function (entry) { nodes.push(renderRankedItem(entry, ageSeconds)); });

    for (var i = ranked.length; i < fillSlots; i += 1) {
      var empty = attentionItem({
        key: "empty-" + i,
        kind: "empty",
        ariaLabel: i === ranked.length ? "Queue clear, no further attention" : null,
      });
      var lineA = element("div", "item-line", { "data-item-line": "", "data-max-lines": "1" });
      var lineB = element("div", "item-line", { "data-item-line": "", "data-max-lines": "1" });
      if (i === ranked.length) {
        // "QUEUE CLEAR" is a claim: it renders only when the decision and risk blocks were
        // actually read. An unknown attention state says so instead.
        lineA.appendChild(element("span", "item-kind", null,
          attentionKnown ? "QUEUE CLEAR" : "ATTENTION UNKNOWN"));
        lineA.appendChild(element("span", "queue-empty-note", null,
          attentionKnown ? "no further attention" : "decision or risk state could not be read"));
        lineB.appendChild(element("span", "queue-empty-note", null,
          attentionKnown ? "decision queue drained · 0 waiting" : "no all-clear without the records"));
      }
      empty.body.appendChild(lineA);
      empty.body.appendChild(lineB);
      empty.item.__signature = "empty";
      nodes.push(empty.item);
    }
    reconcileList(host, nodes, "data-item-key");
  }

  /** R3a `ON-G4`: the five constraint values as a labelled LEDGER, never money cards.
   *
   * Synthesis v2 §5.5 corrects v1's "call-centre KPI" treatment: R3a is a bounded constraint
   * ledger attached to the roster, so each value earns a labelled ROW rather than a
   * free-floating tile. Every value is taken verbatim from the packet's `cost` block; an absent
   * value renders the literal `unknown`, never `$0.00`. Per-row provenance (the packet's own
   * source + age) rides on `data-source`/`data-age-seconds` at every viewport — machine-readable
   * and shown as a compact age chip where the width allows — while `#cost-prov` carries the full,
   * visible source + age the render gate reads.
   */
  function renderCost(glance) {
    var host = document.getElementById("cost-grid");
    clear(host);
    var cost = glance.cost || {};
    var spend = (glance.truth && glance.truth.spend) || {};
    // The five values share one subscription snapshot, so they share one source + age. The truth
    // strip's spend observation is the projection's own provenance carrier for that snapshot, so
    // it leads; a `cost.source` the projection names explicitly is the fallback, then `unknown`.
    var source = spend.source || cost.source || "unknown";
    var age = typeof cost.age_seconds === "number" ? cost.age_seconds
      : (typeof spend.age_seconds === "number" ? spend.age_seconds : null);
    var ageText = ageLabel(age);
    var rows = [
      ["money.spend", "spend", cost.spend],
      ["money.burn", "burn", cost.burn],
      ["money.quota", "quota", cost.quota],
      ["money.wallet", "wallet", cost.wallet],
      ["money.leases", "leases", cost.leases],
    ];
    rows.forEach(function (row) {
      var value = row[2] === undefined || row[2] === null ? "unknown" : row[2];
      var field = appendField(host, row[0], row[1], value, { maxLines: 1 });
      field.classList.add("cost-row");
      // Per-value provenance: the packet's source + age travel WITH the row (F13).
      field.setAttribute("data-source", source);
      field.setAttribute("data-age-seconds", age === null ? "unknown" : String(age));
      field.setAttribute("title", row[1] + " · source " + source + " · age " + ageText);
      field.appendChild(element("span", "cost-prov-row", { "aria-hidden": "true" }, ageText));
    });
    // The block provenance line: the full source + age, visible at rest (the gate reads it).
    var prov = document.getElementById("cost-prov");
    if (prov) prov.textContent = "source " + source + " · age " + ageText;
    // The bounded cap exception, anchored to the heading line so it never adds a ledger row.
    if (cost.money_risk) {
      var marker = element("span", "money-risk", { "data-money-risk": "" });
      marker.appendChild(element("span", null, null, "⚠ near cap"));
      host.appendChild(marker);
    }
    // The hard-budget headroom bar for the ledger. `quota` is the cap fraction; a non-numeric
    // quota draws an explicit unknown track, never a full one.
    var quotaPct = parseInt(String(cost.quota === undefined ? "" : cost.quota).replace("%", ""), 10);
    var costState = isNaN(quotaPct) ? "unknown" : (quotaPct >= 100 ? "over" : (quotaPct >= 90 ? "warn" : "ok"));
    var budgetBar = element("span", "cost-budget", {
      "data-budget-state": costState,
      "data-cap-used": isNaN(quotaPct) ? "unknown" : quotaPct + "%",
      "aria-hidden": "true",
      title: isNaN(quotaPct) ? "budget headroom unknown" : "hard budget " + quotaPct + "% used",
    });
    var budgetFill = element("span", "cost-budget-fill", null);
    if (!isNaN(quotaPct)) budgetFill.style.width = Math.max(0, Math.min(100, quotaPct)) + "%";
    budgetBar.appendChild(budgetFill);
    host.appendChild(budgetBar);
  }

  /** R3b: the packet's MEASURED health statuses — never a client-derived composite score.
   *
   * Synthesis v2 §5.4 retires v1's "one computed health score": it had no measured source in
   * the packet. R3b mirrors the packet's own health fields instead — the worker heartbeat
   * verdict and the projection watermark verdict, each carrying its MEASURED state plus the
   * worst age (and, for projections, the projector lag) as `data-*` evidence. This renderer
   * computes no aggregate at all, so the room cannot manufacture a reassuring score the packet
   * never measured (a3 D-6/D-7).
   */
  function renderHealth(glance) {
    var host = document.getElementById("health-lines");
    clear(host);
    var health = glance.health_detail || {};
    var system = glance.system || {};
    var trust = glance.trust || {};
    var lag = (glance.truth && glance.truth.projection_lag) || {};
    var rows = [
      { key: "workers", label: "workers", detail: health.workers,
        state: (system.workers || {}).state, age: (system.workers || {}).age_seconds },
      { key: "projections", label: "projections", detail: health.projections,
        state: trust.projection_state, age: trust.worst_age, lag: lag.lag },
    ];
    rows.forEach(function (row) {
      var line = element("div", "detail-line", {
        "data-detail-line": "",
        "data-max-lines": "1",
        // The measured evidence the line carries: which dimension, its packet state and worst
        // age (and the projector lag where the packet has one). All packet values, verbatim.
        "data-measure": row.key,
        "data-state": row.state === undefined || row.state === null ? "unknown" : String(row.state),
        "data-age-seconds": typeof row.age === "number" ? String(row.age) : "unknown",
      });
      if (row.lag !== undefined) {
        line.setAttribute("data-lag", typeof row.lag === "number" ? String(row.lag) : "unknown");
      }
      line.appendChild(element("span", null, { "data-label": "" }, row.label));
      appendRawValue(line, row.detail === undefined || row.detail === null ? "unknown" : row.detail, null);
      host.appendChild(line);
    });
  }

  /** Parse the count a composition bucket states (`sol 5` / `0` / `unknown`), or null. */
  function bucketCount(text) {
    var match = /(\d+)\s*$/.exec(String(text === undefined || text === null ? "" : text));
    return match ? parseInt(match[1], 10) : null;
  }

  /**
   * The proportional stacked bar for one marginal's top/other/unknown split.
   *
   * `counts` is the parsed bucket counts (or null). The bar is a NON-FIELD affordance: it
   * derives its proportions ONLY from the packet's own counts and, when any bucket is
   * unparseable or the total is zero, renders ONE explicit `unknown` segment instead of a
   * fabricated full bar.
   */
  function compositionBar(counts) {
    var bar = element("span", "marginal-bar",
      { "data-composition-bar": "", "aria-hidden": "true" });
    var names = ["top", "other", "unknown"];
    var total = 0;
    var complete = true;
    names.forEach(function (name) {
      if (counts[name] === null || counts[name] === undefined) complete = false;
      else total += counts[name];
    });
    if (!complete || total <= 0) {
      bar.setAttribute("data-bar-state", "unknown");
      bar.setAttribute("title", "composition split unknown");
      bar.appendChild(element("span", "marginal-seg",
        { "data-seg": "unknown", "data-bar-state": "unknown" }));
      return bar;
    }
    bar.setAttribute("data-bar-state", "measured");
    bar.setAttribute("title",
      "top " + counts.top + " · other " + counts.other + " · unknown " + counts.unknown);
    names.forEach(function (name) {
      var segment = element("span", "marginal-seg", { "data-seg": name });
      segment.style.width = ((counts[name] / total) * 100).toFixed(2) + "%";
      bar.appendChild(segment);
    });
    return bar;
  }

  /** R3c `ON-G7`: the composition marginals as bounded TOKEN-SPLIT BARS, stated in words.
   *
   * Each marginal (`model`/`condition`/`provider`/`lifecycle`) keeps its three explicit, legible
   * bucket words (never `t`/`o`/`u`) AND adds a proportional stacked bar so the split reads as
   * shape. The bar is derived from the packet's own counts (see `compositionBar`); a malformed
   * or absent split degrades to one explicit unknown segment, never a guessed proportion.
   */
  function renderComposition(glance) {
    var host = document.getElementById("composition");
    clear(host);
    var composition = glance.composition || {};
    // Compact visible names fit the 64px label track; `data-marginal` keeps the full name.
    var shortNames = { model: "model", condition: "cond", provider: "prov", lifecycle: "life" };
    ["model", "condition", "provider", "lifecycle"].forEach(function (name) {
      var marginal = element("div", "marginal", {
        "data-marginal": name,
        "data-max-lines": "1",
      });
      marginal.appendChild(element("span", "marginal-name", { title: name },
        shortNames[name] || name));
      var buckets = element("div", "marginal-buckets", null);
      var data = composition[name] || { top: "unknown 0", other: "0", unknown: "0" };
      var counts = {};
      ["top", "other", "unknown"].forEach(function (bucketName) {
        var bucket = element("span", "marginal-bucket", { "data-bucket": bucketName });
        // Explicit bucket words (top/other/unknown), never t/o/u shorthand a stranger must decode.
        bucket.appendChild(element("span", "bucket-label", null, bucketName));
        var bucketText = String(data[bucketName] === undefined ? "unknown" : data[bucketName]);
        counts[bucketName] = bucketCount(bucketText);
        if (bucketName === "top") {
          // `data-category` names the modal bucket (the gate requires it on `top`).
          var category = bucketText.split(" ")[0] || "unknown";
          bucket.setAttribute("data-category", category);
        }
        appendRawValue(bucket, bucketText, "bucket-value");
        buckets.appendChild(bucket);
      });
      marginal.appendChild(buckets);
      marginal.appendChild(compositionBar(counts));
      host.appendChild(marginal);
    });
  }

  // ── Top-level render ───────────────────────────────────────────────────────────────────

  //: The browser-session retained window for the trends lens. A bounded ring, so a long-lived
  //: tab cannot grow without limit; the lens labels it rather than implying a server history.
  var HISTORY_MAX = 60;

  var AppState = {
    glance: null,
    replayComplete: false,
    rendered: false,
    announcedEpoch: null,
    //: Bounded samples of the glance slices the charts consume (one per control epoch).
    history: [],
    lastHistoryEpoch: null,
    //: True when the projection could not be read, so the charts render an error, not a stale.
    glanceError: false,
    //: The SSE stream's own health: false until a frame/projection arrives, and the wall time
    //: of the last observation (the age loop above stops trusting old health past its window).
    streamConnected: false,
    lastFrameAt: null,
    //: The SSE stream's presentation state + observed age, mirrored from the shell attribute so
    //: the R0 truth strip's stream cell can render them without a full glance re-render.
    streamState: "connecting",
    streamAgeSeconds: null,
    //: The active R0 count filter over the run roster (a `COUNT_FILTERS` key), or null for all.
    runFilter: null,
    //: When the age loop last re-read the projection while the stream was stale (throttle).
    lastStaleFetchAt: null,
    //: The last rendered payload's signature. A no-op poll (same signature) performs ZERO
    //: writes, which is the direction §12.2 #3 contract for keyed write-on-change lists.
    lastSignature: null,
    //: Move 7 — ONE selected attempt feed, bounded and aged, with explicit follow/pause. New
    //: events append only while following; a paused feed buffers up to FEED_MAX and drains on
    //: resume, so the operator controls when urgent updates demand attention.
    feedPaused: false,
    feedEntries: [],
    feedRunId: null,
    feedBuffer: [],
  };

  /**
   * The DOM-relevant signature of a glance payload.
   *
   * Covers every block that feeds the rendered regions. Two payloads with the same signature
   * would produce byte-identical DOM, so the second render is skipped entirely rather than
   * rebuilding identical nodes (which would also fire state-change motion on a quiet poll).
   */
  function glanceSignature(glance) {
    return JSON.stringify([
      glance.control_epoch,
      glance.system,
      glance.trust,
      glance.truth,
      glance.attention,
      glance.run_counts,
      glance.run_sample,
      glance.cost,
      glance.health_detail,
      glance.composition,
    ]);
  }

  /**
   * Append one bounded history sample for the trends lens.
   *
   * Only a NEW control epoch pushes: a repeated render of the same epoch (a poll, a re-render)
   * would otherwise duplicate the point and make the x-axis lie about time. A missing cost or
   * count stays as it was on the wire (a string "unknown") so the chart can render a gap.
   */
  function pushHistory(glance) {
    var epoch = Number(glance.control_epoch || 0);
    if (AppState.lastHistoryEpoch === epoch && AppState.history.length) return;
    AppState.lastHistoryEpoch = epoch;
    AppState.history.push({
      epoch: epoch,
      observed_at: glance.observed_at || "",
      cost: glance.cost || null,
      run_counts: glance.run_counts || null,
      system: glance.system || null,
      trust: glance.trust || null,
    });
    while (AppState.history.length > HISTORY_MAX) AppState.history.shift();
  }

  /** Render every region from one glance payload. */
  function renderGlance(glance) {
    if (!glance || typeof glance !== "object") return;
    AppState.glance = glance;
    // Zero-write no-op: an identical payload leaves the live DOM untouched. This is the
    // strongest form of the write-on-change contract and it makes a quiet poll silent.
    var signature = glanceSignature(glance);
    if (signature === AppState.lastSignature) {
      AppState.rendered = true;
      maybeReady();
      return;
    }
    AppState.lastSignature = signature;
    var root = document.querySelector("[data-glance-shell]");
    if (root) root.setAttribute("data-control-epoch", String(glance.control_epoch || 0));

    renderSystem(glance);
    renderTrust(glance);
    renderTruthStrip(glance);
    renderRunCounts(glance);
    renderRunList(glance);
    renderAttention(glance);
    renderCost(glance);
    renderHealth(glance);
    renderComposition(glance);
    pushHistory(glance);
    // The trends lens is a drill-down; it re-renders only while open, but always receives the
    // fresh history so opening it later shows the retained window rather than a stale chart.
    if (window.ControlRoomCharts) {
      window.ControlRoomCharts.update(AppState.glance, AppState.history, AppState.glanceError);
    }
    AppState.rendered = true;
    maybeReady();
  }

  /** Announce in the single polite live region (transitions only; a no-op poll is silent). */
  function announce(message) {
    var region = document.getElementById("announcer");
    if (!region) return;
    region.textContent = "";
    // A forced microtask break so assistive tech sees a *change*, not a repeated same string.
    window.setTimeout(function () { region.textContent = message; }, 0);
  }

  /** Apply a streamed transition frame (one keyed update + one polite announcement). */
  function applyTransition(frame) {
    if (!frame || !AppState.glance) return;
    var epoch = Number(frame.control_epoch || 0);
    if (frame.glance && typeof frame.glance === "object") {
      AppState.glanceError = false;
      renderGlance(frame.glance);
    } else if (frame.kind && frame.target) {
      var sample = AppState.glance.run_sample || [];
      sample.forEach(function (run) {
        if (run["session.identity"] === frame.target && frame.kind === "run.failed") {
          run["lifecycle.state"] = "failed";
          run["run.live"] = "not-live";
          run["attention.state"] = "active";
        }
      });
      // E-5 (IA §10.5): a NEW critical failure must stay visible, so it claims the reserved
      // risk slot in R1 rather than competing for a ranked remainder slot.
      if (frame.kind === "run.failed") {
        AppState.glance.attention = AppState.glance.attention || {};
        AppState.glance.attention.risk = {
          identity: frame.target, state: "active", action: "inspect",
        };
      }
      renderRunList(AppState.glance);
      renderAttention(AppState.glance);
      // Move 7 — a transition for the SELECTED run appends one live feed entry. A paused feed
      // buffers it (bounded) instead, so pause genuinely stops the stream demanding attention.
      if (frame.target === AppState.feedRunId) {
        appendFeed({ ts: new Date().toISOString(), age: 0, cls: "lifecycle", text: frame.kind });
      }
    }
    if (frame.kind === "health") {
      // A same-epoch health verdict change: announce it even though the epoch did not move.
      announce("Health update");
    } else if (epoch && epoch !== AppState.announcedEpoch) {
      AppState.announcedEpoch = epoch;
      announce(frame.kind ? "Run update: " + frame.kind : "Control epoch " + epoch);
    }
    var root = document.querySelector("[data-glance-shell]");
    if (root) root.setAttribute("data-control-epoch", String(epoch));
  }

  // ── Readiness (the render gate's `[data-render-state="ready"]` contract) ────────────────

  var readyEmitted = false;

  function maybeReady() {
    if (readyEmitted || !AppState.rendered || !AppState.replayComplete) return;
    readyEmitted = true;
    var finish = function () {
      // Two animation frames guarantee layout and paint have settled before the screenshot.
      window.requestAnimationFrame(function () {
        window.requestAnimationFrame(function () {
          var root = document.querySelector("[data-glance-shell]");
          if (root) root.setAttribute("data-render-state", "ready");
        });
      });
    };
    if (document.fonts && document.fonts.ready) {
      document.fonts.ready.then(finish).catch(finish);
    } else {
      finish();
    }
  }

  // ── Data sources ───────────────────────────────────────────────────────────────────────

  /**
   * The explicit "projection unreadable" payload. Every value the failed request could not
   * answer is `unknown`; nothing is asserted all-clear, zero or none. The shell still renders
   * (regions and fields must exist), but no region claims a fact the client never observed.
   */
  function unavailableGlance() {
    return {
      control_epoch: 0,
      source: "unavailable",
      observed_at: "",
      unavailable: true,
      system: {
        browser: { state: "up", age_seconds: 0 },
        control: { state: "unknown", age_seconds: 0 },
        workers: { state: "unknown", age_seconds: 0 },
        projections: { state: "unknown", age_seconds: 0 },
      },
      trust: { epoch: 0, worst_age: 0, projection_state: "unknown", degraded_count: 0,
        stale_count: 0, partial_count: 0, unknown_count: 3 },
      // The truth strip's own explicit-unknown fallback: every count is null (never 0), the
      // spend/lag sources are unavailable, and the client appends its own stream state.
      truth: {
        counts: { running: null, blocked: null, done_unseen: null },
        counts_source: "unavailable",
        counts_age_seconds: null,
        spend: { value: "unknown", cap: "unknown", source: "unavailable", age_seconds: null },
        projection_lag: { value: "unknown", lag: null, state: "unknown",
          source: "unavailable", age_seconds: null },
      },
      attention: {
        decision: { state: "unknown", target: "unknown", kind: "unknown", epoch: 0,
          authority: "unknown", eligibility: "unknown" },
        risk: { identity: "unknown", state: "unknown", action: "unknown" },
        next: { identity: "none", state: "unknown", action: "none" },
        items: [],
      },
      run_counts: { running: null, queued: null, failed: null, live: null },
      run_sample: [],
      cost: { spend: "unknown", burn: "unknown", quota: "unknown", wallet: "unknown",
        leases: "unknown", money_risk: false },
      health_detail: { workers: "unknown", projections: "unavailable" },
      composition: {
        model: { top: "unknown", other: "unknown", unknown: "unknown" },
        condition: { top: "unknown", other: "unknown", unknown: "unknown" },
        provider: { top: "unknown", other: "unknown", unknown: "unknown" },
        lifecycle: { top: "unknown", other: "unknown", unknown: "unknown" },
      },
    };
  }

  /** Fetch the one-shot projection. A failure renders explicit unknowns, never a lie. */
  function loadGlance() {
    fetch("/api/glance", { headers: { Accept: "application/json" } })
      .then(function (response) {
        if (!response.ok) throw new Error("glance " + response.status);
        return response.json();
      })
      .then(function (glance) {
        AppState.glanceError = false;
        // A successful projection fetch is a fresh observation of health even when the SSE
        // stream itself is down; restart the age window without claiming the stream is open.
        AppState.lastFrameAt = Date.now();
        renderGlance(glance);
      })
      .catch(function () {
        // A failed projection is a first-class state: every value the room could not read is
        // rendered `unknown` (never a fabricated zero / none / all-clear), and the charts
        // render their explicit error state.
        AppState.glanceError = true;
        renderGlance(unavailableGlance());
        AppState.replayComplete = true;
        maybeReady();
      });
  }

  //: The shell's stream-health attributes the live screen exposes for operators and tests.
  var STREAM_STALE_SECONDS = 30;

  /** Mark the stream observed-now: a received frame or a successful projection fetch. */
  function touchStream(frameAt) {
    AppState.lastFrameAt = frameAt || Date.now();
    AppState.streamConnected = true;
    setStreamState("open");
  }

  /** Set `[data-stream-state]` on the glance shell (connecting/open/disconnected/stale). */
  function setStreamState(state) {
    AppState.streamState = state;
    var root = document.querySelector("[data-glance-shell]");
    if (root) root.setAttribute("data-stream-state", state);
    // The truth strip shows the same observation to the operator; refresh just that cell.
    renderStreamCell();
  }

  /**
   * Age handling: expose how old the displayed observation is (`data-stream-age-seconds`) and,
   * past `STREAM_STALE_SECONDS` with no frame, stop trusting it as current — re-read the
   * one-shot projection once instead of leaving old health on screen indefinitely.
   */
  function pollStreamAge() {
    var root = document.querySelector("[data-glance-shell]");
    if (!root) return;
    var age = AppState.lastFrameAt
      ? Math.max(0, Math.floor((Date.now() - AppState.lastFrameAt) / 1000))
      : null;
    AppState.streamAgeSeconds = age;
    root.setAttribute("data-stream-age-seconds", age === null ? "unknown" : String(age));
    renderStreamCell();
    if (age === null || age <= STREAM_STALE_SECONDS) return;
    if (AppState.streamConnected) {
      AppState.streamConnected = false;
      setStreamState("stale");
      announce("Health display is " + age + "s old; re-reading the projection");
    }
    // While the stream is down, re-read the projection once per stale window so the resting
    // screen never freezes on a stale health verdict.
    var now = Date.now();
    if (!AppState.lastStaleFetchAt || now - AppState.lastStaleFetchAt > STREAM_STALE_SECONDS * 1000) {
      AppState.lastStaleFetchAt = now;
      loadGlance();
    }
  }

  /** Follow the bounded SSE stream; it is the only open event stream on the screen. */
  function connectEvents() {
    if (typeof window.EventSource !== "function") {
      AppState.replayComplete = true;
      setStreamState("unavailable");
      maybeReady();
      return;
    }
    setStreamState("connecting");
    var source = new window.EventSource("/api/events");
    source.onopen = function () { touchStream(Date.now()); };
    source.onerror = function () {
      // The browser's EventSource reconnects on its own; until it does, the screen names the
      // disconnection and the age loop above keeps the last observation from reading as current.
      AppState.streamConnected = false;
      setStreamState("disconnected");
      announce("Event stream disconnected");
    };
    source.addEventListener("snapshot", function (event) {
      try {
        var frame = JSON.parse(event.data);
        if (frame && frame.glance) {
          AppState.glanceError = false;
          touchStream(Date.now());
          renderGlance(frame.glance);
        }
      } catch (_error) { /* a malformed frame is ignored; the polled snapshot stands */ }
    });
    source.addEventListener("replay_complete", function () {
      touchStream(Date.now());
      AppState.replayComplete = true;
      maybeReady();
    });
    source.addEventListener("transition", function (event) {
      try {
        touchStream(Date.now());
        applyTransition(JSON.parse(event.data));
      } catch (_error) { /* ignore malformed transition */ }
    });
    // A stream that never reaches replay_complete must not wedge the screen at "loading".
    window.setTimeout(function () {
      if (!AppState.replayComplete) {
        AppState.replayComplete = true;
        maybeReady();
      }
    }, 2000);
    window.setInterval(pollStreamAge, 5000);
  }

  // ── Selection dock (R4 drill-down) ──────────────────────────────────────────────────────

  var dockOrigin = null;

  //: Move 7 — the feed is bounded: at most this many entries are kept, oldest dropped first.
  var FEED_MAX = 8;

  /** The stable, copyable typed address of a run object (Move 5). */
  function typedAddress(run) {
    return "run/" + (run["session.identity"] || "unknown")
      + "  phase/" + (run["phase.progress"] || "?")
      + "  attempt/" + (run["attempt.number"] || "?")
      + "  session/" + (run["session.identity"] || "unknown")
      + "  worktree/" + (run["terminal.target"] || "unknown")
      + "  lease/" + (run["budget.lease"] || run["cost.provenance"] || "unknown");
  }

  /**
   * The RECORDED events for a run, in causal order, typed by evidence class (Move 4/7).
   *
   * Each entry is a control record the server composed (`run.events`: attempts, gate verdicts,
   * approvals, command receipts) with its real identifier and timestamp. No recorded history is
   * an explicit single row saying so — never a fabricated sequence with invented ages.
   */
  function feedSeed(run) {
    var recorded = Array.isArray(run["run.events"]) ? run["run.events"] : [];
    if (!recorded.length) {
      return [{ ts: null, age: null, cls: "lifecycle", text: "no recorded events for this run" }];
    }
    return recorded.slice(-FEED_MAX).map(function (event) {
      return {
        id: event.id || "",
        ts: event.ts || null,
        age: null,
        cls: event["class"] || event.cls || "lifecycle",
        text: event.text || "unknown event",
      };
    });
  }

  /** Parse a recorded timestamp into epoch milliseconds, or null when none was recorded. */
  function timestampMs(value) {
    if (value === undefined || value === null || value === "") return null;
    var ms = Date.parse(String(value));
    return isNaN(ms) ? null : ms;
  }

  /** The age of a recorded event in seconds, or null when no timestamp was recorded. */
  function feedAge(entry) {
    var ms = timestampMs(entry.ts);
    if (ms !== null) return Math.max(0, Math.floor((Date.now() - ms) / 1000));
    return typeof entry.age === "number" ? entry.age : null;
  }

  /** The recorded time of an event (UTC clock), never a fabricated age. */
  function feedTime(entry, age) {
    var ms = timestampMs(entry.ts);
    if (ms !== null) return new Date(ms).toISOString().slice(11, 19);
    if (age !== null) return "t+" + age + "s";
    return "—";
  }

  /** One bounded feed row: recorded time, evidence class, text — same material as the row. */
  function feedRow(entry) {
    var age = feedAge(entry);
    var attrs = { "data-evidence-class": entry.cls };
    if (age !== null) attrs["data-age-seconds"] = String(age);
    var li = element("li", "feed-entry", attrs);
    li.appendChild(element("span", "feed-time", null, feedTime(entry, age)));
    li.appendChild(element("span", "feed-class", null, String(entry.cls).toUpperCase()));
    li.appendChild(element("span", "feed-text", null, entry.text));
    return li;
  }

  /** Keep the feed list bounded by dropping the oldest entries. */
  function trimFeed(list) {
    while (list.children.length > FEED_MAX) list.removeChild(list.firstChild);
  }

  /** Append one live entry while following; buffer it while paused (bounded drain on resume). */
  function appendFeed(entry) {
    if (!AppState.feedRunId) return;
    if (AppState.feedPaused) {
      AppState.feedBuffer.push(entry);
      while (AppState.feedBuffer.length > FEED_MAX) AppState.feedBuffer.shift();
      return;
    }
    var list = document.querySelector("[data-feed-list]");
    if (!list) return;
    list.appendChild(feedRow(entry));
    AppState.feedEntries.push(entry);
    trimFeed(list);
  }

  /**
   * Build the ONE bounded attempt feed (Move 7): a follow/pause control, explicit age, and the
   * same ADVISORY/MEASURED/SOURCE classes as the row. The data-feed-follow attribute and the
   * pause style make the state visible to the screenshot adversary and the browser assertions.
   */
  function renderAttemptFeed(run) {
    var wrap = element("section", "attempt-feed",
      { "data-attempt-feed": "", "data-feed-follow": "follow" });
    var head = element("div", "feed-head", null);
    head.appendChild(element("span", "feed-title", null, "ATTEMPT FEED"));
    head.appendChild(element("span", "feed-age", { "data-feed-age": "" },
      "recorded events · bounded " + FEED_MAX));
    var toggle = element("button", "feed-toggle",
      { type: "button", "data-feed-toggle": "", "aria-pressed": "false" }, "Pause");
    head.appendChild(toggle);
    wrap.appendChild(head);

    var list = element("ol", "feed-list", { "data-feed-list": "" });
    wrap.appendChild(list);
    AppState.feedEntries = feedSeed(run);
    AppState.feedRunId = run["session.identity"] || "unknown";
    AppState.feedPaused = false;
    AppState.feedBuffer = [];
    AppState.feedEntries.forEach(function (entry) { list.appendChild(feedRow(entry)); });

    toggle.addEventListener("click", function () {
      AppState.feedPaused = !AppState.feedPaused;
      wrap.setAttribute("data-feed-follow", AppState.feedPaused ? "pause" : "follow");
      wrap.classList.toggle("feed-paused", AppState.feedPaused);
      toggle.textContent = AppState.feedPaused ? "Follow" : "Pause";
      toggle.setAttribute("aria-pressed", AppState.feedPaused ? "true" : "false");
      if (!AppState.feedPaused) {
        AppState.feedBuffer.forEach(function (entry) {
          list.appendChild(feedRow(entry));
          AppState.feedEntries.push(entry);
        });
        AppState.feedBuffer = [];
        trimFeed(list);
      }
    });
    return wrap;
  }

  function openDock(run, origin) {
    var dock = document.getElementById("selection-dock");
    var ladder = document.getElementById("evidence-ladder");
    var title = document.getElementById("dock-title");
    var address = document.getElementById("dock-address");
    if (!dock || !ladder) return;
    clear(ladder);
    if (title) title.textContent = "RUN " + (run["session.identity"] || "unknown");
    if (address) address.textContent = typedAddress(run);
    // The inspector is an attempt-scoped CAUSAL LADDER plus a live, scoped dependency flow
    // (brief §10 / Move 2). visuals.js owns the SVG; the text equivalents it renders alongside
    // keep the dock accessible, printable and readable with no graphics at all. The bounded
    // follow/pause attempt feed (Move 7) is app-owned and appended beneath the spine.
    if (window.ControlRoomVisuals) {
      window.ControlRoomVisuals.render(ladder, run, AppState.glance);
    }
    ladder.appendChild(renderAttemptFeed(run));
    dock.hidden = false;
    // The parity layer re-houses the surfaces the facelift dropped into the reconciled R4
    // sub-regions (R4a address, R4b event stream + actions, R4d step timings) and the workbench
    // lenses. It is optional: if parity.js failed to load, the resting dock still works.
    if (window.ControlRoomParity && window.ControlRoomParity.renderDock) {
      window.ControlRoomParity.renderDock(run, AppState.glance);
    }
    // Contain keyboard focus while the modal dock owns the screen (A-1).
    dock.addEventListener("keydown", trapDockFocus);
    dockOrigin = origin || null;
    var close = document.getElementById("dock-close");
    if (close) close.focus();
  }

  /**
   * A-1 focus containment (IA §10.5): while the modal dock is open, Tab must cycle within it,
   * never escape to the resting roster behind. Shift+Tab from the first wraps to the last and
   * Tab from the last wraps to the first.
   */
  function trapDockFocus(event) {
    if (event.key !== "Tab") return;
    var dock = document.getElementById("selection-dock");
    if (!dock || dock.hidden) return;
    var focusables = dock.querySelectorAll(
      "button, [href], input, select, textarea, [tabindex]:not([tabindex='-1'])");
    if (!focusables.length) return;
    var first = focusables[0];
    var last = focusables[focusables.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  }

  function closeDock() {
    var dock = document.getElementById("selection-dock");
    if (dock) {
      dock.hidden = true;
      dock.removeEventListener("keydown", trapDockFocus);
    }
    // Close the parity-owned per-worker stream (the "exactly one selected stream" invariant).
    if (window.ControlRoomParity && window.ControlRoomParity.closeDock) {
      window.ControlRoomParity.closeDock();
    }
    // Stop feeding a run the operator is no longer inspecting.
    AppState.feedRunId = null;
    AppState.feedBuffer = [];
    if (dockOrigin && typeof dockOrigin.focus === "function") dockOrigin.focus();
    dockOrigin = null;
  }

  function findRunById(runId) {
    var sample = (AppState.glance && AppState.glance.run_sample) || [];
    for (var i = 0; i < sample.length; i += 1) {
      if (sample[i]["session.identity"] === runId) return sample[i];
    }
    return null;
  }

  // ── Chrome wiring ───────────────────────────────────────────────────────────────────────

  function wireChrome() {
    var themeToggle = document.getElementById("theme-toggle");
    if (themeToggle) {
      themeToggle.addEventListener("click", function () {
        var next = document.documentElement.dataset.theme === "light" ? "dark" : "light";
        document.documentElement.dataset.theme = next;
        try { window.localStorage.setItem("control-room-theme", next); } catch (_error) {}
      });
    }
    // R1 step 4: the attention inbox expands IN PLACE. The toggle is a real button, so a click
    // (mouse, Enter or Space) reaches this one delegated handler; no mutation is ever fired here.
    var attentionList = document.getElementById("attention-list");
    if (attentionList) {
      attentionList.addEventListener("click", function (event) {
        var toggle = event.target.closest("[data-attention-toggle]");
        if (toggle) toggleAttention(toggle);
      });
    }
    var runList = document.getElementById("run-list");
    if (runList) {
      runList.addEventListener("click", function (event) {
        var row = event.target.closest("[data-run-id]");
        if (!row) return;
        var run = findRunById(row.getAttribute("data-run-id"));
        if (run) openDock(run, row);
      });
      runList.addEventListener("keydown", function (event) {
        if (event.key !== "Enter" && event.key !== " ") return;
        var row = event.target.closest("[data-run-id]");
        if (!row) return;
        event.preventDefault();
        var run = findRunById(row.getAttribute("data-run-id"));
        if (run) openDock(run, row);
      });
    }
    var close = document.getElementById("dock-close");
    if (close) close.addEventListener("click", closeDock);
    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape") {
        var dock = document.getElementById("selection-dock");
        if (dock && !dock.hidden) closeDock();
      }
    });
  }

  // ── Boot ────────────────────────────────────────────────────────────────────────────────

  function init() {
    wireChrome();
    loadGlance();
    connectEvents();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
