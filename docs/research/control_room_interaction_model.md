---
status: accepted
---

# Control Room — interaction model: lifecycle, decision points, per-worker actions, alerts, drill-down

**Campaign:** `workflows/repository/control_room_ux_repair.yaml`, phase `u1_interaction_model`.
**Date:** 2026-09-11.
**Builds on:** `docs/research/control_room_ux_foundation.md` (`u0_ux_foundation`) — the operator
definition, jobs `J1–J11`, and principles `DP1–DP10`.
**Inputs (read in place):** `docs/research/control_room_direction.md` §2–§3 (run anatomy, immediacy),
`docs/research/control_room_ia.md` §4–§9 (regions, drill-down, alerts, provenance),
`src/agentic_dynamics/control/control_db.py` (the enforced state graphs and records),
`apps/control_room/routes/*` (the surviving endpoints), `apps/control_room/static/*` (the current
client), and `git show main:apps/control_room/static/*` (the old room — the parity reference).

**Claim discipline.** `[M]` measured in-repo; `[C]` computed; `[X]` external corpus source;
`[H]` heuristic; `[P]` local policy. `[skill:…]`/`[cat:…]` resolve to the repaired artifacts
`experiments/research/control_room/{skills,catalogs}.json`.

**The parity hard-rule.** This document is the **contract for the event-stream / actions-per-worker
surface the facelift dropped**. Nothing in the old room may be lost: every old control is either
**preserved**, **re-housed** into a named region/action here, or **explicitly replaced with a
reason**. §6 is the trace table; phase `u2_parity_inventory` enumerates every id against it, and
phase `u5_gate_semantic_parity` proves the result is wired and non-empty.

---

## 0. Scope and the interaction invariants

The model has five parts, in the order the operator meets them:

1. **The lifecycle** (§1) — the states a run and its attempts can be in, and which states permit
   which acts.
2. **The decision points** (§2) — the governed forks, the evidence each requires, and the safe
   action derived from the same state graph the database enforces.
3. **The per-worker/session actions** (§3) — every control, its endpoint, its authority, its
   confirmation door, and the **step-timing + event information it must show**.
4. **The alert model** (§4) — what becomes attention, how it is ranked and announced.
5. **The drill-down paths** (§5) — how a selection becomes evidence.

**Invariants every surface must hold** `[M]` (`control_room_audit.md` §9):

- **I1 — Two-layer reconciliation.** The `/api/glance` snapshot owns retained state; the SSE stream
  overlays transitions; replay is bounded by `replay_complete`; a no-op update writes nothing.
- **I2 — One selected event stream.** At most one per-cell `EventSource` is open; selecting a new
  object closes the prior source before opening the next.
- **I3 — Keyed, write-on-change lists.** Rows reconcile by stable key; `replaceChildren` only for
  unkeyed units; reordering must not steal focus or destroy scroll anchoring.
- **I4 — No HTML-string rendering.** All content is built with `element()`/`textContent`; ids and
  model output are untrusted text.
- **I5 — Mutation trust boundary + idempotency.** Every non-GET passes loopback/tailnet +
  same-origin + JSON + size-cap + `Idempotency-Key` (`services/mutations.py:40-120`), with the
  Redis `SET NX` reserve/replay; irreversible acts keep their typed two-step door.
- **I6 — Observe-only rails never steer.** Supervisor flags, lease-watchdog marks and projection
  watermarks are information; only a human (or the AIO within a lease) actuates.
- **I7 — The room never auto-acts.** A flag is never turned into an automatic steer, interrupt,
  route, retry, or budget change `[M]` (`control_room_direction.md:192-196`).

---

## 1. The run lifecycle

The lifecycle is **not re-derived by the UI**. It is the control database's enforced `RunState`
graph (`src/agentic_dynamics/control/control_db.py:140-249`), and the control packet derives
`active_runs`, `awaiting_approvals`, `promotable_runs`, `failed_runs` and `safe_actions` from the
same graph `[M]`. The UI renders the database's state; it never invents one.

### 1.1 Run states

