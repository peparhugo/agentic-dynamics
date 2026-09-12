/*
 * Control Room — parity layer (UX-repair wave, phase u4).
 *
 * WHY THIS FILE EXISTS
 * --------------------
 * The facelift reduced the old room's ~235 panels/controls to a 24-id resting screen and
 * re-pointed the client at `/api/glance` + `/api/events`. The server kept every route, but the
 * operator lost the per-worker event/action surface, the workforce step-timing view, and every
 * destination board. `experiments/research/control_room/parity_inventory.json` enumerates what
 * was dropped; `docs/research/control_room_ia.md` §12–§15 places each item on a surface.
 *
 * This module re-houses those surfaces without touching the canonical glance contract:
 *
 *   R4b  the selected worker's live event stream + the governed action band
 *   R4d  per-attempt step timings
 *   the workbench lenses: fleet, attention, money, registry, sessions, queue, routing, docs,
 *        audit, health, and the workforce step-timing aggregate
 *
 * Every panel lazy-loads the SAME endpoint the old room used (never a stub), and every mutation
 * goes through the server's loopback + same-origin + JSON + Idempotency-Key trust boundary.
 *
 * The resting screen is untouched: the workbench is `hidden` until opened, and R4 only renders
 * on selection, so the render gate's resting geometry and fixtures are unaffected. All content is
 * built with `element()`/`textContent` (never an HTML string), and every fetch/stream failure is
 * caught and rendered as an explicit state, never a thrown error or a console message.
 */
"use strict";

