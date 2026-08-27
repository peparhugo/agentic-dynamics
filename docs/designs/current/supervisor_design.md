---
status: accepted
---
# Supervisor in the Control Room

## Invariant

The supervisor flags; the human reviews, decides, and acts. Assessment, flag persistence,
flag polling, and flag selection must never call `send_input` or `interrupt`. Only an
explicit operator action in the selected session pane may cross from observation into
control.

The feature extends the current Flask, Redis, SSE, and vanilla-JavaScript Control Room. It
does not add another terminal, event protocol, OpenCode server, or autonomous control loop.
Supervisor `status` and `why` are heuristic assessments, not execution lifecycle facts;
`stalled` and `off_track` therefore remain visually and semantically separate from fleet
states such as `running`, `failed`, and `done`.

## 1. Needs-Attention Surface

### Layout

Place a bounded **Supervisor / Needs Attention** rail at the top of the existing right-hand
column, above the selected-session controls. The fleet remains in its current column and the
existing terminal remains the only transcript surface.

```text
+---------------- command rail: spend / burn / tokens / running / connection ---------------+
| Fleet                              | Existing terminal             | NEEDS ATTENTION  2     |
| filters + pulsing cards            | selected session transcript   | off track  Session A   |
|                                    |                               | stalled    Session B   |
|                                    |                               | Supervisor flags.      |
|                                    |                               | You decide.             |
|                                    |                               +-------------------------+
|                                    |                               | Selected-session pane   |
|                                    |                               | review / steer / stop   |
+------------------------------------+-------------------------------+-------------------------+
| routing drawer                                                     | queue utilities         |
+--------------------------------------------------------------------------------------------+
```

The rail has three stable states:

| State | Presentation | Reason |
|---|---|---|
| No flags | One quiet row: `Supervisor / no sessions need attention` | Absence should be legible without taking space from the fleet. It must not claim that every session is healthy if the data source is degraded. |
| Flags | Count badge and a scrollable list capped to the right-column height | A bounded rail makes attention obvious without causing the fleet or terminal to jump as flags arrive. |
| Degraded | Last useful rows remain, with `Supervisor data delayed` and source detail | Losing Redis, the JSONL fallback, or mapping must not masquerade as a healthy empty state. |

Each row contains, in reading order:

- A text status badge: `OFF TRACK`, `STALLED`, or `ATTENTION` for an unfamiliar value.
- The session title, falling back to the shortened native `session_id`.
- The one-sentence `why` value, clamped visually to two lines but available in the row's
  accessible description and selected pane.
- A compact metadata line: model, flag age, and `last activity <age>`; when no activity
  timestamp is available, show `last activity unavailable` rather than inventing one.
- A `Review unavailable` marker when no exact Redis stream mapping exists. The row remains
  visible, but cannot silently open a guessed transcript.

The rail polls `GET /api/flags` every five seconds, matching the fleet snapshot cadence. A
separate flag SSE connection is unnecessary: the page already owns one global status SSE and
one selected-detail SSE, and flags do not require token-level latency. Polling updates rows by
stable `flag_id`, preserves focus and selection, and announces only a newly seen session or a
changed assessment. It does not repeatedly announce changing age labels.

The count badge uses the command-rail amber accent; `off_track` may use the existing danger
accent. Color is never the only signal. Motion is limited to the existing pulse vocabulary and
disabled by `prefers-reduced-motion`. At narrow widths, the rail becomes a collapsible section
after the command ticker and before the fleet. A nonzero count keeps its header visible, but
does not force the section open over the fleet.

The sentence **“Supervisor flags. You decide.”** is always visible in the rail footer and again
above action controls for a selected flag. This repetition is intentional: it makes the
human-in-the-loop boundary visible both when noticing and when acting.

## 2. Flag-to-Session Review Flow

Selecting a mapped flag performs the same selected-detail handoff as selecting a fleet or
design-session card:

1. Store a selection record containing `kind: "supervisor"`, `flag_id`, native `session_id`,
   and the resolved Redis `cell_id`.
2. Close the prior selected-detail `EventSource` and clear only its cell-local render state.
   The page-lifetime `/api/status` connection stays open.
3. Open the existing `GET /api/events/<cell_id>` source. Retained history, the
   `replay_complete` boundary, live following, pause/follow behavior, and occurrence-based
   replay-race deduplication remain unchanged.
4. Render the activity in the existing terminal and switch the existing session-control pane
   to `supervisor` mode. Do not create a terminal, transcript buffer, or EventSource per flag.
5. Keep the selected rail row visibly pressed. Refreshes may update its reason and timestamps,
   but must not detach the transcript or replace the frozen native action target.

