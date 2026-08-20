---
status: accepted
supersedes: BLUEPRINT.md, BLUEPRINT_v2.md, BLUEPRINT_v3.md, dated handoffs, superseded reviews (see §6)
---

# ARCHITECTURE.md — the single architectural authority

This document is the one current architectural authority for the repository (critique rec 4,
`docs/review/semantic_monolith_review.md` §"The nine recommendations"). It answers, in order: the
planes, the package boundaries, the dependency direction, implemented vs proposed, the canonical
execution loop, and which documents supersede which. Detailed designs live under
`docs/designs/{current,implemented}` and `docs/archive/`; this file is the map, not the design.

**Provenance:** [C] computed from the current tree; [M] measured ground truth; [X] the critique
(`docs/review/semantic_monolith_review.md`); [P] policy/prior (invariants). Where a claim is
internal it carries a `file:line`; where it derives from the critique it names the recommendation.

---

## 1. Planes — eight bounded packages

The repository's single semantic monolith (`src/instrument/` means "almost everything" — critique
finding 1) is partitioned into eight bounded planes. A module's plane is the conceptual system it
serves (critique §"What the repository actually contains (six systems)"), not its current directory.
The physical move into `src/agentic_dynamics/<plane>/` is Stage 1 (`docs/consolidation/stage_map.md`
§4 Stage 1); the full 64-module disposition is `docs/consolidation/design.md` §1.1.

| Plane | One-line ownership | Six-system map |
|---|---|---|
| `core` | Foundation shared by all planes — language profiling, paths, session vocabulary, subprocess streaming; imports only the standard library. | (foundation, not a system) |
| `experiment` | The experiment platform's contract + engine — `ExperimentSpec`, the `requires`/`produces` gate, spec → DAG compilation, the derived spec-lifecycle index. | System 2 — experiment platform |
| `measurement` | The measurement apparatus — perturbation operators, solution/basin/cost/recovery evaluation, entropy, static analysis, codebase graphs. | System 1 — measurement apparatus |
| `runtime` | The agent execution runtime — workflow runner, independent test runner, story orchestrator, post-hoc job transport. | System 3 — execution runtime |
| `adapters` | Model backends — OpenCode and Claude CLI drivers, and the model→backend router. | System 3 — execution runtime |
| `knowledge` | Knowledge + augmentation — identity/authority contract, the nine ingestion producers, retrieval, prompt construction, the RAG seam. | System 4 — knowledge & augmentation |
| `control` | The emerging control system — routing, signal store, supervisor, telemetry, queue steering, observation/actuation ingestion. | System 5 — emerging control |
| `reporting` | Research + publication output — game reports, the LLM review pool, meta-analysis. | System 6 — research & publication |

**System 6 completes with `apps/`** (`apps/{website,control-room}`, moved in Stage 5 — `stage_map.md`
§4 Stage 5): the publication/consumption surface that composes the planes but contains no domain
rules. `apps/` is the ninth top-level unit but is *not* a Python package plane — it is the
application tier at the top of the dependency spine (§3).

The current physical reality: all eight planes still live flat in `src/instrument/` (64 modules —
`docs/consolidation/design.md` §0). The planes above are the *target* boundary; Stage 1 realizes it
and `src/instrument/` becomes a transient compatibility shim (`design.md` §1.2).

---

## 2. Package boundaries — what each plane may and may not import

Boundaries are enforced by a dependency-direction lint, `tests/test_dependency_direction.py`
(added in Stage 1 — `design.md` §1.4), not by prose convention. The tier map is descriptive; the
forbidden edges are the executable rules.

**Tier map** (`design.md` §1.4):

| Tier | Planes |
|---|---|
| 0 — `core` | `language`, `paths`, `session_types`, `streaming` |
| 1 — `planes` | `experiment`, `measurement`, `runtime`, `adapters`, `knowledge`, `reporting` |
| 2 — `control` | `control` |
| 3 — `apps` | `apps/` (outside `src/agentic_dynamics/`, still linted) |

**Forbidden edges** (rec 8, verbatim in `docs/review/semantic_monolith_review.md`):

1. `core` imports nothing from tier ≥ 1 — only stdlib/third-party + core siblings.
2. `measurement` does not import `control`.
3. `knowledge` does not import `control` (knowledge does not actuate).
4. `experiment` does not import `control` (the platform defines; control consumes).
5. `reporting` does not import `control` (output does not steer).
6. `control` does not import `apps`; nothing below tier 3 imports `apps`.
7. `control` does not import `knowledge.retrieval` or `knowledge.prompt_constructor` (control
   consumes facts, not arbitrary retrieved text).
8. `apps` contain no domain rules — no `ExperimentSpec(`/`RuleSpec(`/`Factor(` construction in
   `apps/**` (AST-marker scan).