| State | Meaning `[M]` (`control_db.py:149-182`) | Operator verb | Acts whose preconditions hold |
|---|---|---|---|
| `queued` | accepted, not yet running | **wait** | cancel |
| `running` | executing the workflow | **watch** | cancel; pause→approval when a checkpoint is hit |
| `awaiting_approval` | *a designed stop, never a failure* | **decide** | approve (→running or →verifying); cancel |
| `verifying` | post-hoc gates (tests, review, adversarial) running | **inspect** | cancel; a failed gate → `running` or `awaiting_approval` |
| `promotable` | gates passed; eligible for the permanence gate | **decide** | promote; cancel |
| `promoting` | `scripts/promote.py` squash-merging to main | **wait** | (no cancel — pre-merge only, but the act is in flight) |
| `merged` | on main; **not** yet published (projections may be stale) | **verify downstream** | (none; terminal-pending) |
| `projecting` | knowledge projectors consuming the run's events | **wait** | (none) |
| `published` | projections complete; public surface reflects it | **audit** | terminal |
| `failed` | terminal negative outcome | **triage/audit** | terminal |
| `cancelled` | terminal, before merge | **audit** | terminal |
| `quarantined` | terminal; output exists but is unaccounted-for | **audit** | terminal |

**The graph** (`control_db.py:193-243`) `[M]`:

```text
queued -> running
running           -> {awaiting_approval, verifying, promotable}
awaiting_approval -> {running, verifying}
verifying         -> {running, awaiting_approval, promotable}
promotable        -> promoting -> merged -> projecting -> published
{any non-terminal} -> failed | quarantined
{queued, running, awaiting_approval, verifying, promotable, promoting} -> cancelled
```

**Two distinctions the UI must never erase** `[M]` (`control_db.py:162-165`): `merged` is **not**
`published` (a run can be on main with stale projections), and `awaiting_approval` is **not**
`failed` (a designed stop). The lifecycle label may be a `[P]` simplification, but it **must map
exhaustively** to a `RunState`; `safe_actions` always come from the database graph.

### 1.2 Attempt states

A run contains attempts. An attempt is **one invocation of one step** — a retried step produces
two rows with the same `step_id` and a different `attempt_no`, which is how retry rate and
escalation become measurable (`control_db.py:252-289, 513-518`) `[M]`.

| Attempt state | Meaning | UI mark |
|---|---|---|
| `queued` | accepted, not started | pending |
| `running` | in flight | live |
| `ok` | produced its result | pass |
| `failed` | produced a negative result | fail |
| `awaiting` | completed and **correctly stopped** for a human (checkpoint) | decision |
| `skipped` | not executed by design (resume/`--only-phase`) — recorded, never omitted | skipped |
| `cancelled` | cancelled | cancelled |

Terminal attempt states are `{ok, failed, awaiting, skipped, cancelled}`; a second finish is
refused (`control_db.py:281-289`) `[M]`.

### 1.3 The records the lifecycle exposes

| Record | Fields | Source |
|---|---|---|
| `RunRecord` | `run_id`, `spec_name`, `workflow_revision_id`, `candidate_sha`, `state`, `model`, `started_at`, `ended_at`, `ledger_path`, `cost_usd`, `parent_run_id`, `family_id` | `control_db.py:459-486` `[M]` |
| `RunHeartbeat` | `run_id`, `last_seen_at`, `beat_count`, `actor` — the proof-of-life a zombie sweep reads | `control_db.py:494-509` `[M]` |
| `StepAttemptRecord` | `attempt_id`, `run_id`, `step_id`, `attempt_no`, `model`, `state`, `started_at`, `ended_at`, `tokens`, `cost_usd`, `exit_code`, `error` | `control_db.py:513-535` `[M]` |
| `GateResultRecord` | `gate_id`, `run_id`, `step_id`, `verdict` (`pass\|fail\|error\|waived`), `evidence`, `executor`, `candidate_sha`, `started_at`, `ended_at` | `control_db.py:543-565` `[M]` |
| `ApprovalRecord` | `approval_id`, `run_id`, `gate_id`, `candidate_sha`, `operator`, `decided_at`, `artifact_path` | `control_db.py:573-584` `[M]` |
| `PromotionRecord` | `base_sha`, `squash_sha`, the signed tree | `control_db.py:587+` `[M]` |

### 1.4 Lifecycle events that drive the UI

| Event | Producer | UI reaction |
|---|---|---|
| run-state transition | `ControlDB.transition_run` → `control_epoch` bump → `/api/glance` transition | re-render the roster row; possibly raise an `R1` item |
| step-attempt start/end | each runner phase → `step_attempts` row → epoch bump | update the row's phase/attempt mark; append a feed entry if selected |
| `step_start` / `step_finish` telemetry | runner Redis channel (`services/telemetry.py:80`) | live cost/token sample; never a fabricated timestamp |
| supervisor flag | flagged session | durable `R1` advisory item |
| projection watermark change | `kb_worker` / observer refresh | `R0` system/trust refresh; `R3b` detail |

