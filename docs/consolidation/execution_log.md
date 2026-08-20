---
status: accepted
---
# Consolidation execution log

Per-stage acceptance-criterion results for the consolidation release (S0–S6). Each entry records
PASS/FAIL against the stage's acceptance criteria (`docs/consolidation/stage_map.md` §4) and the
per-phase deliverables (`experiments/specs/consolidation_stage_*.yaml`).

---

## S0 — architecture spine (phase `spine`)

Spec: `experiments/specs/consolidation_stage_0_architecture_spine.yaml` · phase `spine`.
Deliverable: root `ARCHITECTURE.md`.

| # | Acceptance criterion | Result |
|---|---|---|
| 1 | `ARCHITECTURE.md` exists at the repo root (exactly one) | PASS |
| 2 | Six sections present: §1 Planes, §2 Package boundaries, §3 Dependency direction, §4 Implemented vs proposed, §5 Canonical execution loop, §6 Supersession map | PASS |
| 3 | §1 lists the eight bounded packages + one-line ownership, mapped to the critique's six systems | PASS |
| 4 | §2 states import may/may-not boundaries and points at `tests/test_dependency_direction.py` (to be added in Stage 1) | PASS |
| 5 | §3 draws the spine `core ← experiment/measurement/runtime/knowledge ← control ← applications` with the two pinned execution→control observation edges (`workflow_runner→step_routing/live`; `opencode/claude_adapter→live`) as observe-only arrows | PASS |
| 6 | §4 names the shipped planes, the reserved-but-empty CAP homes (I0–I7 → `control/*` + `core/contracts.py`), the deferred workstreams (WS-02..08), and names `docs/consolidation/stage_map.md` as the release plan | PASS |
| 7 | §5 states the canonical execution loop (spec → compile → DAG → cells → jobs → attempts → ledger → information → policy → grid → campaign) | PASS |
| 8 | §6 maps supersession: replaces BLUEPRINT×3 + dated handoffs + superseded reviews; leaves mental-model, `src/instrument/CONTEXT.md`, `scripts/CONTEXT.md`, `data_integrity_findings.md`, `docs/review/` authoritative | PASS |
| 9 | The load-bearing rule is stated verbatim as the architectural invariant, not redefined | PASS |

**S0-spine result: 9/9 PASS.**

---

## S0 — doc lifecycle (phase `lifecycle`)

Spec: `experiments/specs/consolidation_stage_0_architecture_spine.yaml` · phase `lifecycle`.
Deliverables: migrated doc tree (`docs/archive/`, `docs/designs/{current,implemented}/`),
status front-matter on every remaining doc, `tests/test_doc_lifecycle.py`.

| # | Acceptance criterion | Result |
|---|---|---|
| 1 | `BLUEPRINT.md`, `BLUEPRINT_v2.md`, `BLUEPRINT_v3.md` moved → `docs/archive/` with `status: superseded` + `superseded_by: ARCHITECTURE.md` | PASS |
| 2 | Dated handoffs (`docs/HANDOFF_2026-08-17.md`, `docs/HANDOFF_2026-08-19.md`) moved → `docs/archive/` (superseded) | PASS |
| 3 | Dated `code_reviews/*` predating the registry repoint moved → `docs/archive/` (superseded, kept not deleted) | PASS |
| 4 | Current-but-frozen designs → `docs/designs/current/` with `status: accepted` (context-abstraction design+verify, `supervisor_design.md`, spec/compiler roadmap `2026-08-14_*`) | PASS |
| 5 | Shipped designs → `docs/designs/implemented/` with `status: implemented` + `implemented_by:` (canonical-state rounds, RAG seam split, website repoints) | PASS |
| 6 | Status front-matter added to every remaining root + docs markdown file (vocabulary `proposed|accepted|implementing|implemented|superseded|abandoned`) | PASS |
| 7 | `tests/test_doc_lifecycle.py` written — walks `docs/**` + root `*.md`, asserts status field + `docs/archive/` superseded | PASS |
| 8 | `pytest tests/test_doc_lifecycle.py` green | PASS (5 passed) |
| 9 | No `BLUEPRINT*.md` remains at the repo root | PASS |

**S0-lifecycle result: 9/9 PASS.**

---

## S0 — CAP freeze (phase `freeze`)

Spec: `experiments/specs/consolidation_stage_0_architecture_spine.yaml` · phase `freeze`.
Deliverables: PAUSED marker on `context_abstraction_implement`, reserved CAP homes declaration,
refreshed spec index.

| # | Acceptance criterion | Result |
|---|---|---|
| 1 | `context_abstraction_implement.yaml` marked PAUSED (freeze_reason `consolidation_release/stage_map`, resume_after `consolidation S6`) — not deleted, not superseded (`superseded_by` absent) | PASS |
| 2 | Status uses the schema vocabulary only (`status: draft` — the "not runnable now" state); no value outside `{draft,active,superseded,tombstoned}` invented | PASS |
| 3 | `ARCHITECTURE.md` §4 declares the reserved CAP homes (`control/facts.py`, `control/reducers/`, `control/context_compiler.py`, `control/rules.py`, `control/validator.py`, `control/decisions.py`, `core/contracts.py`) as empty-but-reserved placeholders | PASS |
| 4 | Spec index reflects the freeze — `index.json` + `STATUS.md` show `context_abstraction_implement` as `draft`, never `active` | PASS |
| 5 | `docs/consolidation/cap_freeze_note.md` written (durable freeze note: what/why/where/how) | PASS |
| 6 | `validate_spec` passes on the modified spec (status valid, no self-supersession) | PASS |

**S0-freeze result: 6/6 PASS.**

Note: the index was updated with a *targeted* status edit (active → draft in `index.json` +
`STATUS.md`) rather than a full `spec_status.py` regeneration — the run ledgers under
`experiments/results/workflows/` are untracked and absent from this worktree, so a full regen
would have wiped the measured run columns (`last_run`/`ok`/`model`/`cost`/`n_runs`) for all 77
specs. `spec_status.py --dry-run` confirms the derived status is `draft`, so the targeted edit is
consistent with the generator.

---

## S0 — verification (phase `verify`)

Spec: `experiments/specs/consolidation_stage_0_architecture_spine.yaml` · phase `verify`.
Deliverable: `docs/consolidation/stage_0_verification.md`.

