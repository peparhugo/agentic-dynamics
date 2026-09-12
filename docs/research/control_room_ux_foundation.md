---
status: accepted
---

# Control Room — UX foundation: operator, jobs-to-be-done, pain points, and design principles

**Campaign:** `workflows/repository/control_room_ux_repair.yaml`, phase `u0_ux_foundation`.
**Date:** 2026-09-11.
**Predecessors:** the research campaign `control_room_research` (r0 audit → r7 brief) and its
repair passes (`control_room_research_repair`, `control_room_research_repair2`). This phase does
**not** re-open the research; it converts the already-derived, already-repaired corpus into the
three things the UX-repair wave must be graded against: **who the operator is**, **what jobs the
room must do**, **where the current room fails**, and **the principles the implementation must
enact**.

**Inputs (all read in place, none re-fetched):**

| Input | Role |
|---|---|
| `docs/research/control_room_audit.md` | Measured r0 baseline: panels, feeds, cadence, M1–M14, A1–A12 |
| `docs/research/control_room_questions.md` | Operator needs `ON-*`, research questions `RQ-*`, §5 anti-subjectivity criteria |
| `docs/research/control_room_ia.md` | The canonical one-resting-screen glance contract (`R0`–`R3c`, `ON-G1..G7`, pixel budgets) |
| `docs/research/control_room_direction.md` | The eight distinctive moves, removed-generic list, truth contract |
| `experiments/research/control_room/catalogs.json` | The repaired decision catalogs (`[cat:...]`) |
| `experiments/research/control_room/skills.json` | The repaired decision skills (`[skill:...]`) |
| `docs/reviews/control_room_taxonomy_repair.md`, `docs/reviews/control_room_semantic_crosswalk.md` | The evidence repairs: which support counts were inflated and demoted to `[P]` |
| `apps/control_room/static/*` + `apps/control_room/routes/*` (this branch) | The **current room** (the facelift) |
| `git show main:apps/control_room/static/*` + `:routes/*` | The **old room** — the parity reference |

**Claim discipline.** Every factual statement is tagged with the campaign's evidence classes:

- `[M]` **measured** in this repository — a code fact, a control-plane contract, or a p0-repaired
  corpus count.
- `[C]` **computed** — arithmetic over `[M]` inputs (e.g. an id diff).
- `[X]` **external observation** from a named corpus source.
- `[H]` **heuristic** — a reasoned judgement on `[M]`/`[X]`.
- `[P]` **policy** — a local design decision, explicitly *not* external consensus. The repair
  passes moved every inflated or unsupported claim here; principles that rest on `[P]` say so.

**Citation legend.** `[skill:<id>]` and `[cat:<catalog-id>/<item-id>]` resolve to
`experiments/research/control_room/skills.json` / `catalogs.json` (the **repaired** artifacts:
`phase: q0_semantic_crosswalk`, `min_support: 3`). `[M#/A#]` is an r0 misplaced/absent finding;
`[ON-*]` an r1 operator need; `[IA#]`/`[D#]`/`[E#]` the repair-campaign adversary findings.

**The parity hard-rule carried into this wave.** No existing panel, control, or data feed may be
silently dropped. Every item in the old room is **preserve**, **re-house**, or
**replace-with-reason**, and phase `u2_parity_inventory` must enumerate all of them. This document
supplies the *why* and the *principles*; the inventory supplies the *what*.

---

## 1. OPERATOR — who runs this room, and what they must never miss

### 1.1 Two operators, one surface

The room is not a public dashboard. It is the shared instrument of a **human decision-maker** and
the **delegated agent that acts on the human's behalf**. The repository names both, and their
authority is not advisory (`agent_config/rules.md`, AUTHORITY).

**The controller — the human, P0.** The controller alone may: merge a worktree branch into `main`
(the permanence gate — every `feature/*` / `wt_*` branch is an *ephemeral proposal* until signed),
deploy the website, approve a gated run, retire or rename a published URL, and raise a spend cap.
The controller is *“a Bayesian who applies frequentist”* `[M]` (`docs/designs/proposed/self_knowledge_layer.md:39`).
The controller's decisions are the posterior update the machine cannot make for itself.

**The AIO — the AIO Control Agent, the delegated agent, P1.** The AIO is the session with full
information that acts on the controller's behalf — historically called the “master OpenCode
session,” briefly “Logos Control Agent (LCA)” `[M]`. All I/O converges here; all execution radiates
from here. The AIO **reads the ONE control packet every turn, acts only on the `run_id`s /
`candidate_sha`s returned there, routes every permanence verb through the verified commands
(`promote.py`, `publish release`), and never bypasses the gates** `[M]` (`agent_config/rules.md`).

The AIO's continuity across sessions — its own posterior — is the **self-knowledge layer** `[M]`
(`self_knowledge_layer.md:18-19`): *“Every AIO session today starts as a fresh prior: compaction
erases the previous session's posterior.”* The room is the operator's external memory and its
control surface at once.

**Why this matters to the UI.** The two operators have different authorities and different
question sets. The controller needs the **decision board** (what awaits a signature, what is
irreversible, what evidence justifies it). The AIO needs the **operational board** (what is
running, what is failing, what it may act on within its lease). A room that optimizes for one
starves the other; the canonical glance contract (`control_room_ia.md` §4) answers both by making
the *decision object* and the *run object* co-resident.

### 1.2 Their context

- **Scale and shape.** Many concurrent CLI AI coding-agent sessions (`[ON-G2]`; `[M]`
  `control_room_direction.md:54`). The room is local-only, loopback/tailnet, single-operator by
  construction (`services/mutations.py:26-37`) `[M]`.
- **Cadence.** Continuous, not session-based: a 1 s rail tick over 5–60 s polls plus SSE
  transitions (`control_room_audit.md` §3.1–3.2) `[M]`. The operator returns to the screen between
  other work; the screen must be true when they look, not only when they click.
