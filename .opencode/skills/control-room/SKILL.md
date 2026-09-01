---
name: control-room
description: Read-only GET queries against a running apps/control_room/server.py Control Room portal (matrix/status/flags/routing/design-sessions/claude-agents) and a one-shot supervisor assessment pass via supervise.py. Use when asked to check the Control Room, inspect supervisor flags, view the experiment matrix/routing recommendations, or run a supervisor pass — never to steer, interrupt, or otherwise control a running session.
disable-model-invocation: false
user-invocable: false
argument-hint: ""
---

# Control Room Skill — Read-Only Observation Only

**Boundary, stated up front because it is the entire reason this skill exists as written:**
this skill is a **flag-only, observe-never-steer** rail onto the Control Room portal
(`apps/control_room/server.py`) and `scripts/supervise.py`. It exposes GET-only reads. **Never**
issue a POST to any control route (`/api/flags/<id>/steer`, `/api/flags/<id>/interrupt`,
`/api/docs-health/approve` — the docs-remediation signature is the CONTROLLER's, never an agent's,
`/api/design-sessions/<id>/interrupt`, or the `/api/claude-agents` create/stop/respawn/rm/steer
routes) — those are the human-operator control surface, and exposing them as an agent-callable
action would let a session steer or interrupt itself or a peer session through the one channel
the architecture deliberately keeps flag-only. See `docs/architecture/current/supervisor_design.md`
for the full design.

## `apps/control_room/server.py` — GET endpoints

Port: `int(os.environ.get("FINOPS_PORT", "8000"))`. Requires the portal already running
(`python3 apps/control_room/server.py`) — this skill does not start it.

Routes are registered from `apps/control_room/routes/` (`telemetry.py`, `flags.py`,
`registry.py`, `design_sessions.py`, `claude_agents.py`, `docs_health.py`, `index.py`).
The plain-JSON GET endpoints you may read:

```
GET /api/matrix           — experiment cell status matrix        (routes/telemetry.py)
GET /api/routing          — routing recommendations              (routes/telemetry.py)
GET /api/flags            — supervisor flags                     (routes/flags.py)
GET /api/registry         — knowledge registry                   (routes/registry.py)
GET /api/registry/<id>    — registry lineage                     (routes/registry.py)
GET /api/design-sessions  — design session state                 (routes/design_sessions.py)
GET /api/claude-agents    — Claude background session state      (routes/claude_agents.py)
GET /api/docs-health      — docs-drift health + proposal state   (routes/docs_health.py)
```

Primary example — lead with `/api/matrix`, not `/api/status`:

```bash
curl -s "http://127.0.0.1:${FINOPS_PORT:-8000}/api/matrix"
curl -s "http://127.0.0.1:${FINOPS_PORT:-8000}/api/flags"
curl -s "http://127.0.0.1:${FINOPS_PORT:-8000}/api/routing"
curl -s "http://127.0.0.1:${FINOPS_PORT:-8000}/api/design-sessions"
curl -s "http://127.0.0.1:${FINOPS_PORT:-8000}/api/claude-agents"
curl -s "http://127.0.0.1:${FINOPS_PORT:-8000}/api/docs-health"
```

### `/api/status` is a hazard — do not bare-`curl` it

`/api/status` (`routes/telemetry.py`) is a Flask **SSE endpoint**: its generator loop
`while True: ... yield ": ping\n\n"` never terminates on its own — only a client disconnect
stops it. A plain `curl -s`/`fetch()`+`.text()` blocks waiting for a connection close that never
comes. If `/api/status` must be read, use a bounded read:

```bash
curl -s --max-time 5 "http://127.0.0.1:${FINOPS_PORT:-8000}/api/status"
```

or a real SSE client. Never default an example or a script to a bare GET on this endpoint.

## `scripts/supervise.py` — one-shot assessment pass

```bash
python3 scripts/supervise.py --once --location "$(pwd)"
```

Flags: `--once` (run one assessment pass and exit), `--location PATH` (repo location for the
monitor session, default cwd). Same observe-only boundary applies here, restated from the module
docstring: `agentic_dynamics.control.supervisor` deliberately has **no OpenCode client
dependency** — "observation metadata only … prevents flag persistence and stream indexing from
crossing the observation-to-control boundary." Never add a mode, flag, or follow-up action here
that lets an agent steer or interrupt a session.

### Prerequisite: a running opencode server

`supervise.py` creates its flash monitor session through an opencode client at
`OPENCODE_BASE_URL` (default `http://127.0.0.1:4096`) — this is independent of whether the
*caller* is Claude Code or opencode. Running `supervise.py` cold, with no opencode server
listening on port 4096 (or `$OPENCODE_BASE_URL`), fails with a connection error, not a helpful
message. Check for a running opencode server (or set `OPENCODE_BASE_URL`) before running this.

## Common gotchas

- Every route in this skill is GET-only. If a task seems to require steering a session (pausing
  it, injecting a flag response, stopping a Claude background agent), that is out of scope for
  this skill — say so rather than reaching for the POST routes.
- `/api/status` hangs a bare `curl`/`fetch` — always bound it or skip it in favor of the plain-JSON
  endpoints.
- `supervise.py` needs an opencode server on port 4096 (or `$OPENCODE_BASE_URL`) even when
  invoked from Claude Code, since it talks to opencode's API to create its monitor session.
