# taskman — design log

## Design

Pure-Python, stdlib-only package exposing `TaskManager` (`taskman/__init__.py`,
`taskman/manager.py`).

- **Immutable records.** A task is a frozen `Task` dataclass. Mutations replace the
  record for an id; a stored record is never edited in place. `get_task`/`list_tasks`/
  `ready_tasks` project to fresh plain dicts (with fresh `tags`/`depends_on` lists) so a
  caller cannot mutate store state through a returned value.
- **Validate-then-commit.** Every write builds a candidate state, runs all checks
  (priority band, parseable `due_at`, duplicate-free tags/deps, referential integrity,
  cycle detection), and only then assigns the new mapping. A rejected edit therefore
  *structurally* leaves state unchanged — the property `test_cycle_detection_leaves_state_unchanged`
  and the delete-refusal test assert.
- **Derived ordering.** Nothing stores a sort key except a monotonic creation `seq`
  assigned on insert. `list_tasks` and `ready_tasks` sort by `(-priority, seq)`, giving
  priority-descending with creation-order tie-break.
- **Cycle detection.** Iterative three-colour DFS over `id -> depends_on`; a gray child
  is a back-edge. Iterative so deep chains cannot hit the recursion limit.
- **Persistence.** `save` writes a JSON document (`schema`, `seq`, ordered `tasks` list);
  `load` rehydrates it literally, preserving creation order and the counter. No
  re-validation on load — the persisted document is the authority.
- **Ids.** `uuid4().hex`, unique across process boundaries and reloads.

## Verification

`python3 -m pytest tests/flash_ladder/taskman_contract_test.py -q` → **13 passed**.
`ruff check taskman/` → clean.
