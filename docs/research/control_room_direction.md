---
status: accepted
---

# Control Room — direction: the live run as the unit of work (campaign `control_room_research_repair`, phase `p1_rework_direction`)

**Date:** 2026-09-11
**Supersedes:** the r5/r7 `control_room_direction.md` facelift brief (retained as the rejected
baseline; the specific drops are enumerated in §6).
**Inputs:** the measured baseline `docs/research/control_room_audit.md` (r0), the operator-needs
contract `docs/research/control_room_questions.md` (r1), the **repaired** taxonomy/catalogs/skills
`experiments/research/control_room/{taxonomy,catalogs,skills}.json` (p0), and the three adversary
passes r6a (`..._entailment.md`), r6b (`..._design.md`), r6c (`..._ia.md`).
**Repair status:** the p0 repair replaced every inflated support count with direct raw-label support;
`board-per-domain`, `source-provenance`, `degraded-banner`, `uncertainty-encoding`, `audit-trail`,
`budget-thresholds` and `quota-wallet` were deleted as unsupported, and ten catalog moves are now
explicit `[P]`. This direction cites only the repaired counts and marks every unsupported move `[P]`
(`docs/reviews/control_room_taxonomy_repair.md`).

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

The run state machine, aligned to the control db's enforced transitions and the packet's derivations
(`active_runs`, `awaiting_approvals`, `promotable_runs`, `failed_runs`; `[M]`):

```text
proposed -> queued -> leased -> running
    running -> { phase -> attempt }* -> awaiting-evidence
    awaiting-evidence -> verified | flagged
    verified -> awaiting-decision   (approve / promote / cancel / retire)
    awaiting-decision -> settled    (merged / archived / superseded)
    any -> failed | dead-letter     (terminal, keeps identity)
```

`phases_completed/phases_total`, `current_phase`, `changed-at`, and `attention state` are the
lifecycle facts shown per roster row (`[M]`; r6c). The room renders the database's state, never a
re-derived one: `safe_actions` come from the same transition graph the database enforces (`[M]`;
r0 M3, r6c IA3).

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
session→trace→span lineage from `tech-trust-causal-lineage` (18; agentops + dashboards) and
`tech-ops-trace-tree` (20); `[cat:agent-ops/ao-observability]` backs structured traces from
`tech-ops-observability` (18); `[cat:chart-selection/ch-timeline]` backs a run timeline from
`tech-viz-waterfall-timeline` (14, **agentops only** — single-family caveat). The corpus does **not**
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

RUN ROSTER  (default resting body — the fleet of live runs)
  run_id | spec/cell | current phase (n/total) | model×condition×policy
  lifecycle state | changed-at | cost provenance + reserved/settled | attention | decision?

SELECTED RUN / EVIDENCE LADDER  (docked inspector, one live stream)
  identity -> lifecycle -> evidence chain (typed) -> cost -> decision -> registry record

SAFE ACTION  (inline with the decision)
  target + epoch/revision + scope + budget effect + reversibility
  preview -> typed confirmation when required -> execute -> receipt

SECONDARY LENSES  (context, not mandatory hops)
  Money | Health/projections | Decisions/registry | Composition | History
