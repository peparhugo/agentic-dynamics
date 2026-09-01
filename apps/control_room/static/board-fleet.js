"use strict";

/**
 * Control Room — Fleet board logic and the two-axis status language.
 *
 * Pure functions only: nothing here touches the DOM, `window`, or the clock. That is the same
 * contract `control-room-core.js` keeps, and for the same reason — the fleet's ordering,
 * filtering, and change detection decide what the operator sees under a 5s poll, so they must
 * be deterministic and reviewable without a browser.
 *
 * THE TWO AXES (design §2.2). Lifecycle and attention are different questions about a cell and
 * must never share a hue family or a class prefix:
 *
 *   lifecycle  — what the execution is doing: queued/running/done/failed/timeout/retry/unknown.
 *                Rendered on fleet cards. Class prefix `status-`.
 *   attention  — what the SUPERVISOR HEURISTIC thinks a human should look at: off_track,
 *                stalled, attention. Rendered on the Flags board and the supervisor control
 *                panel only — never on a fleet card. Class prefix `flag-status-`.
 *
 * Keeping them in two separate maps, with two separate class prefixes and two separate lookup
 * functions, makes the separation structural rather than a convention someone has to remember:
 * there is no way to ask `lifecycle()` for `off_track` and get an answer.
 *
 * COLOR IS NEVER THE ONLY SIGNAL. Every entry carries `glyph` + `word` + `className`. The
 * renderer draws the glyph as an `aria-hidden` span and the word as text, so the state survives
 * a monochrome display, a color-vision difference, and a screen reader independently.
 *
 * Public surface (window.ControlRoomFleet):
 *   lifecycle(status) / attention(status)  — the vocabularies
 *   visibleCellIds(cells, facet, sortIds)  — urgency-first, then filtered   [design §2.1]
 *   matchesFacet(cellId, status, facet)    — the filter chips + search box
 *   livePhaseEntries(phases)               — LIVE phase entries, newest first [live board]
 *   statusCounts(cells) / countsSummary()  — the footer line               [design §2.5]
 *   cellSignature(fields) / sampleSignature(samples) — change detection    [design §2.5]
 *   orderChanged(currentIds, nextIds)      — reorder only on a real change
 */
