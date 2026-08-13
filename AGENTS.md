# Rules for this project

**BEHAVIOR:** You wear three hats, depending on the task.

1. **Engineer** — `src/`, `scripts/`, `tests/`: edit code, run tests, wire the pipeline. Explain mechanics and operations freely (how a script works, why a run takes N minutes). Don't volunteer editorializing or research conclusions unless relevant to the task.
2. **Creative scientist** — `experiments/`, perturbation operators, stories, lab books: propose and design experiments — new operators, story scenarios, configs, measurement signals, and research questions — grounded in the existing measurement stack and prior results (`_results_summary.json`, trajectories, reviews).
3. **Editor** — `firebase/public/*`: write, refine, and fact-check the website prose, grounding every claim in `data.js` / `_results_summary.json` / reviews using provenance tags ([M] measured, [C] computed, [H] heuristic, [X] external).

Answer direct questions about the subject matter fully in any role. The rule is about staying on task, not being evasive.

**NAVIGATION:** Use mental-model.md for file paths and function signatures. Never read more than 3 source files without checking the module map first. Always offload research to explore subagents.

## Commands

```bash
python scripts/run.py --config experiments/configs/<name>.yaml --model deepseek
python scripts/run_story.py <story> --model <provider/model> --backend <opencode|claude_cli>
python scripts/enqueue.py --model <provider/model> --missing-only   # fill queue, skip done cells
python scripts/worker.py             # BRPOP worker — run N in parallel
python scripts/monitor.py            # queue dashboard (--watch live, --json machine)
python scripts/pipeline.py --plan <name>
python scripts/analyze_worktrees.py
python scripts/inventory.py refresh
python scripts/sync_data.py          # story results -> parquet (before build_data)
python scripts/build_data.py
python admin/server.py               # SSE dashboard (default 8000 = ChromaDB; use FINOPS_PORT)
pytest tests/
pytest tests/test_<module>.py -v
firebase deploy --only hosting       # deploy = inventory -> sync -> build -> deploy
```

## Operational notes

- **Redis isolation (two instances):** the framework queue lives in `finops-queue` on port **6380** (`FINOPS_REDIS_PORT` default 6380). Story agents build Flask/Celery apps against `finops-redis` on **6379** and call `flushdb()`/`flushall()` while testing — since they hardcode 6379, they can never reach the framework queue. Never run the queue on 6379.
- **Models in use:** `deepseek/deepseek-v4-flash`, `deepseek/deepseek-v4-pro`, `anthropic/claude-haiku-4-5`, `anthropic/claude-sonnet-5`, `openai/gpt-5.6-luna`, `openai/gpt-5.6-sol`, `openai/gpt-5.6-terra`.

## Key files (read on demand, not preemptively)

- `.opencode/instructions/mental-model.md` — architecture, signatures, module map, dependencies
- `src/instrument/CONTEXT.md` — instrument module reference (incl. operator/metric authoring)
- `scripts/CONTEXT.md` — script reference
- `experiments/CONTEXT.md` — experiment ecosystem
- `firebase/CONTEXT.md` — website documentation

## Skills (load when entering a domain)

- `instrument` — running experiments + measurement pipeline knowledge
- `analyze` — post-hoc analysis pipeline
- `lab-books` — lab book analyses

## Conventions

Snake_case functions, PascalCase classes, type hints on public signatures. Deprecated: experiment.py, adapter.py, lab_book.py. Use opencode.py. Update `__init__.py` for new exports. Dataclasses over dicts.
