---
status: accepted
---

# Control Room — direction and facelift brief: the live run as the unit of work (campaign `control_room_research_repair2`, phases `q0`–`q6`)

**Date:** 2026-09-11
**Supersedes:** the r5/r7 `control_room_direction.md` facelift brief (retained as the rejected
baseline; the specific drops are enumerated in §6) and the p1/p6 repair brief, whose §4 distinctive
table this revision replaces.
**Inputs:** the measured baseline `docs/research/control_room_audit.md` (r0), the operator-needs
contract `docs/research/control_room_questions.md` (r1), the **q0 quoted-evidence** taxonomy/catalogs/
skills `experiments/research/control_room/{taxonomy,catalogs,skills}.json`, the one-resting-screen IA
`docs/research/control_room_ia.md` (q2, tightened by q5), and the repair2 adversary passes: entailment
(`docs/reviews/control_room_repair2_entailment.md`), design (`docs/reviews/control_room_repair2_design.md`),
and IA (`docs/reviews/control_room_repair2_ia.md`) — all three **PASS**.
**Distinctive-direction rewrite (q1/q4).** §4 is rebuilt around eight exemplar-grounded, agent-native
moves; a blind 10-second **recognizability test**; an explicit **removed** list of generic
dashboard elements; a run/evidence/action **visual grammar**; and a **restraint budget**. Every move
separates *pattern exists* (`[X]`) from *repository requires* (`[M]`) from *composition* (`[P]`), so no
component count is presented as proof of the composition (thesis verdict PASS, q4).
**Support status:** the q0 semantic crosswalk replaced label-level support with quoted, pattern-gated
source evidence and enforced one direct leaf per label (q3 entailment verdict PASS). Counts in §4 and §7
are the current `taxonomy.json` supports; several earlier `[X]` moves are small or `[P]` and say so.
Acceptance criteria include the render gate at 1440×900/1024×768/390×844, the one-resting-screen glance
check (q5 IA verdict PASS), and the §4.2 recognizability test. **No open design blocker remains**;
explicit waivers are listed in §17 and §19.

**What this document is.** A design direction, not a mockup and not a chart gallery. It says what the
room is *for* (operating many CLI AI agents by triaging live runs and making governed decisions), what
the central object is (a run in one of four coupled states), how that object becomes immediate on a
resting screen, and what the implementation may not regress. It replaces the "sleek instrument panel"
thesis with a run-first one, because a panel field is the category default for every observability
tool and says nothing about reasoning agents.

**Claim discipline.** Every statement is labelled:

- `[M]` **measured** in this repository (r0 code facts, control-plane contracts, or the p0-repaired
  corpus counts).
- `[X]` **external observation** from a named source or exemplar checked during acquisition (the
  five-family facet corpus, or a fresh direct check recorded by an adversary).
- `[P]` **policy** — a local design decision, not an external consensus. This is where every repaired
  or unsupported move now lives.

**Citation legend.** `[cat:<catalog>/<item>]` and `[skill:<id>]` = p0-repaired reduction artifacts
(catalog item evidence carries support/family counts); `[M#/A#]` = r0 misplaced/absent finding;
`[ON-*]` = r1 operator need; `[D#]` = r6b design finding; `[IA#]` = r6c IA finding; `[E#]` = r6a
entailment finding; `[src:...]` = corpus source (appendix).

---

## 1. The direction

> **The room is a run-triage console for a fleet of CLI AI agents.** The unit of work is a **live
> run** — a spec/cell executed by one agent session, carrying a lifecycle, a cost, an evidence chain,
> and a pending human decision. The resting screen is the **run roster**, ranked by what needs the
> operator next. Selecting a run opens its **evidence ladder** in place. Every control previews its
> target, scope, revision, reversibility and recording before it acts.

Two sentences carry the identity, and both are behavior, not styling:

1. **Every run is a first-class addressable object with four coupled facets** — lifecycle, cost,
   evidence, decision (§2). A screenshot that does not show a run, its phase, its verification, and
   its pending decision is not this product.
2. **The agent's narration is not the truth.** A model can claim it passed while `test_runner`, the
   ledger, or the registry says otherwise. The room keeps narration, measured facts, independent
   verification, and controller decisions in separate, visible evidence classes (`[M]`; r6b D9).

This is a product direction `[P]`, grounded where possible in the terminal/agent-ops exemplars the
repaired catalogs support (§4) and in r0's measured problems (§5). It is deliberately *not* a
dashboard grammar (§6).

**What "sleek" means here.** Boringly legible under load: operator-first ranking, a calm resting
screen, truthful state, evidence one selection away, safe controls, and accessibility by default.
The visual system (dark/light tokens, restrained motion, accessible status) is a quality bar `[P]`,
never the differentiator — the differentiator is the run object and the decision boundary.

---

## 2. The run object — anatomy

A run is the join of four facets. The room must be able to render all four for the *selected* run at
once, and summarize each facet across the fleet at rest. This is the schema the screen is built from.

```text
RUN = identity × lifecycle × cost × evidence × decision
```

### 2.1 Identity and scope

| Field | Meaning | Source |
|---|---|---|
| `run_id` | stable primary key; never reset by live reconciliation | control db `runs` `[M]` |
| `spec_id` / `workflow` | the compiled ExperimentSpec / agent_task being executed | `experiment_spec` `[M]` |
| `cell_id` / factor assignment | story/cell and the model × condition × policy assignment | ledger job `[M]` |
| `worktree_identity` | the ephemeral worktree the run writes into | admission/lease fields `[M]` |
| `attempts[]` | parent/child attempt chain with retry/escalation reason | ledger `AttemptRecord` `[M]` |
| `control_epoch` | the durable-state watermark; changes when the run's truth changes | control packet `[M]` |

Identity must survive live updates: a run is the same object while it is re-polled, reselected, or
moved between lenses (`[M]`; r6c IA10).

### 2.2 Lifecycle

The run state machine is the control db's enforced `RunState` graph, not a re-derived one
(`src/agentic_dynamics/control/control_db.py:171-208`; the packet derives `active_runs`,
`awaiting_approvals`, `promotable_runs`, `failed_runs` from it; `[M]`):

```text
queued -> running
    running          -> awaiting_approval | verifying | promotable
    awaiting_approval -> running | verifying
    verifying        -> running | awaiting_approval | promotable
    promotable -> promoting -> merged -> projecting -> published
    {any non-terminal} -> failed | quarantined
    {queued, running, awaiting_approval, verifying, promotable, promoting} -> cancelled
```

The UX may render a simplified lifecycle label, but that label must be `[P]` and map exhaustively to
a `RunState`; only the database graph underwrites `safe_actions`. The earlier
"proposed/leased/awaiting-evidence/settled/archived/superseded/dead-letter" sketch is withdrawn as a
`[M]` claim (p3 E2): it named states the database does not enforce.

`phases_completed/phases_total`, `current_phase`, `changed-at`, and `attention state` are the
lifecycle facts shown per roster row (`[M]`; the packet's `active_runs`/`promotable_runs` entries carry
phase counts). The room renders the database's state, never a re-derived one: `safe_actions` come from
the same transition graph the database enforces (`[M]`; r0 M3, r6c IA3).

### 2.3 Cost

Cost is not a separate board; it is a facet of the run:

| Field | Meaning | Source |
|---|---|---|
| `reserved_cost_usd` + `hard_cap_usd` | the lease reserved before any spend (fail-closed) | `control.admission` `[M]` |
| `cost_source` | `metered` / `estimated` / `unknown` / `reconciled` | `core.cost_provenance` `[M]` |
| `cost{inference, orchestration}`, `rework_cost`, `reuse_value` | per-attempt and per-run cost | ledger `[M]` |
| settlement status | `matched` / `underspent` / `overspent` / `unsettled` | `control.settlement` `[M]` |
| provider window / wallet | subscription window % or per-token wallet, by provider | usage/settlement ledger `[M]` |

The rule that makes cost trustworthy: **an unknown cost is never drawn as zero** (`[M]`; the
`cost_provenance` contract). The run context shows reserved vs settled, the provenance class, and the
headroom that the next decision consumes. Fleet-level money is a *lens* (`[cat:ia-layout/…]`), and the
spend/burn/window composition is `[P]` local policy because the corpus states cost tracking, not a
quota/wallet/lease grouping (`[E3]`; `[P]` `[cat:ia-layout/ia-money-grouping]`).

### 2.4 Evidence chain

The evidence ladder is the run's detail spine. Each rung is a **typed evidence class** — the types are
the point, because they carry different authority:

```text
identity
  -> phase
     -> attempt (lifecycle, model, provider version, timestamps)
        -> agent narration / tool events (ADVISORY: what the model claims)
        -> measured runtime facts (MEASURED: ledger events, tokens, timestamps)
        -> change / commit (SOURCE: the diff, the committed tree)
        -> independent verification (MEASURED: test_runner result, evaluator_independent)
        -> static analysis / diagnostics (DERIVED)
        -> cost / lease provenance (MEASURED: admission + settlement)
        -> controller decision (POLICY: the recorded human act)
        -> canonical record (SOURCE/POLICY: registry entry, supersession, causes)
```

