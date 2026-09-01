"use strict";

/**
 * Control Room browser controller.
 *
 * The matrix snapshot owns retained fleet telemetry. The selected-cell stream
 * only overlays not-yet-polled live samples, which prevents polling, replay,
 * and automatic EventSource reconnection from multiplying reported spend.
 */
(function startControlRoom(core, root) {
  const SVG_NS = "http://www.w3.org/2000/svg"
  const MAX_TRANSCRIPT_ROWS = 500
  const MAX_LIVE_SAMPLES_PER_CELL = 500
  const REPLAY_RACE_TAIL = 500
  const REPLAY_RACE_WINDOW_MS = 250
  const MATRIX_POLL_MS = 5000
  const FLAGS_POLL_MS = 5000
  // The docs-drift rail is driven by an HOURLY systemd timer, so anything faster than
  // this would poll a file that cannot have changed. 60s keeps the panel honest within
  // a minute of a scan landing without pretending the underlying cadence is live.
  const DOCS_HEALTH_POLL_MS = 60000
  const DESIGN_LIST_POLL_MS = 10000
  const DRAFT_POLL_MS = 3000
  const BURN_WINDOW_MS = 60000
  // Presentation bound for the Status board's full-width burn trace (design §5.2).
  const BURN_TRACE_SAMPLES = 60
  const CLAUDE_AGENTS_POLL_MS = 10000
  const CLAUDE_AGENTS_DAEMON_POLL_MS = 15000
  const CLAUDE_AGENT_CELL_PREFIX = "claude_bg_"

  // The status vocabulary (glyph + word + class, on two axes) lives in board-fleet.js so the
  // fleet cards, the detail header, the Claude roster, and the flag rows cannot drift apart.
  const fleet = root.ControlRoomFleet
  // Keyed reconciliation + write-on-change helpers, shared by every polled list in this file.
  const list = root.ControlRoomKeyedList
  const { setText, setHidden, setAttribute: setAttr, setClassName } = list

  const state = {
    cells: {},
    stages: {},
    // The last docs-health envelope, plus the two flags that keep the approve
    // affordance from racing itself (see loadDocsHealth / approveProposal).
    docsHealth: null,
    docsHealthApprovePending: false,
    docsHealthRetry: false,
    phases: {},
    statusOverrides: new Map(),
    telemetry: { cells: {}, reported_cost: null, input_tokens: null, output_tokens: null },
    liveSamplesByCell: new Map(),
    burnSamples: [],
    selectedId: null,
    selectedType: null,
    selectedSessionIds: [],
    rows: [],
    buffer: [],
    eventLedgerCounts: new Map(),
    eventLedgerOrder: [],
    replaySkipCounts: new Map(),
    replaySeenCounts: new Map(),
    replayTail: [],
    raceDuplicateCounts: new Map(),
    raceDedupeExpiresAt: 0,
    paused: false,
    follow: true,
    followBeforePause: true,
    filter: "all",
    search: "",
    matrixState: "connecting",
    statusState: "connecting",
    streamState: "disconnected",
    statusSource: null,
    eventSource: null,
    attached: false,
    replayMode: true,
    lastMatrixAt: null,
    lastEventAt: null,
    firstMatrixLoaded: false,
    matrixRequestSequence: 0,
    matrixRequestInFlight: false,
    routingLoaded: false,
    routingOpen: false,
    routingReturnFocus: null,
    registryLoaded: false,
    registryOpen: false,
    registryReturnFocus: null,
    queuePending: false,
    designSessions: new Map(),
    approvedWorkdirs: [],
    designFormKind: null,
    designMutationPending: false,
    draftRequestInFlight: false,
    draftPollTimer: null,
    draftState: null,
    draftSignature: null,
    draftFresh: false,
    supervisorFlags: new Map(),
    supervisorState: "loading",
    supervisorSource: "unknown",
    supervisorWarnings: [],
    supervisorRequestInFlight: false,
    supervisorSelection: null,
    supervisorMutationPending: false,
    supervisorInterrupted: false,
    supervisorSteerKey: null,
    supervisorSteerSignature: null,
    supervisorInterruptKey: null,
    claudeAgents: new Map(),
    claudeAgentsUnavailable: false,
    approvedClaudeAgentWorkdirs: [],
    selectedClaudeAgentId: null,
    claudeAgentMutationPending: false,
    claudeAgentDaemon: null,
    usageRequestInFlight: false,
  }

  /** Query one required shell element. */
  function $(selector) {
    return document.querySelector(selector)
  }

  /** Create an element with optional class and text, always using textContent. */
  function element(tagName, className = "", text = "") {
    const node = document.createElement(tagName)
    if (className) node.className = className
    if (text !== "") node.textContent = text
    return node
  }

  /** Announce important state changes without announcing continuous output. */
  function announce(message, assertive = false) {
    const region = assertive ? $("#alert-status") : $("#polite-status")
    region.textContent = ""
    window.setTimeout(() => {
      region.textContent = message
    }, 0)
  }

  /** Format reported cost at operational precision. */
  function formatCost(value) {
    if (value === null) return null
    return value < 100 ? `$${value.toFixed(4)}` : `$${value.toFixed(2)}`
  }

  /** Compact rail tokens while retaining exact values through title/ARIA text. */
  function compactTokens(value) {
    if (value === null) return "--"
    if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(value >= 10_000_000 ? 1 : 2)}M`
    if (value >= 1_000) return `${(value / 1_000).toFixed(value >= 100_000 ? 0 : 1)}K`
    return Math.round(value).toLocaleString()
  }

  /** Format a server timestamp as a stable human-readable age. */
  function formatAge(value) {
    if (!value) return "unavailable"
    const timestamp = new Date(value).getTime()
    if (!Number.isFinite(timestamp)) return "unavailable"
    const seconds = Math.max(0, Math.floor((Date.now() - timestamp) / 1000))
    if (seconds < 60) return `${seconds}s ago`
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`
    if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`
    return `${Math.floor(seconds / 86400)}d ago`
  }

  /**
   * Format a server-computed age (whole seconds since the last published phase) as a label.
   *
   * `null` (or any non-finite value) is the age-unknown state — a run with no published-phase
   * timestamp and no runner-telemetry tail. It is its own word, never a number: age-unknown
   * must not be readable as "0s ago".
   */
  function formatAgeSeconds(seconds) {
    if (seconds === null || !Number.isFinite(seconds)) return "age unknown"
    if (seconds < 60) return `${Math.floor(seconds)}s ago`
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`
    if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`
    return `${Math.floor(seconds / 86400)}d ago`
  }

  /**
   * Keep heuristic supervisor statuses separate from fleet lifecycle states.
   *
   * The two axes must never be confusable (design §2.2), so this resolves the ATTENTION
   * vocabulary and nothing else: asking it for "running" yields the neutral ATTENTION entry,
   * not a lifecycle state. The returned shape is kept (`label`/`className`) because the
   * supervisor rail composes `flag-<className>` and `flag-status-<className>` class names;
   * `vocabulary` carries the glyph for callers that paint the word.
   */
  function supervisorStatus(value) {
    const vocabulary = fleet.attention(value)
    return { label: vocabulary.word, className: vocabulary.key, vocabulary }
  }

  /** Return normalized status counts for both cards and the command rail. */
  function statusCounts() {
    return fleet.statusCounts(state.cells)
  }

  /**
   * Paint one status vocabulary entry into a node as an aria-hidden glyph plus the word.
   *
   * Color is never the only signal (design §2.2): the glyph survives a monochrome display and
   * the word survives a screen reader, which announces only the text because the glyph is
   * marked decorative. Every status surface in the app goes through here, so there is exactly
   * one place where "how a status looks" is decided.
   */
  function applyStatusWord(node, vocabulary, baseClass = "status-word") {
    node.className = `${baseClass} ${vocabulary.className}`
    const glyph = element("span", "status-glyph", vocabulary.glyph)
    glyph.setAttribute("aria-hidden", "true")
    node.replaceChildren(glyph, document.createTextNode(vocabulary.word))
    return node
  }

  /** Describe the healthiest meaningful aggregate connection state. */
  function overallState() {
    if (state.matrixState === "unavailable") return "offline"
    if (state.statusState === "reconnecting" || state.matrixState === "disconnected") return "reconnecting"
    if (state.statusState === "live" && state.matrixState === "live") return "live"
    return "connecting"
  }

  /** Keep the command rail synchronized with matrix and selected live overlays. */
  function renderRail() {
    const totals = core.reconcileTelemetry(state.telemetry, state.liveSamplesByCell)
    const capped = state.telemetry.history_capped === true
    const spend = $("#reported-spend")
    const formattedSpend = formatCost(totals.reported_cost)
    spend.textContent = formattedSpend ? `${formattedSpend}${capped ? "±" : ""}` : "WAITING FOR COST TELEMETRY"
    spend.setAttribute(
      "aria-label",
      formattedSpend
        ? `${formattedSpend} cumulative reported spend, retained window${capped ? " truncated at 500 entries" : ""}`
        : "Waiting for cost telemetry",
    )
    $("#spend-provenance").textContent = capped ? "RETAINED WINDOW · TRUNCATED" : "RETAINED WINDOW"

    const input = $("#input-tokens")
    const output = $("#output-tokens")
    input.textContent = compactTokens(totals.input_tokens)
    output.textContent = compactTokens(totals.output_tokens)
    input.title = totals.input_tokens === null ? "Unavailable" : `${totals.input_tokens.toLocaleString()} reported input tokens`
    output.title = totals.output_tokens === null ? "Unavailable" : `${totals.output_tokens.toLocaleString()} reported output tokens`
    $("#running-count").textContent = String(statusCounts().running)

    const connection = overallState()
    const badge = $("#overall-state")
    badge.textContent = connection.toUpperCase()
    badge.className = `state-badge state-${connection}`
    $("#redis-state").textContent = state.matrixState === "unavailable" ? "UNAVAILABLE" : state.matrixState.toUpperCase()
    renderBurn()
  }

  /** Render rolling burn and a truthful trace of recently observed live deltas. */
  function renderBurn() {
    const now = Date.now()
    state.burnSamples = state.burnSamples.filter((sample) => now - sample.receivedAt <= BURN_WINDOW_MS)
    const burn = core.burnRate(state.burnSamples, now, BURN_WINDOW_MS)
    const output = $("#burn-rate")
    if (state.burnSamples.length === 0) {
      output.textContent = "WAITING FOR LIVE COST"
    } else {
      output.textContent = `${formatCost(burn)}/min`
    }

    const svg = $("#burn-trace")
    svg.replaceChildren()
    // The Status board shows the whole retained window rather than a rail-sized tail: every
    // sample inside the rolling 60s is already in `burnSamples`, so the cap here is the
    // presentation bound, not a data bound (design §5.2).
    const samples = state.burnSamples.slice(-BURN_TRACE_SAMPLES)
    if (samples.length === 0) {
      svg.setAttribute("aria-label", "No live cost samples in the rolling 60-second window")
      return
    }
    const maximum = Math.max(...samples.map((sample) => sample.cost), 0.000001)
    const points = samples.map((sample, index) => {
      // Geometry follows the 240x48 viewBox: 2px padding on each edge, so a flat series still
      // draws a visible line rather than sitting on the border.
      const x = samples.length === 1 ? 120 : (index / (samples.length - 1)) * 236 + 2
      const y = 45 - (sample.cost / maximum) * 42
      return `${x.toFixed(2)},${y.toFixed(2)}`
    })
    const line = document.createElementNS(SVG_NS, "polyline")
    line.setAttribute("points", points.join(" "))
    line.setAttribute("class", "cost-line")
    svg.appendChild(line)
    svg.setAttribute("aria-label", `${samples.length} live reported cost samples; latest ${formatCost(samples.at(-1).cost)}`)
  }

  /** Return retained samples plus selected live samples absent from the snapshot. */
  function samplesForCell(cellId) {
    const retained = Array.isArray(state.telemetry.cells?.[cellId]?.samples)
      ? state.telemetry.cells[cellId].samples
      : []
    const live = state.liveSamplesByCell.get(cellId) || []
    return retained.concat(live)
  }

  /** Build a defensive, decorative token/cost sparkline and text alternative. */
  function createSparkline(samples) {
    const wrapper = element("div", "sparkline-wrap")
    const recent = samples.slice(-12)
    if (recent.length === 0) {
      wrapper.appendChild(element("div", "sparkline-empty", "no samples"))
      wrapper.appendChild(element("span", "sr-only", "No reported token or cost samples"))
      return wrapper
    }

    const svg = document.createElementNS(SVG_NS, "svg")
    svg.setAttribute("class", "sparkline")
    svg.setAttribute("viewBox", "0 0 180 36")
    svg.setAttribute("aria-hidden", "true")
    const tokenMaximum = Math.max(...recent.map((sample) => core.safeNumber(sample.total_tokens) ?? 0), 1)
    recent.forEach((sample, index) => {
      const tokens = core.safeNumber(sample.total_tokens) ?? 0
      const height = Math.max((tokens / tokenMaximum) * 28, tokens > 0 ? 1 : 0)
      const bar = document.createElementNS(SVG_NS, "rect")
      bar.setAttribute("x", String(index * 15 + 2))
      bar.setAttribute("y", String(33 - height))
      bar.setAttribute("width", "9")
      bar.setAttribute("height", String(height))
      // SVG geometry attributes are more portable than relying on CSS `rx` support alone.
      bar.setAttribute("rx", "2")
      bar.setAttribute("class", "token-bar")
      svg.appendChild(bar)
    })

    const validCosts = recent.map((sample, index) => ({ index, cost: core.safeNumber(sample.cost) }))
      .filter((sample) => sample.cost !== null)
    if (validCosts.length > 0) {
      const costMaximum = Math.max(...validCosts.map((sample) => sample.cost), 0.000001)
      const line = document.createElementNS(SVG_NS, "polyline")
      line.setAttribute(
        "points",
        validCosts.map((sample) => `${sample.index * 15 + 6.5},${31 - (sample.cost / costMaximum) * 25}`).join(" "),
      )
      line.setAttribute("class", "cost-line")
      svg.appendChild(line)
    }
    wrapper.appendChild(svg)

    const latest = recent.at(-1)
    const tokens = core.safeNumber(latest.total_tokens)
    const cost = core.safeNumber(latest.cost)
    const summaryParts = [tokens === null ? "tokens unavailable" : `${tokens.toLocaleString()} tokens`]
    summaryParts.push(cost === null ? "cost unavailable" : `${formatCost(cost)} reported cost`)
    wrapper.appendChild(element("span", "sr-only", `Latest sample: ${summaryParts.join(", ")}; ${recent.length} samples shown`))
    return wrapper
  }

  /**
   * Adopt the shell's static placeholder rather than appending a second one beside it.
   *
   * index.html ships a first-paint placeholder in each polled list ("Loading supervisor
   * flags…", "Loading Claude background sessions…", "No portal-owned design sessions yet.") so
   * the page says something useful before any fetch resolves. A renderer that creates its OWN
   * placeholder node leaves that static one stranded above the rows forever — visible, stale,
   * and pointing at a state the list has long left. Taking ownership of the existing node on
   * the first render keeps one placeholder per list, whoever created it.
   */
  function adoptPlaceholder(container, current) {
    return current || container.querySelector(".empty-state, .error-state")
  }

  /* ── Fleet board ─────────────────────────────────────────────────────────────────────────
     The matrix is the operator's home surface (design §2.1), and it re-renders every 5s
     whether or not anything moved. The renderer below is therefore KEYED rather than
     wholesale: each cell owns one `<article>` that is created once, updated in place, and
     moved only when its position in the urgency order actually changes (design §2.5).

     What that buys, concretely — every item is something the previous rebuild-the-world
     renderer lost on each poll:
       - keyboard focus stays on the card the operator was on, without a re-focus hack;
       - a half-finished text selection of a cell id survives;
       - hover/active state and the running pulse animation do not restart;
       - the scroll position does not jump, because no node the browser is anchored to is
         destroyed;
       - a no-op poll performs ZERO DOM writes, so a screen reader announces nothing.

     Ordering, filtering, counts, and change detection are all decided by board-fleet.js, which
     is pure and browser-free; this section only translates those decisions into DOM. */

  /** Live card handles, keyed by cell id: `{ node, button, statusWord, ... }`. */
  const fleetCards = new Map()

  /** The mounted empty/no-match placeholder, when the grid has no cards to show. */
  let fleetPlaceholder = null

  /** Live-card handles for the LIVE NOW section, keyed by cell id (the live board). */
  const liveNowRows = new Map()

  /** The mounted empty placeholder for the LIVE NOW section. */
  let liveNowPlaceholder = null

  /**
   * Build the DOM for one cell card.
   *
   * Called exactly once per cell id. Every mutable part is kept as a permanent child that is
   * later hidden or retitled rather than created and destroyed, because a node that survives
   * is a node the browser (and the operator's focus) can stay anchored to.
   *
   * The whole card is a single `<button>`: tapping anywhere on it IS the drill-down, with no
   * interstitial, because drill-down is read-only and safe to be one-tap (design §2.4).
   */
  function createFleetCard(cellId) {
    const card = element("article", "cell-card")
    const button = element("button", "cell-select")
    button.type = "button"
    button.dataset.cellId = cellId

    const heading = element("div", "cell-heading")
    const statusWord = element("span", "status-word")
    const selectedLabel = element("span", "selected-label", "SELECTED")
    selectedLabel.hidden = true
    heading.appendChild(statusWord)
    heading.appendChild(selectedLabel)
    button.appendChild(heading)

    // The id is rendered with textContent (never interpolated into markup): cell ids come from
    // the queue and are not trusted input.
    const identity = element("span", "cell-id", cellId)
    button.appendChild(identity)

    // Live workflow phase badge (display-only): "4/7 rerun_contaminated".
    const phaseBadge = element("span", "phase-badge")
    phaseBadge.hidden = true
    button.appendChild(phaseBadge)

    const cost = element("span", "latest-cost", "no cost yet")
    button.appendChild(cost)

    // The sparkline is the one part that is genuinely rebuilt, and only when a new sample
    // arrives; `sparkline` holds the node so the replacement can swap in place.
    const sparkline = createSparkline([])
    button.appendChild(sparkline)
    card.appendChild(button)

    // Pre-sheet fallback for narrow screens; the Detail surface supersedes it, and it stays
    // hidden unless this card is the selected one.
    const jump = element("a", "mobile-anchor card-jump", "Jump to transcript")
    jump.href = "#transcript-panel"
    jump.hidden = true
    card.appendChild(jump)

    // `node` is the handle the shared reconciler moves and removes; the rest are the parts
    // `updateFleetCard` writes.
    return { node: card, card, button, statusWord, selectedLabel, phaseBadge, cost, sparkline, jump, signature: null, sampleSignature: null }
  }

  /**
   * Update one card, writing only the parts whose value actually changed.
   *
   * `facts.signature` is the whole card's fingerprint: when it matches the previous render the
   * function returns immediately and the card is not touched at all.
   */
  function updateFleetCard(entry, cellId, facts) {
    if (entry.signature === facts.signature) return
    entry.signature = facts.signature

    const vocabulary = facts.vocabulary
    setClassName(entry.card, `cell-card ${vocabulary.className}${facts.selected ? " selected" : ""}`)
    applyStatusWord(entry.statusWord, vocabulary)
    setAttr(
      entry.button,
      "aria-label",
      vocabulary.key === "running" ? `Watch running cell ${cellId}` : `Inspect cell ${cellId}`,
    )
    setAttr(entry.button, "aria-pressed", String(facts.selected))
    setHidden(entry.selectedLabel, !facts.selected)
    setHidden(entry.jump, !facts.selected)

    setHidden(entry.phaseBadge, !facts.phase)
    if (facts.phase) setText(entry.phaseBadge, facts.phase)

    setText(entry.cost, facts.cost)

    // Redraw the sparkline only when the sample series grew: it is the most expensive node on
    // the card, and a status-only change must not cost an SVG rebuild.
    if (entry.sampleSignature !== facts.samples) {
      entry.sampleSignature = facts.samples
      const replacement = createSparkline(facts.sampleList)
      entry.sparkline.replaceWith(replacement)
      entry.sparkline = replacement
    }
  }

  /** Format the live workflow phase badge label, or "" when the cell reports no phase. */
  function phaseLabel(cellId) {
    const phase = state.phases[cellId]
    if (!phase || typeof phase !== "object" || typeof phase.name !== "string" || !phase.name) return ""
    const index = Number.isInteger(phase.index) ? phase.index : null
    const total = Number.isInteger(phase.total) ? phase.total : null
    return `${index !== null ? `${index}/${total ?? "?"}` : ""} ${phase.name}`.trim()
  }

  /** Format the phase badge WITH its age for the historical list and LIVE NOW rows.
   *
   * Every card in the current list carries its age so a stalled run "leaves LIVE NOW and shows
   * its age in the historical list" — the badge is the one place the age belongs next to the
   * i-of-N phase without adding a second line. The detail glance keeps the bare ``phaseLabel``
   * because the Detail surface has a dedicated space for recency.
   */
  function phaseBadgeLabel(cellId) {
    const phase = state.phases[cellId]
    if (!phase || typeof phase !== "object" || typeof phase.name !== "string" || !phase.name) return ""
    const label = phaseLabel(cellId)
    return `${label} · ${formatAgeSeconds(phase.age_seconds)}`
  }

  /** Mount, retitle, or remove the "nothing to show" placeholder for the grid. */
  function renderFleetPlaceholder(grid, text) {
    if (!text) {
      fleetPlaceholder?.remove()
      fleetPlaceholder = null
      return
    }
    if (!fleetPlaceholder) {
      // Both empty states are plain copy; the wording distinguishes "the fleet is empty" from
      // "your filter hid everything", which are very different operator problems. The node is
      // appended AFTER the cards so the reconciler's reorder pass never has to step over it.
      fleetPlaceholder = element("p", "empty-state", "No cells are queued or retained")
      grid.appendChild(fleetPlaceholder)
    }
    setText(fleetPlaceholder, text)
  }

  /* ── LIVE NOW (the live board) ───────────────────────────────────────────────────────────
     The live dimension of the phases board, rendered above the full fleet. LIVE NOW lists the
     runs whose last phase was published within the live window (10 minutes, the watchdog
     horizon) or whose runner telemetry is still active — newest first, each with the i-of-N
     phase and its age. Past the window a run leaves LIVE NOW and shows its age in the grid
     below; a run with no timestamp renders "age unknown", never mislabeled. The section is a
     read-only highlight: rows drill into the same detail surface as fleet cards, and the grid
     underneath stays the full list. */

  /** Build one LIVE NOW row: cell id, the i-of-N phase badge, and the age. */
  function createLiveNowRow(cellId) {
    const button = element("button", "live-now-row")
    button.type = "button"
    button.dataset.cellId = cellId
    button.appendChild(element("span", "cell-id", cellId))
    const phaseBadge = element("span", "phase-badge")
    button.appendChild(phaseBadge)
    const age = element("span", "live-age")
    button.appendChild(age)
    return { node: button, button, phaseBadge, age, signature: null }
  }

  /** Refresh one LIVE NOW row, writing only the fields whose text actually changed. */
  function updateLiveNowRow(entry, cellId) {
    const phase = state.phases[cellId]
    if (!phase) return
    const selected = state.selectedType === "cell" && state.selectedId === cellId
    const badge = phaseLabel(cellId)
    const age = formatAgeSeconds(phase.age_seconds)
    const signature = `${badge}|${age}|${selected ? 1 : 0}`
    if (entry.signature === signature) return
    entry.signature = signature
    setClassName(entry.button, `live-now-row${selected ? " selected" : ""}`)
    setAttr(entry.button, "aria-pressed", String(selected))
    setAttr(entry.button, "aria-label", `${badge || cellId} · ${age}`)
    setText(entry.phaseBadge, badge)
    setText(entry.age, age)
  }

  /** Mount, retitle, or remove the LIVE NOW section's empty placeholder. */
  function renderLiveNowPlaceholder(container, text) {
    liveNowPlaceholder = adoptPlaceholder(container, liveNowPlaceholder)
    if (!text) {
      liveNowPlaceholder?.remove()
      liveNowPlaceholder = null
      return
    }
    if (!liveNowPlaceholder) {
      liveNowPlaceholder = element("p", "empty-state", text)
      container.appendChild(liveNowPlaceholder)
    }
    setText(liveNowPlaceholder, text)
  }

  /** Render LIVE NOW: the live runs, newest first, with i-of-N + age (see section header). */
  function renderLiveNow() {
    const section = $("#live-now")
    const container = $("#live-now-list")
    if (!section || !container) return
    const entries = fleet.livePhaseEntries(state.phases)
    setText($("#live-now-count"), entries.length)
    // The section hides when nothing is live UNLESS the operator is explicitly viewing live
    // runs — under the "live" filter, an empty LIVE NOW is the whole story and must stay.
    setHidden(section, entries.length === 0 && state.filter !== "live")
    renderLiveNowPlaceholder(container, entries.length === 0 ? "No runs are live within the window." : "")
    list.reconcile({
      container,
      keys: entries.map(([cellId]) => cellId),
      entries: liveNowRows,
      create: createLiveNowRow,
      update: updateLiveNowRow,
    })
  }

  /** Render urgency-sorted fleet cards without interpolating untrusted IDs. */
  function renderFleet() {
    // LIVE NOW is part of the fleet render: it depends on the same matrix snapshot and the
    // same filter chip, so it must re-render whenever either one moves.
    renderLiveNow()
    const grid = $("#fleet-grid")
    // Re-setting an attribute to the value it already holds still queues a mutation record,
    // which is enough to make a screen reader re-announce a busy region every 5 seconds. Write
    // only on a real change — the same rule the card updates below follow.
    setAttr(grid, "aria-busy", state.matrixState === "connecting" ? "true" : "false")
    // Preserve the immediate skeleton until the first matrix request settles.
    if (!state.firstMatrixLoaded && state.matrixState === "connecting" && Object.keys(state.cells).length === 0) {
      renderRail()
      return
    }
    // The skeleton cards are static markup from index.html; they are dropped once, on the
    // first real render, and never re-created.
    for (const skeleton of Array.from(grid.querySelectorAll(".skeleton-card"))) skeleton.remove()

    // The `live` filter is keyed off the API's phase liveness, not the lifecycle vocabulary:
    // the set of cells whose last phase (or runner telemetry) falls within the live window.
    const liveIds = new Set(fleet.livePhaseEntries(state.phases).map(([cellId]) => cellId))
    const ids = fleet.visibleCellIds(
      state.cells,
      { filter: state.filter, search: state.search, liveIds },
      core.sortCellIds,
    )
    const retained = Object.keys(state.cells).length

    renderFleetPlaceholder(
      grid,
      retained === 0 && state.matrixState !== "connecting"
        ? "No cells are queued or retained"
        : ids.length === 0 && retained > 0
          ? "No cells match the current fleet filter"
          : "",
    )

    // Create, update, remove, and reorder in one pass. Cards survive polls; only genuinely
    // changed cells cost a DOM write, and the order is touched only where it differs.
    list.reconcile({
      container: grid,
      keys: ids,
      entries: fleetCards,
      create: createFleetCard,
      update: (entry, cellId) => {
        const vocabulary = fleet.lifecycle(state.cells[cellId])
        const selected = state.selectedType === "cell" && state.selectedId === cellId
        const sampleList = samplesForCell(cellId)
        const costs = sampleList.map((sample) => core.safeNumber(sample.cost)).filter((value) => value !== null)
        const facts = {
          vocabulary,
          selected,
          sampleList,
          phase: phaseBadgeLabel(cellId),
          cost: costs.length ? `${formatCost(costs.at(-1))} latest reported step` : "no cost yet",
          samples: fleet.sampleSignature(sampleList),
        }
        facts.signature = fleet.cellSignature({
          status: vocabulary.key,
          selected,
          phase: facts.phase,
          cost: facts.cost,
          samples: facts.samples,
        })
        updateFleetCard(entry, cellId, facts)
      },
    })

    // Footer: totals and the counts line, written only when the text actually differs so a
    // no-op poll cannot re-announce them to assistive technology (design §2.5).
    setText($("#fleet-total"), retained)
    setText($("#fleet-counts"), fleet.countsSummary(statusCounts()))
    renderRail()
  }

  /** Pick a border-state class for one pipeline stage from its counts. */
  function pipelineStageClass(stage) {
    const total = stage.total ?? 0
    const done = stage.done ?? 0
    const failed = stage.failed ?? 0
    const running = stage.running ?? 0
    if (running > 0) return "stage-running"
    if (failed > 0) return "stage-failed"
    if (total > 0 && done === total) return "stage-done"
    return "stage-idle"
  }

  /** Render one stage card: name, total, and done/running/queued/failed counts. */
  function stageCard(name, label, stage) {
    const card = element("div", `pipeline-stage ${pipelineStageClass(stage)}`)
    card.appendChild(element("span", "stage-name", label))
    card.appendChild(element("span", "stage-total", `${stage.total ?? 0} ${name === "execute" ? "CELLS" : "JOBS"}`))
    const counts = element("span", "stage-counts")
    const addCount = (status, value) => {
      const wrap = element("span", "count")
      wrap.appendChild(element("span", "n", String(value ?? 0)))
      wrap.appendChild(document.createTextNode(` ${status}`))
      counts.appendChild(wrap)
    }
    addCount("done", stage.done)
    addCount("running", stage.running)
    addCount("queued", stage.queued)
    addCount("failed", stage.failed)
    if (stage.retry) addCount("retry", stage.retry)
    if (stage.timeout) addCount("timeout", stage.timeout)
    card.appendChild(counts)
    return card
  }

  /** Render the execute → analyze → review pipeline summary strip. */
  function renderPipelineStages() {
    const container = $("#pipeline-stages")
    if (!container) return
    container.replaceChildren()
    const stages = state.stages && typeof state.stages === "object" ? state.stages : {}
    const labels = { execute: "EXECUTE", analyze: "ANALYZE", review: "REVIEW" }
    for (const name of ["execute", "analyze", "review"]) {
      const stage = stages[name] && typeof stages[name] === "object" ? stages[name] : {}
      container.appendChild(stageCard(name, labels[name], stage))
    }
  }

  /* ── Docs health ─────────────────────────────────────────────────────────────────────────
     The docs-drift rail's surface: "is the docs current?" as a number, beside the pipeline
     strip. Four properties are deliberate here:

       1. THE SERVER DECIDES THE COLOUR. `condition`/`health`/`word` all arrive on the envelope
          from `services/docs_health.py`. This module never derives a colour from a drift count,
          because the CLI, the supervisor board, and this panel must not be able to disagree
          about what a score means — the same reason the watchdog computes its row's `health`
          server-side rather than in the browser.
       2. COLOUR IS NEVER THE ONLY SIGNAL. Every state paints a glyph AND a word AND a sentence.
          `warranted` and `unmeasured` are both red and are told apart by their word, so the
          state survives a monochrome display, a colour-vision difference, and a screen reader.
       3. "COULD NOT MEASURE" IS NOT "CLEAN". The unmeasured state has its own copy and shows NO
          approve affordance: there is no trustworthy inventory to sign off on. A fetch failure
          is likewise its own state — it never blanks to green.
       4. THE APPROVE KEY IS DERIVED FROM THE PROPOSAL, NOT RANDOM. See `approveProposal`. */

  /** Format an ISO stamp as the compact `YYYY-MM-DD HH:MM` the rest of the portal uses. */
  function docsHealthStamp(value) {
    const text = String(value || "")
    return text ? `${text.slice(0, 16).replace("T", " ")}Z` : "never"
  }

  /** Render one `axis N` definition pair; only axes with a nonzero count are painted. */
  function docsHealthAxes(perAxis) {
    const container = $("#docs-health-axes")
    if (!container) return
    container.replaceChildren()
    const entries = Object.entries(perAxis || {})
      .filter(([, count]) => Number(count) > 0)
      .sort((a, b) => Number(b[1]) - Number(a[1]) || String(a[0]).localeCompare(String(b[0])))
    for (const [axis, count] of entries) {
      const term = element("dt", "docs-health-axis-name", axis.replace(/_/g, " "))
      const value = element("dd", "docs-health-axis-count", String(count))
      container.appendChild(term)
      container.appendChild(value)
    }
  }

  /**
   * Render the finding inventory — the evidence half of the panel.
   *
   * Every row keeps its `basis`: the string naming how to re-derive the finding by hand. That is
   * the scanner's hard rule 4 carried all the way to the browser, and it is what makes the
   * approve button a decision rather than an act of faith — an operator about to authorise ~$3
   * of remediation can check any row without trusting the machine that produced it.
   */
  function docsHealthInventory(data) {
    const container = $("#docs-health-inventory")
    if (!container) return
    container.replaceChildren()
    const rows = Array.isArray(data.inventory) ? data.inventory : []
    if (!rows.length) return
    for (const row of rows) {
      const item = element("details", "docs-health-finding")
      const summary = element("summary", "docs-health-finding-summary")
      summary.appendChild(element("span", `docs-health-finding-status status-${row.status || "unknown"}`, String(row.status || "?").toUpperCase()))
      summary.appendChild(element("span", "docs-health-finding-source", String(row.source || row.check_id || "?")))
      item.appendChild(summary)
      item.appendChild(element("p", "docs-health-finding-claim", `Doc claims: ${row.claim || "—"}`))
      item.appendChild(element("p", "docs-health-finding-truth", `Code says: ${row.code_truth || "—"}`))
      item.appendChild(element("p", "docs-health-finding-basis", `Re-derive: ${row.basis || "—"}`))
      container.appendChild(item)
    }
    if (data.inventory_truncated) {
      // Truncation is reported, never silent: a list that quietly stops is a list an operator
      // reads as complete.
      container.appendChild(element("p", "pane-note",
        `Showing the first ${rows.length} findings of ${data.scan?.drift ?? "?"}. The full inventory is in ${data.scan?.report ?? "the scan report"}.`))
    }
  }

  /**
   * Render the proposal half, including whether the approve affordance is offered at all.
   *
   * `approvable` is computed server-side and simply obeyed here. Hiding the form is a caution
   * against an honest mistake — the gate re-checks the proposal state and takes the atomic claim
   * regardless, so a crafted request cannot get past it either way.
   */
  function docsHealthProposal(data) {
    const panel = $("#docs-health-proposal")
    const form = $("#docs-health-approve-form")
    const detail = $("#docs-health-proposal-detail")
    if (!panel || !form || !detail) return
    const proposal = data.proposal || {}
    const standing = proposal.proposal_id && proposal.state && proposal.state !== "none"
    panel.hidden = !standing
    if (!standing) {
      form.hidden = true
      detail.textContent = ""
      return
    }
    const action = proposal.action || {}
    const budget = Number(action.budget_usd || 0).toFixed(2)
    const phases = Array.isArray(action.phases) ? action.phases.length : 0
    detail.textContent =
      `Proposal ${proposal.proposal_id} (${proposal.state}): ${action.name || "remediation"} ` +
      `— ~$${budget}, ${phases} phases, ${action.model || "unknown model"}. ` +
      `${proposal.detail || ""}`
    form.hidden = !proposal.approvable
    form.dataset.proposalId = proposal.proposal_id
  }

  /** Paint the whole panel from one envelope. Pure render: no fetching, no state mutation. */
  function renderDocsHealth(data) {
    const panel = $("#docs-health")
    if (!panel) return
    panel.dataset.condition = String(data.condition || "unknown")
    const glyph = $("#docs-health-glyph")
    const word = $("#docs-health-word")
    const headline = $("#docs-health-headline")
    const scanned = $("#docs-health-scanned")
    if (glyph) glyph.textContent = String(data.glyph || "·")
    if (word) word.textContent = String(data.word || "UNKNOWN")
    if (headline) headline.textContent = String(data.headline || "")
    if (scanned) {
      const flag = data.flag || {}
      scanned.textContent = data.available
        ? `scanned ${docsHealthStamp(data.scan?.at)}` +
          (flag.raised ? ` · flag raised since ${docsHealthStamp(flag.since)}` : "")
        : "no scan on record"
    }
    docsHealthAxes(data.scan?.per_axis)
    docsHealthInventory(data)
    docsHealthProposal(data)
  }

  /** Paint the panel's own failure state. Never falls back to green. */
  function renderDocsHealthUnavailable(message) {
    renderDocsHealth({
      condition: "unmeasured",
      health: "red",
      word: "UNAVAILABLE",
      glyph: "?",
      headline: `Docs-health rail unreachable: ${message}`,
      available: false,
      scan: {},
      flag: {},
      proposal: {},
      inventory: [],
    })
  }

  /** Poll `/api/docs-health`. A read-only GET — it never scans and never touches the proposal. */
  async function loadDocsHealth() {
    // A poll landing mid-approval would repaint the form (and its hidden state) underneath the
    // operator's hands while their signature is in flight. Skip it; the next tick repaints.
    if (state.docsHealthApprovePending) return
    try {
      const response = await fetch("/api/docs-health")
      const data = await response.json()
      if (!response.ok) throw new Error(data.error || "docs-health unavailable")
      state.docsHealth = data
      renderDocsHealth(data)
    } catch (error) {
      renderDocsHealthUnavailable(error.message || "request failed")
    }
  }

  /**
   * Send the controller's signature.
   *
   * THE IDEMPOTENCY KEY IS DERIVED FROM THE PROPOSAL ID, not minted fresh per click like the
   * other portal mutations. That is the point: a double-click, an impatient second click while
   * the request is in flight, or a page reload followed by another click all produce the SAME
   * key, so the server replays its first answer instead of calling the gate twice. The gate's
   * atomic claim would still make a second call a no-op — but "no second call" is a better
   * property than "a second call that safely declines", and it costs one string to have.
   *
   * The exception is a RETRYABLE failure (the enqueue itself failed and the gate rolled its
   * claim back). Replaying the derived key would replay the cached failure forever, so those get
   * a fresh key — which is honest, because the rail is genuinely dispatchable again.
   */
  async function approveProposal(proposalId, by, reason, retry = false) {
    const key = retry
      ? `docs-approve:${proposalId}:${mutationKey()}`
      : `docs-approve:${proposalId}`
    const response = await fetch("/api/docs-health/approve", {
      method: "POST",
      headers: { "Content-Type": "application/json", "Idempotency-Key": key },
      body: JSON.stringify({ proposal_id: proposalId, by, reason }),
    })
    let data
    try {
      data = await response.json()
    } catch (_error) {
      data = { error: `approve failed with HTTP ${response.status}` }
    }
    return { ok: response.ok, status: response.status, data }
  }

  /** Wire the approve form. Bound once; the form itself is shown/hidden by the render. */
  function bindDocsHealthControls() {
    const form = $("#docs-health-approve-form")
    if (!form) return
    form.addEventListener("submit", async (event) => {
      event.preventDefault()
      if (state.docsHealthApprovePending) return
      const proposalId = form.dataset.proposalId || ""
      const by = $("#docs-health-by").value.trim()
      const reason = $("#docs-health-reason").value.trim()
      const result = $("#docs-health-approve-result")
      const button = $("#docs-health-approve-button")
      if (!proposalId) {
        result.textContent = "No proposal is currently rendered; refresh before approving."
        return
      }
      if (!by) {
        result.textContent = "Sign the approval: an unattributed approval is not an approval."
        return
      }
      state.docsHealthApprovePending = true
      button.disabled = true
      result.textContent = "Recording the signature…"
      try {
        let outcome = await approveProposal(proposalId, by, reason, state.docsHealthRetry)
        if (!outcome.ok && outcome.data?.retryable && !state.docsHealthRetry) {
          // Arm the fresh-key retry for the operator's NEXT click rather than silently
          // re-launching: a dispatch that failed once may have failed for a reason worth
          // reading, and this rail never spends money on the machine's initiative.
          state.docsHealthRetry = true
        }
        const data = outcome.data || {}
        result.textContent = data.detail || data.error || `approve returned HTTP ${outcome.status}`
        announce(`Docs remediation approve: ${data.outcome || outcome.status}`, true)
        if (outcome.ok) state.docsHealthRetry = false
      } catch (error) {
        result.textContent = `Approve failed: ${error.message || error}`
      } finally {
        state.docsHealthApprovePending = false
        button.disabled = false
        loadDocsHealth()
      }
    })
  }

  /* ── Flags board ─────────────────────────────────────────────────────────────────────────
     The supervisor rail is the operator's ALERT QUEUE, promoted from a buried third-column
     `details` block to a full-height board (design §4.1). Three properties matter here and
     each is implemented deliberately:

       1. Read-only. No button in this list ever sends a request; selecting a row only opens
          the Detail surface, where the deliberate Steer composer and the gated Interrupt door
          live (design §4.3, docs/supervisor_design.md).
       2. In-place updates. Rows are keyed by SESSION ID — the stable identity of the thing
          being flagged — and `flag_id` (a server-side digest of the flag's fields) is used as
          the row's revision. Keying by `flag_id` itself, which the design's wording suggests,
          would destroy and rebuild the row on every assessment change, which is precisely the
          reorder-and-steal-focus behavior the requirement exists to prevent.
       3. Three states, verbatim. Empty, flagged, and degraded/unavailable each have their own
          copy from docs/supervisor_design.md §1, and a degraded source still shows the last
          useful rows rather than blanking the board. */

  /** Live flag row handles, keyed by session id. */
  const supervisorRows = new Map()

  /** The mounted empty/degraded placeholder, when there are no rows to show. */
  let supervisorPlaceholder = null

  /** Build one flag row. Every mutable part is a permanent child, updated in place. */
  function createSupervisorRow(sessionId) {
    const button = element("button", "supervisor-flag")
    button.type = "button"
    button.dataset.sessionId = sessionId

    const heading = element("span", "supervisor-flag-heading")
    const statusWord = element("span", "flag-status")
    const title = element("strong", "supervisor-flag-title")
    heading.appendChild(statusWord)
    heading.appendChild(title)
    button.appendChild(heading)

    // `why` is the supervisor's one-sentence rationale; the CSS clamps it to two lines so a
    // long explanation cannot push the next flag off the screen (design §4.2).
    const reason = element("span", "supervisor-flag-reason")
    button.appendChild(reason)

    const meta = element("span", "supervisor-flag-meta")
    button.appendChild(meta)

    const review = element("span", "review-unavailable", "Review unavailable")
    review.hidden = true
    button.appendChild(review)

    return { node: button, button, statusWord, title, reason, meta, review, signature: null }
  }

  /** Refresh one flag row, writing only the fields whose text actually changed. */
  function updateSupervisorRow(entry, sessionId) {
    const flag = state.supervisorFlags.get(sessionId)
    if (!flag) return
    const status = supervisorStatus(flag.status)
    const selected = state.supervisorSelection?.session_id === sessionId
    const label = flag.title || sessionId
    const activity = flag.last_activity_at ? `last activity ${formatAge(flag.last_activity_at)}` : "last activity unavailable"
    const meta = `${flag.model} · flagged ${formatAge(flag.at)} · ${activity}`
    const reviewUnavailable = flag.review?.state === "unavailable"

    // `flag_id` is the server's digest of the flag's fields, so it changes exactly when the
    // assessment changes; the age string and the selection are the only other painted values.
    const signature = `${flag.flag_id || ""}|${meta}|${selected ? 1 : 0}|${reviewUnavailable ? 1 : 0}`
    if (entry.signature === signature) return
    entry.signature = signature

    setClassName(entry.button, `supervisor-flag flag-${status.className}${selected ? " selected" : ""}`)
    setAttr(entry.button, "aria-pressed", String(selected))
    setAttr(
      entry.button,
      "aria-label",
      `${status.label}: ${label}. ${flag.why}. ${reviewUnavailable ? "Review unavailable." : "Review available."}`,
    )
    applyStatusWord(entry.statusWord, status.vocabulary, "flag-status")
    setText(entry.title, flag.title || sessionId.slice(0, 18))
    setText(entry.reason, flag.why)
    setText(entry.meta, meta)
    setHidden(entry.review, !reviewUnavailable)
  }

  /**
   * Mount, retitle, or remove the board's placeholder.
   *
   * The three states are distinct on purpose: "nothing needs attention" is good news, while
   * "the supervisor's data is stale" is a caveat about the board itself and must never be
   * mistaken for the first.
   */
  function renderSupervisorPlaceholder(container, text, degraded) {
    supervisorPlaceholder = adoptPlaceholder(container, supervisorPlaceholder)
    if (!text) {
      supervisorPlaceholder?.remove()
      supervisorPlaceholder = null
      return
    }
    if (!supervisorPlaceholder) {
      supervisorPlaceholder = element("p", "empty-state")
      container.appendChild(supervisorPlaceholder)
    }
    setClassName(supervisorPlaceholder, degraded ? "error-state" : "empty-state")
    setText(supervisorPlaceholder, text)
  }

  /** Render the bounded flag rail while preserving keyboard focus by session ID. */
  function renderSupervisorFlags() {
    const container = $("#supervisor-flag-list")
    setAttr(container, "aria-busy", String(state.supervisorState === "loading"))

    const flags = Array.from(state.supervisorFlags.values())
    setText($("#supervisor-count"), flags.length)

    // Provenance line: which store answered, and whether the answer is stale (design §4.2).
    setText($("#supervisor-source"), `source: ${state.supervisorSource || "unknown"}`)

    const delayed = state.supervisorState === "degraded" || state.supervisorState === "unavailable"
    const delay = $("#supervisor-delay")
    setHidden(delay, !delayed)
    setText(
      delay,
      state.supervisorState === "unavailable"
        ? "Supervisor data unavailable; showing last useful rows"
        : `Supervisor data delayed${state.supervisorWarnings.length ? ` · ${state.supervisorWarnings[0]}` : ""}`,
    )

    renderSupervisorPlaceholder(
      container,
      flags.length > 0
        ? ""
        : delayed
          ? "Supervisor state unavailable; no retained rows to show"
          : state.supervisorState === "loading"
            ? "Loading supervisor flags…"
            : "Supervisor / no sessions need attention",
      delayed,
    )

    list.reconcile({
      container,
      keys: flags.map((flag) => flag.session_id),
      entries: supervisorRows,
      create: createSupervisorRow,
      update: updateSupervisorRow,
    })
  }

  /** Return the selected portal-owned design session, if design mode is active. */
  function selectedDesignSession() {
    return state.selectedType === "design" ? state.designSessions.get(state.selectedId) || null : null
  }

  /** Return the frozen supervisor action target selected by the operator. */
  function selectedSupervisorFlag() {
    return state.supervisorSelection
  }

  /** Render facts and capabilities for a selected supervisor assessment. */
  function renderSupervisorControls(flag) {
    const review = flag.review || { state: "unavailable" }
    const retained = state.supervisorFlags.has(flag.session_id)
    const reviewable = retained
      && !flag.mapping_changed
      && Boolean(review.cell_id)
      && review.state !== "unavailable"
    $("#supervisor-title").textContent = flag.title || flag.session_id
    $("#supervisor-session-id").textContent = flag.session_id
    $("#supervisor-model").textContent = flag.model
    $("#supervisor-status").textContent = supervisorStatus(flag.status).label
    $("#supervisor-reason").textContent = flag.why
    $("#supervisor-review").textContent = reviewable
      ? `${review.state} · ${review.cell_id} · ${review.source || "exact mapping"}`
      : flag.mapping_changed
        ? "Actions unavailable: exact stream mapping changed after selection"
        : retained
        ? "Review unavailable: no exact Redis stream mapping"
        : "Actions unavailable: flag is no longer retained"
    $("#supervisor-activity").textContent = flag.last_activity_at
      ? `${formatAge(flag.last_activity_at)} · ${flag.last_activity_at}`
      : "unavailable"
    const target = flag.title || flag.session_id.slice(0, 18)
    const steer = $("#supervisor-steer")
    steer.textContent = `Steer ${target}`
    steer.disabled = !reviewable || state.supervisorMutationPending
    $("#supervisor-interrupt").disabled = !reviewable || state.supervisorMutationPending || state.supervisorInterrupted
    $("#detach-supervisor").disabled = !state.attached
  }

  /** Return the selected Claude background-session roster entry, if selected. */
  function selectedClaudeAgent() {
    return state.selectedType === "claude_agent"
      ? state.claudeAgents.get(state.selectedClaudeAgentId) || null
      : null
  }

  /* ── Sessions board ──────────────────────────────────────────────────────────────────────
     Two session fleets share one management board (design §6): portal-owned DESIGN sessions
     and CLAUDE background sessions. Both are polled lists, so both go through the same keyed
     reconciler as the fleet and the flag rail — a 10s poll must not rebuild a roster the
     operator is reading, and selecting a row must survive the next poll.

     Ownership is mirrored, never invented: `owned` comes from the backend, which enforces the
     same gate server-side (`_require_owned_claude_agent`). The chip is a read/act signal for
     the operator, not the authorization itself. */

  /** Live recent-design row handles, keyed by portal id. */
  const designRows = new Map()

  /** The "no sessions yet" placeholder for the recent list. */
  let designPlaceholder = null

  /** Build one recent-design row. */
  function createDesignRow(portalId) {
    const button = element("button", "recent-design")
    button.type = "button"
    button.dataset.portalId = portalId
    const title = element("span", "recent-design-title")
    const meta = element("span", "recent-design-meta")
    button.appendChild(title)
    button.appendChild(meta)
    return { node: button, button, title, meta, signature: null }
  }

  /** Refresh one recent-design row in place. */
  function updateDesignRow(entry, portalId) {
    const session = state.designSessions.get(portalId)
    if (!session) return
    const selected = state.selectedType === "design" && state.selectedId === portalId
    const meta = `${session.kind} · ${session.draft_state.replaceAll("_", " ")} · r${session.revision}`
    const signature = `${session.title}|${meta}|${selected ? 1 : 0}`
    if (entry.signature === signature) return
    entry.signature = signature
    setClassName(entry.button, `recent-design${selected ? " selected" : ""}`)
    setAttr(entry.button, "aria-pressed", String(selected))
    setText(entry.title, session.title)
    setText(entry.meta, meta)
  }

  /** Render the portal-owned design sessions as a keyed, in-place list. */
  function renderRecentDesigns() {
    const container = $("#recent-design-list")
    const sessions = Array.from(state.designSessions.values())

    designPlaceholder = adoptPlaceholder(container, designPlaceholder)
    if (sessions.length === 0 && !designPlaceholder) {
      designPlaceholder = element("p", "empty-state", "No portal-owned design sessions yet.")
      container.appendChild(designPlaceholder)
    } else if (sessions.length > 0 && designPlaceholder) {
      designPlaceholder.remove()
      designPlaceholder = null
    }

    list.reconcile({
      container,
      keys: sessions.map((session) => session.portal_id),
      entries: designRows,
      create: createDesignRow,
      update: updateDesignRow,
    })
  }

  /**
   * Fill the Detail surface's glance line: phase, then cost and tokens (design §3.2 steps 3-4).
   *
   * These are the two facts an operator wants immediately after "is it healthy": how far
   * through the workflow the cell is, and what it has spent so far. Both come from the same
   * retained snapshot the fleet card uses, so the sheet can never disagree with the card that
   * opened it. Surfaces without per-cell telemetry (design sessions, supervisor flags, Claude
   * background sessions) pass `null` and the line is hidden rather than shown as blank.
   */
  function renderDetailGlance(cellId) {
    const phase = $("#selected-phase")
    const glance = $("#selected-glance")
    if (!cellId) {
      setHidden(phase, true)
      setHidden(glance, true)
      return
    }

    const label = phaseLabel(cellId)
    setHidden(phase, !label)
    if (label) setText(phase, label)

    const samples = samplesForCell(cellId)
    const costs = samples.map((sample) => core.safeNumber(sample.cost)).filter((value) => value !== null)
    const totalCost = costs.reduce((sum, value) => sum + value, 0)
    const inputTokens = samples.map((sample) => core.safeNumber(sample.input_tokens))
      .filter((value) => value !== null).reduce((sum, value) => sum + value, 0)
    const outputTokens = samples.map((sample) => core.safeNumber(sample.output_tokens))
      .filter((value) => value !== null).reduce((sum, value) => sum + value, 0)

    setHidden(glance, samples.length === 0)
    setText($("#selected-cost"), costs.length ? `${formatCost(totalCost)} reported` : "no cost reported")
    setText($("#selected-tokens"), `${compactTokens(inputTokens)} in · ${compactTokens(outputTokens)} out`)
  }

  /** Mirror authoritative draft capabilities into the design control pane. */
  function renderDesignControls(session) {
    const draft = state.draftState
    $("#design-kind").textContent = session.kind === "workflow" ? "WORKFLOW DESIGN" : "EXPERIMENT DESIGN"
    $("#design-portal-id").textContent = session.portal_id
    $("#design-opencode-id").textContent = session.opencode_session_id || "Unavailable"
    $("#design-session-model").textContent = session.model
    $("#design-session-workdir").textContent = session.workdir_label
    $("#design-draft-name").textContent = session.draft_name
    $("#design-revision").textContent = String(draft?.revision ?? session.revision ?? 0)

    const draftState = draft?.draft_state || session.draft_state || "no_draft"
    const savedCurrent = Boolean(draft?.saved && draft.saved.revision === draft.revision)
    const displayState = savedCurrent
      ? "SAVED"
      : draftState === "valid" && session.saved_revision
        ? "VALID / UNSAVED CHANGES"
        : draftState.replaceAll("_", " ").toUpperCase()
    const badge = $("#validation-badge")
    badge.textContent = displayState
    badge.className = `validation-badge validation-${draft?.validation?.valid ? "valid" : "invalid"}`
    const errors = Array.isArray(draft?.validation?.errors) ? draft.validation.errors : []
    $("#validation-summary").textContent = draft?.validation?.valid
      ? session.kind === "experiment"
        ? `Spec valid · ${draft.matrix?.count ?? 0} cells`
        : "Spec valid · workflow ready"
      : draft?.capabilities?.reason || (errors.length ? `${errors.length} validation error${errors.length === 1 ? "" : "s"}` : "Waiting for the assigned draft.")
    const errorList = $("#validation-errors")
    errorList.replaceChildren(...errors.map((message) => element("li", "", message)))

    const matrix = $("#matrix-preview")
    matrix.hidden = !draft?.matrix
    if (draft?.matrix) {
      $("#matrix-summary").textContent = `${draft.matrix.count} cells${draft.matrix.truncated ? ` · first ${draft.matrix.preview.length} shown` : ""}`
      $("#matrix-cells").textContent = draft.matrix.preview.map((cell) => JSON.stringify(cell)).join("\n")
    }
    $("#save-spec-button").disabled = !state.draftFresh || !draft?.capabilities?.save || state.designMutationPending
    const runForm = $("#run-workflow-form")
    runForm.hidden = session.kind !== "workflow"
    $("#run-workflow-button").disabled = !state.draftFresh || !draft?.capabilities?.run || state.designMutationPending
  }

  /** Render the roster-derived fields and lifecycle affordances for one selected agent. */
  function renderClaudeAgentControls(entry) {
    $("#claude-agent-control-id").textContent = entry.id
    $("#claude-agent-control-status").textContent = String(entry.status || "unknown").toUpperCase()
    $("#claude-agent-control-ownership").textContent = entry.owned
      ? "OWNED — full lifecycle control"
      : "EXTERNAL — not started here; manage it with the claude CLI directly"
    $("#claude-agent-control-model").textContent = entry.model || "Unknown model"
    $("#claude-agent-control-cwd").textContent = entry.cwd || "Unknown workdir"
    $("#claude-agent-owned-controls").hidden = !entry.owned
    $("#claude-agent-steer-form").hidden = !entry.owned
    $("#claude-agent-external-controls").hidden = entry.owned
    $("#claude-agent-transcript-note").textContent = entry.owned
      ? entry.relay_active === false
        ? "Transcript relay paused (fleet at capacity)."
        : "Claude transcripts are a best-effort, tail-bounded relay of “recent output,” not a gapless history API."
      : "External session — showing a one-shot, best-effort log tail only, not a live stream."
  }

  /** Live Claude roster card handles, keyed by session id. */
  const claudeAgentCards = new Map()

  /** The roster's empty/unavailable placeholder. */
  let claudeAgentPlaceholder = null

  /** Build one Claude background-session card (same card shape as a fleet cell). */
  function createClaudeAgentCard(agentId) {
    const card = element("article", "cell-card claude-agent-card")
    const button = element("button", "cell-select")
    button.type = "button"
    button.title = agentId
    button.dataset.claudeAgentId = agentId

    const heading = element("div", "cell-heading")
    const statusWord = element("span", "status-word")
    const ownership = element("span", "ownership-chip")
    heading.appendChild(statusWord)
    heading.appendChild(ownership)
    button.appendChild(heading)
    button.appendChild(element("span", "cell-id", agentId))

    const task = element("span", "claude-agent-task")
    const meta = element("span", "claude-agent-meta")
    button.appendChild(task)
    button.appendChild(meta)
    card.appendChild(button)
    return { node: card, card, button, statusWord, ownership, task, meta, signature: null }
  }

  /**
   * Refresh one roster card in place.
   *
   * `row` is the reconciler's DOM handle; `entry` is the roster record from the API, keeping
   * the same name the rest of the Claude-agent code uses for a roster entry.
   */
  function updateClaudeAgentCard(row, agentId) {
    const entry = state.claudeAgents.get(agentId)
    if (!entry) return
    // The roster reports its own status strings; anything outside the known lifecycle set is
    // shown as UNKNOWN rather than silently colored as something it is not.
    const knownStatuses = new Set(["queued", "running", "done", "failed", "timeout"])
    const raw = String(entry.status || "unknown").toLowerCase()
    const vocabulary = fleet.lifecycle(knownStatuses.has(raw) ? raw : "unknown")
    const selected = state.selectedType === "claude_agent" && state.selectedClaudeAgentId === agentId
    const task = entry.task || entry.title || "No task recorded"
    const meta = `${entry.model || "unknown model"} · ${entry.cwd || "unknown cwd"}`
    const signature = `${vocabulary.key}|${entry.owned ? 1 : 0}|${task}|${meta}|${selected ? 1 : 0}`
    if (row.signature === signature) return
    row.signature = signature

    setClassName(row.card, `cell-card claude-agent-card ${vocabulary.className}${selected ? " selected" : ""}`)
    setAttr(row.button, "aria-pressed", String(selected))
    setAttr(row.button, "aria-label", `${entry.owned ? "Owned" : "External"} Claude background session ${agentId}`)
    applyStatusWord(row.statusWord, vocabulary)
    setClassName(row.ownership, `ownership-chip ${entry.owned ? "owned" : "external"}`)
    setText(row.ownership, entry.owned ? "OWNED" : "EXTERNAL")
    setText(row.task, task)
    setText(row.meta, meta)
  }

  /** Render urgency-agnostic Claude background-session cards, owned first. */
  function renderClaudeAgentGrid() {
    const container = $("#claude-agent-grid")
    setAttr(container, "aria-busy", "false")
    const entries = Array.from(state.claudeAgents.values())

    claudeAgentPlaceholder = adoptPlaceholder(container, claudeAgentPlaceholder)
    const placeholderText = state.claudeAgentsUnavailable
      ? "Supervisor not running — start scripts/claude_agents_supervisor.py to see the roster."
      : entries.length === 0
        ? "No Claude background sessions observed."
        : ""
    if (placeholderText) {
      if (!claudeAgentPlaceholder) {
        claudeAgentPlaceholder = element("p", "empty-state")
        container.appendChild(claudeAgentPlaceholder)
      }
      setText(claudeAgentPlaceholder, placeholderText)
    } else if (claudeAgentPlaceholder) {
      claudeAgentPlaceholder.remove()
      claudeAgentPlaceholder = null
    }

    list.reconcile({
      container,
      keys: entries.map((agent) => agent.id),
      entries: claudeAgentCards,
      create: createClaudeAgentCard,
      update: updateClaudeAgentCard,
    })
    setText($("#claude-agent-total"), entries.length)
  }

  /** Fill the start-session workdir control from backend-owned approved labels. */
  function renderClaudeAgentWorkdirOptions() {
    const select = $("#claude-agent-workdir")
    const previous = select.value
    select.replaceChildren()
    for (const item of state.approvedClaudeAgentWorkdirs) {
      const option = element("option", "", item.label)
      option.value = item.key
      select.appendChild(option)
    }
    if (state.approvedClaudeAgentWorkdirs.some((item) => item.key === previous)) select.value = previous
  }

  /** Render the always-visible, read-only daemon panel (no control affordance here). */
  function renderClaudeAgentDaemon() {
    const daemon = state.claudeAgentDaemon || { running: false }
    $("#daemon-status").textContent = daemon.running ? "RUNNING" : "NOT RUNNING"
    $("#daemon-pid").textContent = daemon.pid ? String(daemon.pid) : "--"
  }

  /** Synchronize terminal and control headers with any of the three selection kinds. */
  function renderSelection() {
    const cellId = state.selectedId
    const supervisor = selectedSupervisorFlag()
    // An unmapped supervisor selection owns the action pane while the prior
    // design stream may remain attached behind it for non-destructive review.
    const design = supervisor ? null : selectedDesignSession()
    const claudeAgent = selectedClaudeAgent()
    $("#cell-control-panel").hidden = Boolean(design || supervisor || claudeAgent)
    $("#design-control-panel").hidden = !design
    $("#supervisor-control-panel").hidden = !supervisor
    $("#claude-agent-control-panel").hidden = !claudeAgent
    $("#transcript-mode").textContent = design ? "Design / Terminal" : claudeAgent ? "Claude background session" : "Cell / Transcript"
    $("#control-mode").textContent = design
      ? "Portal-owned session"
      : supervisor
        ? "Human-reviewed supervisor flag"
        : claudeAgent
          ? (claudeAgent.owned ? "Portal-owned background session" : "External background session — read only")
          : "Read-only attachment"
    $("#ownership-badge").textContent = design ? "INTERACTIVE" : supervisor ? "HUMAN ACTION" : claudeAgent ? (claudeAgent.owned ? "OWNED" : "EXTERNAL") : "READ ONLY"
    $("#ownership-badge").className = (design || supervisor || claudeAgent?.owned) ? "interactive-badge" : "readonly-badge"
    if (design) {
      $("#transcript-title").textContent = design.title
      applyStatusWord($("#selected-status"), { ...fleet.lifecycle("running"), word: design.lifecycle_state.toUpperCase() })
      $("#selected-stream-state").textContent = state.streamState.toUpperCase()
      renderDetailGlance(null)
      renderDesignControls(design)
      renderRecentDesigns()
      return
    }
    if (supervisor) {
      const reviewing = state.selectedType === "supervisor" && state.selectedId === supervisor.review?.cell_id
      if (reviewing) {
        $("#transcript-mode").textContent = "Supervisor / Observed activity"
        $("#transcript-title").textContent = supervisor.title || supervisor.session_id
        const assessment = supervisorStatus(supervisor.status)
        applyStatusWord($("#selected-status"), assessment.vocabulary)
        $("#selected-stream-state").textContent = state.streamState.toUpperCase()
      }
      renderDetailGlance(null)
      renderSupervisorControls(supervisor)
      renderSupervisorFlags()
      renderRecentDesigns()
      return
    }
    if (claudeAgent) {
      const status = String(claudeAgent.status || "unknown").toLowerCase()
      $("#transcript-title").textContent = claudeAgent.id
      applyStatusWord($("#selected-status"), fleet.lifecycle(status))
      $("#selected-stream-state").textContent = state.streamState.toUpperCase()
      renderDetailGlance(null)
      renderClaudeAgentControls(claudeAgent)
      renderRecentDesigns()
      return
    }
    const status = cellId ? core.normalizeStatus(state.cells[cellId]) : "unknown"
    $("#transcript-title").textContent = cellId || "NO CELL SELECTED"
    applyStatusWord($("#selected-status"), fleet.lifecycle(status))
    renderDetailGlance(cellId)
    $("#selected-stream-state").textContent = state.streamState.toUpperCase()
    $("#control-cell").textContent = cellId || "No cell selected"
    $("#control-status").textContent = status.toUpperCase()
    $("#control-stream").textContent = state.streamState.toUpperCase()

    const sessionId = state.selectedSessionIds.at(-1)
    $("#control-session").textContent = sessionId || "Session identity not observed yet"
    $("#copy-session").hidden = !sessionId

    const action = $("#watch-button")
    action.disabled = !cellId
    action.textContent = !cellId
      ? "Select a cell"
      : state.attached
        ? "Detach"
        : status === "running"
          ? "Watch"
          : "Inspect retained history"
    const guidance = !cellId
      ? "Select a cell to inspect telemetry."
      : status === "queued"
        ? "Waiting for worker"
        : core.TERMINAL_STATUSES.has(status)
          ? "Inspecting retained history"
          : state.attached
            ? "Watching the existing event stream"
            : "Selected but detached"
    $("#control-guidance").textContent = guidance
    renderRecentDesigns()
  }

  /** Render normalized transcript rows and preserve follow only when requested. */
  function renderTranscript(scrollToBottom = false) {
    const feed = $("#transcript-feed")
    feed.replaceChildren()
    const design = selectedDesignSession()
    if (!state.selectedId) {
      feed.appendChild(element("div", "terminal-empty", "Select a fleet card to inspect retained events and watch live work."))
    } else if (state.rows.length === 0) {
      const message = state.streamState === "connecting"
        ? "Connecting to retained history…"
        : design
          ? "No retained design-session events observed yet."
          : "No retained events observed for this cell."
      feed.appendChild(element("div", "terminal-empty", message))
    } else {
      for (const row of state.rows) feed.appendChild(createTranscriptRow(row))
    }
    if (scrollToBottom && state.follow) feed.scrollTop = feed.scrollHeight
    $("#jump-live").hidden = state.follow
  }

  /** Build one terminal row with collapsed, safely escaped details. */
  function createTranscriptRow(row) {
    const node = element("article", `transcript-row row-${row.kind}`)
    const meta = element("div", "row-meta")
    meta.appendChild(element("time", "row-time", row.timestamp))
    meta.appendChild(element("span", "row-label", row.label))
    node.appendChild(meta)
    if (row.kind === "spec") {
      if (row.latest) {
        node.appendChild(element("pre", "row-yaml", row.text))
      } else {
        const previous = element("details", "row-details")
        previous.appendChild(element("summary", "", `Show previous revision ${row.revision}`))
        previous.appendChild(element("pre", "row-yaml", row.text))
        node.appendChild(previous)
      }
    } else {
      node.appendChild(element("div", "row-text", row.text))
    }
    if (row.detail) {
      const details = element("details", "row-details")
      details.appendChild(element("summary", "", "Show escaped payload"))
      details.appendChild(element("pre", "row-payload", row.detail))
      node.appendChild(details)
    }
    return node
  }

  /** Add one event sample to bounded live overlays and the rolling burn ledger. */
  function recordLiveSample(cellId, sample) {
    const current = state.liveSamplesByCell.get(cellId) || []
    // The next matrix request that starts after this observation owns the
    // replacement snapshot. Request sequence is unambiguous even when two
    // legitimate events have byte-identical telemetry.
    const observed = { ...sample, observed_after_matrix_request: state.matrixRequestSequence }
    state.liveSamplesByCell.set(
      cellId,
      core.boundedAppend(current, [observed], MAX_LIVE_SAMPLES_PER_CELL),
    )
    if (sample.cost !== null) {
      state.burnSamples.push({ identity: sample.identity, cost: sample.cost, receivedAt: Date.now() })
    }
  }

  /** Remember the latest event occurrences within the retained-log bound. */
  function rememberEvent(rawIdentity) {
    state.eventLedgerOrder.push(rawIdentity)
    state.eventLedgerCounts.set(rawIdentity, (state.eventLedgerCounts.get(rawIdentity) || 0) + 1)
    while (state.eventLedgerOrder.length > MAX_TRANSCRIPT_ROWS) {
      const oldest = state.eventLedgerOrder.shift()
      const remaining = (state.eventLedgerCounts.get(oldest) || 1) - 1
      if (remaining > 0) state.eventLedgerCounts.set(oldest, remaining)
      else state.eventLedgerCounts.delete(oldest)
    }
  }

  /** Initialize one replay pass from the occurrences already presented. */
  function beginReplay() {
    state.replayMode = true
    state.replaySkipCounts = new Map(state.eventLedgerCounts)
    state.replaySeenCounts = new Map()
    state.replayTail = []
    state.raceDuplicateCounts = new Map()
    state.raceDedupeExpiresAt = 0
  }

  /** Return whether this retained occurrence was already presented earlier. */
  function isKnownReplayOccurrence(rawIdentity) {
    const occurrence = (state.replaySeenCounts.get(rawIdentity) || 0) + 1
    state.replaySeenCounts.set(rawIdentity, occurrence)
    return occurrence <= (state.replaySkipCounts.get(rawIdentity) || 0)
  }

  /**
   * Suppress only the immediate subscribe-before-history overlap.
   *
   * Redis subscription starts before history is read, so a just-published
   * event can occur once in replay and once in the queued live messages. The
   * short, bounded tail avoids suppressing legitimate identical future events.
   */
  function isReplayRaceDuplicate(rawIdentity) {
    if (Date.now() > state.raceDedupeExpiresAt) {
      state.raceDuplicateCounts.clear()
      return false
    }
    const remaining = state.raceDuplicateCounts.get(rawIdentity) || 0
    if (remaining === 0) return false
    if (remaining === 1) state.raceDuplicateCounts.delete(rawIdentity)
    else state.raceDuplicateCounts.set(rawIdentity, remaining - 1)
    return true
  }

  /** Normalize, reconcile, account for, and optionally buffer a stream event. */
  function receiveEvent(raw) {
    if (!state.selectedId) return
    const rawIdentity = String(raw ?? "")
    if (state.replayMode) {
      state.replayTail = core.boundedAppend(state.replayTail, [rawIdentity], REPLAY_RACE_TAIL)
      if (isKnownReplayOccurrence(rawIdentity)) return
    } else if (isReplayRaceDuplicate(rawIdentity)) {
      return
    }
    const row = core.normalizeTranscriptEvent(raw, state.selectedId)
    rememberEvent(rawIdentity)
    state.lastEventAt = Date.now()
    state.streamState = "live"
    if (row.sessionId && !state.selectedSessionIds.includes(row.sessionId)) state.selectedSessionIds.push(row.sessionId)
    if (row.sample && !state.replayMode) recordLiveSample(state.selectedId, row.sample)

    if (state.paused) {
      state.buffer = core.boundedAppend(state.buffer, [row], MAX_TRANSCRIPT_ROWS)
      $("#pause-button").textContent = `Resume (${state.buffer.length} buffered)`
    } else {
      const shouldFollow = state.follow && isTranscriptAtBottom()
      state.rows = core.boundedAppend(state.rows, [row], MAX_TRANSCRIPT_ROWS)
      renderTranscript(shouldFollow)
    }
    renderSelection()
    renderFleet()
    if (state.selectedType === "design") void loadDraftState()
  }

  /** Append one browser-generated artifact row within the shared transcript cap. */
  function appendLocalRow(row) {
    const shouldFollow = state.follow && isTranscriptAtBottom()
    state.rows = core.boundedAppend(state.rows, [{
      key: `${state.selectedId}-${Date.now()}-${row.kind}`,
      timestamp: `${new Date().toISOString().slice(11, 19)} UTC`,
      detail: "",
      ...row,
    }], MAX_TRANSCRIPT_ROWS)
    renderTranscript(shouldFollow)
  }

  /** Poll the assigned artifact and add rows only when its coherent state changes. */
  async function loadDraftState() {
    const session = selectedDesignSession()
    if (!session || state.draftRequestInFlight) return
    const selectedAtRequest = session.portal_id
    state.draftRequestInFlight = true
    try {
      const response = await fetch(`/api/design-sessions/${encodeURIComponent(selectedAtRequest)}/spec`)
      const draft = await response.json()
      if (!response.ok) throw new Error(draft.error || "Draft state unavailable")
      if (state.selectedType !== "design" || state.selectedId !== selectedAtRequest) return
      const previous = state.draftState
      const signature = JSON.stringify([
        draft.revision,
        draft.draft_state,
        draft.validation?.errors,
        draft.saved?.revision,
        draft.matrix?.count,
        draft.capabilities?.reason,
      ])
      state.draftState = draft
      state.draftFresh = true
      if (draft.yaml && draft.revision !== previous?.revision) {
        for (const row of state.rows) {
          if (row.kind === "spec") row.latest = false
        }
        appendLocalRow({
          kind: "spec",
          label: "SPEC",
          text: draft.yaml,
          revision: draft.revision,
          latest: true,
        })
      }
      if (signature !== state.draftSignature) {
        const valid = draft.validation?.valid === true
        const matrixText = session.kind === "experiment"
          ? ` · ${draft.matrix?.count ?? 0} cells`
          : " · workflow ready"
        appendLocalRow({
          kind: valid ? "validate-pass" : "validate-error",
          label: valid ? "VALIDATE PASS" : "VALIDATE ERROR",
          text: valid
            ? `spec valid${matrixText}`
            : draft.validation?.errors?.join("\n") || draft.capabilities?.reason || "Waiting for draft",
        })
        state.draftSignature = signature
        announce(valid ? "ExperimentSpec validation passed" : "ExperimentSpec validation changed")
      }
      renderSelection()
    } catch (error) {
      if (state.selectedType === "design" && state.selectedId === selectedAtRequest) {
        state.draftFresh = false
        $("#validation-badge").textContent = "VALIDATION STALE"
        $("#validation-summary").textContent = error.message || "Draft state unavailable"
        $("#save-spec-button").disabled = true
        $("#run-workflow-button").disabled = true
        announce("Draft validation is unavailable; mutation controls are disabled", true)
      }
    } finally {
      state.draftRequestInFlight = false
    }
  }

  /** Detect whether insertion should retain automatic bottom alignment. */
  function isTranscriptAtBottom() {
    const feed = $("#transcript-feed")
    return feed.scrollHeight - feed.scrollTop - feed.clientHeight < 28
  }

  /** Close the previous cell source and attach to the selected raw SSE stream. */
  function connectSelectedStream() {
    if (!state.selectedId) return
    const selectedAtConnect = state.selectedId
    state.streamState = "connecting"
    state.attached = true
    beginReplay()
    state.eventSource = core.replaceEventSource(
      state.eventSource,
      EventSource,
      `/api/events/${encodeURIComponent(selectedAtConnect)}`,
    )
    const source = state.eventSource
    source.onopen = () => {
      if (source !== state.eventSource) return
      state.streamState = "live"
      beginReplay()
      renderSelection()
    }
    source.addEventListener("replay_complete", () => {
      if (source !== state.eventSource) return
      state.replayMode = false
      state.raceDuplicateCounts = new Map()
      for (const identity of state.replayTail) {
        state.raceDuplicateCounts.set(identity, (state.raceDuplicateCounts.get(identity) || 0) + 1)
      }
      state.raceDedupeExpiresAt = Date.now() + REPLAY_RACE_WINDOW_MS
      state.streamState = "live"
      renderSelection()
    })
    source.onmessage = (event) => {
      if (source === state.eventSource && state.selectedId === selectedAtConnect) receiveEvent(event.data)
    }
    source.onerror = () => {
      if (source !== state.eventSource || !state.attached) return
      state.streamState = source.readyState === EventSource.CLOSED ? "unavailable" : "reconnecting"
      beginReplay()
      renderSelection()
      announce(
        state.streamState === "unavailable"
          ? `Event stream unavailable for ${selectedAtConnect}`
          : `Event stream reconnecting for ${selectedAtConnect}`,
        true,
      )
    }
    renderSelection()
    renderTranscript(false)
  }

  /** Select one global cell and hand off the single selected-cell EventSource. */
  function selectCell(cellId, attach) {
    const changed = state.selectedId !== cellId || state.selectedType !== "cell"
    if (changed) {
      if (state.eventSource) state.eventSource.close()
      state.eventSource = null
      state.selectedId = cellId
      state.selectedType = "cell"
      state.supervisorSelection = null
      state.supervisorInterrupted = false
      state.draftState = null
      state.draftSignature = null
      state.draftFresh = false
      if (state.draftPollTimer) window.clearInterval(state.draftPollTimer)
      state.draftPollTimer = null
      try { window.localStorage.removeItem("control-room-selected-design") } catch (_error) {}
      state.selectedSessionIds = []
      state.rows = []
      state.buffer = []
      state.eventLedgerCounts = new Map()
      state.eventLedgerOrder = []
      state.replaySkipCounts = new Map()
      state.replaySeenCounts = new Map()
      state.replayTail = []
      state.raceDuplicateCounts = new Map()
      state.paused = false
      state.follow = true
      state.attached = false
      state.streamState = "disconnected"
      $("#pause-button").textContent = "Pause"
      announce(`Selected cell ${cellId}`)
    }
    renderFleet()
    renderSelection()
    renderTranscript(false)
    if (attach && !state.attached) connectSelectedStream()
  }

  /** Select a portal-owned design identity and hand off the same detail source. */
  function selectDesignSession(portalId, attach) {
    const session = state.designSessions.get(portalId)
    if (!session) return
    const changed = state.selectedId !== portalId || state.selectedType !== "design"
    if (changed) {
      if (state.eventSource) state.eventSource.close()
      state.eventSource = null
      state.selectedId = portalId
      state.selectedType = "design"
      state.supervisorSelection = null
      state.supervisorInterrupted = false
      state.selectedSessionIds = session.opencode_session_id ? [session.opencode_session_id] : []
      state.rows = []
      state.buffer = []
      state.eventLedgerCounts = new Map()
      state.eventLedgerOrder = []
      state.replaySkipCounts = new Map()
      state.replaySeenCounts = new Map()
      state.replayTail = []
      state.raceDuplicateCounts = new Map()
      state.paused = false
      state.follow = true
      state.attached = false
      state.streamState = "disconnected"
      state.draftState = null
      state.draftSignature = null
      state.draftFresh = false
      $("#design-prompt").value = ""
      $("#design-input-result").textContent = ""
      $("#save-spec-result").textContent = ""
      $("#run-workflow-result").textContent = ""
      $("#pause-button").textContent = "Pause"
      $("#run-goal").value = session.intent
      $("#run-model").value = session.model
      $("#run-workdir").value = session.workdir
      try { window.localStorage.setItem("control-room-selected-design", portalId) } catch (_error) {}
      announce(`Selected ${session.kind} design session ${portalId}`)
    }
    renderFleet()
    renderSelection()
    renderTranscript(false)
    if (attach && !state.attached) connectSelectedStream()
    void loadDraftState()
    if (state.draftPollTimer) window.clearInterval(state.draftPollTimer)
    state.draftPollTimer = window.setInterval(loadDraftState, DRAFT_POLL_MS)
  }

  /** Select a flag and hand its exact mapped cell to the sole detail stream. */
  function selectSupervisorFlag(sessionId) {
    const current = state.supervisorFlags.get(sessionId)
    if (!current) return
    const reviewable = Boolean(current.review?.cell_id) && current.review.state !== "unavailable"
    state.supervisorSelection = {
      ...current,
      review: { ...(current.review || {}) },
      mapping_changed: false,
    }
    state.supervisorInterrupted = false
    state.supervisorSteerKey = null
    state.supervisorSteerSignature = null
    state.supervisorInterruptKey = null
    $("#supervisor-steer-prompt").value = ""
    $("#supervisor-steer-result").textContent = ""
    $("#supervisor-interrupt-result").textContent = ""
    closeSupervisorInterruptDoor(false)

    if (!reviewable) {
      // The existing transcript intentionally stays attached. A guessed cell
      // would be more dangerous than showing only the assessment details.
      renderSupervisorFlags()
      renderSelection()
      announce(`Selected supervisor flag for ${sessionId}; review unavailable`)
      return
    }

    if (state.eventSource) state.eventSource.close()
    state.eventSource = null
    state.selectedId = current.review.cell_id
    state.selectedType = "supervisor"
    state.selectedSessionIds = [current.session_id]
    state.rows = []
    state.buffer = []
    state.eventLedgerCounts = new Map()
    state.eventLedgerOrder = []
    state.replaySkipCounts = new Map()
    state.replaySeenCounts = new Map()
    state.replayTail = []
    state.raceDuplicateCounts = new Map()
    state.paused = false
    state.follow = true
    state.attached = false
    state.streamState = "disconnected"
    state.draftState = null
    state.draftSignature = null
    state.draftFresh = false
    if (state.draftPollTimer) window.clearInterval(state.draftPollTimer)
    state.draftPollTimer = null
    $("#pause-button").textContent = "Pause"
    try { window.localStorage.removeItem("control-room-selected-design") } catch (_error) {}
    renderFleet()
    renderSupervisorFlags()
    renderSelection()
    renderTranscript(false)
    connectSelectedStream()
    announce(`Reviewing observed activity for ${sessionId}`)
  }

  /** Select a Claude background session and hand off the same detail source.
   *
   * Only owned sessions attach the shared SSE stream (§1.4:
   * ``claude_bg_<id>`` is exactly the existing ``/api/events/<cell_id>``
   * route). External sessions never attach — they render a one-shot
   * ``/logs`` fetch instead of a live transcript.
   */
  function selectClaudeAgent(id, attach) {
    const entry = state.claudeAgents.get(id)
    if (!entry) return
    const cellId = `${CLAUDE_AGENT_CELL_PREFIX}${id}`
    const changed = state.selectedId !== cellId || state.selectedType !== "claude_agent"
    if (changed) {
      if (state.eventSource) state.eventSource.close()
      state.eventSource = null
      state.selectedId = cellId
      state.selectedType = "claude_agent"
      state.selectedClaudeAgentId = id
      state.selectedSessionIds = []
      state.rows = []
      state.buffer = []
      state.eventLedgerCounts = new Map()
      state.eventLedgerOrder = []
      state.replaySkipCounts = new Map()
      state.replaySeenCounts = new Map()
      state.replayTail = []
      state.raceDuplicateCounts = new Map()
      state.paused = false
      state.follow = true
      state.attached = false
      state.streamState = "disconnected"
      state.draftState = null
      $("#claude-agent-action-result").textContent = ""
      $("#claude-agent-external-log").textContent = ""
      $("#pause-button").textContent = "Pause"
      announce(`Selected Claude background session ${id}`)
    }
    renderClaudeAgentGrid()
    renderSelection()
    renderTranscript(false)
    if (entry.owned && attach && !state.attached) connectSelectedStream()
  }

  /** Detach the browser only; no process or Redis control request is made. */
  function detachSelectedStream() {
    if (state.eventSource) state.eventSource.close()
    state.eventSource = null
    state.attached = false
    state.streamState = "disconnected"
    state.replayMode = true
    renderSelection()
    announce(`Detached from ${state.selectedId}`)
  }

  /** Drop overlays once a matrix request started after they were observed. */
  function pruneReconciledSamples(snapshotRequestSequence) {
    for (const [cellId, samples] of state.liveSamplesByCell.entries()) {
      // Samples arriving during this request remain until the next snapshot,
      // because the current Redis read may have happened before their publish.
      const remaining = samples.filter(
        (sample) => sample.observed_after_matrix_request >= snapshotRequestSequence,
      )
      if (remaining.length > 0) state.liveSamplesByCell.set(cellId, remaining)
      else state.liveSamplesByCell.delete(cellId)
    }
  }

  /** Merge newer status-stream transitions over a potentially older snapshot. */
  function applyStatusOverrides(snapshotCells) {
    const cells = { ...snapshotCells }
    for (const [cellId, override] of state.statusOverrides.entries()) {
      if (core.normalizeStatus(cells[cellId]) === core.normalizeStatus(override.status)) {
        state.statusOverrides.delete(cellId)
        continue
      }
      if (override.remainingSnapshots > 0) {
        cells[cellId] = override.status
        override.remainingSnapshots -= 1
      } else {
        // Repeated matrix disagreement wins if the status stream missed a later transition.
        state.statusOverrides.delete(cellId)
      }
    }
    return cells
  }

  /** Replace the retained snapshot while preserving last-known state on errors. */
  async function loadMatrix() {
    // One request at a time prevents both stale overwrites and slow-endpoint starvation.
    if (state.matrixRequestInFlight) return
    state.matrixRequestInFlight = true
    const requestSequence = ++state.matrixRequestSequence
    try {
      const response = await fetch("/api/matrix")
      const data = await response.json()
      if (!response.ok || data.error) {
        state.matrixState = response.status === 503 ? "unavailable" : "disconnected"
        state.firstMatrixLoaded = true
        announce(response.status === 503 ? "Redis unavailable" : "Fleet snapshot unavailable", true)
        renderFleet()
        return
      }
      const snapshotCells = data.cells && typeof data.cells === "object" ? data.cells : {}
      state.cells = applyStatusOverrides(snapshotCells)
      state.stages = data.stages && typeof data.stages === "object" ? data.stages : {}
      state.phases = data.phases && typeof data.phases === "object" ? data.phases : {}
      state.telemetry = data.telemetry && typeof data.telemetry === "object"
        ? data.telemetry
        : { cells: {}, reported_cost: null, input_tokens: null, output_tokens: null }
      state.matrixState = state.telemetry.available === false ? "disconnected" : "live"
      state.lastMatrixAt = Date.now()
      pruneReconciledSamples(requestSequence)
      renderFleet()
      renderPipelineStages()
      renderSelection()

      // Auto-selection is intentionally limited to the unambiguous one-runner arrival case.
      if (!state.firstMatrixLoaded && !state.selectedId) {
        const running = Object.keys(state.cells).filter((cellId) => core.normalizeStatus(state.cells[cellId]) === "running")
        if (running.length === 1) selectCell(running[0], true)
      }
      state.firstMatrixLoaded = true
    } catch (_error) {
      state.matrixState = "disconnected"
      state.firstMatrixLoaded = true
      announce("Fleet snapshot disconnected; showing last known data", true)
      renderFleet()
    } finally {
      state.matrixRequestInFlight = false
    }
  }

  /** Poll heuristic flags without coupling observation to session controls. */
  async function loadSupervisorFlags() {
    if (state.supervisorRequestInFlight) return
    state.supervisorRequestInFlight = true
    try {
      const response = await fetch("/api/flags?limit=50")
      const data = await response.json()
      if (!response.ok) throw new Error(data.warnings?.[0] || "Supervisor data unavailable")
      const incoming = new Map()
      for (const flag of Array.isArray(data.flags) ? data.flags : []) {
        if (!flag || typeof flag.session_id !== "string") continue
        incoming.set(flag.session_id, flag)
        const prior = state.supervisorFlags.get(flag.session_id)
        if (!prior) announce(`Supervisor flagged ${flag.title || flag.session_id}`)
        else if (prior.status !== flag.status || prior.why !== flag.why) {
          announce(`Supervisor assessment changed for ${flag.title || flag.session_id}`)
        }
      }
      state.supervisorFlags = incoming
      state.supervisorWarnings = Array.isArray(data.warnings) ? data.warnings : []
      // `source` is the envelope's own account of where the flags came from: "redis" (live),
      // "file" (a retained snapshot, therefore degraded), or "none".
      state.supervisorSource = typeof data.source === "string" ? data.source : "unknown"
      state.supervisorState = data.degraded ? "degraded" : "live"
      if (state.supervisorSelection && incoming.has(state.supervisorSelection.session_id)) {
        const refreshed = incoming.get(state.supervisorSelection.session_id)
        // Keep the exact action target and attached cell frozen. Polling may
        // refresh explanatory fields but may never silently remap an action.
        state.supervisorSelection = {
          ...state.supervisorSelection,
          at: refreshed.at,
          title: refreshed.title,
          model: refreshed.model,
          status: refreshed.status,
          why: refreshed.why,
          last_activity_at: refreshed.last_activity_at,
          mapping_changed: Boolean(
            state.supervisorSelection.review?.cell_id
            && refreshed.review?.cell_id
            && state.supervisorSelection.review.cell_id !== refreshed.review.cell_id
          ),
        }
      }
      renderSupervisorFlags()
      renderSelection()
    } catch (error) {
      state.supervisorState = "unavailable"
      state.supervisorSource = "none"
      state.supervisorWarnings = [error.message || "Supervisor data unavailable"]
      renderSupervisorFlags()
      announce("Supervisor data unavailable; showing last useful rows", true)
    } finally {
      state.supervisorRequestInFlight = false
    }
  }

  /** Open the sole page-lifetime fleet status source. */
  function connectStatusStream() {
    if (state.statusSource) return
    state.statusSource = new EventSource("/api/status")
    state.statusSource.onopen = () => {
      state.statusState = "live"
      renderRail()
    }
    state.statusSource.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data)
        if (typeof message.cell_id !== "string" || typeof message.status !== "string") return
        const previous = core.normalizeStatus(state.cells[message.cell_id])
        state.cells[message.cell_id] = message.status
        // Keep the transition through up to two stale matrix polls; a matching
        // snapshot clears it immediately, while queue removal cannot leave a ghost.
        state.statusOverrides.set(message.cell_id, { status: message.status, remainingSnapshots: 2 })
        const next = core.normalizeStatus(message.status)
        if (previous !== next) announce(`${message.cell_id} is now ${next}`)
        renderFleet()
        renderSelection()
      } catch (_error) {
        // Malformed status messages do not invalidate the last good fleet snapshot.
      }
    }
    state.statusSource.onerror = () => {
      state.statusState = "reconnecting"
      renderRail()
      announce("Fleet status stream reconnecting", true)
    }
  }

  /** Build a semantic routing table using text nodes rather than HTML strings. */
  function routingTable(captionText, headers, rows) {
    const wrap = element("div", "table-scroll")
    const table = element("table", "routing-table")
    table.appendChild(element("caption", "sr-only", captionText))
    const head = element("thead")
    const headRow = element("tr")
    headers.forEach((header) => {
      const cell = element("th", "", header)
      cell.scope = "col"
      headRow.appendChild(cell)
    })
    head.appendChild(headRow)
    table.appendChild(head)
    const body = element("tbody")
    rows.forEach((row) => {
      const tr = element("tr")
      row.forEach((value) => tr.appendChild(element("td", "", String(value ?? "?"))))
      body.appendChild(tr)
    })
    table.appendChild(body)
    wrap.appendChild(table)
    return wrap
  }

  /** Format usage dollars without turning missing provider data into a fake zero. */
  function usageUsd(value) {
    const number = core.safeNumber(value)
    return number === null ? "Unavailable" : `$${number.toFixed(2)}`
  }

  /** Build a compact, labeled metric group for balances and spend estimates. */
  function usageMetrics(metrics) {
    const grid = element("div", "metric-grid usage-metric-grid")
    metrics.forEach(({ label, value, detail }) => {
      const card = element("article", "metric-card usage-metric")
      card.appendChild(element("span", "metric-label", label))
      card.appendChild(element("strong", "metric-value cost-value", value))
      if (detail) card.appendChild(element("span", "pane-note", detail))
      grid.appendChild(card)
    })
    return grid
  }

  /** Render an explicit no-data state instead of an empty table. */
  function usageEmpty(text) {
    return element("p", "empty-state", text)
  }

  /** Render a provider or request failure with an actionable, visible state. */
  function usageError(text) {
    return element("p", "error-state", text)
  }

  /** Fetch routing lazily so routing failure never blocks live supervision. */
  async function loadRouting() {
    const content = $("#routing-content")
    content.replaceChildren(element("p", "empty-state", "Loading routing data…"))
    try {
      const response = await fetch("/api/routing")
      const data = await response.json()
      if (!response.ok) throw new Error("routing unavailable")
      const perTask = Array.isArray(data.per_task) ? data.per_task : []
      content.replaceChildren()
      if (perTask.length === 0) {
        content.appendChild(element("p", "empty-state", "No routing data yet. Run experiments across multiple models first."))
      } else {
        content.appendChild(element("h3", "", "Per-task routing"))
        content.appendChild(routingTable(
          "Per-task model routing recommendations",
          ["Task", "Route", "Target", "Best correctness", "Best efficiency"],
          perTask.map((task) => {
            const route = task.routing === "escalate" ? "escalate" : "default"
            return [
              task.task,
              route,
              route === "escalate" ? task.escalate_model : task.default_model,
              task.best_correctness_model,
              task.best_efficiency_model,
            ]
          }),
        ))
        content.appendChild(element("h3", "", "Strategy simulation"))
        const strategyRows = Object.entries(data.strategies || {}).map(([name, strategy]) => {
          const cost = core.safeNumber(strategy?.total_cost)
          const correctness = core.safeNumber(strategy?.avg_correctness)
          return [name, strategy?.n ?? 0, cost === null ? "unavailable" : formatCost(cost), correctness === null ? "unavailable" : `${(correctness * 100).toFixed(0)}%`]
        })
        content.appendChild(routingTable(
          "Routing strategy simulation",
          ["Strategy", "N", "Total cost", "Avg correctness"],
          strategyRows,
        ))
      }
      state.routingLoaded = true
    } catch (_error) {
      content.replaceChildren(element("p", "error-state", "Routing unavailable. Live workspace remains connected."))
    }
  }

  /**
   * Subscription usage — provider quota from the polite cache (15 min TTL, 60 s
   * min refetch floor on the server). Polls hit Redis, never the providers.
   */
  async function loadSubscriptionUsage(force = false) {
    const content = $("#usage-content")
    const refreshButton = $("#usage-refresh")
    if (!content || state.usageRequestInFlight) return
    state.usageRequestInFlight = true
    if (refreshButton) {
      refreshButton.disabled = true
      refreshButton.setAttribute("aria-busy", "true")
    }
    const hadContent = Boolean(content.dataset.loaded)
    if (!content.dataset.loaded) {
      content.replaceChildren(element("p", "empty-state", "Loading subscription usage…"))
    }
    try {
      const url = force ? "/api/subscription-usage?refresh=1" : "/api/subscription-usage"
      const response = await fetch(url)
      const data = await response.json()
      if (!response.ok) {
        const error = new Error(data.error || "usage unavailable")
        error.usageState = data.state
        error.cacheAge = data.cache?.age_seconds
        throw error
      }
      content.replaceChildren()
      content.dataset.loaded = "1"
      content.querySelectorAll("[data-usage-refresh-error]").forEach((node) => node.remove())
      const cache = data.cache || {}
      const cacheState = data.stale ? "stale" : "fresh"
      content.dataset.cacheState = cacheState
      content.appendChild(element("p", "pane-note",
        `Cache: ${cacheState} · age ${cache.age_seconds ?? "unavailable"}s · ` +
        `refresh floor ${cache.min_refresh_seconds ?? "?"}s · ` +
        `fetched ${String(data.fetched_at ?? "?").slice(0, 19).replace("T", " ")}Z · ` +
        `${data.served_from ?? "?"} · ${data.history?.count ?? 0} saved snapshots`))
      if (data.refresh_error) {
        content.appendChild(usageError(`Refresh failed; showing the last snapshot: ${data.refresh_error}`))
      }
      for (const [provider, info] of Object.entries(data.providers || {})) {
        content.appendChild(element("h3", "", `${provider} — ${info.plan ?? "?"}`))
        if (!info.ok) {
          content.appendChild(usageError(`${provider} unavailable: ${info.error ?? "unknown provider error"}`))
          continue
        }
        const windows = Array.isArray(info.windows) ? info.windows : []
        const rows = windows.map((window) => [
          window.name ?? "?",
          `${window.used_percent ?? "?"}%`,
          window.limit_seconds ? `${Math.round(window.limit_seconds / 3600)}h` : "—",
          window.resets_at ? String(window.resets_at).slice(0, 16).replace("T", " ") + "Z" : "—",
        ])
        content.appendChild(rows.length
          ? routingTable(`${provider} subscription usage windows`, ["Window", "Used", "Length", "Resets (UTC)"], rows)
          : usageEmpty(`${provider} has no usage windows in the provider response.`))
      }
      const deepseek = data.deepseek || {}
      content.appendChild(element("h3", "", "deepseek — per-token cash (local opencode.db)"))
      if (!deepseek.ok) {
        content.appendChild(usageError(`DeepSeek local cash unavailable: ${deepseek.error ?? "unknown local DB error"}`))
      } else {
        const totals = deepseek.totals || {}
        content.appendChild(usageMetrics([
          { label: "Local 14d cash estimate", value: usageUsd(totals.cost_usd), detail: "per-token local estimate" },
          { label: "Local tokens", value: Number(totals.tokens ?? 0).toLocaleString(), detail: "opencode.db" },
          { label: "Local sessions", value: String(totals.sessions ?? "Unavailable"), detail: "14-day window" },
        ]))
        const days = Array.isArray(deepseek.days) ? deepseek.days : []
        const dayRows = days.map((day) => [
          day.date ?? "?",
          usageUsd(day.cost_usd),
          day.sessions ?? "?",
          (day.tokens ?? 0).toLocaleString(),
          usageUsd(day.subagent_cost_usd),
        ])
        content.appendChild(dayRows.length
          ? routingTable("DeepSeek per-day cash spend (local DB estimates)", ["Date", "Cost $", "Sessions", "Tokens", "Subagent $"], dayRows)
          : usageEmpty("DeepSeek local cash has no sessions in the 14-day window."))
      }
      const meter = data.deepseek_platform || {}
      content.appendChild(element("h3", "", "deepseek platform — authoritative meter"))
      const wallet = meter.wallet || {}
      const mtotals = meter.totals || {}
      content.appendChild(usageMetrics([
        {
          label: "DeepSeek wallet balance",
          value: wallet.ok === false ? "Unavailable" : usageUsd(wallet.balance_usd),
          detail: wallet.ok === false ? (wallet.error || "wallet summary unavailable") : "platform wallet",
        },
        {
          label: "DeepSeek platform meter · 14d",
          value: meter.ok ? usageUsd(mtotals.estimated_cost_usd) : "Unavailable",
          detail: mtotals.pricing_complete === false ? "unpriced model data present" : "meter tokens × off-peak rates",
        },
        {
          label: "DeepSeek lifetime spend",
          value: wallet.ok === false ? "Unavailable" : usageUsd(wallet.lifetime_cost_usd),
          detail: "platform wallet total",
        },
      ]))
      if (!meter.ok) {
        content.appendChild(usageError(`DeepSeek platform meter unavailable: ${meter.error ?? "unknown meter error"}`))
      } else {
        const days = Array.isArray(meter.days) ? meter.days : []
        const meterRows = days.map((day) => [
          day.date ?? "?",
          usageUsd(day.estimated_cost_usd),
          (day.requests ?? 0).toLocaleString(),
          (day.response_tokens ?? 0).toLocaleString(),
          `${(day.cache_hit_tokens ?? 0).toLocaleString()} / ${(day.cache_miss_tokens ?? 0).toLocaleString()}`,
        ])
        content.appendChild(meterRows.length
          ? routingTable("DeepSeek per-day meter spend (authoritative tokens, estimated $)", ["Date", "Est $", "Requests", "Resp tokens", "Cache hit / miss"], meterRows)
          : usageEmpty("DeepSeek platform meter returned no usage days in the 14-day window."))
      }
    } catch (err) {
      const expired = err.usageState === "expired"
      const message = expired
        ? `Subscription usage expired; refresh to obtain a new snapshot. Cache age: ${err.cacheAge ?? "unavailable"}s.`
        : `Subscription usage unavailable: ${err.message}`
      if (hadContent) {
        const notice = usageError(`Refresh failed; showing the last snapshot. ${message}`)
        notice.dataset.usageRefreshError = "1"
        content.prepend(notice)
        announce("Subscription usage refresh failed; showing the last snapshot", true)
      } else {
        content.replaceChildren(usageError(message))
        announce("Subscription usage unavailable", true)
      }
    } finally {
      state.usageRequestInFlight = false
      if (refreshButton) {
        refreshButton.disabled = false
        refreshButton.removeAttribute("aria-busy")
      }
    }
  }

  /**
   * canonical-state round 2, plan step 17 — fetch the registry table lazily (only
   * once the drawer is first opened, mirroring loadRouting's own state.routingLoaded
   * gate), honoring the three filter controls. GET-only: this panel never sends a
   * mutating request, matching the flag-only rail's existing invariant.
   */
  async function loadRegistry() {
    const content = $("#registry-content")
    content.replaceChildren(element("p", "empty-state", "Loading registry…"))
    $("#registry-lineage").hidden = true
    try {
      const params = new URLSearchParams()
      const recordType = $("#registry-filter-type").value
      const lifecycle = $("#registry-filter-lifecycle").value
      const since = $("#registry-filter-since").value
      if (recordType) params.set("record_type", recordType)
      if (lifecycle) params.set("lifecycle", lifecycle)
      if (since) params.set("since", since)
      const response = await fetch(`/api/registry?${params.toString()}`)
      const data = await response.json()
      if (!response.ok) throw new Error("registry unavailable")
      renderRegistryTable(Array.isArray(data.registry) ? data.registry : [])
      state.registryLoaded = true
    } catch (_error) {
      content.replaceChildren(element("p", "error-state", "Registry unavailable. Live workspace remains connected."))
    }
  }

  /** Render registry rows as a clickable table — a row click loads that entity's lineage. */
  function renderRegistryTable(rows) {
    const content = $("#registry-content")
    content.replaceChildren()
    if (rows.length === 0) {
      content.appendChild(element("p", "empty-state", "No registry entries match this filter."))
      return
    }
    const wrap = element("div", "table-scroll")
    const table = element("table", "routing-table")
    table.appendChild(element("caption", "sr-only", "Canonical-state registry entries — activate a row for its lineage"))
    const head = element("thead")
    const headRow = element("tr")
    ;["knowledge_id", "source_type", "lifecycle_state", "observed_at", "logical_locator"].forEach((header) => {
      const cell = element("th", "", header)
      cell.scope = "col"
      headRow.appendChild(cell)
    })
    head.appendChild(headRow)
    table.appendChild(head)
    const body = element("tbody")
    rows.forEach((row) => {
      const tr = element("tr")
      tr.tabIndex = 0
      tr.setAttribute("role", "button")
      tr.setAttribute("aria-label", `View lineage for ${row.logical_locator || row.entity_id || "entry"}`)
      ;[row.knowledge_id, row.source_type, row.lifecycle_state, row.observed_at, row.logical_locator].forEach((value) => {
        tr.appendChild(element("td", "", String(value ?? "?").slice(0, 60)))
      })
      const openLineage = () => loadRegistryLineage(row.entity_id)
      tr.addEventListener("click", openLineage)
      tr.addEventListener("keydown", (event) => {
        if (event.key !== "Enter" && event.key !== " ") return
        event.preventDefault()
        openLineage()
      })
      body.appendChild(tr)
    })
    table.appendChild(body)
    wrap.appendChild(table)
    content.appendChild(wrap)
    content.appendChild(element("p", "bottom-provenance", `${rows.length} record(s)`))
  }

  /**
   * Fetch and render the one-hop lineage view for one entity_id (design §10 / §5a).
   * File-only (never Neo4j — see admin/server.py's api_registry_lineage docstring),
   * so this always resolves quickly; an actuation record's justifying observation
   * (`causes_record`) renders alongside its own row when present.
   */
  async function loadRegistryLineage(entityId) {
    if (!entityId) return
    const panel = $("#registry-lineage")
    const content = $("#registry-lineage-content")
    panel.hidden = false
    content.replaceChildren(element("p", "empty-state", "Loading lineage…"))
    try {
      const response = await fetch(`/api/registry/${encodeURIComponent(entityId)}`)
      const data = await response.json()
      if (!response.ok) throw new Error(data.error || "lineage unavailable")
      content.replaceChildren()
      content.appendChild(element("pre", "", JSON.stringify(data.record, null, 2)))
      if (data.causes_record) {
        content.appendChild(element("h4", "", "Causes (justifying observation)"))
        content.appendChild(element("pre", "", JSON.stringify(data.causes_record, null, 2)))
      } else if (data.record?.source_type === "actuation") {
        content.appendChild(element("p", "empty-state", "causes citation unresolved"))
      }
    } catch (error) {
      content.replaceChildren(element("p", "empty-state", error.message || "Lineage unavailable"))
    }
  }

  /** Call only the existing queue endpoint and report the completed action. */
  async function runQueueAction(action) {
    if (state.queuePending) return
    state.queuePending = true
    const queueButtons = [$("#enqueue-button"), $("#clear-queue-button")]
    queueButtons.forEach((control) => { control.disabled = true })
    const result = $("#queue-result")
    result.textContent = `${action === "clear" ? "Clearing" : "Enqueuing"}…`
    try {
      const response = await fetch("/api/experiments", {
        method: "POST",
        headers: { "Content-Type": "application/json", "Idempotency-Key": mutationKey() },
        body: JSON.stringify({ action }),
      })
      const data = await response.json()
      if (!response.ok || !data.ok) throw new Error(data.error || data.output || "Action failed")
      result.textContent = data.output || `${action} completed`
      // Refresh opportunistically without tying control availability to a slow observer request.
      void loadMatrix()
    } catch (error) {
      result.textContent = error.message || "Queue action failed"
      announce(result.textContent, true)
    } finally {
      state.queuePending = false
      queueButtons.forEach((control) => { control.disabled = false })
    }
  }

  /** Return a collision-resistant mutation key without requiring a build-time helper. */
  function mutationKey() {
    return window.crypto?.randomUUID?.() || `${Date.now()}-${Math.random().toString(16).slice(2)}`
  }

  /** Call a same-origin JSON design mutation and preserve structured errors. */
  async function designMutation(path, body) {
    const response = await fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json", "Idempotency-Key": mutationKey() },
      body: JSON.stringify(body),
    })
    let data
    try {
      data = await response.json()
    } catch (_error) {
      throw new Error(`Control Room returned an unreadable response (${response.status})`)
    }
    if (!response.ok) {
      const error = new Error(data.error || data.message || `Request failed (${response.status})`)
      error.response = data
      error.status = response.status
      throw error
    }
    return data
  }

  /** Call a supervisor mutation with an operator-owned retry key. */
  async function supervisorMutation(path, body, idempotencyKey) {
    const response = await fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json", "Idempotency-Key": idempotencyKey },
      body: JSON.stringify(body),
    })
    let data
    try {
      data = await response.json()
    } catch (_error) {
      throw new Error(`Control Room returned an unreadable response (${response.status})`)
    }
    if (!response.ok) {
      const error = new Error(data.error || `Request failed (${response.status})`)
      error.status = response.status
      throw error
    }
    return data
  }

  /** Call a same-origin JSON claude-agent mutation and preserve structured errors. */
  async function claudeAgentMutation(path, body) {
    const response = await fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json", "Idempotency-Key": mutationKey() },
      body: JSON.stringify(body),
    })
    let data
    try {
      data = await response.json()
    } catch (_error) {
      throw new Error(`Control Room returned an unreadable response (${response.status})`)
    }
    if (!response.ok) {
      const error = new Error(data.error || data.message || `Request failed (${response.status})`)
      error.response = data
      error.status = response.status
      throw error
    }
    return data
  }

  /** Admit a deliberate steer while preserving failed input for retry. */
  async function submitSupervisorSteer(event) {
    event.preventDefault()
    const flag = selectedSupervisorFlag()
    const prompt = $("#supervisor-steer-prompt").value
    if (!flag || !flag.review?.cell_id || !prompt.trim() || state.supervisorMutationPending) return
    const signature = JSON.stringify([flag.session_id, flag.review.cell_id, prompt])
    if (state.supervisorSteerSignature !== signature) {
      state.supervisorSteerSignature = signature
      state.supervisorSteerKey = mutationKey()
    }
    const selectedSession = flag.session_id
    state.supervisorMutationPending = true
    $("#supervisor-steer-result").textContent = "Admitting steer…"
    renderSupervisorControls(flag)
    try {
      await supervisorMutation(
        `/api/flags/${encodeURIComponent(flag.session_id)}/steer`,
        { cell_id: flag.review.cell_id, prompt },
        state.supervisorSteerKey,
      )
      if (selectedSupervisorFlag()?.session_id !== selectedSession) return
      $("#supervisor-steer-result").textContent = "Steer admitted"
      $("#supervisor-steer-prompt").value = ""
      state.supervisorSteerKey = null
      state.supervisorSteerSignature = null
      announce(`Steer admitted for ${selectedSession}`)
    } catch (error) {
      if (selectedSupervisorFlag()?.session_id !== selectedSession) return
      $("#supervisor-steer-result").textContent = `Steer failed · ${error.message}`
      announce($("#supervisor-steer-result").textContent, true)
    } finally {
      state.supervisorMutationPending = false
      if (selectedSupervisorFlag()) renderSupervisorControls(selectedSupervisorFlag())
    }
  }

  /** Open the local one-way door; this function performs no network request. */
  function openSupervisorInterruptDoor() {
    const flag = selectedSupervisorFlag()
    if (!flag?.review?.cell_id || state.supervisorMutationPending || state.supervisorInterrupted) return
    const phrase = `INTERRUPT ${flag.session_id}`
    $("#supervisor-confirmation-phrase").textContent = phrase
    $("#supervisor-interrupt-confirmation").value = ""
    $("#confirm-supervisor-interrupt").disabled = true
    $("#supervisor-interrupt-door").hidden = false
    $("#supervisor-interrupt-confirmation").focus()
  }

  /** Close the local interrupt door and optionally restore initiating focus. */
  function closeSupervisorInterruptDoor(restoreFocus = true) {
    $("#supervisor-interrupt-door").hidden = true
    $("#supervisor-interrupt-confirmation").value = ""
    $("#confirm-supervisor-interrupt").disabled = true
    if (restoreFocus) $("#supervisor-interrupt").focus()
  }

  /** Submit the exact typed confirmation for server-side revalidation. */
  async function confirmSupervisorInterrupt() {
    const flag = selectedSupervisorFlag()
    if (!flag?.review?.cell_id || state.supervisorMutationPending || state.supervisorInterrupted) return
    const confirmation = $("#supervisor-interrupt-confirmation").value
    if (confirmation !== `INTERRUPT ${flag.session_id}`) return
    state.supervisorInterruptKey ||= mutationKey()
    const selectedSession = flag.session_id
    state.supervisorMutationPending = true
    $("#confirm-supervisor-interrupt").disabled = true
    $("#supervisor-interrupt-result").textContent = "Requesting permanent interrupt…"
    renderSupervisorControls(flag)
    try {
      await supervisorMutation(
        `/api/flags/${encodeURIComponent(flag.session_id)}/interrupt`,
        { cell_id: flag.review.cell_id, confirmation },
        state.supervisorInterruptKey,
      )
      if (selectedSupervisorFlag()?.session_id !== selectedSession) return
      state.supervisorInterrupted = true
      closeSupervisorInterruptDoor(false)
      $("#supervisor-interrupt-result").textContent = "Interrupt accepted; terminal remains attached"
      announce(`Interrupt accepted for ${selectedSession}`)
    } catch (error) {
      if (selectedSupervisorFlag()?.session_id !== selectedSession) return
      $("#supervisor-interrupt-result").textContent = `Interrupt failed · ${error.message}`
      announce($("#supervisor-interrupt-result").textContent, true)
    } finally {
      state.supervisorMutationPending = false
      if (selectedSupervisorFlag()) renderSupervisorControls(selectedSupervisorFlag())
    }
  }

  /** Fill both approved-workdir controls from backend-owned labels. */
  function renderWorkdirOptions() {
    for (const selector of ["#design-workdir", "#run-workdir"]) {
      const select = $(selector)
      const previous = select.value
      select.replaceChildren()
      for (const item of state.approvedWorkdirs) {
        const option = element("option", "", item.label)
        option.value = item.key
        select.appendChild(option)
      }
      if (state.approvedWorkdirs.some((item) => item.key === previous)) select.value = previous
    }
  }

  /** Restore portal ownership summaries without enumerating native server sessions. */
  async function loadDesignSessions({ restore = false } = {}) {
    try {
      const response = await fetch("/api/design-sessions")
      const data = await response.json()
      if (!response.ok) throw new Error(data.error || "Design sessions unavailable")
      state.designSessions = new Map((data.sessions || []).map((session) => [session.portal_id, session]))
      state.approvedWorkdirs = Array.isArray(data.workdirs) ? data.workdirs : []
      renderWorkdirOptions()
      renderRecentDesigns()
      if (restore) {
        let selected = null
        try { selected = window.localStorage.getItem("control-room-selected-design") } catch (_error) {}
        if (selected && state.designSessions.has(selected)) selectDesignSession(selected, true)
      }
      if (state.selectedType === "design" && !state.designSessions.has(state.selectedId)) {
        detachSelectedStream()
        // The selected session disappeared from the authoritative roster, so its per-draft
        // interval must disappear with it instead of waking forever as an early-return poll.
        if (state.draftPollTimer) window.clearInterval(state.draftPollTimer)
        state.draftPollTimer = null
        state.selectedId = null
        state.selectedType = null
        state.draftState = null
        renderSelection()
        renderTranscript(false)
      } else {
        renderSelection()
      }
    } catch (error) {
      $("#recent-design-list").replaceChildren(element("p", "error-state", error.message || "Design sessions unavailable"))
    }
  }

  /** Read the supervisor-maintained roster; this call never reaches the claude CLI. */
  async function loadClaudeAgents() {
    try {
      const response = await fetch("/api/claude-agents")
      const data = await response.json()
      state.claudeAgentsUnavailable = data.error === "supervisor_unavailable"
      const agents = Array.isArray(data.agents) ? data.agents : []
      state.claudeAgents = new Map(
        agents.filter((entry) => entry && typeof entry.id === "string").map((entry) => [entry.id, entry]),
      )
      state.approvedClaudeAgentWorkdirs = Array.isArray(data.workdirs) ? data.workdirs : []
      renderClaudeAgentWorkdirOptions()
    } catch (_error) {
      state.claudeAgentsUnavailable = true
    }
    renderClaudeAgentGrid()
    if (state.selectedType === "claude_agent" && !state.claudeAgents.has(state.selectedClaudeAgentId)) {
      detachSelectedStream()
      state.selectedId = null
      state.selectedType = null
      state.selectedClaudeAgentId = null
    }
    renderSelection()
  }

  /** Read-only ``claude daemon status``; no control affordance is derived here. */
  async function loadClaudeAgentDaemon() {
    try {
      const response = await fetch("/api/claude-agents/daemon")
      state.claudeAgentDaemon = await response.json()
    } catch (_error) {
      state.claudeAgentDaemon = { running: false }
    }
    renderClaudeAgentDaemon()
  }

  /** Reveal a kind-specific start form while preserving entered text on failure. */
  function openDesignStart(kind) {
    state.designFormKind = kind
    $("#design-start-form").hidden = false
    $("#design-start-title").textContent = kind === "workflow" ? "NEW WORKFLOW DESIGN" : "NEW EXPERIMENT DESIGN"
    $("#design-intent-label").textContent = kind === "workflow" ? "Feature goal" : "Research question"
    $("#start-design-session").textContent = kind === "workflow" ? "Start workflow design" : "Start experiment design"
    $("#design-intent").focus()
  }

  /** Start one native session with duplicate submission prevention. */
  async function startDesignSession(event) {
    event.preventDefault()
    if (state.designMutationPending) return
    const button = $("#start-design-session")
    const originalLabel = button.textContent
    state.designMutationPending = true
    button.disabled = true
    button.textContent = "Starting…"
    $("#design-start-result").textContent = "Creating native OpenCode session…"
    try {
      const data = await designMutation("/api/design-sessions", {
        kind: state.designFormKind,
        intent: $("#design-intent").value,
        model: $("#design-model").value,
        workdir: $("#design-workdir").value,
      })
      state.designSessions.set(data.session.portal_id, data.session)
      $("#design-start-form").hidden = true
      $("#design-start-result").textContent = ""
      renderRecentDesigns()
      selectDesignSession(data.session.portal_id, true)
      announce(`${data.session.kind} design session started`)
    } catch (error) {
      $("#design-start-result").textContent = error.message || "Design session could not be started"
      announce($("#design-start-result").textContent, true)
    } finally {
      state.designMutationPending = false
      button.disabled = false
      button.textContent = originalLabel
    }
  }

  /** Admit one queued or steering prompt and report admission separately. */
  async function submitDesignInput(delivery) {
    const session = selectedDesignSession()
    const prompt = $("#design-prompt").value
    if (!session || !prompt.trim() || state.designMutationPending) return
    const button = delivery === "steer" ? $("#steer-design-input") : $("#send-design-input")
    const originalLabel = button.textContent
    state.designMutationPending = true
    button.disabled = true
    button.textContent = delivery === "steer" ? "Steering…" : "Sending…"
    $("#design-input-result").textContent = `${delivery === "steer" ? "Steering" : "Queueing"} input…`
    try {
      await designMutation(`/api/design-sessions/${encodeURIComponent(session.portal_id)}/input`, { prompt, delivery })
      if (selectedDesignSession()?.portal_id !== session.portal_id) return
      $("#design-input-result").textContent = `Input admitted · ${delivery === "steer" ? "steered" : "queued"}`
      $("#design-prompt").value = ""
      announce(`Operator input ${delivery === "steer" ? "steered" : "queued"}`)
    } catch (error) {
      if (selectedDesignSession()?.portal_id !== session.portal_id) return
      $("#design-input-result").textContent = `Admission failed · ${error.message}`
      announce($("#design-input-result").textContent, true)
    } finally {
      state.designMutationPending = false
      button.disabled = false
      button.textContent = originalLabel
      renderSelection()
    }
  }

  /** Save the exact validated revision, requiring a second explicit overwrite action. */
  async function saveSpec(event) {
    event.preventDefault()
    const session = selectedDesignSession()
    if (!session || state.designMutationPending) return
    const filename = $("#save-spec-name").value
    const button = $("#save-spec-button")
    state.designMutationPending = true
    button.disabled = true
    button.textContent = "Saving…"
    $("#save-spec-result").textContent = "Revalidating draft…"
    try {
      let result
      try {
        result = await designMutation(`/api/design-sessions/${encodeURIComponent(session.portal_id)}/save`, { filename, overwrite: false })
      } catch (error) {
        if (error.status !== 409 || !error.response?.conflict) throw error
        if (selectedDesignSession()?.portal_id !== session.portal_id) return
        const replace = window.confirm(`Replace existing spec ${error.response.path}? The previous file will be overwritten atomically.`)
        if (!replace) {
          $("#save-spec-result").textContent = "Save cancelled; existing spec unchanged"
          return
        }
        result = await designMutation(`/api/design-sessions/${encodeURIComponent(session.portal_id)}/save`, { filename, overwrite: true })
      }
      if (selectedDesignSession()?.portal_id !== session.portal_id) return
      $("#save-spec-result").textContent = `Saved ${result.path} at revision ${result.revision}`
      announce(`Saved ExperimentSpec ${result.path}`)
      await loadDraftState()
      void loadDesignSessions()
    } catch (error) {
      if (selectedDesignSession()?.portal_id !== session.portal_id) return
      $("#save-spec-result").textContent = error.message || "Save failed"
      announce($("#save-spec-result").textContent, true)
    } finally {
      state.designMutationPending = false
      button.textContent = "Save spec"
      renderSelection()
    }
  }

  /** Confirm explicit launch parameters before spending budget or changing files. */
  async function runWorkflow(event) {
    event.preventDefault()
    const session = selectedDesignSession()
    if (!session || state.designMutationPending) return
    const launch = {
      goal: $("#run-goal").value,
      model: $("#run-model").value,
      workdir: $("#run-workdir").value,
      backend: $("#run-backend").value || null,
      timeout: Number($("#run-timeout").value),
      thinking_budget_tokens: Number($("#run-thinking-budget").value),
      output_token_limit: Number($("#run-output-limit").value),
      commit: $("#run-commit").checked,
    }
    const confirmation = [
      `Run saved spec: ${state.draftState?.saved?.path}`,
      `Goal: ${launch.goal}`,
      `Model: ${launch.model}`,
      `Workdir: ${launch.workdir}`,
      `Backend: ${launch.backend || "auto"}`,
      `Timeout: ${launch.timeout}s per phase`,
      `Thinking token budget: ${launch.thinking_budget_tokens}`,
      `Output token limit: ${launch.output_token_limit}`,
      `Commit successful phases: ${launch.commit ? "yes" : "no"}`,
      "This can modify the worktree and spend model budget. Continue?",
    ].join("\n")
    if (!window.confirm(confirmation)) return
    const button = $("#run-workflow-button")
    state.designMutationPending = true
    button.disabled = true
    button.textContent = "Launching…"
    $("#run-workflow-result").textContent = "Starting separate workflow execution…"
    try {
      const result = await designMutation(`/api/design-sessions/${encodeURIComponent(session.portal_id)}/run`, launch)
      if (selectedDesignSession()?.portal_id !== session.portal_id) return
      $("#run-workflow-result").textContent = `Launched ${result.execution_id}; select it in Fleet to watch the run`
      announce(`Workflow ${result.execution_id} launched`)
      void loadMatrix()
    } catch (error) {
      if (selectedDesignSession()?.portal_id !== session.portal_id) return
      $("#run-workflow-result").textContent = error.message || "Workflow launch failed"
      announce($("#run-workflow-result").textContent, true)
    } finally {
      state.designMutationPending = false
      button.textContent = "Run workflow"
      renderSelection()
    }
  }

  /** Update clock, staleness, and the rolling window without network activity. */
  function tick() {
    const now = new Date()
    const clock = $("#utc-clock")
    clock.dateTime = now.toISOString()
    clock.textContent = `${now.toISOString().slice(11, 19)} UTC`
    $("#matrix-age").textContent = state.lastMatrixAt
      ? `updated ${Math.max(0, Math.floor((Date.now() - state.lastMatrixAt) / 1000))}s ago`
      : state.matrixState
    renderRail()
    renderSupervisorFlags()
    if (selectedSupervisorFlag()) renderSupervisorControls(selectedSupervisorFlag())
  }

  /** Register all local controls after the immediate shell has rendered. */
  function bindControls() {
    $("#supervisor-steer-form").addEventListener("submit", submitSupervisorSteer)
    $("#supervisor-steer-prompt").addEventListener("input", () => {
      state.supervisorSteerKey = null
      state.supervisorSteerSignature = null
    })
    $("#supervisor-steer-prompt").addEventListener("keydown", (event) => {
      if (event.key === "Enter" && event.ctrlKey) {
        event.preventDefault()
        $("#supervisor-steer-form").requestSubmit()
      }
    })
    $("#supervisor-interrupt").addEventListener("click", openSupervisorInterruptDoor)
    $("#cancel-supervisor-interrupt").addEventListener("click", () => closeSupervisorInterruptDoor())
    $("#supervisor-interrupt-confirmation").addEventListener("input", (event) => {
      const flag = selectedSupervisorFlag()
      $("#confirm-supervisor-interrupt").disabled = !flag
        || event.target.value !== `INTERRUPT ${flag.session_id}`
        || state.supervisorMutationPending
    })
    $("#supervisor-interrupt-door").addEventListener("keydown", (event) => {
      if (event.key === "Escape") {
        event.preventDefault()
        // This is a nested door: Escape closes it, not the containing Detail sheet.
        event.stopPropagation()
        closeSupervisorInterruptDoor()
      }
    })
    $("#confirm-supervisor-interrupt").addEventListener("click", confirmSupervisorInterrupt)
    $("#detach-supervisor").addEventListener("click", detachSelectedStream)
    $("#new-workflow-design").addEventListener("click", () => openDesignStart("workflow"))
    $("#new-experiment-design").addEventListener("click", () => openDesignStart("experiment"))
    $("#cancel-design-start").addEventListener("click", () => {
      $("#design-start-form").hidden = true
      $("#design-start-result").textContent = ""
    })
    $("#design-start-form").addEventListener("submit", startDesignSession)
    $("#design-composer").addEventListener("submit", (event) => {
      event.preventDefault()
      void submitDesignInput("queue")
    })
    $("#steer-design-input").addEventListener("click", () => void submitDesignInput("steer"))
    $("#interrupt-design").addEventListener("click", async () => {
      const session = selectedDesignSession()
      if (!session || state.designMutationPending) return
      if (!window.confirm(`Interrupt active OpenCode work in ${session.portal_id}? The browser stream stays attached.`)) return
      const button = $("#interrupt-design")
      state.designMutationPending = true
      button.disabled = true
      button.textContent = "Interrupting…"
      try {
        await designMutation(`/api/design-sessions/${encodeURIComponent(session.portal_id)}/interrupt`, {})
        $("#design-input-result").textContent = "Interrupt accepted; stream remains attached"
        announce("OpenCode interrupt accepted")
        void loadDesignSessions()
      } catch (error) {
        $("#design-input-result").textContent = error.message || "Interrupt failed"
        announce($("#design-input-result").textContent, true)
      } finally {
        state.designMutationPending = false
        button.disabled = false
        button.textContent = "Interrupt"
      }
    })
    $("#detach-design").addEventListener("click", detachSelectedStream)
    $("#save-spec-form").addEventListener("submit", saveSpec)
    $("#run-workflow-form").addEventListener("submit", runWorkflow)
    // One delegated listener for the entire matrix, instead of one per card. Cards now
    // outlive a poll, so per-card binding would work too — but delegation means a newly
    // created card is interactive the instant it is appended, with no binding step to forget,
    // and it keeps the listener count flat as the fleet grows (design §2.4).
    // Sessions board: both rosters are keyed lists whose rows outlive a poll, so selection is
    // delegated once per container rather than re-bound per row on every render.
    $("#recent-design-list").addEventListener("click", (event) => {
      const row = event.target instanceof Element ? event.target.closest(".recent-design") : null
      const portalId = row?.dataset.portalId
      if (portalId) selectDesignSession(portalId, true)
    })
    $("#claude-agent-grid").addEventListener("click", (event) => {
      const button = event.target instanceof Element ? event.target.closest(".cell-select") : null
      const agentId = button?.dataset.claudeAgentId
      if (agentId) selectClaudeAgent(agentId, true)
    })
    // The flag rail is read-only: this listener only opens the Detail surface for a row, it
    // never sends a request (design §4.3).
    $("#supervisor-flag-list").addEventListener("click", (event) => {
      const row = event.target instanceof Element ? event.target.closest(".supervisor-flag") : null
      const sessionId = row?.dataset.sessionId
      if (sessionId) selectSupervisorFlag(sessionId)
    })
    $("#fleet-grid").addEventListener("click", (event) => {
      const button = event.target instanceof Element ? event.target.closest(".cell-select") : null
      const cellId = button?.dataset.cellId
      if (cellId) selectCell(cellId, true)
    })
    // LIVE NOW rows are the same read-only drill-down as fleet cards: one tap opens the Detail
    // surface for that run, nothing more (the live board is a highlight, never a control).
    $("#live-now-list").addEventListener("click", (event) => {
      const button = event.target instanceof Element ? event.target.closest(".live-now-row") : null
      const cellId = button?.dataset.cellId
      if (cellId) selectCell(cellId, true)
    })
    document.querySelectorAll(".filter-chip").forEach((button) => {
      button.addEventListener("click", () => {
        state.filter = button.dataset.filter
        document.querySelectorAll(".filter-chip").forEach((candidate) => {
          const active = candidate === button
          candidate.classList.toggle("active", active)
          candidate.setAttribute("aria-pressed", String(active))
        })
        renderFleet()
      })
    })
    $("#cell-search").addEventListener("input", (event) => {
      state.search = event.target.value
      renderFleet()
    })
    $("#watch-button").addEventListener("click", () => {
      if (state.attached) detachSelectedStream()
      else connectSelectedStream()
    })
    $("#copy-session").addEventListener("click", async () => {
      const sessionId = state.selectedSessionIds.at(-1)
      if (!sessionId) return
      try {
        await navigator.clipboard.writeText(sessionId)
        announce("Session ID copied")
      } catch (_error) {
        announce("Session ID could not be copied", true)
      }
    })
    $("#pause-button").addEventListener("click", () => {
      if (!state.paused) {
        state.paused = true
        state.followBeforePause = state.follow
        $("#pause-button").textContent = "Resume (0 buffered)"
      } else {
        state.paused = false
        state.rows = core.boundedAppend(state.rows, state.buffer, MAX_TRANSCRIPT_ROWS)
        state.buffer = []
        state.follow = state.followBeforePause
        $("#pause-button").textContent = "Pause"
        $("#follow-button").textContent = `Follow: ${state.follow ? "on" : "off"}`
        $("#follow-button").setAttribute("aria-pressed", String(state.follow))
        renderTranscript(state.follow)
      }
    })
    $("#follow-button").addEventListener("click", () => {
      state.follow = !state.follow
      $("#follow-button").textContent = `Follow: ${state.follow ? "on" : "off"}`
      $("#follow-button").setAttribute("aria-pressed", String(state.follow))
      $("#jump-live").hidden = state.follow
      if (state.follow) $("#transcript-feed").scrollTop = $("#transcript-feed").scrollHeight
    })
    $("#transcript-feed").addEventListener("scroll", () => {
      if (state.follow && !isTranscriptAtBottom()) {
        state.follow = false
        $("#follow-button").textContent = "Follow: off"
        $("#follow-button").setAttribute("aria-pressed", "false")
        $("#jump-live").hidden = false
      }
    })
    $("#jump-live").addEventListener("click", () => {
      state.follow = true
      $("#follow-button").textContent = "Follow: on"
      $("#follow-button").setAttribute("aria-pressed", "true")
      $("#jump-live").hidden = true
      $("#transcript-feed").scrollTop = $("#transcript-feed").scrollHeight
    })
    $("#clear-button").addEventListener("click", () => {
      if (state.buffer.length > 0 && !window.confirm("Clear the local transcript and buffered events? Redis history and the experiment are unchanged.")) return
      state.rows = []
      state.buffer = []
      $("#pause-button").textContent = state.paused ? "Resume (0 buffered)" : "Pause"
      renderTranscript(false)
    })
    $("#routing-toggle").addEventListener("click", () => {
      state.routingOpen = !state.routingOpen
      $("#routing-drawer").hidden = !state.routingOpen
      $("#routing-toggle").setAttribute("aria-expanded", String(state.routingOpen))
      if (state.routingOpen) {
        state.routingReturnFocus = $("#routing-toggle")
        if (!state.routingLoaded) loadRouting()
        $("#routing-refresh").focus()
      }
    })
    $("#routing-drawer").addEventListener("keydown", (event) => {
      if (event.key !== "Escape") return
      event.stopPropagation()
      state.routingOpen = false
      $("#routing-drawer").hidden = true
      $("#routing-toggle").setAttribute("aria-expanded", "false")
      state.routingReturnFocus?.focus()
    })
    $("#routing-refresh").addEventListener("click", loadRouting)
    $("#usage-refresh").addEventListener("click", () => loadSubscriptionUsage(true))
    $("#registry-toggle").addEventListener("click", () => {
      state.registryOpen = !state.registryOpen
      $("#registry-drawer").hidden = !state.registryOpen
      $("#registry-toggle").setAttribute("aria-expanded", String(state.registryOpen))
      if (state.registryOpen) {
        state.registryReturnFocus = $("#registry-toggle")
        if (!state.registryLoaded) loadRegistry()
        $("#registry-refresh").focus()
      }
    })
    $("#registry-drawer").addEventListener("keydown", (event) => {
      if (event.key !== "Escape") return
      // Keep Escape local to Registry when it sits inside the System modal.
      event.stopPropagation()
      state.registryOpen = false
      $("#registry-drawer").hidden = true
      $("#registry-toggle").setAttribute("aria-expanded", "false")
      state.registryReturnFocus?.focus()
    })
    $("#registry-refresh").addEventListener("click", loadRegistry)
    $("#registry-filters").addEventListener("submit", (event) => {
      event.preventDefault()
      loadRegistry()
    })
    $("#enqueue-button").addEventListener("click", () => {
      const warning = "This enqueues the full experiment matrix (~30 cells) on the default model and will incur real cost. Continue?"
      if (window.confirm(warning)) runQueueAction("enqueue")
    })
    /* Clearing the queue is the System sheet's only irreversible action, so it goes through
       the same two-step, type-to-confirm door as the supervisor Interrupt rather than a
       browser `confirm()` dialog: the phrase has to be typed, which cannot be dismissed by
       reflex, and the door states the blast radius in place (design §3.4, §7.2). */
    const QUEUE_CLEAR_PHRASE = "CLEAR QUEUE"

    /** Open or close the clear-queue door, resetting its typed confirmation each time. */
    function setQueueClearDoor(open) {
      const door = $("#queue-clear-door")
      door.hidden = !open
      $("#clear-queue-button").setAttribute("aria-expanded", String(open))
      $("#queue-clear-confirmation").value = ""
      $("#confirm-queue-clear").disabled = true
      if (open) $("#queue-clear-confirmation").focus()
      else $("#clear-queue-button").focus()
    }

    $("#clear-queue-button").addEventListener("click", () => {
      setQueueClearDoor($("#queue-clear-door").hidden)
    })
    $("#cancel-queue-clear").addEventListener("click", () => setQueueClearDoor(false))
    $("#queue-clear-confirmation").addEventListener("input", (event) => {
      // Exact match only, including case: an approximate match would defeat the point of
      // making the operator retype the phrase.
      $("#confirm-queue-clear").disabled = event.target.value !== QUEUE_CLEAR_PHRASE
    })
    $("#confirm-queue-clear").addEventListener("click", () => {
      if ($("#queue-clear-confirmation").value !== QUEUE_CLEAR_PHRASE) return
      setQueueClearDoor(false)
      runQueueAction("clear")
    })
    bindClaudeAgentControls()
  }

  /** Register every Claude background-session control: start, stop, respawn, rm, daemon. */
  function bindClaudeAgentControls() {
    $("#new-claude-agent").addEventListener("click", () => {
      $("#claude-agent-start-form").hidden = false
      $("#claude-agent-task").focus()
    })
    $("#cancel-claude-agent-start").addEventListener("click", () => {
      $("#claude-agent-start-form").hidden = true
      $("#claude-agent-start-result").textContent = ""
    })
    $("#claude-agent-start-form").addEventListener("submit", async (event) => {
      event.preventDefault()
      if (state.claudeAgentMutationPending) return
      const button = $("#start-claude-agent")
      const originalLabel = button.textContent
      state.claudeAgentMutationPending = true
      button.disabled = true
      button.textContent = "Starting…"
      $("#claude-agent-start-result").textContent = "Starting claude --bg session…"
      try {
        const model = $("#claude-agent-model").value.trim()
        const advisor = $("#claude-agent-advisor").value
        const data = await claudeAgentMutation("/api/claude-agents", {
          task: $("#claude-agent-task").value,
          workdir: $("#claude-agent-workdir").value,
          ...(model ? { model } : {}),
          ...(advisor ? { advisor } : {}),
        })
        $("#claude-agent-start-form").hidden = true
        $("#claude-agent-start-result").textContent = ""
        $("#claude-agent-task").value = ""
        announce(`Started Claude background session ${data.id}`)
        await loadClaudeAgents()
        selectClaudeAgent(data.id, true)
      } catch (error) {
        $("#claude-agent-start-result").textContent = error.message || "Could not start session"
        announce($("#claude-agent-start-result").textContent, true)
      } finally {
        state.claudeAgentMutationPending = false
        button.disabled = false
        button.textContent = originalLabel
      }
    })

    $("#claude-agent-stop").addEventListener("click", async () => {
      const entry = selectedClaudeAgent()
      if (!entry || !entry.owned || state.claudeAgentMutationPending) return
      if (!window.confirm(`Stop Claude background session ${entry.id}? The process ends now; the conversation is preserved and can be resumed with Respawn.`)) return
      state.claudeAgentMutationPending = true
      $("#claude-agent-stop").disabled = true
      try {
        const result = await claudeAgentMutation(`/api/claude-agents/${encodeURIComponent(entry.id)}/stop`, {})
        $("#claude-agent-action-result").textContent = result.note || "Stop accepted"
        announce(`Stop accepted for ${entry.id}`)
        void loadClaudeAgents()
      } catch (error) {
        $("#claude-agent-action-result").textContent = error.message || "Stop failed"
        announce($("#claude-agent-action-result").textContent, true)
      } finally {
        state.claudeAgentMutationPending = false
        $("#claude-agent-stop").disabled = false
      }
    })

    $("#claude-agent-respawn").addEventListener("click", async () => {
      const entry = selectedClaudeAgent()
      if (!entry || !entry.owned || state.claudeAgentMutationPending) return
      state.claudeAgentMutationPending = true
      $("#claude-agent-respawn").disabled = true
      try {
        await claudeAgentMutation(`/api/claude-agents/${encodeURIComponent(entry.id)}/respawn`, {})
        $("#claude-agent-action-result").textContent = "Respawned; conversation id unchanged"
        announce(`Respawned ${entry.id}`)
        void loadClaudeAgents()
      } catch (error) {
        $("#claude-agent-action-result").textContent = error.message || "Respawn failed"
        announce($("#claude-agent-action-result").textContent, true)
      } finally {
        state.claudeAgentMutationPending = false
        $("#claude-agent-respawn").disabled = false
      }
    })

    $("#claude-agent-rm").addEventListener("click", async () => {
      const entry = selectedClaudeAgent()
      if (!entry || !entry.owned || state.claudeAgentMutationPending) return
      if (!window.confirm(`Remove Claude background session ${entry.id} from the agents list? The transcript stays on disk and is reachable only outside the Control Room.`)) return
      state.claudeAgentMutationPending = true
      $("#claude-agent-rm").disabled = true
      try {
        const result = await claudeAgentMutation(`/api/claude-agents/${encodeURIComponent(entry.id)}/rm`, {})
        announce(`Removed ${entry.id}`)
        detachSelectedStream()
        state.selectedId = null
        state.selectedType = null
        state.selectedClaudeAgentId = null
        $("#claude-agent-action-result").textContent = result.note || "Removed"
        renderSelection()
        renderTranscript(false)
        void loadClaudeAgents()
      } catch (error) {
        $("#claude-agent-action-result").textContent = error.message || "Rm failed"
        announce($("#claude-agent-action-result").textContent, true)
      } finally {
        state.claudeAgentMutationPending = false
        $("#claude-agent-rm").disabled = false
      }
    })

    $("#claude-agent-steer-form").addEventListener("submit", async (event) => {
      event.preventDefault()
      const entry = selectedClaudeAgent()
      const prompt = $("#claude-agent-steer-prompt").value.trim()
      if (!entry || !entry.owned || state.claudeAgentMutationPending || !prompt) return
      state.claudeAgentMutationPending = true
      const button = $("#claude-agent-steer")
      button.disabled = true
      const originalLabel = button.textContent
      button.textContent = "Steering…"
      try {
        const result = await claudeAgentMutation(`/api/claude-agents/${encodeURIComponent(entry.id)}/steer`, { prompt })
        $("#claude-agent-steer-result").textContent = `Steered — resumed as ${result.id}`
        $("#claude-agent-steer-prompt").value = ""
        announce(`Steered ${entry.id} → ${result.id}`)
        await loadClaudeAgents()
        selectClaudeAgent(result.id, true)
      } catch (error) {
        $("#claude-agent-steer-result").textContent = error.message || "Steer failed"
        announce($("#claude-agent-steer-result").textContent, true)
      } finally {
        state.claudeAgentMutationPending = false
        button.disabled = false
        button.textContent = originalLabel
      }
    })

    $("#claude-agent-detach").addEventListener("click", detachSelectedStream)
    $("#claude-agent-detach-external").addEventListener("click", detachSelectedStream)

    $("#claude-agent-fetch-logs").addEventListener("click", async () => {
      const entry = selectedClaudeAgent()
      if (!entry || entry.owned) return
      $("#claude-agent-fetch-logs").disabled = true
      $("#claude-agent-external-log").textContent = "Fetching…"
      try {
        const response = await fetch(`/api/claude-agents/${encodeURIComponent(entry.id)}/logs`)
        const text = await response.text()
        if (!response.ok) throw new Error(text || `Request failed (${response.status})`)
        $("#claude-agent-external-log").textContent = text || "(no output)"
        announce(`Fetched latest log tail for ${entry.id}`)
      } catch (error) {
        $("#claude-agent-external-log").textContent = error.message || "Log fetch failed"
        announce($("#claude-agent-external-log").textContent, true)
      } finally {
        $("#claude-agent-fetch-logs").disabled = false
      }
    })

    // Blast-radius confirm always required; ending every hosted session needs a
    // second, visually distinct toggle plus its own confirm before it can be sent.
    $("#daemon-stop-button").addEventListener("click", async () => {
      if (state.claudeAgentMutationPending) return
      const keepWorkers = !$("#daemon-end-sessions").checked
      if (!window.confirm("Stop the Claude agents daemon? This affects every background session on this machine, not just ones started from the Control Room.")) return
      if (!keepWorkers && !window.confirm("This also ends every running session the daemon hosts, including sessions not started from the Control Room. Continue?")) return
      state.claudeAgentMutationPending = true
      $("#daemon-stop-button").disabled = true
      $("#daemon-stop-result").textContent = "Stopping daemon…"
      try {
        await claudeAgentMutation("/api/claude-agents/daemon/stop", { keep_workers: keepWorkers })
        $("#daemon-stop-result").textContent = keepWorkers
          ? "Daemon stopped; hosted sessions preserved"
          : "Daemon stopped; every hosted session ended"
        announce($("#daemon-stop-result").textContent, true)
        $("#daemon-end-sessions").checked = false
        void loadClaudeAgentDaemon()
        void loadClaudeAgents()
      } catch (error) {
        $("#daemon-stop-result").textContent = error.message || "Daemon stop failed"
        announce($("#daemon-stop-result").textContent, true)
      } finally {
        state.claudeAgentMutationPending = false
        $("#daemon-stop-button").disabled = false
      }
    })
  }

  bindControls()
  bindDocsHealthControls()
  renderFleet()
  renderPipelineStages()
  renderSelection()
  tick()
  loadMatrix()
  loadSupervisorFlags()
  loadDesignSessions({ restore: true })
  loadClaudeAgents()
  loadClaudeAgentDaemon()
  loadSubscriptionUsage()
  loadDocsHealth()
  connectStatusStream()
  window.setInterval(loadMatrix, MATRIX_POLL_MS)
  window.setInterval(loadSupervisorFlags, FLAGS_POLL_MS)
  window.setInterval(loadDesignSessions, DESIGN_LIST_POLL_MS)
  window.setInterval(loadClaudeAgents, CLAUDE_AGENTS_POLL_MS)
  window.setInterval(loadClaudeAgentDaemon, CLAUDE_AGENTS_DAEMON_POLL_MS)
  window.setInterval(() => loadSubscriptionUsage(), 60_000)
  window.setInterval(loadDocsHealth, DOCS_HEALTH_POLL_MS)
  window.setInterval(tick, 1000)
})(window.ControlRoomCore, window)
