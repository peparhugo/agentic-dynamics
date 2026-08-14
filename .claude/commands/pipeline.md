---
description: Run the full data pipeline from inventory to website deploy
---

Run the complete data pipeline: inventory refresh → analysis → website build → deploy.

This is the `deploy` plan in `experiments/configs/plans.yaml`. Prefer running it via
`python scripts/pipeline.py --plan deploy` for dependency tracking and idempotent resumption.
To run the steps manually (or when Redis is unavailable), load the "analyze" skill and execute in order:

1. `python scripts/inventory.py refresh`
2. `python scripts/inventory.py list`  (verify inventory)
3. `python scripts/analyze_worktrees.py`
4. `python scripts/analyze_trajectories.py`
5. `python scripts/build_data.py`
6. `firebase deploy --only hosting`

Report each step's output and any errors encountered.

Spec direction: `compile_experiment.py` is written and can add a compile/validate phase
(`validate → cells → execute → measure → compare → writeup → adapt`) ahead of this chain; this
command's manual chain still runs the transport-only path directly. See
`code_reviews/2026-08-14_experiment-spec-and-compiler-design.md`.
