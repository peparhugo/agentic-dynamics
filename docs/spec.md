# Spec: Claude Code Background Sessions in the Control Room

Status: design spec, ready for implementation planning. Builds on
`docs/scope.md` (CLI investigation + chosen approach) and
`docs/challenge.md` (adversarial review of that approach). This document is
the synthesis: every challenge point is adjudicated explicitly in §4, and the
adjudication changes the design in §1–§3 rather than sitting beside it.

## 0. What this feature is, in one paragraph

The Control Room already surfaces OpenCode's native sessions through
`admin/opencode_client.py` (HTTP) and `scripts/supervise.py` (a separate
poll-and-relay process). Claude Code has no HTTP API for background
sessions — the `claude` CLI itself is the only documented contract
(`claude --bg`, `claude agents --json --all`, `claude logs`, `claude stop`/
`kill`, `claude respawn`, `claude rm`, `claude daemon status`/`stop`). This
feature adds a parallel fleet section, "Claude background sessions," that
lists those sessions, relays their output into the Control Room's existing
SSE transport, and offers a narrow, confirmed set of lifecycle controls —
without inventing any steering capability the CLI doesn't document.

## 1. Design overview

### 1.1 Scope of this phase

In scope: **observe** (roster, per-session transcript tail, daemon status)
and **lifecycle control** (start, stop/kill, respawn, rm, daemon stop) for
`claude --bg` sessions, reusing the Control Room's existing card/transcript
UI and SSE plumbing.

Out of scope, explicitly: an AI health-flagging monitor analogous to
`scripts/supervise.py`'s flash-model "healthy / stalled / off_track"
assessment loop over OpenCode sessions. `docs/scope.md`'s Problem section
motivates this feature by naming both halves of the OpenCode surface —
observe/control (`opencode_client.py`) *and* flagging (`supervise.py`) — but
the Chosen Integration Approach only builds the first half. §4.4 records this
as a deliberate phasing decision, not an oversight: `claude logs <id>`
output is exactly the kind of text `supervise_once`'s batching already knows
how to summarize, so a Claude-session flagging monitor is a real, buildable
follow-on once this phase's log relay exists to feed it — just not part of
this delivery.

### 1.2 Session ownership: the central design decision

Claude Code's `claude agents --json --all` lists **every** background
session the local `claude daemon` supervisor hosts, including ones an
operator started by hand in an unrelated terminal — the CLI has no concept
of "sessions this UI started." Left unaddressed, that means the Control
Room would render Stop/Respawn/Rm buttons on sessions it has no relationship
to. This spec resolves that (§4.1) by splitting every session the roster
returns into two classes:

- **Owned** — started via this feature's `POST /api/claude-agents`. Recorded
  in a Redis set (`claude_bg:owned_sessions`) at start time. Gets full
  lifecycle control, a continuously relayed transcript from launch, and the
  full card treatment.
- **External** — present in `claude agents --json --all` but not in the
  owned set. Gets a roster row with an "external — not started here" badge,
  a one-shot best-effort log fetch, and **no** lifecycle control affordance
  — Stop/Respawn/Rm are not rendered, and the corresponding endpoints reject
  the action server-side (not just client-side) if the id isn't owned.