The selected pane shows the title, full native `session_id`, model, assessment, full reason,
mapping source, and last activity. It labels the terminal as a review of observed activity,
not as the supervisor's proof that the assessment is correct.

An unmapped or ambiguous historical flag can still be selected to read its reason, but the
terminal stays on the prior selection and the pane says why review is unavailable. This is
safer than constructing `live_<model>_<title>` in the browser: those slugs are truncated and
can collide. Steer and Interrupt remain disabled until the server supplies one exact mapping.

## 3. Steer and Interrupt Doors

### Authorization boundary

Monitored-session controls are narrower than arbitrary OpenCode control. The backend accepts
an action only when all of the following are true:

- The native `session_id` exists in the currently retained supervisor flag set.
- It resolves to exactly one current or snapshotted `cell_id`.
- The browser-supplied `cell_id` matches that mapping, preventing a stale selection from acting
  after a remap.
- The request passes the Control Room's existing loopback Host, loopback remote address,
  same-origin, JSON-object, 64 KiB, and `Idempotency-Key` checks.

This boundary preserves ordinary fleet sessions as read-only and prevents the route from
becoming a general proxy to any guessed `ses_...` identifier. OpenCode connection details and
credentials remain server-side.

### Steer: deliberate, reversible door

The selected supervisor pane has a dedicated multiline **Steer this session** composer. It is
not the design-session `Send` queue and does not expose a delivery selector.

- The operator writes a nonblank prompt and presses the explicit `Steer` button. Plain Enter
  inserts a newline; it never submits. `Ctrl+Enter` may submit when the button is enabled.
- The button names the selected title or shortened ID and shows helper text: `Delivered as a
  steer to the active session; the supervisor will not send this.`
- Submission calls `OpenCodeClient.send_input(session_id, prompt, delivery="steer")` exactly.
  The server, not the browser, fixes `delivery` to `steer`.
- While admission is pending, the composer and button are disabled. A successful response is
  shown as `Steer admitted`; subsequent model output arrives independently through the existing
  terminal SSE.
- Failure leaves the prompt and transcript intact and shows an inline retryable or terminal
  error. Reusing the same idempotency key replays the admission result; editing the prompt
  requires a new key.

```http
POST /api/flags/ses_abc/steer
Idempotency-Key: <browser-generated UUID>
Content-Type: application/json

{"cell_id":"wf_retry_gpt_5_6_sol","prompt":"Re-run the failing test before changing code."}
```

Success is `200`:

```json
{"action":"steer","admitted":true,"session_id":"ses_abc"}
```

Steer has no confirmation modal because it is a reversible intervention, but separating it
from ordinary Send, requiring an explicit control, and naming the target makes it deliberate.

### Interrupt: one-way door

Interrupt is danger-styled and starts a two-step inline door; its first click sends no request.
The door freezes and displays the exact native target, explains that active generation and tool
execution will be stopped, and states that Detach is the non-destructive alternative. The
operator must type the exact phrase `INTERRUPT <session_id>` before **Interrupt permanently** is
enabled. Escape or Cancel closes the door and restores focus to the initiating button.

The typed phrase is also sent to and verified by the server. Client-side confirmation alone is
insufficient for a one-way operation.

```http
POST /api/flags/ses_abc/interrupt
Idempotency-Key: <browser-generated UUID>
Content-Type: application/json

{"cell_id":"wf_retry_gpt_5_6_sol","confirmation":"INTERRUPT ses_abc"}
```

The server rejects a missing or mismatched confirmation with `400` before constructing an
OpenCode request. A valid request calls `OpenCodeClient.interrupt(session_id)` exactly once.
Success, including OpenCode's valid empty response, is normalized to `200`:

```json
{"action":"interrupt","accepted":true,"session_id":"ses_abc"}
```

After acceptance, the terminal remains attached so the human can observe the resulting native
events. The UI disables repeated interruption while the request is pending, labels the action
as accepted afterward, and never interprets Detach, terminal Clear, rail selection, page unload,
or supervisor polling as an interrupt.

For either action, malformed input is `400`, an unretained or unmapped flag is `404`, a changed
mapping or reused idempotency key with a different body is `409`, trust-boundary failures retain
their existing `403`/`413`/`415` behavior, Redis control-state failure is `503`, and native
OpenCode errors preserve their useful upstream status with `code: "opencode_unavailable"`.

## 4. `GET /api/flags` Contract

`GET /api/flags?limit=<n>` is same-origin but read-only. `limit` defaults to 50 and is clamped
to 1 through 100. The response is newest-first and contains at most one row per native
`session_id`; when repeated assessments exist, the newest valid flag wins. The append-only
records remain unchanged in storage for auditability.