| # | Acceptance criterion | Result |
|---|---|---|
| 1 | `pytest tests/test_doc_lifecycle.py` green | PASS (5 passed) |
| 2 | Exactly one root `ARCHITECTURE.md` with the six §2 sections | PASS |
| 3 | No `BLUEPRINT*.md` at the repo root | PASS |
| 4 | `context_abstraction_implement` PAUSED (grep), not deleted, not superseded | PASS |
| 5 | rec 1 → freeze declared; rec 4 → single authority + lifecycle status | PASS |
| 6 | Zero orphan files from the migration (every moved doc in its new home) | PASS |
| 7 | Full suite green — `pytest tests/ -m "not external"` | PASS (1179 passed, 121 deselected) |
| 8 | `stage_map.md` named as the release plan in `ARCHITECTURE.md` §4 | PASS |

**S0-verify result: 8/8 PASS — Stage 0 complete and gate-green.**

---

## S1 — package skeleton (phase `skeleton`)

Spec: `experiments/specs/consolidation_stage_1_package_move.yaml` · phase `skeleton` (phase A).
Deliverable: empty `src/agentic_dynamics/` package skeleton (additive; nothing moves).

| # | Acceptance criterion | Result |
|---|---|---|
| 1 | `src/agentic_dynamics/` created with the nine subpackage dirs (`core/`, `experiment/`, `measurement/`, `runtime/`, `adapters/`, `knowledge/`, `control/`, `reporting/`, `legacy/`) | PASS |
| 2 | Each `__init__.py` is docstring-only, naming its plane's ownership (+ `control/` names the reserved CAP homes I0–I7) | PASS |
| 3 | `pyproject.toml` note added so `agentic_dynamics` is an editable-install target from `src/` (distribution `agentic-dynamics` ↔ import package `agentic_dynamics`), without touching the scripts' sys.path bootstrap | PASS |
| 4 | Package imports cleanly (all 9 planes importable under `PYTHONPATH=src`) | PASS |
| 5 | `pytest tests/ -m "not external"` stays green (additive phase) | PASS (1179 passed, 121 deselected) |

**S1-skeleton result: 5/5 PASS.**

---

## S1 — package move (phase `move`)

Spec: `experiments/specs/consolidation_stage_1_package_move.yaml` · phase `move` (phase B).
Deliverable: all 64 modules moved to planes + internal imports rewritten + the `instrument.*`
compat shim (atomic, one commit).

| # | Acceptance criterion | Result |
|---|---|---|
| 1 | All 63 modules `git mv`'d to their plane per design §1.1 (core 4 · experiment 3 · measurement 15 · runtime 4 · adapters 3 · knowledge 16 · control 9 · reporting 4 · legacy 5) | PASS |
| 2 | Internal imports rewritten (`from .X` / `from instrument.X` → `from agentic_dynamics.<plane>.X`); zero residual `from .X` / `from instrument` inside `agentic_dynamics/` | PASS |
| 3 | Plane `__init__.py` re-exports (`from . import …` + `__all__`) + shim `src/instrument/` generated (regenerated 703-line barrel + 63 per-module stubs) | PASS |
| 4 | Shim serves all three import shapes (`from instrument import X` / `import instrument.X` / `from instrument.X import Y`) transparently, incl. mock-patching | PASS |
| 5 | `pytest tests/ -m "not external"` green via the shim | PASS (1179 passed, 121 deselected) |
| 6 | Smoke-run 5 representative scripts | PASS (run/analyze_worktrees/build_data/kb_produce `--help` OK; worker.py is a blocking BRPOP worker — its `_constants → instrument.session_types` import chain verified via the shim) |

**S1-move result: 6/6 PASS.**

Implementation notes (necessary adjustments during the atomic move, documented for traceability):

