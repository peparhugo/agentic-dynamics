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
 *         selector: `[data-answer="ON-G5"] [data-field="decision.eligibility"]`
 *   (c) spend against a hard budget — `renderRunRow` builds `.row-lease[data-budget-state]` (the
 *       headroom bar) with `data-budget-reserved`, `data-budget-settled`, `data-budget-cap`,
 *       `data-budget-headroom` and `data-budget-settlement`, plus the `cost.provenance` pair.
 *         selector: `.run-row[data-run-id] .row-lease[data-budget-state]`
 *   (d) evidence is inspectable — `renderRunRow` builds `.row-evidence [data-evidence-class]`
 *       marks and `decision.receipt`; `openDock` builds the causal ladder, the typed address and
 *       the bounded follow/pause attempt feed.
 *         selector: `.run-row[data-run-id] .row-evidence [data-evidence-class="measured"]`
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

  /** R2 `ON-G2`: the exact running/queued/failed/live counts. */
  function renderRunCounts(glance) {
    var host = document.getElementById("run-counts");
    clear(host);
    var counts = glance.run_counts || {};
    ["running", "queued", "failed", "live"].forEach(function (key) {
      appendField(host, "runs." + key, key, Number(counts[key] || 0), { maxLines: 1 });
    });
  }

  /** The governed eligibility vocabulary: only these name an acting controller (Move 3). */
  var GOVERNED = { approve: true, promote: true, cancel: true, retire: true };

  /** Take the basename of a path-like token (`wt/control-room` → `control-room`). */
  function basename(value) {
    return String(value === undefined || value === null ? "unknown" : value).split("/").pop();
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
    var statusState = live === "live" ? "live"
      : (lifecycle === "failed" ? "failed" : (governed ? "waiting" : "idle"));
    var statusGlyph = statusState === "live" ? "\u25CF"
      : (statusState === "failed" ? "\u2715" : (statusState === "waiting" ? "\u25B8" : "\u25CB"));

    var row = element("li", "run-row", {
      "data-run-id": session,
      "data-attention": run["attention.state"] || "none",
      "data-live": live,
      "data-decision": governed ? eligibility : "none",
      role: "button",
      tabindex: "0",
      "aria-label": "Agent session " + session + ", " + lifecycle,
    });

    // ── Line 1 · the session identity band (Move 1) ────────────────────────────────────────
    var lineOne = element("div", "row-line session-band",
      { "data-row-line": "", "data-max-lines": "1", "data-agent": session });
    lineOne.appendChild(element("span", "agent-prompt", { "aria-hidden": "true" }, "\u276F"));
    lineOne.appendChild(element("span", "row-status",
      { "data-state": statusState, title: "session state: " + statusState, "aria-hidden": "true" },
      statusGlyph));
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
    var lineTwo = element("div", "row-line run-state", { "data-row-line": "", "data-max-lines": "1" });
    appendField(lineTwo, "phase.progress", lab("phase.progress", "phase"),
      mark("ph", run["phase.progress"]), { maxLines: 1 });
    appendField(lineTwo, "lifecycle.state", lab("lifecycle.state", "lifecycle"),
      mark("life", lifecycle), { maxLines: 1 });
    appendField(lineTwo, "run.live", lab("run.live", "live"), mark("live", live), { maxLines: 1 });
    appendField(lineTwo, "source.commit", lab("source.commit", "commit"),
      mark("cmt", sourceValue), { identifier: true, maxLines: 1 });
    appendField(lineTwo, "cost.provenance", lab("cost.provenance", "cost"), costPair, {
      maxLines: 1, title: "reserved/cap · " + settlement + " · " + costSource,
    });
    appendField(lineTwo, "attention.state", lab("attention.state", "attention"),
      mark("attn", run["attention.state"]), { maxLines: 1 });
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
      { "data-row-line": "", "data-max-lines": "1" });
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

  /** R2 body: the bounded, attention-ranked sample (exactly the viewport's capacity).
   *  Keyed by run id and write-on-change, so an unchanged row keeps its identity and focus. */
  function renderRunList(glance) {
    var host = document.getElementById("run-list");
    var sample = (Array.isArray(glance.run_sample) ? glance.run_sample : [])
      .slice(0, capacities().rows);
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
   */
  function attentionItem(config) {
    var item = element("li", "attention-item", {
      "data-attention-class": config.kind,
      "data-item-key": config.key,
      tabindex: config.answer ? "0" : null,
      "aria-label": config.ariaLabel || null,
    });
    var body = item;
    if (config.answer) {
      body = element("div", null, { "data-answer": config.answer });
      item.appendChild(body);
    }
    return { item: item, body: body };
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

  /** R1 `ON-G5`/`ON-G3`: a ranked, durable work queue of run-linked items, then ONE continuous
   *  clear state. Keyed and write-on-change: reserved rows keep identity across a live update. */
  function renderAttention(glance) {
    var host = document.getElementById("attention-list");
    var attention = glance.attention || {};
    var decision = attention.decision || { state: "none", target: "none", kind: "none",
      epoch: 0, authority: "none", eligibility: "none" };
    var risk = attention.risk || { identity: "none", state: "all-clear", action: "none" };
    var next = attention.next || { identity: "none", state: "clear", action: "none" };
    var nodes = [];
    var pending = String(decision.state || "none") !== "none";

    // ── DECISION (ON-G5) — a governed door, not a button ───────────────────────────────────
    var decisionItem = attentionItem({
      key: "decision",
      kind: "decision",
      answer: "ON-G5",
      ariaLabel: pending
        ? "Pending controller decision: " + decision.kind + " " + decision.target
        : "No pending decision",
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
    attentionLine(decisionItem.body, pending ? "waiting on" : "none pending", [
      ["decision.epoch", "epoch", decision.epoch, false],
      ["decision.authority", "authority", decision.authority, false],
      ["decision.target", "target", decision.target, true],
    ]);
    decisionItem.item.__signature = JSON.stringify(decision);
    nodes.push(decisionItem.item);

    // ── RISK (ON-G3) — the reserved highest-severity run problem ───────────────────────────
    var riskItem = attentionItem({
      key: "risk",
      kind: "risk",
      answer: "ON-G3",
      ariaLabel: "Highest-severity run risk: " + risk.identity,
    });
    attentionLine(riskItem.body, "RISK", [
      ["risk.identity", "target", risk.identity, true],
      ["risk.state", "state", risk.state, false],
    ]);
    attentionLine(riskItem.body, "OWNER", [["risk.action", "action", risk.action, false]]);
    riskItem.item.__signature = JSON.stringify(risk);
    nodes.push(riskItem.item);

    // ── NEXT — the next ranked work item ───────────────────────────────────────────────────
    var nextItem = attentionItem({
      key: "next",
      kind: "next",
      ariaLabel: "Next highest-ranked item: " + next.identity,
    });
    attentionLine(nextItem.body, "NEXT", [
      ["next.identity", "target", next.identity, true],
      ["next.state", "state", next.state, false],
    ]);
    attentionLine(nextItem.body, "OWNER", [["next.action", "action", next.action, false]]);
    nextItem.item.__signature = JSON.stringify(next);
    nodes.push(nextItem.item);

    // Fill the remaining reserved capacity so the at-rest count is exact per viewport. The
    // filler is ONE continuous empty state: only the first carries words, the rest are blank
    // ruler lines (the DOM count the gate measures is preserved).
    var filler = capacities().attention - 3;
    for (var i = 0; i < filler; i += 1) {
      var empty = attentionItem({
        key: "empty-" + i,
        kind: "empty",
        ariaLabel: i === 0 ? "Queue clear, no further attention" : null,
      });
      var lineA = element("div", "item-line", { "data-item-line": "", "data-max-lines": "1" });
      var lineB = element("div", "item-line", { "data-item-line": "", "data-max-lines": "1" });
      if (i === 0) {
        lineA.appendChild(element("span", "item-kind", null, "QUEUE CLEAR"));
        lineA.appendChild(element("span", "queue-empty-note", null, "no further attention"));
        lineB.appendChild(element("span", "queue-empty-note", null,
          "decision queue drained · 0 waiting"));
      }
      empty.body.appendChild(lineA);
      empty.body.appendChild(lineB);
      empty.item.__signature = "empty";
      nodes.push(empty.item);
    }
    reconcileList(host, nodes, "data-item-key");
  }

  /** R3a `ON-G4`: exactly five labelled money values + an optional risk marker. */
  function renderCost(glance) {
    var host = document.getElementById("cost-grid");
    clear(host);
    var cost = glance.cost || {};
    var rows = [
      ["money.spend", "spend", cost.spend],
      ["money.burn", "burn", cost.burn],
      ["money.quota", "quota", cost.quota],
      ["money.wallet", "wallet", cost.wallet],
      ["money.leases", "leases", cost.leases],
    ];
    rows.forEach(function (row) {
      // A cost cell stacks its label over its value on desktop/narrow (two lines); on mobile it
      // is inline (one line). The clamp is the desktop shape, so it declares two lines.
      appendField(host, row[0], row[1], row[2] === undefined ? "unknown" : row[2], { maxLines: 2 });
    });
    if (cost.money_risk) {
      var marker = element("span", "money-risk", { "data-money-risk": "" });
      marker.appendChild(element("span", null, null, "⚠ near cap"));
      host.appendChild(marker);
    }
    // Move 6 — the hard-budget headroom bar for the constraint ledger. `quota` is the cap
    // fraction; a non-numeric quota draws an explicit unknown track, never a full one.
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

  /** R3b: two bounded worker/projection detail lines (a mirror of R0, never its answer). */
  function renderHealth(glance) {
    var host = document.getElementById("health-lines");
    clear(host);
    var health = glance.health_detail || {};
    [["workers", health.workers], ["projections", health.projections]].forEach(function (row) {
      var line = element("div", "detail-line", { "data-detail-line": "", "data-max-lines": "1" });
      line.appendChild(element("span", null, { "data-label": "" }, row[0]));
      appendRawValue(line, row[1] === undefined ? "unknown" : row[1], null);
      host.appendChild(line);
    });
  }

  /** R3c `ON-G7`: four bounded marginals, each with exactly top/other/unknown buckets. */
  function renderComposition(glance) {
    var host = document.getElementById("composition");
    clear(host);
    var composition = glance.composition || {};
    ["model", "condition", "provider", "lifecycle"].forEach(function (name) {
      var marginal = element("div", "marginal", {
        "data-marginal": name,
        "data-max-lines": "1",
      });
      // Compact visible names fit the 64px label track; `data-marginal` keeps the full name.
      var shortNames = { model: "model", condition: "cond", provider: "prov", lifecycle: "life" };
      marginal.appendChild(element("span", "marginal-name", { title: name },
        shortNames[name] || name));
      var buckets = element("div", "marginal-buckets", null);
      var data = composition[name] || { top: "unknown 0", other: "0", unknown: "0" };
      ["top", "other", "unknown"].forEach(function (bucketName) {
        var bucket = element("span", "marginal-bucket", { "data-bucket": bucketName });
        // Explicit bucket words (top/other/unknown), never t/o/u shorthand a stranger must decode.
        bucket.appendChild(element("span", "bucket-label", null, bucketName));
        var bucketText = String(data[bucketName] === undefined ? "unknown" : data[bucketName]);
        if (bucketName === "top") {
          // `data-category` names the modal bucket (the gate requires it on `top`).
          var category = bucketText.split(" ")[0] || "unknown";
          bucket.setAttribute("data-category", category);
        }
        appendRawValue(bucket, bucketText, "bucket-value");
        buckets.appendChild(bucket);
      });
      marginal.appendChild(buckets);
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
      renderRunList(AppState.glance);
      renderAttention(AppState.glance);
      // Move 7 — a transition for the SELECTED run appends one live feed entry. A paused feed
      // buffers it (bounded) instead, so pause genuinely stops the stream demanding attention.
      if (frame.target === AppState.feedRunId) {
        appendFeed({ age: 0, cls: "lifecycle", text: frame.kind });
      }
    }
    if (epoch && epoch !== AppState.announcedEpoch) {
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

  /** Fetch the one-shot projection. A failure renders an explicit degraded screen, never a lie. */
  function loadGlance() {
    fetch("/api/glance", { headers: { Accept: "application/json" } })
      .then(function (response) {
        if (!response.ok) throw new Error("glance " + response.status);
        return response.json();
      })
      .then(function (glance) {
        AppState.glanceError = false;
        renderGlance(glance);
      })
      .catch(function () {
        // A failed projection is a first-class state: the resting screen degrades honestly and
        // the charts render their explicit error state (never a blank or stale panel).
        AppState.glanceError = true;
        renderGlance({
          control_epoch: 0,
          system: {
            browser: { state: "down", age_seconds: 0 },
            control: { state: "unknown", age_seconds: 0 },
            workers: { state: "unknown", age_seconds: 0 },
            projections: { state: "unknown", age_seconds: 0 },
          },
          trust: { epoch: 0, worst_age: 0, projection_state: "unknown", degraded_count: 0,
            stale_count: 0, partial_count: 0, unknown_count: 1 },
          attention: {
            decision: { state: "none", target: "none", kind: "none", epoch: 0,
              authority: "none", eligibility: "none" },
            risk: { identity: "none", state: "all-clear", action: "none" },
            next: { identity: "none", state: "clear", action: "none" },
          },
          run_counts: { running: 0, queued: 0, failed: 0, live: 0 },
          run_sample: [],
          cost: { spend: "unknown", burn: "unknown", quota: "unknown", wallet: "unknown",
            leases: "unknown", money_risk: false },
          health_detail: { workers: "unknown", projections: "unknown" },
          composition: {
            model: { top: "unknown 0", other: "0", unknown: "0" },
            condition: { top: "unknown 0", other: "0", unknown: "0" },
            provider: { top: "unknown 0", other: "0", unknown: "0" },
            lifecycle: { top: "unknown 0", other: "0", unknown: "0" },
          },
        });
        AppState.replayComplete = true;
        maybeReady();
      });
  }

  /** Follow the bounded SSE stream; it is the only open event stream on the screen. */
  function connectEvents() {
    if (typeof window.EventSource !== "function") {
      AppState.replayComplete = true;
      maybeReady();
      return;
    }
    var source = new window.EventSource("/api/events");
    source.addEventListener("snapshot", function (event) {
      try {
        var frame = JSON.parse(event.data);
        if (frame && frame.glance) {
          AppState.glanceError = false;
          renderGlance(frame.glance);
        }
      } catch (_error) { /* a malformed frame is ignored; the polled snapshot stands */ }
    });
    source.addEventListener("replay_complete", function () {
      AppState.replayComplete = true;
      maybeReady();
    });
    source.addEventListener("transition", function (event) {
      try {
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

  /** The seed attempt facts for a run, in causal order, typed by evidence class (Move 4/7). */
  function feedSeed(run) {
    var att = run["attempt.number"] || "?";
    var advisory = run["evidence.advisory"] || "unknown";
    var measured = run["evidence.measured"] || "unknown";
    var source = String(run["source.commit"] || "unknown").replace(/^commit\s+/, "");
    var reserved = run["budget.reserved"] || "unknown";
    var cap = run["budget.cap"] || "unknown";
    return [
      { age: 0, cls: "lifecycle", text: "attempt " + att + " started · " + (run["model.provider"] || "model unknown") },
      { age: 2, cls: "advisory", text: "said " + advisory },
      { age: 4, cls: "measured", text: "measured " + measured },
      { age: 6, cls: "source", text: "commit " + source },
      { age: 8, cls: "measured", text: "lease reserved " + reserved + " / cap " + cap },
    ];
  }

  /** One bounded feed row: age, evidence class, text — the same typed material as the row. */
  function feedRow(entry) {
    var li = element("li", "feed-entry", {
      "data-evidence-class": entry.cls,
      "data-age-seconds": String(entry.age),
    });
    li.appendChild(element("span", "feed-time", null, "t+" + entry.age + "s"));
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
    head.appendChild(element("span", "feed-age", { "data-feed-age": "" }, "age 0s · bounded " + FEED_MAX));
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
    dockOrigin = origin || null;
    var close = document.getElementById("dock-close");
    if (close) close.focus();
  }

  function closeDock() {
    var dock = document.getElementById("selection-dock");
    if (dock) dock.hidden = true;
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
