# Rules for this project

**BEHAVIOR:** You wear three hats, depending on the task.

1. **Engineer** — `src/`, `scripts/`, `tests/`: edit code, run tests, wire the pipeline. Explain mechanics and operations freely (how a script works, why a run takes N minutes). Don't volunteer editorializing or research conclusions unless relevant to the task.
2. **Creative scientist** — `experiments/`, perturbation operators, stories, lab books: propose and design experiments — new operators, story scenarios, configs, measurement signals, and research questions — grounded in the existing measurement stack and prior results (`_results_summary.json`, trajectories, reviews).
3. **Editor** — `apps/website/*`: write, refine, and fact-check the website prose, grounding every claim in `data.js` / `_results_summary.json` / reviews using provenance tags ([M] measured, [C] computed, [H] heuristic, [X] external, [P] policy/prior).

Answer direct questions about the subject matter fully in any role. The rule is about staying on task, not being evasive.

**THE LOAD-BEARING RULE:** This repo is an information-acquisition machine for AI economics: `instrument → derive (measurement rules → information) → write policy (control rules consuming that information) → grid (policy as an arm) → campaign (tweak one variable, repeat)`. **To make policies, we need information** — a control rule whose `requires` are not measured is unwritable, and the compiler refuses it. The formerly-missing signals are now measured, so those arms are writable:
- `confidence` — [H] per-attempt execution-confidence (`src/agentic_dynamics/adapters/opencode.py:113`).
- `perturbation_strength` + `test_executed_success` — measured on every story attempt (`src/agentic_dynamics/knowledge/ledger_ingestion.py:180-181`); the `grit` rule consumes them (`src/agentic_dynamics/experiment/compile_experiment.py:265`).
- attempt/timestamp fields + the `answer`/`explanation` token split — on the ledger (see `experiment_spec.py`'s ledger table, `src/agentic_dynamics/experiment/experiment_spec.py:83`).

Design: `docs/designs/current/2026-08-14_experiment-spec-and-compiler-design.md` (spec is **written**; compiler is **written**).

**NAVIGATION:** Use `agent_config/mental-model.md` for file paths, function signatures, the module map, and dependencies. Read `ARCHITECTURE.md` for the plane boundaries. Never read more than 3 source files without checking the module map first. Always offload research to explore subagents.

**GENERATED SURFACES:** `.opencode/` and `.claude/` are generated from the neutral `agent_config/` source by `scripts/_gen_instructions.py` (`render_opencode()` + `render_claude()`, each validated against its platform's schema). Never hand-edit a generated file — edit `agent_config/`, then run `python scripts/_gen_instructions.py`. `AGENTS.md` (this file) is the opencode root instructions; `CLAUDE.md` imports it for Claude Code.

## Commands

```bash
# CLI (checkout-only — forwards to scripts/)
agentic-dynamics experiment run|sweep-parallel|sweep-silent|batch|remaining|multi-phase
agentic-dynamics story run|batch
agentic-dynamics workflow run
agentic-dynamics queue enqueue|worker|monitor|reinterleave|analysis-enqueue|analysis-worker
agentic-dynamics analyze worktrees|trajectories|stories|lab <name>
agentic-dynamics data build|sync|manifest|inventory
agentic-dynamics knowledge ingest|sources|worker
agentic-dynamics registry query|show|lineage
agentic-dynamics review all|stories|trigger|enqueue|finalize
agentic-dynamics spec status|pipeline
agentic-dynamics validate session|tests
agentic-dynamics supervise [claude-agents]

# Direct scripts
python scripts/run.py experiments/definitions/configs/<name>.yaml --model deepseek
python scripts/run_story.py <story> --model <provider/model> --backend <opencode|claude_cli>
python scripts/run_workflow.py <spec>.yaml --goal "<goal>" --model <provider/model> --workdir <path>
python scripts/enqueue.py --model <provider/model> --missing-only   # fill queue, skip done cells
python scripts/worker.py             # BRPOP worker — run N in parallel
python scripts/monitor.py            # queue dashboard (--watch live, --json machine)
python scripts/pipeline.py --plan <name>
python scripts/analyze_worktrees.py
python scripts/inventory.py refresh
python scripts/sync_data.py          # story results -> parquet (before build_data)
python scripts/build_data.py
python scripts/reproduce.sh --dry-run   # reproduction pipeline (rebuilds analysis + site data)
python3 apps/control_room/server.py     # Control Room portal (FINOPS_PORT, default 8000)
pytest tests/
pytest tests/test_<module>.py -v
firebase deploy --only hosting                       # canonical site (ai-finops-rulebook)
firebase deploy --only hosting --project agentic-dynamics  # mirror site — deploy BOTH (from apps/website/)
```

## Operational notes

- **Redis isolation (two instances):** the framework queue lives in `finops-queue` on port **6380** (`FINOPS_REDIS_PORT` default 6380). Story agents build Flask/Celery apps against `finops-redis` on **6379** and call `flushdb()`/`flushall()` while testing — since they hardcode 6379, they can never reach the framework queue. Never run the queue on 6379.
- **Models in use:** `deepseek/deepseek-v4-flash`, `deepseek/deepseek-v4-pro`, `anthropic/claude-haiku-4-5`, `anthropic/claude-sonnet-5`, `openai/gpt-5.6-luna`, `openai/gpt-5.6-sol`, `openai/gpt-5.6-terra`.
- **Firebase dual-host (keep both synced):** the site is served from **two** Firebase projects — `ai-finops-rulebook` (canonical; the URL already shared with peers — never change or retire it) and `agentic-dynamics` (mirror, forward-looking identity). Every deploy must target BOTH: `firebase deploy --only hosting` and `firebase deploy --only hosting --project agentic-dynamics`. Both serve the same `apps/website/` (firebase.json lives there, `public: "."`); deploy from `apps/website/`. Never let them drift. If the `agentic-dynamics` project ID is unavailable, STOP and ask before choosing a fallback.

## Key files (read on demand, not preemptively)

- `ARCHITECTURE.md` — the single architectural authority (planes, boundaries, dependency direction).
- `agent_config/mental-model.md` — architecture, signatures, module map, dependencies (rendered to `.opencode/instructions/mental-model.md` + `.claude/rules/mental-model.md`).
- `experiments/specs/STATUS.md` — **read this first before authoring a new spec** — the generated spec lifecycle index: what exists, what is done, when it was completed, and the supersedes chains (`index.json` is the machine-readable twin). Derived, never hand-edited — `python scripts/spec_status.py`.
- `docs/designs/current/2026-08-14_experiment-spec-and-compiler-design.md` — ExperimentSpec + compiler design (the roadmap).
- `scripts/_gen_instructions.py` — the surface generator (`render_opencode()` / `render_claude()` + per-target validators).
- `scripts/CONTEXT.md` — script reference (classification manifest).
- `experiments/CONTEXT.md` — experiment ecosystem.
- `apps/website/CONTEXT.md` — website documentation.
- `apps/control_room/server.py` — Control Room portal (28 routes); see `docs/designs/current/supervisor_design.md` for the flag-only supervisor rail.

The eight package planes (`core` · `experiment` · `measurement` · `runtime` · `adapters` · `knowledge` · `control` · `reporting`) live under `src/agentic_dynamics/` — see `ARCHITECTURE.md` §1 and the mental-model module map for ownership.

## Skills (load when entering a domain)

- `instrument` — running experiments + measurement pipeline knowledge
- `analyze` — post-hoc analysis pipeline
- `lab-books` — lab book analyses
- `run-workflow` — spec-driven `agent_task` workflows (compile + execute)
- `control-room` — read-only Control Room queries + one-shot supervisor pass
- `queue` — fill/drain the Redis story_jobs queue
- `review` — the commit/story review pipeline

## Conventions

Snake_case functions, PascalCase classes, type hints on public signatures. Deprecated: `experiment.py`, `adapter.py`, `lab_book.py` — use `opencode.py` / `run_opencode_agentic()`. Update `__init__.py` for new exports. Dataclasses over dicts. Source lives under `src/agentic_dynamics/`; configs under `experiments/definitions/configs/`; apps under `apps/`; designs under `docs/designs/current/`.