---

## 2. Decision points

A **decision point** is a governed fork where the machine proposes and the controller (or the AIO
within a lease) disposes `[M]` (`agent_config/rules.md`; `control_room_direction.md:192-196`).
Every decision point renders as a **decision object**, never as a bare button.

### 2.1 The decision object

| Field | Meaning | Source |
|---|---|---|
| `kind` | `approve` / `promote` / `cancel` / `retire` / `raise-cap` (P0), or `retry` / `escalate` / `steer` / `interrupt` (P1, lease-bounded) | derived from state + packet |
| `authority` | the controller alone for P0; any actor within its lease for P1 | `agent_config/rules.md` `[M]` |
| `target` | the exact run / worktree / `candidate_sha` the act changes | `RunRecord`, `ApprovalRecord` `[M]` |
| `rationale` | why the machine proposes it (proposer + evidence authority) | packet `safe_actions`, gate results |
| `gate` | the gate id / promotion command the act routes through | `gate_results`, `promote.py` `[M]` |
| `reversibility` | reversible, or requires a typed confirmation | `[P]` per act (below) |
| `safe_action` | the database-derived next action, or `none` | `control_db.ALLOWED_TRANSITIONS` `[M]` |
| `receipt` | the decision record + recording coverage that closes the act | approvals / decision records `[M]` |

### 2.2 Decision catalogue

| Decision | Trigger state | Authority | Evidence required to decide | Safe action derivation | Reversibility | Receipt |
|---|---|---|---|---|---|---|
| **approve** | `awaiting_approval` | controller (P0) | run identity + `candidate_sha`; the gate that stopped; the measured evidence at that gate; elapsed/waiting age; fee/lease effect | `ALLOWED_TRANSITIONS[awaiting_approval].intersect(packet.safe_actions)`; `approve` eligible | reversible until promotion (resume vs verify) | `ApprovalRecord` (+ decision record) |
| **promote** | `promotable` | controller (P0) | full gate set `pass` on the **same** `candidate_sha`; independent verification; base/squash target; blast radius on `main` | `ALLOWED_TRANSITIONS[promotable]` → `promoting`; `promote.py` | **irreversible** (typed door) | `PromotionRecord` + receipt |
| **cancel** | any pre-merge state | controller (P0) or orchestrator | reason; current state; whether work is in flight (in-flight cancel is destructive) | `ALLOWED_TRANSITIONS[state] ∋ cancelled` | irreversible for the run; a revert is a **new** run | decision record |
| **retire / rename URL** | published surface | controller (P0) | the published URL, its dependents, replacement plan | policy `[P]` | **irreversible / externally visible** | decision record |
| **raise-cap** | a threshold reached | controller (P0) | current cap, spend to date, requested new cap, why | policy `[P]` (admission) | reversible (lower again) | decision record |
| **retry** | `failed` attempt / flaky gate | AIO within lease (P1) | failure class (retry-worthy?); `retry_reason`; remaining budget | ledger retry policy | reversible | attempt row (`attempt_no+1`) |
| **escalate** | model/attempt under-performing | AIO within lease (P1) | measured shortfall; `confidence`; escalation target | routing/escalation policy | reversible | attempt row (`escalation_from/to`) |
| **steer** | live flagged session | AIO within lease (P1) | current flag; target `cell_id`; the prompt | `POST /api/flags/<session_id>/steer` | reversible (a further steer) | actuation record |
| **interrupt** | live flagged session | AIO within lease (P1) | the flag; why not detach; typed confirmation | `POST /api/flags/<session_id>/interrupt` | **irreversible** for the generation | actuation record |

### 2.3 The safe-action preview contract

Every mutation previews before execution `[M]` (`control_room_direction.md:267-273`). The preview
shows, at minimum: **target and current selection**; repository / worktree / model / provider /
cell context; requested scope and blast radius; current run state and control epoch/revision; the
gate id + `candidate_sha`; proposer and evidence authority; admission/budget effect;
reversibility; the database-derived safe action; and the **receipt** that will close it. Typed
confirmation stays for irreversible acts and **never substitutes** for current-state validation
(the server re-validates target/ownership at use time — `flags.py:53-67`, `claude_agents.py:135-140`).

---

## 3. Actions available per worker / session

This is the core of the restored surface. Each row names the target class, the action, the
**surviving endpoint**, its authority, its confirmation door, and what it must show. All mutation
routes exist on the current server (`apps/control_room/routes/*`) and in the old client
(`git show main:apps/control_room/static/app.js`); the current client wires none of them.