- **The decision boundary.** *The machine proposes; the controller disposes.* Two tiers, neither
  advisory (`agent_config/rules.md`). The room must therefore make proposals **legible, addressable,
  and safely executable** without ever auto-executing them.
- **The recording requirement.** *A session that does not write its close record has not closed*
  `[M]` (`agent_config/rules.md`; `self_knowledge_layer.md:133-146`). A consequential act is not
  finished until it is recorded. The room is where the operator confirms that recording happened.
- **Time zone and provenance.** The room runs UTC (`#utc-clock` `[M]`); every consequential number
  carries a source and a freshness bound (`control_room_direction.md` §8).

### 1.3 What they must never miss

Ranked by the cost of a miss (money, dropped or wrongly-permanent work, false confidence,
irreversibility). Each maps to an `ON-*` need and an authoritative field.

| # | Must-never-miss | Why it is catastrophic to miss | Need | Authoritative source |
|---|---|---|---|---|
| N1 | **A controller decision is pending** (approval / promotion) | The machine is blocked; a wrong or late signature merges unverified work or stalls the fleet | `ON-G5`, `ON-A4` | control packet `awaiting_approvals`, `promotable_runs` `[M]` |
| N2 | **A run failed or timed out just now** | The next retry/escalation decision is time-sensitive; a miss burns budget on a dead path | `ON-G3`, `ON-A1` | packet `failed_runs`, `RunState` graph `[M]` |
| N3 | **A spend/quota/lease threshold is crossed** | The autonomous half can keep spending; an unknown cost drawn as zero hides the overrun | `ON-G4`, `ON-A3` | subscription-usage + lease registry `[M]` |
| N4 | **A worker or knowledge projection is unhealthy/stale** | Green-but-stale is the exact false-authority failure the control plane exists to remove | `ON-G6`, `ON-A2` | packet `unhealthy_workers`, projection watermarks `[M]` |
| N5 | **A supervisor flag was raised or changed** | The observe-only rail never steers; if the human does not read it, nobody acts | `ON-A5` | `GET /api/flags` `[M]` |
| N6 | **An action was (or was not) recorded** | An unrecorded consequential act is a reconstruction, not a record | `ON-D4` | recording audit, registry lineage `[M]` |
| N7 | **What the fleet looks like** (by model/condition/provider) | Misreading capacity causes bad routing and bad campaign planning | `ON-G7` | packet `active_runs`/`failed_runs` `[M]` |

**What must never be missed, structurally:** N1–N4 are *capacity-reserved* — the canonical IA
reserves fixed regions and refuses to let a governance decision bury a fresh failure
(`control_room_ia.md` §4, R1; Move 8) `[M]`.

---

## 2. JOBS-TO-BE-DONE

Each job is concrete, operator-phrased, and carries: **trigger/cadence**, **frequency**, **cost of
failure**, **evidence it needs**, and **current-room status** (measured in §3). “Cost” combines
money, dropped/wrongly-permanent work, and false confidence, as in the r0 ranking method.

### J1 — Glance: *is the system healthy, what is running, is anything wrong?*

- **Trigger/cadence:** continuous; answered on every return to the screen, no interaction.
- **Frequency:** every work session (many times per shift).
- **Cost of failure:** HIGH. A missed failure/decision compounds while the operator is away; a
  green-but-stale board manufactures false confidence (`[M]` r0 M2).
- **Evidence needed:** connection + control plane + workers + projections each named with state and
  worst age; running/queued/failed/live counts; a reserved risk row; a reserved decision row; five
  money values; explicit stale/partial/unknown counts (`control_room_ia.md` §4) `[M]`.
- **Current status:** the facelift **satisfies** this (canonical `R0`–`R3c`, `ON-G1..G7`), with two
  caveats: the fleet is a **bounded sample** and `ON-G7` composition is capped (`glance.py:391-438`)
  — the old room's full grid is gone (§3).

### J2 — Triage a stalled or failed run to a decision

- **Trigger/cadence:** on a failure/risk signal; event-driven.
- **Frequency:** per incident (tens per campaign).
- **Cost of failure:** HIGH. Wrong triage = money burned on a doomed retry (“retry worthiness”) or
  an abandoned run that was one step from success; the queue can deadlock behind a stalled cell.
- **Evidence needed:** the run's identity, lifecycle state, phase progress, attempt chain, last
  tool/command, the measured `test_runner` result vs the model's narration, cost/lease state, and
  the *safe* next action with its blast radius (`control_room_direction.md` §2; Move 2/3) `[M]`.
- **Current status:** **partial**. The resting `R2` row + `R4` evidence ladder carry identity,
  lifecycle, evidence classes and eligibility; the room has **no action that fires an endpoint**
  (§3 P1/P2), so triage terminates in “inspect”, not “act”.

### J3 — Decide approve / cancel (and promote / retire)

- **Trigger/cadence:** when the machine proposes; blocked-waiting.
- **Frequency:** per gated run (the permanence gate).
- **Cost of failure:** CRITICAL and often **irreversible** — merging a `feature/*` proposal into
  `main`, approving a gated run, or raising a cap. These are the controller's P0 acts
  (`agent_config/rules.md`) `[M]`.
- **Evidence needed:** target, kind, control epoch, authority, eligibility, scope/blast radius,
  budget effect, reversibility, and the receipt (`control_room_direction.md` §2.5; Move 3) `[M]`.
- **Current status:** **partial**. `ON-G5` shows “pending/none” and an eligibility token
  (`glance.py:213-260`); there is **no approve/promote/cancel door wired to the mutation routes**
  that still exist server-side (§3 P1).

### J4 — Inspect evidence and step timings

