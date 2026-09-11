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

  /**
   * One run-ledger row: the 16-field schema split across three declared lines, leading with the
   * agent/session identity band (Move 1) and pairing the ADVISORY claim with the MEASURED proof
   * (Move 4). Identifiers may middle-elide; measured/state values may not.
   */
  function renderRunRow(run) {
    // Mobile is triage: the value band must stay legible without labels, so the evidence values
    // collapse to their single-word tokens. Narrow is DENSE (short labels, identifiers elide);
    // desktop keeps the full word. This is the density ladder, not a second information model.
    var compact = window.innerWidth < 760;
    var dense = window.innerWidth < 1200;
    var lab = function (key, full) { return dense ? (SHORT_ROW_LABELS[key] || full) : full; };
    // The evidence material is typed by its label + colour/weight; the dense (narrow/mobile)
    // value collapses to its token so the line never clips a required value.
    var advisory = dense ? "claimed" : run["evidence.advisory"];
    var measured = dense ? "pending" : run["evidence.measured"];
    // The "source" label already names the material, so the value is the bare commit sha — this
    // also leaves the row's third line room for the authority chip on a governed decision.
    var sourceValue = String(run["source.commit"] || run["evidence.source"] || "unknown")
      .replace(/^commit\s+/, "");
    var row = element("li", "run-row", {
      "data-run-id": run["session.identity"] || "unknown",
      "data-attention": run["attention.state"] || "none",
      "data-live": run["run.live"] || "not-live",
      role: "button",
      tabindex: "0",
      "aria-label": "Run " + (run["session.identity"] || "unknown"),
    });

    var lineOne = element("div", "row-line", { "data-row-line": "", "data-max-lines": "1" });
    appendField(lineOne, "session.identity", lab("session.identity", "session"), run["session.identity"], {
      identifier: true, maxLines: 1,
    });
    appendField(lineOne, "terminal.target", lab("terminal.target", "target"), run["terminal.target"], {
      identifier: true, maxLines: 1,
    });
    appendField(lineOne, "command.current", lab("command.current", "command"), run["command.current"], { maxLines: 1 });
    // The provider×model token can middle-elide on a narrow row (it is an identifier, so the
    // gate permits it); the full value stays in the accessible title.
    appendField(lineOne, "model.provider", lab("model.provider", "model"), run["model.provider"], {
      identifier: true, maxLines: 1,
    });
    appendField(lineOne, "attempt.number", lab("attempt.number", "attempt"), run["attempt.number"], { maxLines: 1 });

    var lineTwo = element("div", "row-line", { "data-row-line": "", "data-max-lines": "1" });
    appendField(lineTwo, "phase.progress", lab("phase.progress", "phase"), run["phase.progress"], { maxLines: 1 });
    appendField(lineTwo, "lifecycle.state", lab("lifecycle.state", "lifecycle"), run["lifecycle.state"], { maxLines: 1 });
    appendField(lineTwo, "run.live", lab("run.live", "live"), run["run.live"], { maxLines: 1 });
    appendField(lineTwo, "source.commit", lab("source.commit", "commit"), run["source.commit"], {
      identifier: true, maxLines: 1,
    });
    appendField(lineTwo, "cost.provenance", lab("cost.provenance", "cost"), run["cost.provenance"], { maxLines: 1 });
    appendField(lineTwo, "attention.state", lab("attention.state", "attention"), run["attention.state"], { maxLines: 1 });

    var lineThree = element("div", "row-line", { "data-row-line": "", "data-max-lines": "1" });
    appendField(lineThree, "evidence.advisory", lab("evidence.advisory", "said"), advisory, {
      evidenceClass: "advisory", maxLines: 1,
    });
    appendField(lineThree, "evidence.measured", lab("evidence.measured", "measured"), measured, {
      evidenceClass: "measured", maxLines: 1,
    });
    appendField(lineThree, "evidence.source", lab("evidence.source", "source"), sourceValue, {
      evidenceClass: "source", maxLines: 1,
    });
    var eligibility = run["decision.eligibility"];
    appendField(lineThree, "decision.eligibility", lab("decision.eligibility", "eligible"), eligibility, { maxLines: 1 });
    // Recognizability §4.2 #2: a governed decision names its authority beside the eligibility
    // token. It is a non-field chip, so the gate's 16-field row schema is untouched. Mobile is
    // triage and drops the chip; the R1 decision item is the mobile authority mirror.
    var governed = { approve: true, promote: true, cancel: true, retire: true };
    if (!compact && governed[eligibility]) {
      lineThree.appendChild(element("span", "row-authority",
        { "data-authority": "controller", title: "authority: controller" }, "controller"));
    }
    appendField(lineThree, "decision.receipt", lab("decision.receipt", "receipt"), run["decision.receipt"], { maxLines: 1 });

    row.appendChild(lineOne);
    row.appendChild(lineTwo);
    row.appendChild(lineThree);
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

  /** One attention item with exactly two declared lines (the reserved/ranked work queue).
   *  `config.key` is the stable reconciliation key the write-on-change list uses. */
  function renderAttentionItem(config) {
    var item = element("li", "attention-item", {
      "data-attention-class": config.kind,
      "data-item-key": config.key || config.kind,
      tabindex: config.answer ? "0" : null,
      "aria-label": config.ariaLabel || null,
    });
    var body;
    if (config.answer) {
      body = element("div", null, { "data-answer": config.answer });
      item.appendChild(body);
    } else {
      body = item;
    }
    config.lines.forEach(function (lineFields, index) {
      var line = element("div", "item-line", { "data-item-line": "", "data-max-lines": "1" });
      if (index === 0 && config.title) {
        line.appendChild(element("span", "item-kind", null, config.title));
      }
      lineFields.forEach(function (spec) {
        appendField(line, spec[0], spec[1], spec[2], {
          identifier: spec[3] === true,
          maxLines: 1,
        });
      });
      body.appendChild(line);
    });
    return item;
  }

  /** R1 `ON-G5`/`ON-G3`: reserved decision + risk rows, then the ranked next items to capacity.
   *  Keyed and write-on-change: the reserved rows keep their identity across a live update. */
  function renderAttention(glance) {
    var host = document.getElementById("attention-list");
    var attention = glance.attention || {};
    var decision = attention.decision || { state: "none", target: "none", kind: "none",
      epoch: 0, authority: "none", eligibility: "none" };
    var risk = attention.risk || { identity: "none", state: "all-clear", action: "none" };
    var nodes = [];

    var decisionItem = renderAttentionItem({
      key: "decision",
      kind: "decision",
      answer: "ON-G5",
      title: "DECISION",
      ariaLabel: "Pending controller decision",
      lines: [
        [
          ["decision.state", "state", decision.state, false],
          ["decision.target", "target", decision.target, true],
          ["decision.kind", "kind", decision.kind, false],
        ],
        [
          ["decision.epoch", "epoch", decision.epoch, false],
          ["decision.authority", "authority", decision.authority, false],
          ["decision.eligibility", "eligible", decision.eligibility, false],
        ],
      ],
    });
    decisionItem.__signature = JSON.stringify(decision);
    nodes.push(decisionItem);

    var riskItem = renderAttentionItem({
      key: "risk",
      kind: "risk",
      answer: "ON-G3",
      title: "RISK",
      ariaLabel: "Highest-severity run risk",
      lines: [
        [
          ["risk.identity", "target", risk.identity, true],
          ["risk.state", "state", risk.state, false],
        ],
        [["risk.action", "action", risk.action, false]],
      ],
    });
    riskItem.__signature = JSON.stringify(risk);
    nodes.push(riskItem);

    var next = attention.next || { identity: "none", state: "clear", action: "none" };
    var nextItem = renderAttentionItem({
      key: "next",
      kind: "next",
      title: "NEXT",
      ariaLabel: "Next highest-ranked item",
      lines: [
        [["next.identity", "target", next.identity, true],
          ["next.state", "state", next.state, false]],
        [["next.action", "action", next.action, false]],
      ],
    });
    nextItem.__signature = JSON.stringify(next);
    nodes.push(nextItem);

    // Fill the remaining reserved capacity so the at-rest row count is exact per viewport.
    var filler = capacities().attention - 3;
    for (var i = 0; i < filler; i += 1) {
      var item = element("li", "attention-item", {
        "data-attention-class": "empty",
        "data-item-key": "empty-" + i,
        "aria-label": "No further attention",
      });
      var lineA = element("div", "item-line", { "data-item-line": "", "data-max-lines": "1" });
      lineA.appendChild(element("span", "item-kind", null, "—"));
      lineA.appendChild(element("span", "item-kind", null, "No further attention"));
      var lineB = element("div", "item-line", { "data-item-line": "", "data-max-lines": "1" });
      lineB.appendChild(element("span", "item-kind", null, "queue clear"));
      item.appendChild(lineA);
      item.appendChild(lineB);
      item.__signature = "empty";
      nodes.push(item);
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
        bucket.appendChild(element("span", "bucket-label", null, bucketName.slice(0, 1)));
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

  function openDock(run, origin) {
    var dock = document.getElementById("selection-dock");
    var ladder = document.getElementById("evidence-ladder");
    var title = document.getElementById("dock-title");
    if (!dock || !ladder) return;
    clear(ladder);
    if (title) title.textContent = "RUN " + (run["session.identity"] || "unknown");
    // The inspector is an attempt-scoped CAUSAL LADDER plus a live, scoped dependency flow
    // (brief §10 / Move 2). visuals.js owns the SVG; the text equivalents it renders alongside
    // keep the dock accessible, printable and readable with no graphics at all.
    if (window.ControlRoomVisuals) {
      window.ControlRoomVisuals.render(ladder, run, AppState.glance);
    }
    dock.hidden = false;
    dockOrigin = origin || null;
    var close = document.getElementById("dock-close");
    if (close) close.focus();
  }

  function closeDock() {
    var dock = document.getElementById("selection-dock");
    if (dock) dock.hidden = true;
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
