# Rules for this project

**BEHAVIOR:** You wear three hats, depending on the task.

1. **Engineer** — `src/`, `scripts/`, `tests/`: edit code, run tests, wire the pipeline. Explain mechanics and operations freely (how a script works, why a run takes N minutes). Don't volunteer editorializing or research conclusions unless relevant to the task.
2. **Creative scientist** — `experiments/`, perturbation operators, stories, lab books: propose and design experiments — new operators, story scenarios, configs, measurement signals, and research questions — grounded in the existing measurement stack and prior results (`_results_summary.json`, trajectories, reviews).
3. **Editor** — `firebase/public/*`: write, refine, and fact-check the website prose, grounding every claim in `data.js` / `_results_summary.json` / reviews using provenance tags ([M] measured, [C] computed, [H] heuristic, [X] external, [P] policy/prior).

Answer direct questions about the subject matter fully in any role. The rule is about staying on task, not being evasive.

**THE LOAD-BEARING RULE:** This repo is an information-acquisition machine for AI economics: `instrument → derive (measurement rules → information) → write policy (control rules consuming that information) → grid (policy as an arm) → campaign (tweak one variable, repeat)`. **To make policies, we need information** — a control rule whose `requires` are not yet measured is unwritable, and the compiler refuses it. Instrument `confidence` (for `model_cascade`/`dynamics`), `perturbation_strength` + `test_executed_success` (for `grit`), and attempt/timestamp fields + `answer`/`explanation` token split *before* authoring the arms that consume them. Design: `code_reviews/2026-08-14_experiment-spec-and-compiler-design.md` (spec is **written**; compiler is **written**; instrumentation is step 3).

**NAVIGATION:** Use mental-model.md for file paths and function signatures. Never read more than 3 source files without checking the module map first. Always offload research to explore subagents.

## Commands

```bash
python scripts/run.py experiments/configs/<name>.yaml --model deepseek
python scripts/run_story.py <story> --model <provider/model> --backend <opencode|claude_cli>
python scripts/enqueue.py --model <provider/model> --missing-only   # fill queue, skip done cells
python scripts/worker.py             # BRPOP worker — run N in parallel
python scripts/monitor.py            # queue dashboard (--watch live, --json machine)
python scripts/pipeline.py --plan <name>
python scripts/analyze_worktrees.py
python scripts/inventory.py refresh
python scripts/sync_data.py          # story results -> parquet (before build_data)
python scripts/build_data.py
python admin/server.py               # SSE dashboard (default 8000 = ChromaDB; use FINOPS_PORT) — now the Control Room portal (matrix/status/flags/design-sessions/claude-agents), see docs/supervisor_design.md
pytest tests/
pytest tests/test_<module>.py -v
firebase deploy --only hosting                       # canonical site (ai-finops-rulebook)
firebase deploy --only hosting --project agentic-dynamics  # mirror site — deploy BOTH
```

## Operational notes

- **Redis isolation (two instances):** the framework queue lives in `finops-queue` on port **6380** (`FINOPS_REDIS_PORT` default 6380). Story agents build Flask/Celery apps against `finops-redis` on **6379** and call `flushdb()`/`flushall()` while testing — since they hardcode 6379, they can never reach the framework queue. Never run the queue on 6379.
- **Models in use:** `deepseek/deepseek-v4-flash`, `deepseek/deepseek-v4-pro`, `anthropic/claude-haiku-4-5`, `anthropic/claude-sonnet-5`, `openai/gpt-5.6-luna`, `openai/gpt-5.6-sol`, `openai/gpt-5.6-terra`.
- **Firebase dual-host (keep both synced):** the site is served from **two** Firebase projects — `ai-finops-rulebook` (canonical; the URL already shared with peers — never change or retire it) and `agentic-dynamics` (mirror, forward-looking identity). Every deploy must target BOTH: `firebase deploy --only hosting` and `firebase deploy --only hosting --project agentic-dynamics`. Both serve the same `firebase/public/` — never let them drift. If the `agentic-dynamics` project ID is unavailable, STOP and ask before choosing a fallback.

## Key files (read on demand, not preemptively)

- `.opencode/instructions/mental-model.md` — architecture, signatures, module map, dependencies
- `code_reviews/2026-08-14_experiment-spec-and-compiler-design.md` — ExperimentSpec + compiler design (the roadmap)
- `src/instrument/CONTEXT.md` — instrument module reference (incl. operator/metric authoring)
- `scripts/CONTEXT.md` — script reference
- `experiments/CONTEXT.md` — experiment ecosystem
- `firebase/CONTEXT.md` — website documentation
- `docs/supervisor_design.md` — Control Room / supervisor subsystem (flag-only rail: observe, never steer); see also `docs/spec.md`, `docs/scope.md` for the fuller design cluster.

Both `src/instrument/experiment_spec.py` and `src/instrument/compile_experiment.py` are **written** — see `src/instrument/CONTEXT.md` for the module table and the ledger's still-unmeasured fields.

## Skills (load when entering a domain)

- `instrument` — running experiments + measurement pipeline knowledge
- `analyze` — post-hoc analysis pipeline
- `lab-books` — lab book analyses

## Conventions

Snake_case functions, PascalCase classes, type hints on public signatures. Deprecated: experiment.py, adapter.py, lab_book.py. Use opencode.py. Update `__init__.py` for new exports. Dataclasses over dicts.
