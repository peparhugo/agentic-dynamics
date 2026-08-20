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








