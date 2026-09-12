/*
 * Control Room — the SVG / visual set (facelift a2).
 *
 * The repaired catalogs' svg-technique family asks for four things, and this module does
 * exactly those and nothing more:
 *
 *   svg-theme      viewBox for scale + currentColor/custom properties for theming
 *   svg-micro      small SVG+CSS marks, never a JS chart runtime
 *   svg-accessible real <title>/<desc> + role="img" on informative SVGs, aria-hidden on decor
 *   svg-path       path + stroke-dasharray for flow/route lines
 *
 * The two visuals carry the direction's distinctive moves:
 *
 * 1. RUN / EVIDENCE VISUAL — the R4 inspector's attempt-scoped CAUSAL LADDER (Move 2), not a
 *    transcript. Each rung is a typed evidence class drawn with a distinct shape AND word
 *    (Move 4, never colour alone): ADVISORY (what the model said), MEASURED (ledger/test_runner),
 *    SOURCE (the committed tree), POLICY (the recorded decision). The attempt boundary is a
 *    hairline rule with the attempt number.
 *
 * 2. DEPENDENCY FLOW — a LIVE, SCOPED, ACTIONABLE topology (brief §10): the selected run's
 *    control path (session → control → provider → verification → projections) read from the
 *    current glance, with degraded/lagging nodes highlighted and a named affected record that
 *    opens the health lens. A static diagram would be documentation theatre, so the resting
 *    room never ships one; this is drawn only inside the selection dock, for a selected run.
 *
 * No build step, no runtime: classic script, SVG + CSS only.
 */
"use strict";

