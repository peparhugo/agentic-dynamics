# `taskman` — design note and result

## Design

Pure-Python, stdlib-only package at the repo root, so `import taskman` resolves when pytest
runs from the checkout root.

- **One store, one writer.** `TaskManager` owns a single `dict[task_id, _Task]`. Validation is
  separated from mutation: every operation validates all candidate values into locals first and
  only touches the store at a commit point. This is what makes the cycle-rejection guarantee
  ("leaves state unchanged") mechanical rather than best-effort.
- **Dataclasses inside, plain dicts outside.** `_Task` gives explicit typed fields internally;
  `to_dict()` converts at the boundary and copies nested lists, so callers cannot mutate
  internal state through a returned dict.
- **Explicit creation order.** Each task carries a persisted `_seq` (not dict insertion order)
  as the tie-breaker, so `list_tasks` is `(-priority, _seq)` and the ordering survives
  save/load.
- **Cycle detection as reachability.** The dependency graph is acyclic by invariant. `add_task`
  can never create a cycle (new node, no inbound edges); only `update_task` checks, via an
  iterative DFS from the proposed deps looking for a path back to the edited task.
- **Unique ids** come from `uuid.uuid4().hex`, so uniqueness does not depend on a counter
  surviving a round-trip. `due_at` is validated with `datetime.fromisoformat` but the original
  string is stored verbatim, so the exact representation round-trips.

## Result

```
python3 -m pytest tests/flash_ladder/taskman_contract_test.py -q
13 passed in 0.05s
```

`ruff check taskman/` — all checks passed. No test files were modified.