```json
{
  "generated_at": "2026-08-14T15:04:05Z",
  "source": "redis",
  "degraded": false,
  "warnings": [],
  "flags": [
    {
      "flag_id": "b8fc6d5b72c1a16e",
      "at": "2026-08-14T15:03:00Z",
      "session_id": "ses_abc",
      "title": "Fix retry accounting",
      "model": "gpt-5.6-sol",
      "status": "off_track",
      "why": "The session is editing pricing before reproducing the failed test.",
      "last_activity_at": "2026-08-14T15:02:51Z",
      "review": {
        "state": "mapped",
        "cell_id": "wf_retry_gpt_5_6_sol",
        "source": "publisher_index",
        "mapped_at": "2026-08-14T15:02:51Z"
      }
    }
  ]
}
```

The six existing flag fields, `at`, `session_id`, `title`, `model`, `status`, and `why`, remain
required and retain their meanings. `flag_id` is a stable truncated SHA-256 of those canonical
fields and is used only for rendering and deduplication. `last_activity_at` and `review` are
additive transport metadata; they do not affect the supervisor verdict. Ages are calculated in
the browser from server timestamps so polling does not generate false row changes.

The supervisor persists in this order:

1. Append the complete flag to `experiments/results/supervisor/flags.jsonl`.
2. `LPUSH supervisor_flags <canonical-json>` on framework Redis (port 6380/DB 1), then
   `LTRIM supervisor_flags 0 199`.
3. Print the existing stdout flag line.

Writing the append-only file first ensures a Redis outage cannot erase the assessment. Redis
is the bounded hot read path; the file is the durable recovery path. Neither write invokes a
session-control method, preserving flag-only semantics.

The endpoint first reads up to 200 Redis entries. If Redis is unavailable, the key is absent,
or the list is empty, it reads a bounded tail of the JSONL file and reports `source: "file"`.
Malformed records are skipped and counted in `warnings`; strings are returned as text and must
be rendered with `textContent`. A working fallback returns `200` with `degraded: true`. If
neither source is readable, return `503` with the same envelope, an empty `flags` array, and an
actionable warning. If both sources are healthy and empty, return `200`, `source: "none"`, and
`degraded: false`.

The file fallback reads from the end with a fixed byte/record bound rather than loading the
unbounded append-only file on every request. Source records are normalized defensively, but the
API does not recategorize the heuristic verdict. An unfamiliar nonempty status is exposed and
rendered as `ATTENTION`; a missing required identity causes that record to be skipped.

## 5. Native Session-to-Cell Mapping

### Authoritative index

Add the Redis hash `supervisor_session_cells`, keyed by native `session_id`. Each value is
canonical JSON:

```json
{
  "session_id": "ses_abc",
  "cell_id": "wf_retry_gpt_5_6_sol",
  "source": "publisher_index",
  "mapped_at": "2026-08-14T15:02:51Z",
  "last_activity_at": "2026-08-14T15:02:51Z"
}
```

The mapping is registered at the point where both identities are known:

- Any `LivePublisher(cell_id)` event containing a native identity registers that
  `session_id -> cell_id` pair. Identity extraction accepts the existing top-level
  `sessionID` and `part.sessionID` forms plus relayed `data.sessionID`. This captures workflow
  `wf_*`, story, and portal-managed streams without parsing titles.
- Before the supervisor starts a relay, it registers the relay's native session and exact
  `live_*` cell. Relay IDs retain the readable model/title prefix and append a short native-ID
  suffix, preventing two equal or truncated titles from sharing a terminal stream.
- A direct publisher mapping has precedence over a supervisor-relay mapping. A relay therefore
  supplies review for otherwise unbridged sessions but cannot replace the workflow or story
  stream that already owns the activity.

On each event, `last_activity_at` advances monotonically. A producer may replace its own stale
mapping, and a direct publisher may replace a relay mapping; a relay may not replace a direct
mapping. These precedence rules prevent thread timing from choosing which transcript opens.

At flag time, the supervisor copies the current mapping and last-activity timestamp into the
flag record. `GET /api/flags` prefers the current exact hash entry, then uses that immutable flag
snapshot if Redis was restarted. This snapshot is why file fallback remains reviewable rather
than merely readable.

The API exposes one of four review states:

| State | Meaning | UI behavior |
|---|---|---|
| `mapped` | One exact indexed cell exists | Review and actions enabled. |
| `snapshot` | The live index is absent but the flag contains an exact prior mapping | Review enabled, marked historical; actions require the backend to revalidate the snapshot. |
| `stale` | A mapping exists but has not observed activity within the configured active window | Review enabled; actions warn that OpenCode may reject an inactive session. |
| `unavailable` | No exact mapping exists or legacy data is ambiguous | Reason remains visible; terminal handoff and actions disabled. |

