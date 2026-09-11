# taskman design note

Pure-Python, stdlib-only package exposing `TaskManager` at `taskman/__init__.py`.

## Design
- **Store:** one insertion-ordered `dict` of `id -> task record`. Dict insertion order is
  creation order, which the contract needs for priority-tie ordering.
- **IDs:** `uuid4().hex` — unique within and across processes, and stable through save/load.
- **Validation-before-mutation:** every validator runs before the record is touched, so a
  rejected `update_task` leaves state exactly as it was (cycle case in the contract).
- **`due_at`:** validated with `datetime.fromisoformat` but stored as the original string, so
  the JSON round-trip is byte-exact.
- **Ordering:** `list_tasks` sorts by `-priority`; Python's stable sort preserves creation order
  for ties. `ready_tasks` filters not-done tasks whose dependencies are all done.
- **Cycles:** DFS over a temporary adjacency map built with the proposed dependency list; a
  back-edge raises `ValueError` before any write.
- **Persistence:** JSON `{"tasks": [...]}`; `save`/`load` round-trip all fields.

## Result
`python3 -m pytest tests/flash_ladder/taskman_contract_test.py -q` → **13 passed**.
