# `taskman` design log

## The design space (three materially different internal designs)

The obvious implementation is a mutable `dict[str, dict]`. The three candidates
below differ across every axis the brief named — data model, ordering,
persistence, and cycle detection.

### A. Mutable dict-of-dicts (the obvious baseline)

- **Data model.** `self._tasks: dict[str, dict]`; every write mutates a task dict
  in place.
- **Ordering.** Rely on dict insertion order plus Python's stable sort
  (`sort(key=lambda t: -t["priority"])`) to keep creation order on ties.
- **Persistence.** `json.dump(self._tasks, ...)`; `load` reads the snapshot back.
- **Cycle detection.** DFS/BFS at mutation time, with a hand-written snapshot and
  rollback if the new edge closes a cycle.

### B. Immutable records + a maintained reverse-dependency index

- **Data model.** Frozen `Task` dataclasses in a copy-on-write mapping, plus a
  derived `dependents: dict[str, set[str]]` index for O(1) delete guards and
  ready-set maintenance.
- **Ordering.** An explicit monotonic `seq` counter; sort by `(-priority, seq)`.
- **Persistence.** Serialize the record mapping (a snapshot).
- **Cycle detection.** Kahn topological sort over the whole dependency graph
  (leftover nodes ⇒ cycle).

### C. Event-sourced append-only journal + pure fold  ← **chosen**

- **Data model.** There is no mutable task state. The manager owns one append-only
  `list[Event]`; the visible `{task_id: Task}` is a **pure fold** (`project`) over
  that journal. `Task` is frozen.
- **Ordering.** Creation order is a `seq` carried inside `add` events and derived
  from the journal on load, so it never regresses across deletes.
- **Persistence.** `save` writes the **journal**, not the projected state; `load`
  is literally replay (`TaskManager.load == project(events)`).
- **Cycle detection.** An iterative three-colour DFS run against a *speculative*
  fold `project(existing + candidate)`.

## Why C is the most different from the obvious approach

A starts from mutable state and derives persistence from it. C inverts the
direction: **the log is the source of truth and the state is derived.** Nothing
is ever mutated in place — a write appends an immutable event and re-folds.

That inversion pays for itself in the contract's hardest requirement, "a cycle
(and every other rejected edit) leaves state unchanged":

1. build the candidate event,
2. fold `existing + candidate` into a *trial* state,
3. validate the trial (fields, referential integrity, acyclicity),
4. only on success adopt the longer journal **and** the trial state together.

Because step 4 is the only mutation, a failure cannot leave a partial edit
behind — the "unchanged on rejection" property is structural, not a rollback
dance. The same purity makes `save`/`load` exact: the file is the history, and
replaying it reconstructs the identical store.

Trade-off accepted: every mutation re-folds the whole journal, so writes are
O(n) rather than O(1). At the contract's scale that is irrelevant, and it buys
the invariant above plus trivially auditable state. A production version would
keep an incremental projection while preserving the append-only log.

## Files

| File | Responsibility |
|---|---|
| `_model.py` | Frozen `Task`, field validators/normalizers, public-dict projection |
| `_graph.py` | Iterative DFS cycle detection; `(-priority, seq)` ordering |
| `_journal.py` | `Event`, pure `project` fold, JSON (de)serialization |
| `manager.py` | `TaskManager` — the validating shell over the journal |
| `__init__.py` | Public export (`TaskManager`, `SCHEMA_ID`) |

## Log

- **Design chosen:** event-sourced journal + pure fold (C above).
- **Test result:** `python3 -m pytest tests/flash_ladder/taskman_contract_test.py -q`
  → **13 passed**. Additional hand checks (self-cycle, duplicate deps, delete
  guard, save/load after a delete, update-cycle atomicity) also pass.