The browser never derives a cell from model/title, scans Redis keys, or substitutes the native
`session_id` into `/api/events/<cell_id>`. The server also does not choose among multiple
candidate streams by recency alone. Explicitly exposing `unavailable` is preferable to showing
the wrong transcript and steering the wrong native session.

## 6. Acceptance List

1. [ ] The existing Control Room still renders its command ticker, fleet, single terminal,
   selected-session controls, routing drawer, and queue utilities at desktop and 375 px widths.
2. [ ] A bounded, keyboard-reachable Needs Attention rail shows status, reason, model, flag age,
   last activity, count, empty, loading, fallback, and unavailable states without using color
   alone or forcing focus.
3. [ ] The rail and selected pane display `Supervisor flags. You decide.` and no supervisor code
   path calls `send_input(..., delivery="steer")` or `interrupt` while assessing, emitting,
   polling, mapping, relaying, or selecting flags.
4. [ ] `emit_flag` preserves the existing six verdict fields and append-only JSONL/stdout
   behavior, additionally writes canonical JSON to `supervisor_flags`, trims the hot list, and
   remains useful when framework Redis is unavailable.
5. [ ] `GET /api/flags` returns newest-first, stable, deduplicated session rows from Redis and
   uses bounded JSONL fallback with explicit source/degradation metadata after Redis loss or
   restart.
6. [ ] Malformed flag records, unfamiliar statuses, missing files, Redis errors, and a total
   source outage produce the documented visible states and status codes rather than a false
   all-clear or uncaught exception.
7. [ ] Native IDs observed by workflow, story, design, and supervisor relay publishers register
   exact Redis cell mappings; equal model/title pairs cannot collide, and direct publisher
   streams take precedence over relay streams.
8. [ ] Selecting a mapped flag closes the prior selected-detail source and opens its cell through
   the existing `/api/events/<cell_id>` terminal path. The page never owns more than one global
   and one selected-detail EventSource.
9. [ ] Unmapped, stale, and fallback-snapshot flags remain visible with explicit review state;
   neither browser nor server guesses a `live_*` ID from model/title.
10. [ ] A deliberate Steer submits a nonblank prompt to the exact native ID via
    `OpenCodeClient.send_input(..., delivery="steer")`, reports admission separately from model
    output, preserves failed input, and cannot be triggered by plain Enter.
11. [ ] Interrupt sends no request before the operator types `INTERRUPT <session_id>`; the server
    independently validates that exact phrase and the mapped cell before calling
    `OpenCodeClient.interrupt(session_id)` once.
12. [ ] Detach, Clear, flag selection, refresh, page unload, and supervisor polling never
    interrupt a session. After an accepted interrupt, the existing terminal remains attached.
13. [ ] New mutation routes enforce loopback/same-origin JSON, bounded bodies, current flagged
    ownership, exact mapping, and idempotency; ordinary fleet sessions remain read-only.
14. [ ] Flag title, reason, model, IDs, native events, and errors are inserted with `textContent`;
    focus survives polling, changed flags are announced without token-stream chatter, and
    reduced-motion preferences are honored.
15. [ ] Backend tests cover Redis ordering, JSONL fallback, deduplication, malformed records,
    mapping precedence, authorization, stale selections, idempotency, exact steer delivery,
    server-side interrupt confirmation, empty interrupt responses, and OpenCode failures using
    fake Redis and a mocked `OpenCodeClient`, never live port 4096.
16. [ ] Frontend tests cover rail states, one-terminal handoff, selection/focus preservation,
    deliberate Steer, the two-step Interrupt door, disabled actions for unmapped flags, safe
    text rendering, and mobile/reduced-motion structure.
17. [ ] All pre-existing admin route, SSE, replay, telemetry, design-session, frontend, and
     mutation-boundary tests pass unchanged, all new supervisor tests pass, and the complete
     repository `pytest` suite passes.

## 7. The execution-hardening rail (cap_runner_hardening2)

Three mechanisms close the execution gaps the terra post-mortem, the hardening review, and the
revamp3 checkpoint violation measured. All three share the flag-only discipline (this design's
hard rule 2): **they record and surface; they never steer.** None of them touches the steer /
interrupt doors in §3.

### 7.1 Server-level orphan sweep (design §Gap 1) — the supervisor-side monitor

