# Claude Code Background Sessions Scope

## 1. Problem

The Control Room already hosts a native supervisor surface for OpenCode:
`admin/opencode_client.py` talks to the running OpenCode server, and
`scripts/supervise.py` relays native sessions into the Control Room's
Redis-backed event streams and flags stalled/off-track work for human review.
There is no equivalent surface for Claude Code's own background-session
mechanism.

`src/instrument/claude_adapter.py` drives the `claude` CLI today, but only in
headless, single-shot mode: `run_claude_agentic` builds one
`claude -p "<prompt>" --output-format stream-json --dangerously-skip-permissions
[--model ...]` subprocess, streams its `stream-json` events through
`ClaudeStreamAdapter`, and returns when that one process exits
[src/instrument/claude_adapter.py:236-346]. It never enumerates, attaches to,
or controls a `claude --bg` background session, and it maps the framework's
advisor-model id `claude-fable-5` to `claude-sonnet-5` for the primary model
[src/instrument/claude_adapter.py:185-211] — Claude Code's own
`--advisor fable` server-side advisor is a distinct mechanism, unused today.

Claude Code separately ships a background-session product: `claude --bg`
starts a supervised session that keeps running after the launching terminal
exits, `claude agents` lists and monitors those sessions, and `claude attach`,
`claude logs`, `claude stop`/`kill`, `claude respawn`, and `claude rm` manage
one session's lifecycle, all hosted by a `claude daemon` supervisor process.
None of this is visible from the Control Room. An operator who dispatches a
`claude --bg` task today has no fleet card, no transcript, and no lifecycle
controls inside the command rail — they have to shell out separately, which
is exactly the gap the OpenCode native surface already closed for OpenCode.

This feature adds the Claude analog: list, observe, and lifecycle-control
`claude --bg` sessions and the `claude daemon` that hosts them, inside the
existing Control Room, reusing its command-rail aesthetic and SSE/Redis
transport rather than building a second dashboard.

## 2. Investigated CLI Facts

Investigated against the Claude Code CLI reference,
<https://code.claude.com/docs/en/cli-reference>. Commands and flags below are
quoted from that reference; anything not stated there is called out as not
possible rather than inferred.

### Starting a background session

- `claude --bg "<task>"` / `claude --background "<task>"` — starts the task as
  a background agent and returns immediately, printing the session ID and
  management commands. Cannot be combined with `-p`/`--print`. Can combine
  with `--exec` to run a shell command as a background job instead of a Claude
  session, and with `--agent` to run a specific subagent.
- `--dangerously-skip-permissions`, when set on a `--bg` launch, persists
  across supervisor restarts for that session (i.e., a respawn keeps the
  original permission mode).

### Listing / observing

- `claude agents` — opens an interactive terminal "agent view" for monitoring
  and dispatching background sessions; **requires an interactive terminal**,
  so it is not something a Flask backend can drive headlessly.
- `claude agents --json` — prints active sessions as a JSON array, scriptable.
- `claude agents --json --all` — same, but includes completed background
  sessions.
- `claude agents --cwd <path>` — restricts the listing to sessions started
  under that directory.
- `claude logs <id>` — prints recent output from one background session. This
  is a plain, non-interactive stdout dump — safe to call headlessly and diff.
- `claude attach <id>` — attaches to a background session **in a terminal**
  to view and follow it live; the reference explicitly scopes this to
  "view/follow," not steering input, and — like `claude agents` — implies a
  real interactive TTY, not a scriptable stream.
- `claude daemon status` — prints the background-session supervisor's state,
  version, socket directory, and worker count; exits 1 if the supervisor
  isn't running.

### Lifecycle control

- `claude stop <id>` / `claude kill <id>` (`kill` is an alias for `stop`) —
  stops a background session.
- `claude respawn <id>` — restarts a background session, running or stopped,
  **with its conversation intact**. `claude respawn --all` restarts every
  running session (e.g., to pick up an updated Claude Code binary).
- `claude rm <id>` — removes a session from the list. The transcript is not
  deleted; it stays on disk and remains reachable via `claude --resume`.
- `claude daemon stop --any` — stops the background-session supervisor and
  every session it hosts. `--any` is required to confirm stopping an
  on-demand supervisor (the default supervisor kind). `--keep-workers` leaves
  the background sessions running so the next supervisor reconnects to them
  instead of killing them. This is the documented recovery path for an
  unresponsive supervisor.