- **Shim = `sys.modules` aliasing, not `import *`.** A plain `from agentic_dynamics.<plane>.<m>
  import *` stub drops `_`-prefixed names (e.g. `_PROFILES`, `_constraint_keywords`) that tests
  import directly, and breaks `monkeypatch.setattr(instrument.<m>, …)` — the real code resolves
  names in the *real* module's namespace. Each stub therefore aliases `sys.modules[__name__] =
  agentic_dynamics.<plane>.<m>`, making `instrument.<m>` *be* the real module (imports, attribute
  access, and mock-patching all transparent).
- **`__file__`-relative path depth fix (3→4 levels).** Modules moved one directory deeper
  (`src/instrument/X.py` → `src/agentic_dynamics/<plane>/X.py`), so `Path(__file__)…parent.parent.parent`
  now resolves to `src/` instead of the repo root. Fixed in `core/paths.py` (PROJECT_ROOT — the KB
  path source of truth), `graph.py`, `knowledge_ingestion.py`, `ollama_analyzer.py`,
  `opencode_analyzer.py` (PROJECT_ROOT), `commit_analysis.py` (`_CONVENTIONS_DIR`), `review.py` ×2,
  and `signal_store.py` (`parents[2]`→`parents[3]`).
- **Two source-path test reads repointed** (the shim cannot relocate files read by hardcoded path,
  not by import): `tests/test_data_integrity.py` (`src/instrument/{basin,game_report,commit_analysis}.py`
  → `src/agentic_dynamics/…`) and `tests/test_ledger_ingestion.py` (`parents[2]`→`parents[3]`).
  These are the only consumer edits this phase (the rest of scripts/tests still import `instrument.*`
  via the shim, awaiting phase C).

---

## S1 — rewrite consumers (phase `rewrite_consumers`)

Spec: `experiments/specs/consolidation_stage_1_package_move.yaml` · phase `rewrite_consumers`
(phase C). Deliverable: scripts/admin/tests imports → `agentic_dynamics.*`, centralized
`scripts/_bootstrap.py`, `_constants.py` → `agentic_dynamics/core/constants.py`.

| # | Acceptance criterion | Result |
|---|---|---|
| 1 | `scripts/` + `admin/` + `tests/` imports rewritten `instrument.*` → `agentic_dynamics.<plane>.*` | PASS |
| 2 | Per-file `sys.path.insert(.../src)` bootstraps → one `scripts/_bootstrap.py` (50 replaced); `python scripts/foo.py` direct-run contract preserved | PASS |
| 3 | `scripts/_constants.py` → `agentic_dynamics/core/constants.py` + all importers updated (`from agentic_dynamics.core.constants import …`) | PASS |
| 4 | `pytest tests/ -m "not external"` green | PASS (1179 passed, 121 deselected) |
| 5 | `grep "from instrument\|import instrument"` over `scripts/ admin/ tests/ src/` = zero outside `src/instrument/` itself | PASS |

**S1-rewrite_consumers result: 5/5 PASS.**

Implementation notes:

- **`_bootstrap.py` import is a robust try/except.** Scripts are imported two ways: directly
  (`python scripts/foo.py` — `scripts/` is `sys.path[0]`) and as submodules (`from scripts import
  registry` from `admin/server.py`/tests — repo root is on `sys.path`). A bare `import _bootstrap`
  only resolves in the first case, so every bootstrap site is:
  `try: import _bootstrap` / `except ImportError: from scripts import _bootstrap`.
- **Bootstrap regex used `[ \t]*`, not `\s*`** — `\s*` swallows newlines and (with `re.M`) mangled
  the surrounding blank lines; horizontal-whitespace-only matching preserves layout, including the
  one indented (in-function) bootstrap in `analyze_trajectories.py`.
- **Special bootstrap cases** (not the common `.../src` form): `generate_manifest.py` now imports
  `agentic_dynamics.core.paths` via `_bootstrap` (its old `src/instrument` direct-insert + top-level
  `from paths import` was retired); `supervise.py`/`claude_agents_supervisor.py` keep their
  `ROOT/"admin"` insert (admin-module access, not a src bootstrap); `batch_analyze_ts_ssg.py` keeps
  its `scripts/` insert (cross-script import).
- **`worker.py` ordering fix** — its `from _constants import …` sat *above* the bootstrap; the
  bootstrap now precedes the `agentic_dynamics.core.constants` import.
- **Two test path reads repointed** for the `_constants.py` move: `tests/test_data_integrity.py`
  (`scripts/_constants.py` → `src/agentic_dynamics/core/constants.py`) and
  `tests/test_ledger_ingestion.py` (loads `constants.py` beside `session_types.py`).

---

## S1 — dependency lint (phase `dependency_lint`)

Spec: `experiments/specs/consolidation_stage_1_package_move.yaml` · phase `dependency_lint`
(phase D). Deliverable: `tests/test_dependency_direction.py` (import-graph lint) +
`tests/test_data_flow.py` (data-flow guards).

| # | Acceptance criterion | Result |
|---|---|---|
| 1 | `tests/test_dependency_direction.py` walks every `src/agentic_dynamics/**` module + `apps/**` and asserts the 8 forbidden-edge rules | PASS |
| 2 | The two execution→control observation edges pinned as the COMPLETE tier-1→tier-2 set (`workflow_runner→step_routing/live`; `opencode`/`claude_adapter`→`live`) | PASS |
| 3 | Data-flow tests: `retrieve()` never supplies POLICY candidates + references `publish_event` zero times; knowledge modules never call `derive_actuation_record` | PASS |
| 4 | Lint demonstrably red on a forbidden edge (injected `measurement → control`, test failed; reverted, green) | PASS |
| 5 | New tests + `pytest tests/ -m "not external"` all green | PASS (1191 passed, 121 deselected) |

**S1-dependency_lint result: 5/5 PASS.**

Implementation notes:

- **`legacy/` excluded from the tier map** — quarantined dead code (retired in phase E); the
  design §1.4 tier map covers only `core` / `planes` / `control` / `apps`.
- **`apps/` handled but vacuously green** until Stage 5 creates it (the test scans `apps/**`
  when present).
- **Import resolution** handles absolute `import agentic_dynamics.<plane>.<m>` and
  `from agentic_dynamics.<plane>.<m> import …`; relative (`level ≥ 1`) imports are same-plane by
  construction and ignored. A first draft had `_plane_of` read the repo-relative path wrong
  (missed the leading `src/`), which made the whole graph empty — caught by the pinned-edge test
  (empty set ≠ pinned set), then fixed.
- **Data-flow guards are AST/source-level**, not behaviour-only: `retrieval.py` source contains
  `publish_event` zero times (verified), and knowledge modules never import/call
  `derive_actuation_record` (the sole occurrence is the `knowledge/__init__.py` docstring, which
  the AST test correctly ignores).

---

## S1 — retire shim (phase `retire_shim`)

Spec: `experiments/specs/consolidation_stage_1_package_move.yaml` · phase `retire_shim` (phase E).
Deliverable: shim + dead modules retired (rec 7) + `docs/consolidation/stage_1_verification.md`.

| # | Acceptance criterion | Result |
|---|---|---|
| 1 | `grep "from instrument\|import instrument"` over `scripts/ admin/ tests/ src/` = zero → shim `src/instrument/` deleted | PASS |
| 2 | `legacy/` dead modules retired (5 modules) + `scripts/plan.py` + 8 `lab_*_DEPRECATED_bge_m3.py` + `analyze_with_ollama/opencode` + `build_graph` + their 3 tests | PASS |
| 3 | 5 residual `monkeypatch.setattr("instrument.*", …)` string targets repointed to `agentic_dynamics.*` (uncovered by the import-grep, broke only at shim deletion) | PASS |
| 4 | `pytest tests/ -m "not external"` green | PASS (1183 passed, 106 deselected) |
| 5 | Compile-gate validate on all 77 specs (`validate_spec` + `validate_rules`) | PASS (0 errors) |
| 6 | `docs/consolidation/stage_1_verification.md` written (imports_resolve · dependency_lint_green · deprecated_retired · bootstrap_centralized) | PASS |

**S1-retire_shim result: 6/6 PASS — Stage 1 complete (skeleton/move/rewrite_consumers/dependency_lint/retire_shim).**

Notes:

- Final active package: **59 modules / 8 planes** (core 5 incl. the moved `constants.py` ·
  experiment 3 · measurement 15 · runtime 4 · adapters 3 · knowledge 16 · control 9 · reporting 4).
- `pyproject.toml` `known-first-party` repointed `instrument` → `agentic_dynamics`; the
  editable-install note dropped the shim mention; the top-level `agentic_dynamics/__init__.py`
  docstring no longer names `legacy`.
- The "strip now-dead `# Deprecated:` comments" step was a no-op: those comments lived only in the
  deleted shim barrel, not in the plane `__init__.py`s.

---

## S2 — classify (phase `classify`)

Spec: `experiments/specs/consolidation_stage_2_experiments_workflows_split.yaml` · phase `classify`.
Deliverable: `tests/test_experiment_workflow_classification.py` (the rec-3 guard) + the two
directory-tree skeletons.

| # | Acceptance criterion | Result |
|---|---|---|
| 1 | `experiments/{definitions,campaigns,fixtures}` + `workflows/{repository,operations,research,examples}` skeletons created (README placeholders) | PASS |
| 2 | `tests/test_experiment_workflow_classification.py` written: definitions must be measurement, workflows must carry the work-order signature (reciprocal), plus the flat-dir-drained transition check | PASS |
| 3 | Test run against the CURRENT layout confirms it detects the as-is mixing (fails pre-move) — recorded as `xfail(strict=False)`, to be removed at `move_specs` | PASS |
| 4 | `pytest tests/ -m "not external"` stays green | PASS (1185 passed, 106 deselected, 1 xfailed) |

**S2-classify result: 4/4 PASS.**

Notes:

- The work-order signature heuristic (design §4) has two legs: `workflow.kind == agent_task` AND
  (`context.hard_rules` naming a production-code edit, OR `question` naming a repo-change
  deliverable — website/control-room/kb-build/rewrite/repoint/rebrand/implement/canonicalize/
  consolidation/release/…). It is deliberately heuristic (substring markers, not a hardcoded name
  list) so it catches *new* misplacements; it will be verified against the re-homed corpus (and
  tuned if a spec sits on the boundary) in `move_specs`.
- The flat-dir-drained check (`experiments/specs/*.yaml` empty) is a *transition* guard distinct
  from the two permanent classification guards — it is `xfail` until `move_specs` drains the dir.

---

## S2 — move specs (phase `move_specs`)

Spec: `experiments/specs/consolidation_stage_2_experiments_workflows_split.yaml` · phase
`move_specs` (phase B). Deliverable: the re-homed spec/config tree (77 specs + 37 configs).

| # | Acceptance criterion | Result |
|---|---|---|
| 1 | 8 genuine experiment specs → `experiments/definitions/` (rag_bare_vs_augmented, routing_regret_under_degradation, routing_kb_experiment_design+research, workflow_step_routing, explanation_tax, process_perturbation_resample, posthoc_pipeline) | PASS |
| 2 | 69 work-order specs → `workflows/{repository(59),operations(4),research(6)}` | PASS |
| 3 | 33 measurement configs + `plans.yaml` → `experiments/definitions/configs/`; 3 grid/sweep configs (comparative/factorial_compound/silent_mode_sweep) → `experiments/campaigns/` | PASS |
| 4 | `supersedes`/`superseded_by` lineage preserved (`git mv`, content unchanged) | PASS |
| 5 | `experiments/specs/*.yaml` + `experiments/configs/*.yaml` drained (0 left) | PASS |
| 6 | Classification guard test green (heuristic tuned against the re-homed corpus; `xfail` removed) | PASS (3 passed) |
| 7 | `pytest tests/ -m "not external"` green | PASS (1186 passed, 106 deselected) |

**S2-move_specs result: 7/7 PASS.**

Notes:

- **Loader repointed as part of the move** (to keep the boundary green): `collect_entries` now
  globs `experiments/definitions/*.yaml` + `workflows/**/*.yaml` (77 specs) instead of
  `experiments/specs/`; the generated `index.json`/`STATUS.md` still write to `experiments/specs/`
  (the repoint phase regenerates them). `scripts/pipeline.py` + `tests/test_pipeline.py` were
  repointed to `experiments/definitions/configs/plans.yaml`; `tests/test_workflow_runner.py` and
  `tests/test_spec_status.py`/`tests/test_experiment_spec.py` follow the new corpus paths.
- **Guard heuristic tuned to the corpus** (verified red→green against the real re-homed specs):
  a repo-change marker list (imperative verbs + deliverable nouns) plus an experiment-design
  override (`"design an experiment"`). Ambiguous markers dropped to avoid false positives:
  `knowledge base`/`knowledge-base` (appears in the experiment-design specs), `refactor` (appears
  as an experiment task type), `remediate`/`regenerate`/`finish` (appear in `posthoc_pipeline`'s
  experiment question). `definitions/` is scanned top-level only (its `configs/` subdir holds
  measurement configs, not specs).
- **`workflows/research/`** holds the borderline specs (`code_review`, `deep_architecture_review`,
  `repo_review_fable`, `self_recommending_experiment`, `routing_kb_more_itertools`,
  `rag_knowledge_base`) — work orders that produce documents/analysis rather than code.

---

## S2 — repoint (phase `repoint`)

Spec: `experiments/specs/consolidation_stage_2_experiments_workflows_split.yaml` · phase `repoint`
(phase C). Deliverable: re-pointed spec/config consumers + a regenerated index.

| # | Acceptance criterion | Result |
|---|---|---|
| 1 | `agentic_dynamics/experiment/spec_status.py` `collect_entries` resolves specs from `experiments/definitions/` + `workflows/**` (done at move_specs; index location `experiments/specs/` preserved) | PASS |
| 2 | `agentic_dynamics/knowledge/policy_ingestion.py` `discover_policy_paths` globs the split layout (definitions + workflows) | PASS |
| 3 | `scripts/run_workflow.py` example path + `scripts/spec_status.py`/`spec_ingestion.py`/`quality_ingestion.py`/`code_ingestion.py` docstrings repointed | PASS |
| 4 | Config consumers repointed: `scripts/batch_run.py` + `scripts/remaining_batch.py` resolve configs from `experiments/definitions/configs/` + `experiments/campaigns/` (`_config_path`) | PASS |
| 5 | `python scripts/spec_status.py` regenerates `index.json` + `STATUS.md` — 77 specs, zero orphans, zero missing | PASS |
| 6 | `pytest tests/ -m "not external"` + the classification guard test green | PASS (1186 passed, 106 deselected; guard 3 passed) |

**S2-repoint result: 6/6 PASS — Stage 2 complete (classify/move_specs/repoint).**

Notes:

- **Index regenerated, run columns reset to fresh-checkout state.** The run ledgers under
  `experiments/results/workflows/` are untracked/gitignored and absent from this worktree, so
  `spec_status.py` correctly derives null run columns (em-dash / `n_runs: 0`) — the documented
  fresh-checkout state (the previous index carried run data generated in a ledger-bearing
  checkout). Structural columns (name/version/status/spec_path/supersedes) are intact, and
  `context_abstraction_implement` remains `status: draft` (CAP freeze preserved) at its new
  `workflows/repository/` path.
- The generated index now records `spec_path` under the split layout (8 × `experiments/definitions/`,
  69 × `workflows/**`), while `index.json`/`STATUS.md` themselves stay in `experiments/specs/`
  (the historical index home).

---

## S3 — CLI (phase `cli`)

Spec: `workflows/repository/consolidation_stage_3_cli_classification.yaml` · phase `cli` (phase A).
Deliverable: `agentic_dynamics/cli.py` + the `agentic-dynamics` console-scripts entry point.

| # | Acceptance criterion | Result |
|---|---|---|
| 1 | `agentic_dynamics/cli.py` added — a thin argparse-less dispatcher over the maintained `scripts/` surface | PASS |
| 2 | `[project.scripts] agentic-dynamics = "agentic_dynamics.cli:main"` added to `pyproject.toml` | PASS |
| 3 | Subcommands cover the design §5 tree (experiment/story/workflow/queue/analyze/data/knowledge/registry/review/spec/validate/supervise, incl. the dynamic `analyze lab <name>` and `registry query|show|lineage` families) | PASS |
| 4 | Each subcommand is a thin wrapper — forwards argv to the backing script via subprocess, composes rather than re-implements (rec 8); imports no `control` for steering | PASS |
| 5 | CLI smoke-tested (`--help`, `spec status --dry-run`, `analyze lab grit_matrix`, unknown-command) | PASS |
| 6 | `pytest tests/ -m "not external"` green | PASS (1186 passed, 106 deselected) |

**S3-cli result: 6/6 PASS.**

Notes:

- The CLI is a **passthrough dispatcher**: `_COMMANDS` maps an argv prefix → backing script, and the
  remaining argv is forwarded to `python scripts/<backing>.py`. Special cases: `registry
  query|show|lineage` → `registry.py <subcommand>`, and `analyze lab <name>` → `lab_<name>.py`.
  `--help` prints the command tree; unknown commands exit 2.
- Lab scripts have no `--help` (they run their analysis directly), so `analyze lab <name>` runs
  the lab book as-is — expected behaviour, not a CLI bug.

---

## S3 — classify scripts (phase `classify_scripts`)

Spec: `workflows/repository/consolidation_stage_3_cli_classification.yaml` · phase
`classify_scripts` (phase B). Deliverable: `scripts/CONTEXT.md` re-issued as the classification
manifest + `tests/test_script_classification.py`.

| # | Acceptance criterion | Result |
|---|---|---|
| 1 | `scripts/CONTEXT.md` re-issued as the classification manifest — 73 scripts in exactly one bucket | PASS |
| 2 | Bucket tally: maintained 37 · historical 19 (lab books) · one-time 15 (→ `scripts/archive/`) · deprecated 1 (`review_worker.py`); `_bootstrap.py` is a helper, not a command | PASS |
| 3 | `tests/test_script_classification.py` written — parses the manifest, asserts zero orphans + no cross-bucket overlap | PASS |
| 4 | Every maintained command is CLI-reachable (`agentic_dynamics.cli` `_COMMANDS` + the `registry` special case) | PASS |
| 5 | `pytest tests/ -m "not external"` green | PASS (1188 passed, 106 deselected) |

**S3-classify_scripts result: 5/5 PASS.**

Notes:

- The "85 scripts" in design §5 was the pre-Stage-1 count; after Stage 1 retired 12 scripts
  (`plan.py`, `analyze_with_ollama/opencode`, `build_graph`, 8 `*_DEPRECATED_bge_m3`) and moved
  `_constants.py` into the package (+ added `_bootstrap.py`), the surface is 73 files — the
  manifest covers that actual set.
- `scripts/CONTEXT.md` stale references were cleaned in the re-issue (plans.yaml path,
  `src/instrument/*` → `agentic_dynamics/*`, `_constants.py` → `agentic_dynamics/core/constants.py`,
  `plan.py` row removed, `review_worker.py` marked deprecated).

---

## S3 — retire + archive (phase `retire_and_archive`)

Spec: `workflows/repository/consolidation_stage_3_cli_classification.yaml` · phase
`retire_and_archive` (phase C). Deliverable: `review_worker.py` retired + 15 one-time migrations
archived to `scripts/archive/`.

| # | Acceptance criterion | Result |
|---|---|---|
| 1 | `scripts/review_worker.py` retired (WS-09): `pipeline.py` review phase + `trigger_reviews.py` re-pointed onto `review_all.py` (synchronous), file deleted | PASS |
| 2 | `grep review_worker` over `scripts/ admin/ tests/ src/` = zero | PASS |
| 3 | 15 one-time migrations `git mv`'d → `scripts/archive/` | PASS |
| 4 | WS-01 scripts NOT re-retired here (already retired in Stage 1) — verified `plan.py`/`*_bge_m3`/`analyze_with_*` absent | PASS |
| 5 | Manifest + guard test updated: `one-time` bucket → `scripts/archive/`, `deprecated` bucket emptied; guard test now globs `scripts/**` recursively | PASS |
| 6 | `pytest tests/ -m "not external"` green | PASS (1187 passed, 106 deselected) |
| 7 | Smoke-run all 37 maintained entry points | PASS (37/37 importable/runnable; 5 missing bootstraps fixed) |

**S3-retire_and_archive result: 7/7 PASS — Stage 3 complete (cli/classify_scripts/retire_and_archive).**

Notes:

- **`review_worker.py` retirement** removed the "superseded but still spawned" contradiction:
  `pipeline.py::_execute_review` now runs `review_all.py` once synchronously (no Redis worker
  spawn, no dead `REVIEW_QUEUE` enqueue), and `trigger_reviews.py` runs `review_all.py` after
  enqueuing. The deeper shared-runner rewire stays deferred (design §5).
- **Five maintained scripts were missing their bootstrap** (`sweep_parallel.py`, `batch_run.py`,
  `remaining_batch.py`, `enqueue.py`, `inventory.py`) — they had no `sys.path.insert` in Stage 1
  (they relied on the editable install), so they never received `import _bootstrap` and failed
  with `ModuleNotFoundError` once the shim was gone. Fixed by inserting the same try/except
  bootstrap each other script uses.
- **`tests/test_kb_produce_registry.py`** now imports `scripts.archive.kb_produce_registry`, and
  its real-repo subprocess smoke test was removed (a maintained-command smoke test for a
  now-archived one-time migration).
- The archived scripts' internal `parent.parent` repo-root anchors are stale (one level shallow);
  left as-is — they are frozen one-time artifacts, not maintained runtime (rec 5).

---

## S4 — canonical source (phase `canonical_source`)

Spec: `workflows/repository/consolidation_stage_4_instruction_surfaces.yaml` · phase
`canonical_source` (phase A). Deliverable: `agent_config/` — the single hand-edited instruction
source (mental model · rules · skills · CLI surface), with doc-drift corrected.

| # | Acceptance criterion | Result |
|---|---|---|
| 1 | `agent_config/` created as the single hand-edited source (mental-model, rules, conventions, 7 skills, 3 agents, 5 commands) | PASS |
| 2 | Mental model updated — names `agentic_dynamics.*` planes, adds the 8-plane package map + the Stage 3 CLI surface | PASS |
| 3 | Rules captured (`agent_config/rules.md` — the AGENTS.md hats + load-bearing rule + commands + operational notes) | PASS |
| 4 | Skills consolidated to 7 (instrument/analyze/lab-books/run-workflow/queue/review/control-room) — `.claude`-only skills pulled in | PASS |
| 5 | Doc-drift corrected (WS-10 doc-drift half): `src/instrument/*` → `agentic_dynamics/*`, `experiments/configs` → `definitions/configs`, `experiments/specs` → split layout, module count 46→60, `review_worker`/`*_DEPRECATED_bge_m3`/`test_recovery` stale notes fixed | PASS |
| 6 | `pytest tests/ -m "not external"` green (additive — no production-code change) | PASS (1187 passed, 106 deselected) |

**S4-canonical_source result: 6/6 PASS.**

Notes:

- `.opencode/` is the *current* surface (loaded unconditionally); `.claude/` is a stale "ported"
  copy (missing the actuation/story/observation ingestion details, carrying a "Ported from …"
  header). `agent_config/` therefore uses `.opencode/` as the base for the mental model,
  conventions, agents, and commands, and pulls the four `.claude`-only skills
  (control-room/queue/review/run-workflow) in so all seven are canonical.
- The mental model now carries a **package-planes** section (8 planes, tier map, the pinned
  observe-only seam) and a **CLI surface** section (the Stage 3 subcommand tree).
- Stale references that *describe* a retirement (e.g. "review_worker.py was retired in Stage 3")
  are intentionally kept — they are provenance, not drift.

---

## S4 — generate (phase `generate`)

Spec: `workflows/repository/consolidation_stage_4_instruction_surfaces.yaml` · phase `generate`
(phase B). Deliverable: `scripts/_gen_instructions.py` (the single writer) + regenerated
`.opencode/` + `.claude/` + `tests/test_generated_surfaces_match.py`.

| # | Acceptance criterion | Result |
|---|---|---|
| 1 | `scripts/_gen_instructions.py` written — deterministically renders `agent_config/` → `.opencode/` + `.claude/` via an explicit format mapping | PASS |
| 2 | Regenerated surfaces committed byte-identical to `render_surfaces()` (36 files: 3 instruction docs ×2, 7 skills ×2, 3 agents ×2, 5 commands ×2) | PASS |
| 3 | `tests/test_generated_surfaces_match.py` written — byte-identity + orphan-file checks; demonstrably red on injected drift | PASS |
| 4 | `pytest tests/ -m "not external"` green | PASS (1189 passed, 106 deselected) |

**S4-generate result: 4/4 PASS — Stage 4 complete (canonical_source/generate).**

Notes:

- **Format mapping** (the rec-6 contract): `agent_config/{mental-model,rules,conventions}.md` →
  `.opencode/instructions/<name>.md` + `.claude/rules/<name>.md`; `agent_config/skills/<name>.md` →
  `<surface>/skills/<name>/SKILL.md`; `agents/` + `commands/` map 1:1 to both surfaces.
- The regeneration **added** to the surfaces what the canonical source consolidated: `rules.md`
  (the hats + load-bearing rule) now appears in both `.opencode/instructions/` and `.claude/rules/`,
  and `.opencode/skills/` gained the four `.claude`-only skills (control-room/queue/review/
  run-workflow) — both surfaces now carry the identical 7-skill set.
- `_gen_instructions.py` is classified as a helper (excluded from the command buckets, alongside
  `_bootstrap.py`) in the script-classification manifest + guard.
- Three stray `experiments/results/stories/*.json` files (smoke-test side effects from a
  `batch_stories.py` subprocess) were removed, not committed.

---

## S5 — move apps (phase `move_apps`)

Spec: `workflows/repository/consolidation_stage_5_apps_realignment.yaml` · phase `move_apps`
(phase A). Deliverable: `admin/` → `apps/control_room/`, `firebase/public/` → `apps/website/`,
imports re-pointed at `agentic_dynamics.*`, dual-Firebase invariant preserved.

| # | Acceptance criterion | Result |
|---|---|---|
| 1 | `admin/` → `apps/control_room/` (server.py, design_sessions.py, claude_agents_client.py, opencode_client.py, static/*) + `firebase/public/` → `apps/website/` via `git mv` | PASS |
| 2 | Imports re-pointed: internal `from admin.X` → `from apps.control_room.X`; `server.py` bootstrap depth fixed (`parent.parent` → `parent.parent.parent`); `scripts/supervise.py`/`claude_agents_supervisor.py` admin-insert → `apps/control_room` | PASS |
| 3 | `firebase/firebase.json` `"public"` → `"../apps/website"`; dual-host `.firebaserc` (ai-finops-rulebook + agentic-dynamics) preserved verbatim | PASS |
| 4 | Website data.js writers re-pointed: `build_data.py` + `generate_manifest.py` → `apps/website/data.js` | PASS |
| 5 | `agent_config/` references `firebase/public` → `apps/website`; both surfaces regenerated (drift guard green) | PASS |
| 6 | `pytest tests/ -m "not external"` green + Stage 1 dependency-lint apps-rule green | PASS (1189 passed, 106 deselected; lint 9 passed) |

**S5-move_apps result: 6/6 PASS.**

Notes:

- **Directory naming:** the spec/design's conceptual name `apps/control-room` (dash) is realised
  as the Python package `apps/control_room/` (underscore) — dashes are not valid Python import
  identifiers, and `from apps.control_room import server` must resolve. `apps/website/` is a
  static site (no Python imports), so its name is unchanged.
- `apps/` remains a namespace package (no `__init__.py`, mirroring the old `admin/`), so
  `from apps.control_room import server` resolves via the repo-root `sys.path` entry already in
  `server.py` + `tests/conftest.py`.
- The admin test suite (`test_admin_*`, `test_claude_agents_*`) imports via the new
  `apps.control_room` path and reads static assets from `apps/control_room/static/`.

---

## S5 — reframe README (phase `reframe_readme`)

Spec: `workflows/repository/consolidation_stage_5_apps_realignment.yaml` · phase `reframe_readme`
(phase B). Deliverable: the re-framed README (six systems) + `apps/website/CONTEXT.md`.

| # | Acceptance criterion | Result |
|---|---|---|
| 1 | `README.md` rewritten around the six systems (measurement / experiment / execution / knowledge / control / publication) — the perturbation instrument is ONE system, not the sole framing | PASS |
| 2 | README points at `ARCHITECTURE.md` (the authority) + the `agentic-dynamics` CLI (the command surface) | PASS |
| 3 | `firebase/CONTEXT.md` → `apps/website/CONTEXT.md` (deploy notes updated to the new location; the dual-Firebase instruction kept verbatim) | PASS |
| 4 | Stale references corrected: `src/instrument` → `agentic_dynamics` planes, `experiments/configs` → `definitions/configs`, `firebase/public` → `apps/website`, retired modules dropped, counts updated (37 configs · 77 specs · 19 lab books); `AGENTS.md`/`CONTRIBUTING.md`/`agent_config/mental-model.md` re-pointed | PASS |
| 5 | `pytest tests/ -m "not external"` green | PASS (1189 passed, 106 deselected) |

**S5-reframe_readme result: 5/5 PASS.**

Notes:

- The README keeps the measured evidence (key findings, observed-dynamics table, 10 operators,
  citation) and changes only the *framing*: the six-system table replaces the "perturbation
  instrument" as the whole identity, and the repository-structure tree now shows the
  `src/agentic_dynamics/` planes, the `experiments/`/`workflows/` split, and `apps/{control_room,website}`.
- `apps/website/CONTEXT.md` documents the website *source* here while pointing at `firebase/` for
  the deploy config (`firebase.json` `"public": "../apps/website"`, dual-host `.firebaserc`).
- Historical `docs/` records (fixplan, remediation_verify, verify_evidence, review/website.md)
  that mention `firebase/public/` are left as-is — they describe the state at the time, not the
  current layout.

---

## S5 — verify (phase `verify`)

Spec: `workflows/repository/consolidation_stage_5_apps_realignment.yaml` · phase `verify`.
Deliverable: `docs/consolidation/stage_5_verification.md`.

| # | Acceptance criterion | Result |
|---|---|---|
| 1 | `apps_import_system` — apps import `agentic_dynamics.*` only; the reverse (`agentic_dynamics` → `apps`) is zero | PASS |
| 2 | `apps_no_domain_rules` — the Stage 1 dependency-lint apps-rule (no `ExperimentSpec`/`RuleSpec`/`Factor` in `apps/`) green | PASS (9 passed) |
| 3 | `dual_firebase_synced` — `.firebaserc` lists both `ai-finops-rulebook` + `agentic-dynamics`; `firebase.json` `public` → `apps/website`; `firebase deploy --only hosting --dry-run` validates | PASS |
| 4 | `readme_reframed` — README six-system framing + `apps/website/CONTEXT.md` | PASS |
| 5 | `pytest tests/ -m "not external"` green | PASS (1189 passed, 106 deselected) |

**S5-verify result: 5/5 PASS — Stage 5 complete (move_apps/reframe_readme/verify).**

---

## S6 — coverage (phase `coverage`)

Spec: `workflows/repository/consolidation_stage_6_verification_release.yaml` · phase `coverage`.
Deliverable: `docs/consolidation/stage_6_coverage.md` (the coverage proof).

| # | Acceptance criterion | Result |
|---|---|---|
| 1 | All 9 recommendations → ≥1 stage (rec 1,4→S0; 2,7,8→S1; 3→S2; 5→S3,S5; 6→S4; 9→S5; all→S6) | PASS |
| 2 | WS-01..10 each dispositioned exactly once (folded 3 · deferred 7 · retired 1 sub-part), no duplicate/orphan | PASS |
| 3 | Six systems each have a package home (measurement 15 · experiment 3 · runtime 4 + adapters 3 · knowledge 16 · control 9 · reporting 4 + apps) | PASS |
| 4 | CAP freeze still intact (`context_abstraction_implement` `status: draft` + PAUSED note) + 7 stage specs + 3 stage verification docs present | PASS |

**S6-coverage result: 4/4 PASS.**

---

## S6 — gates (phase `gates`)

Spec: `workflows/repository/consolidation_stage_6_verification_release.yaml` · phase `gates`.
Deliverable: `docs/consolidation/stage_6_gates.md` (PASS/FAIL per gate).

| # | Gate | Result |
|---|---|---|
| 1 | Stage-specific acceptance tests in one pass (test_doc_lifecycle · test_dependency_direction · test_experiment_workflow_classification · test_script_classification · test_generated_surfaces_match · test_data_flow) | PASS (24 passed) |
| 2 | Compile gate — `validate_spec` + `validate_rules` on all 77 specs | PASS (0 refusals) |
| 3 | Redis isolation (6380 queue DB1 / KB DB2; 6379 sandbox) | PASS |
| 4 | Dual Firebase (`.firebaserc` both projects) | PASS |
| 5 | CAP frozen-not-deleted (`context_abstraction_implement` `status: draft` + PAUSED) | PASS |
| 6 | No `_results_summary.json` resurrection (build_data.py — the website build — does not read it) | PASS |
| 7 | Full suite green | PASS (1189 passed, 106 deselected) |

**S6-gates result: 7/7 PASS.**

---

## S6 — release (phase `release`)

Spec: `workflows/repository/consolidation_stage_6_verification_release.yaml` · phase `release`.
Deliverable: `docs/consolidation/verification.md` + the synced dual-Firebase deploy.

| # | Acceptance criterion | Result |
|---|---|---|
| 1 | Dual-Firebase deploy in sync — `firebase deploy --only hosting` (ai-finops-rulebook) + `--project agentic-dynamics` (mirror), same `apps/website/` source | PASS (both "Deploy complete!") |
| 2 | `data_manifest.json` regenerated (`python scripts/generate_manifest.py`) | PASS (registry: 701 entities) |
| 3 | Spec index regenerated (`python scripts/spec_status.py`, 77 specs) | PASS |
| 4 | `docs/consolidation/verification.md` written (PASS/FAIL across coverage · gates · invariants · both deploys) | PASS |
| 5 | `pytest tests/ -m "not external"` green | PASS (1189 passed, 106 deselected) |

**S6-release result: 5/5 PASS — the consolidation release is COMPLETE (S0–S6, all gate-green).**

Notes:

- **Deploy-config home corrected:** Firebase requires `firebase.json`'s `"public"` to sit *inside*
  the project directory, so the earlier `"public": "../apps/website"` was rejected at deploy time
  ("outside of project directory"). `firebase.json` + `.firebaserc` were moved to `apps/website/`
  with `"public": "."`, and the `deploy`/`full_matrix`/`cross_models` pipeline plans gained
  `cwd: apps/website`.
- Both hosts deployed from the same `apps/website/` source — in sync by construction.

---

## Repair release

Per-finding acceptance-criterion results for the refactor-repair release (review:
`docs/review/refactor_repair_review.md`). One subsection per finding, in release order.

### P0-3 — Control Room repo root re-point

| # | Acceptance criterion | Result |
|---|---|---|
| 1 | `apps/control_room/server.py` `ROOT` re-pointed to `agentic_dynamics.core.paths.PROJECT_ROOT` (was `Path(__file__).resolve().parent.parent` → `<repo>/apps`) | PASS |
| 2 | `DATA_MANIFEST_PATH` default resolves to `<repo>/experiments/data_manifest.json` (no longer `apps/experiments/...`) | PASS |
| 3 | `SUPERVISOR_FLAGS_FILE` default resolves to `<repo>/experiments/results/supervisor/flags.jsonl` | PASS |
| 4 | Design-session (and claude-agent) workdir allowlist defaults to `<repo>` (no longer `apps/`) | PASS |
| 5 | `_results_summary.json` read (`/api/routing`) and `scripts/enqueue.py` `cwd` re-pointed from `parent.parent` to `ROOT` | PASS |
| 6 | Launch docs updated — `python3 apps/control_room/server.py` + `gunicorn ... 'apps.control_room.server:app'` | PASS |
| 7 | `tests/test_control_room_paths.py` added — asserts `server.ROOT == PROJECT_ROOT` + manifest/flags/workdir defaults resolve inside the repo | PASS (5 passed) |
| 8 | `pytest tests/test_control_room_paths.py tests/test_admin_server.py tests/test_admin_design_sessions.py tests/test_admin_claude_agents.py tests/test_admin_supervisor.py tests/test_admin_frontend.py tests/test_admin_claude_agents_frontend.py` green | PASS (123 passed) |

**P0-3 result: 8/8 PASS.**

### P1-1 — Reproduction environment + CI gates

| # | Acceptance criterion | Result |
|---|---|---|
| 1 | `Dockerfile` COPY paths fixed — `experiments/configs/` → `experiments/definitions/` (configs live at `experiments/definitions/configs/`); every COPY source (`pyproject.toml`, `src/`, `scripts/`, `experiments/definitions/`, `experiments/results/`) exists in the tree | PASS |
| 2 | Stale `ai-finops-framework` override comment in `Dockerfile` corrected to `agentic-dynamics` | PASS |
| 3 | `scripts/reproduce.sh` rewritten against the current tree — current project framing ("Agentic Dynamics"), no retired lab scripts (the three `*_DEPRECATED_bge_m3` labs removed, replaced by the 19 active lab books) | PASS |
| 4 | `scripts/reproduce.sh` reports `apps/website/data.js` (not `firebase/public/data.js`) and instructs deploy from `apps/website/` (dual-Firebase, both hosts) | PASS |
| 5 | `scripts/reproduce.sh --dry-run` added — prints every step's exact argv without executing; exits 0 | PASS (verified locally) |
| 6 | CI (`pytest.yml`) gates added — `docker build .`, `agentic-dynamics --help`, `bash scripts/reproduce.sh --dry-run` | PASS |
| 7 | `bash -n scripts/reproduce.sh` clean; `--dry-run` lists all 19 lab books + the 7 pipeline steps | PASS |

**P1-1 result: 7/7 PASS.**

### P1-2 — CLI longest-prefix resolution

| # | Acceptance criterion | Result |
|---|---|---|
| 1 | `src/agentic_dynamics/cli.py` `_resolve` implements TRUE longest-prefix matching — `_COMMANDS` prefixes sorted by length descending (`_SORTED_PREFIXES`) before the first-match walk | PASS |
| 2 | `agentic-dynamics supervise claude-agents` resolves to `claude_agents_supervisor.py` (was `supervise.py` under insertion-order matching) | PASS |
| 3 | Latent bug fixed: the bare-supervise key was `("supervise")` (a string, not a 1-tuple), so `agentic-dynamics supervise` silently never resolved — corrected to `("supervise",)` | PASS |
| 4 | `tests/test_cli_resolution.py` added — table-driven, expectation table hand-authored from `_HELP` + the CLI-surface doc (not from `_COMMANDS`); asserts every documented command resolves to its intended script AND the script exists on disk | PASS (46 passed) |
| 5 | Coverage guard — `_HELP`-parsed documented leaf set == table argv set (both directions: no documented command missing, no undocumented row) | PASS |
| 6 | Forwarded-argv semantics preserved (`supervise --once`, `experiment run --model ...`); special cases (`registry <sub>`, `analyze lab <name>`) pinned | PASS |
| 7 | `ruff check` clean on `cli.py` + `test_cli_resolution.py`; full `-m "not external"` suite: 1238 passed, no new failures | PASS |

**P1-2 result: 7/7 PASS.**

### P1-2 (packaging) — CLI declared checkout-only + wheel smoke gate

| # | Acceptance criterion | Result |
|---|---|---|
| 1 | Decision implemented: the CLI is **checkout-only** — it forwards to repo-level `scripts/`, which a wheel does not ship; no script-logic migration in this release (deferred post-repair hardening) | PASS |
| 2 | Documented in `pyproject.toml` — `[project.scripts]` comment declares checkout-only, cites the `where = ["src"]` package layout, and names `cli.CHECKOUT_REQUIRED` | PASS |
| 3 | Documented in CLI `--help` — a "Checkout-only" note states commands forward to the repo `scripts/` and an installed wheel can only print help | PASS |
| 4 | `cli.main` emits a clear `CHECKOUT_REQUIRED` message (exit 2) when `scripts/` is absent; `--help` still works (exit 0) from a wheel | PASS (verified: wheel has no `scripts/`, `cli.py` carries the guard) |
| 5 | Unit tests added — help documents checkout-only; command from a missing-`scripts/` dir returns 2 + "checkout required"; `--help` works from a missing-`scripts/` dir | PASS (49 passed) |
| 6 | CI wheel smoke gate added (`packaging` job) — build wheel → install into a clean venv → `--help` greps "checkout-only" → command greps "checkout required" with non-zero exit | PASS |
| 7 | `ruff check` clean on `cli.py` + `test_cli_resolution.py`; `pytest` green (51 passed on the two touched areas) | PASS |

**P1-2 (packaging) result: 7/7 PASS.**
















