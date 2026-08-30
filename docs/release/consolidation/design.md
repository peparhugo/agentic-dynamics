---
status: accepted
---
# Design — per-stage design with migration mechanics

**Phase `design` of `consolidation_release`.** Consumes `docs/release/consolidation/stage_map.md` (the
dependency order) and turns it into decision-complete designs: Stage 1 in full (package map, shim,
import-rewrite order, dependency lint), the `ARCHITECTURE.md` skeleton + doc-lifecycle migration,
the experiments/workflows classification rule, the CLI command-surface mapping, and a per-stage
acceptance-test list. Design only — no production code is edited here; the stage specs (next phase)
turn each design into an executable `consolidation_stage_*.yaml`.

**Provenance:** [C] computed from the current tree (module/script counts re-verified this phase);
[M] measured ground truth; [X] the critique (`semantic_monolith_review.md`); [P] policy/prior
(invariants).

---

## 0. Ground truth re-verified this phase

| Fact | Value | Source |
|---|---|---|
| `src/instrument/` modules | 64 `.py` (incl. `__init__.py`) | `ls src/instrument/*.py \| wc -l` = 64 |
| `scripts/` scripts | 85 `.py` (incl. `_constants.py`) | `ls scripts/*.py \| wc -l` = 85 |
| `tests/` files | 70 (69 `test_*.py` + `conftest.py`) | `ls tests/ \| wc -l` = 70 |
| `admin/` | 4 `.py` + `static/` (9 files) | `ls admin/` |
| Barrel `__init__.py` | 703 lines of `from .X import …` re-exports | `wc -l src/instrument/__init__.py` |
| `sys.path` bootstraps | 50 of 85 scripts insert `src/` | `grep -l "sys.path" scripts/*.py \| wc -l` |
| Deprecated modules | `experiment,adapter,lab_book,recovery,trajectory` (+ `scripts/plan.py`, 8 `*_DEPRECATED_bge_m3`) | WS-01 / `docs/refactor/review.md` |
| Core leaf modules | `language,paths,session_types,streaming` import only stdlib | grep (this phase) |

Two cross-plane edges were confirmed this phase and shape the dependency lint (§1.4): `live.py`
imports `supervisor.py` (both telemetry/observe), and `workflow_runner.py` + `opencode.py` +
`claude_adapter.py` import `live`; `workflow_runner.py` imports `step_routing`. These are the
*execution → control-observation* edges and are handled explicitly below.

---

## 1. Stage 1 — modular monorepo package move (the crux)

### 1.1 Final package map — all 64 modules dispositioned