- **Trigger/cadence:** on demand, per selected run/attempt.
- **Frequency:** every consequential decision (J2/J3) and every review.
- **Cost of failure:** HIGH (false confidence). Accepting the agent's narration as truth is the
  single failure the evidence-class design exists to prevent (`control_room_direction.md` §1/§4.1
  Move 4) `[M]`.
- **Evidence needed:** the attempt-scoped causal ladder — narration / measured ledger facts /
  independent `test_runner` result / commit (SOURCE) / cost / decision / receipt — and the **step
  timing** facts (queue wait, service time, first token, start/end) that explain *where* time and
  cost went (`ledger_ingestion.py:180-181`; `experiment_spec.py` `AttemptRecord` `[M]`).
- **Current status:** **partial/at-risk**. The ladder exists (`#selection-dock`,
  `#evidence-ladder`, `[data-attempt-feed]`); there is **no workforce step-timing surface** and no
  per-step cost/token detail equivalent to the old transcript (§3 P3).

### J5 — Watch spend

- **Trigger/cadence:** continuous; per return to screen.
- **Frequency:** continuously; decisions at thresholds.
- **Cost of failure:** HIGH (money). Quota exhaustion halts the fleet; an unshown lease reservation
  means headroom was already spent. `[M]` r0 M1/A5.
- **Evidence needed:** spend, burn, provider quota, wallet, **reserved leases**, hard-cap headroom,
  settlement status, and provenance (`measured|estimated|unknown`) — with the rule *an unknown cost
  is never shown as `$0.00`* (`control_room_direction.md` Move 6; `core.cost_provenance`) `[M]`.
- **Current status:** **partial**. `R3a` gives the five values with explicit `unknown`
  (`glance.py:342-388`) — a genuine improvement over the old buried System page — but the room has
  no spend trend and no live burn trace (§3 P4).

### J6 — Intervene per worker / session

- **Trigger/cadence:** on a runaway, zombie, or misbehaving session; event-driven.
- **Frequency:** per incident.
- **Cost of failure:** HIGH. A runaway worker keeps spending and holds a concurrency lease; an
  unattended background `claude --bg` session leaks resources.
- **Evidence needed:** worker/session identity, ownership (owned vs external), status, current
  command, lease, logs; actions start/stop/detach/steer/status — each previewing target, scope,
  reversibility and recording (`control_room_audit.md` §2.3; `control_room_interaction_model` to
  follow) `[M]`.
- **Current status:** **absent from the UI**. The old room exposed `#supervisor-control-panel`,
  `#supervisor-steer`, `#supervisor-interrupt`, `#watch-button`, `#claude-agent-*`, and
  `#cell-control-panel`; the facelift keeps only read-only eligibility tokens. The routes survive
  (`POST /api/flags/<id>/steer|interrupt`; `POST /api/claude-agents/<id>/stop|respawn|rm|steer`).

### J7 — Audit what happened (and confirm it was recorded)

- **Trigger/cadence:** at session close, at review, or after any consequential act.
- **Frequency:** per session / per campaign close.
- **Cost of failure:** MEDIUM-HIGH (process + amnesia). Without it the next session re-litigates
  settled questions and cannot reproduce a result.
- **Evidence needed:** who did what, when, with what authority; the decision record; the registry
  lineage (what superseded what, `causes` links); recording coverage (`control_room_audit.md` M4,
  M12; `self_knowledge_layer.md` §records) `[M]`.
- **Current status:** **absent**. `GET /api/registry` remains an overflow in the old room and has
  **no surface at all** in the facelift; `GET /api/recording-audit` and
  `POST /api/recording-sweep/run` had no consumer in either room (`[M]` r0 M4/M12).

### J8 — Start / enqueue work

- **Trigger/cadence:** per campaign or fill.
- **Frequency:** per campaign phase.
- **Cost of failure:** MEDIUM-HIGH. Unbudgeted work must never enter the queue (admission is
  fail-closed), and a mis-filled matrix wastes a whole run.
- **Evidence needed:** what will be enqueued, its budget/lease, the queue depth, and the clear/enqueue
  confirmation doors (`control_room_audit.md` §2.4) `[M]`.
- **Current status:** **absent**. Old `#enqueue-button`, `#clear-queue-button`,
  `#confirm-queue-clear`; route `POST /api/experiments` survives; no UI consumer now.

### J9 — Route / choose the model for a task

- **Trigger/cadence:** on demand, before a run or campaign.
- **Frequency:** per task type / per campaign.
- **Cost of failure:** MEDIUM (cost/quality misallocation) — “which model/strategy should I route
  this to, at what simulated cost/correctness?” (`control_room_audit.md` §2.2, ON-D5) `[M]`.
- **Evidence needed:** recommendation inputs + evidence beside the run context.
- **Current status:** **absent**. Old `#board-routing`/`#routing-drawer`; route `GET /api/routing`
  survives; no UI consumer now.

### J10 — Manage background Claude sessions

- **Trigger/cadence:** per background session.
- **Frequency:** per session.
- **Cost of failure:** MEDIUM (resource leak; missed intervention). `[ON-D7]`
- **Evidence needed:** roster with ownership, daemon status/PID, owned vs external controls.
- **Current status:** **absent**. Old `#claude-agents` grid, `#claude-agent-daemon-panel`; routes
  survive (`GET /api/claude-agents`, `/daemon`, `POST` start/stop). No UI consumer now.

### J11 — Record / close the session (the operator's own posterior)

- **Trigger/cadence:** every session close.
- **Frequency:** per session.
- **Cost of failure:** HIGH (systemic) — *“a session that does not write its close record has not
  closed”* (`agent_config/rules.md`) `[M]`; the self-knowledge layer depends on it
  (`self_knowledge_layer.md:18-19, 133-146`).
- **Evidence needed:** the session record, decision records, beliefs, scoreboard, reflections.
- **Current status:** **not a room surface** in either room; carried here because the operator
  definition (§1.1) makes it in-scope for the room as the AIO's spine.

### J-summary