This mirrors the reasoning `docs/scope.md` already applies to `claude daemon
stop` ("affects every session the supervisor hosts, not just ones started
from the Control Room") and extends it to the plain roster list, which the
original scope left unscoped.

### 1.3 Fleet layout

The existing fleet view (`admin/static/app.js`, cell cards + design-session
cards) gains one additive section, "Claude background sessions," rendered
with the same card list markup and selection pattern `selectCell`/
`selectDesignSession` already use [admin/static/app.js:721-801]. No new
page, panel type, or visual language.

Each card shows: session id (truncated with full id on hover/title attr),
status (`running`/`stopped`/`completed`/`unknown`, taken from the roster
JSON), task/title (truncated), model, cwd, started/updated timestamps, and
an **Owned**/**External** badge per §1.2. Owned cards render Stop, Respawn,
Rm, and Detach controls in a control panel below the transcript pane,
mirroring the existing Interrupt/Detach panel for design sessions
[admin/static/app.js:1267-1304] minus Interrupt (§3.4 explains why no
interrupt-equivalent exists) plus Respawn and Rm. External cards render only
Detach and a "fetch latest log tail" button.

A separate, always-visible **Daemon** panel (not per-card) shows `claude
daemon status` output read-only, plus a single, separately gated "Stop
daemon" control (§3.5).

### 1.4 Session id → renderable identity

A background session's CLI-native id becomes the Control Room's `cell_id`
for that session, namespaced as `claude_bg_<id>`, the same trick
`scripts/supervise.py`'s `_cell_id_for` already uses for OpenCode sessions
[scripts/supervise.py:151-155]. Concretely:

- The id is validated against a strict allowlist pattern
  (`^[A-Za-z0-9_-]{1,128}$`) everywhere it crosses a trust boundary — reading
  it from `claude agents --json` output, accepting it as a URL path segment,
  and using it to build a Redis key or `LivePublisher` cell id. An id that
  fails the pattern is dropped from the roster with a logged warning rather
  than passed through; this is the same discipline `_slugify` applies to
  OpenCode titles/models before building a `cell_id`
  [scripts/supervise.py:146-155], made stricter here because a background
  session id (unlike a free-text title) is expected to already be a stable
  machine identifier and any deviation is more likely an attack or a parsing
  bug than legitimate data.
- `GET /api/events/claude_bg_<id>` is the existing, unmodified
  `/api/events/<cell_id>` endpoint [admin/server.py:450-490] — no new SSE
  route, no new frontend `EventSource` handling. The frontend's
  `selectClaudeAgent(id, attach)` (new, mirroring `selectDesignSession`
  [admin/static/app.js:758-801]) just points `state.selectedId` at
  `claude_bg_<id>` and calls the existing `connectSelectedStream()`.
- The roster entry the browser renders and the `cell_id` used for its
  transcript are thus always derivable from each other by one string
  operation (`claude_bg_` + id / strip the prefix), so no separate id-mapping
  table is needed anywhere in the stack.

## 2. Observe path + endpoint contract

### 2.1 Why polling moves out of the Flask process

`admin/server.py`'s own docstring already flags that `app.run(threaded=True)`
is a single-process dev server where every SSE client holds one request
thread for the life of a tab [admin/server.py:16-20]. Adding a module-level
thread that shells out to `claude agents --json --all` on an interval, plus
one polling thread per relayed session, stacks more long-lived
thread-plus-blocking-subprocess load onto that same process. §4.3 adopts the
challenge's alternative: give Claude-agent polling the same treatment
`scripts/supervise.py` already gets for OpenCode — a separate process that
owns every polling `subprocess` call and writes only to Redis, with
`admin/server.py` staying a Redis reader for the roster/transcript paths.
Mutating actions (start/stop/respawn/rm/daemon status/stop) are short,
bounded, one-shot commands and stay as synchronous subprocess calls inside
Flask request handlers — it is specifically continuous polling, not all
subprocess use, that doesn't belong in the request-serving process.

### 2.2 `admin/claude_agents_client.py`

A subprocess wrapper mirroring the shape of `OpenCodeClient`
[admin/opencode_client.py] but calling the `claude` CLI instead of an HTTP
API, following the same binary-resolution and subprocess pattern
`claude_adapter.py` already uses for headless runs
[src/instrument/claude_adapter.py:36-46, 291-299]:

```
list_agents(cwd: str, *, all: bool = True, timeout: float = 15.0) -> list[dict]
    # claude agents --json [--all] --cwd <cwd>
start_agent(task: str, *, cwd: str, model: str, advisor: str | None,
            skip_permissions: bool, timeout: float = 15.0) -> dict
    # claude --bg "<task>" --cwd <cwd> [--model <model>] [--advisor <advisor>]
    #   [--dangerously-skip-permissions]
get_logs(session_id: str, *, timeout: float = 10.0) -> str
    # claude logs <session_id>
stop_agent(session_id: str, *, timeout: float = 10.0) -> dict
    # claude stop <session_id>
respawn_agent(session_id: str, *, timeout: float = 10.0) -> dict
    # claude respawn <session_id>
rm_agent(session_id: str, *, timeout: float = 10.0) -> dict
    # claude rm <session_id>
daemon_status(*, timeout: float = 5.0) -> dict
    # claude daemon status  (exit code 1 => {"running": False})
daemon_stop(*, keep_workers: bool = True, timeout: float = 10.0) -> dict
    # claude daemon stop --any [--keep-workers]
```

Every call returns parsed JSON (or, for `get_logs`, raw text) on success and
raises a `ClaudeAgentsError` (mirroring `OpenCodeError`
[admin/opencode_client.py:28-36]) that distinguishes: binary not found,
non-zero exit (with captured stderr), malformed JSON, and timeout. No call
touches stdin — every subprocess is invoked with `stdin=DEVNULL` so a
misbehaving command can never block waiting for terminal input, which is the
concrete risk the scope already flags for `attach`/`agents` (§ "What is
explicitly NOT possible").

### 2.3 `scripts/claude_agents_supervisor.py`

A new, separate long-running process, structurally parallel to
`scripts/supervise.py` but simpler (no monitor-session flagging loop — that's
explicitly deferred, §1.1):

- **Roster refresh.** Every `CLAUDE_AGENTS_POLL_INTERVAL` seconds (default
  10), for each path in the configured workdir allowlist (§3.2), runs
  `list_agents(path, all=True)`. Unions the results by id (a session can only
  be under one cwd, so this is a simple dict merge), tags each entry
  `owned: <id in claude_bg:owned_sessions>`, and writes the resulting JSON
  array to a Redis key `claude_bg:roster` with a TTL of `2 *
  CLAUDE_AGENTS_POLL_INTERVAL` seconds. The TTL means a dead/stalled
  supervisor produces a visibly stale (then absent) roster rather than a
  silently frozen one.
- **Transcript relay — owned sessions only.** For every roster entry with
  `owned: true` and a non-terminal status (or a terminal status reached less
  than `CLAUDE_AGENTS_RELAY_GRACE_SECONDS`, default 120, ago — so the final
  lines of a just-finished session are still captured), the supervisor
  ensures one relay thread is running, mirroring `_relay_session`
  [scripts/supervise.py:158-176]: loop, call `get_logs(id)`, diff against a
  per-session cursor (line count) stored in Redis
  (`claude_bg:cursor:<id>`), publish only the new lines through
  `LivePublisher(f"claude_bg_{id}")` [src/instrument/live.py:47-105], sleep,
  repeat. The thread exits once the grace period after a terminal status
  elapses, and `LivePublisher.set_status("done")` is called so the frontend's
  existing "stream ended" handling applies unchanged.
- **No relay for external sessions.** Sessions present in the roster but not
  in `claude_bg:owned_sessions` are never polled for logs by the supervisor.
  This is both the resource bound the challenge asked for (§4.3) and a
  courtesy/safety boundary: the Control Room does not continuously shell out
  against a process an operator started elsewhere without it being told to.
  §2.4 covers how an operator can still see an external session's recent
  output on demand.
- **Bounded concurrency.** Relay threads are capped at
  `CLAUDE_AGENTS_MAX_RELAYS` (default 20); if the owned-session count exceeds
  that, the supervisor logs a warning and relays the most-recently-updated
  sessions first. This is a real, documented cap, not a silent truncation —
  the roster itself (unaffected by the cap) still lists every owned session
  regardless of relay status, and a card without an active relay shows
  "transcript relay paused (fleet at capacity)" rather than an empty pane
  that looks like nothing happened.

### 2.4 New read endpoints in `admin/server.py`

- `GET /api/claude-agents` — reads `claude_bg:roster` from Redis. If the key
  is absent or the JSON fails to parse, returns `{"error":
  "supervisor_unavailable", "agents": []}` with a 200 (a rendering concern,
  not a hard failure — the fleet section shows a "supervisor not running"
  state, the rest of the Control Room is unaffected). Never calls
  `list_agents` synchronously — this is a pure Redis read, matching how
  `api_matrix` reads its own cached hashes [admin/server.py:384-421].
- `GET /api/claude-agents/<id>/logs` — for **external** sessions only (owned
  sessions get their transcript via `/api/events/claude_bg_<id>` and don't
  need this route); validates `id` against the same `^[A-Za-z0-9_-]{1,128}$`
  pattern from §1.4, calls `claude_agents_client.get_logs(id)` synchronously
  with the client's bounded timeout, truncates the response to a fixed cap
  (e.g. 64 KB) matching the "bound... log-tail size" constraint, and returns
  it as plain text with a note that this is a one-shot, best-effort tail, not
  a live stream.
- `GET /api/claude-agents/daemon` — calls `daemon_status()` synchronously
  (bounded 5s timeout — a single fast status check, not a poll loop, so it
  stays inside Flask per §2.1's carve-out) and returns its JSON, or `{
  "running": false }` derived from exit code 1. Read-only; no control
  affordance is attached to this response, matching acceptance criterion 8.
- `GET /api/events/claude_bg_<id>` — no new code. This is the existing
  `/api/events/<cell_id>` route [admin/server.py:450-490], invoked with a
  `claude_bg_`-prefixed id. Retained-history replay, the `replay_complete`
  boundary, and heartbeat pings all behave exactly as they do for any other
  cell id, because the supervisor publishes through the same
  `LivePublisher`/Redis log+channel primitives every other relay uses
  [src/instrument/live.py:47-105].

### 2.5 Transcript fidelity — stated honestly

Owned-session transcripts are relayed continuously from shortly after launch
(§2.3), so in practice they are close to gapless — the same shape of
guarantee OpenCode sessions get from `scripts/supervise.py`'s
`relay_once`/`_relay_session` [scripts/supervise.py:178-193]. But the
underlying primitive is different in kind, not just in polling cadence:
`claude logs <id>` is documented as printing "recent output," a bounded
tail with no stated retention window, not a durable, gapless history API the
way OpenCode's `/api/session/{id}/event` SSE stream is
[admin/opencode_client.py:114-137]. Two consequences follow, and both are
stated in the UI and in acceptance criterion 4 rather than left implicit:

1. There is a small window — bounded by `CLAUDE_AGENTS_POLL_INTERVAL`,
   default 10s — between `claude --bg` returning a session id and the
   supervisor's first relay poll picking it up. Output produced in that
   window is not lost *if* `claude logs` still has it in its tail on the
   first poll (very likely at 10s for a session that just started), but this
   spec makes no stronger guarantee than that.
2. If `claude logs`'s own retention window is ever shorter than expected
   (e.g. under sustained high-volume output), lines could be dropped between
   two consecutive polls with no way for the Control Room to detect the gap,
   because `claude logs` exposes no cursor/offset primitive to detect
   under-run against — only content to diff against last-seen text. This is
   a limitation of the CLI contract, not an implementation gap; if a future
   CLI version adds an offset- or cursor-based tail command, this design
   should switch to it.

External-session transcripts (§2.4's one-shot `/logs` fetch) carry the same
"recent output, not full history" caveat, more visibly so, since there is no
continuous relay building a longer retained window at all.

## 3. Control path + door discipline

### 3.1 Mutation guard

Every new `POST` route reuses the loopback + same-origin + JSON +
`Idempotency-Key` guard `admin/server.py` already enforces for
`/api/design-sessions/*`
[admin/server.py:104-124, 127-178] — implemented as a small sibling helper,
`_claude_agent_mutation_body()`, with the same checks (loopback remote addr,
loopback `Host`, matching `Origin`, `application/json`, size cap, required
`Idempotency-Key`) rather than a parameterized shared function, to honor the
constraint that `/api/design-sessions*` behavior must not change
[docs/scope.md §4]. The existing `_idempotent_design_response` reservation
pattern (Redis `SET NX` + replay-on-retry) is reused the same way, under a
`claude-agent:<operation>:<id>` cache-key namespace so a retried Stop
request can't double-fire.

### 3.2 `POST /api/claude-agents` — start

Body: `{"workdir": "<allowlist key>", "task": "<string>", "model":
"<optional string>", "advisor": "<optional enum>"}`.

- `workdir` must be a key in a configured allowlist, `FINOPS_CLAUDE_AGENT_WORKDIRS`
  (same `PATH{os.pathsep}PATH...` env shape as
  `FINOPS_DESIGN_WORKDIRS` [admin/server.py:85-94], parsed by a small
  sibling function rather than by extending `_design_sessions()`, again to
  avoid touching the design-session code path). A raw filesystem path from
  the browser is never accepted, matching the same rule
  `DesignSessionManager` already applies to `workdir_key`
  [admin/design_sessions.py:284-288].
- `task` is bounded the same way `intent`/`prompt` are for design sessions
  (`MAX_DESIGN_PROMPT_CHARS`-equivalent cap).
- `model`, if present, is passed through `_resolve_claude_model`
  [src/instrument/claude_adapter.py:203-211] so a UI-selected model produces
  the identical `--model` argument the headless adapter would produce for
  the same id.
- `advisor`, if present, must be one of a fixed set (`fable`, `opus`,
  `sonnet`) or match a full model-id shape; it is passed straight through as
  `--advisor <value>` with no other logic, per the scope's constraint.
- The launch always includes `--dangerously-skip-permissions`, consistent
  with every other Claude CLI invocation this framework already makes
  headlessly [src/instrument/claude_adapter.py:291-299] — Control-Room-
  launched sessions are unattended by construction, the same as headless
  runs. Per the CLI reference, this flag persists across a `respawn` for the
  life of the session.
- On success, the client's `start_agent` result includes the new session id
  (parsed from `claude --bg`'s stdout, which the reference states prints the
  session id and management commands). The handler adds that id to
  `claude_bg:owned_sessions` (Redis `SADD`, no TTL — ownership is permanent
  for the id's lifetime; the set is only pruned when `rm` succeeds, §3.4)
  before returning `{"ok": true, "id": "<id>"}` to the browser. The next
  supervisor poll tick (≤ `CLAUDE_AGENTS_POLL_INTERVAL` seconds later) picks
  the session up as owned and starts its relay, per §2.3.

### 3.3 `POST /api/claude-agents/<id>/stop` and `/respawn`

Both require the id to be present in `claude_bg:owned_sessions`; if not,
the handler returns `403 {"error": "session not started from the Control
Room; manage it with the claude CLI directly"}` **before** shelling out —
this is the server-side half of the ownership boundary from §1.2, not just a
hidden button.

- **Stop** (`claude stop <id>`, `kill` is the CLI's alias for the same
  operation, so this feature exposes only `stop`) is a one-way door in the
  sense the scope's constraint means: it ends the running process
  immediately, and the UI must not let that happen from a stray click. The
  frontend requires `window.confirm` before sending the request, matching
  the existing Interrupt-confirmation pattern
  [admin/static/app.js:1284]. The response states plainly that the
  conversation is preserved and can be resumed with **Respawn** — stop is
  not "conversation deleted," it is "process ended, resumable."
- **Respawn** (`claude respawn <id>`) restarts a running-or-stopped session
  with its conversation intact. It is control, not destructive — the scope
  explicitly says it "does not require the same confirmation weight, though
  it should still be a deliberate click, not a default action." The UI
  implements this as a plain button (no `window.confirm`), not bound to any
  keyboard shortcut or auto-triggered flow, and the response/roster entry is
  checked to confirm the conversation id is unchanged before the card
  re-renders as running.

### 3.4 `POST /api/claude-agents/<id>/rm`

Requires ownership (§3.3's same check) and `window.confirm` (rm removes the
session from `claude agents`'s own list; while the reference states the
transcript stays on disk and remains reachable via `claude --resume`, that
resume path is outside this UI, so from the Control Room's perspective this
is effectively a one-way door on the *card*, even though the data isn't
deleted). On success, the handler also removes the id from
`claude_bg:owned_sessions` and its relay cursor key, and the response text
states explicitly: "removed from the Claude agents list; transcript remains
on disk and is reachable via `claude --resume <id>` outside the Control
Room."

### 3.5 `POST /api/claude-agents/daemon/stop`

The most severe control this feature exposes, because `claude daemon stop`
affects **every** session the local `claude daemon` hosts, including
external ones this UI has no relationship to and cannot even fully
enumerate confidently (an external session could be under a cwd outside the
configured allowlist and never appear in this feature's roster at all, yet
still be killed by this call). Accordingly:

- Body: `{"keep_workers": true}` by default; the operator must pass
  `{"keep_workers": false}` explicitly to also end every running session
  along with the supervisor. The handler rejects a missing `keep_workers`
  field rather than defaulting silently in the request-parsing layer, so the
  choice is always explicit in the logged request body, not just the UI
  copy.
- The frontend requires a `window.confirm` whose copy names the blast
  radius plainly, e.g.: *"Stop the Claude agents daemon? This affects every
  background session on this machine, not just ones started from the
  Control Room."* — and a second, visually distinct confirm/toggle before
  `keep_workers: false` can even be sent, so "end every session" cannot be
  reached by the same single click that stops the supervisor.
- This control lives in the daemon panel (§1.3), never inside a per-session
  card and never as part of any bulk/multi-select action.

### 3.6 Door-discipline summary

| Action | Reversible? | Confirmation | Scope |
|---|---|---|---|
| Start | n/a (creates) | none (deliberate form submit) | one session, owned workdir only |
| Stop/kill | Process ends now; conversation resumable via Respawn | `window.confirm` | one owned session |
| Respawn | Fully reversible (that's its purpose) | deliberate click, no confirm dialog | one owned session |
| Rm | Removed from list; transcript stays on disk, resumable only outside this UI | `window.confirm` | one owned session |
| Daemon stop (keep-workers) | Supervisor restarts and reconnects; sessions survive | `window.confirm`, blast-radius copy | every session on the host |
| Daemon stop (end sessions) | Every hosted session ends | `window.confirm` + separate explicit toggle | every session on the host |
| Detach | N/A — browser only | none needed | browser tab only, no process effect |

## 4. Challenge adjudication

Every point in `docs/challenge.md` is addressed below. §0 and §1 of the
challenge (CLI-fact verification and five points of agreement) are adopted
without modification and are folded into §1–§3 above without a separate
row, since there was nothing to resolve. The four disagreement points
(§2.1–§2.4) get individual verdicts.

| # | Challenge point | Verdict | Why |
|---|---|---|---|
| 4.1 | **2.1** Unscoped `--all` roster mixes external sessions in with no visual distinction, exposing Stop/Rm on sessions the operator didn't start | **Adopted, with a stronger mechanism than proposed.** Challenge suggested `--cwd`-scoped polling + an owned-set + "strongest confirmation copy (or disable outright)" for external sessions. This spec adopts `--cwd`-scoped polling and the owned-set (§1.2, §2.3), and picks the "disable outright" branch rather than stronger confirmation copy: external sessions get no Stop/Respawn/Rm affordance in the UI *and* the corresponding endpoints reject the action server-side if the id isn't owned (§3.3). Outright disabling is simpler to reason about and audit than a confirmation-copy variant that still has a code path to the destructive action; there's no legitimate Control-Room workflow that needs to stop a session it didn't start. |
| 4.2 | **2.2** Relaying only the selected session loses early history a session accumulates before anyone selects its card, unlike OpenCode's gapless relay | **Synthesized.** Full adoption of "relay every roster session continuously" was rejected because, combined with 4.1's ownership split, it would mean continuously polling external sessions the Control Room has no business polling. Instead: owned sessions (the only ones this feature can act on anyway) get continuous relay starting within one poll interval of launch (§2.3), which is close to OpenCode's guarantee for the sessions that matter to this UI; external sessions get on-demand one-shot log fetches only (§2.4), never continuous relay. §2.5 states explicitly, in both this document and acceptance criterion 4, that `claude logs` is a bounded-tail primitive, not the gapless equivalent OpenCode's SSE history gives — exactly the honesty check the challenge asked for, without over-building continuous relay for sessions this UI shouldn't be polling in the first place. |
| 4.3 | **2.3** Embedding polling threads + subprocess calls in the single-process Flask dev server risks the exact resource pressure its own docstring warns about | **Adopted.** `scripts/claude_agents_supervisor.py` (§2.1, §2.3) takes over all polling and relay subprocess calls, structurally parallel to `scripts/supervise.py`. `admin/server.py` only reads Redis for `GET /api/claude-agents` and the transcript route. Short, bounded, one-shot mutating commands (start/stop/respawn/rm/daemon status/daemon stop) stay as synchronous Flask-side subprocess calls, per the challenge's own carve-out — it is the *polling* that doesn't belong in the request-serving process, not all subprocess use. |
| 4.4 | **2.4** The Problem section motivates this feature by naming both the observe/control half and the AI-flagging half of `scripts/supervise.py`, but only the first is built, unstated | **Adopted.** §1.1 states explicitly that AI health-flagging for Claude background sessions is out of scope for this phase and is a real, buildable follow-on once this phase's `claude logs` relay exists to feed it (the challenge's own observation that `supervise_once`'s batching already knows how to summarize this shape of text). This is the "add one sentence to §3/§4" resolution the challenge offered as sufficient, applied here instead as an explicit phase-scope statement. |

## 5. Acceptance criteria

1. `admin/claude_agents_client.py` wraps `claude agents --json --all --cwd
   <path>`, `claude --bg`, `claude logs <id>`, `claude stop <id>`, `claude
   respawn <id>`, `claude rm <id>`, `claude daemon status`, and `claude
   daemon stop --any [--keep-workers]` as subprocess calls (stdin closed on
   every call), each returning parsed JSON/text or a distinguishable error
   for a missing binary, non-zero exit, malformed JSON, or timeout.
2. `scripts/claude_agents_supervisor.py` runs as a separate process; it is
   the only thing that polls `claude agents --json --all` or `claude logs`.
   It writes `claude_bg:roster` (TTL'd, tagged `owned`) and relays log lines
   for owned, non-terminal-or-recently-terminal sessions only, into
   `LivePublisher(f"claude_bg_{id}")`, capped at `CLAUDE_AGENTS_MAX_RELAYS`
   concurrent relay threads with the overflow surfaced in the UI, not
   silently dropped.
3. `GET /api/claude-agents` reads `claude_bg:roster` from Redis and never
   blocks on a live CLI call; a missing/stale key returns a
   `supervisor_unavailable` state instead of hanging or 500ing.
4. A background session's transcript is exposed through the existing `GET
   /api/events/<cell_id>` endpoint under `claude_bg_<id>`; the
   `replay_complete` boundary and retained-history behavior are unchanged
   for both pre-existing and new cell ids; both the UI copy and this spec
   state that Claude transcripts are best-effort/tail-bounded relays of a
   "recent output" primitive, not a gapless history API.
5. `POST /api/claude-agents` starts a session via `claude --bg`, accepts
   only a workdir key from `FINOPS_CLAUDE_AGENT_WORKDIRS` (never a raw
   path), resolves the model through `_resolve_claude_model`, accepts an
   optional fixed-set `advisor` value, enforces the loopback/JSON/
   Idempotency-Key guard, records the new id in `claude_bg:owned_sessions`,
   and returns the new session id.
6. `POST /api/claude-agents/<id>/stop`, `/respawn`, and `/rm` each: reject
   (403, before any subprocess call) an id absent from
   `claude_bg:owned_sessions`; enforce the mutation guard; and for stop/rm,
   require that the client went through an explicit confirmation step.
   Respawn's response/roster reflects an unchanged conversation id. Rm's
   response states plainly that the transcript remains on disk.
7. `GET /api/claude-agents/daemon` returns `claude daemon status` output (or
   a derived "supervisor not running" state from exit code 1) as a read-only
   observation with no control affordance attached.
8. `POST /api/claude-agents/daemon/stop` requires an explicit `keep_workers`
   boolean in the body (no silent default in request parsing), requires
   client-side confirmation naming the host-wide blast radius, and requires
   a second, distinct confirmation before `keep_workers: false` can be sent.
9. No endpoint, client method, or UI control sends input to, prompts, or
   otherwise steers a running background session; no subprocess call in
   `admin/claude_agents_client.py` or `scripts/claude_agents_supervisor.py`
   writes to a launched session's stdin. Grepping the new code for
   `delivery: steer` or a stdin-writing subprocess against an attached
   session finds nothing.
10. The Control Room fleet view gains a "Claude background sessions"
    section using the existing card/list visual language; selecting an
    owned card reuses the existing selection/`EventSource` hand-off and
    transcript pane; external cards render distinctly (badge, no lifecycle
    buttons) and use the one-shot `/logs` fetch instead of the SSE
    transcript pane.
11. Detach on any background-session card only closes the browser
    `EventSource`, exactly like existing cell/design-session Detach; it
    never calls stop, respawn, rm, or daemon stop.
12. All existing `/api/matrix`, `/api/status`, `/api/events/<cell_id>`,
    `/api/routing`, `/api/experiments`, and `/api/design-sessions*`
    behavior, Redis keys, and tests are unchanged by this feature.
13. Backend tests mock the `claude` subprocess (missing binary, non-zero
    exit, malformed JSON, timeout) and cover: list/start/stop/respawn/rm/
    daemon-status/daemon-stop, the mutation guard on every new `POST`
    route, the workdir-allowlist rejection path, the model/advisor
    pass-through, and — specifically — the ownership-rejection path (stop/
    respawn/rm against an id not in `claude_bg:owned_sessions` returns 403
    without invoking the subprocess wrapper).
14. Frontend tests or a documented manual check cover: roster rendering
    with the owned/external distinction, card selection reusing the shared
    transcript pane for owned sessions, the one-shot log fetch for external
    sessions, confirmation prompts for stop/rm/daemon-stop (including the
    second, distinct confirmation for `keep_workers: false`), and that no
    UI path offers a "send" or "steer" action for any background session.
15. The repository's `pytest` suite passes unchanged for all pre-existing
    tests after this feature is implemented (this feature is additive only
    — no existing test's behavior is expected to change).
