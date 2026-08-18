# Implementation trace — R3 + R9 + BUG-2 (task-type vocabulary unification)

Phase 3 (trace) of `repo_review_fable`. Traces every change required by R3/R9
(`docs/review/restructure.md`) and BUG-2 (`docs/review/bugs.md`) to its concrete
location in source, with a PASS/FAIL verdict per item and the gate result. All
`file:line` references are re-read from the working tree at this commit.

---

## 1. The single source of truth — `src/instrument/session_types.py`

R9's "After" asks for "a single `TaskType`/session-pattern definition in
`experiment_spec` (or a new `session_types.py`)". Chose **`session_types.py`** over
`experiment_spec.py`:

- `experiment_spec.py` is the spec/compiler dataclass surface (452 lines of
  `Workflow`/`Factor`/`RuleSpec` dataclasses + YAML loader + the requires/produces
  validator). The vocabulary is consumed by `routing`, `story`, and `ledger_ingestion`
  — none of which are spec/compiler modules — so folding it into `experiment_spec`
  would force unrelated consumers to depend on the spec layer.
- A dedicated leaf module keeps the vocabulary **dependency-light**: it imports only
  `re`, so importing it never drags the Redis/Chroma/Neo4j machinery of the package
  (the R6 "value-only import that doesn't pull redis" concern, applied to R3/R9).

Three definitions now live here, one per prior duplication:

| Item | Location | Prior state |
|---|---|---|
| `EXPERIMENT_SESSION_PATTERNS` | `session_types.py:55` | declared in `scripts/_constants.py:23` |
| `normalize_task` | `session_types.py:68` | duplicated in `routing.py:16` + `_constants.py:53` |
| `TASK_TYPES` / `DEFAULT_TASK_TYPE` | `session_types.py:40-44` | bare string `"feature_addition"` in `story.py` |

**PASS.**

---

## 2. R3 — delete the `scripts/` reverse-import and its dead branch

R3's seam is `ledger_ingestion._load_experiment_session_patterns` +
`classify_session` (`ledger_ingestion.py:79-126` at review time).

### 2a. `_load_experiment_session_patterns` deleted

- Removed the `importlib.util.spec_from_file_location` exec of
  `scripts/_constants.py` (was `ledger_ingestion.py:79-103`), the module-level call
  `EXPERIMENT_SESSION_PATTERNS = _load_experiment_session_patterns()` (was `:103`),
  and the now-unused `import importlib.util` + `PROJECT_ROOT` import.
- The only `src/instrument → scripts` edge in the package is gone. `import
  instrument` no longer assumes the `scripts/` directory layout exists.

### 2b. `classify_session` collapsed to the `meta_` prefix check

`src/instrument/ledger_ingestion.py:78-99` is now the two-way result it actually was:

```python
def classify_session(session_title: str) -> str:
    if session_title.startswith("meta_"):
        return SOURCE_TYPE_META
    return SOURCE_TYPE_ATTEMPT
```

The dead middle branch (`if any(p in ... for p in EXPERIMENT_SESSION_PATTERNS):
return SOURCE_TYPE_ATTEMPT`) and its identical fallthrough were removed; the docstring
now documents *why* (both returned the same value, so the list never changed output).

**PASS** — verified two ways:
- `python3 -c "import instrument"` succeeds and `_finops_scripts_constants` (the
  module name the old exec registered) is **absent** from `sys.modules`.
- No reference to `_load_experiment_session_patterns`, `importlib`, or `PROJECT_ROOT`
  remains in `ledger_ingestion.py`.

---

## 3. R9 — one task-type vocabulary

### 3a. Edge reversed: `scripts/_constants.py` imports *from* instrument

`scripts/_constants.py:3-4` now:

```python
from instrument.session_types import EXPERIMENT_SESSION_PATTERNS as EXPERIMENT_SESSION_PATTERNS
from instrument.session_types import normalize_task as normalize_task
```

