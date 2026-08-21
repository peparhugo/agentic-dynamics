# Conventions & Gotchas

## Coding Conventions

- Function/variable: `snake_case`. Class: `PascalCase`. Constants: `UPPER_CASE`.
- Type hints required on all public function signatures.
- Module docstrings at top of every file.
- Line length: 100 chars max.
- Imports grouped: stdlib first, then third-party, then internal.
- No bare excepts — always catch specific exceptions.
- Dataclasses preferred over dicts for structured data.

## Spec/Compiler Conventions (written — see docs/designs/current/2026-08-14_experiment-spec-and-compiler-design.md)

- **Measure before policy.** `RuleSpec` declares `requires` (information it consumes) and
  `produces` (information it emits). `plane` is `"measurement"` (produces) or `"control"`
  (consumes). The validator refuses a control rule whose `requires` are unmet. The formerly-
  missing signals are now measured — `confidence` [H] (`src/agentic_dynamics/adapters/opencode.py:113`),
  `perturbation_strength` + `test_executed_success` (`src/agentic_dynamics/knowledge/ledger_ingestion.py:180-181`),
  `answer`/`explanation` token split, attempt/timestamp fields — so `model_cascade`/`dynamics`/
  `grit` arms are writable.
- **Evidence classes:** `[M]` measured, `[C]` computed, `[H]` heuristic, `[X]` external,
  `[P]` policy/prior. Control rules are `[H]`/`[P]`; measurement rules are `[M]`/`[C]`.
- **Policy is a factor level.** `decide(job, state) -> {route, depth, retry, escalate, budget,
  deadline}` goes in the grid as a `Factor` level, not a side-channel.
- **Specs live in `experiments/definitions/*.yaml` (experiments) + `workflows/**/*.yaml` (work
  orders)** — the rec-3 split. `Workflow.kind` is `story | task | experiment | agent_task`;
  `experiment` makes a campaign an experiment of experiments (same interpreter at every level).
  **Read `experiments/specs/STATUS.md` FIRST** before authoring a new one — it is the generated
  spec lifecycle index; `experiments/specs/index.json` is its machine-readable twin. Both are
  derived, never hand-edited — regenerate with `python scripts/spec_status.py`.

## Anti-Patterns

- Do NOT import from retired modules (`experiment.py`, `adapter.py`, `lab_book.py` were
  retired in Stage 1). Use `agentic_dynamics.adapters.opencode` / `run_opencode_agentic()`.
- Do NOT add heavy deps to core modules. Optional heavy deps go behind try/except.
- Do NOT hardcode model names or pricing. Use `agentic_dynamics.measurement.efficiency:PROVIDER_PRICING`.
- Do NOT read `experiment.py` or `adapter.py` for new work — they were retired in Stage 1.
- Do NOT hand-author policy logic as a one-off in scripts. `compile_experiment.py` is written and
  generalizes `_gen_matrix_cells` (`pipeline.py:394`) as `experiment_matrix` and
  `routing.simulate_strategies` (`routing.py:98`) as `compare_arms` — route new grid/comparison
  work through the spec, not through direct calls to those two.

## Project-Specific Gotchas

- `__init__.py` exports 100+ symbols. Adding a new public class means updating `__all__`.
- `scripts/analyze_worktrees.py` is the largest analysis script. Be careful editing it.
- `scripts/run.py` and `scripts/analyze_worktrees.py` share similar logic but are NOT unified.
  If you fix a bug in one, check the other.
- Use `scripts/pipeline.py` (YAML-driven, `experiments/definitions/configs/plans.yaml`) for
  orchestration work (the old standalone plan scripts were retired in Stage 1).
- Publication labs read the canonical corpus (`agentic_dynamics.reporting.canonical_corpus`) —
  refresh inventory and regenerate before running; never read the retired `_results_summary.json`.
- `scripts/build_data.py` generates `apps/website/data.js` — don't edit that file directly.
- DeepSeek pricing lives in `agentic_dynamics.measurement.efficiency:PROVIDER_PRICING["deepseek"]`.
  Claude pricing at `PROVIDER_PRICING["anthropic"]`.
- `tests/conftest.py` has availability check fixtures — tests skip gracefully when infra is down.
- `BUILTIN_STORIES` (in `agentic_dynamics.runtime.story`) defines task_manager_api,
  static_site_gen, notification_service. Stories are also defined in configs as YAML.
- The `measurement`/`adapters`/`runtime` planes hold the experiment apparatus; `reporting` holds
  game reports + reviews; `core` holds language/paths/streaming. See `ARCHITECTURE.md` §1.

## Testing

- Run: `pytest tests/` from project root.
- Most tests use pytest markers for optional deps (neo4j, ollama, chroma, sonar).
- `test_story.py` needs opencode available to pass (skips gracefully otherwise).
- When adding a new module, add tests to `tests/` and update `__init__.py` exports.

## Session Discipline

- One subsystem per session. Don't cross domains.
- Use explore subagents for file research — keep primary context clean.
- Load a skill before starting work in that domain.
- Use `/run-exp`, `/analyze`, `/pipeline`, `/lab` commands for common tasks.
- When in doubt, check mental-model.md before reading source files.
