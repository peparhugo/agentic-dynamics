# Conventions & Gotchas

## Coding Conventions

- Function/variable: `snake_case`. Class: `PascalCase`. Constants: `UPPER_CASE`.
- Type hints required on all public function signatures.
- Module docstrings at top of every file.
- Line length: 100 chars max.
- Imports grouped: stdlib first, then third-party, then internal.
- No bare excepts — always catch specific exceptions.
- Dataclasses preferred over dicts for structured data.

## Spec/Compiler Conventions (written — see code_reviews/2026-08-14)

- **Measure before policy.** `RuleSpec` declares `requires` (information it consumes) and
  `produces` (information it emits). `plane` is `"measurement"` (produces) or `"control"`
  (consumes). The validator refuses a control rule whose `requires` are unmet. Instrument the
  information (`confidence`, `answer`/`explanation` token split, attempt/timestamp fields)
  before writing `model_cascade`/`dynamics` arms.
- **Evidence classes:** `[M]` measured, `[C]` computed, `[H]` heuristic, `[X]` external,
  `[P]` policy/prior. Control rules are `[H]`/`[P]`; measurement rules are `[M]`/`[C]`.
- **Policy is a factor level.** `decide(job, state) -> {route, depth, retry, escalate, budget,
  deadline}` goes in the grid as a `Factor` level, not a side-channel.
- **Specs live in `experiments/specs/*.yaml`** (11 real specs, e.g. `agentic_dynamics_story.yaml`). `Workflow.kind` is
  `story | task | experiment | agent_task`; `experiment` makes a campaign an experiment of
  experiments (same interpreter at every level).

## Anti-Patterns

- Do NOT import from deprecated modules: `experiment.py`, `adapter.py`, `lab_book.py`.
  Use `opencode.py` / `run_opencode_agentic()` instead.
- Do NOT add heavy deps to core modules. Optional heavy deps go behind try/except.
- Do NOT hardcode model names or pricing. Use `efficiency.py:PROVIDER_PRICING`.
- Do NOT read `experiment.py` or `adapter.py` for new work — they have deprecation warnings.
- Do NOT hand-author policy logic as a one-off in scripts. `compile_experiment.py` is written and
  generalizes `_gen_matrix_cells` (`pipeline.py:394`) as `experiment_matrix` and
  `routing.simulate_strategies` (`routing.py:98`) as `compare_arms` — route new grid/comparison
  work through the spec, not through direct calls to those two.

## Project-Specific Gotchas

- `__init__.py` exports 100+ symbols. Adding a new public class means updating `__all__`.
- `scripts/analyze_worktrees.py` is 1396 lines — the biggest file. Be careful editing it.
- `scripts/run.py` and `scripts/analyze_worktrees.py` share similar logic but are NOT unified.
  If you fix a bug in one, check the other.
- `scripts/plan.py` is DEPRECATED (hardcoded phases). Use `scripts/pipeline.py` (YAML-driven,
  `experiments/configs/plans.yaml`) for any new orchestration work. Don't edit plan.py.
- Lab books read `_results_summary.json` and `inventory.json` — always refresh these first.
- `scripts/build_data.py` generates `firebase/public/data.js` — don't edit that file directly.
- DeepSeek pricing lives in `efficiency.py:PROVIDER_PRICING["deepseek"]`.
  Claude pricing at `PROVIDER_PRICING["anthropic"]`.
- `tests/conftest.py` has availability check fixtures — tests skip gracefully when infra is down.
- `BUILTIN_STORIES` in story.py has 3 stories: task_manager_api, static_site_gen,
  notification_service. Stories are also defined in configs as YAML.
- v0.6-v0.9 modules (story, commit_analysis, review, entropy, codebase_graph,
  mutation, language, lsp_diagnostics) are the newest layer. Older modules (perturb, basin,
  solution, efficiency, strategy, game_report) are battle-tested core.

## Testing

- Run: `pytest tests/` from project root.
- Most tests use pytest markers for optional deps (neo4j, ollama, chroma, sonar).
- `test_story.py` is the largest (330L) — needs opencode available to pass.
- When adding a new module, add tests to `tests/` and update `__init__.py` exports.

## Session Discipline

- One subsystem per session. Don't cross domains.
- Use explore subagents for file research — keep primary context clean.
- Load a skill before starting work in that domain.
- Use `/run-exp`, `/analyze`, `/pipeline`, `/lab` commands for common tasks.
- When in doubt, check mental-model.md before reading source files.