The corpus supports the *causal shape* and the trace/span tree: `[cat:trust-attention/tr-lineage]` backs a
session→trace→span lineage from `tech-ops-trace-tree` (17, agentops + dashboards); `[cat:agent-ops/ao-observability]` backs structured traces from
`tech-ops-observability` (9); `[cat:chart-selection/ch-timeline]` backs a run timeline from
`tech-viz-waterfall-timeline` (3, **agentops only** — single-family caveat). The corpus does **not**
state that every agent-ops source ships an identical waterfall (`[E5]`), so the claim is scoped to the
cited sources. The narration-vs-verification split is repository-specific `[M]` (`test_runner` is the
sole source of truth for `test_executed_success`), not a corpus finding; it is stated as `[M]`.

Registry lineage (supersession/causality) is reachable from the run but is *not* the same surface as
the runtime trace (`[M]`; r0 M4, r6c IA11).

### 2.5 Decision state

A run may be blocked on a **governed human decision**. The decision object is explicit:

| Field | Meaning |
|---|---|
| decision kind | approve / promote / cancel / retire / raise-cap (P0), or a lease-bounded P1 act |
| authority | the controller alone for P0; any actor within its lease for P1 |
| target | the exact run/worktree/candidate SHA the act changes |
| rationale | why the machine proposes it (proposer + evidence authority) |
| gate | the gate ID / promotion command the act routes through |
| reversibility | reversible, or requires typed confirmation |
| safe action | the database-derived next action, or none |
| receipt | the decision record + recording coverage that closes the act |

The authority model is fixed and non-advisory: **the machine proposes; the controller disposes**;
observe-only rails (supervisor, lease watchdog) raise flags and never steer (`[M]`; r0, r6b D12). The
room may make a decision *fast*, but it must never turn a flag into an automatic steer, interrupt,
route, retry, or budget action (`[P]`). The decision queue is `awaiting_approvals` / `promotable_runs`
from the control packet (`[M]`; r0 M3/A3).

---

## 3. How the run object becomes immediate on screen

Immediacy means: at rest the operator sees the fleet of runs and what needs them; one selection
reveals the whole run; the decision is taken in place. No board hopping reconstructs a single
decision (`[P]`; r6b D2, r6c IA2/IA9).

```text
PERSISTENT SCOPE / TRUTH
  repository | worktree/campaign scope | browser connection | control epoch | degraded summary

ATTENTION INBOX  (durable, ranked, deduplicated)
  pending decisions | run failures/stalls | money-risk exceptions | worker/projection impact
  advisory flags | process gaps

RUN LEDGER  (default resting body — the fleet of live agent sessions)
  session/agent | worktree/terminal | current command/tool | provider×model | attempt
  phase | lifecycle | ADVISORY claim | MEASURED proof | lease/cost | eligibility | receipt

SELECTED RUN / EVIDENCE LADDER  (docked inspector, one live stream)
  identity -> lifecycle -> evidence chain (typed) -> cost -> decision -> registry record

SAFE ACTION  (inline with the decision)
  target + epoch/revision + scope + budget effect + reversibility
  preview -> typed confirmation when required -> execute -> receipt

SECONDARY LENSES  (context, not mandatory hops)
  Money | Health/projections | Decisions/registry | Composition | History
```

### 3.1 The resting screen (no interaction)

The default body is a **run ledger**, not a panel grid. It is a keyed, write-on-change list
(`[M]`) whose rows are agent sessions, ranked so that actionable state floats: pending decisions and
failures first, then running/queued, then settled. Each row carries enough run anatomy to decide
whether to open it: session identity, terminal target, current command, attempt boundary, phase
progress, lifecycle, paired ADVISORY/MEASURED evidence marks, cost provenance, attention, eligibility,
and receipt coverage. `R1` and `R3` are annotation gutters for this ledger, not peer panels; their
values must never be rendered as a dashboard card wall.

The persistent scope/truth strip and the attention inbox are the only global summaries. Money, health,
registry and composition are **lenses** opened deliberately, not peer destinations an incident must be
reassembled across (`[P]`; r6b D2). This is the direct repair of r5's four-peer-board IA, which the
adversaries rejected (`[E2]`).

### 3.2 Selection and the evidence ladder

Selecting a run establishes one joined context and opens the ladder (§2.4) in a docked inspector.
Selection is stable: it survives live reconciliation and compatible lens changes; scope, filters,
sort, time range, scroll, and follow/pause persist; incompatible scope changes confirm; disappeared or
stale objects keep their identity (`[M]`; r0 §9.2, r6c IA10). Exactly one event stream is open at a
time (`[M]`; r0 §9.1/9.2). The roster stays visible while the inspector is open — the fleet is never
lost to a modal (`[P]`; r6c IA1/IA2).

### 3.3 The attention inbox

Attention is stateful work, not a decorative strip (`[P]`; r6b D3). Each item has a stable key, a
typed source object, severity + actionability, first/last-seen, scope, lifecycle
(`new|active|snoozed|resolved|stale`), authority (measured/computed/heuristic/policy/unknown), and an
evidence link plus a database-derived safe action when one exists. Announcement policy: one polite
live region, on **transitions only**, deduplicated; ordinary changing metrics (spend/burn/running) are
labelled and readable but not announced (`[M]`; r0 M9; `[X]` `[src:mdn-live-regions]`).

The stateful-inbox pattern is `[X]` from the r6b direct check of Linear Triage (inside the dashboards
family as a product, outside the sampled technique labels); the internal alerting surface is backed by
`[cat:ia-layout/ia-attention-surface]` from `tech-trust-alerting` (6, **dashboards only**). The
specific state machine and snooze/resolution semantics are `[P]`.

### 3.4 Safe action

Every mutation previews, before execution (`[M]`; r0 M14, r6b D12): target and current selection;
repository/worktree/model/provider/cell context; requested scope and blast radius; current run state
and control epoch/revision; gate ID + candidate SHA; proposer and evidence authority; admission/budget
effect; reversibility; the DB-derived safe action; the resulting decision/recording receipt. Typed
confirmation stays for irreversible acts and never substitutes for current-state validation (`[M]`).

### 3.5 Mobile — triage/inspection, not a stacked wall

Mobile is **triage and inspection mode** (`[P]`; r6b D11, r6c IA16): the first view is unresolved
attention and recently changed runs; one selected object and its evidence ladder are preserved; target
context and safe actions precede secondary charts; fleet comparison is an explicit filtered view
rather than a compressed desktop mosaic; and the same truth, focus-containment, focus-return, and
query/time-preservation rules hold as on desktop.

---

## 4. Distinctive moves — exemplar-grounded and agent-native

This is the identity-bearing section. Every move names the exemplar that inspired it, what the
exemplar actually does, and what OURS does *differently* for operating a fleet of CLI AI agents. It
answers the p4 design critique directly: the composition must not be a generic observability shell
with runs substituted for services (p4 D1/D2/D4/D5/D9).

### 4.0 Three claims, kept separate

A design critique (p4 D4) requires the direction to stop blurring three different things. Every move
below separates them explicitly:

1. **Pattern exists `[X]`** — a named exemplar (or repaired catalog item) demonstrates a component or
   interaction pattern. This is bounded external observation, scoped to the cited source, never a
   claim of consensus.
2. **Repository requires `[M]`** — a local contract (the control packet, `RunState`, admission/lease,
   `test_runner`) forces a behavior regardless of what any corpus shows.
3. **Composition is `[P]`** — how those patterns are arranged into *this* screen is a local product
   decision. No support count makes the composition externally grounded.

The q0 semantic crosswalk replaced label-level support with quoted, pattern-gated source evidence, so
several earlier counts moved or dropped below the ≥3-source bar. The counts below are the current
direct supports from `taxonomy.json`. Component patterns may be `[X]`; **every constellation is
`[P]`**.

### 4.1 The moves

**Move 1 — Session/agent identity is the row's primary key, never a service name.**
- **Exemplar (`[X]`):** `nvitop` (`[src:nvitop]`) and `btop` (`[src:btop]`) process tables, `k9s`
  (`[src:k9s]`) resource view, Textual (`[src:textual]`); catalog `[cat:agent-ops/ao-observability]`
  (`tech-ops-session-grouping` 7, agentops only; `[cat:agent-ops/ao-observability]`).
- **What the exemplar does:** gives a repeated operational activity a stable session identity that
  can be organized and filtered.
- **What OURS does differently:** the addressable object is an **agent session**, and each actionable
  row leads with `session/agent → worktree/host target → current command/tool → provider×model →
  attempt`. A stranger can identify which agent is acting and where it is writing without translating
  a service name. This is the departure from "observability dashboard with runs substituted for services".
- **Class:** pattern `[X]`; composition `[P]`.

