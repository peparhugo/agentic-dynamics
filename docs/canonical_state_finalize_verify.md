# canonical_state_finalize — Verify

Verify pass for `experiments/specs/canonical_state_finalize.yaml`'s `verify` phase, run
against `feature/canonical-state-finalize` at commit `e66790776` (2026-08-18). Traces the
three consumer/projection gaps the spec named (see the spec's `remaining_gaps` field and
`code_reviews`/`docs/canonical_state_r2_design.md`) to the code that closes each one, with
the pytest evidence for every claim below — no gap is marked PASS on narrative alone.

## Gap → code trace

| Gap | What was broken | Files that close it | Key functions | Tests | Verdict |
|---|---|---|---|---|---|
| **G1** — `kb-registry-v1`/`kb-neo4j-v1` never saw `KnowledgeEvent.operation`, so a `delete` tombstone or `supersede` chain landed in the stream correctly but was recorded as `lifecycle_state: "current"` regardless | `src/instrument/knowledge_stream.py`, `scripts/kb_worker.py` | `knowledge_stream._handler_wants_operation` (L367), `knowledge_stream.process_entry` (L387, now threads `operation`/`reason` into any handler that declares an `operation` parameter — chroma/ledger handlers unaffected); `kb_worker._lifecycle_state_for` (L107), the `kb-registry-v1` handler (L267, derives `lifecycle_state` per operation and appends a "predecessor superseded" marker line on `supersede`), the `kb-neo4j-v1` handler (L385, persists `lifecycle_state`, gates the `SUPERSEDES` edge on `operation == "supersede"`, adds `CLEARED_BY`/`REPLACED_BY` edges) | `tests/test_knowledge_stream.py` (20 tests, incl. `test_process_entry_passes_operation_to_an_opted_in_handler`, `test_process_entry_does_not_pass_operation_to_a_plain_handler`), `tests/test_kb_worker.py` (subset: `test_kb_registry_v1_handler_delete_is_tombstoned`, `test_kb_registry_v1_handler_supersede_marks_predecessor_superseded_with_effective_valid_to`, `test_kb_neo4j_v1_handler_persists_lifecycle_state_*`, `test_kb_neo4j_v1_handler_does_not_write_supersedes_edge_for_upsert`, `test_kb_neo4j_v1_handler_writes_cleared_by_edge_for_flag_tombstone`, `test_kb_neo4j_v1_handler_writes_replaced_by_edge_for_non_flag_tombstone`) | **PASS** |
| **G2** — `generate_manifest.py`'s registry compaction took the latest-by-`indexed_at` row per `entity_id` verbatim; it never derived `superseded`/`tombstoned` from the `supersedes`/delete chain, and a `supersede`'s two same-`indexed_at`, same-`entity_id` lines (the successor's own line + G1's predecessor marker) could nondeterministically pick the wrong one as "current" | `scripts/generate_manifest.py` | `_iter_registry_rows` (L49), `_derive_lifecycle` (L74, derives `(lifecycle_state, valid_to)` purely from the `supersedes` chain — works even without G1's marker line present), `_compact_registry_index` (L110, redesigned as two passes: dedupe by `knowledge_id` first — not `entity_id` — then roll each entity's versions up into one head row + a nested `versions` history) | `tests/test_generate_manifest.py` (15 tests, incl. `test_compact_registry_index_supersede_marks_predecessor_superseded_with_effective_valid_to`, `test_compact_registry_index_derives_supersession_even_without_a_marker_line`, `test_compact_registry_index_three_version_chain`, `test_compact_registry_index_supersede_then_tombstone`, `test_compact_registry_index_tombstone_wins_over_an_older_current_row`) | **PASS** |
| **G3** — the flag auto-clear rule (docs/canonical_state_base_design.md, "Open Question 6"(c): a healthy observation should retract an untombstoned flag for the same session) was never wired; `CLEARED_BY`/`REPLACED_BY` edges were named in the design but written nowhere | `scripts/kb_worker.py` | `_cell_id_and_status_from_observation_text` (L128, recovers `(cell_id, status)` from an `observation` record's `text` — the only field carrying that correlation), `_clear_flag_record` (L161, mints a new immutable version of the flag, `causes` set, since the original artifact can never be edited in place), `_maybe_autoclear_flag` (L188, the rule itself — gated on `status == "healthy"`, a known untombstoned flag, and `FINOPS_KB_WRITE=1`; publishes exactly one `delete` event with `reason="auto-cleared: subsequent observation was healthy"`; never imports `OpenCodeClient`, never constructs an `actuation` event), the in-process `flag_by_session_id` index inside the `kb-registry-v1` handler (L267) | `tests/test_kb_worker.py` (subset: `test_flag_autoclear_healthy_observation_emits_exactly_one_delete_for_the_flag`, `test_flag_autoclear_non_healthy_observation_does_not_clear`, `test_flag_autoclear_no_actuation_event_is_ever_produced`, `test_flag_autoclear_noop_when_no_known_flag_for_session`, `test_flag_autoclear_requires_finops_kb_write`, `test_flag_autoclear_is_idempotent_across_repeated_healthy_observations`, `test_flag_autoclear_does_not_reclear_a_flag_already_tombstoned`); the `CLEARED_BY`/`REPLACED_BY` edge-writing itself is G1's `kb-neo4j-v1` handler (reused unmodified — G3 only had to emit the `delete`+`causes` event that triggers it) | **PASS** |

Line numbers above are current as of commit `e66790776` and will drift on future edits —
they are cited for orientation while reading this doc alongside the diff, not as a
permanent index.

## Full regression gate

```
$ pytest tests/ -m "not external" -q
........................................................................ [  7%]
........................................................................ [ 14%]
........................................................................ [ 21%]
........................................................................ [ 28%]
........................................................................ [ 35%]
........................................................................ [ 42%]
........................................................................ [ 49%]
........................................................................ [ 56%]
........................................................................ [ 63%]
........................................................................ [ 70%]
........................................................................ [ 77%]
........................................................................ [ 84%]
........................................................................ [ 91%]
........................................................................ [ 98%]
................                                                         [100%]
1024 passed, 101 deselected, 19 warnings in 15.77s
```

**Verdict: PASS.** 1024 passed, 0 failed. The 101 deselected tests are the suite's
existing `external` marker (infra-gated: neo4j/ollama/chroma/sonar/live Redis — see
`tests/conftest.py`'s availability-check fixtures), unaffected by this spec's scope.

The three gap-tracing test files alone (`tests/test_knowledge_stream.py`,
`tests/test_kb_worker.py`, `tests/test_generate_manifest.py` — 65 tests) also pass in
isolation:

```
$ pytest tests/test_knowledge_stream.py tests/test_kb_worker.py tests/test_generate_manifest.py -q
.................................................................        [100%]
65 passed in 0.28s
```

## Backward-compatibility invariant — the 1,913-artifact corpus

Design §11's checklist requires that every pre-existing `experiments/results/kb/*.json`
artifact still parses via `KnowledgeRecord.from_dict` after this round's field/behavior
changes — none of G1/G2/G3 touch the `KnowledgeRecord`/`KnowledgeEvent` dataclasses
themselves (both were already frozen by the round-2 schema work this spec builds on), so
this is a regression check, not new ground:

```
$ python3 -c "
import json, glob
from instrument.knowledge import KnowledgeRecord

paths = sorted(glob.glob('experiments/results/kb/*.json'))
print('total artifacts:', len(paths))
failures = []
for p in paths:
    try:
        KnowledgeRecord.from_dict(json.loads(open(p).read()))
    except Exception as e:
        failures.append((p, repr(e)))
print('failures:', len(failures))
"
total artifacts: 1913
failures: 0
```

**Verdict: PASS.** 1,913 artifacts found (matches the corpus size this spec's `context`
documents), 0 `from_dict` failures.

## Summary

| Check | Result |
|---|---|
| G1 — operation threaded through consumers, lifecycle_state/edges derived from it | PASS |
| G2 — manifest compaction derives lifecycle_state/valid_to from the supersede/delete chain | PASS |
| G3 — flag auto-clear rule wired, CLEARED_BY/REPLACED_BY edges written | PASS |
| Full regression (`pytest tests/ -m "not external" -q`) | PASS — 1024 passed, 0 failed |
| 1,913-artifact backward-compat invariant | PASS — 0 failures |

All three consumer/projection gaps this spec named are closed, the full non-external test
suite is green, and the pre-existing KB artifact corpus remains fully backward-compatible.
No further work is outstanding for `canonical_state_finalize`.
