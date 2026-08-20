---
description: Run post-hoc analysis on experiment worktrees
---

Run the full post-hoc analysis pipeline on experiment worktrees.

First, load the "analyze" skill. Then:

1. Refresh inventory: `python scripts/inventory.py refresh`
2. Analyze worktrees: `python scripts/analyze_worktrees.py`
3. Analyze trajectories: `python scripts/analyze_trajectories.py`
4. Build website data: `python scripts/build_data.py`

If a specific worktree is needed: `python scripts/analyze_worktrees.py --worktree /tmp/exp_$ARGUMENTS`

Use `--no-tests` to skip pytest for speed. Use `--limit N` to process only N worktrees.

Report: number of worktrees processed, game reports generated, any failures.