### 3.1 The action catalogue

#### A. OpenCode experiment cell / session (the run's agent)

| Action | Endpoint | Authority | Door | Must show |
|---|---|---|---|---|
| **Attach / Watch** | *client-only*: open `GET /api/events/<cell_id>` (`telemetry.py:213-252`) | P1 (read) | none | cell id, status, stream state, OpenCode session id; replay→live boundary; follow/pause/clear |
| **Detach** | *client-only*: close the `EventSource` (I2) | P1 | none | "detached, retained history still inspectable" |
| **Copy session id** | *client-only* | P1 | none | the observed session id, copyable |
| **Steer** | `POST /api/flags/<session_id>/steer` (`flags.py:26-60`) body `{cell_id, prompt}` | P1 | none (additive) | the flag reason; the target cell; that the supervisor will **not** send it |
| **Interrupt** | `POST /api/flags/<session_id>/interrupt` (`flags.py:64-88`) body `{cell_id, confirmation:"INTERRUPT <session_id>"}` | P1 | **typed two-step door** | one-way warning; Detach as the non-destructive alternative; exact phrase |

#### B. Background `claude` session

| Action | Endpoint | Authority | Door | Must show |
|---|---|---|---|---|
| **Start** | `POST /api/claude-agents` (`claude_agents.py:76-125`) body `{workdir, task, model?, advisor?}` | P1 | approval of `workdir` server-side | approved workdir; task; model; advisor (`fable\|opus\|sonnet\|<model-id>`) |
| **Status / roster** | `GET /api/claude-agents` (`claude_agents.py:32-49`) | read | — | id, status, **ownership** (`OWNED`/`EXTERNAL`), model, workdir, task |
| **Stop** | `POST /api/claude-agents/<id>/stop` | P1 (owned only) | none (conversation preserved) | "process ends; Respawn resumes it" |
| **Respawn** | `POST /api/claude-agents/<id>/respawn` | P1 (owned only) | none | conversation preserved; same id |
| **Rm** | `POST /api/claude-agents/<id>/rm` | P1 (owned only) | danger-styled; transcript remains on disk | the `claude --resume <id>` fallback |
| **Steer** | `POST /api/claude-agents/<id>/steer` body `{prompt, model?, advisor?}` | P1 (owned only) | none | **stop+resume semantics**; the **new session id supersedes** the old (`claude_agents.py:193-256`) |
| **Logs** | `GET /api/claude-agents/<id>/logs`; external "Fetch latest log tail" | read | — | bounded tail; external sessions are read-only |
| **Daemon** | `GET /api/claude-agents/daemon`; `POST /api/claude-agents/daemon/stop` body `{keep_workers}` | P1 | stop is fleet-wide and severe | daemon status/PID; "most severe control this feature exposes" |

#### C. Design session (workflow/experiment authoring)

| Action | Endpoint | Authority | Door | Must show |
|---|---|---|---|---|
| **Create** | `POST /api/design-sessions` body `{intent, kind, model?, workdir?}` | P1 | — | kind, model, workdir, intent |
| **List / open** | `GET /api/design-sessions`; `GET /api/design-sessions/<id>/spec` | read | — | draft, revision, validation badge/errors, matrix preview |
| **Input (send/queue)** | `POST /api/design-sessions/<id>/input` body `{prompt, delivery:"queue\|steer"}` | P1 | — | delivery mode; the conversation it joins |
| **Interrupt** | `POST /api/design-sessions/<id>/interrupt` | P1 | danger-styled | draft preserved; interrupt is not delete |
| **Save spec** | `POST /api/design-sessions/<id>/save` body `{filename, overwrite}` | P1 | conflict returns 409 | basename; overwrite is explicit |
| **Run workflow** | `POST /api/design-sessions/<id>/run` body `{goal, model, workdir, timeout, commit, thinking_budget_tokens, output_token_limit, backend?}` | P1 | launch-parameter confirmation; spends budget | workdir is approved; commit flag; timeout; **spend warning** |

#### D. Queue controls

| Action | Endpoint | Authority | Door | Must show |
|---|---|---|---|---|
| **Enqueue** | `POST /api/experiments` body `{action:"enqueue"}` (`telemetry.py:358-388`) | P1 | confirmation (spawns real inference) | budget/admission; "most expensive mutation" |
| **Clear** | `POST /api/experiments` body `{action:"clear"}` | P1 | **typed two-step door** | queue depth removed |
| **Reinterleave** | `POST /api/queue/reinterleave` (`telemetry.py:391-418`) | P1 | none (future picks only) | `before`/`after` provider summary; count |

