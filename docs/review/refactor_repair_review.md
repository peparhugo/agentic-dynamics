# Refactor-Repair Review — external critique (2026-08-20)

**Provenance [X]:** operator-provided external review of main at `1e360335f` (the S0–S6
consolidation merge), received 2026-08-20. Retained as the citable input for the
refactor-repair release. Every load-bearing claim below was re-verified against the tree
before authoring the repair spec (verification marks in square brackets).

## Verdict

The major refactor worked. The repository is now a **coherent modular monorepo that has
completed the architectural rehome, but has not completed the operational and semantic
stabilization of that rehome.** The old problem was that everything belonged to
`instrument`. The new problem is conventional and repairable: several paths, commands,
specifications, and agent instructions still describe or depend on the pre-refactor
repository.

| Area | Assessment |
|---|---|
| Architectural structure | 8.5/10 |
| Package boundaries | 8/10 |
| Regression guards | 8/10 |
| Operational refactor completeness | 5/10 |
| Agent/developer documentation | 3/10 |
| Internal module decomposition | 6/10 |
| Overall current state | 7/10 |

Do a focused refactor-repair release before implementing the Context Abstraction Plane.
Do NOT undo the refactor.

## What the refactor genuinely fixed

1. The semantic monolith is gone — eight explicit planes; ARCHITECTURE.md defines
   ownership, imports, shipped vs proposed, and supersedes the blueprints + handoffs.
2. Experiments (`experiments/definitions/`), workflows (`workflows/{examples,operations,
   repository,research}/`), and applications (`apps/{website,control_room}/`) have homes.
3. Architecture is enforced, not documented — guard tests for dependency direction,
   data-flow, experiment/workflow placement, script classification, generated-surface
   drift, doc lifecycle, data integrity.
4. Historical architecture has a lifecycle — one ARCHITECTURE.md authority, archived
   blueprints, status vocabulary enforced by a test.
5. The CAP has reserved homes (`control/facts.py`, `control/reducers/`,
   `control/context_compiler.py`, `control/rules.py`, `control/validator.py`,
   `control/decisions.py`, `core/contracts.py`) — note: reserved on paper; the physical
   placeholder files were never created. [verified]

## P0 findings

### P0-1 — The agent configuration refactor is semantically wrong

`agent_config/` is copied verbatim into BOTH `.opencode/` and `.claude/`, with a drift
test requiring byte-identity. That solves text drift but creates **schema drift**: the
two platforms do not share formats (mode/model/permission mapping; command argument
indexing; frontmatter fields). The repository's own accepted port document says they
require **translation, not verbatim duplication**. A byte-equality test can be green
while emitting invalid Claude configuration.

**Fix:** one semantic source + two renderers (`render_opencode()`, `render_claude()`),
each validated against its own schema. Invariant: meaning equivalence where platforms
permit, not byte equality.

### P0-2 — The authoritative agent instructions still describe the old repository

`AGENTS.md` (`status: accepted`) still instructs `experiments/configs/`,
`src/instrument/`, `admin/server.py`, old `code_reviews/` paths, the old manual
surface-sync model, and says confidence/perturbation_strength/test_executed_success
still need instrumentation (they are measured — `experiment_spec.py` says so). [verified]
`CLAUDE.md` imports AGENTS.md (inherits the staleness) and claims surfaces are
hand-synchronized with no build step — the opposite of the generator. `CONTRIBUTING.md`,
`scripts/CONTEXT.md`, `experiments/CONTEXT.md` retain old paths/taxonomy. In an
agent-operated repo, stale instructions are runtime context given to the systems
modifying the codebase.

**Fix:** rewrite the instruction docs against the current tree + add a guard over all
`status: accepted` and `docs/designs/current` documents rejecting retired path families
(`src/instrument/`, `experiments/configs/`, `admin/server.py`, `firebase/public/`,
`code_reviews/2026-08-14_...`) with a narrow historical allowlist.

### P0-3 — The Control Room's repository root is wrong after the move

`apps/control_room/server.py:162` — `ROOT = Path(__file__).resolve().parent.parent`
resolves to `<repo>/apps`, not the repo root; default paths for `data_manifest.json`
and supervisor flags resolve under `apps/experiments/...`; design-session workdir
defaults to `apps/`. [verified] Launch docs still say `python3 admin/server.py` /
`gunicorn ... admin.server:app`. [verified] Use `agentic_dynamics.core.paths.PROJECT_ROOT`.

**Fix:** re-point to `PROJECT_ROOT`, update launch docs, add the invariant test
(`server.ROOT == PROJECT_ROOT`).

## P1 findings

### P1-1 — The reproduction environment was not updated

`Dockerfile:28` — `COPY experiments/configs/ experiments/configs/` — the directory no
longer exists (configs live at `experiments/definitions/configs/`). A clean Docker build
fails. [verified] `scripts/reproduce.sh` still calls the project "AI FinOps Framework",
runs retired lab scripts (`lab_reasoning_divergence.py`, `lab_semantic_clusters.py`,
`lab_cross_model_reasoning.py`), reports `firebase/public/data.js`, and instructs deploy
from `firebase/`. With `set -euo pipefail` the missing scripts terminate the run. CI does
not build the image or smoke the reproduction entrypoint.

