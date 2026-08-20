---
status: accepted
---
# Stage Map — consolidation release

**Phase `stage_map` of `consolidation_release`.** Decomposes the semantic-monolith critique
(`docs/review/semantic_monolith_review.md` — [X], 9 recommendations) into a dependency-ordered,
executable stage set, folds/defers/retires the `refactor_master_plan` workstreams (WS-01..10), and
declares the Context Abstraction Plane freeze. Design + staging only: this document writes no
production code — each stage becomes a gate-passing `experiments/specs/consolidation_stage_*.yaml`
in the later `stage_specs` phase, executed in order by later workflows.

**Provenance:** [C] computed from the current tree (counts re-verified this phase); [X] the critique
(recommendation numbers "rec N"); [M] measured ground truth; [P] policy/prior (invariants).

---

## 1. The release outcome (what "done" means)

Per the critique's blunt summary, the consolidation release has **one outcome** — a structural
rehome, not new functionality:

> one architectural spine · clear bounded packages · experiments separated from work orders ·
> one CLI · one instruction source · one current architecture document · old generations
> archived or deleted.

Every stage below is a dependency-ordered increment toward that outcome. The load-bearing rule
(`instrument → derive → policy → grid → campaign`, gated by `requires`/`produces`) and the
operational invariants (Redis isolation, dual Firebase, CAP frozen-not-deleted) survive every
stage boundary — a stage that breaks either is wrong by definition.

---

## 2. Recommendation coverage matrix (rec → stage)

Each of the nine recommendations lands in ≥1 stage; no recommendation is orphaned.

| Rec | Recommendation (critique §"The nine recommendations") | Primary stage(s) | Disposition |
|---|---|---|---|
| 1 | Freeze architectural expansion (pause CAP I0–I7) | **S0** | freeze declared; reserved homes reserved |
| 2 | Modular monorepo under `src/agentic_dynamics/` | **S1** | package move |
| 3 | Separate experiments from workflows | **S2** | split + guard test |
| 4 | One root `ARCHITECTURE.md` + doc lifecycle | **S0** | authority + status fields |
| 5 | One CLI + script classification | **S3** (CLI) + **S5** (public identity) | collapse + classify |
| 6 | One canonical instruction source (`agent_config/`) | **S4** | generate, don't hand-edit |
| 7 | Delete deprecated code (or `legacy/`, zero imports) | **S1** | folded WS-01 |
| 8 | Dependency-direction rules, auto-enforced | **S1** | lint as pytest |
| 9 | Website + control room as `apps/` | **S5** | consume-the-system |

**Stage 6 (consolidation verification release)** is the cross-cutting gate that asserts *all nine*
recs are satisfied and both Firebase hosts are deployed in sync.

---

## 3. Stage overview (the dependency order)

```
S0 architecture spine + doc lifecycle + CAP freeze
 └─ S1 modular monorepo package move + compat re-exports   (crux)
     ├─ S2 experiments-vs-workflows split
     │   └─ S3 CLI + script classification
     │       ├─ S4 instruction surfaces
     │       └─ S5 apps/ + public-identity realignment
     └──────────────────────────────────────────────────► S6 verification release
```

| Stage | id | Name | Recs | Effort | Risk | Needs | Blocks |
|---|---|---|---|---|---|---|---|
| S0 | `architecture-spine-doc-lifecycle-freeze` | Architecture spine + doc lifecycle + CAP freeze | 1, 4 | M | LOW | — | S1–S6 |
| S1 | `modular-monorepo-package-move` | Modular monorepo package move + compat re-exports | 2, 7, 8 | L | HIGH | S0 | S2–S6 |
| S2 | `experiments-workflows-split` | Experiments-vs-workflows split | 3 | M | MED | S1 | S3, S5, S6 |
| S3 | `cli-script-classification` | CLI + script classification | 5 | L | MED | S2 | S4, S5, S6 |
| S4 | `instruction-surfaces` | Instruction surfaces | 6 | M | LOW | S3 | S6 |
| S5 | `apps-public-identity-realignment` | apps/ + public-identity realignment | 9, 5 | M | MED | S1, S2, S3 | S6 |
| S6 | `consolidation-verification-release` | Consolidation verification release | all | S | LOW | S0–S5 | — |

