# Rules for this project

**BEHAVIOR:** Do not analyze, summarize, discuss, or evaluate the project's subject matter (FinOps, AI costs, Grit, perturbation theory, experiments). This is a codebase with Python files. You edit them. You run tests. That's it. Stay quiet about what the project means. If the user asks about FinOps specifically, answer directly and briefly.

**NAVIGATION:** Use mental-model.md for file paths and function signatures. Never read more than 3 source files without checking the module map first. Always offload research to explore subagents.

## Commands

```bash
python scripts/run.py --config experiments/configs/<name>.yaml --model deepseek
python scripts/run_story.py <story> --model <provider/model> --backend <opencode|claude_cli>
python scripts/pipeline.py --plan <name>
python scripts/analyze_worktrees.py
python scripts/inventory.py refresh
python scripts/sync_data.py          # story results -> parquet (before build_data)
python scripts/build_data.py
python admin/server.py               # live control plane (port 8000)
pytest tests/
pytest tests/test_<module>.py -v
firebase deploy --only hosting       # deploy = inventory -> sync -> build -> deploy
```

## Key files (read on demand, not preemptively)

- `.opencode/instructions/mental-model.md` — architecture, signatures, module map, dependencies
- `src/instrument/CONTEXT.md` — instrument module reference
- `scripts/CONTEXT.md` — script reference
- `experiments/CONTEXT.md` — experiment ecosystem
- `firebase/CONTEXT.md` — website documentation

## Skills (load when entering a domain)

- `instrument` — running experiments + measurement pipeline knowledge
- `analyze` — post-hoc analysis pipeline
- `lab-books` — lab book analyses

## Conventions

Snake_case functions, PascalCase classes, type hints on public signatures. Deprecated: experiment.py, adapter.py, lab_book.py. Use opencode.py. Update `__init__.py` for new exports. Dataclasses over dicts.
