# taskman — design note

## Contract
Pure-Python, stdlib-only package exposing `TaskManager`, satisfying
`tests/flash_ladder/taskman_contract_test.py` (13 behavioural tests).

## Design
- **State**: one insertion-ordered `dict[task_id -> task dict]`. Dict order *is*
  creation order, so priority-tie ordering is just a stable sort.
- **Id**: `uuid.uuid4().hex` (unique without cross-cell coordination).
- **Validation**: priority (int, 1..5, bools rejected), `due_at`
  (`datetime.fromisoformat`, original string preserved for exact round-trip),
  tags (iterable, bare string rejected), dependencies (must exist, no self-ref).
- **Atomic writes**: every mutation builds a `deepcopy` candidate, validates the
  candidate's graph, then swaps it in — a rejected update leaves state unchanged.
  This is what the cycle test asserts.
- **Cycle detection**: iterative DFS with white/grey/black colouring; a
  back-edge to a grey node is a cycle (iterative to avoid recursion limits).
- **Queries**: `list_tasks` filters then stable-sorts by priority descending;
  `ready_tasks` returns not-`done` tasks whose deps are all `done`. Reads return
  deep copies so callers cannot mutate internal state.
- **Persistence**: JSON `{version, tasks: [...]}`; `load` is a two-pass
  rebuild (place all, then validate) so hand-edited file ordering is safe.

## Result
`python3 -m pytest tests/flash_ladder/taskman_contract_test.py -q` → **13 passed**.
No test file modified.
