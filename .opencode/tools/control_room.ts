import { tool } from "@opencode-ai/plugin"

// CONVENTION BREAK: this tool talks HTTP (fetch) to a running apps/control_room/server.py, not
// Bun.$ to a scripts/*.py CLI — it targets a live Flask server, not a subprocess.
// It does NOT start the portal (that's `python3 apps/control_room/server.py`, unchanged).
//
// SECURITY CONSTRAINT (do not weaken): read-only GET endpoints only. Never wrap a POST
// route here (/api/flags/<id>/steer, /api/flags/<id>/interrupt,
// /api/design-sessions/<id>/interrupt, /api/claude-agents create/stop/respawn/rm/steer)
// — those are the human-operator control surface, and exposing them as an agent-callable
// tool would let a session steer or interrupt itself or a peer session through the one
// channel the architecture deliberately keeps flag-only. Same boundary as supervisor.ts.
const ENDPOINTS: Record<string, string> = {
  matrix: "/api/matrix",
  status: "/api/status",
  flags: "/api/flags",
  routing: "/api/routing",
  design_sessions: "/api/design-sessions",
  claude_agents: "/api/claude-agents",
  // Read-only operational surfaces added for the Units 4-5 delivery work (F0): the projection
  // health block, the one resting-screen projection, and the operational read models.
  projections: "/api/projections",
  glance: "/api/glance",
  operations: "/api/operations",
}

/** Hard deadline for ONE portal request: a live portal answers fast; a hung one must not
 *  hang the turn. */
const REQUEST_TIMEOUT_MS = 10_000

/**
 * The portal's base URL. Explicit `CONTROL_ROOM_URL` wins; otherwise compose from the same
 * `FINOPS_HOST`/`FINOPS_PORT` the portal's systemd unit declares; otherwise the compatible
 * loopback default (127.0.0.1:8000). Exported for the focused test.
 */
export function resolveBaseUrl(env: Record<string, string | undefined> = process.env): string {
  const explicit = (env.CONTROL_ROOM_URL || "").trim().replace(/\/+$/, "")
  if (explicit) return explicit
  const host = (env.FINOPS_HOST || "127.0.0.1").trim()
  const port = (env.FINOPS_PORT || "8000").trim()
  return `http://${host}:${port}`
}

export default tool({
  description:
    "Read-only GET query against the running Control Room portal (apps/control_room/server.py). Base URL: CONTROL_ROOM_URL, else http://$FINOPS_HOST:$FINOPS_PORT (default 127.0.0.1:8000). Requires the portal already running — this tool does not start it. NOTE: `status` is a Server-Sent-Events STREAM (it never completes), so a one-shot call to it will hit the request deadline; `glance` is the resting-screen read (the default).",
  args: {
    endpoint: tool.schema
      .enum([
        "matrix",
        "status",
        "flags",
        "routing",
        "design_sessions",
        "claude_agents",
        "projections",
        "glance",
        "operations",
      ])
      .optional()
      // The default must be a COMPLETE one-shot read: `status` streams forever, so using it
      // as the default made every default call die on the request deadline (found live during
      // the F0 post-restart verification). The resting screen's payload is `glance`.
      .default("glance"),
  },
  async execute(args) {
    // RUNTIME fallback (review finding P2): the OpenCode 1.18.15 custom-tool path validates
    // with the schema but forwards the ORIGINAL arguments — Zod's parsed/defaulted result is
    // discarded — so a schema-level `.default()` never reaches execute and `{}` would build
    // `...undefined`. Resolve the default HERE and use the resolved value everywhere.
    const endpoint = args.endpoint ?? "glance"
    const url = `${resolveBaseUrl()}${ENDPOINTS[endpoint]}`

    let res: Response
    let text: string
    try {
      res = await fetch(url, { signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS) })
      // Body consumption belongs INSIDE the error boundary (review fix): a server may send
      // headers and then stall the body — that must surface as `unavailable`, never as an
      // uncaught deadline escaping the tool's structured outcome.
      text = await res.text()
    } catch (e) {
      // Unavailable service: distinguish the deadline from other transport failures, keep the
      // real reason, and never fabricate data.
      const reason =
        e instanceof Error && e.name === "TimeoutError"
          ? `no response within ${REQUEST_TIMEOUT_MS}ms`
          : e instanceof Error
            ? e.message
            : String(e)
      return {
        output: `Control Room portal unavailable at ${url}: ${reason}. Start it with: python3 apps/control_room/server.py`,
        metadata: { endpoint, url, outcome: "unavailable" },
      }
    }

    if (!res.ok) {
      // Non-success response: the HTTP status is the answer; the body is passed through.
      return {
        output: text || `Control Room request failed (HTTP ${res.status})`,
        metadata: { endpoint, url, status: res.status, outcome: "non-success" },
      }
    }

    return {
      output: text,
      metadata: { endpoint, url, timestamp: new Date().toISOString(), outcome: "ok" },
    }
  },
})