Two legitimate execution→control *observation* edges are pinned as positive assertions (below, §3);
every other tier-1→tier-2 edge fails the lint. Companion data-flow tests assert `retrieve()` never
returns an `authority==POLICY` candidate and references `publish_event` zero times, and that
knowledge modules never call `derive_actuation_record` (`design.md` §1.4).

---

## 3. Dependency direction — the spine

```
        ┌───────────────────────────────────────────────────────────┐
        │   core                                                   │
        │   ▲                                                      │
        │   │ experiment · measurement · runtime · knowledge        │
        │   │        · adapters · reporting   ▲                    │
        │   │                                 │ (observe-only)      │
        │   │                                 │                     │
        │   └─── control ──────────────────────┤                     │
        │        ▲                            │                     │
        └────────┼────────────────────────────┼─────────────────────┘
                 │                            │
            applications (apps/)  ◄────────────┘
```

Reading bottom-up, the spine is:

```
core ← experiment / measurement / runtime / knowledge ← control ← applications
```

`core` is imported by everything; the planes import `core` and each other only within their tier;
`control` consumes the planes and `core`; `applications` compose everything and are imported by
nothing. This is the directional graph of rec 8 (`semantic_monolith_review.md` recommendation 8).

The two **pinned execution→control observation edges** — the only tier-1→tier-2 imports, asserted
as the *complete* set by the lint (`design.md` §1.4) — are drawn as dashed, observe-only arrows:

```
runtime.workflow_runner ─ ─ ▶ control.step_routing, control.live     (execution consults the
                                                                    per-step router + publishes
                                                                    telemetry)
adapters.opencode ─ ─ ─ ─ ▶ control.live                            (adapters publish telemetry)
adapters.claude_adapter ─ ─▶ control.live
```

These are the supervisor design's "observe, never steer" seam made structural: **telemetry up,
decisions down.** The execution tier publishes observation into `control` (telemetry, the per-step
router); it never receives steering back through the same edge. `workflow_runner` importing
`step_routing` and `live`, and `opencode`/`claude_adapter` importing `live`, are the confirmed
cross-plane edges today (`docs/consolidation/design.md` §0) and are pinned — not blanket-rejected.

---

## 4. Implemented vs proposed

### Shipped today (real code, `src/instrument/` until Stage 1 moves it)

- **Execution core** — `perturb.py → backends.py → opencode.py / claude_adapter.py → [LLM] →
  trajectory`, then `solution.py + basin.py + efficiency.py + recovery.py → strategy.py →
  game_report.py` (`.opencode/instructions/mental-model.md` "linear core").
- **Story / mutation / review / graph / diagnostics** — multi-session orchestration, mutation
  compilation, commit analysis, entropy, codebase graph, LSP diagnostics.
- **Routing** — per-task model recommendation + strategy simulation (`routing.py`,
  `step_routing.py`).
- **Runtime RAG / Knowledge Base** — merged (`knowledge.py`/`retrieval.py`/`prompt_constructor.py`/
  `knowledge_stream.py`), wired into `run_workflow()` as `rag_augment`, default OFF.
- **Spec/compiler** — `experiment_spec.py` + `compile_experiment.py` (both written), the
  `requires`/`produces` gate, `spec_status.py`.
- **Supervisor + workflow runner + test runner** — `supervisor.py` (observe-only), `workflow_runner.py`
  (phase execution in a worktree), `test_runner.py` (sole source of `test_executed_success`).

### Reserved-but-empty — the Context Abstraction Plane homes (CAP I0–I7)

The CAP design (`docs/context_abstraction/design.md` §9) is **frozen** by this release
(`stage_map.md` §6): its implementation pauses until consolidation S6, but its structural homes are
declared here so post-consolidation implementation is **drop-in**. Each reserved home is an empty
placeholder (module docstring + `# reserved for CAP I<n>`):

| CAP increment | Component | Reserved home (`src/agentic_dynamics/`) |
|---|---|---|
| I0 | Fact schema + predicate registry (`CanonicalFact`, `FACT_PREDICATES`, `EPISTEMIC_MAP`, `verify_chain`) | `control/facts.py` |
| I1 | `spec_status/v1` reducer | `control/reducers/` |
| I2 | Ledger reducers (`attempt_facts/v1`, `job_facts/v1`) | `control/reducers/` |
| I3 | Workflow reducer (`workflow_facts/v1`, `policy_facts/v1`) | `control/reducers/` |
| I4 | Context Compiler (read-only) | `control/context_compiler.py` |
| I5 | Fact contracts in the spec gate (`FactRequirement`, `validate_fact_contracts`) | `core/contracts.py` |
| I6 | Controller + validator, shadow mode | `control/rules.py` + `control/validator.py` + `control/decisions.py` |
| I7 | Apply `route` for one opted-in spec | `control/` (seam in `run_workflow`) |

These are the exact reserved homes of `stage_map.md` §6 ("Reserved package homes"). The dependency
lint permits `control` to import `core` and `knowledge` — but nothing imports `control` except the
reserved seam (§3), consistent with "control consumes facts" (rec 8).

