# Conventions & Gotchas

## Coding Conventions

- Function/variable: `snake_case`. Class: `PascalCase`. Constants: `UPPER_CASE`.
- Type hints required on all public function signatures.
- Module docstrings at top of every file.
- Line length: 100 chars max.
- Imports grouped: stdlib first, then third-party, then internal.
- No bare excepts — always catch specific exceptions.
- Dataclasses preferred over dicts for structured data.

## Anti-Patterns

- Do NOT import from deprecated modules: `experiment.py`, `adapter.py`, `lab_book.py`.
  Use `opencode.py` / `run_opencode_agentic()` instead.
- Do NOT add heavy deps to core modules. Optional heavy deps go behind try/except.
- Do NOT hardcode model names or pricing. Use `efficiency.py:PROVIDER_PRICING`.
- Do NOT read `experiment.py` or `adapter.py` for new work — they have deprecation warnings.

## Project-Specific Gotchas

- `__init__.py` exports 100+ symbols. Adding a new public class means updating `__all__`.
- `scripts/analyze_worktrees.py` is 1396 lines — the biggest file. Be careful editing it.
- `scripts/run.py` and `scripts/analyze_worktrees.py` share similar logic but are NOT unified.
  If you fix a bug in one, check the other.
- Lab books read `_results_summary.json` and `inventory.json` — always refresh these first.
- `scripts/build_data.py` generates `firebase/public/data.js` — don't edit that file directly.
- DeepSeek pricing lives in `efficiency.py:PROVIDER_PRICING["deepseek"]`.
  Claude pricing at `PROVIDER_PRICING["anthropic"]`.
- `tests/conftest.py` has availability check fixtures — tests skip gracefully when infra is down.
- `BUILTIN_STORIES` in story.py has 3 stories: task_manager_story, static_site_gen_story,
  notification_service_story. Stories are also defined in configs as YAML.
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
