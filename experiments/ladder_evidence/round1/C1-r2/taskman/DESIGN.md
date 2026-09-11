# taskman — design note

Cell log for the flash-ladder `taskman` generation task. The brief asked for at least three
materially different internal designs before implementing the one judged *most different from
the most obvious approach*. Those alternatives and the chosen design are recorded here, followed
by the verification result.

## Candidate designs

### Design A — mutable dict-of-dicts (the obvious baseline)

* **Data model:** `{task_id: {"title": ..., "priority": ..., ...}}`; the public dict *is* the
  internal record, so `get_task` can hand out the live object.
* **Ordering:** re-sort on every `list_tasks()` with a stable `sorted(key=lambda t: -t["priority"])`,
  relying on Python's stable sort plus dict insertion order for the tie-break.
* **Persistence:** `json.dump(self._tasks)`.
* **Cycle detection:** recursive depth-first search from the edited node over `depends_on`.
* **Why rejected:** it is the approach anyone reaches for first; it leaks internal state, makes
  "state unchanged on a rejected update" an accident of call ordering, and recursion depth is an
  unexamined input.

### Design B — relational, in-memory (normalised tables)

* **Data model:** one dict per *relation* — `tasks`, `task_tags`, `task_deps` — treated as tables,
  with foreign-key checks performed by hand at write time.
* **Ordering:** a materialised `ORDER BY priority DESC, seq` sequence rebuilt after every mutation.
* **Persistence:** the three tables serialised separately and re-joined on load.
* **Cycle detection:** a Floyd–Warshall transitive closure over the dependency relation; a cycle
  exists when the closure has a self-loop.
* **Why rejected:** the normalisation is real work for no consumer (nothing queries tags/deps as
  independent relations), and an O(V^3) closure on every edit is wasteful for this contract.

### Design C — immutable records + derived indexes (chosen)

* **Data model:** each task is a frozen `Task` dataclass; the manager owns *derived* structure —
  a forward `_tasks` map, a reverse `_dependents` adjacency map, and an ordered id list. Public
  reads return fresh dicts, so callers cannot mutate internal state.
* **Ordering:** the id list is kept continuously sorted by `(-priority, seq)` using
  `bisect.insort` with a key, rather than re-sorted per query. `seq` is a monotonic creation
  counter, which makes the tie-break explicit rather than an implicit property of dict order.
* **Persistence:** a versioned, canonical snapshot (`"schema": "taskman/v1"`) storing records in
  creation order + `next_seq`. `load` rebuilds every derived index from the records — it never
  trusts stored adjacency — so a saved file can never smuggle in an inconsistent graph.
* **Cycle detection:** Kahn's topological elimination over the *whole* candidate graph. If the
  number of nodes eliminated is less than the node count, a directed dependency cycle exists.
  The candidate graph is assembled and validated before any mutation, which is what makes the
  "cycle leaves state unchanged" contract structural instead of best-effort.
* **Why chosen:** it is the design that differs on all four axes (immutable model, incrementally
  maintained ordering, versioned rebuild-on-load persistence, Kahn instead of DFS) while keeping
  every mutation a validate-then-commit transaction.

## Verification

```
$ python3 -m pytest tests/flash_ladder/taskman_contract_test.py -q
.............                                                            [100%]
13 passed in 0.08s
```

Result: **13 passed**, no test files modified.

- The incremental `bisect.insort` ordering was exercised by `test_list_tasks_orders_by_priority_desc`
  and by the priority-changing `update_task` in `test_update_fields_and_unknown_id`.
- Kahn cycle detection was exercised by `test_cycle_detection_leaves_state_unchanged`; the
  candidate-graph-first ordering is what leaves the two tasks' dependencies untouched.
- Versioned rebuild-on-load persistence was exercised by `test_save_load_round_trip`.