### Deferred workstreams — WS-02..08

Seven functional workstreams from `docs/refactor/plan.md` are **deferred, not cancelled**: they
resume post-consolidation as standalone specs running *inside* the new structure. Disposition per
`stage_map.md` §5:

| WS | Disposition | Resumes in |
|---|---|---|
| WS-02 KB branch integration | DEFERRED | `knowledge/` |
| WS-03 KB write-path | DEFERRED | `knowledge/` |
| WS-04 lab book registry repoint | DEFERRED (guard-test pattern promoted to S2/S6) | `reporting/` |
| WS-05 compiler matrix wire | DEFERRED | `experiment/` + `control/` |
| WS-06 compiler compare/evaluate | DEFERRED | post-consolidation |
| WS-07 compiler adapt/campaign | DEFERRED | post-consolidation |
| WS-08 admin step_sample | DEFERRED | `apps/control-room` |

(Folded, not deferred: WS-01 → S1 `retire_shim`, WS-09 → S3 retire `review_worker.py`, WS-10 →
S1 sys.path + S3 archive; WS-10's doc-drift half is retired — superseded by this file + Stage 4's
regenerated instruction surfaces. `stage_map.md` §5.)

### The release plan

This consolidation is staged by **`docs/consolidation/stage_map.md`** — the dependency-ordered
release plan (S0 → S1 → S2 → S3 → S4/S5 → S6). Stage 0 (this file + doc lifecycle + CAP freeze)
is the baseline; every later stage consumes this file's plane/boundary definitions.

---

## 5. The canonical execution loop

The repository is an **information-acquisition machine for AI economics** — controlled trials →
raw events → information → policy → grid → campaign → repeat. The canonical loop
(`.opencode/instructions/mental-model.md`):

```
  spec (ExperimentSpec) ──compile──▶ DAG ──▶ cells (factor cross-product) ──▶ jobs ──▶ attempts
        ▲                                  │                                            │
        │                                  │                                            ▼
        └──adapt (tweak one factor)── compare ◀── information ◀── measure ◀── ledger (events)
```

Written linearly: **spec → compile → DAG → cells → jobs → attempts → ledger → information → policy
→ grid → campaign.** The compiler generalizes today's linear execution core (the reuse map in
`mental-model.md`); `adapt` is the campaign loop that tweaks one factor at a time.

---

## 6. Supersession map — what this file replaces, and what stays

**This file replaces (moved to `docs/archive/`, `status: superseded`, `superseded_by:
ARCHITECTURE.md`):**

| Replaced | Reason |
|---|---|
| `BLUEPRINT.md`, `BLUEPRINT_v2.md`, `BLUEPRINT_v3.md` | Three generations of the architecture stored in prose (critique finding 4). This file is the single map. |
| `docs/HANDOFF_2026-08-17.md`, `docs/HANDOFF_2026-08-19.md` | Dated handoffs; the current state is this file + `stage_map.md`. |
| dated `code_reviews/*` predating the registry repoint | Superseded reviews (kept in `docs/archive/`, not deleted). |

**These remain authoritative (not replaced):**

| Document | Role |
|---|---|
| `.opencode/instructions/mental-model.md` | The file map, signatures, and dependencies — the operational reference, not the architectural authority. |
| `src/instrument/CONTEXT.md` | The instrument module reference (operator/metric authoring, the merged KB). |
| `scripts/CONTEXT.md` | The per-script reference (the authoritative script table). |
| `docs/data_integrity_findings.md` | The data-integrity boundary (no `_results_summary.json` resurrection). |
| `docs/review/` | The review directory — including the critique this file answers (`semantic_monolith_review.md`). |
| `docs/consolidation/{stage_map,design}.md` | The release plan + per-stage design this file is one output of. |

---

## 7. The architectural invariant — the load-bearing rule

> **To make policies, we need information.**

```
instrument (ledger) → derive (measurement rules → information)
  → write policy (control rules consuming that information)
  → grid (policy as an arm) → campaign (tweak one variable, repeat)
```

`RuleSpec` declares `requires` (the information a rule CONSUMES) and `produces` (the information it
EMITS). The validator refuses a control rule whose `requires` are unsatisfied:

```
ERROR: policy arm "dynamics" requires [confidence, first_pass, deadline_slack]
       — not produced by the ledger or any rule in this spec. Instrument these first.
```

The rule is **untouchable** and restated here, not redefined (`stage_map.md` §1; this file's
hard-rule (5)). Consequence for ordering: instrument `confidence` (for `model_cascade`/`dynamics`),
`perturbation_strength` + `test_executed_success` (for `grit`), and the attempt/timestamp +
`answer`/`explanation` token split *before* authoring the control arms that consume them — those
fields are now MEASURED (`mental-model.md` "Ledger"). Every stage of this consolidation, and every
post-consolidation CAP increment, is gated by this invariant.