(function () {
  // ── DOM helpers (self-contained; the file has no dependency on app.js internals) ─────────

  /** Create an element with attributes and text; `true` means a bare attribute. */
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

  /** Remove every child (textContent-only; never parses markup). */
  function clear(node) {
    while (node.firstChild) node.removeChild(node.firstChild);
  }

  /** Append a simple span of text. */
  function span(parent, className, text) {
    var node = element("span", className || null, null, text);
    parent.appendChild(node);
    return node;
  }

  /** A human "N ago" from seconds, or an honest unknown. */
  function ago(seconds) {
    if (seconds === null || seconds === undefined || isNaN(Number(seconds))) return "unknown";
    var value = Number(seconds);
    if (value < 60) return value + "s";
    if (value < 3600) return Math.round(value / 60) + "m";
    if (value < 86400) return Math.round(value / 3600) + "h";
    return Math.round(value / 86400) + "d";
  }

  // ── Network helpers ─────────────────────────────────────────────────────────────────────

  /** A short, unique idempotency key; the server requires one on every mutation. */
  function idempotencyKey() {
    return "cr-" + Date.now().toString(36) + "-" + Math.random().toString(36).slice(2, 10);
  }

  /** GET JSON with a graceful `{ok,status,data,error}` result (never throws). */
  function getJSON(path) {
    return fetch(path, { headers: { Accept: "application/json" } })
      .then(function (response) {
        return response.json().catch(function () { return {}; })
          .then(function (data) { return { ok: response.ok, status: response.status, data: data }; });
      })
      .catch(function (error) { return { ok: false, status: 0, data: {}, error: String(error) }; });
  }

  /** POST JSON through the trust boundary. Returns the same graceful result shape. */
  function postJSON(path, body) {
    return fetch(path, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
        "Idempotency-Key": idempotencyKey(),
      },
      body: JSON.stringify(body || {}),
    })
      .then(function (response) {
        return response.json().catch(function () { return {}; })
          .then(function (data) { return { ok: response.ok, status: response.status, data: data }; });
      })
      .catch(function (error) { return { ok: false, status: 0, data: {}, error: String(error) }; });
  }

  // ── Confirmation (a non-native two-step / typed door) ─────────────────────────────────────
  //
  // The direction forbids native `window.confirm` (r0 M14): irreversible acts keep a composed
  // door. One bar is created lazily and reused; `requestConfirm` resolves true/false.

  var confirmBar = null;

  function ensureConfirmBar() {
    if (confirmBar) return confirmBar;
    confirmBar = element("div", "confirm-bar", { id: "confirm-bar", role: "alertdialog", hidden: true });
    document.body.appendChild(confirmBar);
    return confirmBar;
  }

  /** Render a confirmation door. `phrase` (optional) requires an exact typed match. */
  function requestConfirm(message, phrase) {
    return new Promise(function (resolve) {
      var bar = ensureConfirmBar();
      clear(bar);
      bar.hidden = false;
      bar.appendChild(element("p", "confirm-message", null, message));
      var input = null;
      if (phrase) {
        bar.appendChild(element("p", "confirm-hint", null, "Type " + phrase + " to continue."));
        input = element("input", "confirm-input", { type: "text", autocomplete: "off",
          "aria-label": "Type the confirmation phrase" });
        bar.appendChild(input);
      }
      var actions = element("div", "confirm-actions");
      var confirm = element("button", "danger-action", { type: "button" }, phrase ? "Confirm" : "Continue");
      var cancel = element("button", "secondary-action", { type: "button" }, "Cancel");
      if (phrase) confirm.disabled = true;
      if (input) {
        input.addEventListener("input", function () {
          confirm.disabled = input.value.trim() !== phrase;
        });
      }
      function done(value) {
        bar.hidden = true;
        clear(bar);
        resolve(value);
      }
      confirm.addEventListener("click", function () { done(true); });
      cancel.addEventListener("click", function () { done(false); });
      actions.appendChild(cancel);
      actions.appendChild(confirm);
      bar.appendChild(actions);
      (input || confirm).focus();
    });
  }

  // ── Action band ───────────────────────────────────────────────────────────────────────────
  //
  // A governed action is a first-class object (interaction model §2/§3.1): it names its target,
  // authority, reversibility, confirmation door and receipt. `renderReceipt` is the
  // `[data-action-receipt]` the parity gate checks.

  /**
   * Build one governed action chip. `opts`:
   *   verb, label, target, authority, path, method, body, reversible, phrase, confirm, after
   */
  function actionChip(opts) {
    var chip = element("button", "wb-action", {
      type: "button",
      "data-action": opts.verb,
      "data-action-target": opts.target || "none",
      "data-action-authority": opts.authority || "controller",
      "data-action-reversible": opts.reversible === false ? "false" : "true",
      "data-action-confirmation": opts.phrase || "none",
      title: opts.title || opts.label,
    }, opts.label);
    chip.addEventListener("click", function () {
      var gate = Promise.resolve(true);
      if (opts.phrase) gate = requestConfirm(opts.confirm || opts.label, opts.phrase);
      else if (opts.reversible === false) gate = requestConfirm(opts.confirm || opts.label);
      gate.then(function (ok) {
        if (!ok) return null;
        chip.disabled = true;
        // Client-only actions (attach/detach/copy) pass no path.
        if (!opts.path) {
          chip.disabled = false;
          if (opts.after) opts.after({ ok: true, status: 0, data: {} });
          return null;
        }
        return postJSON(opts.path, opts._body ? opts._body() : (opts.body || {})).then(function (result) {
          chip.disabled = false;
          renderReceipt(chip, result);
          if (opts.after) opts.after(result);
        });
      });
    });
    return chip;
  }

  /** Render the receipt of one action next to its chip (and keep the last one only). */
  function renderReceipt(chip, result) {
    var existing = chip.parentNode && chip.parentNode.querySelector("[data-action-receipt]");
    if (existing) existing.remove();
    var text = result.ok
      ? (result.data && (result.data.action || result.data.note || result.data.outcome)) || "recorded"
      : (result.data && result.data.error) || result.error || ("failed " + result.status);
    var receipt = element("span", "action-receipt", {
      "data-action-receipt": result.ok ? "recorded" : "failed",
      "data-receipt-status": String(result.status),
      role: "status",
    }, result.ok ? "recorded · " + text : "failed · " + text);
    chip.insertAdjacentElement("afterend", receipt);
  }

  // ── Generic key/value renderer (for provider-specific payloads) ───────────────────────────
  //
  // `subscription-usage`, `recording-audit`, and `routing` shapes are provider-specific; a
  // values-first recursive table renders any of them without inventing a schema, and never
  // silently drops a field. Object/array values collapse into a <details>.

  function renderKV(host, value) {
    if (value === null || value === undefined) { span(host, "kv-empty", "—"); return; }
    if (typeof value !== "object") { span(host, "kv-scalar", String(value)); return; }
    if (Array.isArray(value)) {
      if (!value.length) { span(host, "kv-empty", "(none)"); return; }
      value.forEach(function (item, index) {
        var row = element("div", "kv-row");
        span(row, "kv-key", "[" + index + "]");
        var val = element("div", "kv-val");
        renderKV(val, item);
        row.appendChild(val);
        host.appendChild(row);
      });
      return;
    }
    var keys = Object.keys(value);
    if (!keys.length) { span(host, "kv-empty", "(empty)"); return; }
    keys.forEach(function (key) {
      var item = value[key];
      var row = element("div", "kv-row");
      span(row, "kv-key", key);
      var val = element("div", "kv-val");
      if (item && typeof item === "object") {
        var details = element("details", "kv-details");
        details.appendChild(element("summary", null, null,
          Array.isArray(item) ? item.length + " items" : "object"));
        var inner = element("div", "kv-inner");
        renderKV(inner, item);
        details.appendChild(inner);
        val.appendChild(details);
      } else {
        val.textContent = item === null ? "null" : String(item);
      }
      row.appendChild(val);
      host.appendChild(row);
    });
  }

  /** A panel header with a title + optional refresh control. */
  function panelHeader(title, note) {
    var head = element("header", "panel-head");
    head.appendChild(element("h3", "panel-title", null, title));
    if (note) head.appendChild(element("span", "panel-note", null, note));
    return head;
  }

  /** Render a graceful panel-level state (loading / empty / error). */
  function panelState(host, kind, message) {
    clear(host);
    host.appendChild(element("p", "panel-state " + kind, { "data-panel-state": kind }, message));
  }

  // ── R4b: the selected worker's event stream + actions ─────────────────────────────────────

  //: The one open per-cell stream (the "exactly one selected event stream" invariant).
  var workerStream = null;
  var workerStreamCell = null;

  /** Close the selected worker stream, if any. Called on dock close and re-selection. */
  function closeWorkerStream() {
    if (workerStream) {
      try { workerStream.close(); } catch (_error) { /* already closed */ }
    }
    workerStream = null;
    workerStreamCell = null;
  }

  /** Set the visible stream state on the follow/pause toggle. */
  function setStreamState(state) {
    var toggle = document.getElementById("dock-stream-toggle");
    if (toggle) toggle.setAttribute("data-stream-state", state);
    var target = document.getElementById("dock-worker-target");
    if (target) target.setAttribute("data-stream-state", state);
  }

  /** Append one typed event row (same ADVISORY/MEASURED/SOURCE material as the row). */
  function appendWorkerEvent(event) {
    var list = document.getElementById("dock-event-feed");
    if (!list) return;
    var entry = normalizeEvent(event);
    list.appendChild(entry);
    while (list.children.length > 40) list.removeChild(list.firstChild);
    list.scrollTop = list.scrollHeight;
  }

  /**
   * Normalise a raw opencode event into a display row.
   *
   * The vocabulary matches the old transcript/client parser: step_start, step_finish, reasoning,
   * operator, text, tool_use/tool. A malformed/unknown event is still shown (with its raw type)
   * rather than dropped — an operator watching a stream values an unfamiliar frame over silence.
   */
  function normalizeEvent(raw) {
    var event = raw && typeof raw === "object" ? raw : {};
    var part = event.part && typeof event.part === "object" ? event.part : event;
    var type = String(event.type || part.type || "event").replace(/-/g, "_").toLowerCase();
    var detail = "";
    if (type === "step_finish") {
      var tokens = part.tokens && typeof part.tokens === "object" ? part.tokens : {};
      var cost = part.cost;
      var bits = [];
      if (typeof cost === "number") bits.push("$" + cost.toFixed(4));
      if (typeof tokens.input === "number") bits.push(tokens.input + " in");
      if (typeof tokens.output === "number") bits.push(tokens.output + " out");
      if (typeof tokens.reasoning === "number") bits.push(tokens.reasoning + " reason");
      detail = bits.join(" · ");
    } else if (type === "tool_use" || type === "tool") {
      var state = (part.state && part.state.status) || part.status || "observed";
      var name = part.name || part.tool || part.tool_name || "tool";
      detail = state + " · " + name;
    } else if (type === "text" || type === "reasoning") {
      detail = String(part.text || part.reasoning || event.text || "").slice(0, 240);
    } else if (type === "step_start") {
      detail = "step " + (part.step || part.name || "started");
    }
    var time = event.timestamp || part.timestamp || event.time || "";
    var row = element("li", "feed-entry", { "data-feed-entry": "", "data-event-kind": type });
    row.appendChild(element("span", "feed-time", null, formatTime(time)));
    row.appendChild(element("span", "feed-class", null, type.toUpperCase()));
    row.appendChild(element("span", "feed-text", null, detail || "—"));
    return row;
  }

  /** Format a producer timestamp, or an honest arrival marker (never a fabricated clock). */
  function formatTime(value) {
    if (value === undefined || value === null || value === "") return "now";
    var date = null;
    if (typeof value === "number") {
      date = new Date(value >= 1e11 ? value : value * 1000);
    } else {
      date = new Date(String(value));
    }
    if (isNaN(date.getTime())) return String(value).slice(0, 12);
    return date.toISOString().slice(11, 19);
  }

  /** Seed the feed from the run's typed facts so it is useful before any live event arrives. */
  function seedWorkerFeed(run) {
    var list = document.getElementById("dock-event-feed");
    if (!list) return;
    clear(list);
    var seeds = [
      ["lifecycle", "attempt " + (run["attempt.number"] || "?") + " · " + (run["model.provider"] || "model unknown")],
      ["advisory", "said " + (run["evidence.advisory"] || "unknown")],
      ["measured", "measured " + (run["evidence.measured"] || "unknown")],
      ["source", "commit " + String(run["source.commit"] || "unknown").replace(/^commit\s+/, "")],
      ["measured", "lease reserved " + (run["budget.reserved"] || "unknown") + " / cap " + (run["budget.cap"] || "unknown")],
    ];
    seeds.forEach(function (seed) {
      var entry = element("li", "feed-entry", { "data-feed-entry": "", "data-event-kind": seed[0] });
      entry.appendChild(element("span", "feed-time", null, "seed"));
      entry.appendChild(element("span", "feed-class", null, String(seed[0]).toUpperCase()));
      entry.appendChild(element("span", "feed-text", null, seed[1]));
      list.appendChild(entry);
    });
  }

  /**
   * Open `GET /api/events/<cell_id>` — the same endpoint and frame vocabulary the old room used.
   *
   * The stream is best-effort: under the render gate every non-glance `/api/*` request is
   * aborted, so `onerror` closes it and marks the state `unavailable` while the seeded typed
   * facts remain. That is the honest "could not observe" state, never an empty panel.
   */
  function openWorkerStream(cellId) {
    closeWorkerStream();
    seedWorkerFeed(currentRun || {});
    var toggle = document.getElementById("dock-stream-toggle");
    if (toggle) {
      toggle.disabled = false;
      toggle.textContent = "Pause";
      toggle.setAttribute("aria-pressed", "false");
    }
    if (!cellId || cellId === "unknown" || cellId === "none" || typeof window.EventSource !== "function") {
      setStreamState("unavailable");
      return;
    }
    try {
      var source = new window.EventSource("/api/events/" + encodeURIComponent(cellId));
      workerStream = source;
      workerStreamCell = cellId;
      setStreamState("connecting");
      source.addEventListener("replay_complete", function () { setStreamState("live"); });
      source.onmessage = function (message) {
        try { appendWorkerEvent(JSON.parse(message.data)); } catch (_error) { /* ignore frame */ }
      };
      source.onerror = function () {
        setStreamState("unavailable");
        try { source.close(); } catch (_error) { /* already closed */ }
        if (workerStream === source) workerStream = null;
      };
      // A stream with no boundary must not read as live forever.
      window.setTimeout(function () {
        if (workerStream === source) setStreamState("unavailable");
      }, 2000);
    } catch (_error) {
      setStreamState("unavailable");
    }
  }

  /** Best-effort cell id for the selected run: its spec cell, else the terminal target. */
  function cellIdFor(run) {
    var cell = run["spec.cell"];
    if (cell && cell !== "unknown" && cell !== "none") return String(cell);
    var target = String(run["terminal.target"] || "").replace(/^wt\//, "");
    if (target && target !== "unknown" && target !== "none") return target;
    return String(run["session.identity"] || "unknown");
  }

  // ── R4a address + R4d step timings ────────────────────────────────────────────────────────

  /** R4a: the identity/scope facts for the selected run. */
  function renderAddress(run) {
    var host = document.getElementById("dock-address-region");
    if (!host) return;
    clear(host);
    var facts = [
      ["session", run["session.identity"]],
      ["target", run["terminal.target"]],
      ["command", run["command.current"]],
      ["model", run["model.provider"]],
      ["attempt", run["attempt.number"]],
      ["spec/cell", run["spec.cell"]],
      ["phase", run["phase.progress"]],
      ["lifecycle", run["lifecycle.state"]],
      ["live", run["run.live"]],
      ["cost", run["cost.provenance"]],
      ["eligibility", run["decision.eligibility"]],
      ["receipt", run["decision.receipt"]],
    ];
    facts.forEach(function (fact) {
      var field = element("span", "dock-fact", { "data-dock-field": fact[0] });
      span(field, "dock-fact-key", fact[0]);
      span(field, "dock-fact-value", fact[1] === undefined || fact[1] === null ? "unknown" : fact[1]);
      host.appendChild(field);
    });
  }

  //: The canonical step-timing fields (interaction model §3.3). Order matters for the operator.
  var TIMING_FIELDS = [
    ["queue_wait", "queue wait"],
    ["service_time", "service time"],
    ["first_token", "first token"],
    ["duration", "duration"],
    ["retries", "retries"],
    ["tokens.in", "tokens in"],
    ["tokens.out", "tokens out"],
    ["tokens.answer", "tokens answer"],
    ["tokens.explanation", "tokens explanation"],
    ["cost", "cost"],
    ["exit_code", "exit code"],
    ["verification", "verification"],
  ];

  /**
   * R4d: one row per timing field with `[data-timing]` + `[data-state]`.
   *
   * Only fields the portal can actually observe are `measured`; the ledger's queue/service/
   * first-token fields are not exposed by any portal route, so they render as explicit
   * `unknown` rather than a fabricated 0 (interaction model §3.3; DP6).
   */
  function renderTimings(run, timingSample) {
    var host = document.getElementById("timing-grid");
    if (!host) return;
    clear(host);
    var values = {
      "queue_wait": ["unknown", "unknown"],
      "service_time": ["unknown", "unknown"],
      "first_token": ["unknown", "unknown"],
      "duration": ["unknown", "unknown"],
      "retries": [String(run["attempt.number"] || "1"), "measured"],
      "tokens.in": ["unknown", "unknown"],
      "tokens.out": ["unknown", "unknown"],
      "tokens.answer": ["unknown", "unknown"],
      "tokens.explanation": ["unknown", "unknown"],
      "cost": [run["budget.reserved"] || "unknown", run["budget.reserved"] ? "measured" : "unknown"],
      "exit_code": ["unknown", "unknown"],
      "verification": [run["evidence.measured"] || "unknown", "measured"],
    };
    if (timingSample) {
      // The retained matrix telemetry gives real per-step samples: tokens + cost are measured,
      // and the gap between consecutive sample timestamps is a genuine inter-step duration.
      if (timingSample.tokens_in !== undefined) values["tokens.in"] = [timingSample.tokens_in, "measured"];
      if (timingSample.tokens_out !== undefined) values["tokens.out"] = [timingSample.tokens_out, "measured"];
      if (timingSample.cost !== undefined) values["cost"] = [timingSample.cost, "measured"];
      if (timingSample.duration !== undefined) values["duration"] = [timingSample.duration, "measured"];
    }
    TIMING_FIELDS.forEach(function (spec) {
      var value = values[spec[0]] || ["unknown", "unknown"];
      var row = element("div", "timing-row", {
        "data-timing": spec[0],
        "data-state": value[1],
      });
      span(row, "timing-label", spec[1]);
      span(row, "timing-value", value[1] === "measured" ? String(value[0]) : "unknown");
      host.appendChild(row);
    });
  }

  /** Lazy enrichment: read `/api/matrix` telemetry for this cell and re-render the timings. */
  function loadTimingSample(run) {
    var cell = cellIdFor(run);
    if (!cell || cell === "unknown") return;
    getJSON("/api/matrix").then(function (result) {
      if (!result.ok || !currentRun) return;
      var telemetry = result.data && result.data.telemetry;
      var cells = (telemetry && telemetry.cells) || {};
      var sample = cells[cell];
      if (!sample || !Array.isArray(sample.samples) || !sample.samples.length) return;
      var step = sample.samples[0] || {};
      var duration = null;
      if (sample.samples.length > 1) {
        var a = new Date(sample.samples[0].timestamp || 0).getTime();
        var b = new Date(sample.samples[1].timestamp || 0).getTime();
        if (!isNaN(a) && !isNaN(b) && a > b) duration = ((a - b) / 1000).toFixed(1) + "s";
      }
      renderTimings(currentRun, {
        tokens_in: sample.input_tokens,
        tokens_out: sample.output_tokens,
        cost: step.cost,
        duration: duration,
      });
    });
  }

  // ── R4b action band ───────────────────────────────────────────────────────────────────────

  /** Build the governed action band for the selected run. */
  function renderActions(run) {
    var host = document.getElementById("dock-actions");
    if (!host) return;
    clear(host);
    var session = String(run["session.identity"] || "unknown");
    var cell = cellIdFor(run);
    var eligibility = String(run["decision.eligibility"] || "inspect");

    // The eligibility token is the at-rest governance answer (Move 3); it is not a button.
    host.appendChild(element("span", "action-eligibility", {
      "data-action-eligibility": eligibility,
      "data-action-authority": eligibility === "promote" ? "controller" : "aios",
    }, "eligibility: " + eligibility));

    // Client-only actions always exist: copy the typed session id, and attach/detach the stream.
    host.appendChild(actionChip({
      verb: "copy-session", label: "Copy session", target: session, authority: "aios",
      reversible: true,
      after: function () { copyText(session); },
    }));
    host.appendChild(actionChip({
      verb: "attach", label: "Reattach stream", target: cell, authority: "aios",
      reversible: true,
      after: function () { openWorkerStream(cell); },
    }));

    // The flag-backed actions are lazy: under the fixture gate `/api/flags` is aborted, so the
    // steer/interrupt chips appear only when a real flag actually maps to this session.
    getJSON("/api/flags?limit=50").then(function (result) {
      if (!result.ok || !currentRun) return;
      var flags = (result.data && result.data.flags) || [];
      var match = flags.filter(function (flag) {
        return flag.session_id === session
          || (flag.review && flag.review.cell_id === cell)
          || (flag.title && String(flag.title).indexOf(session) !== -1);
      })[0];
      if (!match) return;
      var cellId = (match.review && match.review.cell_id) || cell;
      host.appendChild(element("span", "action-flag-reason", null, "flag: " + (match.why || match.status || "")));
      host.appendChild(actionChip({
        verb: "steer", label: "Steer", target: match.session_id, authority: "aios",
        reversible: true, path: "/api/flags/" + encodeURIComponent(match.session_id) + "/steer",
        body: { cell_id: cellId, prompt: "operator steer from the Control Room" },
      }));
      host.appendChild(actionChip({
        verb: "interrupt", label: "Interrupt", target: match.session_id, authority: "aios",
        reversible: false, phrase: "INTERRUPT " + match.session_id,
        path: "/api/flags/" + encodeURIComponent(match.session_id) + "/interrupt",
        body: { cell_id: cellId, confirmation: "INTERRUPT " + match.session_id },
      }));
    });
  }

  /** Copy text to the clipboard, silently tolerant of insecure contexts. */
  function copyText(value) {
    try {
      if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(value);
    } catch (_error) { /* clipboard unavailable; the typed address is still on screen */ }
  }

  // ── The selected run (module state) ───────────────────────────────────────────────────────

  var currentRun = null;

  /** Render every R4 sub-region for the selected run; called by app.js `openDock`. */
  function renderDock(run, glance) {
    currentRun = run || null;
    if (!run) return;
    renderAddress(run);
    renderActions(run);
    renderTimings(run);
    openWorkerStream(cellIdFor(run));
    loadTimingSample(run);
  }

  /** Called by app.js `closeDock`. */
  function onDockClose() {
    closeWorkerStream();
    currentRun = null;
  }

  // ── Workbench panels ──────────────────────────────────────────────────────────────────────

  var currentPanel = null;

  //: Lazy-load state per panel, so reopening a panel does not refetch unless asked.
  var loaded = {};

  /** Fleet: the full roster from `/api/matrix`, with filters, search and density. */
  function loadFleet(host) {
    panelState(host, "loading", "Loading the fleet…");
    getJSON("/api/matrix").then(function (result) {
      if (!result.ok) { panelState(host, "error", "Fleet unavailable (HTTP " + result.status + ")"); return; }
      var data = result.data || {};
      var cells = data.cells || {};
      var phases = data.phases || {};
      var telemetry = (data.telemetry && data.telemetry.cells) || {};
      clear(host);
      host.appendChild(panelHeader("FLEET", (data.total || 0) + " cells · " + (data.running || 0) + " running"));

      var controls = element("div", "panel-controls");
      var search = element("input", "panel-input", { type: "search", placeholder: "Filter by cell id…",
        "aria-label": "Filter fleet by cell id", "data-fleet-search": "" });
      var state = "all";
      var tableBody = element("tbody", null);

      function renderRows() {
        clear(tableBody);
        var query = search.value.trim().toLowerCase();
        Object.keys(cells).filter(function (id) {
          if (query && id.toLowerCase().indexOf(query) === -1) return false;
          if (state === "live") return phases[id] && phases[id].live;
          if (state === "running") return cells[id] === "running" || cells[id] === "ended";
          if (state === "risk") return cells[id] === "failed" || cells[id] === "timeout";
          return true;
        }).sort().forEach(function (id) {
          var phase = phases[id] || {};
          var tel = telemetry[id] || {};
          var row = element("tr", null, { "data-cell-id": id });
          row.appendChild(element("td", null, null, id));
          row.appendChild(element("td", null, null, cells[id] || "unknown"));
          row.appendChild(element("td", null, null, phase.name ? phase.name + " " + (phase.index || "?")
            + "/" + (phase.total || "?") : "—"));
          row.appendChild(element("td", null, null, phase.age_seconds !== undefined
            && phase.age_seconds !== null ? ago(phase.age_seconds) : "unknown"));
          row.appendChild(element("td", null, null, tel.latest_cost === undefined || tel.latest_cost === null
            ? "unknown" : "$" + Number(tel.latest_cost).toFixed(4)));
          row.appendChild(element("td", null, null, tel.input_tokens === undefined || tel.input_tokens === null
            ? "unknown" : tel.input_tokens + "/" + (tel.output_tokens === null ? "?" : tel.output_tokens)));
          tableBody.appendChild(row);
        });
        if (!tableBody.children.length) {
          var empty = element("tr");
          empty.appendChild(element("td", null, { colspan: "6" }, "No cells match."));
          tableBody.appendChild(empty);
        }
      }

      var filter = element("select", "panel-select", { "aria-label": "Filter by state", "data-fleet-filter": "" });
      [["all", "All"], ["live", "Live"], ["running", "Running/ended"], ["risk", "Failed/timeout"]]
        .forEach(function (option) {
          filter.appendChild(element("option", null, { value: option[0] }, option[1]));
        });
      filter.addEventListener("change", function () { state = filter.value; renderRows(); });
      search.addEventListener("input", renderRows);
      var density = element("button", "wb-action", { type: "button", "data-action": "density-toggle",
        "data-action-target": "fleet", "data-action-authority": "aios", "data-action-reversible": "true",
        "data-action-confirmation": "none" }, "Density");
      density.addEventListener("click", function () { host.classList.toggle("panel-compact"); });

      controls.appendChild(search);
      controls.appendChild(filter);
      controls.appendChild(density);
      host.appendChild(controls);

      var table = element("table", "panel-table", { "data-fleet-table": "" });
      var thead = element("thead");
      var headRow = element("tr");
      ["CELL", "STATE", "PHASE", "AGE", "LATEST $", "TOK in/out"].forEach(function (label) {
        headRow.appendChild(element("th", null, null, label));
      });
      thead.appendChild(headRow);
      table.appendChild(thead);
      table.appendChild(tableBody);
      host.appendChild(table);
      renderRows();
    });
  }

  /** Attention: the full supervisor flag list from `/api/flags`. */
  function loadAttention(host) {
    panelState(host, "loading", "Loading supervisor flags…");
    getJSON("/api/flags?limit=50").then(function (result) {
      if (!result.ok) { panelState(host, "error", "Flags unavailable (HTTP " + result.status + ")"); return; }
      clear(host);
      var flags = (result.data && result.data.flags) || [];
      host.appendChild(panelHeader("ATTENTION", flags.length + " flags · source "
        + ((result.data && result.data.source) || "unknown")));
      if (!flags.length) { panelState(host, "empty", "No supervisor flags retained."); return; }
      var list = element("ul", "panel-list");
      flags.forEach(function (flag) {
        var item = element("li", "panel-item", { "data-flag-id": flag.session_id });
        item.appendChild(element("span", "item-title", null, flag.title || flag.session_id));
        item.appendChild(element("span", "item-meta", null,
          (flag.model || "model?") + " · " + (flag.status || "?") + " · "
          + (flag.last_activity_at ? ago((Date.now() - new Date(flag.last_activity_at).getTime()) / 1000) : "no activity")));
        item.appendChild(element("p", "item-why", null, flag.why || "no reason recorded"));
        var cellId = (flag.review && flag.review.cell_id) || flag.session_id;
        var actions = element("div", "item-actions");
        actions.appendChild(actionChip({
          verb: "steer", label: "Steer", target: flag.session_id, authority: "aios",
          reversible: true, path: "/api/flags/" + encodeURIComponent(flag.session_id) + "/steer",
          body: { cell_id: cellId, prompt: "operator steer from the Control Room" },
        }));
        actions.appendChild(actionChip({
          verb: "interrupt", label: "Interrupt", target: flag.session_id, authority: "aios",
          reversible: false, phrase: "INTERRUPT " + flag.session_id,
          path: "/api/flags/" + encodeURIComponent(flag.session_id) + "/interrupt",
          body: { cell_id: cellId, confirmation: "INTERRUPT " + flag.session_id },
          after: function () { loadAttention(host); },
        }));
        item.appendChild(actions);
        list.appendChild(item);
      });
      host.appendChild(list);
    });
  }

  /** Money: provider windows + wallet + the reserved-lease admission board. */
  function loadMoney(host, refresh) {
    panelState(host, "loading", "Loading subscription usage…");
    var path = "/api/subscription-usage" + (refresh ? "?refresh=1" : "");
    getJSON(path).then(function (result) {
      if (!result.ok) { panelState(host, "error", "Usage unavailable (HTTP " + result.status + ")"); return; }
      clear(host);
      host.appendChild(panelHeader("MONEY", "consumed + reserved (lease admission)"));
      var refreshBtn = element("button", "wb-action", { type: "button", "data-action": "refresh",
        "data-action-target": "money", "data-action-authority": "aios", "data-action-reversible": "true",
        "data-action-confirmation": "none" }, "Refresh usage");
      refreshBtn.addEventListener("click", function () { loadMoney(host, true); });
      host.appendChild(refreshBtn);
      var kv = element("div", "kv-table");
      renderKV(kv, result.data);
      host.appendChild(kv);
    });
  }

  /** Registry: canonical records + one-hop lineage. */
  function loadRegistry(host) {
    panelState(host, "loading", "Loading the registry…");
    getJSON("/api/registry").then(function (result) {
      if (!result.ok) { panelState(host, "error", "Registry unavailable (HTTP " + result.status + ")"); return; }
      clear(host);
      var rows = (result.data && result.data.registry) || [];
      host.appendChild(panelHeader("REGISTRY", rows.length + " canonical records"));
      if (!rows.length) { panelState(host, "empty", "No canonical records in the manifest."); return; }
      var table = element("table", "panel-table", { "data-registry-table": "" });
      var headRow = element("tr");
      ["ENTITY", "TYPE", "LIFECYCLE", "AUTHORITY", "OBSERVED"].forEach(function (label) {
        headRow.appendChild(element("th", null, null, label));
      });
      table.appendChild(element("thead", null, null)).appendChild(headRow);
      var body = element("tbody");
      rows.slice(0, 200).forEach(function (record) {
        var row = element("tr", null, { "data-entity-id": record.entity_id || "" });
        var entity = element("td");
        var link = element("button", "link-button", { type: "button", "data-lineage": record.entity_id || "" },
          (record.entity_id || "unknown").slice(0, 24));
        link.addEventListener("click", function () { showLineage(host, record.entity_id); });
        entity.appendChild(link);
        row.appendChild(entity);
        row.appendChild(element("td", null, null, record.source_type || "?"));
        row.appendChild(element("td", null, null, record.lifecycle_state || "?"));
        row.appendChild(element("td", null, null, record.authority || "?"));
        row.appendChild(element("td", null, null, String(record.observed_at || "").slice(0, 19) || "?"));
        body.appendChild(row);
      });
      table.appendChild(body);
      host.appendChild(table);
    });
  }

  /** Show one entity's lineage inline (one-hop; the route is file-only by design). */
  function showLineage(host, entityId) {
    if (!entityId) return;
    getJSON("/api/registry/" + encodeURIComponent(entityId)).then(function (result) {
      if (!result.ok) { panelState(host, "error", "Lineage unavailable (HTTP " + result.status + ")"); return; }
      clear(host);
      host.appendChild(panelHeader("LINEAGE", entityId));
      var back = element("button", "wb-action", { type: "button" }, "← Back to registry");
      back.addEventListener("click", function () { loadRegistry(host); });
      host.appendChild(back);
      var kv = element("div", "kv-table");
      renderKV(kv, result.data);
      host.appendChild(kv);
    });
  }

  /** Sessions: design sessions + background claude sessions with owned actions. */
  function loadSessions(host) {
    panelState(host, "loading", "Loading sessions…");
    Promise.all([getJSON("/api/design-sessions"), getJSON("/api/claude-agents"),
      getJSON("/api/claude-agents/daemon")]).then(function (results) {
      clear(host);
      host.appendChild(panelHeader("SESSIONS", "design + background claude"));
      renderDesignSessions(host, results[0]);
      renderClaudeAgents(host, results[1], results[2]);
    });
  }

  function renderDesignSessions(host, result) {
    var section = element("section", "panel-section", { "data-lens-section": "design" });
    section.appendChild(element("h4", "section-title", null, "DESIGN SESSIONS"));
    if (!result.ok) { section.appendChild(element("p", "panel-state error", null, "Design sessions unavailable.")); host.appendChild(section); return; }

    // A compact create form (re-houses `#design-start-form` + the launchers): kind + intent +
    // model + workdir, POSTed to the same `POST /api/design-sessions` route.
    var form = element("div", "panel-form");
    var kind = element("select", "panel-select", { "aria-label": "Design kind", "data-design-kind": "" });
    ["workflow", "experiment"].forEach(function (value) {
      kind.appendChild(element("option", null, { value: value }, value));
    });
    var intent = element("input", "panel-input", { type: "text", placeholder: "Feature goal…",
      "aria-label": "Design intent" });
    var model = element("input", "panel-input", { type: "text", placeholder: "model (optional)" });
    var workdir = element("input", "panel-input", { type: "text", placeholder: "approved workdir" });
    form.appendChild(kind);
    form.appendChild(intent);
    form.appendChild(model);
    form.appendChild(workdir);
    form.appendChild(actionChip({
      verb: "create", label: "New design session", target: "design", authority: "aios",
      reversible: true, path: "/api/design-sessions",
      body: {}, // replaced at click time below via a wrapper
      after: function () { loadSessions(host); },
      _body: function () { return { intent: intent.value, kind: kind.value, model: model.value,
        workdir: workdir.value }; },
    }));
    section.appendChild(form);

    var sessions = (result.data && result.data.sessions) || result.data || [];
    if (!Array.isArray(sessions) || !sessions.length) { section.appendChild(element("p", "panel-state empty", null, "No design sessions.")); host.appendChild(section); return; }
    var list = element("ul", "panel-list");
    sessions.forEach(function (session) {
      var id = session.portal_id || session.id;
      var item = element("li", "panel-item", { "data-design-id": id || "" });
      item.appendChild(element("span", "item-title", null, (session.kind || "design") + " · " + (id || "?")));
      item.appendChild(element("span", "item-meta", null,
        (session.model || "model?") + " · " + (session.workdir || session.workdir_key || "workdir?")));
      var actions = element("div", "item-actions");
      actions.appendChild(actionChip({
        verb: "interrupt", label: "Interrupt", target: id, authority: "aios", reversible: false,
        path: "/api/design-sessions/" + encodeURIComponent(id) + "/interrupt", body: {},
        after: function () { loadSessions(host); },
      }));
      actions.appendChild(actionChip({
        verb: "input", label: "Send", target: id, authority: "aios", reversible: true,
        path: "/api/design-sessions/" + encodeURIComponent(id) + "/input",
        body: { prompt: "continue", delivery: "queue" },
      }));
      actions.appendChild(actionChip({
        verb: "save", label: "Save spec", target: id, authority: "aios", reversible: true,
        path: "/api/design-sessions/" + encodeURIComponent(id) + "/save",
        body: { filename: String(session.draft_name || session.kind || "design") + ".yaml", overwrite: true },
        after: function () { loadSessions(host); },
      }));
      actions.appendChild(actionChip({
        verb: "run", label: "Run workflow", target: id, authority: "aios", reversible: false,
        confirm: "Run a workflow from this design session? This spends model budget.",
        path: "/api/design-sessions/" + encodeURIComponent(id) + "/run",
        body: { goal: "continue", model: session.model || "", workdir: session.workdir_key || session.workdir || "",
          timeout: 1800, commit: true, thinking_budget_tokens: 0, output_token_limit: 0 },
        after: function () { loadSessions(host); },
      }));
      item.appendChild(actions);
      list.appendChild(item);
    });
    section.appendChild(list);
    host.appendChild(section);
  }

  function renderClaudeAgents(host, result, daemon) {
    var section = element("section", "panel-section", { "data-lens-section": "claude" });
    section.appendChild(element("h4", "section-title", null, "CLAUDE SESSIONS"));
    var daemonData = daemon && daemon.ok ? daemon.data : {};
    section.appendChild(element("p", "item-meta", null, "daemon: "
      + (daemonData.running === undefined ? "unknown" : (daemonData.running ? "running pid " + (daemonData.pid || "?") : "stopped"))));
    var stopDaemon = actionChip({
      verb: "daemon-stop", label: "Stop daemon", target: "daemon", authority: "aios",
      reversible: false, path: "/api/claude-agents/daemon/stop", body: { keep_workers: true },
    });
    section.appendChild(stopDaemon);

    // A compact start form (re-houses `#claude-agent-start-form`): workdir + task + optional
    // model/advisor, POSTed to the same `POST /api/claude-agents` route.
    var startForm = element("div", "panel-form");
    var workdir = element("select", "panel-select", { "aria-label": "Approved workdir", "data-claude-workdir": "" });
    var workdirs = (result.data && result.data.workdirs) || [];
    (Array.isArray(workdirs) ? workdirs : Object.keys(workdirs)).forEach(function (entry) {
      var key = typeof entry === "string" ? entry : (entry.key || entry.value);
      var label = typeof entry === "string" ? entry : (entry.label || key);
      workdir.appendChild(element("option", null, { value: key }, label));
    });
    var task = element("input", "panel-input", { type: "text", placeholder: "Task prompt…",
      "aria-label": "Task prompt" });
    var model = element("input", "panel-input", { type: "text", placeholder: "model (optional)" });
    var advisor = element("select", "panel-select", { "aria-label": "Advisor (optional)" });
    advisor.appendChild(element("option", null, { value: "" }, "no advisor"));
    ["fable", "opus", "sonnet"].forEach(function (value) {
      advisor.appendChild(element("option", null, { value: value }, value));
    });
    startForm.appendChild(workdir);
    startForm.appendChild(task);
    startForm.appendChild(model);
    startForm.appendChild(advisor);
    startForm.appendChild(actionChip({
      verb: "start", label: "Start session", target: "claude", authority: "aios", reversible: true,
      path: "/api/claude-agents",
      _body: function () { return { workdir: workdir.value, task: task.value,
        model: model.value, advisor: advisor.value }; },
      after: function () { loadSessions(host); },
    }));
    section.appendChild(startForm);

    var agents = result.ok ? ((result.data && result.data.agents) || []) : [];
    if (!result.ok) { section.appendChild(element("p", "panel-state error", null, "Claude agents unavailable.")); host.appendChild(section); return; }
    if (!agents.length) { section.appendChild(element("p", "panel-state empty", null, "No background claude sessions.")); host.appendChild(section); return; }
    var list = element("ul", "panel-list");
    agents.forEach(function (agent) {
      var id = agent.id || agent.session_id;
      var owned = Boolean(agent.owned);
      var item = element("li", "panel-item", { "data-claude-id": id || "" });
      item.appendChild(element("span", "item-title", null, (owned ? "OWNED " : "EXTERNAL ") + (id || "?")));
      item.appendChild(element("span", "item-meta", null,
        (agent.status || "?") + " · " + (agent.model || "model?") + " · " + (agent.cwd || agent.workdir || "?")));
      var actions = element("div", "item-actions");
      if (owned) {
        actions.appendChild(actionChip({ verb: "stop", label: "Stop", target: id, authority: "aios",
          reversible: true, path: "/api/claude-agents/" + encodeURIComponent(id) + "/stop", body: {},
          after: function () { loadSessions(host); } }));
        actions.appendChild(actionChip({ verb: "respawn", label: "Respawn", target: id, authority: "aios",
          reversible: true, path: "/api/claude-agents/" + encodeURIComponent(id) + "/respawn", body: {},
          after: function () { loadSessions(host); } }));
        actions.appendChild(actionChip({ verb: "rm", label: "Rm", target: id, authority: "aios",
          reversible: false, path: "/api/claude-agents/" + encodeURIComponent(id) + "/rm", body: {},
          after: function () { loadSessions(host); } }));
        actions.appendChild(actionChip({ verb: "steer", label: "Steer", target: id, authority: "aios",
          reversible: true, path: "/api/claude-agents/" + encodeURIComponent(id) + "/steer",
          body: { prompt: "continue" }, after: function () { loadSessions(host); } }));
      } else {
        actions.appendChild(actionChip({ verb: "logs", label: "Fetch logs", target: id, authority: "aios",
          reversible: true, path: null, after: function () { loadAgentLogs(host, id); } }));
      }
      item.appendChild(actions);
      list.appendChild(item);
    });
    section.appendChild(list);
    var logHost = element("pre", "agent-log", { "data-claude-log": "" });
    section.appendChild(logHost);
    host.appendChild(section);
  }

  function loadAgentLogs(host, id) {
    getJSON("/api/claude-agents/" + encodeURIComponent(id) + "/logs").then(function (result) {
      var log = host.querySelector("[data-claude-log]");
      if (log) log.textContent = result.ok ? String(JSON.stringify(result.data, null, 2)).slice(0, 4000)
        : "logs unavailable (HTTP " + result.status + ")";
    });
  }

  /** Queue: enqueue / clear / reinterleave, with the queue depth from `/api/matrix`. */
  function loadQueue(host) {
    panelState(host, "loading", "Loading queue…");
    getJSON("/api/matrix").then(function (result) {
      clear(host);
      var data = result.ok ? result.data : {};
      host.appendChild(panelHeader("QUEUE", "queued " + (data.queued || 0) + " · done "
        + (data.done || 0) + " · failed " + (data.failed || 0)));
      var actions = element("div", "panel-actions");
      actions.appendChild(actionChip({ verb: "enqueue", label: "Enqueue", target: "story_jobs",
        authority: "controller", reversible: true, confirm: "Enqueue experiments? This spawns real inference spend.",
        path: "/api/experiments", body: { action: "enqueue" }, after: function () { loadQueue(host); } }));
      actions.appendChild(actionChip({ verb: "clear", label: "Clear queue", target: "story_jobs",
        authority: "controller", reversible: false, phrase: "CLEAR QUEUE",
        path: "/api/experiments", body: { action: "clear" }, after: function () { loadQueue(host); } }));
      actions.appendChild(actionChip({ verb: "reinterleave", label: "Reinterleave", target: "story_jobs",
        authority: "aios", reversible: true, path: "/api/queue/reinterleave", body: {},
        after: function (r) {
          var receipt = host.querySelector("[data-queue-receipt]");
          if (receipt) receipt.textContent = "before " + JSON.stringify(r.data.before || {})
            + " → after " + JSON.stringify(r.data.after || {});
        } }));
      host.appendChild(actions);
      host.appendChild(element("p", "item-meta", { "data-queue-receipt": "" }, ""));
    });
  }

  /** Routing: model/strategy recommendations (the re-housed routing board). */
  function loadRouting(host) {
    panelState(host, "loading", "Loading routing…");
    getJSON("/api/routing").then(function (result) {
      if (!result.ok) { panelState(host, "error", "Routing unavailable (HTTP " + result.status + ")"); return; }
      clear(host);
      host.appendChild(panelHeader("ROUTING", "recommendation inputs beside the run"));
      var kv = element("div", "kv-table");
      renderKV(kv, result.data);
      host.appendChild(kv);
    });
  }

  /** Docs health: the drift verdict + the controller remediation approval. */
  function loadDocs(host) {
    panelState(host, "loading", "Loading docs health…");
    getJSON("/api/docs-health").then(function (result) {
      if (!result.ok) { panelState(host, "error", "Docs health unavailable (HTTP " + result.status + ")"); return; }
      clear(host);
      var data = result.data || {};
      host.appendChild(panelHeader("DOCS HEALTH", data.condition || data.available === false
        ? "condition " + (data.condition || "unmeasured") : ""));
      var kv = element("div", "kv-table");
      renderKV(kv, data);
      host.appendChild(kv);
      var proposal = data.proposal || (data.docs_health && data.docs_health.proposal);
      if (proposal && (proposal.id || proposal.proposal_id)) {
        var form = element("div", "panel-form");
        form.appendChild(element("h4", "section-title", null, "CONTROLLER APPROVAL"));
        var by = element("input", "panel-input", { type: "text", placeholder: "signer (by)",
          "aria-label": "Signer", value: "controller" });
        var reason = element("input", "panel-input", { type: "text", placeholder: "reason (optional)",
          "aria-label": "Reason" });
        form.appendChild(by);
        form.appendChild(reason);
        form.appendChild(actionChip({
          verb: "approve", label: "Approve remediation", target: proposal.id || proposal.proposal_id,
          authority: "controller", reversible: false,
          confirm: "Approve and dispatch this docs remediation?",
          path: "/api/docs-health/approve",
          body: { proposal_id: proposal.id || proposal.proposal_id, by: by.value || "controller",
            reason: reason.value, dispatch: true },
          after: function () { loadDocs(host); },
        }));
        host.appendChild(form);
      }
    });
  }

  /** Recording audit: decision-record coverage + the one-click backfill sweep. */
  function loadAudit(host) {
    panelState(host, "loading", "Loading recording audit…");
    getJSON("/api/recording-audit").then(function (result) {
      if (!result.ok) { panelState(host, "error", "Recording audit unavailable (HTTP " + result.status + ")"); return; }
      clear(host);
      host.appendChild(panelHeader("RECORDING AUDIT", "decision-record coverage"));
      var kv = element("div", "kv-table");
      renderKV(kv, result.data);
      host.appendChild(kv);
      host.appendChild(actionChip({
        verb: "sweep", label: "Run recording sweep", target: "recording", authority: "controller",
        reversible: false, confirm: "Run the decision-record backfill sweep?",
        path: "/api/recording-sweep/run", body: {}, after: function () { loadAudit(host); },
      }));
    });
  }

  /** Health: per-projection watermark detail (`/api/projections`). */
  function loadHealth(host) {
    panelState(host, "loading", "Loading projections…");
    getJSON("/api/projections").then(function (result) {
      if (!result.ok) { panelState(host, "error", "Projections unavailable (HTTP " + result.status + ")"); return; }
      clear(host);
      var data = result.data || {};
      var rows = data.projections || data.report || (Array.isArray(data) ? data : []);
      host.appendChild(panelHeader("PROJECTIONS", rows.length + " consumer groups"));
      if (!rows.length) { panelState(host, "empty", "No projection report."); return; }
      var table = element("table", "panel-table", { "data-projection-table": "" });
      var headRow = element("tr");
      ["PROJECTION", "HEALTH", "LAG", "AGE", "LAST ERROR"].forEach(function (label) {
        headRow.appendChild(element("th", null, null, label));
      });
      table.appendChild(element("thead", null, null)).appendChild(headRow);
      var body = element("tbody");
      rows.forEach(function (row) {
        var tr = element("tr", null, { "data-projection": row.projection || "" });
        tr.appendChild(element("td", null, null, row.projection || "?"));
        tr.appendChild(element("td", null, { "data-health": row.health || "unknown" }, row.health || "unknown"));
        tr.appendChild(element("td", null, null, row.lag_events === null || row.lag_events === undefined
          ? "unknown" : row.lag_events));
        tr.appendChild(element("td", null, null, ago(row.age_seconds)));
        tr.appendChild(element("td", null, null, row.last_error || "—"));
        body.appendChild(tr);
      });
      table.appendChild(body);
      host.appendChild(table);
    });
  }

  /**
   * Workforce step timings: aggregate the retained matrix telemetry by cell.
   *
   * The portal does not expose the ledger's queue_wait/service_time fields, so this panel shows
   * what IS observable — step count, cost, tokens, last activity, and the median gap between
   * consecutive step timestamps — and labels the unobservable fields `unknown` rather than
   * inventing a number (interaction model §3.3; DP6).
   */
  function loadWorkforce(host) {
    panelState(host, "loading", "Aggregating workforce step timings…");
    getJSON("/api/matrix").then(function (result) {
      if (!result.ok) { panelState(host, "error", "Workforce timings unavailable (HTTP " + result.status + ")"); return; }
      clear(host);
      var telemetry = (result.data && result.data.telemetry && result.data.telemetry.cells) || {};
      var cells = (result.data && result.data.cells) || {};
      host.appendChild(panelHeader("WORKFORCE STEP TIMINGS", "retained telemetry · gaps are "
        + "measured; queue/service/first-token are not exposed and render unknown"));
      var table = element("table", "panel-table", { "data-workforce-table": "" });
      var headRow = element("tr");
      ["CELL", "STEPS", "$ TOTAL", "TOK in/out", "MED GAP", "LAST STEP"].forEach(function (label) {
        headRow.appendChild(element("th", null, null, label));
      });
      table.appendChild(element("thead", null, null)).appendChild(headRow);
      var body = element("tbody");
      var ids = Object.keys(telemetry);
      if (!ids.length) {
        panelState(host, "empty", "No retained step telemetry yet.");
        host.appendChild(table);
        return;
      }
      ids.forEach(function (id) {
        var tel = telemetry[id] || {};
        var samples = Array.isArray(tel.samples) ? tel.samples : [];
        var gaps = [];
        for (var i = 0; i + 1 < samples.length; i += 1) {
          var a = new Date(samples[i].timestamp || 0).getTime();
          var b = new Date(samples[i + 1].timestamp || 0).getTime();
          if (!isNaN(a) && !isNaN(b) && a >= b) gaps.push((a - b) / 1000);
        }
        gaps.sort(function (x, y) { return x - y; });
        var median = gaps.length ? gaps[Math.floor(gaps.length / 2)].toFixed(1) + "s" : "unknown";
        var row = element("tr", null, { "data-cell-id": id });
        row.appendChild(element("td", null, null, id));
        row.appendChild(element("td", null, { "data-timing": "steps",
          "data-state": samples.length ? "measured" : "unknown" }, String(samples.length)));
        row.appendChild(element("td", null, { "data-timing": "cost",
          "data-state": tel.reported_cost === null || tel.reported_cost === undefined ? "unknown" : "measured" },
          tel.reported_cost === null || tel.reported_cost === undefined ? "unknown" : "$" + Number(tel.reported_cost).toFixed(4)));
        row.appendChild(element("td", null, null, (tel.input_tokens === null || tel.input_tokens === undefined
          ? "unknown" : tel.input_tokens) + "/" + (tel.output_tokens === null || tel.output_tokens === undefined
          ? "unknown" : tel.output_tokens)));
        row.appendChild(element("td", null, { "data-timing": "step_gap",
          "data-state": gaps.length ? "measured" : "unknown" }, median));
        row.appendChild(element("td", null, null, samples.length && samples[0].timestamp
          ? formatTime(samples[0].timestamp) : "unknown"));
        body.appendChild(row);
      });
      table.appendChild(body);
      host.appendChild(table);
      host.appendChild(element("p", "item-meta", null, "cells tracked: " + Object.keys(cells).length));
    });
  }

  // ── Step-11/12 read views: Operations + Surfaces (re-housed from main) ────────────────────
  //
  // These lenses keep the destination boards main added after the facelift branched — the
  // operational packet + run detail (`/api/operations`, `/api/runs/<run_id>`) and the
  // step-5/6/7 read models (`/api/quality`, `/api/stories/<name>/arc`, `/api/value`,
  // `/api/arms/compare`, `/api/queue/sla`, `/api/escalations`, `/api/batch`, `/api/energy`) —
  // inside the refreshed presentation. Every value renders as the payload returned it: a named
  // `unavailable`/scenario state stays verbatim (never a fabricated 0 or an all-clear), and the
  // batch lane keeps its "not measurable" label until a batch transport actually exists.

  /** Render a payload value (including its state blocks) without inventing one. */
  function stateText(value) {
    if (value === null || value === undefined) return "—";
    if (typeof value === "object") {
      if (value.state) return value.state + (value.reason ? " — " + value.reason : "");
      return "—";
    }
    return String(value);
  }

  /** A data table; rows can carry a run id for the click-through run detail. */
  function table(captionText, headers, rows, opts) {
    opts = opts || {};
    var wrap = element("div", "table-scroll");
    var node = element("table", "routing-table panel-table");
    node.appendChild(element("caption", "sr-only", null, captionText));
    var thead = element("thead");
    var headRow = element("tr");
    headers.forEach(function (header) { headRow.appendChild(element("th", null, null, header)); });
    thead.appendChild(headRow);
    node.appendChild(thead);
    var tbody = element("tbody");
    (rows || []).forEach(function (cells, index) {
      var tr = element("tr");
      var runId = opts.runIds ? opts.runIds[index] : null;
      if (runId) {
        tr.setAttribute("data-run-id", runId);
        tr.className = "clickable";
        tr.setAttribute("tabindex", "0");
        tr.setAttribute("role", "button");
        tr.setAttribute("aria-label", "Open run " + runId + " detail");
      }
      cells.forEach(function (value) { tr.appendChild(element("td", null, null, stateText(value))); });
      tbody.appendChild(tr);
    });
    node.appendChild(tbody);
    wrap.appendChild(node);
    return wrap;
  }

  function note(text) { return element("p", "panel-note", null, text); }

  /** A relative age for a producer timestamp, or an honest unknown. */
  function ageText(value) {
    if (!value) return "—";
    var then = new Date(value).getTime();
    if (isNaN(then)) return String(value);
    return ago((Date.now() - then) / 1000);
  }

  var RUN_HEADERS = ["Run", "Spec", "State", "Phases", "Model", "Candidate", "Started"];

  function runRow(entry) {
    var progress = entry.phases_completed === undefined && entry.phases_total === undefined
      ? "—" : (entry.phases_completed || 0) + "/" + (entry.phases_total || 0);
    return [entry.run_id, entry.spec_name, entry.state, progress, entry.model,
      entry.candidate_sha ? String(entry.candidate_sha).slice(0, 12) : "—",
      entry.started_at ? ageText(entry.started_at) : "—"];
  }

  /** A titled block inside the operations lens. */
  function sectionBlock(title, body) {
    var block = element("section", "panel-section surface-block");
    block.appendChild(element("h4", "section-title", null, title));
    block.appendChild(body);
    return block;
  }

  /** Operations lens: the packet-derived snapshot + click-through per-run detail. */
  function loadOperations(host) {
    panelState(host, "loading", "Loading operations…");
    getJSON("/api/operations").then(function (result) {
      if (!result.ok) {
        panelState(host, "error", "Operations unavailable (HTTP " + result.status + ")");
        return;
      }
      clear(host);
      host.appendChild(panelHeader("OPERATIONS", "the one packet · run detail on click"));
      renderOperations(host, result.data || {});
    });
  }

  function renderOperations(host, data) {
    var source = data.source || {};
    var active = data.active_runs || [];
    var promotable = data.promotable_runs || [];
    var attention = data.attention || [];
    var degraded = data.degraded || [];
    var lag = data.projection_lag || {};
    // A degraded control DB means every count derived from it reads "unavailable", never 0.
    var dbDegraded = degraded.some(function (entry) { return entry.surface === "control_db"; });

    var summary = element("div", "kv-table");
    [
      ["Control epoch", String(source.control_epoch || "—")],
      ["Repo head", String(source.repo_head_sha || "—").slice(0, 9)],
      ["Active runs", dbDegraded ? "unavailable" : String(active.length)],
      ["Decisions owed", dbDegraded ? "unavailable" : String(attention.length)],
      ["Promotable runs", dbDegraded ? "unavailable" : String(promotable.length)],
      ["Unhealthy workers", String((data.unhealthy_workers || []).length)],
    ].forEach(function (pair) {
      var row = element("div", "kv-row");
      span(row, "kv-key", pair[0]);
      row.appendChild(element("div", "kv-val", null, pair[1]));
      summary.appendChild(row);
    });
    host.appendChild(summary);

    if (degraded.length) {
      host.appendChild(sectionBlock("DEGRADED SURFACES", table("Degraded surfaces",
        ["Surface", "Reason"], degraded.map(function (e) { return [e.surface, e.reason]; }))));
    }

    host.appendChild(sectionBlock("ATTENTION", attention.length ? table(
      "Attention (decisions owed)",
      ["Kind", "Run", "Spec", "Gate", "Candidate", "Purpose"],
      attention.map(function (e) {
        return [e.kind, e.run_id, e.spec_name, e.gate_id || "(run)",
          e.candidate_sha ? String(e.candidate_sha).slice(0, 12) : "—",
          e.purpose || e.reason || "—"];
      }),
      { runIds: attention.map(function (e) { return e.run_id; }) })
      : note(dbDegraded
        ? "The control database could not be read — decisions owed cannot be listed."
        : "No decisions owed.")));

    var safe = data.safe_actions || [];
    host.appendChild(sectionBlock("SAFE ACTIONS", safe.length ? table(
      "Safe actions (from the enforced transition graph)",
      ["Action", "Run", "Candidate", "Gate"],
      safe.map(function (e) {
        return [e.action, e.run_id || "—",
          e.candidate_sha ? String(e.candidate_sha).slice(0, 12) : "—", e.gate_id || "—"];
      }),
      { runIds: safe.map(function (e) { return e.run_id || null; }) })
      : note(dbDegraded
        ? "The control database could not be read — safe actions cannot be derived."
        : "No safe actions offered.")));

    var runs = active.concat(promotable);
    host.appendChild(sectionBlock("ACTIVE + PROMOTABLE RUNS", runs.length ? table(
      "Active and promotable runs", RUN_HEADERS, runs.map(runRow),
      { runIds: runs.map(function (e) { return e.run_id; }) })
      : note(dbDegraded
        ? "The control database could not be read — active runs cannot be listed."
        : "No active or promotable runs.")));

    var lagRows = Object.keys(lag).map(function (key) { return [key, stateText(lag[key])]; });
    host.appendChild(sectionBlock("PROJECTION LAG", lagRows.length
      ? table("Projection lag", ["Projection", "Unconfirmed events"], lagRows)
      : note("No projection watermarks reported.")));

    // The run-detail drawer: a click on any run row fetches /api/runs/<id>. A named error
    // (unreadable/incomplete read) renders by name, never as a blank detail.
    var drawer = element("section", "run-detail-drawer", { id: "run-detail-drawer", hidden: true });
    var dhead = element("header", "drawer-header");
    dhead.appendChild(element("h3", "panel-title", { id: "run-detail-title" }, "RUN DETAIL"));
    var dclose = element("button", "icon-button",
      { type: "button", "aria-label": "Close run detail" }, "✕");
    dhead.appendChild(dclose);
    drawer.appendChild(dhead);
    var detailContent = element("div", "run-detail-content", { id: "run-detail-content" });
    drawer.appendChild(detailContent);
    host.appendChild(drawer);
    dclose.addEventListener("click", function () { drawer.hidden = true; clear(detailContent); });
    function activate(event) {
      var row = event.target.closest("tr[data-run-id]");
      if (!row) return;
      if (event.type === "keydown") {
        if (event.key !== "Enter" && event.key !== " ") return;
        event.preventDefault();
      }
      openRunDetail(row.getAttribute("data-run-id"), drawer, detailContent);
    }
    host.addEventListener("click", activate);
    host.addEventListener("keydown", activate);
  }

  function openRunDetail(runId, drawer, content) {
    if (!runId) return;
    drawer.hidden = false;
    clear(content);
    content.appendChild(note("Loading run detail…"));
    getJSON("/api/runs/" + encodeURIComponent(runId)).then(function (result) {
      clear(content);
      if (!result.ok) {
        content.appendChild(note("Run detail unavailable (HTTP " + result.status + ")"));
        return;
      }
      if (result.data && result.data.error) {
        content.appendChild(note("Run detail unavailable: " + result.data.error));
        return;
      }
      renderRunDetail(content, result.data || {});
    });
  }

  /** A generic object table over whatever keys the control record actually carries. */
  function objectTable(captionText, rows, preferredKeys) {
    if (!rows || !rows.length) return note("None recorded.");
    var keys = preferredKeys.filter(function (key) {
      return rows.some(function (row) { return key in row; });
    });
    var extra = [];
    rows.forEach(function (row) {
      Object.keys(row).forEach(function (key) {
        if (keys.indexOf(key) === -1 && key.slice(-5) !== "_json" && extra.indexOf(key) === -1) {
          extra.push(key);
        }
      });
    });
    var headers = keys.concat(extra);
    return table(captionText, headers, rows.map(function (row) {
      return headers.map(function (key) { return row[key]; });
    }));
  }

  function renderRunDetail(content, data) {
    var run = data.run || {};
    var identity = element("div", "kv-table");
    [
      ["Spec", run.spec_name || "—"], ["State", run.state || "—"], ["Model", run.model || "—"],
      ["Candidate", run.candidate_sha ? String(run.candidate_sha).slice(0, 12) : "—"],
      ["Started", run.started_at ? ageText(run.started_at) : "—"],
      ["Cost", run.cost_usd === null || run.cost_usd === undefined
        ? "unavailable" : "$" + Number(run.cost_usd).toFixed(4)],
    ].forEach(function (pair) {
      var row = element("div", "kv-row");
      span(row, "kv-key", pair[0]);
      row.appendChild(element("div", "kv-val", null, pair[1]));
      identity.appendChild(row);
    });
    content.appendChild(identity);
    content.appendChild(sectionBlock("ATTEMPTS", objectTable("Attempts", data.attempts || [],
      ["attempt_number", "phase", "model", "status", "first_pass", "accepted", "retry_reason",
        "escalation_from", "escalation_to", "cost_usd"])));
    content.appendChild(sectionBlock("GATES", objectTable("Gates", data.gates || [],
      ["gate_id", "candidate_sha", "status", "verdict", "created_at"])));
    content.appendChild(sectionBlock("APPROVALS", objectTable("Approvals", data.approvals || [],
      ["gate_id", "candidate_sha", "purpose", "operator", "created_at"])));
    content.appendChild(sectionBlock("COMMAND JOURNAL", objectTable("Command journal", data.commands || [],
      ["verb", "state", "actor", "rationale", "candidate_sha", "created_at"])));
  }

  //: The step-6/7 read models, one panel each (the batch lane is `renderBatchPanel`).
  var SURFACE_ROUTES = [
    ["quality", "/api/quality"],
    ["value", "/api/value"],
    ["arms", "/api/arms/compare"],
    ["sla", "/api/queue/sla"],
    ["escalations", "/api/escalations"],
    ["batch", "/api/batch"],
    ["energy", "/api/energy"],
  ];

  /** Surfaces lens: every read model independent; a failed fetch renders its own state. */
  function loadSurfaces(host) {
    panelState(host, "loading", "Loading surfaces…");
    Promise.all(SURFACE_ROUTES.map(function (pair) { return getJSON(pair[1]); }))
      .then(function (results) {
        clear(host);
        host.appendChild(panelHeader("SURFACES", "step-5/6/7 read models · states rendered verbatim"));
        var grid = element("div", "surface-grid");
        SURFACE_ROUTES.forEach(function (pair, index) {
          var result = results[index];
          grid.appendChild(result.ok
            ? renderSurfacePanel(pair[0], result.data || {})
            : surfacePanel(pair[0], pair[0].toUpperCase(),
                "unavailable — HTTP " + result.status + " (" + pair[1] + ")"));
        });
        grid.appendChild(renderStoryArcPanel(null));
        host.appendChild(grid);
      });
  }

  function surfacePanel(name, title, body) {
    var panel = element("section", "surface-panel", { "data-surface": name });
    panel.appendChild(element("h3", null, null, title));
    if (typeof body === "string") panel.appendChild(note(body));
    else if (body) panel.appendChild(body);
    return panel;
  }

  function renderSurfacePanel(name, data) {
    switch (name) {
      case "quality": return renderQualityPanel(data);
      case "value": return renderValuePanel(data);
      case "arms": return renderArmsPanel(data);
      case "sla": return renderSlaPanel(data);
      case "escalations": return renderEscalationPanel(data);
      case "batch": return renderBatchPanel(data);
      case "energy": return renderEnergyPanel(data);
      default: return surfacePanel(name, name.toUpperCase(), stateText(data));
    }
  }

  /** Grit — the one formal definition — per model, with its coverage beside it. */
  function renderQualityPanel(data) {
    var body = element("div");
    var population = data.population || {};
    var excluded = Object.keys(population.exclusions || {}).map(function (key) {
      return key + "=" + population.exclusions[key];
    }).join(", ");
    body.appendChild(note("cells " + (population.eligible_cells === undefined ? "—"
      : population.eligible_cells) + "/" + (population.resolved_cells === undefined ? "—"
      : population.resolved_cells) + " eligible" + (excluded ? " (excluded: " + excluded + ")" : "")));
    var rows = (data.models || []).map(function (model) {
      var grit = (model.grit && model.grit.overall) || {};
      var first = model.first_pass || {};
      var narration = model.narration || {};
      var gritty = grit.grit === null || grit.grit === undefined
        ? (grit.insufficient_support ? "insufficient support" : "—")
        : grit.grit + " (n=" + grit.n + (grit.insufficient_support ? ", low" : "") + ")";
      return [model.model, gritty, stateText(first.first_pass_rate), stateText(first.accepted_rate),
        stateText(narration.explanation_ratio),
        (first.n_eligible === undefined ? "—" : first.n_eligible) + "/"
          + (first.n_total === undefined ? "—" : first.n_total) + " attempts"];
    });
    body.appendChild(table("Model quality",
      ["Model", "Grit", "First-pass", "Accepted", "Explanation ratio", "First-pass coverage"], rows));
    if ((data.degraded || []).length) {
      body.appendChild(note("degraded: " + data.degraded.map(function (d) { return d.surface; }).join(", ")));
    }
    return surfacePanel("quality", "MODEL QUALITY (rules 1/2/5)", body);
  }

  /** observed-only value: accepted outcomes and cost per accepted outcome, verbatim. */
  function renderValuePanel(data) {
    var body = element("div");
    body.appendChild(note(data.formula || ""));
    body.appendChild(note("BVI: " + stateText(data.bvi)));
    body.appendChild(table("Observed value",
      ["Run", "Arm", "Accepted", "Total cost", "Cost / accepted", "Cost coverage"],
      (data.rows || []).map(function (row) {
        return [row.run, row.arm, row.accepted_outcomes, row.total_cost_usd,
          row.cost_per_accepted === undefined
            ? (row.cost_per_accepted_reason || "—") : row.cost_per_accepted,
          row.cost_captured_records + "/" + row.outcomes_total + " costs"];
      })));
    return surfacePanel("value", "RUN VALUE (rule 10, observed-only)", body);
  }

  /** the compare/adapt ranking, exactly as compare_arms returned it. */
  function renderArmsPanel(data) {
    var body = element("div");
    var comparison = data.comparison || {};
    body.appendChild(note((data.state || "—")
      + (data.state_reason ? " — " + data.state_reason : "")
      + " · best: " + (comparison.best_arm === undefined ? "—" : comparison.best_arm)
      + " · n=" + (data.n_outcomes === undefined ? 0 : data.n_outcomes)));
    var rows = Object.keys(comparison.arms || {}).map(function (arm) {
      var stats = comparison.arms[arm];
      var coverage = stats.coverage || {};
      return [arm, stats.n, stats.eligible === false ? "no" : "yes",
        stats.weighted_loss === undefined
          ? (stats.missing_objectives ? "missing " + stats.missing_objectives.join(",") : "—")
          : stats.weighted_loss,
        coverage.cost ? coverage.cost.n + "/" + coverage.cost.of : "—"];
    });
    body.appendChild(table("Arms", ["Arm", "n", "Eligible", "Weighted loss", "Cost coverage"], rows));
    return surfacePanel("arms", "ARM COMPARISON (P6)", body);
  }

  /** queue depth, burn, the breach value and the settled completions. */
  function renderSlaPanel(data) {
    var body = element("div");
    if ((data.degraded || []).length) {
      body.appendChild(note("degraded: " + data.degraded.map(function (entry) {
        return entry.surface + " — " + entry.reason;
      }).join("; ")));
    }
    var queue = data.queue || {};
    var burn = data.burn || {};
    var sla = data.sla || {};
    body.appendChild(note("depth " + (queue.depth === undefined ? "—" : queue.depth)
      + " · burn " + stateText(burn.burn_per_h) + "/h over " + stateText(burn.span_h)
      + "h · horizon " + stateText(sla.horizon)));
    var breach = sla.breach_rate || {};
    body.appendChild(note("breach: " + (breach.state === "measured"
      ? "timeouts " + breach.value.timeout_breaches + "/" + breach.value.total_phases_with_breach_fields
        + ", gates " + breach.value.gate_breaches
      : stateText(breach))));
    body.appendChild(note("2× rule: "
      + stateText(sla.twice_depth_rule && sla.twice_depth_rule.threshold_jobs) + " jobs ("
      + ((sla.twice_depth_rule && sla.twice_depth_rule.basis) || "—") + ")"));
    var completions = (data.recent_completions && data.recent_completions.rows) || [];
    body.appendChild(table("Recent completions",
      ["Cell", "Status", "Queue wait (ms)", "Service (ms)", "Deadline slack (ms)"],
      completions.slice(0, 10).map(function (row) {
        return [row.cell_id, row.status, row.queue_wait_ms === undefined ? "—" : row.queue_wait_ms,
          row.service_time_ms === undefined ? "—" : row.service_time_ms,
          row.deadline_slack_ms === undefined ? "—" : row.deadline_slack_ms];
      })));
    return surfacePanel("sla", "QUEUE / SLA (rule 9)", body);
  }

  /** the cascade surface: recorded events only, the armed flag, and E_x labeled. */
  function renderEscalationPanel(data) {
    var body = element("div");
    body.appendChild(note("armed: " + (data.armed === true ? "yes" : "no")
      + (data.armed_note ? " — " + data.armed_note : "")));
    body.appendChild(table("Escalation events", ["From", "To", "Reason", "Cost"],
      (data.events || []).map(function (event) {
        return [event.from, event.to, event.reason || "—",
          event.cost_usd === undefined ? "—" : event.cost_usd];
      })));
    body.appendChild(note("E_x: " + stateText(data.e_x) + " (" + ((data.e_x && data.e_x.class) || "—") + ")"));
    return surfacePanel("escalations", "ESCALATION CASCADE (rule 8)", body);
  }

  /** explicitly not-measurable until a batch transport exists; the scenario is labeled. */
  function renderBatchPanel(data) {
    var body = element("div");
    if ((data.degraded || []).length) {
      body.appendChild(note("degraded: " + data.degraded.map(function (entry) {
        return entry.surface + " — " + entry.reason;
      }).join("; ")));
    }
    body.appendChild(note(data.measurable
      ? "batch fraction " + data.batch_fraction + " (" + data.batch_jobs + "/" + data.marked_jobs + ")"
      : "not measurable — " + (data.reason || "no marker")
        + " (scanned " + (data.scanned_jobs === undefined ? 0 : data.scanned_jobs) + " jobs)"));
    var modeled = data.modeled || {};
    body.appendChild(note("modeled scenario: discount " + modeled.discount
      + " / horizon " + modeled.horizon_h + "h · class " + (modeled.class || "—")));
    return surfacePanel("batch", "BATCH DISCOUNT (rule 6)", body);
  }

  /** energy/EPM: external + modeled sources labeled; the measured gap named. */
  function renderEnergyPanel(data) {
    var body = element("div");
    var model = data.energy_model || {};
    body.appendChild(note("model: " + model.per_prompt_token_j + " J/prompt · "
      + model.per_output_token_j + " J/output · " + model.per_reasoning_token_j
      + " J/reasoning (" + (model.class || "—") + ")"));
    var epm = data.epm || {};
    body.appendChild(note(epm.state === "published"
      ? "EPM: " + ((epm.baseline && epm.baseline.value) === undefined ? "—" : epm.baseline.value)
        + " baseline / " + ((epm.aggressive && epm.aggressive.value) === undefined ? "—" : epm.aggressive.value)
        + " aggressive (" + epm.class + ")"
      : "EPM: " + stateText(epm)));
    var ranking = data.energy_ranking || {};
    var models = Array.isArray(ranking.models) ? ranking.models : [];
    body.appendChild(table("Energy ranking", ["Model", "Avg energy (J)", "J per LOC"],
      models.slice(0, 8).map(function (row) {
        return [row.id || row.model || "—",
          row.avg_energy_j === undefined ? "—" : row.avg_energy_j,
          row.avg_energy_j_per_loc === undefined ? "—" : row.avg_energy_j_per_loc];
      })));
    body.appendChild(note("measured session energy: " + stateText(data.measured_session_energy)));
    body.appendChild(note("flip horizon: " + stateText(data.flip_horizon)));
    return surfacePanel("energy", "ENERGY / EPM (rule 4)", body);
  }

  /** the story arc panel: a name input + the fetched arc, or explicit guidance. */
  function renderStoryArcPanel(data, name) {
    var panel = element("section", "surface-panel", { "data-surface": "story-arc" });
    panel.appendChild(element("h3", null, null, "STORY ARC (rule 3)"));
    var controls = element("div", "surface-controls");
    var input = element("input", "surface-input",
      { type: "text", id: "story-arc-name", placeholder: "story_id or story_name", value: name || "" });
    var button = element("button", null, { type: "button", "data-story-arc-load": "true" }, "Load arc");
    button.addEventListener("click", loadStoryArc);
    input.addEventListener("keydown", function (event) {
      if (event.key === "Enter") { event.preventDefault(); loadStoryArc(); }
    });
    controls.appendChild(input);
    controls.appendChild(button);
    panel.appendChild(controls);
    var body = element("div", null, { id: "story-arc-body" });
    body.appendChild(note(data ? "" : "Enter a story_id or story_name and load its arc."));
    if (data) renderStoryArcBody(data);
    panel.appendChild(body);
    return panel;
  }

  function renderStoryArcBody(data) {
    var body = document.getElementById("story-arc-body");
    if (!body) return;
    clear(body);
    if (data === null) { body.appendChild(note("Story not found.")); return; }
    body.appendChild(note(data.matched_by + " · " + data.stories_matched + " story(ies) · snowball "
      + stateText(data.snowball_factor) + " · velocity " + stateText(data.velocity) + " · β "
      + stateText(data.beta && data.beta.value) + " (" + ((data.beta && data.beta.class) || "—") + ")"));
    body.appendChild(table("Sessions", ["Session", "Cost", "Code lines", "n"],
      (data.sessions || []).map(function (row) {
        return [row.session_number, stateText(row.cost_usd),
          row.code_lines === undefined ? "—" : row.code_lines, row.n];
      })));
    if (data.snowball_reason) body.appendChild(note(data.snowball_reason));
  }

  function loadStoryArc() {
    var input = document.getElementById("story-arc-name");
    var name = (input && input.value.trim()) || "";
    var body = document.getElementById("story-arc-body");
    if (!name) {
      if (body) { clear(body); body.appendChild(note("Enter a story_id or story_name first.")); }
      return;
    }
    if (body) { clear(body); body.appendChild(note("Loading " + name + "…")); }
    getJSON("/api/stories/" + encodeURIComponent(name) + "/arc").then(function (result) {
      if (result.status === 404) { renderStoryArcBody(null); return; }
      if (!result.ok) {
        if (body) { clear(body); body.appendChild(note("Arc unavailable (HTTP " + result.status + ")")); }
        return;
      }
      renderStoryArcBody(result.data || {});
    });
  }

  //: The workbench registry: order = nav order; `load(host)` is called the first time the panel
  //: is shown (and by an explicit refresh) so no endpoint is touched at rest.
  var PANELS = [
    { id: "fleet", label: "Fleet", load: loadFleet },
    { id: "attention", label: "Attention", load: loadAttention },
    { id: "money", label: "Money", load: loadMoney },
    { id: "registry", label: "Registry", load: loadRegistry },
    { id: "sessions", label: "Sessions", load: loadSessions },
    { id: "queue", label: "Queue", load: loadQueue },
    { id: "routing", label: "Routing", load: loadRouting },
    { id: "docs", label: "Docs", load: loadDocs },
    { id: "audit", label: "Audit", load: loadAudit },
    { id: "health", label: "Health", load: loadHealth },
    { id: "workforce", label: "Workforce", load: loadWorkforce },
    { id: "operations", label: "Operations", load: loadOperations },
    { id: "surfaces", label: "Surfaces", load: loadSurfaces },
  ];

  var workbenchOrigin = null;

  /** Show one panel, hiding the others; lazy-load it the first time. */
  function openPanel(id) {
    currentPanel = id;
    PANELS.forEach(function (panel) {
      var node = document.getElementById("wb-" + panel.id);
      if (node) node.hidden = panel.id !== id;
    });
    var buttons = document.querySelectorAll("#workbench-nav [data-lens-target]");
    Array.prototype.forEach.call(buttons, function (button) {
      button.setAttribute("aria-selected", button.getAttribute("data-lens-target") === id ? "true" : "false");
    });
    var host = document.getElementById("wb-" + id);
    if (!host) return;
    var panel = PANELS.filter(function (entry) { return entry.id === id; })[0];
    if (!panel) return;
    // Re-load when the panel was never loaded OR when it is a live surface the operator returns
    // to (fleet/attention/queue). Static reporting panels keep their result until Refresh.
    if (!loaded[id] || id === "fleet" || id === "attention" || id === "queue") {
      loaded[id] = true;
      panel.load(host);
    }
  }

  /** Build the workbench nav once. */
  function buildNav() {
    var nav = document.getElementById("workbench-nav");
    if (!nav || nav.children.length) return;
    PANELS.forEach(function (panel) {
      var button = element("button", "wb-tab", {
        type: "button", role: "tab", "data-lens-target": panel.id, "aria-selected": "false",
      }, panel.label);
      button.addEventListener("click", function () { openPanel(panel.id); });
      nav.appendChild(button);
    });
  }

  function openWorkbench(origin) {
    var workbench = document.getElementById("workbench");
    if (!workbench) return;
    buildNav();
    workbench.hidden = false;
    workbenchOrigin = origin || null;
    var open = document.getElementById("workbench-open");
    if (open) open.setAttribute("aria-expanded", "true");
    openPanel(currentPanel || "fleet");
    var close = document.getElementById("workbench-close");
    if (close) close.focus();
  }

  function closeWorkbench() {
    var workbench = document.getElementById("workbench");
    if (workbench) workbench.hidden = true;
    var open = document.getElementById("workbench-open");
    if (open) open.setAttribute("aria-expanded", "false");
    if (workbenchOrigin && typeof workbenchOrigin.focus === "function") workbenchOrigin.focus();
    workbenchOrigin = null;
  }

  /** A-1/A-6: keep focus inside the workbench modal and close it on Escape. */
  function trapFocus(event) {
    if (event.key === "Escape") { closeWorkbench(); return; }
    if (event.key !== "Tab") return;
    var workbench = document.getElementById("workbench");
    if (!workbench || workbench.hidden) return;
    var focusables = workbench.querySelectorAll(
      "button, [href], input, select, textarea, [tabindex]:not([tabindex='-1'])");
    if (!focusables.length) return;
    var first = focusables[0];
    var last = focusables[focusables.length - 1];
    if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
    else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
  }

  // ── Chrome wiring + boot ──────────────────────────────────────────────────────────────────

  function init() {
    var open = document.getElementById("workbench-open");
    if (open) open.addEventListener("click", function () { openWorkbench(open); });
    var close = document.getElementById("workbench-close");
    if (close) close.addEventListener("click", closeWorkbench);
    var workbench = document.getElementById("workbench");
    if (workbench) workbench.addEventListener("keydown", trapFocus);

    // The worker stream follow/pause control toggles the selected feed's presentation state.
    var streamToggle = document.getElementById("dock-stream-toggle");
    if (streamToggle) {
      streamToggle.addEventListener("click", function () {
        var list = document.getElementById("dock-event-feed");
        var paused = streamToggle.getAttribute("aria-pressed") === "true";
        streamToggle.setAttribute("aria-pressed", paused ? "false" : "true");
        streamToggle.textContent = paused ? "Pause" : "Follow";
        if (list) list.setAttribute("data-feed-paused", paused ? "false" : "true");
      });
    }
  }

  //: The public seam app.js calls from openDock/closeDock (loaded before this file).
  window.ControlRoomParity = {
    renderDock: renderDock,
    closeDock: onDockClose,
    openPanel: openPanel,
    openWorkbench: openWorkbench,
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