| Job | Frequency | Cost of failure | Current status |
|---|---|---|---|
| J1 Glance | continuous | HIGH | satisfied (bounded roster) |
| J2 Triage stalled/failed | per incident | HIGH | partial (inspect only) |
| J3 Approve/cancel | per gated run | CRITICAL | partial (no door) |
| J4 Evidence + step timings | per decision | HIGH | partial/at-risk |
| J5 Watch spend | continuous | HIGH | partial (no trend/burn) |
| J6 Intervene per worker | per incident | HIGH | absent |
| J7 Audit what happened | per session | MED-HIGH | absent |
| J8 Start/enqueue | per campaign | MED-HIGH | absent |
| J9 Route model | per task | MEDIUM | absent |
| J10 Manage Claude sessions | per session | MEDIUM | absent |
| J11 Record/close | per session | HIGH | not a room surface |

---

## 3. PAIN POINTS — the current room measured against the old UI

### 3.1 Method (reproducible)

- **“Old room”** = `main` (`apps/control_room/static/index.html`, `static/app.js`, `routes/`),
  the parity reference the workflow hard-rules name.
- **“Current room”** = this branch (`feature/control-room-research`), the facelift + repair2 screen.
- **Panel parity** = the diff of unique `id="…"` values:
  `git show main:apps/control_room/static/index.html | grep -oE 'id="[^"]+"' | sort -u`
  vs the same over the working tree.
- **Feed/route parity** = the diff of `fetch(`/`EventSource(` tokens in `static/*.js`, against the
  registered routes (`grep -nE 'app\.(get|post)\(' apps/control_room/routes/`).
- **Capability parity** = the action verbs the two front ends can emit (old `app.js` mutation
  calls vs current `GOVERNED` token set).

**Measured headline** `[C]`: **235 unique ids in the old room, 24 in the current room — 234 ids
are not present in the current room** (the single shared id is `theme-toggle`). Old `app.js` is
3,420 lines; the current static layer is ~3,456 lines across eight JS modules — *more code, far
fewer surfaces*: the facelift spent its budget on the resting screen and the visual system, and
paid for it with the operational surfaces.

**The critical structural fact** `[M]`: the current **server still registers every old route**
(the 36 registered endpoints include `POST /api/experiments`, `POST /api/queue/reinterleave`,
`POST /api/flags/<id>/steer|interrupt`, `POST /api/claude-agents/…`, `POST /api/design-sessions/…`,
`POST /api/docs-health/approve`, `GET /api/registry`, `GET /api/routing`,
`GET /api/subscription-usage`, `GET /api/projections`, `GET /api/recording-audit`,
`POST /api/recording-sweep/run`). The current **front end fetches exactly two of them**:
`GET /api/glance` and the glance SSE at `GET /api/events` `[M]`
(`grep -rhoE '(fetch|EventSource)\(...' apps/control_room/static/*.js`). **The capability did not
disappear from the machine; it disappeared from the operator.**

### 3.2 The findings, ranked

#### P1 — Every per-worker action surface is gone; only read-only eligibility remains. **Cost: CRITICAL.**

- **Old:** `#supervisor-control-panel` (`supervisor-steer`, `supervisor-interrupt` behind a typed
  door), `#claude-agent-*` (`stop`, `respawn`, `rm`, `steer`, `detach`), `#cell-control-panel`,
  `#watch-button`, `#copy-session`, and the `#board-flags` steer/interrupt doors `[M]`
  (`git show main:apps/control_room/static/index.html`).
- **Current:** the run rows carry a decision token — `app.js:239` defines
  `GOVERNED = { approve: true, promote: true, cancel: true, retire: true }` — but **no code path
  POSTs any of the surviving routes** `[M]`. `.run-row[data-decision="approve"] .row-decision` is a
  *label*, not a door.
- **Consequence:** J3 and J6 cannot be completed in the room. The operator can see that a run needs
  approval and cannot give it; can see a runaway worker and cannot stop it. The “machine proposes /
  controller disposes” boundary becomes “machine proposes / controller leaves the room”.
- **Mechanism:** `control_room_direction.md` Move 3 (“rows show eligibility, never a button”) was
  implemented as *no action anywhere*, which is stronger than the move: the move reserves the
  action for the inspector (`R4`), and `R4` has no action control.

#### P2 — The per-worker live event stream is gone (and the `/api/events` name was repurposed). **Cost: HIGH.**

- **Old:** one page-lifetime `EventSource("/api/status")` for all cell transitions plus one
  `EventSource("/api/events/<cell_id>")` for the selected cell, rendered in `#transcript-panel`
  with Follow / Pause / Clear / Jump-to-live and a 500-row bound `[M]` (`control_room_audit.md`
  §2.3, §3.2).
- **Current:** `GET /api/events` now serves the **glance** stream (`glance.py:509-526`;
  `endpoint="api_glance_events"`), and the current client consumes only that. The per-cell route
  `GET /api/events/<cell_id>` still exists server-side but **nothing consumes it** `[M]`.
- **Consequence:** J4's “what is the agent doing, step by step, live?” is answered only by the
  bounded `[data-attempt-feed]` in `#selection-dock`; there is no fleet-wide transition stream and
  no per-cell follow/pause control.

#### P3 — No workforce step-timing surface. **Cost: HIGH.**

- **Measured:** neither the old nor the current room has a dedicated step-timing panel; the old
  transcript exposed per-event cost/tokens, and the current ladder exposes attempt/evidence, but
  the ledger's timing fields (`queue_wait_ms`, `service_time_ms`, `first_token_at`,
  `started_at`/`ended_at`) have no view `[M]` (`experiment_spec.py` `AttemptRecord`).
- **Consequence:** J4 cannot explain *where* a run's time and cost went; r0 A4 (“worker/fleet
  execution health absent”) is unresolved. This is a **required-but-absent** surface the repair must
  *add*, not merely preserve — the spec names it explicitly.