**Fix:** repair Dockerfile + reproduce.sh against current paths; add `docker build .`,
`agentic-dynamics --help`, `scripts/reproduce.sh --dry-run` as CI gates.

### P1-2 — The unified CLI has a real command-resolution bug

`_resolve()` claims longest-prefix matching but iterates `_COMMANDS` in insertion order
(`src/agentic_dynamics/cli.py:101-106`). [verified] `("supervise",)` is registered before
`("supervise", "claude-agents")`, so `agentic-dynamics supervise claude-agents` invokes
the wrong script. No test asserts every documented command resolves to its intended
script. Also: `pyproject.toml` publishes a console entry point, but the CLI invokes
repo-level `scripts/` which a wheel does not contain — works from an editable checkout
only.

**Fix:** sort prefixes by length descending + table-driven resolution tests; declare
checkout-only explicitly OR migrate script logic into package modules (scripts become
thin shims).

### P1-3 — The experiment/workflow split is visually correct but semantically unreliable

Placement is decided by substring heuristics over question text. Real misplacements
survive: `experiments/definitions/posthoc_pipeline.yaml` (starts workers, drains queues,
regenerates site data — operational) and `workflow_step_routing.yaml` (phases survey/
design/implement/verify modifying source — repository development) both live in
definitions. [verified]

**Fix:** explicit validated metadata — `artifact_kind: experiment|workflow`,
`intent: measure|mutate`, `side_effects.{repository,external_services}`, `repeatable` —
with deterministic placement from the metadata, and the compiler rejecting an
"experiment" that contains source-modification phases unless sandboxed. Do not let a
substring classifier decide architectural identity indefinitely.

### P1-4 — The lifecycle index does not identify current work

Nearly all 77 entries are `active` — including completed consolidation stages, completed
rewrites, completed implementations. `derive_status()` defaults everything to `active`
unless authored status/superseded_by exists; a successful run does not imply completion.
That is right for repeatable experiments, wrong for one-shot repository workflows.
STATUS.md is an execution ledger, not an answer to "what work remains?".

**Fix:** lifecycle semantics differ by artifact kind — Experiment: `draft|active|
superseded|tombstoned`; Workflow: `draft|runnable|running|completed|superseded|
tombstoned` (or at minimum `repeatable: true|false`). A successful run of a
non-repeatable workflow marks it `completed`. Show artifact kind + repeatability in
STATUS.md; separate "runnable now" from "ran successfully in history".

## Architectural debt that remains

1. **Local monoliths survived the package move** — `runtime/story.py` (~61KB),
   `workflow_runner.py` (~30KB), `measurement/perturb.py` (~35KB),
   `knowledge/graph.py` (~40KB), `knowledge_ingestion.py` (~26KB),
   `prompt_constructor.py` (~25KB), `reporting/review.py` (~29KB),
   `apps/control_room/server.py` (~70KB), `design_sessions.py` (~37KB); scripts layer:
   `analyze_worktrees.py` (~1,398 lines), `pipeline.py` (~1,267), `build_data.py`
   (~1,188). Split only where responsibilities justify: `apps/control_room/` →
   `routes/ services/ clients/ paths.py`; `knowledge/` → `model/ ingestion/ storage/
   retrieval/ augmentation/`; `runtime/story/` → `models.py orchestration.py
   persistence.py conditions.py`.
2. **The dependency lint is not airtight** — relative imports (`from ..control import
   ...`) can bypass the AST cross-plane analysis; `runtime.workflow_runner → control.
   step_routing` is documented "observe-only" but is a decision dependency. Cleaner:
   dependency inversion — `Router(Protocol)` in core/runtime with the control
   implementation injected at the composition root; same for telemetry.
3. **The measured-signal vocabulary is inconsistent** —
   `experiment_spec.py` says confidence is measured and the compiler admits control
   arms requiring it; `control/step_routing.py:44` and `signal_store.py` still describe
   it as unmeasured and hard-forbid it. [verified] Before implementing canonical facts,
   create ONE signal registry: `name, producer, evidence class, scope, value type,
   measured status, permitted consumers, freshness`.

## What to do next — the repair release, in order

1. **Repair operational breakage** — P0-3 (server ROOT + docs + invariant test),
   P1-1 (Dockerfile + reproduce.sh + CI gates), P1-2 (CLI resolution + packaging).
2. **Repair agent context** — P0-1 (two renderers + schema validation), P0-2
   (instruction rewrite + stale-path guard).
3. **Make artifact identity explicit** — P1-3 (metadata + compiler validation +
   reclassification).
4. **Make lifecycle useful** — P1-4 (per-kind semantics + completed states).
5. **Harden rather than restructure** — relative-import resolution in the lint;
   routing/telemetry protocols; split server.py first, then story.py + knowledge
   surfaces; migrate logic out of the largest maintained scripts.
6. **Then resume the Context Abstraction Plane.**

The codebase no longer needs another grand architectural reinvention. It needs a
disciplined stabilization pass that makes the runtime paths, agent instructions,
artifact taxonomy, and lifecycle model match the architecture that is now already in
place.