Target layout per critique rec 2: `src/agentic_dynamics/{core,experiment,measurement,runtime,
adapters,knowledge,control,reporting}/` plus `legacy/` (rec 7). Assignment rule: **a module's plane
is the conceptual system it serves** (critique's six systems → subpackage), with foundation shared
by all → `core`, and retired → `legacy`.

#### core/ — foundation, no internal deps (4)

| Module | Reason |
|---|---|
| `language.py` | Tree-sitter foundation; "no internal deps" (CONTEXT) — every plane keys off `LanguageProfile`. |
| `paths.py` | Single source of truth for KB/registry filesystem paths; leaf (imports nothing). |
| `session_types.py` | Task/session vocabulary; "imports only the standard library" (docstring). |
| `streaming.py` | Shared subprocess line-runner (stdlib only); used by adapters + scripts. |

#### experiment/ — the experiment platform, system 2 (3)

| Module | Reason |
|---|---|
| `experiment_spec.py` | Spec dataclasses + `requires`/`produces` validator — the platform's contract layer. |
| `compile_experiment.py` | spec → DAG; generalizes the grid/compare surface (the platform's engine). |
| `spec_status.py` | Derived spec-lifecycle index (`STATUS.md`/`index.json`) — platform metadata, not a knowledge record. |

> Grid/cell/campaign (`adapt.py`, `JobRecord`/`AttemptRecord`) land here post-consolidation
> (WS-05/06/07 deferred); reserved now by `__init__` docstrings.

#### measurement/ — measurement apparatus, system 1 (15)

| Module | Reason |
|---|---|
| `perturb.py` | The 10 perturbation operators — the instrument's independent variable. |
| `prompt_perturbation.py` | Flash-authored session perturbation (companion to deterministic operators). |
| `mutation.py` | Mutation compiler (spec/code semantic perturbation, hashable artifact). |
| `solution.py` | 4-dimension correctness/constraints/quality/novelty evaluation. |
| `basin.py` | Structural divergence from baseline (basin-escape). |
| `efficiency.py` | Token/$/joule cost per model architecture. |
| `recovery_cost.py` | Economic cost of constraint recovery ($/constraint). |
| `strategy.py` | Archetype classification (CONSERVATIVE/EXPLORATORY/EXPLOITATIVE/FLAILING). |
| `semantic_validation.py` | Model-agnostic escape signals (markers/AST/latency). |
| `constraint_detection.py` | Detects whether the model noticed a removed constraint. |
| `commit_analysis.py` | Per-commit AST diff + Sonar delta + convention scoring. |
| `sonar.py` | SonarQube static-analysis metrics + differential quality. |
| `lsp_diagnostics.py` | Language-server diagnostics with graceful fallback. |
| `entropy.py` | Architectural entropy (information-theoretic disorder). |
| `codebase_graph.py` | Import-graph structural metrics (modularity/coupling/centrality). |

#### runtime/ — agent execution runtime, system 3 (4)

| Module | Reason |
|---|---|
| `workflow_runner.py` | Executes an `agent_task` workflow's phases in a worktree (the DAG's execute phase). |
| `test_runner.py` | Independent pytest/jest/go-test/cargo-test runner; sole source of `test_executed_success`. |
| `story.py` | Multi-session story orchestrator (N sequential sessions, per-session commits). |
| `posthoc.py` | Shared post-hoc job construction + enqueue primitives (the `execute→analyze→review` transport). |

#### adapters/ — model backends, system 3 (3)

| Module | Reason |
|---|---|
| `opencode.py` | Drives real opencode sessions (think/write/test loop); yields `AgenticResult.confidence`. |
| `claude_adapter.py` | Drives the Claude CLI (`stream-json`) → opencode events. |
| `backends.py` | Routes `anthropic/*` → Claude CLI, else opencode (`run_agentic`). |

#### knowledge/ — knowledge + augmentation, system 4 (16)

| Module | Reason |
|---|---|
| `knowledge.py` | Canonical identity + authority contract (ids, `Authority`, vocab, lineage). |
| `knowledge_stream.py` | Durable Redis Streams transport + the three write gates. |
| `record_factory.py` | Shared record-builder factory (seam S3). |
| `retrieval.py` | Deterministic dense+lexical RRF retrieval pipeline. |
| `prompt_constructor.py` | Typed prompt-constructor (one flash call + validator). |
| `augment.py` | The `retrieve→construct→render` seam (R7). |
| `graph.py` | Neo4j knowledge-graph client (full-text search, codebase-graph loader). |
| `embeddings.py` | `EmbeddingClient` + `ChromaStore` (dense store, collection isolation). |
| `knowledge_ingestion.py` | Producer: `finding` records (`measured-finding/v1` + `phase-finding/v1`). |
| `code_ingestion.py` | Producer: `code` records (`code/v1`). |
| `quality_ingestion.py` | Producer: `report` records (`quality/v1`). |
| `policy_ingestion.py` | Producer: `policy` records (`policy/v1`; citation-only). |
| `story_ingestion.py` | Producer: `story` records (`story/v1`). |
| `review_ingestion.py` | Producer: `review` records (`review/v1`). |
| `ledger_ingestion.py` | Producer: `ledger_job`/`ledger_attempt`/`meta_session` records (`ledger/v1`). |
| `spec_ingestion.py` | Producer: `spec` lifecycle records (`spec-lifecycle/v1`). |

#### control/ — emerging control system, system 5 (9)

| Module | Reason |
|---|---|
| `routing.py` | Task-optimal routing + strategy simulation (consumed by `build_data.py`/`admin/server.py`). |
| `step_routing.py` | Per-step model routing (consumed by `workflow_runner` — the execution→control edge). |
| `signal_store.py` | Measured per-model signal store for routing decisions. |
| `supervisor.py` | Supervisor flag/session↔cell Redis contracts — observe-only, no opencode dep. |
| `live.py` | Redis pub/sub telemetry (the "control/telemetry plane", unscoped, observe-only). |
| `pipeline_status.py` | Three-stage pipeline queue status (Control Room matrix + `monitor.py`). |
| `queue_reinterleave.py` | Round-robin queue steering across providers. |
| `observation_ingestion.py` | Producer: `observation`/`flag` records (supervisor verdicts). |
| `actuation_ingestion.py` | Producer: `actuation` records (candidate instruction, `causes`-linked). |

#### reporting/ — research + publication output, system 6 (4)

| Module | Reason |
|---|---|
| `game_report.py` | Combines all metrics into the Markdown game report. |
| `review.py` | LLM review pool (commit/story reviewer, cross-model comparator, test generator). |
| `ollama_analyzer.py` | Qualitative analysis via Ollama (narrative over metrics). |
| `opencode_analyzer.py` | Meta-experiment analysis via real opencode sessions. |

#### legacy/ — retired (fold WS-01) (5)

| Module | Reason |
|---|---|
| `experiment.py` | Deprecated orchestrator; superseded by `opencode.py` + `experiment_spec`. |
| `adapter.py` | Deprecated instrumented LLM wrapper. |
| `lab_book.py` | Deprecated YAML-frontmatter persistence. |
| `recovery.py` | Dead-in-production (only `tests/` importers); superseded by `recovery_cost.py`. |
| `trajectory.py` | Dead-in-production; `analyze_trajectories.py` parses `session.jsonl` directly, not this module. |

**`__init__.py` (barrel)** is not a plane — it becomes the compat shim (next section).

**Tally:** core 4 · experiment 3 · measurement 15 · runtime 4 · adapters 3 · knowledge 16 ·
control 9 · reporting 4 · legacy 5 · barrel 1 = **64**. Zero orphans; every module dispositioned
once.

### 1.2 Compatibility re-export strategy (the `instrument.*` shim)

Goal: the 85 scripts + 70 test files keep importing `from instrument.X import …` unchanged during
the transition, so the move and the consumer rewrite are *two independently-verifiable steps* rather
than one big-bang.

**Mechanism — a generated shim package.** `src/instrument/` is kept as a thin package whose only
job is to re-export the moved modules. For each moved module `<m>` now at
`agentic_dynamics.<plane>.<m>`, the shim emits `src/instrument/<m>.py`:

```python
# compat shim — GENERATED by consolidation Stage 1; do not edit by hand.
# Re-exports agentic_dynamics.<plane>.<m> so `from instrument.<m> import …` keeps working
# until every consumer is rewritten to the real package. Removed in Stage 1's final phase.
from agentic_dynamics.<plane>.<m> import *            # noqa: F401,F403
from agentic_dynamics.<plane>.<m> import __all__       # noqa: F401  (if defined)
```

The barrel `src/instrument/__init__.py` is regenerated to preserve the current 703-line surface:
every `from .X import name` is rewritten `from agentic_dynamics.<plane>.X import name`, so
`from instrument import X`, `import instrument.X`, and `from instrument.X import Y` all resolve.

**Why `import *` + `__all__` rather than PEP 562 `__getattr__`:** the scripts use *submodule*
imports (`from instrument.perturb import …`, `from instrument import perturb`), which `__getattr__`
on the package alone does not serve without a meta-path finder. Per-module stub files are mechanical,
greppable, and delete-able — the right trade for a transient shim.

**Deprecation signal:** the generated `__init__.py` emits a `DeprecationWarning` on import
(`"instrument.* is a compat shim — import agentic_dynamics.* instead"`), silenced by default so the
transition is quiet but visible under `-W always`.

**Deletion gate:** the shim is deleted only when `grep -r "from instrument\|import instrument"` over
`scripts/ admin/ tests/ src/` returns zero matches outside the shim itself — enforced as a Stage 1
acceptance test (a failing grep = a blocked retire).

### 1.3 Import-rewrite order (phases of the Stage 1 execution spec)

Each phase is one green commit; the tree is green before *and* after every phase (no observable
broken intermediate state).

| Phase | Action | Green gate |
|---|---|---|
| A `skeleton` | Create `src/agentic_dynamics/` with 9 plane dirs + empty `__init__.py`s (docstring-only; `legacy/` too). Additive, nothing moves. | `pytest tests/ -m "not external"` still green (new package is inert). |
| B `move` | `git mv` all 64 modules to their plane (preserves history); rewrite **internal** imports `from .X import` / `from instrument.X import` → `from agentic_dynamics.<plane>.X import` (relative stays relative within a plane); regenerate the plane `__init__.py`s and the shim `src/instrument/` in the *same* commit. | `pytest` green via the shim; `python scripts/run.py --help`-style smoke on 5 representative scripts. |
| C `rewrite-consumers` | Rewrite `scripts/` + `admin/` + `tests/` imports `instrument.` → `agentic_dynamics.<plane>.`, replacing the `sys.path.insert(…/src)` bootstrap with `scripts/_bootstrap.py` (or editable install). `_constants.py` moves to `agentic_dynamics/core/` (it is a shared constant module, not a command). | `pytest` green; `grep` shows zero `instrument.` imports outside the shim. |
| D `dependency-lint` | Add `tests/test_dependency_direction.py` (§1.4) and the data-flow tests; run them. | lint + data-flow tests green. |
| E `retire-shim` | Delete `src/instrument/` (zero importers remain); retire `legacy/` modules that WS-01 marks dead (already isolated in `legacy/`, no current imports). | `pytest` green; `grep -r instrument` = zero; compile-gate `validate` on all committed specs green. |

**Ordering rationale:** B is atomic so the shim is never half-written (a half-moved tree would be
unimportable); C is separated from B so a mass-import rewrite is reviewable independently of the
move; D lands the enforcement *after* the move settles so the lint reflects the real post-move graph;
E is the rec-7 deletion, done last because "retire only after the last importer is repointed"
(load-bearing-rule principle 3 in `docs/refactor/plan.md`).

### 1.4 Dependency-direction lint (a pytest walking the import graph)

`tests/test_dependency_direction.py` enforces rec 8 *verbatim*, not a blanket 4-tier DAG — because
the real graph contains two legitimate execution→control edges (confirmed §0) that a blanket tier
rule would falsely reject. The tier map is descriptive; the forbidden edges are the explicit rules.

**Tier map** (module → tier), hardcoded:

- tier 0 `core`: `language,paths,session_types,streaming`
- tier 1 `planes`: `experiment,measurement,runtime,adapters,knowledge,reporting`
- tier 2 `control`: `control`
- tier 3 `apps`: `apps/` (applications — outside `src/agentic_dynamics/`, still linted)

**Forbidden-edge assertions** (walk `ast.parse` imports of every `src/agentic_dynamics/**` module +
`apps/**`):

1. `core` imports nothing from tier ≥ 1 (only stdlib/third-party + core siblings). — *rec 8 "core
   imports nothing from higher layers."*
2. `measurement` does not import `control`. — *rec 8 verbatim.*
3. `knowledge` does not import `control` (knowledge does not actuate). — *rec 8 verbatim.*
4. `experiment` does not import `control`. — *faithful extension: the platform defines; control
   consumes.*
5. `reporting` does not import `control`. — *faithful extension: output does not steer.*
6. `control` does not import `apps`; nothing below tier 3 imports `apps`. — *apps consume the
   system; nothing is consumed-by-apps.*
7. `control` does not import `knowledge.retrieval` or `knowledge.prompt_constructor`. — *rec 8
   "control consumes facts, not arbitrary retrieved text."*
8. `apps` contain no domain rules: no `ExperimentSpec(` / `RuleSpec(` / `Factor(` construction in
   `apps/**` (AST-marker scan). — *rec 8 "apps may compose layers but contain no domain rules."*

**Explicitly allowed (and pinned by a positive assertion, so new edges don't sneak in):**

- `runtime.workflow_runner` → `control.step_routing`, `control.live` (execution consults the
  per-step router + publishes telemetry).
- `adapters.opencode`, `adapters.claude_adapter` → `control.live` (adapters publish telemetry).

These are asserted as the *complete* set of tier-1→tier-2 edges: the lint fails if any tier-1
module other than those named imports `control`. (This is the observation seam the supervisor design
names "observe, never steer" — telemetry up, decisions down.)

**Data-flow tests** (separate file, not import-graph): `retrieve()` never returns an
authority==POLICY candidate and references `publish_event` zero times (rec 8 "retrieval never
supplies canonical facts"); knowledge modules never call `actuation_ingestion.derive_actuation_record`
(rec 8 "knowledge does not actuate").

---

## 2. `ARCHITECTURE.md` skeleton (Stage 0)

One root `ARCHITECTURE.md` answering the critique's rec-4 list. Section skeleton (each section is a
checklist item in S0's acceptance tests):

1. **Planes** — the eight bounded packages (§1.1) + their one-line ownership; the six systems map
   (`measurement`→system 1, `experiment`→system 2, `runtime`+`adapters`→system 3, `knowledge`→
   system 4, `control`→system 5, `reporting`+`apps`→system 6).
2. **Package boundaries** — what each plane may/may not import (the §1.4 tier map + forbidden edges,
   stated in prose and pointing at `tests/test_dependency_direction.py`).
3. **Dependency direction** — the ASCII spine
   `core ← experiment/measurement/runtime/knowledge ← control ← applications` with the two pinned
   execution→control observation edges drawn as dashed (observe-only) arrows.
4. **Implemented vs proposed** — a table: shipped planes/features vs reserved-but-empty homes (CAP
   I0–I7 homes from `stage_map.md` §6) vs deferred workstreams (WS-02..08).
5. **The canonical execution loop** — `spec → compile → DAG → cells → jobs → attempts → ledger →
   information → policy → grid → campaign` (the mental model's cycle).
6. **Supersession map** — which documents this file replaces (BLUEPRINT×3, dated handoffs, superseded
   reviews) and which remain authoritative (mental-model, `src/instrument/CONTEXT.md`,
   `scripts/CONTEXT.md`, `data_integrity_findings.md`, the review directory).

---

## 3. Doc-lifecycle migration (Stage 0)

Status vocabulary (rec 4): `proposed | accepted | implementing | implemented | superseded |
abandoned`, plus `supersedes:` and `implemented_by:` fields. A YAML front-matter block is added to
the top of each doc.

**Moves to `docs/archive/`** (with `status: superseded` + `superseded_by: ARCHITECTURE.md` or a
named successor):

| Source | New home | Status |
|---|---|---|
| `BLUEPRINT.md`, `BLUEPRINT_v2.md`, `BLUEPRINT_v3.md` | `docs/archive/` | superseded |
| `docs/HANDOFF_2026-08-17.md`, `docs/HANDOFF_2026-08-19.md` | `docs/archive/` | superseded |
| dated `code_reviews/*` predating the registry repoint | `docs/archive/` | superseded (keep, not delete) |
| `docs/reviews/restructure.md` §5.2 (the `source_type` item) | note in `docs/reviews/knowledge_base.md` | superseded (per ADR-4) |

**Moves to `docs/designs/current/`**: the context-abstraction design (`design.md` + `verify.md`),
`supervisor_design.md`, the spec/compiler roadmap (`code_reviews/2026-08-14_*`) — as the *current*
(unimplemented, frozen-for-CAP) designs.

**Moves to `docs/designs/implemented/`**: designs whose code has shipped (canonical-state rounds,
RAG seam split, website repoints) — each with `implemented_by:` naming the merged branch/PR.

**Lifecycle rule (the classification test):** a root/docs markdown file without a status front-matter
block fails a Stage 0 lint (`tests/test_doc_lifecycle.py` walks `docs/**` + root `*.md`, asserts a
status field + a `supersedes:`/`implemented_by:` where applicable). This makes "is this current, old,
proposal, generated artifact, or research result?" answerable from the path + status field (rec 3's
healthy-repo test).

---

## 4. Experiments-vs-workflows classification rule (Stage 2)

**The rule (rec 3):** a spec is an **experiment** iff it studies a *hypothesis about a model's
behavior/cost/quality under some condition* and produces a *measured result*. A spec is a
**workflow** iff it is a *work order that changes the repository* (build/write/fix/repoint/rebrand)
with a deliverable artifact, not a measurement.

**Layout:**

```
experiments/
  definitions/   # genuine ExperimentSpecs + the 34 configs (hypothesis-testing)
  campaigns/     # grid/campaign sequencing (factorial_compound, silent_mode_sweep, cross_models…)
  fixtures/      # seed codebases, stories, perturbation fixtures
  results/       # reports/, kb/, registry_index.jsonl, _results_summary.json (historical), etc.
workflows/
  repository/    # website rewrites, KB construction, control-room dev, data remediation, rebranding
  operations/    # queue steering, review workers, registry canonicalize
  research/      # rag_bare_vs_augmented (a *comparison* — but its *definition* is an experiment; its
                 #   build steps are workflows — the spec is split: the hypothesis → experiments/definitions,
                 #   the build → workflows/repository)
  examples/      # template specs
```

**The guard test** `tests/test_experiment_workflow_classification.py`:
- loads every `experiments/definitions/*.yaml` and asserts `workflow.kind` is a *measurement*
  workflow (story/task/experiment) **or** a rule/metadata key marks it an experiment; fails if it
  detects a work-order signature (`workflow.kind: agent_task` whose `context.hard_rules` include
  "DESIGN/IMPLEMENT ONLY … edit production code", or whose `question` names a repo-change deliverable
  like *website/control-room/kb-build/rewrite/repoint/rebrand*).
- the reciprocal: every `workflows/**/*.yaml` asserts the work-order signature. A misplaced spec
  fails the test in the direction it was misplaced.

This is a *test, not a convention* (rec 2's "path tells you what plane" applied to specs), and it is
the anti-resurrection pattern from WS-04 generalized.

**Known re-homes** (from the 67-spec `STATUS.md`): `website_rewrite`, `website_repoint`,
`website_registry_repoint`, `control_room_*`, `rag_knowledge_base_build`/`_wire`/`_reconcile`/
`_produce`, `kb_*`, `queue_steer`, `canonical_state_*`, `agentic_dynamics_rebrand`,
`remediation_data_integrity`, `spec_lifecycle`, `claude_tools_to_skills`, `opencode_docs_refresh` →
`workflows/`; `rag_bare_vs_augmented`, `routing_*`, `workflow_step_routing`, `explanation_tax`,
`process_perturbation_resample`, `posthoc_pipeline` → `experiments/`.

---

## 5. CLI command-surface mapping (Stage 3)

One entry point `agentic-dynamics` (thin CLI adapters; rec 8 "scripts become thin CLI adapters
only"). Mapping of every maintained script → subcommand; the rest classified.

```
agentic-dynamics
├─ experiment run <config> …                ← scripts/run.py
├─ experiment sweep …                       ← scripts/sweep_parallel.py, sweep_silent_mode.py,
│                                             batch_run.py, remaining_batch.py, multi_phase.py
├─ story run <story> …                      ← scripts/run_story.py
├─ story batch <story>                      ← scripts/batch_stories.py
├─ workflow run <spec> …                    ← scripts/run_workflow.py
├─ queue enqueue …                          ← scripts/enqueue.py
├─ queue worker …                           ← scripts/worker.py
├─ queue monitor …                          ← scripts/monitor.py
├─ queue reinterleave …                     ← scripts/reinterleave_queue.py
├─ queue analysis …                         ← scripts/enqueue_analysis.py, analysis_worker.py
├─ analyze worktrees                        ← scripts/analyze_worktrees.py
├─ analyze trajectories                     ← scripts/analyze_trajectories.py
├─ analyze stories                          ← scripts/analyze_stories.py
├─ analyze lab <name>                       ← the 19 active scripts/lab_*.py
├─ data build                               ← scripts/build_data.py
├─ data sync                                ← scripts/sync_data.py
├─ data manifest                            ← scripts/generate_manifest.py
├─ data inventory …                         ← scripts/inventory.py
├─ knowledge ingest                         ← scripts/kb_produce.py
├─ knowledge sources                        ← scripts/kb_produce_sources.py
├─ knowledge worker                         ← scripts/kb_worker.py
├─ registry query|show|lineage              ← scripts/registry.py
├─ review all|stories|trigger|enqueue|finalize ← scripts/review_all.py, review_stories.py,
│                                                trigger_reviews.py, enqueue_reviews.py, finalize_reviews.py
├─ spec status                              ← scripts/spec_status.py
├─ spec pipeline <plan> …                   ← scripts/pipeline.py
├─ validate session …                       ← scripts/validate_session.py
├─ validate tests …                         ← scripts/verify_tests.py
└─ supervise [--once]                       ← scripts/supervise.py, claude_agents_supervisor.py
```

**Classification of the rest (each lands in exactly one bucket, zero orphans):**

| Bucket | Scripts | Disposition |
|---|---|---|
| maintained command | all above | thin CLI adapters (rec 8) |
| one-time migration | `backfill_artifacts,backfill_story_artifacts,backfill_story_transcripts,backfill_deep_metrics,batch_analyze_ts_ssg,finish_sweep,regen_typescript_ssg,backfill_sonar,backfill_costs,compute_sonar_deltas,embed_sessions,recovery_cost_table,rescore_conventions,recover_stories,kb_produce_registry` | → `scripts/archive/` (fold WS-10) |
| historical analysis | the 19 active `lab_*.py` (kept as `analyze lab <name>`, no rewrite) | maintained (analysis-only) |
| deprecated | `plan.py`, `review_worker.py` (fold WS-09), `analyze_with_ollama.py`, `analyze_with_opencode.py`, `build_graph.py`, 8 `lab_*_DEPRECATED_bge_m3.py` | retire (fold WS-01) |
| module | `_constants.py` | move to `agentic_dynamics/core/` |

---

## 6. Per-stage acceptance test list (a later execution workflow must run)

Every stage's verify phase runs the named tests *plus* the standing gates (`pytest tests/ -m "not
external"`, `compile_spec` validate on all committed specs, the §stage_map invariants). The lists
below are the stage-*specific* additions.

### Stage 0 — architecture spine + doc lifecycle + freeze
- `tests/test_doc_lifecycle.py`: every root `*.md` + `docs/**/*.md` has a status front-matter; `docs/archive/` entries carry `status: superseded`; `docs/designs/{current,implemented}` entries carry `status` + `implemented_by:`.
- exactly one root `ARCHITECTURE.md`; `assert` no `BLUEPRINT*.md` at root.
- `ARCHITECTURE.md` contains the §2 sections (planes/boundaries/direction/implemented-vs-proposed/loop/supersession).
- `context_abstraction_implement` carries the freeze note (§stage_map §6) — asserted by reading the spec YAML.

### Stage 1 — package move
- 64/64 modules present under `src/agentic_dynamics/*` + `legacy/`; `assert` the §1.1 tally.
- all 85 scripts + 70 test files import via the shim with **zero source edits** (the phase-B green gate).
- `tests/test_dependency_direction.py` green (§1.4, all 8 forbidden-edge assertions + 2 pinned positive edges).
- data-flow tests green: retrieval supplies no POLICY facts / zero `publish_event`; knowledge never calls `derive_actuation_record`.
- `grep -r "from instrument\|import instrument" scripts/ admin/ tests/` = zero after phase E.
- `pytest tests/ -m "not external"` green at every phase boundary.

### Stage 2 — experiments/workflows split
- `tests/test_experiment_workflow_classification.py` green (and demonstrably red when a work-order spec is dropped into `experiments/definitions/`).
- `scripts/spec_status.py` regenerates `STATUS.md`/`index.json` from new paths, zero orphan specs.
- every work-order spec (the §4 known re-homes) lives under `workflows/`; every hypothesis spec under `experiments/definitions/`.

### Stage 3 — CLI + script classification
- `agentic-dynamics --help` lists every §5 subcommand; each subcommand runs its backing script (smoke).
- the classification manifest (in `scripts/CONTEXT.md`) covers all 85 scripts, zero orphans.
- `review_worker.py` retired; `pipeline.py`/`trigger_reviews.py` no longer reference it.
- `scripts/archive/` contains the §5 one-time migrations, none importable as maintained commands.

### Stage 4 — instruction surfaces
- `tests/test_generated_surfaces_match.py` green: `agent_config/` regenerates `.opencode/` + `.claude/` byte-identically; the test fails on drift.
- no `.opencode/`/`.claude/` file is hand-edited (the generation script + guard test are the only writers).

### Stage 5 — apps/ + public-identity
- `admin/server.py` + `firebase/public/` live under `apps/{control-room,website}` and import `agentic_dynamics.*` (not the reverse).
- `tests/test_dependency_direction.py` apps-rule green (no domain rules in `apps/`).
- dual-Firebase invariant: `firebase deploy --only hosting` targets BOTH `ai-finops-rulebook` + `agentic-dynamics` (same `public/`).
- README re-framed (six systems; perturbation instrument is one of them) — human-verified against the §stage_map outcome.

### Stage 6 — consolidation verification release
- coverage: 9 recs → ≥1 stage; WS-01..10 dispositioned; zero orphans (§stage_map §5).
- all stage-specific tests above green in one run.
- `compile_spec` validate on every committed spec green.
- invariant audit green: Redis isolation, dual Firebase, CAP frozen-not-deleted, no `_results_summary.json` resurrection.
- both Firebase hosts deployed in sync.

---

## 7. Risks carried into the stage specs

| Risk | Stage | Mitigation |
|---|---|---|
| Mass `git mv` + import rewrite breaking the tree | S1 | atomic phase B (move + shim same commit); C separated; green at every phase |
| Lint false-positive on the two execution→control edges | S1 | they are pinned positive assertions, not blanket-tier (rec-8-verbatim) |
| Spec re-home breaking `spec_status.py` | S2 | re-point paths first, regenerate index, assert zero orphans |
| `.opencode`/`.claude` drift after generation | S4 | byte-identity guard test |
| Firebase deploy path move losing dual-host sync | S5 | both-host deploy asserted in S5 + S6 acceptance tests |
| Shim left behind (rec 7 half-done) | S1 | deletion gate = the `grep` acceptance test (phase E) |
