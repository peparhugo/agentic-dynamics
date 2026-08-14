"use strict";

/**
 * Pure data helpers for the Control Room.
 *
 * Keeping parsing, reconciliation, and transcript normalization independent of
 * the DOM makes stream behavior deterministic and browser-free testable.
 */
(function exposeControlRoomCore(root) {
  const TERMINAL_STATUSES = new Set(["done", "failed", "timeout"])
  const STATUS_ORDER = { running: 0, failed: 1, timeout: 2, queued: 3, done: 4, unknown: 5 }

  /** Return only finite, non-negative numeric telemetry. */
  function safeNumber(value) {
    return typeof value === "number" && Number.isFinite(value) && value >= 0 ? value : null
  }

  /** Map producer status variants into the finite visual state vocabulary. */
  function normalizeStatus(value) {
    const status = typeof value === "string" ? value.toLowerCase() : ""
    return Object.prototype.hasOwnProperty.call(STATUS_ORDER, status) ? status : "unknown"
  }

  /** Normalize legacy hyphenated event names without changing unknown names. */
  function normalizeType(value) {
    return typeof value === "string" ? value.toLowerCase().replaceAll("-", "_") : ""
  }

  /** Parse a raw event while preserving malformed text for a RAW transcript row. */
  function parseEvent(raw) {
    if (raw && typeof raw === "object") return { event: raw, raw: JSON.stringify(raw), valid: true }
    const text = String(raw ?? "")
    try {
      const event = JSON.parse(text)
      return event && typeof event === "object"
        ? { event, raw: text, valid: true }
        : { event: null, raw: text, valid: false }
    } catch (_error) {
      return { event: null, raw: text, valid: false }
    }
  }

  /** Produce a short stable presentation key for transcript rows. */
  function eventKey(cellId, raw) {
    const text = `${cellId}\u0000${String(raw ?? "")}`
    let hash = 2166136261
    for (let index = 0; index < text.length; index += 1) {
      hash ^= text.charCodeAt(index)
      hash = Math.imul(hash, 16777619)
    }
    return (hash >>> 0).toString(16).padStart(8, "0")
  }

  /** Format numbers consistently with the Flask sample identity helper. */
  function identityNumber(value) {
    if (value === null) return ""
    return value.toFixed(12).replace(/0+$/, "").replace(/\.$/, "") || "0"
  }

  /** Read a producer-supplied timestamp without creating a fake event time. */
  function suppliedTimestamp(event, part) {
    for (const container of [event, part]) {
      for (const key of ["timestamp", "time", "created_at", "createdAt"]) {
        const value = container?.[key]
        if (typeof value === "string" || safeNumber(value) !== null) return value
      }
    }
    return null
  }

  /** Extract a chartable step sample from current and legacy event shapes. */
  function extractSample(raw) {
    const parsed = parseEvent(raw)
    if (!parsed.valid) return null
    const event = parsed.event
    if (normalizeType(event.type) !== "step_finish") return null
    const part = event.part && typeof event.part === "object" ? event.part : event
    const tokens = part.tokens && typeof part.tokens === "object" ? part.tokens : {}
    const inputTokens = safeNumber(tokens.input)
    const outputTokens = safeNumber(tokens.output)
    const reasoningTokens = safeNumber(tokens.reasoning)
    let cacheTokens = safeNumber(tokens.cache)
    if (tokens.cache && typeof tokens.cache === "object") {
      const values = [safeNumber(tokens.cache.read), safeNumber(tokens.cache.write)].filter(
        (value) => value !== null,
      )
      cacheTokens = values.length ? values.reduce((sum, value) => sum + value, 0) : null
    }
    let totalTokens = safeNumber(tokens.total)
    if (totalTokens === null) {
      const values = [inputTokens, outputTokens, reasoningTokens, cacheTokens].filter(
        (value) => value !== null,
      )
      totalTokens = values.length ? values.reduce((sum, value) => sum + value, 0) : null
    }
    const cost = safeNumber(part.cost)
    if (cost === null && totalTokens === null) return null

    const timestamp = suppliedTimestamp(event, part)
    const sessionId = event.sessionID || part.sessionID || ""
    const identity = [
      sessionId,
      timestamp ?? "",
      cost,
      inputTokens,
      outputTokens,
      reasoningTokens,
      cacheTokens,
      totalTokens,
    ]
      .map((value, index) => (index < 2 ? String(value) : identityNumber(value)))
      .join("|")
    return {
      identity,
      timestamp,
      cost,
      input_tokens: inputTokens,
      output_tokens: outputTokens,
      reasoning_tokens: reasoningTokens,
      cache_tokens: cacheTokens,
      total_tokens: totalTokens,
    }
  }

  /** Render a supplied timestamp in UTC, or an honest arrival marker. */
  function displayTimestamp(value) {
    if (value === null || value === undefined || value === "") return "received now"
    const date = new Date(value)
    if (Number.isNaN(date.getTime())) return String(value)
    return `${date.toISOString().slice(11, 19)} UTC`
  }

  /** Convert arbitrary values to readable text without trusting them as HTML. */
  function readable(value) {
    if (typeof value === "string") return value
    if (value === undefined) return ""
    try {
      return JSON.stringify(value, null, 2)
    } catch (_error) {
      return String(value)
    }
  }

  /** Normalize one raw stream event into a semantic terminal row. */
  function normalizeTranscriptEvent(raw, cellId = "") {
    const parsed = parseEvent(raw)
    if (!parsed.valid) {
      return {
        key: eventKey(cellId, parsed.raw),
        kind: "raw",
        label: "RAW",
        timestamp: "received now",
        text: parsed.raw,
        detail: "",
        sessionId: "",
        sample: null,
      }
    }

    const event = parsed.event
    const part = event.part && typeof event.part === "object" ? event.part : event
    const type = normalizeType(event.type)
    const common = {
      key: eventKey(cellId, parsed.raw),
      timestamp: displayTimestamp(suppliedTimestamp(event, part)),
      sessionId: event.sessionID || part.sessionID || "",
      sample: extractSample(event),
      detail: "",
    }
    if (type === "reasoning") {
      return { ...common, kind: "think", label: "THINK", text: readable(part.text) }
    }
    if (type === "text") {
      return { ...common, kind: "agent", label: "AGENT", text: readable(part.text) }
    }
    if (type === "tool_use" || type === "tool") {
      const tool = part.tool || part.name || "unknown"
      const toolState = part.state && typeof part.state === "object" ? part.state : {}
      const status = toolState.status || part.status || "observed"
      const input = toolState.input ?? part.input
      const output = toolState.output ?? part.output
      const summary = readable(input).replace(/\s+/g, " ").slice(0, 180) || "No input reported"
      return {
        ...common,
        kind: "tool",
        label: `TOOL ${tool}`,
        text: `${status} · ${summary}`,
        detail: readable(output),
      }
    }
    if (type === "step_start") {
      const number = part.step ?? part.id ?? ""
      return { ...common, kind: "step-start", label: "STEP START", text: number ? `Step ${number}` : "New step" }
    }
    if (type === "step_finish") {
      const sample = common.sample
      const fields = []
      if (sample?.input_tokens !== null) fields.push(`${sample.input_tokens.toLocaleString()} in`)
      if (sample?.output_tokens !== null) fields.push(`${sample.output_tokens.toLocaleString()} out`)
      if (sample?.reasoning_tokens !== null) fields.push(`${sample.reasoning_tokens.toLocaleString()} reasoning`)
      if (sample?.cache_tokens !== null) fields.push(`${sample.cache_tokens.toLocaleString()} cache`)
      if (sample?.cost !== null) fields.push(`$${sample.cost.toFixed(4)} reported`)
      return { ...common, kind: "step", label: "STEP", text: fields.join(" · ") || "No usage reported" }
    }
    return {
      ...common,
      kind: "event",
      label: "EVENT",
      text: type || "Unknown JSON event",
      detail: readable(event),
    }
  }

  /** Append in order while enforcing the shared 500-entry presentation bound. */
  function boundedAppend(current, additions, limit = 500) {
    return current.concat(additions).slice(-limit)
  }

  /** Merge live, not-yet-polled samples over the authoritative snapshot. */
  function reconcileTelemetry(snapshot, liveSamplesByCell) {
    const telemetry = snapshot && typeof snapshot === "object" ? snapshot : {}
    const overlays = []
    for (const samples of liveSamplesByCell.values()) overlays.push(...samples)
    const sumField = (base, field) => {
      const values = overlays.map((sample) => safeNumber(sample[field])).filter((value) => value !== null)
      const validBase = safeNumber(base)
      if (validBase === null && values.length === 0) return null
      return (validBase ?? 0) + values.reduce((sum, value) => sum + value, 0)
    }
    return {
      reported_cost: sumField(telemetry.reported_cost, "cost"),
      input_tokens: sumField(telemetry.input_tokens, "input_tokens"),
      output_tokens: sumField(telemetry.output_tokens, "output_tokens"),
      overlays,
    }
  }

  /** Sum valid live cost deltas in the fixed rolling 60-second window. */
  function burnRate(samples, now = Date.now(), windowMs = 60000) {
    return samples
      .filter((sample) => now - sample.receivedAt <= windowMs && now >= sample.receivedAt)
      .map((sample) => safeNumber(sample.cost))
      .filter((value) => value !== null)
      .reduce((sum, value) => sum + value, 0)
  }

  /** Return cell IDs in urgency-first, deterministic order. */
  function sortCellIds(cells) {
    return Object.keys(cells).sort((left, right) => {
      const statusDifference = STATUS_ORDER[normalizeStatus(cells[left])] - STATUS_ORDER[normalizeStatus(cells[right])]
      return statusDifference || left.localeCompare(right)
    })
  }

  /** Close the prior selected-cell source before constructing its replacement. */
  function replaceEventSource(current, EventSourceClass, url) {
    if (current) current.close()
    return new EventSourceClass(url)
  }

  const core = {
    TERMINAL_STATUSES,
    safeNumber,
    normalizeStatus,
    parseEvent,
    eventKey,
    extractSample,
    normalizeTranscriptEvent,
    boundedAppend,
    reconcileTelemetry,
    burnRate,
    sortCellIds,
    replaceEventSource,
  }
  root.ControlRoomCore = core
  if (typeof module !== "undefined" && module.exports) module.exports = core
})(typeof globalThis !== "undefined" ? globalThis : window)