#### E. Supervisor flag controls

| Action | Endpoint | Authority | Door | Must show |
|---|---|---|---|---|
| **List** | `GET /api/flags?limit=50` | read | — | `at`, `session_id`, `title`, `model`, `status`, `why`, `last_activity_at`, review mapping, `lease` when present (`supervisor.py:19, 46-51`) |
| **Steer / Interrupt** | as A above | P1 | steer none; interrupt typed door | the flag reason + the mapped `cell_id` re-validated at use time |

#### F. Docs-health remediation

| Action | Endpoint | Authority | Door | Must show |
|---|---|---|---|---|
| **Inspect** | `GET /api/docs-health` | read | — | four axes, scanned time, proposal id, headline |
| **Approve / dispatch** | `POST /api/docs-health/approve` body `{proposal_id, by, reason, dispatch}` (`docs_health.py:97-160`) | controller (P0) | signature is an explicit act | the exact `proposal_id` the panel rendered; signer; reason; dispatch flag |

### 3.2 The per-worker event stream contract

The event stream is what makes a worker inspectable rather than merely visible. It is **two
streams from the old room**, both still registered server-side `[M]`:

- **`GET /api/status`** (`telemetry.py:187-210`) — a page-lifetime SSE of **all** cell status
  transitions, 15 s heartbeat. Drives row-status updates and transition-only announcements.
- **`GET /api/events/<cell_id>`** (`telemetry.py:213-252`) — replay the retained log in order,
  emit `event: replay_complete`, then stream live frames, 15 s heartbeat. **One at a time** (I2).

Each frame must be rendered with the event vocabulary the client already parses
(`control-room-core.js:79-206`): `step_start`, `step_finish`, `reasoning`, `operator`, `text`,
`tool_use`/`tool`. The replay boundary is what lets the client exclude history from the live
burn/token window. **A worker's event stream must show:** the ordered events with an honest
timestamp (producer-supplied, or an explicit "received now" marker — never a fabricated time);
tool calls with their state; and the live cost/token sample attached to each `step_finish`.

### 3.3 The step-timing contract

**This is the surface the facelift dropped and neither room had fully** `[M]`
(`control_room_ux_foundation.md` P3; r0 A4). It is required, not optional. Step timing is a join
of three authoritative sources:

| Timing field | Source | Meaning |
|---|---|---|
| `started_at`, `ended_at` | `StepAttemptRecord` (`control_db.py:527-528`) | wall-clock span of one step invocation → duration |
| `attempt_no` | `StepAttemptRecord` | retries of the same `step_id`; `attempt_no > 1` is a retry |
| `queue_wait_ms` | ledger `AttemptRecord` | time queued before lease/start (scheduling pressure) |
| `service_time_ms` | ledger `AttemptRecord` | time actually executing (model + tools) |
| `first_token_at` | ledger `AttemptRecord` | time-to-first-token (latency, not just duration) |
| `tokens_in` / `tokens_out` / `tokens_reasoning` / `tokens_answer` / `tokens_explanation` | ledger `AttemptRecord` (`experiment_spec.py:382-386`) | where the output budget went (the answer/explanation split) |
| `cost_usd`, `tokens` | `StepAttemptRecord` | per-attempt cost/tokens |
| `exit_code`, `error` | `StepAttemptRecord` | process outcome; `None` is "not observed", never `0` |
| `test_executed_success`, `evaluator_independent`, `confidence` | ledger `AttemptRecord` | verification and uncertainty |
| `step_start` / `step_finish` samples | events (`services/telemetry.py:67-128`) | live per-step cost/token observation |

**Where it appears:**

- **Per attempt** — inside `R4`'s evidence ladder (`#evidence-ladder`), each attempt row shows
  step id, attempt number, model, state, duration, queue wait, service time, first-token, tokens
  (answer vs explanation), cost + provenance, exit code, verification mark.
- **Workforce aggregate** — a bounded **step-timing view** in `R3b` (or a dedicated workforce
  panel) shows p50/p95 queue wait, p50/p95 service time, first-token latency, retry rate, and
  tokens-per-attempt across the live fleet, by model — enough to answer "where is the fleet
  spending time and money?" without a per-card chart (DP7; avoids r0 M6).

**Honesty rules:** an unobserved timing is rendered `unknown`, never `0 ms`; a retained-window
aggregate is labelled with its window; the aggregate is not announced (only transitions are —
§4.3).