The one verified 43.4-minute stall was an **orphaned delegation**: the authoring session (in the
opencode server) spawned a task (subagent); the parent session died mid-delegation; the subagent
**completed** but its result was never reaped. The runner-level watchdog cannot see this case —
it watches the runner's own agent process's transcript, and a dead parent is a process exit, not
a stall. The orphan lives in the **opencode server layer**, which only this sweep observes.

- **Observation surface:** the opencode server's session store (the SQLite `session`/`part`
  tables this Control Room already reads), read-only.
- **Detection (deterministic on transcript timestamps):** a task is an orphan when (a) the parent
  session has NO meaningful part strictly after the task's spawn time AND (b) the subagent
  session/process has terminated (a `step-finish` exists → completed, result produced; or silent
  past `crash_grace_s` with no step-finish → crashed, no result). `idle_minutes` counts from the
  subagent's termination.
- **Action (flag-only):** record the orphan (dated, flagged, queryable — durable
  `experiments/results/orphans/orphans.jsonl` + the bounded Redis `orphan_events` hot list + the
  canonical registry `source_type=orphan`), reap the orphaned subagent's process if still alive
  (SIGTERM of a pid whose cmdline references it — zombie reaping, not steering), and surface the
  record. No opencode client, no `send_input`/`interrupt`/`resume` (AST-guarded).
- **Cadence:** configurable (`ORPHAN_SWEEP_INTERVAL`, default 5 min); `--once` for one pass.
- **Implementation:** `agentic_dynamics/control/orphan_sweep.py` + `scripts/orphan_sweep.py`
  (CLI `agentic-dynamics supervise orphans`).

### 7.2 Relabel tree-identity gate (design §Gap 2) — the runner-side tree gate

revamp2's attempt A was reset away entirely, then attempt B (the "resume") committed a
**tree-identical copy** under compliant `[workflow]` messages (`git diff f6fc35edf 20eeb801b` is
empty). The merged commit enforcement checks the MESSAGE — the relabel's messages matched, so it
would pass. The tree gate closes that.

- **Discarded-trees ledger:** `experiments/results/workflows/<spec>/discarded_trees.jsonl`,
  keyed `(spec, branch, tree_hash, discarded_at)`. The reset/rollback path records via
  `record_discarded_tree` / the CLI `agentic-dynamics workflow discard-tree`
  (`scripts/record_discarded_tree.py`); idempotent.
- **Detection (post-phase, agent phases only):** the phase's committed tree (approvals-excluded —
  scaffolding never changes work identity) compared against the ledger; a match fails the phase
  `RELABEL` with the identical-tree proof (both hashes + the discarded record). Strict always —
  never canonicalized.
- **The operator-approval escape (the legit-reuse path):** an operator-signed
  `approvals/<spec>/<phase>_tree_reuse.md` committed BEFORE the phase (present at the pre-head),
  naming the tree + phase + a real operator signature + a date, authorizes the reuse.
- **Implementation:** `src/agentic_dynamics/runtime/workflow_runner.py` (`_enforce_tree_gate`).

### 7.3 Mechanical human checkpoint (design §Gap 3) — the designed stop

revamp3's p2 committed the delta preview AND the unsigned approval template, then the runner
moved straight into p3-p6 and recorded `ok: True` while the approval sat unsigned — "STOP for
the operator" was a sentence in a prompt, and prompt rules without mechanics get ignored.

- **The checkpoint phase kind:** a phase declaring `checkpoint: true` that completes successfully
  records the campaign state `awaiting_operator_approval` and EXITS CLEANLY — phase status
  `awaiting` (a designed stop, never an error; the operator's tools read "waiting", not
  "failed"), run result `awaiting: true` + `awaiting_phase` + `awaiting_reason`; exit code 0.
- **The approval contract:** `approvals/<spec>/<phase>_approval.md` must be committed at HEAD,
  authored AFTER the checkpoint commit (absent at the checkpoint commit AND the checkpoint
  commit an ancestor of HEAD), and carry a real operator signature (non-placeholder `operator:` /
  `SIGNED-BY-OPERATOR:` line + a real date). An unsigned template or a signed-before-the-work
  artifact never authorizes.
- **Resume gating:** `--resume` verifies every completed checkpoint phase's contract BEFORE any
  further phase runs; unsatisfied → the resume stops again with `awaiting_operator_approval`
  (`awaiting_reason="approval_refused"`) and runs nothing; valid → proceeds.
- **Implementation:** `src/agentic_dynamics/runtime/workflow_runner.py`
  (`_checkpoint_approval_valid` / the phase-loop stop / the resume gate); the measured violator
  `workflows/repository/cap_site_revamp3.yaml` declares `checkpoint: true` on its p2.