Sequencing rationale (refines the suggested skeleton — inherited, not blindly):

- **S0 before S1** because S1's package map is the *physical* realization of S0's ARCHITECTURE.md
  planes; a move without the authority document would re-derive the same prose sprawl the critique
  flags (rec 4).
- **S3 depends on S2** because the CLI's `workflow run` / `experiment run` subcommands must reference
  the split paths; classifying scripts against an unsplit tree would be re-done after S2.
- **S4 after S3** because the canonical `agent_config/` documents the CLI command surface and module
  paths; generating `.opencode/`+`.claude/` from a source that still names 85 loose scripts would
  churn twice.
- **S5 is a fan-in** of S1 (imports rewrite), S2 (site/workflow data paths), S3 (site/knowledge
  subcommands); it is deliberately late so apps move *after* their import roots stabilize.

---

## 4. Stage details

### Stage 0 — architecture-spine-doc-lifecycle-freeze (rec 1, 4)

- **id:** `architecture-spine-doc-lifecycle-freeze`
- **name:** Architecture spine + doc lifecycle + CAP freeze
- **Delivers:** rec 1 (freeze), rec 4 (one current architectural authority + doc lifecycle).
- **Scope (files/dirs touched):**
  - new root `ARCHITECTURE.md` (planes, package boundaries, dependency direction, implemented vs
    proposed, canonical execution loop, supersession map).
  - root `BLUEPRINT.md`, `BLUEPRINT_v2.md`, `BLUEPRINT_v3.md` → `docs/archive/` (superseded).
  - `README.md`, `AGENTS.md`, `CLAUDE.md`, `docs/*.md` top-level handoffs/code reviews → lifecycle
    status header (`proposed | accepted | implementing | implemented | superseded | abandoned`
    + `supersedes:` + `implemented_by:`).
  - new `docs/designs/{current,implemented}/` and `docs/archive/`.
  - `experiments/specs/context_abstraction_implement.yaml` — freeze note (see §6).
  - `experiments/specs/STATUS.md` + `index.json` — regenerated with the freeze note.
- **Inputs:** `semantic_monolith_review.md`; `docs/review/*`; `docs/refactor/{review,plan,tradeoffs,
  design_final}.md` (from `feature/refactor-master-plan`); `.opencode/instructions/mental-model.md`;
  `docs/context_abstraction/design.md` (§9 I0–I7) and `docs/supervisor_design.md`.
- **Outputs:** `ARCHITECTURE.md` (the single superseding map); doc-lifecycle status fields on every
  remaining top-level doc; populated `docs/designs/{current,implemented}` + `docs/archive/`; the CAP
  freeze note.
- **Acceptance criteria:**
  1. Exactly one root `ARCHITECTURE.md` exists and its "supersession map" names which docs it
     replaces (BLUEPRINT×3, dated handoffs, superseded reviews).
  2. No `BLUEPRINT*.md` remains at the root (moved to `docs/archive/`).
  3. Every remaining top-level doc carries a lifecycle status field; `docs/archive/` entries carry
     `status: superseded` + `superseded_by:`.
  4. `context_abstraction_implement` is marked **PAUSED** (not deleted, not superseded) — §6.
  5. `docs/consolidation/stage_map.md` (this file) is named as the release plan in ARCHITECTURE.md's
     "implemented vs proposed" section.
  6. Doc-only change: `pytest tests/ -m "not external"` still green (no code touched).