(function initControlRoomFleet(root, core) {
  /**
   * Lifecycle vocabulary — the execution axis.
   *
   * `word` is what a screen reader announces, `glyph` is decorative, `className` pairs the
   * entry with the `--status-*` token of the same name in style.css, and `key` is the bare
   * suffix used where a component composes its own class (e.g. `cell-card status-running`).
   */
  const LIFECYCLE = {
    queued: { axis: "lifecycle", key: "queued", word: "QUEUED", glyph: "○", className: "status-queued" },
    running: { axis: "lifecycle", key: "running", word: "RUNNING", glyph: "◔", className: "status-running" },
    done: { axis: "lifecycle", key: "done", word: "DONE", glyph: "✓", className: "status-done" },
    failed: { axis: "lifecycle", key: "failed", word: "FAILED", glyph: "×", className: "status-failed" },
    timeout: { axis: "lifecycle", key: "timeout", word: "TIMEOUT", glyph: "◷", className: "status-timeout" },
    retry: { axis: "lifecycle", key: "retry", word: "RETRY", glyph: "↻", className: "status-retry" },
    ended: { axis: "lifecycle", key: "ended", word: "ENDED", glyph: "◻", className: "status-ended" },
    unknown: { axis: "lifecycle", key: "unknown", word: "UNKNOWN", glyph: "?", className: "status-unknown" },
  }

  /**
   * Attention vocabulary — the supervisor-heuristic axis.
   *
   * `off_track` is deliberately rose, not the lifecycle red: a heuristic verdict must not be
   * misreadable as an execution failure (design §2.2). `stalled` shares amber with `timeout` on
   * purpose — both mean "look at this, it is not catastrophic" — and the axes stay
   * distinguishable by location and word, which is why the word is never optional.
   */
  const ATTENTION = {
    off_track: { axis: "attention", key: "off-track", word: "OFF TRACK", glyph: "▲", className: "flag-status-off-track" },
    stalled: { axis: "attention", key: "stalled", word: "STALLED", glyph: "■", className: "flag-status-stalled" },
    attention: { axis: "attention", key: "attention", word: "ATTENTION", glyph: "◆", className: "flag-status-attention" },
  }

  /** The "Risk" filter chip: states where something needs a human's judgment, not just time. */
  const RISK_STATUSES = new Set(["failed", "timeout", "unknown"])

  /**
   * Footer order (design §2.5). Urgency-first so it reads in the same order the grid sorts,
   * and the first five are always printed even at zero: a count line whose columns appear and
   * disappear is a line the operator has to re-read every poll.
   */
  const COUNT_ORDER = ["running", "queued", "done", "failed", "timeout"]
  const COUNT_ORDER_OPTIONAL = ["retry", "unknown"]

  /** Normalize any producer status into the lifecycle vocabulary. */
  function lifecycle(value) {
    // core owns the normalization (it collapses `retry_3` -> `retry`); this module owns only
    // the presentation of the result, so the two never disagree about what a status IS.
    const status = core ? core.normalizeStatus(value) : String(value || "unknown").toLowerCase()
    return LIFECYCLE[status] || LIFECYCLE.unknown
  }

  /** Normalize a supervisor assessment into the attention vocabulary. */
  function attention(value) {
    const key = typeof value === "string" ? value.toLowerCase() : ""
    return ATTENTION[key] || ATTENTION.attention
  }

  /**
   * Decide whether one cell survives the current facet (filter chip + search box).
   *
   * Search is a plain case-insensitive substring test against the full cell id: the ids are
   * long and compound (`wf_retry_gpt_5_6_sol`), so substring beats prefix, and anything fuzzier
   * would make "why is this card here?" unanswerable at a glance.
   *
   * The `live` filter consults `facet.liveIds` — the set of cells the API marked LIVE within
   * the phase window. It is a set, not a status, because liveness is a phase-board property
   * the status vocabulary cannot express; the caller builds it from the matrix's `phases`.
   */
  function matchesFacet(cellId, status, facet) {
    const filter = facet?.filter || "all"
    const search = (facet?.search || "").toLowerCase()
    const passesFilter = filter === "all"
      || (filter === "running" && status === "running")
      || (filter === "risk" && RISK_STATUSES.has(status))
      || (filter === "live" && Boolean(facet?.liveIds?.has(cellId)))
    return passesFilter && String(cellId).toLowerCase().includes(search)
  }

  /**
   * Return the visible cell ids, urgency-first.
   *
   * Ordering is delegated to `core.sortCellIds` (running -> retry -> failed -> timeout ->
   * queued -> done -> unknown, then lexicographic) rather than re-derived here: one comparator
   * for the whole app means a card cannot move because two files disagree about urgency.
   * Filtering happens after sorting so the surviving cards keep their absolute order.
   */
  function visibleCellIds(cells, facet, sortIds) {
    const sorted = typeof sortIds === "function" ? sortIds(cells) : Object.keys(cells || {})
    return sorted.filter((cellId) => matchesFacet(cellId, lifecycle(cells[cellId]).key, facet))
  }

  /**
   * Return the LIVE phase entries, newest first — the content of the LIVE NOW section.
   *
   * A run is live when the API says so (its last phase, or its runner-telemetry tail, falls
   * within the live window). `last_phase_ts` is normalized to a UTC ISO string server-side, so
   * a descending string compare is exactly a newest-first sort. Age-unknown runs (no timestamp)
   * are never live and therefore never appear here.
   */
  function livePhaseEntries(phases) {
    return Object.entries(phases || {})
      .filter(([, phase]) => Boolean(phase && phase.live === true))
      .sort((left, right) =>
        String(right[1].last_phase_ts || "").localeCompare(String(left[1].last_phase_ts || "")),
      )
  }

  /** Count every retained cell by lifecycle state, including the states at zero. */
  function statusCounts(cells) {
    const counts = { queued: 0, running: 0, done: 0, failed: 0, timeout: 0, retry: 0, unknown: 0 }
    for (const value of Object.values(cells || {})) counts[lifecycle(value).key] += 1
    return counts
  }

  /** Render the footer summary line: `7 running - 12 queued - 8 done - 2 failed - 0 timeout`. */
  function countsSummary(counts) {
    const always = COUNT_ORDER.map((status) => `${counts[status] || 0} ${status}`)
    // A nonzero retry/unknown count is itself news, so those columns appear only when they
    // have something to say.
    const optional = COUNT_ORDER_OPTIONAL
      .filter((status) => (counts[status] || 0) > 0)
      .map((status) => `${counts[status]} ${status}`)
    return always.concat(optional).join("  ·  ")
  }

  /**
   * A stable content fingerprint for one card.
   *
   * The fleet re-renders every 5 seconds whether or not anything moved. Comparing this string
   * against the previous one lets the renderer skip every DOM write for an unchanged card,
   * which is what keeps row identity stable, focus intact, and text selection alive across a
   * no-op poll (design §2.5). Every field that is actually painted appears here — miss one and
   * the card silently goes stale.
   */
  function cellSignature(fields) {
    return [
      fields.status || "",
      fields.selected ? "1" : "0",
      fields.phase || "",
      fields.cost || "",
      fields.samples || "",
    ].join(" ")
  }

  /**
   * A fingerprint for a cell's sample series, used to decide whether to redraw its sparkline.
   *
   * The sparkline is the most expensive thing on a card (one SVG rect per sample), and it only
   * changes when a new sample arrives — the length plus the last sample's identity captures
   * that, because samples are append-only.
   */
  function sampleSignature(samples) {
    if (!Array.isArray(samples) || samples.length === 0) return "0"
    const latest = samples[samples.length - 1]
    return `${samples.length}|${latest?.identity ?? ""}`
  }

  /**
   * True when two id lists differ in content or order.
   *
   * Reordering the DOM is what destroys scroll anchoring and steals focus, so the renderer asks
   * this first and moves nothing when the answer is no.
   */
  function orderChanged(currentIds, nextIds) {
    if (currentIds.length !== nextIds.length) return true
    for (let index = 0; index < nextIds.length; index += 1) {
      if (currentIds[index] !== nextIds[index]) return true
    }
    return false
  }

  const fleet = {
    LIFECYCLE,
    ATTENTION,
    RISK_STATUSES,
    COUNT_ORDER,
    lifecycle,
    attention,
    matchesFacet,
    visibleCellIds,
    livePhaseEntries,
    statusCounts,
    countsSummary,
    cellSignature,
    sampleSignature,
    orderChanged,
  }

  root.ControlRoomFleet = fleet
  if (typeof module !== "undefined" && module.exports) module.exports = fleet
})(typeof globalThis !== "undefined" ? globalThis : window, (typeof globalThis !== "undefined" ? globalThis : window).ControlRoomCore)