**Move 2 — The inspector is an attempt-scoped causal ladder, not a transcript.**
- **Exemplar (`[X]`):** trace/span trees `[cat:trust-attention/tr-lineage]` (`tech-ops-trace-tree`
  17) and the session waterfall `[cat:chart-selection/ch-timeline]` (`tech-viz-waterfall-timeline` 3,
  **agentops only**).
- **What the exemplar does:** renders a parent/child span tree with a timing waterfall so a
  distributed failure is walkable cause-to-effect.
- **What OURS does differently:** the tree is re-keyed to agent semantics — `session → phase →
  attempt → {narration, measured facts, commit, independent verification, cost, decision, record}` —
  and every rung is a **typed evidence class**, not a latency span. Attempt boundaries are visible on
  the resting row and the full ladder is one selection away; the product explains an agent's work rather
  than merely reporting service latency (Move 4).
- **Class:** pattern `[X]`; composition `[P]`.

**Move 3 — Every consequential act is a decision object; rows show eligibility, never a button.**
- **Exemplar (`[X]`/`[M]`):** the repaired attention surface (`tech-trust-alerting` 6;
  `[cat:ia-layout/ia-attention-surface]`) keeps an operational problem addressable after detection;
  the repository's own promotion gate supplies the `[M]` safe-action graph.
- **What the exemplar does:** gives a problem a stable lifecycle instead of reducing it to a transient
  toast; the control packet re-validates the target before a mutation.
- **What OURS does differently:** the *unit* is a governed decision over an agent run: target, control
  epoch, scope/blast radius, budget effect, reversibility, proposer + evidence authority, and the
  receipt that closes it. At rest a row shows a compact **eligibility token**
  (`observe|inspect|approve|promote|cancel|retire|none`); the full preview stays in the inspector; the
  machine proposes and the controller disposes, and no flag ever becomes an automatic steer (p4 D7).
  The visible distinction is a governed decision door, not a generic CRUD button.
- **Class:** repo contract `[M]`; composition `[P]`.

**Move 4 — Narration and verification are visibly different materials.**
- **Exemplar (`[X]`):** the evaluation loop `[cat:agent-ops/ao-eval]` (`tech-ops-eval-loop` 21,
  **agentops only**) documents a build → eval → patch loop.
- **What the exemplar does:** makes evaluation a distinct step that feeds back into work rather than
  treating the work product's assertion as its score.
- **What OURS does differently:** three visually distinct classes — **ADVISORY** (what the model
  claims), **MEASURED** (ledger events, tokens, timestamps, `test_runner`), **SOURCE** (the diff and
  committed tree) — where independent verification is the *only* place a "passed" mark is allowed, and
  a run cannot render "done" without the measured class. These paired marks are visible on the resting
  row before selection; a generic dashboard has no such authority boundary (`[M]`: `test_runner` is
  the sole source of `test_executed_success`).
- **Class:** repo contract `[M]`; composition `[P]`.

**Move 5 — Objects are addressed by a typed grammar on a persistent roster.**
- **Exemplar (`[X]`):** keyboard-first operation (`tech-int-keyboard-first` 6) plus the direct
  command-palette record (`tech-ia-command-palette` 1; `[cat:ia-layout/ia-command-palette]`).
  `fzf`, `k9s`, and Lazygit remain named exemplars, but the repaired direct command-palette evidence
  is one record, not a consensus count.
- **What the exemplar does:** lets an operator type to find/address an object and jump directly, with
  keyboard-first operation and no pointer required.
- **What OURS does differently:** every object carries a stable typed address — `run`, `phase`,
  `attempt`, `session`, `worktree`, `lease`, `flag`, `approval`, `record` — and the roster persists
  while an object is selected. The palette *accelerates* the roster; it is not the information
  architecture, because palette-over-boards is the generic dashboard idiom (p4 D8).
- **Class:** pattern `[X]`; composition `[P]`.

**Move 6 — Cost is attached to the attempt and lease, not promoted to a KPI board.**
- **Exemplar (`[X]`/`[M]`):** per-trace cost attribution `[cat:ia-layout/money-cost-attribution]`
  (`tech-money-cost-attribution` 4, **agentops only**); the repository admission/lease gate `[M]`.
- **What the exemplar does:** attributes spend to the session/run that incurred it.
- **What OURS does differently:** cost is a run facet — reserved vs settled, the `cost_source`
  class, hard-cap headroom, settlement status, and the rule that **an unknown cost is never drawn as
  zero**. `R3a` is a bounded constraint ledger, not a field of money cards; only an exception earns
  attention priority (`[P]` grouping; `[cat:ia-layout/ia-money-grouping]`).
- **Class:** repo contract `[M]`; pattern `[X]`; composition `[P]`.

**Move 7 — One selected evidence feed has follow/pause; the room is not a chart wall.**
- **Exemplar (`[X]`):** live-update semantics (`tech-int-live-follow` 10;
  `[cat:ia-layout/ia-attention-surface]`). The repaired taxonomy supports live/real-time update
  behavior, but `tech-viz-log-stream` is currently `[P]` and is not cited as external proof.
- **What the exemplar does:** distinguishes live change from ordinary content and gives the operator
  control over when urgent updates demand attention.
- **What OURS does differently:** exactly one selected attempt feed can follow or pause; it is bounded,
  aged, and carries the same ADVISORY/MEASURED classes as the row. No per-card sparkline or ambient
  chart can compete with the decision queue (p4 D9).
- **Class:** pattern `[X]`; composition `[P]`.

**Move 8 — Attention is a durable state machine over runs and control-plane health.**
- **Exemplar (`[X]`/`[P]`):** Linear Triage's new/active/snoozed/resolved state (direct check, p4);
  catalog `[cat:ia-layout/ia-attention-surface]` (`tech-trust-alerting` 6, **dashboards only**).
- **What the exemplar does:** gives an item a stable identity and a lifecycle rather than an ephemeral
  toast.
- **What OURS does differently:** attention is ranked by severity × actionability across *agent runs*
  and worker/projection health, with critical capacity reserved so a new run failure cannot be buried
  by a governance decision; announcements are transition-only, polite, and foreground-pull (no invented
  push channel). It is a work queue, not a row of red cards. The specific state machine and snooze
  semantics are `[P]`.
- **Class:** pattern `[X]`; composition `[P]`.

**Distinctiveness gate.** A move counts as distinctive only when all three fields are visible in the
design brief: (1) the named exemplar pattern, (2) the changed operator action for an agent run, and
(3) the screenshot carrier that lets a stranger recognize that change. The eight moves above satisfy
that gate. None is a KPI, peer board, chart default, or generic service-health substitution; each is
anchored in session identity, attempt/evidence authority, governed action, typed addressing, lease
cost, one selected feed, or durable run attention.

### 4.2 Recognizability test (blind, 10 seconds)

A stranger shown the **resting screenshot with no run selected and this document hidden** must be able
to say each of the following within ten seconds and point to the carrying pixels. The fixture contains
one waiting-for-approval session, one failed session, one running session, and a money-risk lease; it
must be rendered at 1440×900 and 390×844. The test does not allow the reviewer to open `R4`, hover a
tooltip, read explanatory prose, or infer meaning from color alone.

| # | The stranger says | Visible element that carries it |
|---|---|---|
| 1 | "These are AI agent sessions, not services." | The identity band on every actionable roster row: session/agent token + worktree/host target + current command/tool + provider×model + attempt (Move 1). |
| 2 | "That run is waiting on a person." | The `approve` eligibility token, `controller` authority marker, and waiting state are visible on the R2 row and mirrored in the ranked R1 decision item (Move 3). |
| 3 | "This is spend against a hard budget." | The R2 row's attached lease/cost band shows reserved vs settled, `cost_source`, and headroom; R3a repeats the money-risk exception, never as a free KPI card (Move 6). |
| 4 | "The agent claimed it passed, but that is not the verified result." | The same R2 row visibly pairs an ADVISORY claim mark with a MEASURED `test_runner` result mark; the full ladder is optional drill-down, not the carrier (Move 4). |
| 5 | "I can act from here, and it will be recorded." | The row's eligibility token is adjacent to a receipt-coverage token (`recorded`/`missing`); the preview opens from that token but recognition does not depend on R4 (Move 3). |

The stranger must identify all five statements and point to the correct carriers in both captures. A
generic observability comparator must fail at least statements 1, 4, and 5. Fewer than five correct
answers, any answer requiring selection/hover, or a comparator that passes all five is a design failure,
not a copy fix (p4 acceptance gate).

### 4.3 Removed — elements that could belong to a generic Grafana-style dashboard

The q0 support repair and the p4 design critique forced a second pass over the composition. These
elements are **removed** from the resting screen; each would let a reviewer mistake the product for a
generic observability tooling shell.

