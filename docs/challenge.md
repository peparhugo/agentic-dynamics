---
status: accepted
---
# Challenge: Claude Code Background Sessions Scope

Reviewed against `docs/scope.md`, the code it cites
(`admin/opencode_client.py`, `scripts/supervise.py`, `admin/server.py`,
`src/instrument/claude_adapter.py`, `admin/design_sessions.py`,
`admin/static/app.js`), and the live Claude Code CLI reference
(`https://code.claude.com/docs/en/cli-reference`), fetched directly for this
review rather than taken on faith.

## 0. CLI facts: verified accurate

Section 2's quoted commands and flags (`--bg`/`--background`, `claude
agents`/`--json`/`--all`/`--cwd`, `claude attach`, `claude logs`, `claude
daemon status`, `claude daemon stop --any [--keep-workers]`, `claude
stop`/`kill`, `claude respawn [--all]`, `claude rm`, `--advisor <model>`) were
re-fetched from the live reference for this review and match the scope
document essentially verbatim, including the "requires an interactive
terminal" caveat on `claude agents` and the "recent output" wording on
`claude logs`. The document's central claim — that the CLI is a documented,
scriptable contract for everything except send-input/steer — holds up. This
matters because the whole feature stands or falls on that contract being
right, and it is.

## 1. Where I agree

- **No invented steer/interrupt.** The CLI has no equivalent to OpenCode's
  `delivery: queue|steer` [admin/opencode_client.py:94-102], and the scope
  correctly refuses to fake one via subprocess stdin. This also matches the
  repo's own existing philosophy: `scripts/supervise.py`'s monitor is
  explicitly "flags only. A human decides the intervention"
  [scripts/supervise.py:9,48]. Not inventing a control the vendor doesn't
  document is the right call, not just a cautious one.
- **`claude logs` over `claude attach`/`claude agents` for headless
  polling.** Both of the latter are documented as needing a real TTY; `logs`
  is a plain stdout dump. Driving only the scriptable subset via subprocess
  is consistent with how `claude_adapter.py` already drives the CLI
  [src/instrument/claude_adapter.py:291-299].
- **Reusing `GET /api/events/<cell_id>` under a `claude_bg_<id>` cell
  namespace** instead of a new SSE shape is the same trick
  `scripts/supervise.py` already uses for OpenCode (`_cell_id_for`,
  [scripts/supervise.py:151-155]) and it's the right one here too — zero new
  frontend stream types.
- **Daemon-stop defaulting to `--keep-workers`, gated separately from
  routine controls.** `daemon stop` is documented as affecting every session
  the supervisor hosts, not just Control-Room-started ones, and scoping it as
  a rare, explicitly-confirmed action with a safe default is proportionate to
  that blast radius.
- **Reusing `_resolve_claude_model` and the workdir-allowlist shape**
  [src/instrument/claude_adapter.py:203-211; admin/server.py:81-101] instead
  of building parallel model-resolution or path-validation logic is the
  correct anti-duplication call, and it's consistent with how
  `admin/design_sessions.py` already restricts `workdir_key` to an approved
  map [admin/design_sessions.py:284-288].
- **Reusing the loopback + JSON + Idempotency-Key mutation guard**
  [admin/server.py:104-124] for every new `POST` route rather than writing a
  second guard is correct; it's exactly what `/api/design-sessions/*` already
  does for every mutating endpoint.

## 2. Where I disagree

### 2.1 The roster is host-wide, not Control-Room-owned — this is a safety gap, not a detail

`claude agents --json --all` lists **every** background session on the
machine, including ones an operator started by hand in a terminal, unrelated
to the Control Room. The scope's acceptance criteria (#2) only says the
roster comes from that call; nothing scopes it to sessions the Control Room
itself launched. That means the fleet UI will show Stop/Respawn/Rm buttons —
one-way-door actions per the scope's own constraint — on sessions the
operator didn't start and may not know about, with no visual distinction.
Contrast this with the daemon-stop action, where the scope *does* explicitly
call out "affects every session the supervisor hosts, not just ones started
from the Control Room" (§3 Rationale, criterion 9) — the same reasoning
should apply to the plain roster list, and it doesn't.

**Alternative:** query `claude agents --cwd <path> --json --all` once per
configured workdir-allowlist entry (the CLI supports exactly this scoping
flag) instead of one unscoped `--all` call, and additionally track
Control-Room-launched session ids in a small Redis set written at `--bg`
start time. Render sessions found only via the `--cwd` scan but absent from
that set as "external — not started here," and require the strongest
confirmation copy (or disable Stop/Rm outright) for them. This costs one
Redis set and a few more `--cwd`-scoped calls; it does not touch the
`--all`-vs-scoped decision the daemon-stop rationale already implicitly
endorses.

### 2.2 Relaying only the *selected* session loses history the OpenCode side never loses

The decision routes log-diffing through "the currently selected/attached
session only" (§3 Decision). Compare `scripts/supervise.py`, which the scope
repeatedly cites as the pattern to mirror: `relay_once` maintains one relay
thread **per active session**, continuously, regardless of what's selected in
the UI [scripts/supervise.py:178-193]. That works for OpenCode because the
native server holds durable, gapless history independent of the Control
Room's polling — `iter_events` can always backfill full history on attach
[admin/opencode_client.py:114-137]. `claude logs <id>` has no such backing
store from the Control Room's point of view: the reference describes it as
"recent output," i.e. a bounded tail, not a durable full-history API. Combine
those two facts and a session that runs for a while before anyone selects its
card can have its early output permanently unrecoverable — there is no
retained window for a cell nobody was polling, and by the time it's selected
`claude logs` may no longer have the early lines to backfill from.

**Alternative:** mirror `relay_once`'s actual behavior, not just its naming
convention — start a `claude logs`-diffing thread for every session returned
by the roster poll (bounded by the same `--cwd` scoping from 2.1), not just
the selected one, so retained history accumulates in Redis the same way it
does for OpenCode regardless of UI attention. If the resource cost of N
concurrent polling threads is the actual reason for the "selected only"
choice, say so explicitly and put a number on it (max concurrent relays,
poll interval) rather than leaving "selected only" implicit — either way,
acceptance criterion 4 should state plainly that Claude transcripts are
best-effort/tail-bounded, not the gapless equivalent OpenCode gets, so nobody
mistakes the "reuses the same SSE endpoint" plumbing for "reuses the same
fidelity guarantee."

### 2.3 Embedding subprocess polling in the Flask dev server risks the resource the docstring already warns about

`admin/server.py`'s own module docstring flags that `app.run(threaded=True)`
is "Flask's built-in single-process development server" and that every SSE
client "holds one request thread... for the life of the tab, so there is no
connection cap" [admin/server.py:16-20]. The scope's decision to add a
"module-level thread" that runs `claude agents --json --all` on an interval
plus (per 2.2, ideally N) `claude logs`-polling relay threads, each shelling
out via `subprocess`, adds more long-lived thread + blocking-subprocess
pressure to that same single process — on top of the SSE thread-per-tab load
the docstring already flags as needing a production gunicorn front-end for
multi-operator use. The scope explicitly rejects "a new always-on service"
(§3 Decision) without weighing this against the alternative the codebase
already has for exactly this shape of problem.

**Alternative:** give the poller/relay the same separate-process treatment
`scripts/supervise.py` already has for OpenCode, e.g.
`scripts/claude_agents_supervisor.py`: it owns all `subprocess` calls to
`claude`, writes the roster and relayed log lines straight to Redis, and
`admin/server.py` only ever reads Redis for `GET /api/claude-agents*` — the
same read-only relationship `api_matrix`/`api_events` already have to
`scripts/supervise.py`'s output. `POST` actions (start/stop/respawn/rm/daemon
stop) can stay synchronous subprocess calls inside Flask, since those are
short, bounded, one-shot commands, not long-lived polling loops — it's
specifically the *polling* that doesn't belong in the request-serving
process, not all subprocess use.

### 2.4 The Problem framing promises more than the Approach delivers, silently

The Problem section justifies this feature by pointing at "the Control
Room['s]... native supervisor surface for OpenCode," and names both halves
of it: `admin/opencode_client.py` (observe/control) *and*
`scripts/supervise.py`, described as flagging "stalled/off-track work for
human review" [docs/scope.md:5-8]. The Chosen Integration Approach then only
builds the `opencode_client.py`-equivalent half (list/observe/lifecycle
control) — there is no proposed equivalent to the flash-model monitor that
reads session activity and emits healthy/stalled/off_track flags. That may
well be the right phasing choice (get observe+control shipped first), but
the scope never says so — it cites the flagging behavior as motivation and
then quietly doesn't build it, which reads as an oversight rather than a
decision if a reader isn't cross-checking `scripts/supervise.py` themselves.
It's a real, buildable follow-on: `claude logs <id>` output is exactly the
kind of text `supervise_once`'s batching already knows how to summarize
[scripts/supervise.py:211-240], so nothing here is CLI-blocked.

**Alternative:** either trim the Problem section's framing to the half
actually being built (observe + lifecycle control), or add one sentence to
§3/§4 stating that AI-flagging of background-session health is explicitly
out of scope for this phase and left as a follow-up once `claude logs`
polling exists to feed it. Either fixes the mismatch; leaving it unstated
does not.

## 3. Recommendation

Proceed to the spec phase with the CLI contract and the observe/control
shape as scoped — but resolve 2.1 (roster ownership scoping) and 2.4
(explicit phasing of the flagging gap) in the spec itself before writing
acceptance criteria, since both change what "done" means; 2.2 and 2.3 are
implementation-shape calls that can be settled during spec or left as
explicit, documented trade-offs if the team prefers the simpler
selected-only/embedded-poller path.
