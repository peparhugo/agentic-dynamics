"use strict"

/**
 * Control Room browser controller.
 *
 * The matrix snapshot owns retained fleet telemetry. The selected-cell stream
 * only overlays not-yet-polled live samples, which prevents polling, replay,
 * and automatic EventSource reconnection from multiplying reported spend.
 */
(function startControlRoom(core) {
  const SVG_NS = "http://www.w3.org/2000/svg"
  const MAX_TRANSCRIPT_ROWS = 500
  const MAX_LIVE_SAMPLES_PER_CELL = 500
  const REPLAY_RACE_TAIL = 500
  const REPLAY_RACE_WINDOW_MS = 250
  const MATRIX_POLL_MS = 5000
  const BURN_WINDOW_MS = 60000
  const STATUS_SYMBOLS = {
    queued: "○",
    running: "◔",
    done: "✓",
    failed: "×",
    timeout: "◷",
    unknown: "?",
  }

  const state = {
    cells: {},
    statusOverrides: new Map(),
    telemetry: { cells: {}, reported_cost: null, input_tokens: null, output_tokens: null },
    liveSamplesByCell: new Map(),
    burnSamples: [],
    selectedId: null,
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
    queuePending: false,
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

  /** Return normalized status counts for both cards and the command rail. */
  function statusCounts() {
    const counts = { queued: 0, running: 0, done: 0, failed: 0, timeout: 0, unknown: 0 }
    for (const value of Object.values(state.cells)) counts[core.normalizeStatus(value)] += 1
    return counts
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
    const spend = $("#reported-spend")
    const formattedSpend = formatCost(totals.reported_cost)
    spend.textContent = formattedSpend || "WAITING FOR COST TELEMETRY"
    spend.setAttribute(
      "aria-label",
      formattedSpend ? `${formattedSpend} cumulative reported spend, retained window` : "Waiting for cost telemetry",
    )

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
    const samples = state.burnSamples.slice(-20)
    if (samples.length === 0) {
      svg.setAttribute("aria-label", "No live cost samples in the rolling 60-second window")
      return
    }
    const maximum = Math.max(...samples.map((sample) => sample.cost), 0.000001)
    const points = samples.map((sample, index) => {
      const x = samples.length === 1 ? 60 : (index / (samples.length - 1)) * 116 + 2
      const y = 21 - (sample.cost / maximum) * 18
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

  /** Render urgency-sorted fleet cards without interpolating untrusted IDs. */
  function renderFleet() {
    const grid = $("#fleet-grid")
    grid.setAttribute("aria-busy", state.matrixState === "connecting" ? "true" : "false")
    // Preserve the immediate skeleton until the first matrix request settles.
    if (!state.firstMatrixLoaded && state.matrixState === "connecting" && Object.keys(state.cells).length === 0) {
      renderRail()
      return
    }
    const focusedCellId = document.activeElement?.classList.contains("cell-select")
      ? document.activeElement.dataset.cellId
      : null
    grid.replaceChildren()
    const search = state.search.toLowerCase()
    const ids = core.sortCellIds(state.cells).filter((cellId) => {
      const status = core.normalizeStatus(state.cells[cellId])
      const matchesFilter = state.filter === "all"
        || (state.filter === "running" && status === "running")
        || (state.filter === "risk" && ["failed", "timeout", "unknown"].includes(status))
      return matchesFilter && cellId.toLowerCase().includes(search)
    })

    if (Object.keys(state.cells).length === 0 && state.matrixState !== "connecting") {
      grid.appendChild(element("p", "empty-state", "No cells are queued or retained"))
    } else if (ids.length === 0) {
      grid.appendChild(element("p", "empty-state", "No cells match the current fleet filter"))
    }

    for (const cellId of ids) {
      const status = core.normalizeStatus(state.cells[cellId])
      const selected = state.selectedId === cellId
      const card = element("article", `cell-card status-${status}${selected ? " selected" : ""}`)
      const button = element("button", "cell-select")
      button.type = "button"
      button.dataset.cellId = cellId
      button.setAttribute("aria-label", status === "running" ? `Watch running cell ${cellId}` : `Inspect cell ${cellId}`)
      button.setAttribute("aria-pressed", String(selected))
      button.addEventListener("click", () => selectCell(cellId, true))

      const heading = element("div", "cell-heading")
      const statusLabel = element("span", `status-word status-${status}`, `${STATUS_SYMBOLS[status]} ${status.toUpperCase()}`)
      heading.appendChild(statusLabel)
      if (selected) heading.appendChild(element("span", "selected-label", "SELECTED"))
      button.appendChild(heading)
      button.appendChild(element("span", "cell-id", cellId))

      const samples = samplesForCell(cellId)
      const costs = samples.map((sample) => core.safeNumber(sample.cost)).filter((value) => value !== null)
      button.appendChild(element("span", "latest-cost", costs.length ? `${formatCost(costs.at(-1))} latest reported step` : "no cost yet"))
      button.appendChild(createSparkline(samples))
      card.appendChild(button)
      if (selected) {
        const jump = element("a", "mobile-anchor card-jump", "Jump to transcript")
        jump.href = "#transcript-panel"
        card.appendChild(jump)
      }
      grid.appendChild(card)
    }

    // A status or telemetry update must not eject a keyboard operator from the fleet.
    if (focusedCellId) {
      const focusedReplacement = Array.from(grid.querySelectorAll(".cell-select"))
        .find((button) => button.dataset.cellId === focusedCellId)
      focusedReplacement?.focus({ preventScroll: true })
    }

    const counts = statusCounts()
    $("#fleet-total").textContent = String(Object.keys(state.cells).length)
    const countText = ["queued", "running", "done", "failed", "timeout"]
      .map((status) => `${status} ${counts[status]}`)
      .join("  ·  ")
    $("#fleet-counts").textContent = countText
    renderRail()
  }

  /** Synchronize transcript and read-only control headers with one selection. */
  function renderSelection() {
    const cellId = state.selectedId
    const status = cellId ? core.normalizeStatus(state.cells[cellId]) : "unknown"
    $("#transcript-title").textContent = cellId || "NO CELL SELECTED"
    $("#selected-status").textContent = status.toUpperCase()
    $("#selected-status").className = `status-word status-${status}`
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
  }

  /** Render normalized transcript rows and preserve follow only when requested. */
  function renderTranscript(scrollToBottom = false) {
    const feed = $("#transcript-feed")
    feed.replaceChildren()
    if (!state.selectedId) {
      feed.appendChild(element("div", "terminal-empty", "Select a fleet card to inspect retained events and watch live work."))
    } else if (state.rows.length === 0) {
      const message = state.streamState === "connecting"
        ? "Connecting to retained history…"
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
    node.appendChild(element("div", "row-text", row.text))
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
    const changed = state.selectedId !== cellId
    if (changed) {
      if (state.eventSource) state.eventSource.close()
      state.eventSource = null
      state.selectedId = cellId
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
      state.telemetry = data.telemetry && typeof data.telemetry === "object"
        ? data.telemetry
        : { cells: {}, reported_cost: null, input_tokens: null, output_tokens: null }
      state.matrixState = state.telemetry.available === false ? "disconnected" : "live"
      state.lastMatrixAt = Date.now()
      pruneReconciledSamples(requestSequence)
      renderFleet()
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
        headers: { "Content-Type": "application/json" },
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
  }

  /** Register all local controls after the immediate shell has rendered. */
  function bindControls() {
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
      state.routingOpen = false
      $("#routing-drawer").hidden = true
      $("#routing-toggle").setAttribute("aria-expanded", "false")
      state.routingReturnFocus?.focus()
    })
    $("#routing-refresh").addEventListener("click", loadRouting)
    $("#enqueue-button").addEventListener("click", () => runQueueAction("enqueue"))
    $("#clear-queue-button").addEventListener("click", () => {
      const warning = "This clears queued metadata; it does not cancel running work."
      if (window.confirm(warning)) runQueueAction("clear")
    })
  }

  bindControls()
  renderFleet()
  renderSelection()
  tick()
  loadMatrix()
  connectStatusStream()
  window.setInterval(loadMatrix, MATRIX_POLL_MS)
  window.setInterval(tick, 1000)
})(window.ControlRoomCore)