| Removed element | Reason |
|---|---|
| Fixed left navigation **rail** of peer destinations | The canonical ops-dashboard shell; replaced by a persistent roster plus deliberate lenses (p4 D1). |
| **Peer board / card grid** (Work · Money · Health · Decisions) | Fragments one run decision across places; no source states domain partitioning (`[E2]`, p4 D1). |
| **Top-row KPI stat tiles** | A dashboard glance idiom that displaces the roster; the roster *is* the glance. |
| **Per-card sparklines / microcharts** | No shared scale, so they cannot compare; removed for one-scale time-series (`[M6]`). |
| **Global truth footer** as the trust model | A footer cannot qualify a local value's source/scope/revision; provenance travels per value (p4 D4). |
| **Unconditional gauge / status-grid defaults** | Mark support is thin (gauge 1, heatmap 1); both are now `[P]` (`[E1]`, p4 D6). |
| **Colour-only status dots and repeated neon marks** | Fails non-colour status and reads as retro-ops costume (p4 D5/D9; §12.1). |
| **Decorative glow / pulse and uppercase telemetry texture** | Atmosphere, not information; the restraint budget (§4.5, p4 D9). |
| **Static topology / architecture SVG in the resting room** | Documentation theatre; live+scoped or a System/help link only (p4 D7). |
| **Command palette as primary navigation** | A palette accelerates a board; it cannot replace typed addressability (p4 D8, Move 5). |
| **Generic transcript + metadata sidebar** | A log viewer is not a causal explanation; replaced by the typed ladder (p4 D9, Move 2). |
| **Time-range picker as the primary control** | A charting idiom; run triage is ordered by attention, not by a date range. |
| **"Mission control" / flight-deck mood language** | A mood is not an identity and is the category default (p4 D5). |

### 4.4 Visual grammar for run / evidence / action (p4 D5)

Identity is carried by composition and mark semantics, not by tokens. The following treatments are
`[P]` (tokens, contrast, reduced motion and SVG technique remain hygiene, per §11–§12):

- **Run identity:** a left-anchored monospace identity band (session token, worktree path, current
  command) with no card border; density comes from alignment, not chrome.
- **Attempt boundary:** a hairline rule with attempt number, model, and timestamps; attempts stack in
  the ladder instead of becoming cards.
- **Agent-reported (ADVISORY):** a muted, quoted "said" treatment — never a pass mark.
- **Independently verified (MEASURED):** the test-runner glyph plus timestamp — the only permitted
  "passed" mark, always accompanied by its source and age.
- **Proposed vs authorized action:** a hollow/dashed "proposed by <authority>" affordance versus a
  solid affordance that names the acting controller, the epoch, and the receipt.
- **Lease / cost constraint:** a headroom bar attached to the run, not a free-floating chart.
- **Terminal target:** a monospace worktree/host token with a copy affordance, so the operator knows
  where the agent is actually writing.

### 4.5 Restraint budget (p4 D9)

To keep the identity from collapsing back into dashboard costume, the resting screen holds a budget:
no decorative glow or pulse; no uppercase telemetry texture used as decoration; no repeated bright
status marks; no default card field; no chart whose only purpose is atmosphere; no animation except
state transitions. Validation is a **blind A/B**: a reviewer compares the screen to a generic
observability dashboard and must locate the run/evidence/action distinction without prose.

**Thesis failure rule.** If the resting screenshot can be described as “truth bar + alert cards +
service table + KPI rail,” the thesis has failed even if all `ON-G1..G7` anchors are present. Kill the
following implementation elements before acceptance: lifecycle-first roster rows, money/health/fleet
KPI cards, generic red alert tiles, a transcript sidebar, and any selection-only evidence/action cue.
Replace them with the session identity band, attempt boundary, paired ADVISORY/MEASURED marks, lease
constraint attached to the row, and visible eligibility/receipt tokens. Those are the screenshot-level
carriers of the thesis, not prose or color tokens.

---

## 5. Why the room exists (measured problem statement)

This direction is motivated by r0's measured facts, not by a desire for a new skin. It must answer the
glance needs the audit found partial or absent (`[M]`; r0 §4, r1 §4.1):

- `ON-G1` up / connected — separate browser connection, control-plane health, dependency health and
  freshness, not one badge (`[M]`; r0 M2, A1).
- `ON-G2` running / queued / failed / live — the run roster, live state always visible (`[M]`; r0 M7).
- `ON-G3` failing / stalled / at risk — durable attention inbox items, not a count (`[M]`; r0 M2, A2).
- `ON-G4` money — **all five** labelled values (spend, burn, provider-window %, wallet headroom,
  reserved leases) at rest in `R3a`, plus a money-risk exception marker; the full ledger is the Money
  lens (`[M]`; r0 M1; canonical contract in `control_room_ia.md` §4).
- `ON-G5` decision needed — actionable decision objects (`[M]`; r0 M3, A3).
- `ON-G6` fresh / trustworthy — per-object truth + a compact global degraded summary (`[M]`; r0 M2,
  A10).
- `ON-G7` fleet shape — a **bounded** composition rollup at rest in `R3c` (model × condition ×
  provider × lifecycle); performance is a separate lens (`[M]`; r0 A6).
- Drill-down `ON-D1..D7` — one run, step by step, why flagged, safe action, route, cost-by-step, and
  background-session management, all from the run object (`[M]`; r0 §4).
- Alert `ON-A1..A6` — failure, unhealthy worker/projection, threshold, pending decision, flag,
  staleness, delivered in-room and retained (`[M]`; r0 A1–A5).

The full M1–M14 / A1–A12 disposition is retained in §13.

---

## 6. The generic grammar we reject (explicit r5 drops)

r6b found the r5 composition was a familiar observability dashboard (`rail → attention strip → domain
boards → cards → docked detail → truth footer`) and would read as Grafana/Datadog with different
tokens (`[D1]`). This rewrite drops the following r5 elements by name and reason:

| Dropped r5 element | Why it is dropped | Replacement |
|---|---|---|
| **"Instrument panel" / "premium flight deck"** as the product thesis or mood language | A mood is not an identity; the metaphor is the category default (`[D1]`, `[D5]`) | Run-first thesis (§1) |
| **Rail → attention strip → domain-board field → docked detail → footer** shell | The canonical ops-dashboard stack; a screenshot is indistinguishable after logo removal (`[D1]`) | Roster → evidence ladder → inline decision (§3) |
| **Four peer boards (Work / Money / Health / Decisions)** as primary IA | Fragments one run decision across five places; corpus never showed domain partitioning (`[D2]`, `[E2]`) | One run context + secondary lenses (`[P]`) |
| **Decoration-only attention strip** | An alert dump without state, ownership, or resolution (`[D3]`) | Stateful attention inbox (§3.3) |
| **Global truth footer as the trust model** | A footer cannot qualify which source/scope/revision a number has (`[D4]`) | Provenance travels with each value; only scope/connection/epoch/degraded stay global (§8) |
| **"One active board at a time"** | The operator loses the fleet while investigating one object (`[IA1]`) | Roster persists beside the inspector (§3.2) |
| **Unconditional chart defaults** (gauge, status grid, small multiples, timeline) | Mark-specific support was inflated or thin (`[D6]`, `[E1]`, `[E6]`) | Every chart states question/decision/baseline/fallback (§7); gauge, small multiples now `[P]` |
| **Per-card sparklines / microcharts** | No shared scale; cannot compare (`[M6]`) | One-scale time-series on the run/lens; SVG micro-visuals only as glyphs (§7) |
| **Static architecture/topology SVG in the resting room** | Documentation theater; consumes attention without answering "what is failing now" (`[D7]`, `[M]`) | Out of the resting room; live+scoped inspector or a System/help link (§10) |
| **Command palette as navigation** | A palette accelerates a visual board; it cannot replace addressability (`[D8]`) | Terminal grammar on a persistent roster; palette as accelerator (§3) |
| **Generic transcript-plus-sidebar detail** | A log viewer is not a causal explanation (`[D9]`) | Typed evidence ladder (§2.4) |
| **"Vanilla JS" as a design virtue** | No-build is a guardrail, not an aesthetic or proof about React (`[D10]`, `[E7]`) | No-build lives in implementation constraints (§12) |
| **Mobile as a stacked desktop wall** | A phone is not a narrower operations wall (`[D11]`) | Mobile is triage/inspection mode (§3.5) |
| **Alerting as a third disclosure depth** | Attention is an orthogonal lifecycle, not a deeper page (`[IA5]`) | Two axes: disclosure and attention (§9) |
| **"Interrupt"/notification language** | No delivery channel exists; promising one is dishonest (`[IA6]`) | Honest foreground pull + durable inbox (§3.3) |

---

## 7. Chart set (no unconditional defaults)

**Acceptance criterion:** no chart is a default (`[P]`; r6b D6, r6c IA14). Every accepted chart states
its operator question, the decision it changes, the comparison baseline and time scope, the data
completeness/sampling rule, its textual/table equivalent, its fallback for too-few/too-many
observations, and a performance + focus-preservation budget.

Initial implementation set (counts and tables before marks):

