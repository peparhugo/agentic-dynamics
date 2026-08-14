---
name: control-room
description: Read-only GET queries against a running admin/server.py Control Room portal (matrix/status/flags/routing/design-sessions/claude-agents) and a one-shot supervisor assessment pass via supervise.py. Use when asked to check the Control Room, inspect supervisor flags, view the experiment matrix/routing recommendations, or run a supervisor pass — never to steer, interrupt, or otherwise control a running session.
disable-model-invocation: false
user-invocable: false
argument-hint: ""
---

# Control Room Skill — Read-Only Observation Only

**Boundary, stated up front because it is the entire reason this skill exists as written:**
this skill is a **flag-only, observe-never-steer** rail onto `admin/server.py`'s Control
Room portal and `scripts/supervise.py`. It exposes GET-only reads. **Never** issue a POST to
any of `admin/server.py`'s control routes (`/api/flags/<id>/steer`,
`/api/flags/<id>/interrupt`, `/api/design-sessions/<id>/interrupt`, or the
`/api/claude-agents` create/stop/respawn/rm/steer routes) — those are the human-operator
control surface, and exposing them as an agent-callable action would let a session steer or
interrupt itself or a peer session through the one channel the architecture deliberately
keeps flag-only. See `docs/supervisor_design.md` for the full design.

## `admin/server.py` — GET endpoints

Port: `admin/server.py:1365`, `int(os.environ.get("FINOPS_PORT", "8000"))`. Requires the
portal already running (`python admin/server.py`) — this skill does not start it.

6 confirmed `@app.get(...)` routes:

```
admin/server.py:738  GET /api/matrix           — experiment cell status matrix
admin/server.py:779  GET /api/status           — SSE stream (see hazard note below)
admin/server.py:805  GET /api/flags            — supervisor flags
admin/server.py:860  GET /api/routing          — routing recommendations
admin/server.py:903  GET /api/design-sessions  — design session state
admin/server.py:1094 GET /api/claude-agents    — Claude background session state
```

Primary example — lead with `/api/matrix`, not `/api/status`:

```bash
curl -s "http://127.0.0.1:${FINOPS_PORT:-8000}/api/matrix"
curl -s "http://127.0.0.1:${FINOPS_PORT:-8000}/api/flags"
curl -s "http://127.0.0.1:${FINOPS_PORT:-8000}/api/routing"
curl -s "http://127.0.0.1:${FINOPS_PORT:-8000}/api/design-sessions"
curl -s "http://127.0.0.1:${FINOPS_PORT:-8000}/api/claude-agents"
```

### `/api/status` is a hazard — do not bare-`curl` it

`/api/status` (`admin/server.py:779-802`) is a Flask **SSE endpoint**: its generator loop
does `while True: ... yield ": ping\n\n"` and never terminates on its own — only a client
disconnect stops it. A plain `curl -s`/`fetch()`+`.text()` blocks waiting for a connection
close that never comes, i.e. it hangs the calling process. If `/api/status` must be read,
use a bounded read instead:

```bash
curl -s --max-time 5 "http://127.0.0.1:${FINOPS_PORT:-8000}/api/status"
```

or a real SSE client. Never default an example or a script to a bare GET on this endpoint.

## `scripts/supervise.py` — one-shot assessment pass

Confirmed flags, `scripts/supervise.py:348-350`:

```
--once            flag — run one assessment pass and exit
--location PATH   default: str(ROOT) — repo location for the monitor session
```

```bash
python3 scripts/supervise.py --once --location "$(pwd)"
```

Same observe-only boundary applies here, restated from `supervisor.ts`'s own header comment:
`src/instrument/supervisor.py` deliberately has **no OpenCode client dependency** "so
observation can't become control" — never add a mode, flag, or follow-up action here that
lets an agent steer or interrupt a session.

### Prerequisite: a running opencode server

`supervise.py` instantiates `OpenCodeClient(BASE_URL)` where
`BASE_URL = os.environ.get("OPENCODE_BASE_URL", "http://127.0.0.1:4096")`
(`scripts/supervise.py:34`) to create its flash monitor session — this is independent of
whether the *caller* is Claude Code or opencode. Running `supervise.py` cold, with no
opencode server listening on port 4096 (or `$OPENCODE_BASE_URL`), fails with a connection
error, not a helpful message. Check for a running opencode server (or set
`OPENCODE_BASE_URL`) before running this.

## Common gotchas

- Every route in this skill is GET-only. If a task seems to require steering a session
  (pausing it, injecting a flag response, stopping a Claude background agent), that is out
  of scope for this skill — say so rather than reaching for the POST routes.
- `/api/status` hangs a bare `curl`/`fetch` — always bound it or skip it in favor of the
  5 plain-JSON endpoints.
- `supervise.py` needs an opencode server on port 4096 (or `$OPENCODE_BASE_URL`) even when
  invoked from Claude Code, since it talks to opencode's API to create its monitor session.