- **Risk:** LOW (documentation only; no import surface).
- **Effort:** M.
- **Needs:** — (baseline).
- **Blocks:** S1–S6 (every stage consumes ARCHITECTURE.md's plane/boundary definitions).

### Stage 1 — modular-monorepo-package-move (rec 2, 7, 8) — **the crux**

- **id:** `modular-monorepo-package-move`
- **name:** Modular monorepo package move + compatibility re-exports
- **Delivers:** rec 2 (modular monorepo), rec 7 (delete/quarantine deprecated), rec 8
  (auto-enforced dependency direction). **Folds WS-01** (dead-code retirement) and the
  **sys.path half of WS-10**.
- **Scope (files/dirs touched):**
  - `src/instrument/` (64 modules) → `src/agentic_dynamics/{core,experiment,measurement,runtime,
    adapters,knowledge,control,reporting}/` per the disposition table in `docs/consolidation/design.md`
    (this phase's next artifact); deprecated `experiment.py`, `adapter.py`, `lab_book.py`,
    `recovery.py`, `trajectory.py` → `src/agentic_dynamics/legacy/` (zero current imports) or
    deleted outright.
  - new `src/instrument/` **shim package** re-exporting from `src/agentic_dynamics/*` so the 85
    scripts + 70 test files keep importing unchanged during the transition.
  - every `scripts/*.py` `sys.path` bootstrap → one `scripts/_bootstrap.py` (editable install or
    equivalent) — replaces ~55 per-file `sys.path.insert` hacks.
  - new dependency-direction lint (a pytest walking the import graph, asserting
    `core ← experiment/measurement/runtime/knowledge ← control ← applications`, plus: knowledge
    never actuates, retrieval never supplies canonical facts, apps contain no domain rules).
- **Inputs:** `ARCHITECTURE.md` (S0 planes); `docs/refactor/design_final.md` §1 module map +
  §2 seam list; `docs/refactor/review.md` accounting (which modules are dead); the mental model's
  reuse map.
- **Outputs:** the `src/agentic_dynamics/` package tree; the `src/instrument/` compat shim; the
  dependency lint test; `legacy/` quarantine; deleted dead modules (or legacy-imports-free).
- **Acceptance criteria:**
  1. All 85 scripts + 70 test files import successfully via the shim with **zero source edits** (the
     shim is the transition contract).
  2. `pytest tests/ -m "not external"` green at every commit boundary.
  3. The dependency-direction lint passes (`core` imports nothing higher; `measurement` does not
     import `control`; `knowledge` does not actuate; `apps` contain no domain rules).
  4. Deprecated modules (`experiment/adapter/lab_book/recovery/trajectory.py`, `scripts/plan.py`,
     8 `lab_*_DEPRECATED_bge_m3.py`) are gone from the live package or in `legacy/` with no current
     import — folded WS-01.
  5. `scripts/_bootstrap.py` replaces per-file `sys.path.insert`; `python scripts/foo.py` direct-run
     still works (folded WS-10 sys.path half).
  6. `compile_experiment.py`'s `requires`/`produces` gate still passes on all committed specs
     (load-bearing rule intact through the move).
- **Risk:** HIGH (mass import move; largest breakage surface — see `tradeoffs.md` §4, "import
  surface" table).
- **Effort:** L.
- **Needs:** S0.
- **Blocks:** S2, S3, S4, S5, S6.

### Stage 2 — experiments-workflows-split (rec 3)

- **id:** `experiments-workflows-split`
- **name:** Experiments-vs-workflows split
- **Delivers:** rec 3 (separate experiments from workflows). Promotes WS-04's anti-resurrection
  guard-test *pattern* into a classification guard test (WS-04 itself stays deferred — §5).
- **Scope (files/dirs touched):**
  - `experiments/{definitions,campaigns,fixtures,results}` — genuine hypothesis-testing specs/configs.
  - new `workflows/{repository,operations,research,examples}` — work orders (e.g. `website_rewrite`,
    `control_room_portal`, `rag_knowledge_base_build`, `rag_knowledge_base_wire`, KB construction,
    queue steering, control-room development, documentation refresh, data remediation, rebranding).
  - `experiments/specs/STATUS.md`, `experiments/specs/index.json`, `scripts/run_workflow.py`,
    `scripts/spec_status.py`, `src/instrument/spec_ingestion.py` — path references re-pointed.
  - new classification guard test: fails when a work-order spec lands in `experiments/definitions/`
    (a test, not a convention).
- **Inputs:** S1 package map (spec/`workflow` loader paths); `experiments/specs/` (67 specs, per
  `STATUS.md`); `experiments/configs/` (34); `experiments/results/`.
- **Outputs:** reorganized `experiments/` + new `workflows/`; classification guard test; re-pointed
  spec/status/ingestion references.
- **Acceptance criteria:**
  1. Every genuine experiment spec lives under `experiments/definitions/`; every work order under
     `workflows/operations/` (or `repository`/`research`/`examples` as its nature dictates).
  2. The classification guard test is green and *demonstrably* fails when a work-order spec is
     placed in `experiments/definitions/`.
  3. `python scripts/spec_status.py` regenerates `STATUS.md` + `index.json` from the new paths with
     no orphans.
  4. `rag_bare_vs_augmented`, `rag_knowledge_base`, etc. remain experiments; `website_rewrite`,
     `control_room_portal`, `rag_knowledge_base_build` become workflows (critique rec 3 examples).
- **Risk:** MED (spec-path moves break `run_workflow.py`/`spec_status.py`/ingestion references).
- **Effort:** M.
- **Needs:** S1.
- **Blocks:** S3 (CLI `experiment run` / `workflow run`), S5 (site + workflow data paths), S6.

### Stage 3 — cli-script-classification (rec 5)

- **id:** `cli-script-classification`
- **name:** CLI + script classification
- **Delivers:** rec 5 (one CLI + script classification). **Folds WS-09** (retire `review_worker.py`)
  and the **archive half of WS-10** (7 one-time backfill scripts).
- **Scope (files/dirs touched):**
  - new `agentic-dynamics` CLI entry point with subcommands: `experiment run`, `workflow run`,
    `queue worker/monitor`, `analyze worktrees/trajectories`, `data build`, `knowledge ingest`,
    `registry query`, `site build`.
  - `scripts/*.py` (85) classified into: **maintained command** (backed by a CLI subcommand) /
    **one-time migration** (→ `scripts/archive/`) / **historical analysis** (lab books, kept as
    analysis-only) / **deprecated** (retired).
  - `scripts/review_worker.py` retired (folded WS-09 — resolve the "superseded but still spawned"
    contradiction); the deeper `pipeline.py` review-phase rewire to `review_all.py` is deferred.
  - `scripts/{backfill_artifacts,backfill_story_artifacts,backfill_story_transcripts,
    backfill_deep_metrics,batch_analyze_ts_ssg,finish_sweep,regen_typescript_ssg}.py` →
    `scripts/archive/` (folded WS-10).
  - new `scripts/CONTEXT.md` classification manifest (the authoritative per-script table, re-issued).
- **Inputs:** S2 path map (subcommand paths); `scripts/CONTEXT.md`; `scripts/pipeline.py` review
  phase (`:531,536,1148`).
- **Outputs:** the CLI; the classification manifest; `scripts/archive/`; retired `review_worker.py`.
- **Acceptance criteria:**
  1. Every maintained script has a CLI subcommand; no maintained command lives *only* as a loose
     script.
  2. The classification manifest covers all 85 scripts with zero orphans.
  3. One-time migrations live in `scripts/archive/`, not beside the maintained runtime.
  4. `review_worker.py` is retired and no longer spawned (`pipeline.py`/`trigger_reviews.py` no
     longer reference it).
  5. Smoke-run of every maintained entry point passes.
- **Risk:** MED.
- **Effort:** L.
- **Needs:** S2.
- **Blocks:** S4 (instructions reference the CLI), S5 (site/knowledge subcommands), S6.

### Stage 4 — instruction-surfaces (rec 6)

- **id:** `instruction-surfaces`
- **name:** Instruction surfaces
- **Delivers:** rec 6 (one canonical instruction source). Absorbs the doc-drift half of WS-10
  (module/script/test counts and stale notes corrected in the canonical source, then regenerated).
- **Scope (files/dirs touched):**
  - new `agent_config/` — the canonical, hand-edited instruction source (mental model, module map,
    skills, rules, CLI surface).
  - `.opencode/` and `.claude/` → **generated** copies, never hand-edited.
  - a generation script + guard test `generated_surfaces_match` (fails on drift).
- **Inputs:** S3 CLI command surface; `.opencode/instructions/mental-model.md`; the S1 package map.
- **Outputs:** `agent_config/` canonical source; regenerated `.opencode/` + `.claude/`; drift guard
  test.
- **Acceptance criteria:**
  1. Exactly one canonical instruction source (`agent_config/`).
  2. `.opencode/` + `.claude/` are byte-identical to the generated output of `agent_config/`.
  3. `generated_surfaces_match` test fails on drift.
  4. No `.opencode/`/`.claude/` file is hand-edited after this stage (enforced by the guard test +
     review rule).
- **Risk:** LOW.
- **Effort:** M.
- **Needs:** S3.
- **Blocks:** S6.

### Stage 5 — apps-public-identity-realignment (rec 9, 5)

- **id:** `apps-public-identity-realignment`
- **name:** apps/ + public-identity realignment
- **Delivers:** rec 9 (website + control room as applications), and the rec-5 *public-identity* half
  (README re-framed from "perturbation instrument" to "research operating system").
- **Scope (files/dirs touched):**
  - `admin/{server,design_sessions,claude_agents_client,opencode_client}.py` + `admin/static/*` →
    `apps/control-room/`.
  - `firebase/public/` → `apps/website/`.
  - `README.md` re-framed around the six systems (measurement apparatus · experiment platform ·
    agent execution runtime · knowledge/augmentation · emerging control · research/publication).
  - `firebase/CONTEXT.md` → `apps/website/CONTEXT.md`; dual-Firebase deploy notes preserved.
- **Inputs:** S1 import map (apps import from `src/agentic_dynamics/`); S2 data paths; S3 CLI
  (`site build`, `knowledge ingest`, `registry query`).
- **Outputs:** `apps/{website,control-room}`; re-framed README; re-pointed imports; preserved
  dual-Firebase invariant.
- **Acceptance criteria:**
  1. `admin/server.py` + `firebase/public/` live under `apps/` and import from
     `src/agentic_dynamics/` (not the reverse).
  2. No domain rules inside `apps/` (rec 8 enforced by the S1 lint).
  3. Domain results → publication data → website, not interleaved with runtime architecture.
  4. Dual-Firebase invariant holds: `firebase deploy --only hosting` targets BOTH
     `ai-finops-rulebook` and `agentic-dynamics` (canonical + mirror, same `public/`).
  5. README describes the research operating system; the perturbation instrument is *one* system,
     not the sole framing.
- **Risk:** MED (import re-points + Firebase deploy path moves).
- **Effort:** M.
- **Needs:** S1, S2, S3.
- **Blocks:** S6.

### Stage 6 — consolidation-verification-release (all)

- **id:** `consolidation-verification-release`
- **name:** Consolidation verification release
- **Delivers:** all nine recs — the release gate.
- **Scope (files/dirs touched):** repo-wide verification; `experiments/specs/STATUS.md` +
  `index.json` refresh; `data_manifest.json` regen; both Firebase deploys.
- **Inputs:** S0–S5 outputs.
- **Outputs:** `docs/consolidation/verification.md` (PASS/FAIL per check); green full suite; synced
  dual-Firebase deploys.
- **Acceptance criteria:**
  1. Coverage proof: all 9 recs → ≥1 stage; all WS-01..10 dispositioned (§5); zero orphans.
  2. `pytest tests/ -m "not external"` green; dependency lint green; every guard test (classification,
     anti-resurrection, generated-surfaces-match) green.
  3. `compile_spec` gate passes on every committed spec (load-bearing rule intact end-to-end).
  4. Invariant audit: Redis isolation (6380 queue DB1 + KB DB2; 6379 sandbox), dual Firebase, CAP
     frozen-not-deleted, no `_results_summary.json` resurrected as a live source.
  5. Both Firebase hosts deployed in sync (`ai-finops-rulebook` + `agentic-dynamics`).
- **Risk:** LOW (verification; the riskiest work is upstream of S6).
- **Effort:** S.
- **Needs:** S0–S5.
- **Blocks:** — (post-consolidation CAP implementation unblocks; the deferred workstreams resume
  inside the new structure).

---

## 5. refactor_master_plan workstream disposition (WS-01..10)

Supersession, not duplication. Each of the ten functional workstreams from
`docs/refactor/plan.md` (produced on `feature/refactor-master-plan`) is folded into a consolidation
stage, deferred into the new structure, or retired — exactly once, no orphan, no duplicate execution.

| WS | refactor spec | Disposition | Lands in | Note |
|---|---|---|---|---|
| WS-01 | `refactor_01_retire_dead_code` | **FOLDED** | S1 | Rec 7's deprecated-module deletion IS WS-01; done inside the package move (`legacy/` quarantine or delete). |
| WS-02 | `refactor_02_kb_branch_integration` | **DEFERRED** | post-consolidation (`knowledge/`) | Functional KB work (`source_type` typing); runs inside `src/agentic_dynamics/knowledge/`, not re-planned. |
| WS-03 | `refactor_03_kb_write_path` | **DEFERRED** | post-consolidation (`knowledge/`) | Functional `kb_producer` helper; runs inside the new structure. |
| WS-04 | `refactor_04_labbook_registry_repoint` | **DEFERRED** | post-consolidation (`reporting/`) | Functional data-integrity work; its *anti-resurrection guard-test pattern* is promoted into S2's classification test + S6's invariant audit, but the repoint itself is deferred. |
| WS-05 | `refactor_05_compiler_matrix_wire` | **DEFERRED** | post-consolidation (`experiment/`+`control/`) | Functional compiler work (strangler wire-in); runs inside the new structure. |
| WS-06 | `refactor_06_compiler_compare_evaluate` | **DEFERRED** | post-consolidation | Functional; runs inside the new structure. |
| WS-07 | `refactor_07_compiler_adapt_campaign` | **DEFERRED** | post-consolidation | Functional; runs inside the new structure. |
| WS-08 | `refactor_08_admin_step_sample` | **DEFERRED** | post-consolidation (`apps/control-room`) | Functional admin dedup; runs inside `apps/control-room` after S5 moves it. |
| WS-09 | `refactor_09_review_worker` | **FOLDED** (retire) / **DEFERRED** (rewire) | S3 (retire) | The `review_worker.py` retirement is S3 script classification; the deeper `pipeline.py`→`review_all.py` shared-runner rewire is deferred. |
| WS-10 | `refactor_10_syspath_archive_docs` | **FOLDED** (sys.path + archive) / **RETIRED** (doc drift) | S1 (sys.path), S3 (archive) | The ~55-file `sys.path` bootstrap folds into S1's `_bootstrap.py`; the 7 one-time backfill archives fold into S3; the *doc-count drift corrections* are retired — superseded by S0's `ARCHITECTURE.md` + S4's regenerated instruction surfaces. |

**Disposition tally:** folded 3 (WS-01, WS-09, WS-10), deferred 7 (WS-02..08), retired 1 sub-part
(WS-10 doc-drift). The deferred workstreams are **not cancelled** — they resume post-consolidation
as standalone specs running *inside* `src/agentic_dynamics/`, with their `depends_on` re-pointed at
the consolidation stages (their existing `refactor_<n>_*.yaml` specs remain the content source; the
`stage_specs` phase records the supersession in each stage's `question` text).

---

## 6. Context Abstraction Plane freeze (rec 1)

**Where the freeze lands:**

1. **Spec index note.** `experiments/specs/context_abstraction_implement.yaml` gains a lifecycle
   note — **PAUSED, not deleted, not superseded**: `status:` carries a `paused` marker (with
   `freeze_reason: consolidation_release/stage_map` and `resume_after: consolidation S6`) so
   `spec_status.py` renders it distinctly in `STATUS.md`/`index.json` (the index must never show it
   as `active`/runnable). The design survives; only execution pauses.
2. **Reserved package homes.** `ARCHITECTURE.md` (S0) declares the structural homes the CAP
   components will occupy, so post-consolidation implementation is **drop-in**. Reservation maps
   I0–I7 (`docs/context_abstraction/design.md` §9) onto the S1 package layout:

   | CAP increment | Component | Reserved home |
   |---|---|---|
   | I0 | Fact schema + predicate registry (`CanonicalFact`, `FACT_PREDICATES`, `EPISTEMIC_MAP`, `verify_chain`) | `src/agentic_dynamics/control/facts.py` |
   | I1 | `spec_status/v1` reducer | `src/agentic_dynamics/control/reducers/` |
   | I2 | Ledger reducers (`attempt_facts/v1`, `job_facts/v1`) | `src/agentic_dynamics/control/reducers/` |
   | I3 | Workflow reducer (`workflow_facts/v1`, `policy_facts/v1`) | `src/agentic_dynamics/control/reducers/` |
   | I4 | Context Compiler (read-only) | `src/agentic_dynamics/control/context_compiler.py` |
   | I5 | Fact contracts in the spec gate (`FactRequirement`, `validate_fact_contracts`) | `src/agentic_dynamics/core/contracts.py` |
   | I6 | Controller + validator, shadow mode | `src/agentic_dynamics/control/rules.py` + `control/validator.py` + `control/decisions.py` |
   | I7 | Apply `route` for one opted-in spec | `src/agentic_dynamics/control/` (seam in `run_workflow`) |

   Reserved homes are **empty placeholders** (a module docstring + `# reserved for CAP I<n>`), so a
   later CAP implementation drops in without re-planning the package map. The dependency-direction
   lint (S1) must permit `control` to import `core` and `knowledge` — but nothing imports `control`
   except the reserved seam, consistent with the "control consumes facts" rule (rec 8).

3. **The gate stays closed.** `context_abstraction_implement` is the one spec explicitly *excluded*
   from execution until S6 completes; the stage order never schedules it, and S6's invariant audit
   asserts it is still PAUSED (not deleted).

---

## 7. Global invariants (asserted at every stage boundary + finally at S6)

1. `pytest tests/ -m "not external"` green at every stage's verify phase.
2. `compile_spec` passes on every committed spec — the `requires`/`produces` gate is untouchable.
3. Redis isolation: `finops-queue` DB 1 (telemetry) + KB stream DB 2 on **6380**; story-agent
   sandbox on **6379**; the framework queue is never on 6379.
4. Dual Firebase: `ai-finops-rulebook` (canonical) + `agentic-dynamics` (mirror), same `public/`,
   always deployed together.
5. CAP frozen-not-deleted; reserved homes present but unimplemented.
6. No `_results_summary.json` resurrected as a live build/lab input (data-integrity boundary).
7. Deprecated modules retired only inside S1's package move (never before their last importer is
   re-pointed by the shim).

**Stop-the-line conditions** (any ⇒ halt, do not advance to the next stage): a non-green pytest
run; a `compile_spec` gate failure; a Redis/dual-Firebase invariant violation; a workstream executed
in two places (duplicate) or none (orphan); a `_results_summary.json` resurrection.

---

## 8. Coverage proof (feeds the `verify` phase)

- **All 9 recommendations** map to ≥1 stage (§2) — none orphaned.
- **All WS-01..10** map to exactly one disposition (§5) — none orphaned, none duplicated.
- **CAP freeze** lands in the spec index note + 7 reserved package homes (§6) — rec 1 satisfied
  without deleting the design.
- **The six systems** (critique §"What the repository actually contains") each have a home in the S1
  package map: measurement → `measurement/`, experiment platform → `experiment/`, execution runtime →
  `runtime/` + `adapters/`, knowledge/augmentation → `knowledge/`, control → `control/`, research/
  publication → `reporting/` + `apps/`.