The `as X as X` form is the explicit re-export idiom (satisfies ruff F401) so the 6
call sites that still do `from _constants import EXPERIMENT_SESSION_PATTERNS` /
`normalize_task` (e.g. `analyze_worktrees.py`, `inventory.py`, 4 lab books) keep
working unchanged.

### 3b. `normalize_task` deduplicated

- `routing.py:14` is `from .session_types import normalize_task` (local def deleted);
  `routing.py:156` still uses it internally in `compute_routing`.
- `_constants.py`'s local def (was `:53`) deleted.
- `routing.normalize_task is session_types.normalize_task` is `True` (single object).

### 3c. `story.SessionSpec.task_type` wired to the vocabulary

- `story.py:37` imports `DEFAULT_TASK_TYPE`; `story.py:143` documents the field as
  `see instrument.session_types.TASK_TYPES`; `story.py:162` replaces the bare
  `"feature_addition"` default with `DEFAULT_TASK_TYPE`.

**PASS.**

---

## 4. BUG-2 — the dead branch and the fragile loader

BUG-2's fix is exactly §2 above (move the list into `src/instrument/`, reverse the
edge, collapse `classify_session`). The reproduction precondition is now structurally
impossible: `classify_session` no longer reads `EXPERIMENT_SESSION_PATTERNS` at all, so
there is no branch to be dead and no loader to be fragile.

**PASS.**

---

## 5. Barrel export — `src/instrument/__init__.py`

- Import block added at `__init__.py:161-165`
  (`DEFAULT_TASK_TYPE`, `EXPERIMENT_SESSION_PATTERNS`, `TASK_TYPES`, `normalize_task`).
- `__all__` entries added at `__init__.py:455`.
- `normalize_task` moved out of the `from .routing import ...` line (it now comes
  from `session_types` directly; `routing` still re-exports it for
  `from instrument.routing import normalize_task` callers).

**PASS.**

---

## 6. Test update — the reversed invariant

`tests/test_ledger_ingestion.py:120-135` replaced
`test_classify_session_uses_the_real_analyze_worktrees_pattern_list` (which asserted
the *old* reverse-import behavior) with
`test_experiment_session_patterns_live_in_instrument_not_scripts`, asserting the new
invariant via identity:

```python
assert module.EXPERIMENT_SESSION_PATTERNS is st.EXPERIMENT_SESSION_PATTERNS
assert module.normalize_task is st.normalize_task
```

where `module` is `scripts/_constants.py` loaded by path. This guards against the list
ever being re-declared (or re-copied) back into `scripts/`. The remaining
`classify_session` behavior tests (meta-batch routing, real-experiment titles,
unclassified-title registration) are unchanged and still pass.

**PASS.**

---

## 7. Gate result

```text
$ pytest tests/ -m "not external" -q
1026 passed, 101 deselected, 19 warnings in 18.59s
```

Targeted gate (the four files named in the task's VERIFY line):

```text
$ pytest tests/test_ledger_ingestion.py tests/test_step_routing.py \
    tests/test_routing.py tests/test_workflow_runner.py -q
70 passed
```

`ruff check` on all touched files: **clean**. `import instrument` does not exec
`scripts/_constants.py` (`_finops_scripts_constants` absent from `sys.modules`).

---

## 8. Do-not-do items honored

- **No** `source_type` field added to `KnowledgeEvent` (restructure.md §5.2 — only R2
  formalizes the registry; out of scope here).
- **No** re-declared copy of the pattern list left in `scripts/` — `_constants.py`
  imports, doesn't define.
- **No** fabrication: `None ≠ 0.0` and the authority ordinal untouched (this change is
  KB-local vocabulary cleanup; provenance and comparability are preserved by
  construction, per restructure.md §6).

---

*Traced at the `feature/task-vocabulary-unify` working tree; prior-review line numbers
quoted from `docs/review/restructure.md` / `docs/review/bugs.md` (reviewed at commit
`1baff2a6f`).*