```

### 3.1 The resting screen (no interaction)

The default body is the **run roster**, not a panel grid. It is a keyed, write-on-change list
(`[M]`) whose rows are runs/cells, ranked so that actionable state floats: pending decisions and
failures first, then running/queued, then settled. Each row carries enough run anatomy to decide
whether to open it: phase progress, lifecycle, cost provenance, attention, and whether a decision is
pending.

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
`[cat:ia-layout/ia-attention-surface]` from `tech-trust-alerting` (23, **dashboards only**). The
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

## 4. Distinctive moves and their provenance

This table is the (a) requirement: each move is either grounded in the repaired catalogs (with the
support count and family breadth) or marked `[P]`. Nothing here is presented as external consensus
unless the repaired evidence warrants it; single-family evidence carries its caveat.

| Distinctive move | Grounding | Class |
|---|---|---|
| Run roster as the default body, keyed and triage-ranked | resource-list/master-detail terminal exemplars: `[cat:ia-layout/ia-master-detail]` (`tech-ia-master-detail` 4, craft only); keyboard-first operation `[cat:ia-layout/ia-command-palette]` (`tech-int-keyboard-first` 22, 3 families) | `[X]` / `[P]` layout |
| Master–detail inspector while the roster stays visible | `tech-ia-master-detail` 4 (craft only) + `tech-ia-dashboard-layout` 43 (dashboards) | `[X]` (thin, single-family) |
| Causal evidence ladder (session→trace→span → attempt → commit → test) | `[cat:trust-attention/tr-lineage]` `tech-trust-causal-lineage` 18 + `tech-ops-trace-tree` 20; `[cat:agent-ops/ao-observability]` `tech-ops-observability` 18; `[cat:chart-selection/ch-timeline]` `tech-viz-waterfall-timeline` 14 (agentops only) | `[X]` (timeline single-family) |
| Narration ≠ independent verification | repository contract: `test_runner` is the sole source of `test_executed_success` | `[M]` |
| Eval loop (datasets→runs→scores→compare) attached to the run | `[cat:agent-ops/ao-eval]` `tech-ops-eval-loop` 24 (agentops only) | `[X]` |
| Session/run grouping across many sessions | `tech-ops-session-grouping` 14 (agentops only) | `[X]` |
| Prompt registry linked to runs | `[cat:agent-ops/ao-prompt]` `tech-ops-prompt-registry` 3 (agentops only, thin) | `[X]` (thin) |
| Bounded live log stream with follow/pause | `[cat:chart-selection/ch-log-stream]` `tech-viz-log-stream` 32 (4 families); `tech-int-live-follow` 22 (3 families) | `[X]` |
| Metrics/latency over time with one scale | `tech-ops-metrics` 34 (3 families); `[cat:chart-selection/ch-time-series]` `tech-viz-time-series-marks` 12 (2 families) | `[X]` |
| Cost attribution to the run | `[cat:ia-layout/money-cost-attribution]` `tech-money-cost-attribution` 13 (agentops only) | `[X]` (single-family) |
| Safe-action preview + typed confirmation | repository trust boundary `[M]`; k9s/Railway plan/apply `[X]` (r6b direct check) | `[M]` / `[X]` |
| Terminal grammar: keyboard addressing, visible context, readonly mode, escape | `tech-int-keyboard-first` 22; `[cat:ia-layout/ia-command-palette]` 11; CLI family (34) | `[X]` |
| Persisted density ladder without losing selection | `[cat:ia-layout/ia-density-ladder]` `tech-ia-density-ladder` 8 (3 families) | `[X]` |
| Token system + dark/light parity + forced-colors | `[cat:color-motion/cm-tokens]` `tech-vis-design-tokens` 29 (4 families); `cm-forced-colors` `tech-vis-forced-colors` 4 (craft only) | `[X]` |
| Status never colour-only | `[cat:color-motion/cm-status-color]` `tech-vis-colorblind-safe-status` 12 (3 families); `tech-int-aria-live` 4 | `[X]` |
| SVG micro-visuals (sparkline/status glyph) as SVG+CSS | `[cat:svg-technique/svg-micro]` `tech-svg-micro-visual` 17 (3 families) | `[X]` |
| Attention inbox with a state machine | `[cat:ia-layout/ia-attention-surface]` `tech-trust-alerting` 23 (dashboards only) + Linear Triage `[X]` | `[X]` + `[P]` |
| Domain-split boards (work/money/health/decisions) as primary IA | **no source states domain partitioning** (r3 support was inflated from generic dashboards) | `[P]` — demoted `[cat:ia-layout/ia-board-per-domain]` |
| Money grouping (spend/burn/quota/wallet/leases) on one board | **no source states quota/wallet/budget**; cost tracking is supported, the composition is not | `[P]` — `[cat:ia-layout/ia-money-grouping]` |
| Provenance badge (measured/estimated/unknown) | **no source states provenance**; grounded in the repo `cost_provenance` contract | `[P]` — `[cat:trust-attention/tr-provenance]` |
| Degraded banner naming the dependency | **no source states it**; grounded in the projection-watermark contract | `[P]` — `[cat:trust-attention/tr-degraded]` |
| Uncertainty / "unmeasured" encoding | **no source states it**; grounded in the `unknown` cost class | `[P]` — `[cat:trust-attention/tr-uncertainty]` |
| Freshness / retained-window marker | direct support 1 record | `[P]` — `[cat:trust-attention/tr-freshness]` |
| Actor audit trail | **no source states it** | `[P]` — `[cat:ia-layout/ia-audit-trail]` |
| Gauge mark for a bounded quantity | direct support 1 record | `[P]` — `[cat:chart-selection/ch-gauge]` |
| Small multiples | direct support 2 records | `[P]` — `[cat:chart-selection/ch-small-multiples]` |
| Virtualized-table rendering | direct support 3 records; the general table surface is supported (`tech-viz-data-table` 32) | `[P]` |
| Flow-diagram topology | direct support 2 records; the path tracer craft is supported | `[P]` — `[cat:svg-technique/svg-flow]` |
| No-build / "React is unnecessary" | r0 §9.8 local guardrail; the corpus shows viable alternatives, not necessity | `[P]` `[E7]` |

---

## 5. Why the room exists (measured problem statement)

This direction is motivated by r0's measured facts, not by a desire for a new skin. It must answer the
glance needs the audit found partial or absent (`[M]`; r0 §4, r1 §4.1):

- `ON-G1` up / connected — separate browser connection, control-plane health, dependency health and
  freshness, not one badge (`[M]`; r0 M2, A1).
- `ON-G2` running / queued / failed / live — the run roster, live state always visible (`[M]`; r0 M7).
- `ON-G3` failing / stalled / at risk — durable attention inbox items, not a count (`[M]`; r0 M2, A2).
- `ON-G4` money — a money-risk exception at rest; full spend/burn/windows/wallet/leases in the run
  context and the Money lens (`[M]`; r0 M1).
- `ON-G5` decision needed — actionable decision objects (`[M]`; r0 M3, A3).
- `ON-G6` fresh / trustworthy — per-object truth + a compact global degraded summary (`[M]`; r0 M2,
  A10).
- `ON-G7` fleet shape — a secondary composition lens, performance separated (`[M]`; r0 A6).
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
| 1 | What needs me now? | ranked run roster: counts, rates, sortable table | `[X]` `tech-viz-data-table` 32; `[P]` virtualization |
| 2 | What happened in this run? | bounded causal timeline/waterfall, one question per step | `[X]` `tech-viz-waterfall-timeline` 14 (agentops only) |
| 3 | Cost/quality over time | line/area or sparkline on **one shared scale** | `[X]` `tech-viz-time-series-marks` 12; `tech-ops-metrics` 34 |
| 4 | Bounded quantity | text + progress; gauge only where a maximum exists | `[P]` `ch-gauge` (direct support 1) |
| 5 | Live output | bounded log stream with follow/pause/filter | `[X]` `tech-viz-log-stream` 32 |

Deferred: small multiples `[P]` (2 records) and threshold bands (thin) are not defaults; canvas
decimation only when a measured mark count requires it (`[X]` ECharts canvas-vs-SVG; `tech-viz-rendering-performance` 17).

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

- **Glance:** the resting roster + inbox + truth strip answer ON-G1..G6 without another board.
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
| M1 | quota/wallet/leases become a run cost facet + a Money lens; money-risk exception at rest `[P]` grouping |
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
| 1 | The run is the default addressable object; ON-G1..G6 answerable at rest without board hopping | r6c IA1/IA2, r6b D1/D2 |
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
| 18 | Inflated support claims are `[P]`/`[X]` after the p0 repair; no consensus claims | r6a E1–E8 |

---

## 15. Open items

- **Implementation.** The facelift itself is a later phase; this document is the direction it executes.
- **Exemplar weakening.** The run-object pattern rests on thin/single-family evidence in places
  (master–detail 4 craft-only; waterfall timeline / session grouping / eval loop / cost attribution
  agentops-only; prompt registry 3). Those moves are labelled `[X]` with the caveat, not consensus.
- **Deferred external notifications** remain a named decision, not a silent promise (`[IA6]`).

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
