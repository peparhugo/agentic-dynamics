---
status: accepted
supersedes: BLUEPRINT.md, BLUEPRINT_v2.md, BLUEPRINT_v3.md, dated handoffs, superseded reviews (see §8)
---

# ARCHITECTURE.md — the single architectural authority

This document is the one current architectural authority for the repository (critique rec 4,
`docs/reviews/semantic_monolith_review.md` §"The nine recommendations"). It answers, in order: the
planes, the package boundaries, the dependency direction, implemented vs proposed, the canonical
execution loop, and which documents supersede which. Detailed designs live under
`docs/designs/{current,implemented}` and `docs/archive/`; this file is the map, not the design.

**Provenance:** [C] computed from the current tree; [M] measured ground truth; [X] the critique
(`docs/reviews/semantic_monolith_review.md`); [P] policy/prior (invariants). Where a claim is
internal it carries a `file:line`; where it derives from the critique it names the recommendation.

---

## 1. Planes — eight bounded packages

The repository's single semantic monolith (the old `src/instrument/` — "almost everything" —
critique finding 1) is partitioned into eight bounded planes, realized as
`src/agentic_dynamics/<plane>/` (Stage 1, `docs/release/consolidation/stage_map.md` §4). A module's plane
is the conceptual system it serves (critique §"What the repository actually contains (six
systems)"), not its former directory. The full 64-module disposition — executed, with the
transient `instrument.*` compatibility shim retired at the end of Stage 1 — is
`docs/release/consolidation/design.md` §1.1.

| Plane | One-line ownership | Six-system map |
|---|---|---|
| `core` | Foundation shared by all planes — language profiling, paths, session vocabulary, subprocess streaming; imports only the standard library. | (foundation, not a system) |
| `experiment` | The experiment platform's contract + engine — `ExperimentSpec`, the `requires`/`produces` gate, spec → DAG compilation, the derived spec-lifecycle index. | System 2 — experiment platform |
| `measurement` | The measurement apparatus — perturbation operators, solution/basin/cost/recovery evaluation, entropy, static analysis, codebase graphs. | System 1 — measurement apparatus |
| `runtime` | The agent execution runtime — workflow runner, independent test runner, story orchestrator, post-hoc job transport. | System 3 — execution runtime |
| `adapters` | Model backends — OpenCode and Claude CLI drivers, and the model→backend router. | System 3 — execution runtime |
| `knowledge` | Knowledge + augmentation — identity/authority contract, the nine ingestion producers, retrieval, prompt construction, the RAG seam. | System 4 — knowledge & augmentation |
| `control` | The implemented control plane — fact plane + reducers, context compiler, shadow-mode controller/validator, routing, supervisor, telemetry, queue steering, observation/actuation ingestion. | System 5 — control |
| `reporting` | Research + publication output — game reports, the LLM review pool, meta-analysis. | System 6 — research & publication |

**System 6 completes with `apps/`** (`apps/{website,control-room}`, moved in Stage 5 — `stage_map.md`
§4 Stage 5): the publication/consumption surface that composes the planes but contains no domain
rules. `apps/` is the ninth top-level unit but is *not* a Python package plane — it is the
application tier at the top of the dependency spine (§3).

[C] The physical reality today: all eight planes live in `src/agentic_dynamics/<plane>/` — 107
tracked Python modules at the pinned SHA `806c0d344831ec32abfdc15d37b8a4a4175ca63a`
(`git ls-files 'src/agentic_dynamics/**/*.py' | wc -l`, measured 2026-09-01) — plus the
`agentic-dynamics` CLI; [P] the deprecated five were retired in Stage 1 — see
`docs/release/consolidation/design.md` §1.1's `legacy/` rows. [P] `src/instrument/` no longer exists; its
compatibility shim was deleted once every consumer had been rewritten (Stage 1, phase E).

---

## 2. Package boundaries — what each plane may and may not import

Boundaries are enforced by a dependency-direction lint, `tests/test_dependency_direction.py`
(`design.md` §1.4), not by prose convention. The tier map is descriptive; the
forbidden edges are the executable rules.

**Tier map** (`design.md` §1.4):

| Tier | Planes |
|---|---|
| 0 — `core` | `language`, `paths`, `session_types`, `streaming` |
| 1 — `planes` | `experiment`, `measurement`, `runtime`, `adapters`, `knowledge`, `reporting` |
| 2 — `control` | `control` |
| 3 — `apps` | `apps/` (outside `src/agentic_dynamics/`, still linted) |

**Forbidden edges** (rec 8, verbatim in `docs/reviews/semantic_monolith_review.md`):

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