#### P4 — The money/health/decision boards were folded into the glance, but routing/registry/usage/queue/docs-health were dropped outright. **Cost: HIGH.**

- **Re-house (acceptable, not a drop):** Fleet→`R2`, Flags→`R1`, Status→`R3a`, docs-health
  proposal→`ON-G5`. These are legitimate re-housings and should be recorded as such.
- **Dropped (silent, not re-housed):** `#board-routing` (`GET /api/routing`),
  `#registry-drawer` (`GET /api/registry`), `#usage-content` (`GET /api/subscription-usage`),
  `#enqueue-button`/`#clear-queue-button` (`POST /api/experiments`),
  `#docs-health-*` panel, the `#claude-agents` grid, `#recent-design-list` and the design
  start/save/run/input controls, and `#live-now-list` `[M]`.
- **Consequence:** J7–J10 have no surface; `ON-D3/D4/D5/D7` are unserved.

#### P5 — Two authorities the old audit flagged are still unrendered — and the current room's green can hide them. **Cost: HIGH.**

- `GET /api/projections` and the `projections` block on `/api/matrix` had no consumer in the old
  room (`[M]` r0 M2/A2); the current room **reads projection health only into `R0`/`R3b`**
  (`glance.py:101-159`), which is a partial fix, but there is no per-projection detail surface.
- `GET /api/recording-audit` / `POST /api/recording-sweep/run` still have **no UI consumer**
  (`[M]` r0 M12).
- **Consequence:** the “is what I am looking at trustworthy / is it recorded?” jobs (J7, N4, N6)
  are only half-covered.

#### P6 — The roster is a bounded sample, not the fleet. **Cost: MEDIUM-HIGH.**

- **Old:** `#fleet-grid` + `#matrix-cells` rendered from the `/api/matrix` cell set with filters
  (All/Live/Running/Risk), search `#cell-search`, density `#density-toggle`, and counts
  `#fleet-counts` `[M]` (`board-fleet.js:124-161`).
- **Current:** `#run-list` is fed by `glance.run_sample` = `active_runs` + `failed_runs`, ranked
  active-then-failed (`glance.py:455-457`); there is no filter, search, density control, or
  separate live-now view `[M]`.
- **Consequence:** `ON-G2` is answered as *counts* but not *enumerability*; the operator cannot
  slice a large fleet or find a specific cell without a namespace change to the projection.

#### P7 — Queue control, design-session workflow, and the docs-health remediation flow are absent. **Cost: MEDIUM.**

- Old `#queue-door` / `#confirm-queue-clear` / `#queue-result`, `#design-start-form`,
  `#design-composer`, `#save-spec-*`, `#run-workflow-*`, `#interrupt-*`,
  `#docs-health-approve-form` `[M]`.
- Current: none. Routes survive (`POST /api/experiments`, `POST /api/design-sessions/…`,
  `POST /api/docs-health/approve`).

#### P8 — The generic-dashboard corrections were healthy, but they removed *both* the generic chrome and the genuine capability. **Cost: MEDIUM.**

- The direction's §4.3 removed left-rail board navigation, peer boards, KPI tiles and per-card
  microcharts as generic idioms `[M]`. That critique is sound and the current room is cleaner for
  it. `[H]` The error appears to be that the removal was applied at *capability* granularity
  instead of *chrome* granularity: “no peer boards” silently became “no routing/registry/queue
  surfaces,” and “no per-card microchart” became “no per-card step timing or worker actions.”

### 3.3 What the facelift got right (recorded so the repair does not regress it)

- The **canonical one-resting-screen glance contract** (`control_room_ia.md` §4) is implemented:
  `R0`/`R1`/`R2`/`R3a`/`R3b`/`R3c` with `ON-G1..G7` at rest (`apps/control_room/static/index.html`;
  `app.js:494-537`). `ON-G3`/`ON-G5` are built dynamically, exactly one each `[M]`.
- **`GET /api/glance`** is a genuinely new, read-only projection that joins the control packet,
  projection watermarks, worker heartbeats and the usage snapshot, with the **null-not-zero**
  discipline (`glance.py:1-29, 441-479`) `[M]` — this is the *right* foundation for a truthful
  room and must be extended, not replaced.
- A **token/theme/SVG visual system** with dark/light/forced-colors, a render gate at three
  viewports, and 86 screenshots (`apps/control_room/verification/gate_report.md`) `[M]`.

**The repair thesis, stated once:** keep the glance contract and the visual system; **restore the
operational surfaces and the decision doors** on top of the *same* `/api/glance` projection and the
*same* surviving routes, with a parity inventory that proves nothing was dropped.

---

## 4. DESIGN PRINCIPLES

Each principle is derived from the **repaired corpus** (`skills.json` / `catalogs.json`), names the
research evidence, states **what it forbids**, and names the **UI element that enacts it**. Where
the repair passes demoted a claim to `[P]`, the principle says so and does not dress policy as
consensus (`docs/reviews/control_room_taxonomy_repair.md` §7).

### DP1 — Operator-first ranking: the resting screen answers `ON-G1..G7` in priority order, above the fold, with no interaction.

- **Statement.** The first screen returns the highest-cost answers first — system/trust, attention
  (risk then decision), then the run ledger, then money, then fleet shape — in a fixed order that a
  stranger can read without clicking. `[M]` r0 M5/M7 (docs-health and duplicate lists pushed
  fleet state below the fold); `control_room_ia.md` §4 canonical map `G1→R0, G2→R2, G3/G5→R1,
  G4→R3a, G6→R0, G7→R3c` `[M]`.