| Priority | Run question | Form | Grounding |
|---|---|---|---|
| 1 | What needs me now? | ranked run ledger: counts, rates, sortable table | `[X]` `tech-viz-data-table` 21; `[P]` virtualization |
| 2 | What happened in this run? | bounded causal timeline/waterfall, one question per step | `[X]` `tech-viz-waterfall-timeline` 3 (agentops only) |
| 3 | Cost/quality over time | line/area or sparkline on **one shared scale** | `[X]` `tech-viz-time-series-marks` 8; `tech-ops-metrics` 17 |
| 4 | Bounded quantity | text + progress; gauge only where a maximum exists | `[P]` `ch-gauge` (no direct support) |
| 5 | Live output | bounded selected-attempt feed with follow/pause/filter | `[P]` log-stream composition; `[X]` `tech-int-live-follow` 10 |

Deferred: small multiples `[P]` (no direct support) and threshold bands (no source) are not defaults; canvas
decimation only when a measured mark count requires it (`[X]` ECharts canvas-vs-SVG; `tech-viz-rendering-performance` 16).

---

## 8. Truth and provenance contract

One global footer cannot qualify local data (`[D4]`). Keep global only: scope, browser connection,
control epoch, and a compact degraded summary. Attach to **every consequential value** (`[M]` where a
repo contract exists, else `[P]`):

- source and projection (ledger, Redis, registry, browser state);
- observation time and age;
- scope, retained window, and truncation/partiality;
- revision or control epoch where applicable;
- measured / estimated / unknown / unmeasured semantics;
- a link to the event or record the value came from.

**Green never lies:** a stale or unmeasured subsystem must not render as healthy (`[M]`; r0 M2). The
`partial: True` cost contract and the `history_capped` marker are preserved (`[M]`). Refresh is split
by role — current control/attention always on; one live stream for the selected object; analytical
lenses poll while visible; historical views on demand with a marked age (`[M]`; r0 M8).

---

## 9. Glance / drill-down / alert contract

Disclosure and attention are separate axes (`[P]`; r6c IA5):

```text
Disclosure:  roster (fleet) -> selected run -> evidence detail
Attention:   observation -> state transition -> attention item -> resolution
```

- **Glance:** the resting roster + inbox + truth strip answer all of ON-G1..G7 without another board
  (canonical contract per `control_room_ia.md` §4).
- **Drill-down:** one selection opens the full run (identity → lifecycle → evidence → cost →
  decision → record) with no board hopping.
- **Alert:** durable inbox items, transition-only polite announcements; foreground pull-first, with an
  honest promise and no invented delivery channel (`[M]`; r0 M9; `[P]` `[IA6]`).

---

## 10. SVG set

- **Topology:** ship only if live, scoped, and actionable (highlight the selected run's dependencies,
  lag, and affected records); otherwise link the architecture docs from System/help. No static diagram
  in the resting room (`[P]`; r6b D7).
- **Micro-visuals:** sparkline, status glyph, and flow line as small SVG+CSS (path +
  `stroke-dasharray`/gradient), never a JS chart runtime for a 40px mark (`[X]`
  `[cat:svg-technique/svg-micro]`; `[P]` the no-runtime choice).
- **Authoring:** `viewBox` for scale; `currentColor`/custom properties for theming; real `<text>` for
  print/zoom; `<title>`/`<desc>` + role for informative SVGs; `aria-hidden` for decorative;
  forced-colors safe (`[X]` `[src:mdn-viewbox]` `[src:mdn-use]` `[src:mdn-forced-colors]`).

---

## 11. Motion budget

- Animate **state changes only**, short (roughly 100–240 ms) and decelerating (`[P]`).
- No entrance animation on poll, no layout-shifting motion, no decorative pulse; liveness is a
  labelled state and a settled timestamp (`[P]`; r6b D5).
- Honor `prefers-reduced-motion`: durations collapse, repeating animation stops, state stays conveyed
  by copy/icon/timestamp (`[X]` `[src:mdn-reduced-motion]`; `[P]`).
- Motion never competes with the 1 s tick / 5 s poll cadence (`[M]`).

---

## 12. Accessibility and no-regression constraints

### 12.1 Accessibility bar

- WCAG 2.2 AA contrast: ≥ 4.5:1 body, ≥ 3:1 large text (`[X]` `[src:wcag-contrast]`; `[P]`).
- Status is never colour-only: every lifecycle/attention state pairs colour with shape and a word
  (`[M]`; r0 §9.5).
- Tables use real focusable controls inside semantic cells; no `<tr role="button">` pseudo-buttons
  (`[M]`; r0 M10; `[X]` `[src:w3c-tables]`).
- One transition-only polite live region; ordinary metrics labelled, not announced (`[M]`; r0 M9).
- Modal/sheet surfaces: labelled dialog, focus trap, Escape, scrim dismissal, return focus (`[M]`).
- Forced-colors/high-contrast via system colors and `currentColor` (`[X]` `[src:mdn-forced-colors]`).
- Keyboard: addressable objects, typed search, visible focus, preserved selection, escape paths (`[X]`
  `[src:w3c-apg]`; `[P]`).

### 12.2 No-regression requirements (measured r0 §9)

1. Two-layer reconciliation: matrix snapshot owns retained telemetry; SSE overlays live samples;
   bounded replay with a `replay_complete` boundary and de-dup windows.
2. One selected event stream at a time.
3. Keyed, write-on-change lists; a no-op poll performs zero writes.
4. No HTML-string rendering; all content built with `element()`/`textContent`.
5. Two-axis status language (lifecycle vs supervisor attention); colour never alone.
6. Mutation trust boundary + idempotency on every non-GET, typed doors preserved.
7. Accessible chrome: `hidden` (not CSS-only) deactivation, focus traps, reduced motion.
8. No build step: six classic scripts in dependency order.

**Out of scope (guardrails).** No framework migration or build step; no new mutating route class or
automatic actuation; no new persistence plane or decorative poller; no invented telemetry
(per-cell model/condition/confidence/heartbeat/quality encoding only if the API later provides it)
(`[M]`; r0 §9, r6b D6).

---

## 13. r0 dispositions (retained)

### 13.1 Present but misplaced (M1–M14)

| # | Disposition in this direction |
|---|---|
| M1 | quota/wallet/leases become a run cost facet + the five-value `R3a` at rest (canonical contract) + the Money lens; grouping is `[P]` |
| M2 | projection health renders as per-object truth + global degraded summary |
| M3 | the control packet is the current-state authority (runs, approvals, promotable, failed, workers, lag, epoch, `safe_actions`) |
| M4 | registry lineage is reachable from the run/decision, not only a destination |
| M5 | docs health collapses to one process-health owner; warranted proposals become decisions |
| M6 | per-card sparklines removed; no replacement inherits the noise |
| M7 | `LIVE NOW` merged into the roster; live/change state always visible |
| M8 | hidden heavy lenses pause; current control/attention do not |
| M9 | rail mirrors labelled/readable, not live-announced |
| M10 | real controls inside table cells |
| M11 | reinterleave affordance with order/target preview, idempotency, receipt |
| M12 | recording coverage surfaces as process health; a missing record becomes an attention item |
| M13 | one canonical pipeline summary; no re-parenting |
| M14 | typed doors + safe-action validation and preview |

### 13.2 Absent (A1–A12)

| # | Disposition |
|---|---|
| A1 | stateful attention inbox (health aggregate + log) |
| A2 | projection/latency health with impact + local provenance |
| A3 | complete decision objects (approvals/promotable) + safe actions |
| A4 | worker health linked to affected runs |
| A5 | historical trends as a secondary lens tied to a decision and time scope |
| A6 | fleet composition/performance lens, separated |
| A7 | operator topology live+scoped or out of the rest view |
| A8 | object search + bounded event search |
| A9 | notifications deferred; honest foreground-only promise |
| A10 | per-object data age + global degraded summary |
| A11 | auth/multi-operator unchanged; actor identity + recording on actions `[P]` |
| A12 | mobile triage/inspection mode |

---

## 14. Acceptance checklist

The implementation is graded against these; each maps to a required disposition.