### Advisor

- `--advisor <model>` (e.g. `--advisor fable`, `--advisor opus`,
  `--advisor sonnet`, or a full model ID) enables the server-side advisor tool
  for a session, and works with any session mode, including background
  (`claude --bg --advisor fable "task"`). `fable` requires Fable 5 access. It
  takes precedence over the `advisorModel` setting. This is a pass-through
  launch flag, not something the Control Room implements — it only needs to
  be exposed as an optional start-time input.

### What is explicitly NOT possible

The reference documents no way to send input to, or otherwise interactively
steer, a *running* background session. `attach` is view/follow only; there is
no `claude bg send`, no prompt-injection command, and no documented
`delivery: steer` equivalent to OpenCode's native
`POST /api/session/{id}/prompt` [contrast with admin/opencode_client.py:94-102].
Concretely:

- **Interrupt has no direct analog.** OpenCode's `interrupt` stops active work
  *without* ending the session [admin/opencode_client.py:104-107]. Claude
  Code's closest primitives are `stop` (ends the session; conversation is
  preserved but the process is gone) and `respawn` (restarts the session with
  its conversation intact, effectively resuming after a stop). Neither is a
  live, in-flight interrupt-and-keep-running.
- **There is no send-input / steer control.** This spec deliberately does not
  invent one. Any control surface for background sessions is limited to the
  lifecycle verbs the CLI actually exposes: stop/kill, respawn, rm, and
  daemon stop.
- **`claude agents` and `claude attach` need a real TTY**, so this feature
  uses only the scriptable subset (`claude agents --json --all`,
  `claude logs <id>`, `claude daemon status`, and the lifecycle commands)
  driven via `subprocess`, the same way `claude_adapter.py` already drives the
  CLI for headless runs [src/instrument/claude_adapter.py:291-299].

## 3. Chosen Integration Approach

### Decision

Add a small `admin/claude_agents_client.py` subprocess wrapper around the
scriptable `claude` subcommands above (list, start, logs, stop, respawn, rm,
daemon status), mirroring the shape of `OpenCodeClient`
[admin/opencode_client.py] but calling a CLI instead of an HTTP API. Add a
lightweight poller (module-level thread or endpoint-triggered refresh, not a
new always-on service) that periodically runs `claude agents --json --all` to
refresh a Redis-cached roster, and — for the currently selected/attached
session only — diffs `claude logs <id>` output and republishes new lines
through the existing `LivePublisher` event/log channel used by
`instrument/live.py`, under a distinct `cell_id` namespace (e.g.
`claude_bg_<session-id>`). The existing `GET /api/events/<cell_id>` SSE
endpoint, its retained-history replay, and its `replay_complete` boundary
[admin/server.py:450-490] then serve the transcript with zero new SSE
machinery. Add new `POST`-mutating endpoints for start/stop/respawn/rm/daemon
actions, all behind the loopback + JSON + Idempotency-Key guard the
design-session endpoints already enforce [admin/server.py:104-124, 127-178].

The frontend gets one additive fleet section — "Claude background sessions"
— rendered with the same card list, selection, and transcript hand-off
pattern `selectCell`/`selectDesignSession` already use
[admin/static/app.js:721-796], not a new page or visual language. Lifecycle
buttons (Stop, Respawn, Rm) use the same `window.confirm`-gated pattern as the
existing Interrupt control [admin/static/app.js:1284-1300], and Detach stays
a browser-only `EventSource.close()` with no process effect
[admin/static/app.js:803-811].

### Rationale

- **Subprocess, not a new client library or service.** `claude_adapter.py`
  already resolves the CLI binary and drives it via subprocess for headless
  runs [src/instrument/claude_adapter.py:36-46, 291-299]; there is no HTTP API
  for background sessions to call instead — the CLI *is* the contract. This
  keeps the pattern consistent with the one Claude Code integration this
  repo already has, and avoids adding a daemon RPC client that isn't
  documented.
- **`claude logs` polling instead of `claude attach`.** `attach` is
  documented as an interactive terminal follow, the same category as
  `claude agents`'s own "requires an interactive terminal" caveat. Wiring a
  no-TTY subprocess to `attach` risks it blocking on terminal I/O or emitting
  control codes meant for a real terminal. `logs` is a plain stdout dump,
  safe to call on an interval and diff — the same shape as
  `scripts/supervise.py`'s existing poll-and-relay loop
  [scripts/supervise.py:81-94, 158-176, 243-269], just polling a CLI command
  instead of an HTTP session.