- **Research evidence.** `[skill:glance]` — “rank the glance screen operator-first: (1) system/
  connection health, (2) running/queued/failed, (3) anything failing or stale, (4) money,
  (5) decisions pending, (6) fleet shape”; supported by `[cat:ia-layout/ia-attention-surface]`
  (“give alerts and health a first-class board”) and `[cat:trust-attention/tr-degraded]`. The exact
  *ordering* and the domain split are `[P]` (`skill-glance` local-policy note; r6a E2–E4).
- **Forbids.** Docs-health/registry/governance chrome above fleet state; a green badge over stale
  data; a duplicate “live now” list competing with the roster; anything decorative before a
  decision-relevant signal.
- **Enacts.** `[data-region="R0"/"R1"/"R2"/"R3a"/"R3b"/"R3c"]` and exactly-one
  `[data-answer="ON-G1..G7"]`, verified by the render gate (`control_room_ia.md` §10; current
  `index.html:50-175`, `app.js:494-537`).

### DP2 — The unit of work is an agent-native, addressable **run object**, not a service.

- **Statement.** Every actionable row leads with `session/agent → worktree/host target → current
  command/tool → provider×model → attempt`, and every object carries a stable typed address
  (`run`, `phase`, `attempt`, `session`, `worktree`, `lease`, `flag`, `approval`, `record`).
  Identity survives re-polling and re-selection. `[M]` (`control_room_direction.md` §2.1).
- **Research evidence.** `[skill:agent-ops]` — the trace/span tree is the core navigation object;
  `[cat:agent-ops/ao-observability]` (session grouping, `tech-ops-session-grouping` 7, agentops
  only) and `[cat:trust-attention/tr-lineage]` (session→trace→span). Move 1/5 (`[X]` exemplars
  `nvitop`/`btop`/`k9s`/Textual). Composition `[P]`.
- **Forbids.** Service-name primary keys; a run list that loses identity on live update; a command
  palette used as the information architecture (palette over boards is the generic idiom; Move 5).
- **Enacts.**   `.run-row[data-run-id]` with `[data-field="terminal.target"]`,
  `[data-field="command.current"]`, `[data-field="model.provider"]`, `[data-field="run.live"]`
  (the recognizability block, `index.html:11-46`); `glance.py:307-339`.

### DP3 — Narration is not truth: evidence travels in typed classes.

- **Statement.** What the model *claims* (ADVISORY), what the ledger *measured* (MEASURED), and
  what the committed tree *is* (SOURCE) are visually distinct; independent verification
  (`test_runner`) is the **only** source of a “passed” mark, and a run cannot render “done”
  without the measured class. `[M]` (`test_runner` is the sole source of `test_executed_success`;
  `control_room_direction.md` §8).
- **Research evidence.** `[skill:trust]` (provenance on consequential numbers; explicit
  uncertainty) + `[cat:agent-ops/ao-eval]` — “make evaluation a distinct step rather than treating
  the work product's assertion as its score” (`tech-ops-eval-loop` 21, agentops only). Move 4
  (`[M]` repo contract + `[X]` pattern). Provenance badges and unmeasured encoding are `[P]`
  (`tr-provenance`, `tr-uncertainty`).
- **Forbids.** A single health number collapsing distinct failure modes; the agent's “done” shown
  as truth; estimated cost shown as metered; a green badge when a projection is stale.
- **Enacts.** `.row-evidence[data-evidence-class="advisory"|"measured"]` and
  `[data-field="decision.receipt"]` on the row; the `#evidence-ladder[data-attempt-boundary]` in
  `#selection-dock` (`index.html:42-46, 186-196`).

### DP4 — Every consequential act is a **governed decision with a receipt**; machine proposes, controller disposes.

- **Statement.** At rest a row shows a compact eligibility token
  (`observe|inspect|approve|promote|cancel|retire|none`); the full preview (target, epoch, scope/
  blast radius, budget effect, reversibility, proposer + evidence authority) lives one selection
  away and the act closes with a recorded receipt. The room never auto-steers. `[M]`
  (`agent_config/rules.md` P0/P1; packet `safe_actions` is the derived authority).
- **Research evidence.** `[skill:shell-ia]` — “keep money on the money board and alerts on an
  attention board…”; `[cat:ia-layout/ia-attention-surface]` (“a stable lifecycle instead of a
  transient toast,” `tech-trust-alerting` 6); Move 3. The concrete eligibility vocabulary and the
  composition are `[P]`.
- **Forbids.** A flag becoming an automatic steer; bare CRUD buttons with no target/scope/receipt;
  a consequential act that is not recorded at the moment of the act
  (`agent_config/rules.md`: “Recording is part of the act”).
- **Enacts.** `[data-field="decision.eligibility"]`, `[data-authority="controller"]`,
  `.run-row[data-decision] .row-decision` (the at-rest token), and the `R4` decision/flag preview
  carrying the safe-action contract (`index.html:27-30`); `glance.py:213-260`.
  *Repair requirement:* the token must terminate in a real door (P1) — eligibility without an
  action is DP4 half-enacted.

### DP5 — Money is a bounded, attributable constraint on the attempt — never a KPI; unknown is not zero.

- **Statement.** Cost is a run facet: reserved vs settled, `cost_source`, hard-cap headroom,
  settlement status (`matched|underspent|overspent|unsettled`), attributed to the attempt and its
  lease, with provider windows and wallet read *together*. `[M]` (`core.cost_provenance`;
  `control_room_direction.md` Move 6; gives the exact five-value `ON-G4` answer).
- **Research evidence.** `[skill:charts]` + `[cat:ia-layout/money-cost-attribution]` (“attribute
  cost to the run/agent that incurred it,” `tech-money-cost-attribution` 4, agentops only) and
  `[cat:ia-layout/ia-money-grouping]`. The quota/wallet/threshold composition is `[P]` (r6a E3;
  `money-cost-attribution` is the `[X]` part).
- **Forbids.** Top-row KPI stat tiles; money cards dethroning the roster; a `$0.00` for an unread
  cost; estimated or unknown shown as metered; lease reservations omitted from the money view.
