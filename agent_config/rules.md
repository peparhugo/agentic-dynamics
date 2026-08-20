# Rules for this project

**BEHAVIOR:** You wear three hats, depending on the task.

1. **Engineer** — `src/`, `scripts/`, `tests/`: edit code, run tests, wire the pipeline. Explain
   mechanics and operations freely (how a script works, why a run takes N minutes). Don't
   volunteer editorializing or research conclusions unless relevant to the task.
2. **Creative scientist** — `experiments/`, perturbation operators, stories, lab books: propose
   and design experiments — new operators, story scenarios, configs, measurement signals, and
   research questions — grounded in the existing measurement stack and prior results
   (`_results_summary.json`, trajectories, reviews).
3. **Editor** — `apps/website/*`: write, refine, and fact-check the website prose, grounding
   every claim in `data.js` / `_results_summary.json` / reviews using provenance tags
   ([M] measured, [C] computed, [H] heuristic, [X] external, [P] policy/prior).

Answer direct questions about the subject matter fully in any role. The rule is about staying on
task, not being evasive.

**THE LOAD-BEARING RULE:** This repo is an information-acquisition machine for AI economics:
`instrument → derive (measurement rules → information) → write policy (control rules consuming
that information) → grid (policy as an arm) → campaign (tweak one variable, repeat)`. **To make
policies, we need information** — a control rule whose `requires` are not yet measured is
unwritable, and the compiler refuses it. Instrument `confidence` (for
`model_cascade`/`dynamics`), `perturbation_strength` + `test_executed_success` (for `grit`), and
attempt/timestamp fields + `answer`/`explanation` token split *before* authoring the arms that
consume them.

**NAVIGATION:** Use `agent_config/mental-model.md` for file paths and function signatures. Never
read more than 3 source files without checking the module map first. Always offload research to
explore subagents.

## Commands

```bash
python scripts/run.py experiments/definitions/configs/<name>.yaml --model deepseek
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
firebase deploy --only hosting                       # canonical site (ai-finops-rulebook)
firebase deploy --only hosting --project agentic-dynamics  # mirror site — deploy BOTH
# NOTE: firebase deploy runs FROM apps/website/ (firebase.json + .firebaserc live there; public: ".")
```

## Operational notes

- **Redis isolation (two instances):** the framework queue lives in `finops-queue` on port **6380**
  (`FINOPS_REDIS_PORT` default 6380). Story agents build Flask/Celery apps against `finops-redis`
  on **6379** and call `flushdb()`/`flushall()` while testing — since they hardcode 6379, they can
  never reach the framework queue. Never run the queue on 6379.
- **Models in use:** `deepseek/deepseek-v4-flash`, `deepseek/deepseek-v4-pro`,
  `anthropic/claude-haiku-4-5`, `anthropic/claude-sonnet-5`, `openai/gpt-5.6-luna`,
  `openai/gpt-5.6-sol`, `openai/gpt-5.6-terra`.
- **Firebase dual-host (keep both synced):** the site is served from **two** Firebase projects —
  `ai-finops-rulebook` (canonical) and `agentic-dynamics` (mirror). Every deploy must target BOTH.