### 3.4 Action-state rules (shared)

- A control is **enabled only when the target's authoritative state permits the act** (the same
  `ALLOWED_TRANSITIONS` / ownership checks the server re-validates).
- An action in flight **disables duplicates** and is idempotent by `Idempotency-Key` (I5).
- **Irreversible** actions (`interrupt`, `rm`, `queue clear`, `promote`, `retire`, `daemon-stop`)
  carry the typed two-step door; `detach`/`stop`/`respawn` are the non-destructive alternatives.
- **Every action emits a receipt** — the response is shown inline (`aria-live="polite"`) and, where
  consequential, recorded as an actuation/decision record (I6/I7; `flags.py:52-59`).
- **No automatic action.** A flag, a threshold, or a watermark may raise an `R1` item with a
  suggested safe action; it never executes one.

---

## 4. Alert model

Attention is **stateful work**, not a decorative strip `[M]` (`control_room_direction.md:253-265`).
It is the `R1` region's reason to exist, and it is what makes `J1` (glance) and `J2` (triage)
completable without scanning the fleet.

### 4.1 Alert catalogue

| Need | Detection → `R1` item | Item opens | Item severity |
|---|---|---|---|
| `ON-A1` run failed/timed out | lifecycle transition to `failed` → **failure** | `R4` run evidence ladder | high |
| `ON-A2` worker/projection unhealthy | dependency state (packet `unhealthy_workers`, projection watermark) → **impact**, listing affected runs | `R3b` detail / affected runs | high |
| `ON-A3` spend/quota threshold crossed | window/lease threshold (usage snapshot + admission) → **money-risk** with window/headroom/reset | `R3a` / run cost rung | high (money) |
| `ON-A4` controller decision pending | packet `awaiting_approvals` / `promotable_runs` → **decision** | `R4` decision object + safe action | high (blocking) |
| `ON-A5` supervisor flag raised/changed | flag event → **advisory** row (persistent Flags view retained) | `R4` flag detail | medium |
| `ON-A6` room data stale/disconnected | freshness floor crossed → **degraded** state in `R0` + local stale marker | `R3b` dependency | high (trust) |

### 4.2 Attention item schema and lifecycle

Each item carries `[M]`/`[P]` (`control_room_direction.md:255-260`; `control_room_ia.md:397-407`):

- a **stable key** (so re-polls update rather than duplicate);
- a **typed source object** (`run`, `flag`, `projection`, `worker`, `lease`, `docs-proposal`);
- **severity + actionability**, ranked severity × actionability;
- **first-seen / last-seen**;
- **scope**;
- **authority class** (`measured` / `computed` / `heuristic` / `policy` / `unknown`);
- an **evidence link** and, when one exists, a **database-derived safe action**;
- a **lifecycle**: `new | active | snoozed | resolved | stale` (`[P]` state machine).

**Capacity is reserved:** the `R1` region keeps fixed slots so a fresh failure cannot be buried by
a governance decision (`control_room_ia.md` §4; Move 8) `[M]`.

### 4.3 Announcement policy

- **One polite live region**, `aria-live="polite"` (`#announcer`), announces **transitions only**,
  deduplicated `[M]` (`control_room_direction.md:258-260`; current `app.js:785-828`).
- **Ordinary changing metrics** (spend, burn, running, tokens) are labelled and readable but
  **never announced** — this is the fix for the old room's rail that was `aria-hidden` (r0 M9).
- Announcements are generated from a **control-epoch change** or a typed transition, not from a
  no-op poll (the keyed write-on-change contract, I3).
- The alert model is **in-room only**: impossible to miss **while the room is foregrounded**, with
  durable unseen history. No browser notification, sound, or webhook is promised `[P]`
  (`control_room_ia.md:371-374`).

### 4.4 What is never an alert

A KPI readout, a chart, a per-card sparkline, or a routine metric is not an alert. If nothing needs
a human, `R1` says so explicitly (`all clear` / `none pending`) rather than rendering an empty box
(DP1/DP6).

---

## 5. Drill-down paths

Drill-down is **one selection from the roster or inbox into `R4`**; the roster and summaries
remain visible (`control_room_ia.md:339-345`) `[M]`. `R4` is hidden at rest and is not a layout
region (`index.html:180-197`).

### 5.1 Paths