- **Enacts.** `R3a` — `[data-field="money.spend|burn|quota|wallet|leases"]` plus the bounded
  `[data-money-risk]` exception (`glance.py:342-388`), and the per-row
  `.row-lease[data-budget-reserved|settled|cap|headroom|settlement]` (`index.html:33-36`).

### DP6 — Green must never lie: provenance, freshness, degraded and uncertainty are first-class.

- **Statement.** Every consequential number carries a source class and a freshness bound; a
  stale/lagging/failing projection, a degraded dependency, a partial window and an unmeasured value
  each render as distinct, explicit states. A zero recorded four hours ago is not current.
  `[M]` (`control.projection_watermarks` classify rules; `control_room_audit.md` M2/A10).
- **Research evidence.** `[skill:trust]` (provenance + freshness + degraded banner + explicit
  uncertainty; avoid “a fresh-looking chart over stale/partial data”) with
  `[cat:trust-attention/tr-freshness]`, `[tr-degraded]`, `[tr-uncertainty]`. All three premium
  techniques are `[P]` (r6a E4), grounded in the repository's own `cost_provenance` /
  projection-watermark contracts.
- **Forbids.** A global truth footer as the trust model; partial data rendered as complete;
  retained-window data implying live; “unknown” omitted (never fabricate a zero).
- **Enacts.** `R0` trust answers `[data-field="trust.epoch|worst_age|projection_state|degraded_count|stale_count|partial_count|unknown_count"]` and the four named system dimensions
  `system.browser|control|workers|projections` (`glance.py:162-210`); `R3b` health detail
  `health_detail.workers|projections`.

### DP7 — Marks answer questions, and charts run on a performance budget.

- **Statement.** Map each operator question to the mark that answers it: cost/burn/latency over
  time → line/area + inline sparkline; fleet/node status → status grid; a bounded quantity →
  gauge; a large set → sortable (virtualized) table; live output → one log/event stream with
  follow/pause; a multi-step run → timeline/waterfall; cross-group comparison → small multiples.
  Bound live marks: canvas over SVG for high-frequency series, decimation, lazy render.
- **Research evidence.** `[skill:charts]`; `[cat:chart-selection/ch-time-series]`,
  `[ch-status-grid]`, `[ch-gauge]`, `[ch-table]`, `[ch-log-stream]`, `[ch-timeline]`,
  `[ch-small-multiples]`, `[ch-perf]`. Gauge/small-multiples/status-grid-default/table
  virtualization are `[P]` (r6a E1); `ch-perf`'s lazy render is the corpus' only *measured*
  performance evidence.
- **Forbids.** Per-card microcharts that cannot compare (`[M]` r0 M6); mixing three chart grammars
  on one page; rebuilding a 500-row list per event; color as the only status signal.
- **Enacts.** The status rail `.row-status`, `R3c` bounded composition marginals
  `[data-marginal="model|condition|provider|lifecycle"]` (`glance.py:391-438`), and the single
  bounded `[data-attempt-feed][data-feed-follow]` — with **no** per-card sparkline.

### DP8 — One restrained, accessible visual system: one token layer, dark-first + real light + forced-colors, status never color-alone.

- **Statement.** One CSS-custom-property token set (surface/elevation/accent/status/type) derives
  dark and light themes and a forced-colors path; status uses few colorblind-safe hues, always
  paired with shape or label; dense data uses tabular numerals on a small type scale; motion is a
  short feedback budget that honors `prefers-reduced-motion`.
- **Research evidence.** `[skill:visual-system]`; `[cat:color-motion/cm-tokens]`,
  `[cm-status-color]`, `[cm-dark-first]`, `[cm-type]`, `[cm-motion]`, `[cm-reduced-motion]`,
  `[cm-forced-colors]`. Several of these are explicitly `[P]` in the repaired catalog
  (`cm-accent`, `cm-icon`, `cm-elevation`, `cm-reduced-motion`, `cm-forced-colors`); only
  `cm-status-color` and `cm-dark-first` rest on broader corpus support.
- **Forbids.** Inverting light to fake dark; accent everywhere / more than a handful of hues;
  color-only status dots; motion competing with the 1 s live cadence; decorative chrome over data.
- **Enacts.** The CSS token block in `static/style.css`, `#theme-toggle` (the one id shared with
  the old room), the color+glyph status rail `.row-status`, and the render gate's contrast /
  forced-colors capture matrix (`verification/gate_report.md`) `[M]`.

### DP9 — Build-less vanilla JS, with theme-aware accessible SVG micro-visuals.

- **Statement.** Keep the console build-less: vanilla-JS state/render + CSS custom properties, and
  hand-authored SVG/CSS micro-visuals. Use a chart runtime only where streaming breadth or a broad
  mark catalog justifies it. Author diagrams with `viewBox` + `currentColor`, give informative SVG
  a `title`/`desc`, keep labels as `<text>`, and mark decorative SVG `aria-hidden`.
- **Research evidence.** `[skill:delivery]` (build-less; the no-build guardrail is `[P]`, r6a E7;
  `[cat:frameworks/fw-no-build]`, `[fw-canvas-stream]`, `[fw-d3]`); `[skill:svg]` with
  `[cat:svg-technique/svg-theme]`, `[svg-micro]`, `[svg-accessible]`, `[svg-print]`.
- **Forbids.** A React SPA/build pipeline for a single-page local console; pulling a JS chart
  runtime for a 40 px sparkline; hard-coded SVG fills; text outlined to paths; decorative SVG
  announced to screen readers.
- **Enacts.** The no-build shell (`control-room-core.js`, `charts.js`, `visuals.js` alongside
  `app.js`, `shell.js`, `board-fleet.js`, `keyed-list.js`, `detail-sheet.js`), and
  `static/architecture.svg` (currently orphaned — r0 §2.6/A7; the repair should either place it as
  a scoped system/help link or leave it out, per direction §4.3).

