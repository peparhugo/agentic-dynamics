# `taskman` — design note and test log

## Design

A single stdlib-only package at the repo root (`taskman/`), because
`scripts/run_flash_ladder.py:_export_cell` archives the top-level `taskman`
directory verbatim for scoring — the package must be self-contained and
importable with only the repo root on `sys.path`.

**Data model.** Internally the store is an ordered `dict[str, Task]` keyed by a
`uuid4().hex` id, where `Task` is a frozen dataclass. Frozen so that a reference
cannot be mutated in place; `update_task` builds a replacement with
`dataclasses.replace` only after all validation passes. `get_task` / `list_tasks`
/ `ready_tasks` return fresh `dataclasses.asdict` copies, so callers cannot alter
the store through a returned dict.

**Ordering.** Python dicts preserve insertion order, and tasks are only ever
appended in creation order, so insertion order *is* creation order. Listing
sorts stably by `-priority`: deterministic priority-descending with creation
order breaking ties, with no secondary index to keep in sync.

**Atomic validation.** Every mutating method validates *all* inputs (and the
proposed dependency graph) before rebinding the store. The cycle test depends on
this: `update_task(first, depends_on=[second])` computes the candidate, runs a
colour-marking DFS over the adjacency implied by the store with the candidate's
edges substituted, raises `ValueError`, and never mutates.

**Cycle detection.** Whole-graph DFS with an active-stack ("grey") set; revisiting
a grey node is a back-edge. On `add_task` a cycle is impossible because the new
node has no incoming edges yet, so only dependency existence is checked.

**Validation rules.** Priority is an `int` in 1..5 (`bool` rejected explicitly —
it is an `int` subclass and `True` masquerading as priority 1 is a bug). Status
is one of `todo`/`doing`/`done`. `due_at` is validated with
`datetime.fromisoformat` (tolerating a trailing `Z` for 3.10) but the *original
string* is stored, keeping save/load an exact round-trip. Dependency ids must
already exist, may not be self, and are de-duplicated preserving order.

**Persistence.** `save` writes a JSON object `{"version": 1, "tasks": [...]}` in
creation order; `load` re-inserts in file order, reproducing the original
tie-breaking. Only known fields are read, so future extra keys still load.

## Test log

```
python3 -m pytest tests/flash_ladder/taskman_contract_test.py -q
.............  [100%]
13 passed in 0.08s
```

All 13 contract tests pass. A manual smoke run additionally confirmed
dependency de-duplication, ready-set computation, the priority/due-date/cycle
rejections (with state unchanged after the cycle rejection), and the
delete-dependents ordering rule.