- **Reuse the `cell_id`-namespaced relay-into-`/api/events/<cell_id>` pattern.**
  `scripts/supervise.py` already proves this pattern for OpenCode: it invents
  a readable `cell_id` per native session (`_cell_id_for`,
  [scripts/supervise.py:151-155]) and relays that session's events into the
  Control Room's existing Redis event log/channel so the frontend needs no
  new stream type [scripts/supervise.py:158-176]. Background Claude sessions
  do the same under a `claude_bg_` prefix, so `admin/server.py`'s SSE
  endpoint, replay boundary, and frontend transcript renderer need no changes.
- **No steer/send-input control, anywhere in the surface.** The CLI reference
  has no equivalent to OpenCode's `delivery: queue|steer` prompt admission
  [admin/opencode_client.py:94-102]. Inventing one (e.g. by piping into a
  wrapped subprocess's stdin) would control a mechanism the CLI doesn't
  document as supported and could silently corrupt session state. The
  Control Room's job here is Observe (list, logs, daemon status) and a
  narrow, confirmed Control (start, stop/kill, respawn, rm, daemon stop) —
  not steering.
- **Reuse the existing model-alias table and workdir-allowlist pattern.**
  Background-session start should call `_resolve_claude_model`
  [src/instrument/claude_adapter.py:203-211] so a UI-selected model produces
  the exact same `--model` argument the headless adapter already produces,
  and should restrict `--cwd`/launch directory the same way design sessions
  restrict `workdir` to a configured allowlist
  [admin/server.py:81-101], rather than accepting an arbitrary path from the
  browser.
- **Daemon-stop is scoped as a rare, heavily-gated action, not a routine
  control.** `claude daemon stop` affects every session the supervisor hosts,
  not just ones the Control Room started. It is exposed only as an explicit,
  separately confirmed action, defaults to `--keep-workers` (sessions survive
  and the next supervisor reconnects to them) unless the operator
  affirmatively also wants to end running sessions, and is not offered from
  any bulk or default control.

## 4. Constraints

- Extend `admin/server.py` and `admin/static/` additively. Do not modify
  `admin/opencode_client.py`, `scripts/supervise.py`, or any
  `/api/design-sessions*` behavior — that surface belongs to a different
  feature owner and this feature must not change its endpoints, Redis keys,
  or semantics.
- Drive `claude` exclusively via `subprocess`, matching
  `src/instrument/claude_adapter.py`'s existing pattern. No new network
  service, no daemon RPC client, no polling of an undocumented socket
  protocol — only the CLI surfaces named in section 2.
- Do not implement, expose, or imply a send-input/steer control for a running
  background session. If the CLI reference gains one in the future, treat
  that as new investigation, not something to anticipate now.
- Reuse `GET /api/events/<cell_id>` and its retained-history/`replay_complete`
  contract [admin/server.py:450-490] for background-session transcripts. Do
  not add a second SSE endpoint shape or a new frontend stream type.
- Reuse the loopback + same-origin + JSON + `Idempotency-Key` mutation guard
  [admin/server.py:104-178] for every new `POST` endpoint (start, stop,
  respawn, rm, daemon stop), exactly as `/api/design-sessions/*` already does.
- Every destructive action — `stop`/`kill`, `rm`, `daemon stop` — is a
  one-way door from the operator's perspective and requires an explicit
  confirmation step in the UI before the request is sent, matching the
  existing Interrupt confirmation pattern [admin/static/app.js:1284-1300].
  `respawn` is control but not destructive (conversation survives) and does
  not require the same confirmation weight, though it should still be a
  deliberate click, not a default action.
- `claude daemon stop` defaults to `--keep-workers`; only an explicit,
  separately labeled operator choice omits it and allows sessions to be
  killed along with the supervisor.
- Restrict where background sessions can be started to a configured directory
  allowlist, reusing the shape of the existing `workdirs` mapping
  [admin/server.py:81-101]. Never accept an arbitrary filesystem path from
  the browser as a launch `--cwd`.
- Reuse `_resolve_claude_model`
  [src/instrument/claude_adapter.py:203-211] for model selection so background
  sessions and headless runs resolve framework model ids identically.
  `--advisor` is passed straight through as an optional string from a small
  fixed set (`fable`, `opus`, `sonnet`, or a full model id); do not build new
  advisor logic.
- No new build step, dependency, or frontend framework. Python + the existing
  vanilla JS/CSS static app remain the implementation surface, per the
  Control Room's existing constraints.
- Bound poll frequency, JSON body size, and log-tail size the same way
  `/api/design-sessions` already bounds request size and prompt length
  [admin/server.py:66-67]; an unavailable `claude` binary or daemon must
  degrade to a visible error state, not hang the Flask request thread.

## 5. Acceptance Criteria

1. [ ] `admin/claude_agents_client.py` wraps `claude agents --json --all`,
   `claude --bg`, `claude logs <id>`, `claude stop <id>`,
   `claude respawn <id>`, `claude rm <id>`, and `claude daemon status` /
   `claude daemon stop --any [--keep-workers]` as subprocess calls, each
   returning parsed JSON or raw text plus a distinguishable error for a
   missing binary, non-zero exit, or timeout.
2. [ ] `GET /api/claude-agents` returns the cached/refreshed roster from
   `claude agents --json --all` (id, status, task/title, model, cwd,
   started/updated timestamps) without blocking on a live CLI call for every
   request.
3. [ ] `POST /api/claude-agents` starts a session via `claude --bg`, accepts
   only a workdir key from the configured allowlist (never a raw path),
   resolves the requested model through `_resolve_claude_model`, accepts an
   optional `--advisor` value from the fixed set, enforces the loopback/JSON/
   Idempotency-Key guard, and returns the new session id.
4. [ ] A background session's transcript is exposed through the existing
   `GET /api/events/<cell_id>` endpoint under a `claude_bg_<id>` cell id fed
   by a `claude logs <id>`-polling relay; no new SSE route or event schema is
   added, and the existing `replay_complete` boundary behavior is unchanged
   for both existing and new cell ids.
5. [ ] `POST /api/claude-agents/<id>/stop` (aliasing `kill`) requires the
   mutation guard, requires the caller to have gone through an explicit
   confirmation step client-side, and reports whether the CLI accepted the
   stop.
6. [ ] `POST /api/claude-agents/<id>/respawn` restarts the session and the
   response/roster reflects that its conversation id is unchanged.
7. [ ] `POST /api/claude-agents/<id>/rm` requires confirmation, removes the
   session from the roster, and the response/UI states plainly that the
   transcript remains on disk and is not deleted.
8. [ ] `GET /api/claude-agents/daemon` returns `claude daemon status` output
   (or a clear "supervisor not running" state derived from its exit code 1)
   as a read-only observation with no control affordance attached.
9. [ ] `POST /api/claude-agents/daemon/stop` is a separate, explicitly
   confirmed action; it defaults to `--keep-workers` and only omits it when
   the operator has made an additional, distinct choice to also end running
   sessions; the UI states that this affects every session the supervisor
   hosts, not just ones started from the Control Room.
10. [ ] No endpoint, UI control, or client method sends input to, prompts,
    or otherwise steers a running background session. Grepping the new code
    for anything resembling `delivery: steer` or a stdin-writing subprocess
    against an attached session finds nothing.
11. [ ] The Control Room fleet view gains a "Claude background sessions"
    section using the existing card/list visual language; selecting a card
    reuses the existing selection/EventSource hand-off and transcript pane
    instead of a new page or panel type.
12. [ ] Detach on a background-session card only closes the browser
    `EventSource`, exactly like existing cell/design-session Detach; it never
    calls stop, respawn, or rm.
13. [ ] All existing `/api/matrix`, `/api/status`, `/api/events/<cell_id>`,
    `/api/routing`, `/api/experiments`, and `/api/design-sessions*` behavior,
    Redis keys, and tests are unchanged by this feature.
14. [ ] Backend tests mock the `claude` subprocess (missing binary, non-zero
    exit, malformed JSON, timeout) and cover list/start/stop/respawn/rm/daemon
    status/daemon stop, the mutation guard on every new `POST` route, the
    workdir allowlist rejection path, and the model/advisor pass-through.
15. [ ] Frontend tests or a documented manual check cover: roster rendering,
    card selection reusing the shared transcript pane, confirmation prompts
    for stop/rm/daemon-stop, and that no UI path offers a "send" or "steer"
    action for a background session.
16. [ ] The repository's `pytest` suite passes unchanged for all
    pre-existing tests after this feature is implemented.