### DP10 — Selection is a docked master–detail that survives live updates; a command palette accelerates, never replaces.

- **Statement.** Selecting a node opens a docked detail region that persists while data updates,
  with the roster visible alongside; long-tail surfaces use progressive disclosure; a persisted
  density mode is available. A command palette and global shortcuts are an accelerator over the
  visual IA, never the only path.
- **Research evidence.** `[skill:shell-ia]`; `[cat:ia-layout/ia-master-detail]`,
  `[ia-command-palette]`, `[ia-progressive-disclosure]`, `[ia-density-ladder]`. The command
  palette's direct corpus support is one record (Move 5), so palette-as-primary is explicitly
  forbidden; the docked-detail persistence is the move's real requirement (`ON-D1`).
- **Forbids.** A detail view that resets when live data updates; a palette as the sole navigation;
  burying quota/leases or approvals in an overflow drawer; losing selection across edits.
- **Enacts.** `#selection-dock` (docked ≥760 px, bottom sheet below; `detail-sheet.js`) with
  `#evidence-ladder` and the bounded `[data-attempt-feed]`; `#lens-open`/`#lens-close` for
  deliberate lenses. *Repair requirement:* the dock must also host the per-worker **actions** and
  the **step-timing** view (P1/P3) so DP10 carries J4/J6 as well as J2.

### Principle → corpus → element (one table)

| # | Principle (short) | Primary repaired refs | Forbids (short) | UI element |
|---|---|---|---|---|
| DP1 | Operator-first ranking | `[skill:glance]`, `[cat:ia-layout/ia-attention-surface]` | chrome above fleet; green over stale | `R0..R3c`, `ON-G1..G7` |
| DP2 | Agent-native addressable run | `[skill:agent-ops]`, `[cat:agent-ops/ao-observability]` | service-name rows; palette-as-IA | `.run-row[data-run-id]` |
| DP3 | Typed evidence classes | `[skill:trust]`, `[cat:agent-ops/ao-eval]` | narration as truth; one health number | `.row-evidence[data-evidence-class]`, ladder |
| DP4 | Governed decisions + receipt | `[skill:shell-ia]`, `[cat:ia-layout/ia-attention-surface]` | auto-steer; unrecorded act | decision token + `R4` preview |
| DP5 | Money as bounded constraint | `[skill:charts]`, `[cat:ia-layout/money-cost-attribution]` | KPI tiles; unknown as `$0.00` | `R3a`, `.row-lease[data-budget-*]` |
| DP6 | Green never lies | `[skill:trust]`, `[cat:trust-attention/tr-*]` | global truth footer; partial as complete | `R0` trust fields, `R3b` |
| DP7 | Marks with a budget | `[skill:charts]`, `[cat:chart-selection/*]` | per-card microcharts; color-only | rail, `R3c`, one feed |
| DP8 | One token layer, accessible | `[skill:visual-system]`, `[cat:color-motion/*]` | fake dark; accent glut | CSS tokens, `#theme-toggle` |
| DP9 | Build-less + accessible SVG | `[skill:delivery]`, `[skill:svg]`, `[cat:svg-technique/*]` | React build; JS sparkline | no-build shell, SVG |
| DP10 | Master–detail that persists | `[skill:shell-ia]`, `[cat:ia-layout/ia-master-detail]` | reset-on-update; overflow burial | `#selection-dock`, lens |

---

## 5. How this foundation is used (handoff)

- **`u1_interaction_model`** takes §1 (operator/authority) and §2 (jobs J1–J11) as its contract:
  run-lifecycle states, decision points and the evidence each needs, **actions per worker/session**
  (J6/J10), and the **step-timing** view (J4/P3).
- **`u2_parity_inventory`** takes §3's id/route diff as its starting enumeration and must classify
  **every** old panel, control and feed as preserve / re-house / replace-with-reason — no silent
  drops. The `GOVERNED`-without-a-door finding (P1) and the repurposed `/api/events` (P2) are
  mandatory rows.
- **`u3_reconcile_ia`** must keep the canonical `ON-G1..G7` map and pixel budgets while adding the
  per-worker event/action region and the step-timing region explicitly.
- **`u4_implement`** keeps the glance contract and visual system and restores the dropped surfaces
  on the *same* `/api/glance` projection and the *same* surviving routes.
- **`u5_gate_semantic_parity`** extends `scripts/verify_control_room_rendering.py` with the
  semantic glance checks, the **feature-parity** checks (every inventory id/region present, wired,
  non-empty with live data or an explicit documented empty-state), and the per-worker
  event/action + step-timing checks.

---

## 6. Reproduce

```bash
# Old-room vs current-room panel diff (P1 measurement)
comm -23 \
  <(git show main:apps/control_room/static/index.html | grep -oE 'id="[^"]+"' | sort -u) \
  <(grep -oE 'id="[^"]+"' apps/control_room/static/index.html | sort -u) | wc -l   # 234

# Front-end feed parity (P2): only two endpoints are consumed by the current client
grep -rhoE '(fetch|EventSource)\("([^"]+)"' apps/control_room/static/*.js | sort -u

# Routes the server still registers (capability survives server-side)
grep -rnE 'app\.(get|post)\(' apps/control_room/routes/ apps/control_room/server.py | wc -l  # 36

# The repaired corpus the principles cite
python3 -c "import json;d=json.load(open('experiments/research/control_room/skills.json'));print([s['id'] for s in d['skills']])"
```

**Doc lifecycle:** this file carries `status: accepted` (`tests/test_doc_lifecycle.py:66-120`).

*End of phase `u0_ux_foundation`. The operator definition, the jobs, the measured pain points and
the ten principles are the contract for phases `u1`–`u7`; the parity inventory (`u2`) makes them
enumerable, and the semantic + feature-parity gate (`u5`) makes them testable.*