| Need | Path |
|---|---|
| `ON-D1` one run, step by step live | select `R2` row → `R4` evidence ladder → attempt → transcript/tool events (one live stream, follow/pause) |
| `ON-D2` why flagged / safe action | select `R1` item or `R2` row → `R4` decision/flag object → safe-action preview |
| `ON-D3` design draft/validation | Sessions object → `R4` design-session inspector |
| `ON-D4` canonical explanation | `R4` → registry record link → canonical-lineage view (distinct from the runtime trace) |
| `ON-D5` route + cost/quality | `R4` → routing recommendation inputs + evidence, beside the run context |
| `ON-D6` cost by step/model/cell | `R4` cost/lease provenance rung; aggregate in the Money lens |
| `ON-D7` background `claude` session | Sessions object → `R4` Claude-session inspector with owned actions |

Design sessions, background `claude` sessions, supervisor flags, routing, registry, recording and
queue controls **all keep explicit entry paths and global-search classes** `[P]`
(`control_room_ia.md:357-358`). This is precisely the set the facelift dropped (u0 §3 P4).

### 5.2 Selection persistence contract

Selection survives live reconciliation and compatible lens changes `[M]`
(`control_room_direction.md:244-251`): scope, filters, sort, time range, scroll, transcript query
and follow/pause persist; incompatible scope changes confirm; a disappeared/stale object keeps its
identity; closing restores focus to the origin; **exactly one event stream is open** (I2). The
roster stays visible while the inspector is open — the fleet is never lost to a modal.

### 5.3 Mobile

Mobile is **triage and inspection mode** `[P]` (`control_room_direction.md:275-281`): the first
view is unresolved attention and recently-changed runs; one selected object and its evidence
ladder are preserved; target context and safe actions precede secondary charts; fleet comparison is
an explicit filtered view, not a compressed desktop mosaic — and the reference widths
(390×844 / 1024×768 / 1440×900) are gate-enforced (`control_room_ia.md` §3, §10).

---

## 6. Parity trace — every old surface maps to a contract element

The old room is `main`. This table is the binding of the facelift's dropped ids to the interaction
model above; `u2_parity_inventory` expands it to every panel/control/feed, and no row may end as a
silent drop.

| Old surface (id) | Disposition | Contract element here |
|---|---|---|
| `#watch-button`, `#control-cell`, `#control-status`, `#control-stream`, `#control-session`, `#copy-session` | **re-house** | §3.1.A attach/detach/copy; `R4` address band |
| `#supervisor-control-panel`, `#supervisor-steer*`, `#supervisor-interrupt*` | **re-house** | §3.1.A/E + §2.2 steer/interrupt + §2.3 preview |
| `#transcript-panel`, `#transcript-feed`, `#follow-button`, `#pause-button`, `#clear-button`, `#jump-live` | **re-house** | §3.2 event stream; `R4` bounded feed (`[data-attempt-feed][data-feed-follow]`) |
| `#cell-control-panel` | **re-house** | `R4` identity/lifecycle facts; §3.3 step timings |
| `#claude-agents`, `#claude-agent-grid`, `#claude-agent-daemon-panel` | **re-house** | §3.1.B status/roster/daemon; Sessions object → `R4` |
| `#claude-agent-start-form`, `#claude-agent-stop`, `#claude-agent-respawn`, `#claude-agent-rm`, `#claude-agent-steer`, `#claude-agent-detach*`, `#claude-agent-fetch-logs` | **re-house** | §3.1.B owned/external controls |
| `#design-start-form`, `#design-composer`, `#send-design-input`, `#steer-design-input`, `#interrupt-design`, `#detach-design`, `#save-spec-form`, `#run-workflow-form` | **re-house** | §3.1.C design controls + §2.3 preview |
| `#recent-design-list`, `#recent-designs-title` | **re-house** | Sessions object type (§5.1 `ON-D3`) |
| `#queue-title`, `#enqueue-button`, `#clear-queue-button`, `#queue-clear-*` | **re-house** | §3.1.D queue controls |
| `#board-fleet`, `#fleet-grid`, `#matrix-cells`, `#fleet-counts`, `#cell-search`, `#density-toggle`, `#live-now-list` | **re-house** | `R2` roster + `R0`/`R3` + a full-fleet lens (u0 §3 P6) |
| `#board-status`, `#reported-spend`, `#burn-trace`, `#burn-rate` | **re-house** | `R3a` + Money lens; live burn is not a rest-carried number (u0 §3 P4) |
| `#board-flags`, `#supervisor-flag-list`, `#supervisor-rail` | **re-house** | `R1` advisory + persistent Flags view (`ON-A5`) |
| `#board-routing`, `#routing-drawer`, `#routing-content` | **replace-with-reason** | routing inputs beside the run (`ON-D5`); a peer board is the rejected generic idiom (`control_room_direction.md` §4.3) |
| `#system-sheet`, `#registry-drawer`, `#registry-*` | **replace-with-reason** | Registry becomes a canonical-lineage **evidence destination** (`ON-D4`), not an overflow drawer (r0 M4) |
| `#usage-content`, `#usage-refresh` | **re-house** | `R3a` five values + `R3b`/Money lens; `GET /api/subscription-usage` |
| `#docs-health*`, `#docs-health-approve-form` | **re-house** | `R1` decision + `ON-G5`; `POST /api/docs-health/approve` (§3.1.F) |
| `#projections` (route only, never rendered) | **preserve-and-render** | `R0` system/trust + `R3b`; closes r0 M2 |
| `/api/recording-audit`, `/api/recording-sweep/run` (routes only) | **preserve-and-render** | audit surface (`J7`) + decision-receipt coverage; closes r0 M12 |
| `/api/queue/reinterleave` (route only) | **preserve-and-render** | §3.1.D |
| `#overall-state`, `#utc-clock`, rail mirrors `[data-mirror]` | **re-house** | `R0` named system dimensions; mirrors become labels, not live regions (r0 M9) |
| `#board-sessions`, `#sessions-title` | **re-house** | Sessions object type + search (§5.1) |

