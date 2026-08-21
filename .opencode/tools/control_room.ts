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
}

export default tool({
  description:
    "Read-only GET query against the running Control Room portal (apps/control_room/server.py). Requires the portal already running on FINOPS_PORT (default 8000) — this tool does not start it.",
  args: {
    endpoint: tool.schema.enum(["matrix", "status", "flags", "routing", "design_sessions", "claude_agents"]).optional().default("status"),
  },
  async execute(args) {
    const port = process.env.FINOPS_PORT || "8000"
    const url = `http://127.0.0.1:${port}${ENDPOINTS[args.endpoint]}`

    let res: Response
    try {
      res = await fetch(url)
    } catch (e) {
      return `Control Room portal not reachable at ${url}. Start it with: python3 apps/control_room/server.py`
    }

    const text = await res.text()
    if (!res.ok) {
      return { output: text || `Control Room request failed (HTTP ${res.status})`, metadata: { endpoint: args.endpoint, status: res.status } }
    }

    return {
      output: text,
      metadata: { endpoint: args.endpoint, url, timestamp: new Date().toISOString() },
    }
  },
})
