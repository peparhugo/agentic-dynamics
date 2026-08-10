# Analyze Experiments

Post-hoc analysis of completed experiments. Generates Game Reports and summary data
from raw worktree directories (`/tmp/exp_*`).

## Primary Workflow

```bash
# 1. Refresh inventory from opencode.db + worktrees
python scripts/inventory.py refresh

# 2. Analyze all worktrees → game reports + _results_summary.json
python scripts/analyze_worktrees.py
python scripts/analyze_worktrees.py --no-tests     # Skip pytest (faster)
python scripts/analyze_worktrees.py --worktree /tmp/exp_xyz  # Single worktree

# 3. Analyze session transcripts (step-level operational metrics)
python scripts/analyze_trajectories.py

# 4. Validate generated code
python scripts/validate_session.py --worktree /tmp/exp_xyz

# 5. Build website data
python scripts/build_data.py
```

## What Each Script Produces

| Script | Input | Output |
|--------|-------|--------|
| `analyze_worktrees.py` | `/tmp/exp_*` worktrees | GameReport `.md` files, `_results_summary.json` |
| `analyze_trajectories.py` | `session.jsonl` in worktrees | `_trajectory_summary.json`, `_trajectory_aggregate.json` |
| `validate_session.py` | Generated code in worktrees | Test pass/fail per worktree |
| `inventory.py` | opencode.db, worktrees, configs | `inventory.json` |
| `build_data.py` | inventory.json, _results_summary.json | `firebase/public/data.js` |

## Inspecting Results

```bash
python scripts/inventory.py list      # All experiments
python scripts/inventory.py stats     # Aggregate statistics
python scripts/inventory.py report    # Numbers for the evidence page
python scripts/inventory.py worktrees # List worktrees
```

## Game Report Format

Each GameReport (`experiments/results/reports/exp_*.md`) contains:
- Reasoning dynamics (trajectory, tool calls, exploration vs recovery)
- Solution quality (correctness, constraint satisfaction, tests passed)
- Resource efficiency (tokens, dollars, joules)
- Strategy archetype classification
- All metrics provenance-tagged [M]/[C]/[H]/[X]
