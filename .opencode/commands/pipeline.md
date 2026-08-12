---
description: Run the full data pipeline from inventory to website deploy
agent: build
subtask: true
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