**Explicit replacement reasons** (the only non-preserve dispositions):

- **Routing board → run-context lens.** A peer board fragments one run decision across
  destinations; routing inputs belong beside the run that will use them
  (`control_room_direction.md` §4.3, Move 5) `[P]`.
- **Registry overflow → evidence destination.** Canonical lineage is what *justifies* a decision;
  burying it behind a gear makes the evidence hardest to reach when it is most needed (r0 M4)
  `[P]`.

---

## 7. Gate hooks for `u5_gate_semantic_parity`

The implementation must expose stable, testable handles so the semantic + feature-parity gate can
prove the model without reading prose:

- **Lifecycle:** every `R2` row carries `[data-run-id]` and a lifecycle state that maps to a
  `RunState`; the decision token carries a value in
  `observe|inspect|approve|promote|cancel|retire|none`.
- **Decision points:** `R1` items carry `[data-attention-class]` in
  `decision|risk|advisory|impact|money-risk` and, where actionable, a `[data-action]` + epoch.
- **Actions:** each actionable control carries a stable `[data-action]` and target id; an action
  fires its endpoint; a control with no legal action is absent or disabled, never a live button.
- **Event stream:** the selected dock exposes `[data-attempt-feed]` with ≥1 non-empty frame under
  a live fixture and an explicit empty-state otherwise; `[data-feed-follow]` toggles.
- **Step timings:** the workforce view exposes `[data-timing="queue_wait|service_time|first_token|duration|retry"]`
  with each value `[data-state="measured|unknown"]` — an unknown is never a fabricated `0`.
- **Alerts:** a transition raises exactly one keyed `R1` item; a no-op poll announces nothing; the
  single polite live region is the only `aria-live` transition channel.
- **Parity:** every §6 row resolves to a present element or an explicit documented empty-state;
  the gate enumerates `experiments/research/control_room/parity_inventory.json` and reports any id
  with no element and no reason.

---

## 8. Reproduce

```bash
# The enforced lifecycle and records
sed -n '140,300p' src/agentic_dynamics/control/control_db.py

# The surviving per-worker action endpoints
grep -rnE 'app\.(get|post)\(' apps/control_room/routes/flags.py \
  apps/control_room/routes/claude_agents.py apps/control_room/routes/design_sessions.py \
  apps/control_room/routes/telemetry.py apps/control_room/routes/docs_health.py

# The event/step-timing vocabulary the client parses
grep -nE 'step_start|step_finish|tool_use|reasoning|operator|timestamp' \
  apps/control_room/static/control-room-core.js

# The old-room controls this contract restores (the parity reference)
git show main:apps/control_room/static/app.js | grep -nE 'fetch\(|EventSource\('
git show main:apps/control_room/static/index.html | grep -oE 'id="[^"]+"' | sort -u
```

**Doc lifecycle:** this file carries `status: accepted` (`tests/test_doc_lifecycle.py:66-120`).

*End of phase `u1_interaction_model`. This is the contract for the event-stream / actions-per-worker
surface the facelift dropped; `u2_parity_inventory` enumerates every old surface against §6, and
`u4_implement` must realize it while `u5_gate_semantic_parity` proves it.*