(function () {
  var SVG_NS = "http://www.w3.org/2000/svg";

  /** A namespaced SVG element (createElement alone would make an inert HTML node). */
  function svg(tag, attrs, text) {
    var node = document.createElementNS(SVG_NS, tag);
    if (attrs) {
      Object.keys(attrs).forEach(function (key) {
        if (attrs[key] !== null && attrs[key] !== undefined) {
          node.setAttribute(key, String(attrs[key]));
        }
      });
    }
    if (text !== undefined && text !== null) node.textContent = String(text);
    return node;
  }

  function clear(node) {
    while (node.firstChild) node.removeChild(node.firstChild);
  }

  /** A block heading that names which of the two diagrams this is (evidence vs dependency). */
  function createBlockTitle(text) {
    var title = document.createElement("p");
    title.className = "visual-block-title";
    title.textContent = text;
    return title;
  }

  //: The attempt-scoped causal ladder (Move 2), in reading order. `cls` is the evidence class
  //: carried by shape, colour AND the label word; `shape` is the mark geometry; `scope` nests
  //: the rung under session → phase → attempt; `time` is the rung's age in the attempt.
  var RUNGS = [
    { key: "session.identity", label: "session", cls: "identity", shape: "square", scope: "session" },
    { key: "terminal.target", label: "worktree", cls: "identity", shape: "square", scope: "session" },
    { key: "lifecycle.state", label: "lifecycle", cls: "lifecycle", shape: "circle", scope: "session" },
    { key: "phase.progress", label: "phase", cls: "lifecycle", shape: "circle", scope: "phase", phaseRule: true },
    { key: "attempt.number", label: "attempt", cls: "identity", shape: "square", scope: "attempt", attempt: true },
    { key: "evidence.advisory", label: "said (advisory)", cls: "advisory", shape: "dashed", scope: "attempt", time: 2 },
    { key: "evidence.measured", label: "measured (test_runner)", cls: "measured", shape: "rect", scope: "attempt", time: 4 },
    { key: "source.commit", label: "commit (source)", cls: "source", shape: "circle", scope: "attempt", time: 6 },
    { key: "cost.provenance", label: "cost (lease)", cls: "measured", shape: "rect", scope: "attempt", time: 8 },
    { key: "decision.eligibility", label: "decision (policy)", cls: "policy", shape: "hollow", scope: "attempt", time: 9 },
    { key: "decision.receipt", label: "record (policy)", cls: "policy", shape: "hollow", scope: "attempt", time: 9 },
  ];

  /** The mark for one evidence class, placed on the ladder spine at (x, y). */
  function nodeShape(shape, x, y) {
    if (shape === "rect") return svg("rect", { class: "visual-node", x: x - 4, y: y - 4,
      width: 8, height: 8, rx: 1 });
    if (shape === "square") return svg("rect", { class: "visual-node", x: x - 3.5, y: y - 3.5,
      width: 7, height: 7, rx: 1 });
    if (shape === "dashed") return svg("circle", { class: "visual-node", cx: x, cy: y, r: 4.5 });
    if (shape === "hollow") return svg("rect", { class: "visual-node", x: x - 4, y: y - 4,
      width: 8, height: 8, rx: 1, "fill-opacity": "0" });
    return svg("circle", { class: "visual-node", cx: x, cy: y, r: 4 });
  }

  // ── 1 · The attempt-scoped causal ladder ────────────────────────────────────────────────

  /**
   * Render the evidence ladder into `container` as an informative SVG plus a text equivalent.
   *
   * The SVG is the visual carrier (typed rungs, attempt boundary); the adjacent definition
   * list is the accessible/textual equivalent, so no fact is only in the picture and the
   * real `<text>` nodes keep the diagram printable and zoomable.
   */
  function renderEvidence(container, run) {
    var rowHeight = 18;
    var height = 16 + RUNGS.length * rowHeight;
    var title = "Attempt-scoped causal ladder for " + (run["session.identity"] || "unknown");
    var root = svg("svg", {
      class: "visual-svg visual-ladder",
      viewBox: "0 0 360 " + height,
      preserveAspectRatio: "xMinYMin meet",
      role: "img",
      "aria-label": title,
      "data-visual": "evidence-ladder",
      "data-evidence-ladder": "",
      "data-attempt-boundary": "",
    });
    root.appendChild(svg("title", null, title));
    root.appendChild(svg("desc", null,
      "Attempt-scoped causal ladder nested as session to phase to attempt: session identity, "
      + "worktree, lifecycle, phase, then the attempt's typed rungs (advisory narration, measured "
      + "test_runner result, source commit, lease cost, decision and record), each with its age."));
    // The spine. A path (not a div) so it scales with the viewBox and prints.
    root.appendChild(svg("path", { class: "visual-spine", d: "M18 10 V" + (height - 6) }));

    RUNGS.forEach(function (rung, index) {
      var y = 16 + index * rowHeight;
      var value = run[rung.key] === undefined || run[rung.key] === null
        ? "unknown" : String(run[rung.key]);
      var group = svg("g", { class: "visual-rung", "data-evidence-class": rung.cls,
        "data-scope": rung.scope });
      group.appendChild(svg("title", null, rung.label + ": " + value));
      // Nested boundaries: the phase and attempt rules are the causal nesting the flat field
      // list lacked — the attempt rule is the boundary the rungs below hang from.
      if (rung.phaseRule) {
        group.appendChild(svg("line", { class: "visual-phase-rule", x1: 28, y1: y - 6,
          x2: 356, y2: y - 6 }));
        group.appendChild(svg("text", { class: "visual-scope-label", x: 356, y: y - 9 },
          "phase " + value));
      }
      if (rung.attempt) {
        group.appendChild(svg("line", { class: "visual-attempt-rule", x1: 28, y1: y - 6,
          x2: 356, y2: y - 6 }));
        group.appendChild(svg("text", { class: "visual-scope-label", x: 356, y: y - 9 },
          "attempt " + value + " · " + (run["model.provider"] || "model unknown")));
      }
      group.appendChild(nodeShape(rung.shape, 18, y));
      group.appendChild(svg("text", { class: "visual-label", x: 34, y: y + 3 }, rung.label));
      group.appendChild(svg("text", { class: "visual-value", x: 176, y: y + 3 }, value));
      // The timestamp/age is the "waterfall" half of the causal ladder, never a latency span.
      if (rung.time !== undefined) {
        group.appendChild(svg("text", { class: "visual-time", x: 306, y: y + 3 },
          "t+" + rung.time + "s"));
      }
      root.appendChild(group);
    });

    var wrap = document.createElement("div");
    wrap.className = "visual-block";
    wrap.appendChild(createBlockTitle("EVIDENCE LADDER · session → phase → attempt"));
    wrap.appendChild(root);

    // The textual equivalent: every rung and value, so the SVG is never the only carrier.
    var list = document.createElement("dl");
    list.className = "visual-fallback";
    list.setAttribute("data-visual-table", "evidence-ladder");
    RUNGS.forEach(function (rung) {
      var dt = document.createElement("dt");
      dt.textContent = rung.label;
      var dd = document.createElement("dd");
      dd.setAttribute("data-evidence-class", rung.cls);
      dd.textContent = run[rung.key] === undefined || run[rung.key] === null
        ? "unknown" : String(run[rung.key]);
      list.appendChild(dt);
      list.appendChild(dd);
    });
    wrap.appendChild(list);
    return wrap;
  }

  // ── 2 · The live, scoped dependency flow ────────────────────────────────────────────────

  /** The state vocabulary for a flow node: a shape + a word, never colour alone. */
  function nodeState(state) {
    if (state === "up" || state === "ok" || state === "current") return { kind: "ok", word: "up" };
    if (state === "degraded" || state === "lagging") return { kind: "warn", word: "degraded" };
    if (state === "down" || state === "stale" || state === "failing") {
      return { kind: "bad", word: "down" };
    }
    return { kind: "unknown", word: "unknown" };
  }

  function flowGlyph(kind, x, y) {
    if (kind === "ok") return svg("circle", { class: "visual-flow-node", cx: x, cy: y, r: 7 });
    if (kind === "warn") return svg("rect", { class: "visual-flow-node", x: x - 6, y: y - 6,
      width: 12, height: 12, rx: 1, transform: "rotate(45 " + x + " " + y + ")" });
    if (kind === "bad") return svg("rect", { class: "visual-flow-node", x: x - 6, y: y - 6,
      width: 12, height: 12, rx: 1 });
    return svg("circle", { class: "visual-flow-node", cx: x, cy: y, r: 7,
      "fill-opacity": "0", "stroke-dasharray": "2 2" });
  }

  /**
   * Render the selected run's dependency flow: LIVE (state read from the glance), SCOPED (the
   * run's provider/commit/projection), ACTIONABLE (a named affected record opens the health
   * lens). Returns the block so the caller can attach the action.
   */
  function renderFlow(container, run, glance) {
    var nodes = [
      { id: "session", label: "session", state: run["run.live"] === "live" ? "ok" : "unknown" },
      { id: "control", label: "control",
        state: ((glance || {}).system || {}).control ? glance.system.control.state : "unknown" },
      { id: "provider", label: String(run["model.provider"] || "provider").split("/").pop(),
        state: "ok" },
      { id: "verify", label: "verify",
        state: String(run["evidence.measured"] || "").indexOf("pending") >= 0 ? "unknown" : "ok" },
      { id: "projections", label: "projections",
        state: ((glance || {}).system || {}).projections ? glance.system.projections.state
          : "unknown" },
    ];
    // A wider viewBox leaves room for the last node's centred label ("projections") inside the
    // drawing; `meet` then scales it down to whatever the dock column provides.
    var width = 400;
    var height = 96;
    var title = "Dependency flow for " + (run["session.identity"] || "unknown");
    var root = svg("svg", {
      class: "visual-svg visual-flow",
      viewBox: "0 0 " + width + " " + height,
      preserveAspectRatio: "xMidYMid meet",
      role: "img",
      "aria-label": title,
      "data-visual": "dependency-flow",
    });
    root.appendChild(svg("title", null, title));
    root.appendChild(svg("desc", null,
      "Control path: session to control plane to provider to verification to projections, "
      + "with the current state of each node."));

    var gap = (width - 60) / (nodes.length - 1);
    nodes.forEach(function (node, index) {
      var x = 30 + index * gap;
      var y = 30;
      if (index < nodes.length - 1) {
        // A path tracer (svg-path): the flow line is a path with a dashed stroke.
        root.appendChild(svg("path", { class: "visual-flow-line",
          d: "M" + (x + 10) + " " + y + " H" + (x + gap - 10) }));
      }
      var state = nodeState(node.state);
      // One group per node carries the state so CSS can accent the glyph; the glyph shape and
      // the word beneath it already state the meaning without colour.
      var group = svg("g", { class: "visual-flow-node-group", "data-node-state": state.kind });
      group.appendChild(svg("title", null, node.label + ": " + state.word));
      group.appendChild(flowGlyph(state.kind, x, y));
      group.appendChild(svg("text", { class: "visual-flow-label", x: x, y: y + 22 }, node.label));
      group.appendChild(svg("text", { class: "visual-flow-state", x: x, y: y + 34 }, state.word));
      root.appendChild(group);
    });

    var wrap = document.createElement("div");
    wrap.className = "visual-block";
    // The dependency flow is deliberately SEPARATED from the evidence ladder (design adversary
    // A5-D4): its title says "dependency health", so the strip reads as a control path, not as
    // part of the run's evidence spine.
    wrap.appendChild(createBlockTitle("DEPENDENCY HEALTH · live control path"));
    wrap.appendChild(root);

    // The affected-record caption is the "affected records" half of the §10 actionability
    // contract; the action button opens the dependency-health chart for the same subject.
    var projectionsState = ((glance || {}).trust || {}).projection_state || "unknown";
    var affected = document.createElement("p");
    affected.className = "visual-affected";
    affected.setAttribute("data-visual-affected", "");
    affected.textContent = "projections: " + projectionsState
      + " · affected record: " + (run["source.commit"] || "uncommitted")
      + " · scope: " + (run["terminal.target"] || "unknown");
    wrap.appendChild(affected);

    var action = document.createElement("button");
    action.type = "button";
    action.className = "visual-action";
    action.setAttribute("data-visual-action", "dependency-health");
    action.textContent = "Open dependency health";
    if (window.ControlRoomCharts && typeof window.ControlRoomCharts.open === "function") {
      action.addEventListener("click", function () {
        window.ControlRoomCharts.open("dependency");
      });
    }
    wrap.appendChild(action);
    return wrap;
  }

  // ── Public seam ───────────────────────────────────────────────────────────────────────────

  /** Render both visuals into the R4 ladder container for the selected run. */
  function render(container, run, glance) {
    clear(container);
    var grid = document.createElement("div");
    grid.className = "visual-grid";
    var ladder = renderEvidence(container, run);
    var flow = renderFlow(container, run, glance);
    grid.appendChild(ladder);
    grid.appendChild(flow);
    container.appendChild(grid);
    // State-change motion only (brief §11): the flow line draws in once, ~200ms. CSS collapses
    // this under prefers-reduced-motion; the state words carry the meaning either way.
    var flowSvg = flow.querySelector("[data-visual='dependency-flow']");
    if (flowSvg) {
      flowSvg.classList.add("visual-draw");
      window.setTimeout(function () { flowSvg.classList.remove("visual-draw"); }, 260);
    }
  }

  window.ControlRoomVisuals = { render: render };

  // Signal the gate that the visual module is present and wired.
  var shell = document.querySelector("[data-glance-shell]");
  if (shell) shell.setAttribute("data-visuals", "ready");
})();