Two legitimate adapter→control *telemetry* edges are pinned as positive assertions (below, §3);
runtime's routing *decision* and telemetry are dependency-inverted onto runtime-owned protocols
(refactor-repair Debt-2), so every other tier-1→tier-2 edge fails the lint. Companion data-flow
tests assert `retrieve()` never returns an `authority==POLICY` candidate and references
`publish_event` zero times, and that knowledge modules never call `derive_actuation_record`
(`design.md` §1.4).

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

[M] Reading bottom-up, the spine is:

```
core ← experiment / measurement / runtime / adapters / knowledge / reporting ← control ← applications
```

— the lint's tier model (`tests/test_dependency_direction.py:9-15,35-51`) plus each plane's
`__init__.py` import map (`src/agentic_dynamics/{core,experiment,measurement,runtime,adapters,knowledge,control,reporting}/__init__.py:1`).

[M] `core` is imported by everything; the planes import `core` and each other only within their tier;
`control` consumes the planes and `core`; `applications` compose everything and are imported by
nothing — the lint's forbidden-edge assertions walk the full import graph and measure exactly this
(`tests/test_dependency_direction.py:187-193`). [X] This is the directional graph of rec 8 (`semantic_monolith_review.md` recommendation 8).

The two **pinned adapter→control telemetry edges** — the only tier-1→tier-2 imports, asserted
as the *complete* set by the lint (`tests/test_dependency_direction.py`) — are drawn as dashed,
observe-only arrows:

```
adapters.opencode ─ ─ ─ ─ ▶ control.live                            (adapters publish telemetry)
adapters.claude_adapter ─ ─▶ control.live
```

These are the supervisor design's "observe, never steer" seam made structural: **telemetry up,
decisions down.** The runtime's routing *decision* is dependency-inverted (refactor-repair
Debt-2): `runtime.workflow_runner` consumes the runtime-owned `Router` and `TelemetryPublisher`
protocols (`runtime/routing.py`, `runtime/telemetry.py`) and the control implementations
(`control.step_routing.route_step`, `control.live.LivePublisher`) are injected at the composition
root (`scripts/run_workflow.py`) — so `runtime` never imports `control`. The two adapters still
publish telemetry directly, which is the only remaining cross-plane edge and is pinned, not
blanket-rejected.

---

## 4. Implemented vs proposed

### Shipped today (real code, all under `src/agentic_dynamics/` since Stage 1)

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

### The Context Abstraction Plane — implementation-status map (CAP I0–I10)

[P] The CAP design (`docs/architecture/current/context_abstraction_design.md:1-13`) is **frozen** — the design
doc is the commitment and is never revised here. [C] This section is the CURRENT map: every increment
I0–I7 plus the addenda (I9 `pattern/v1`, typed checkpoints, the fact auto-emit hook) is
**implemented** and under `src/agentic_dynamics/control/` (+ `core/contracts.py` for the spec-gate
increment) — the package export map names each module (`src/agentic_dynamics/control/__init__.py:35-51`,
`src/agentic_dynamics/core/contracts.py:46-50`), with per-row consumption anchors below. [C] The old
placeholder language is gone because the modules exist, are consumed by named campaigns, and are gated
by real tests (the `test_context_plane_*.py` suite). Per-module status:

| CAP module | Design commitment (§9) | Implemented module | Current consumption state | Current gate | Current limitation |
|---|---|---|---|---|---|
| **Fact plane** | I0–I3, addenda | `control/facts.py` (`CanonicalFact`, `FACT_PREDICATES`, `EPISTEMIC_MAP`, `verify_chain`), `control/fact_ingestion.py` (record pipe + supersede chain), `control/reducers/` (`spec_status`, `attempt_facts`, `job_facts`, `policy_facts`, `workflow_facts`, `story_facts`, `pattern`, `code_change_facts`, `checkpoint`) | [C] Batch producers `scripts/kb_produce_facts.py` + `kb_produce_campaign_evidence.py`; the workflow-completion auto-emit hook (`kb_produce_facts.derive_run_facts` ← `scripts/run_workflow.py:465-497`); `scripts/spec_status.py` (spec_status/v1). [C] Campaigns cap_2b, cap_session_routing_prospective, cap_escalation_measurement read fact records back from the registry (the reducer registry at `src/agentic_dynamics/control/reducers/__init__.py:42-62`). | `test_context_plane_facts.py`, `test_context_plane_reducers.py`, `test_kb_produce_facts_integration.py`, `test_fact_auto_emit.py` (+`_adversarial`), `test_story_facts_reducer.py`, `test_code_change_facts.py` | I8+ blocked: no budget *owner* / deadline model is declared, so `budget_remaining` / `deadline_slack` predicates stay unwritten (design §9's blocked table) |
| **Context Compiler** | I4 (read-only) | `control/context_compiler.py` (compiler + `route_next_job/v1` contract + snapshots) | [C] `scripts/run_workflow.py --cap-snapshot` records a snapshot beside every `route_step` call (`scripts/run_workflow.py:303-309`); consumed internally by `control/rules.py`, `control/validator.py`, `control/profiles.py`, `control/reducers/checkpoint.py` (`compile_context` at `src/agentic_dynamics/control/context_compiler.py:717`) | `test_context_plane_compiler.py`, `test_context_plane_seam.py`, `test_evidence_prereq_gate.py` | Read-only by design: admissibility/unknown/stale/conflict rates are measured, never consumed by a routing decision; `--cap-shadow` compares but the deterministic `route_step` still executes |
| **step_routing** | Baseline (pinned, not a CAP increment) | `control/step_routing.py` (`route_step`), consumed via the dependency-inverted `runtime.routing.Router` protocol | [C] Composition root `scripts/run_workflow.py:379-393`; `runtime.workflow_runner` consumes the protocol, never imports control (`route_step` at `src/agentic_dynamics/control/step_routing.py:188`, pinned tier-1→tier-2 edges at `tests/test_dependency_direction.py:43-51`) | `test_step_routing.py`, `test_dependency_direction.py` | Deterministic + unconditional — the decision never yields to a shadow recommendation |
| **evidence_analyzer** | Evidence-selection/admissibility half of I4 | `control/evidence_analyzer.py` | [C] Phase-boundary evidence selection in `runtime/workflow_runner.py`, `runtime/change_analyzer.py`, `knowledge/graph.py` (`EvidenceChangeAnalyzer` at `src/agentic_dynamics/control/evidence_analyzer.py:129`); `scripts/evidence_prereq_gate.py` | `test_evidence_prereq_gate.py` | Selection is injection-scoped (populated only when a `change_analyzer` is injected) |
| **pattern_minting** | I9 addendum | `control/reducers/pattern.py` (`pattern/v1`) | [C] `scripts/kb_produce_facts.py --reducer pattern/v1` (single input door: the canonical-corpus `finding` table; the reducer at `src/agentic_dynamics/control/reducers/pattern.py:115-128`) | `test_context_plane_pattern.py` | One input door only — an empty finding table yields no fact (coverage invariant) |
| **checkpoint** | Typed checkpoints | `control/checkpoint.py` + `control/reducers/checkpoint.py` | [C] The `--cap-snapshot`/`--cap-shadow` path in `scripts/run_workflow.py:394-416`; the checkpoint reducer (`checkpoint_v1` at `src/agentic_dynamics/control/reducers/checkpoint.py:131-178`, registered at `src/agentic_dynamics/control/reducers/__init__.py:29`) | `test_context_plane_checkpoint.py` | Not yet consumed by a session-routing v2 with real stale context (the next release's science) |
| **decisions + rules + validator** | I6 controller, shadow mode | `control/rules.py` (rule engine + shadow decisions), `control/validator.py` (`ControlValidator`), `control/decisions.py` (`ControlDecision`), `control/verify_proposal.py` | [C] `scripts/run_workflow.py --cap-shadow` (decisions recorded + validated, never applied — `make_shadow_router` at `src/agentic_dynamics/control/rules.py:9-11`, `scripts/run_workflow.py:394-405`); cap_2a_shadow_calibration (agreement/divergence measured); cap_2b adaptive arm applies accepted proposals — the one applied path, inside its campaign cells per its own `apply_only_in_adaptive_arm` invariant (`workflows/repository/cap_2b.yaml:36-37,64-66`, 3 applied cells in `experiments/results/cap_2b/cap_2b_score_20260826T160018Z.json`), distinct from the I7 workflow-runner apply seam (`make_applying_router` at `src/agentic_dynamics/control/rules.py:12-19`, gated by `workflow.params.control_route: true` — no committed spec sets it, `tests/test_context_plane_seam.py:271-284`); `compile_experiment` rule evaluator | `test_context_plane_controller.py`, `test_context_plane_contracts.py`, `test_context_plane_profiles.py` | Shadow by default — actuation only on the cap_2b campaign's adaptive arm and the opted-in I7 `control_route` seam (both gated); `actuation_ingestion` still has zero call sites |
| **Fact contracts in the spec gate** | I5 | `core/contracts.py` (`FactRequirement`, `validate_fact_contracts`, refusals R1–R10) | [C] `compile_experiment.validate_rules` — the requires/produces gate refuses a control rule whose predicates are unproduced (`FactRequirement` at `src/agentic_dynamics/core/contracts.py:50`) | `test_context_plane_contracts.py`, `test_compile_experiment.py` | Refusal-only; no dynamic/updated contracts |
| **Scope hierarchy** | §10 (levels + two Redis planes) | `scope_path` across `control/facts.py` + the reducers (`ReducerInput.scope_path`), per-cell `repository_id` scoping in `knowledge/retrieval.py`, DB-2 KB vs DB-1 telemetry vs 6379 story sandbox | [C] Every reducer invocation + `retrieve()` scope pre-filter (`scope_path` at `src/agentic_dynamics/control/facts.py:148`, the hard pre-filter at `src/agentic_dynamics/knowledge/retrieval.py:395-408`) | `test_context_plane_facts.py` (scope semantics), `test_kb_produce_facts_extension.py` | org/workload levels exercised; program/job/attempt levels partly declared, not fully exercised |

[C] Consumption in production: cap_2a_rerun2/rerun3 (shadow calibration — `rules`/`validator`/
`evidence_analyzer`), cap_2b (adaptive arm — `decisions`/`validator` + fact contracts),
cap_escalation_measurement and cap_session_routing_prospective (fact plane + reducers),
cap_story_bridge (story_facts reducer), cap_pattern_minting (pattern/v1) — each campaign spec names
its consuming modules (`workflows/repository/cap_2a_rerun2.yaml`,
`workflows/repository/cap_2b.yaml:36-66`, `workflows/repository/cap_escalation_measurement.yaml`,
`workflows/repository/cap_session_routing_prospective.yaml`, `workflows/repository/cap_story_bridge.yaml`,
`workflows/repository/cap_pattern_minting.yaml`). [M] The dependency lint
still permits `control` to import `core` and `knowledge`, and nothing below tier 2 imports
`control` except the pinned adapter→`control.live` telemetry seam (§3) — "control consumes facts"
(rec 8) is enforced, not assumed (`tests/test_dependency_direction.py:187-193`).

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

This consolidation was staged by **`docs/release/consolidation/stage_map.md`** — the dependency-ordered
release plan (S0 → S1 → S2 → S3 → S4/S5 → S6), now complete (S6: `docs/release/consolidation/verification.md`
"Final result: PASS"). This file's plane/boundary definitions are the release's architectural spine.

---

## 5. Fleet ladder — containerized execution

[M] `Containerfile.fleet` defines the `fleet/base`, `fleet/orchestrator`, and `fleet/supervisor`
targets; the base supplies the non-root toolchain, while the orchestrator adds the Docker client and
sibling-spawn wrapper (`Containerfile.fleet:3-23`, `78-109`, `112-143`). [M] The active compose
supervisor units currently use `fleet/base`, not the defined supervisor target
(`infrastructure/docker-compose.ladder.yml:99-106`, `docs/reviews/fleet_ladder_implementation_adversary.md:17-18`).

[M] `infrastructure/docker-compose.ladder.yml:139-339` declares cell pools, the orchestrator
services, and supervisor-managed `fleet-manager`, Control Room, game-board, and review-trigger
units. The fleet manager exposes heartbeats and per-queue dead-letter counts; the live slice-1
cutover recorded both surfaces and a no-double-processing probe
(`docs/fleet/04_slice1_live_cutover_log.md:12-18`, `45-77`).

[M] The Docker socket is mounted read-only only by the orchestrator tier
(`infrastructure/docker-compose.ladder.yml:108-137`); `scripts/fleet/spawn_wrapper.py:155-240`
validates a sibling request's scope, phase authorization, mounts, network, and write flags before
building a Docker command. The slice-2 log records that pre-socket validation and the orchestrator
image build (`docs/fleet/05_slice2_orchestrator_log.md:12-17`, `34-67`).

[M] The compose mount inventory includes the worktree, read-only repository aliases plus writable
`.git` overlays, results, a shared OpenCode-state directory, and read-only credentials/configuration
(`infrastructure/docker-compose.ladder.yml:49-88`). [C] The state mount keeps the host's live
OpenCode state out of cells, but it is shared by scaled cells and therefore is not per-cell state
isolation (`infrastructure/docker-compose.ladder.yml:57-64,90-97,143-155`). [C] The mount guard's
allowlist covers the repository-alias and `.git` targets declared by compose, mirroring the
wrapper's runtime `CONTRACT_TARGETS` (`scripts/fleet/spawn_wrapper.py:79-97`); its
`test_mount_contract_holds_no_unexpected_target` check passes (and
`test_mount_guard_rejects_a_foreign_target` proves a foreign target still fails) and the guard is
not weakened (`tests/test_fleet_guards.py:86-102,136-153`).

[M] The accepted slice-4 log records the then-run coverage for mount targets, the single socket
tier, supervisor mount restrictions, heartbeats/DLQ, the write boundary, and scope/network
invariants (`docs/fleet/07_slice4_guards_log.md:20-30`). [P] Current operating claims distinguish
that historical evidence from the current mount-guard state (which now passes).

[M] The slice logs record the live cutover, orchestrator validation, Neo4j consumer/RRF leg, and
guard suite in `docs/fleet/04_slice1_live_cutover_log.md:12-18`,
`docs/fleet/05_slice2_orchestrator_log.md:12-17`,
`docs/fleet/06_slice3_neo4j_rrf_log.md:12-17`, and
`docs/fleet/07_slice4_guards_log.md:12-18`. [M] The `green_main_closure` ledger records a
successful workflow run in `/tmp/wt_green_main`; the ledger does not establish its container runtime
(`experiments/results/workflows/green_main_closure/20260831T201627Z.json:2-14`).

## 6. Isolation inventory

[M] The framework queue is Redis DB 1 on port 6380 and the durable knowledge stream is DB 2 on the
same instance; the story-agent sandbox uses port 6379 and can call `flushall()`, so it must never
share that instance (`src/agentic_dynamics/knowledge/knowledge_stream.py:10-16`, `46-55`). In the ladder, cells reach
the queue container's internal 6379 only on `fleet-net`; `finops-redis` is deliberately absent
from that network (`infrastructure/docker-compose.ladder.yml:22-32`, `344-351`).

[M] Knowledge records include `repository_id` in their identity, and a workflow cell scope is
`self-<worktree>` unless `FINOPS_CELL_ID` pins it
(`src/agentic_dynamics/knowledge/record_factory.py:106-175`,
`src/agentic_dynamics/runtime/workflow_runner.py:820-829`). [M] The workflow path supplies that
non-empty cell scope, while a direct `retrieve()` call with an empty requested scope disables the
repository filter; callers requiring isolation must supply a non-empty cell or shared scope
(`src/agentic_dynamics/knowledge/retrieval.py:395-408`).

[P] Worktree branches are ephemeral proposals until the controller's permanence decision; the
snapshot's awaiting-permanence board records that decision boundary
(`docs/designs/proposed/system_knowledge_abstraction.md:77-81`). [M] Container phase scopes are
the closed `SCOPE_VOCABULARY` and `PHASE_SCOPE_AUTHORIZATION`; the spawn wrapper rejects an
unknown or unauthorized scope before the socket call
(`src/agentic_dynamics/experiment/experiment_spec.py:49-133`,
`scripts/fleet/spawn_wrapper.py:155-192`).

[P] The supervisor is an observation rail: it flags but does not call `send_input` or `interrupt`;
only an explicit operator action may cross into control (`docs/architecture/current/supervisor_design.md:6-17`).
[C] Internal sandbox separation is evidenced by the `fleet-net` membership check. Internet egress
is direct today: no cell scope configures `HTTP_PROXY`/`HTTPS_PROXY`, so the egress proxy is the
declared policy point but not yet the enforced route — stated as current operating reality, not as
an open fix (`infrastructure/docker-compose.ladder.yml:3-6,259-271`,
`docs/fleet/04_slice1_live_cutover_log.md:126-134`, `docs/reviews/fleet_ladder_implementation_adversary.md:15-18,50-70`).

## 7. The canonical execution loop

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

## 8. Supersession map — what this file replaces, and what stays

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
| `agent_config/mental-model.md` (generated into `.opencode/instructions/mental-model.md` + `.claude/`) | The file map, signatures, and dependencies — the operational reference, not the architectural authority. |
| `scripts/CONTEXT.md` | The per-script reference (the authoritative script table, machine-parsed by the classification guard). |
| `docs/verification/data_integrity_findings.md` | The data-integrity boundary (no `_results_summary.json` resurrection). |
| `docs/reviews/` | The review directory — including the critique this file answers (`semantic_monolith_review.md`). |
| `docs/release/consolidation/{stage_map,design}.md` | The release plan + per-stage design this file is one output of. |
| `docs/designs/implemented/fleet_ladder_architecture.md` | Implemented fleet topology, mount/scope contract, evidence, and retained open limitations. |

---

## 9. The architectural invariant — the load-bearing rule

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