| # | Criterion | Source |
|---|---|---|
| 1 | The run is the default addressable object; `ON-G1..G7` answerable at rest per the §16 contract (desktop) | r6c IA1/IA2, r6b D1/D2, p5 IA1–IA4 |
| 2 | The run object renders all four facets (lifecycle, cost, evidence, decision) for the selected run | §2 |
| 3 | The control packet is the current-state authority with epoch and derived safe actions | r6c IA3 |
| 4 | Durable attention inbox with the field model and transition-only announcements | r6b D3, r6c IA4 |
| 5 | Disclosure and attention are separate axes | r6c IA5 |
| 6 | Truth travels with each consequential value; only scope/connection/epoch/degraded stay global | r6b D4, r6c IA7 |
| 7 | Refresh split by role; hidden heavy views pause, current state does not | r6c IA8 |
| 8 | Detail navigation contract (identity, persistence, focus return) | r6c IA10 |
| 9 | Evidence ladder separates narration, measurement, verification, lineage | r6b D9, r6c IA11 |
| 10 | All existing entry paths migrated (design, Claude, Flags, Routing, Registry, recording, queue) | r6c IA12 |
| 11 | Safe-action preview on every mutation; typed confirmation for irreversible acts | r6b D12, r6c IA9 |
| 12 | Mobile is triage/inspection mode | r6b D11, r6c IA16 |
| 13 | No unconditional chart defaults; every chart justified | r6b D6, r6c IA14 |
| 14 | Topology live+scoped or moved out | r6b D7 |
| 15 | Terminal grammar: object addressing, context, readonly, preview/apply, escape | r6b D8 |
| 16 | Truthful in-room alert language; no false interrupt promise | r6c IA6 |
| 17 | All no-regression guardrails hold | r0 §9 |
| 18 | Supports use q0 quoted, pattern-gated evidence; composition claims are `[P]`, never consensus | q0 crosswalk; p3 E1/E4 |
| 19 | Render gate: Playwright screenshots + size/overflow/aspect/contrast/first-paint/console checks pass at desktop **and** mobile, zero failures | campaign §a5; §18.1 |
| 20 | One-resting-screen glance check: every required `ON-G*` answer is visible at rest with no page/region scroll per breakpoint, and blind reviewers identify each answer | p5 IA8; §16, §18.2 |
| 21 | Recognizability test: a blind reviewer states all five §4.2 sentences in ten seconds and points to the carrying element | p4 acceptance gate; §4.2, §18.7 |
| 22 | Every p3/p4/p5 disposition is **CLOSED** with its fix, or **WAIVED** with a one-line reason; no `OPEN` or `SPECIFIED` state survives | p3 E1–E5, p4 D1–D9, p5 IA1–IA11; §17 |

---

## 15. Scope notes (direction line; no open blockers)

- **Implementation.** The facelift itself is a later phase; this document is the direction it executes,
  and §18 grades the result. It is not a condition on the brief.
- **Exemplar weakening.** After the q0 quoted-evidence repair the run-object pattern rests on small
  or single-family evidence in places (waterfall timeline 3, session grouping 7, eval loop 21 and cost
  attribution 4 are agentops-only; master–detail is now `[P]` with direct support 1). Component
  patterns are labelled `[X]` with the caveat; the composition stays `[P]` (§4.0). This is disclosed
  strength-of-evidence, not an open finding.
- **External notifications** are an explicit waiver (W1, §17): no delivery channel exists, so the
  in-room durable inbox is the whole promise (`[IA6]`).

---

## 16. The resting screen — the canonical glance contract (brief)

The IA contract now lives in `docs/research/control_room_ia.md` (q2 contract, tightened by the q5 IA
adversary). **That file's §4 is the only canonical `ON-G1..G7` list.** This section deliberately does
not repeat its breakpoint table or need mapping: a repeated table would become a second contract and
could drift. The earlier mobile `ON-G7` omission and narrow-desktop ticker fallback remain withdrawn.
The IA owns the per-need region, visible content, fold coordinates, vertical/horizontal/content budget,
and render-gate checks for 1440×900, 1024×768, and 390×844.

**Binding single-valued map (authoritative in IA §4; restated here only as a reference, never as a
second contract):** `ON-G1→R0`, `ON-G2→R2`, `ON-G3→R1`, `ON-G4→R3a`, `ON-G5→R1`, `ON-G6→R0`,
`ON-G7→R3c`. If this line and IA §4 ever disagree, IA §4 wins and this line is corrected.

**Binding requirements from the p4/p5 dispositions (detail in the IA doc):**

1. **Agent-native identity (D2).** Each actionable R2 row (or the roster header) must show
   session/agent id, worktree/terminal target, current command/tool, provider+model, and attempt.
2. **Reserved attention answers (IA6).** R1 reserves one risk/all-clear row and one
   decision/none-pending row, then ranks remaining capacity by severity × actionability. Neither
   canonical answer can be buried by the other class.
3. **Bounded composition (IA4/IA7).** R3c is a bounded set of marginals (capped groups with explicit
   `other`/`unknown`), never an unbounded cross-product, and it answers at mobile too.
4. **At-rest action eligibility (IA9/D7).** A row exposes compact eligibility
   (`observe`/`inspect`/`approve`/`promote`/`cancel`/`retire`/none); the full preview stays in R4.
5. **Tiered provenance (IA11/D6).** Glance shows state + age + one authority marker; full provenance
   and event links live in R4. `ON-G1` and `ON-G6` are complete in R0; local chips are mirrors only.
6. **Selected-state persistence (IA10).** One arrangement per breakpoint; every region promised to
   remain visible is tested (IA §3.3 / §10).
7. **Mechanical acceptance.** The IA §10 selector contract (`[data-region]`, `[data-answer]`,
   `[data-field]`) and the five geometry primitives are what the render gate implements; a passing
   screenshot must show all seven answers, not merely the region anchors.

## 17. Adversary dispositions (p3 entailment, p4 design, p5 IA)

All three repair2 adversaries re-ran against explicit pass conditions and returned **PASS**:
`control_room_repair2_entailment.md` (quoted, technique-stating evidence), `control_room_repair2_design.md`
(thesis/recognizability), and `control_room_repair2_ia.md` (canonical glance). Every one of the **25**
findings below is therefore **CLOSED** with the fix named; the former `SPECIFIED`/`OPEN` language is
retired. The brief is unconditional on all 25 items. The only non-requirements are the explicit
**waivers** at the end of this section, each with a one-line reason.

| ID | Severity | Required disposition | Status |
|---|---|---|---|
| E1 | BLOCKER | Rebuild the crosswalk from record-level direct evidence; regenerate taxonomy/catalogs/skills/direction/IA; downgrade moves that lose backing to `[P]`. | **CLOSED (q0 semantic crosswalk; §4 re-grounded)** |
| E2 | HIGH | Use the real `RunState` graph (or label the UX lifecycle `[P]` with a total mapping). | **CLOSED (brief §2.2)** |
| E3 | MEDIUM | Fix the narrow-desktop glance contract (minimum ticker schema or explicit narrowing). | **CLOSED (q2 IA §4: all seven answers at 1024×768; ticker withdrawn)** |
| E4 | MEDIUM | Enforce one-leaf-per-label, or document/test explicit many-to-many evidence roles. | **CLOSED (q0: one direct leaf per label, verified in build)** |
| E5 | MEDIUM | Normalize claim classes: `[M]` repo facts, `[X]` external, `[P]` placement/policy. | **CLOSED (brief §4.0; composition claims forced `[P]`)** |
| D1 | BLOCKER | Replace a primary structural axis with agent/run-native grammar; blind screenshot test vs a generic-dashboard comparator. | **CLOSED (brief §4: session-first moves + §4.3 removed list + blind comparator)** |
| D2 | BLOCKER | Make agent/session/worktree/current-command identity primary on the resting screen; define visible CLI address grammar. | **CLOSED** — §4.1 Move 1, §4.4 identity band, and IA §10.2 row-field schema/selectors make the identity band and typed grammar a render-gate requirement (q4 PASS). |
| D3 | HIGH | Specify measurable region budgets + breakpoints + ticker schema; test comprehension. | **CLOSED (q2 IA §3.2 pixel budget + §10 comprehension tests)** |
| D4 | HIGH | Separate "pattern exists" from "composition is distinctive"; keep composition `[P]`; re-ground after E1/E4. | **CLOSED (brief §4.0/§4.1; re-grounded to q0 supports)** |
| D5 | HIGH | Define a domain-specific visual grammar for run/evidence/action; tokens are hygiene. | **CLOSED (brief §4.4)** |
| D6 | MEDIUM-HIGH | Tier provenance; distinct channels for decisions/failures/advisories; scan-time test. | **CLOSED** — §4.1 Move 4, §8 per-region provenance inventory, and IA §10 G-4/G-13/B-10 enforce the ADVISORY/MEASURED/SOURCE channels and the scan path. |
| D7 | MEDIUM-HIGH | Surface action eligibility at rest without automatic actuation. | **CLOSED** — §4.1 Move 3, IA §2 reserved decision answer, and IA §10 eligibility enum make observe/inspect/approve/promote/cancel/retire/none a gated at-rest field. |
| D8 | MEDIUM | Name desktop/narrow/mobile contracts; five-capture blind screenshot set. | **CLOSED (brief §16)** |
| D9 | MEDIUM | Restraint budget + blind "generic dashboard vs Control Room" comparison. | **CLOSED (brief §4.5 + §4.3)** |
| IA1 | BLOCKER | One authoritative per-breakpoint contract across r1/p1/p2. | **CLOSED (q2 IA §4: one canonical `ON-G1..G7` list, both breakpoints)** |
| IA2 | BLOCKER | No required glance answer may depend on page/R3 scroll; complete ticker schema. | **CLOSED (q2 IA §3.2/§10: budgets + no-scroll primitives; ticker withdrawn)** |
| IA3 | CRITICAL | Guarantee the five `ON-G4` values at rest, or formally narrow r1. | **CLOSED (q2 IA §4: all five values at 1440×900 and 390×844)** |
| IA4 | CRITICAL | Bounded `ON-G7` rollup at rest, or formally move it out of the universal glance contract. | **CLOSED (q2 IA §4/T4: bounded `R3c` at both breakpoints; no mobile omission)** |
| IA5 | HIGH | One canonical answer per need; shared epoch/age for split summaries; remove duplicate writers. | **CLOSED (q5 IA §4/§8: complete single-region answers; mirrors omit `data-answer`)** |
| IA6 | HIGH | Global severity ranking or reserved critical capacity; saturated-inbox fixture. | **CLOSED (q2 IA §2: severity×actionability ranking + reserved slot; fixture F-1)** |
| IA7 | HIGH | Region dimensions, type floor, row caps, truncation, bounded cardinality. | **CLOSED (q2 IA §3.2 budget + §10 type floor/row caps + bounded `R3c`)** |
| IA8 | HIGH | Split acceptance into screenshot, blind comprehension, browser/a11y, and event/state tests. | **CLOSED (q2 IA §10: classes G/B/A/E with five geometry primitives)** |
| IA9 | MEDIUM-HIGH | Compact action eligibility at rest; full preview in R4. | **CLOSED (q5 IA §2: reserved R1 decision answer; R2 mirror is non-authoritative)** |
| IA10 | MEDIUM | One selected-state arrangement per breakpoint; test region persistence. | **CLOSED (q2 IA §3.3: fixed desktop/mobile selected-state; every region tested)** |
| IA11 | MEDIUM | Enumerate per-region provenance fields; align the acceptance test. | **CLOSED (q2 IA §8: per-region provenance inventory; `AC-7`/G-4 aligned)** |

**Ledger totals: 25 CLOSED, 0 WAIVED, 0 OPEN, 0 SPECIFIED.**

**Explicit waivers (the only non-requirements).** These are outside the 25-finding ledger; each is a
deliberate non-requirement, so the brief is unconditional on everything else:

| # | Waived item | One-line reason |
|---|---|---|
| W1 | External push/notification delivery (r1 alert channel) | No delivery channel exists; the durable in-room inbox with transition-only polite announcements is the entire promise (r6c IA6; §3.3). |
| W2 | Live-production data inside the render gate | The gate is deterministic fixture-driven by design, so it neither starts a deployment nor requires the glance endpoint to be running; production wiring is graded by the scope and acceptance criteria instead. |
| W3 | Per-projection rows for registry/ledger/chroma/neo4j at rest | `ON-G1`/`ON-G6` are complete in `R0`; `R3b` requires only the aggregate worst lag/age, and per-projector detail is drill-down by design (q5 IA). |
| W4 | Mobile `ON-G7` omission or narrow-desktop ticker | Both were withdrawn because they broke the single contract; keeping all seven answers at all three viewports is cheaper than a second fallback schema (p5 IA1/IA2/IA4). |

## 18. Facelift brief — acceptance criteria, render gate, and glance check

**Scope.** Re-compose and restyle `apps/control_room/static/`, plus one additive read-only glance
projection on the existing Control Room server if the current endpoints cannot supply the IA §10.6
fixture schema. No framework migration or build step; no new mutating route class or automatic
actuation; no new persistence plane or decorative poller; no invented telemetry (`[M]`; r0 §9,
§12.2). Every projected field must derive from the existing control packet/ledger sources.

**Acceptance criteria.**

1. **Render gate (three breakpoints).** A new `verify_control_room_rendering.py` (patterned on the
   website's `verify_svg_rendering.py`) serves the IA §10.6 fixtures, captures Playwright screenshots,
   and runs gate-style checks at **1440×900, 1024×768, and 390×844**, in dark, light, and forced-colors,
   against the IA §10 geometry/schema/parent-mapping/line-budget/contrast contract.
   **Zero failures at all three viewports**; per-viewport screenshots retained; no regressions against
   the current portal. The gate is deterministic and uses fixtures, not live production data (waiver W2).
2. **One-resting-screen glance check.** At **both** 1440×900 and 390×844 (and narrow desktop
   1024×768), all seven `ON-G1..G7` answer anchors are present, non-zero, and fully inside the initial
   viewport with no page scroll and no region scroll; the five geometry primitives and the §10
   selector map in `control_room_ia.md` are the implementation contract. Blind reviewers must identify
   each answer and the correct next action.
3. **Contrast.** WCAG 2.2 AA: ≥ 4.5:1 body text, ≥ 3:1 large text, in dark, light, and forced-colors
   (`[X]` `[src:wcag-contrast]` `[src:mdn-forced-colors]`).
4. **Accessibility bar.** §12.1 holds: non-colour status, semantic table controls, one transition-only
   live region, labelled dialogs with focus containment/return, keyboard operation.
5. **No regressions.** The eight measured guardrails in §12.2 hold, plus the control-packet authority,
   the mutation/idempotency boundary, keyed write-on-change rendering, and the no-build constraint.
6. **Adversary closure.** All 25 dispositions in §17 are **CLOSED** and the three repair2 adversaries
   returned PASS; only the explicit waivers W1–W4 are non-requirements. No `OPEN` or `SPECIFIED`
   disposition is carried into the facelift.
7. **Recognizability test.** A blind reviewer shown the **resting** full-screen desktop and mobile
   screenshots, with this document hidden and no run selected, states all five §4.2 sentences within
   ten seconds and can point to the visible element carrying each. Selection, hover, color-only cues,
   and explanatory prose are disallowed. A miss is a design failure, not a copy fix.

**Gate order.** p5 IA8 fixes the test classes: (1) screenshot geometry, (2) blind comprehension,
(3) browser/accessibility automation, (4) event/network/state. A pass requires all four; DOM presence
alone is not a pass. The §4.2 recognizability test is part of blind comprehension class (2).

## 19. Blockers and waivers carried into the facelift

**No open design blocker is carried into the facelift.** The three repair2 adversaries all returned
**PASS** — `control_room_repair2_entailment.md` (quoted evidence), `control_room_repair2_design.md`
(thesis/recognizability), and `control_room_repair2_ia.md` (canonical glance) — and the 25-item ledger
in §17 is fully **CLOSED**. The brief is unconditional except for the explicit waivers W1–W4.

- **E1/E4/E5 (entailment).** CLOSED by q0: quoted, pattern-gated, one-direct-leaf-per-label support with
  a build-time verifier and a regression test; §4/§7 use the repaired supports and keep composition `[P]`.
- **D1/D2/D3/D4/D5/D6/D7/D8/D9 (design + identity + provenance).** CLOSED by q4 and the IA: session-first
  moves, the §4.3 removed list, the §4.4 visual grammar, the §4.5 restraint/kill rule, the §4.2 resting
  recognizability test, the per-row identity/evidence/eligibility schema, and tiered provenance.
- **IA1–IA11 (canonical glance).** CLOSED by q2/q5: one authoritative single-valued contract, no split
  answers, no resting scroll, all seven answers above the fold at all three viewports, exact
  budgets/schemas/fixtures, and implementable render-gate checks (`control_room_ia.md` §3.2/§4/§10).
- **Implementation (not a design blocker).** The facelift (`a1`–`a7`) and
  `verify_control_room_rendering.py` are the graded work this brief specifies; they are acceptance
  criteria, not unresolved questions.
- **Explicit waivers only.** W1 external notifications; W2 live data in the render gate; W3
  per-projection rest rows; W4 mobile `ON-G7` omission / narrow-desktop ticker. Nothing else is waived.

---

## Appendix — sources cited

The appendix is the corpus provenance; full 64-character hashes and extracted text live in
`experiments/research/control_room/sources/` and `sources.jsonl`; facet records carry the same hash in
`corpus/*.jsonl`. Counts below are the p0-repaired direct-label supports.

| Tag | Family | sha256 (16) | URI |
|---|---|---|---|
| `[src:linear]` | dashboards | `eb0e0bc396ddd962` | https://linear.app/ |
| `[src:vercel]` | dashboards | `c26a33d2b08d2b60` | https://vercel.com/ |
| `[src:vercel-geist]` | dashboards | `74aeb67b13ba6192` | https://vercel.com/geist/colors |
| `[src:grafana]` | dashboards | `789c3cf84b24905d` | https://grafana.com/docs/grafana/latest/dashboards/ |
| `[src:datadog]` | dashboards | `10b7d1ed79891712` | https://docs.datadoghq.com/dashboards/ |
| `[src:sentry]` | dashboards | `78abfbfa297e2a6d` | https://docs.sentry.io/product/dashboards/ |
| `[src:railway]` | dashboards | `fb3d9950d9d1705b` | https://docs.railway.com/ |
| `[src:fly]` | dashboards | `302af27b202b0d9a` | https://fly.io/docs/ |
| `[src:supabase]` | dashboards | `a62f83704d3f940d` | https://supabase.com/docs |
| `[src:stripe]` | dashboards | `255311919f90098f` | https://stripe.com/docs |
| `[src:posthog]` | dashboards | `923433f300af8023` | https://posthog.com/docs/product-analytics |
| `[src:langfuse-obs]` | agentops | `0a1784a27f750267` | https://langfuse.com/docs/observability/overview |
| `[src:langfuse-cost]` | agentops | `245019da24ca609e` | https://langfuse.com/docs/analytics/overview |
| `[src:langfuse-scores]` | agentops | `4667e20442936138` | https://langfuse.com/docs/scores/overview |
| `[src:langsmith]` | agentops | `216cc0ec88b4a616` | https://docs.smith.langchain.com/ |
| `[src:langsmith-eval]` | agentops | `60381850f2ec94ec` | https://docs.smith.langchain.com/evaluation |
| `[src:braintrust]` | agentops | `943a46764e1dce65` | https://www.braintrust.dev/docs/guides/evals |
| `[src:helicone]` | agentops | `20ead7ec1d1155ef` | https://docs.helicone.ai/ |
| `[src:arize]` | agentops | `03f451e9e86f8ade` | https://docs.arize.com/phoenix |
| `[src:weave]` | agentops | `d08fed9663231367` | https://weave-docs.wandb.ai/guides/tools/playground |
| `[src:uplot]` | dataviz | `c3a34c9200af26ab` | https://github.com/leeoniya/uPlot |
| `[src:echarts]` | dataviz | `caa87df6c6cfc387` | https://echarts.apache.org/en/index.html |
| `[src:echarts-aria]` | dataviz | `dfb00439e589043e` | https://echarts.apache.org/handbook/en/best-practices/aria/ |
| `[src:echarts-canvas]` | dataviz | `f7498c71e2215e1a` | https://echarts.apache.org/handbook/en/best-practices/canvas-vs-svg/ |
| `[src:vega-lite]` | dataviz | `2064f3499486a4bb` | https://vega.github.io/vega-lite/ |
| `[src:d3]` | dataviz | `a2d77a5b707ffb7d` | https://d3js.org/ |
| `[src:nivo]` | dataviz | `7fbbcfe5789d6603` | https://nivo.rocks/line/ |
| `[src:tremor]` | dataviz | `ad8fe3598ecb31d8` | https://www.tremor.so/ |
| `[src:shadcn]` | dataviz | `b34430159fcfd06c` | https://ui.shadcn.com/charts |
| `[src:warp]` | cli | `b5c3555b32cf6350` | https://www.warp.dev/ |
| `[src:ghostty]` | cli | `c2dd13ab48151194` | https://ghostty.org/ |
| `[src:textual]` | cli | `5fe641dcb2a0ba93` | https://textual.textualize.io/ |
| `[src:nvitop]` | cli | `f0d68d37b1d8bc32` | https://github.com/XuehaiPan/nvitop |
| `[src:btop]` | cli | `f6d5e898349bb60c` | https://github.com/aristocratos/btop |
| `[src:fzf]` | cli | `69fcc77a700dd447` | https://github.com/junegunn/fzf |
| `[src:lazygit]` | cli | `bcba07779b22b8e0` | https://github.com/jesseduffield/lazygit |
| `[src:k9s]` | cli | `1a478e7877c824fe` | https://github.com/derailed/k9s |
| `[src:kitty]` | cli | `a3d50cc44562b66c` | https://sw.kovidgoyal.net/kitty/ |
| `[src:mdn-viewbox]` | craft | `c953bc2f52e375d0` | https://developer.mozilla.org/en-US/docs/Web/SVG/Attribute/viewBox |
| `[src:mdn-use]` | craft | `4ce5f6172aae264a` | https://developer.mozilla.org/en-US/docs/Web/SVG/Element/use |
| `[src:mdn-reduced-motion]` | craft | `e3fe57980976a907` | https://developer.mozilla.org/en-US/docs/Web/CSS/@media/prefers-reduced-motion |
| `[src:mdn-forced-colors]` | craft | `ebbddff1da6be245` | https://developer.mozilla.org/en-US/docs/Web/CSS/@media/forced-colors |
| `[src:mdn-custom-props]` | craft | `a91bb30d7c48d173` | https://developer.mozilla.org/en-US/docs/Web/CSS/Using_CSS_custom_properties |
| `[src:mdn-live-regions]` | craft | `11655ccb46931ebe` | https://developer.mozilla.org/en-US/docs/Web/Accessibility/ARIA/Guides/Live_regions |
| `[src:mdn-color-mix]` | craft | `3ab0045d33f37663` | https://developer.mozilla.org/en-US/docs/Web/CSS/color_value/color-mix |
| `[src:webdev-a11y]` | craft | `abe7da4e372ad808` | https://web.dev/learn/accessibility/ |
| `[src:webdev-design]` | craft | `64d16f4d7158c427` | https://web.dev/learn/design/ |
| `[src:webdev-contrast]` | craft | `aded09c8b9cfa9b7` | https://web.dev/articles/color-and-contrast-accessibility |
| `[src:webdev-reduced]` | craft | `00c6f4b49de13c1b` | https://web.dev/articles/prefers-reduced-motion |
| `[src:webdev-contentvis]` | craft | `7aa4893ce08fa550` | https://web.dev/articles/content-visibility |
| `[src:nng-tables]` | craft | `7bb44646100f45ed` | https://www.nngroup.com/articles/data-tables/ |
| `[src:nng-progressive]` | craft | `704fe924fed0ccae` | https://www.nngroup.com/articles/progressive-disclosure/ |
| `[src:nng-response]` | craft | `ffa84c46b1dc9665` | https://www.nngroup.com/articles/response-times-3-important-limits/ |
| `[src:nng-skeleton]` | craft | `ae670dfbb428a6ce` | https://www.nngroup.com/articles/skeleton-screens/ |
| `[src:nng-color]` | craft | `def697856da898b9` | https://www.nngroup.com/articles/color-enhance-design/ |
| `[src:nng-dark]` | craft | `effad3bad3f8f8d5` | https://www.nngroup.com/articles/dark-mode/ |
| `[src:nng-micro]` | craft | `e70316fbafc50556` | https://www.nngroup.com/articles/microinteractions/ |
| `[src:nng-icon]` | craft | `1d9e07b7547bfde0` | https://www.nngroup.com/articles/icon-usability/ |
| `[src:nng-dash]` | craft | `b665ad15d558dbd6` | https://www.nngroup.com/articles/dashboards-preattentive/ |
| `[src:refactoringui]` | craft | `d89a448704f5301e` | https://www.refactoringui.com/ |
| `[src:smashing-svg]` | craft | `b8bc0e988e39ee25` | https://www.smashingmagazine.com/2025/11/smashing-animations-part-6-svgs-css-custom-properties/ |
| `[src:smashing-aria]` | craft | `44d54c5850d776a2` | https://www.smashingmagazine.com/2025/06/what-i-wish-someone-told-me-aria/ |
| `[src:smashing-type]` | craft | `88846b6feced9773` | https://www.smashingmagazine.com/2023/10/choose-typefaces-fintech-products-guide-part1/ |
| `[src:smashing-tokens]` | craft | `5786269a0bca7790` | https://www.smashingmagazine.com/2024/05/naming-best-practices/ |
| `[src:cstricks-svg]` | craft | `45906cdcaa5d19ce` | https://css-tricks.com/mega-list-svg-information/ |
| `[src:cstricks-accessible]` | craft | `03dcc0382b1f0621` | https://css-tricks.com/accessible-svgs/ |
| `[src:cstricks-line]` | craft | `5b1adeb30b08f494` | https://css-tricks.com/svg-line-animation-works/ |
| `[src:svg-tutorial]` | craft | `ea201b4404388cbe` | https://svg-tutorial.com/ |
| `[src:wcag-quickref]` | craft | `ed61b139cdf28bff` | https://www.w3.org/WAI/WCAG22/quickref/ |
| `[src:wcag-contrast]` | craft | `3352aaf477e97391` | https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html |
| `[src:w3c-tables]` | craft | `627865eeda93dba0` | https://www.w3.org/WAI/tutorials/tables/ |
| `[src:w3c-apg]` | craft | `67aa84429d27fba3` | https://www.w3.org/WAI/ARIA/apg/patterns/ |
| `[src:inclusive-components]` | craft | `ac8dbab4744ac5bf` | https://inclusive-components.design/ |
| `[src:every-layout]` | craft | `4b5a5ab9eabd35d8` | https://every-layout.dev/ |
| `[src:josh-spring]` | craft | `71b1e7fa215f3d5a` | https://www.joshwcomeau.com/animation/a-friendly-introduction-to-spring-physics/ |
| `[src:butterick]` | craft | `ef40706eeb33417f` | https://practicaltypography.com/summary-of-key-rules.html |
