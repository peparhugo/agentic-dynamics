# Implementation trace — record-field fidelity (BUG-1 / BUG-4+R5 / BUG-7)

Closes the three record-fidelity findings from `docs/review/bugs.md` and the R5
restructuring recommendation from `docs/review/restructure.md`. Each row traces the bug
to the exact fix, the test that pins it, and the result. Read at commit `HEAD` of
`feature/kb-record-fidelity`.

---

## Trace table

| # | Bug (severity) | Root cause | Fix | Verifying test(s) | Result |
|---|---|---|---|---|---|
| BUG-1 | `observed_at` dropped on the stream round-trip (HIGH) | `record_to_artifact` blanks `observed_at` (volatile), and `extract_record` reattached `event.occurred_at` (producer wall-clock) in its place — the cell's own run timestamp was irrecoverably replaced | Add a trailing-default `observed_at` field to `KnowledgeEvent` (`knowledge.py:213`); `record_to_event` now carries `record.observed_at` (`knowledge_ingestion.py:400`); `extract_record` reattaches `event.observed_at or event.occurred_at` (`knowledge_ingestion.py:429`); `default_extract` mirrors the same fallback (`knowledge_stream.py:351`) | `tests/test_knowledge_ingestion.py::test_observed_at_round_trips_the_entry_timestamp_not_the_producer_clock`; `tests/test_knowledge.py::test_event_observed_at_round_trips_through_to_dict`, `test_event_from_dict_accepts_fixture_with_no_observed_at_key` | **PASS** |
| BUG-4 / R5 | flag auto-clear re-parses producer prose (MEDIUM) | The kb-registry-v1 consumer recovered `(cell_id, status)` by string-splitting the rendered `text`; a render change silently no-op'd clearing | Add trailing-default `subject_id`/`subject_status` fields to `KnowledgeRecord` (`knowledge.py:306-307`); populate structurally in `build_observation_record` (`observation_ingestion.py:140-141`) and `build_flag_record` (`observation_ingestion.py:225-226`); delete `_cell_id_and_status_from_observation_text` and read the structured fields in `_maybe_autoclear_flag` (`kb_worker.py:190-191`); key the in-process flag index on `subject_id` (`kb_worker.py:327`) | `tests/test_kb_worker.py::test_autoclear_reads_structured_subject_not_text`; `tests/test_observation_ingestion.py::test_observation_record_carries_structured_subject`, `test_flag_record_carries_structured_subject`; `tests/test_knowledge.py::test_record_subject_fields_round_trip_through_to_dict`, `test_record_from_dict_accepts_fixture_with_no_subject_keys` | **PASS** |
| BUG-7 | `perturbation_strength` fabricated as `0.0` baseline (LOW) | `_summary_entry_to_story_result` defaulted `entry.get("perturbation_strength", 0.0)`, stamping a genuinely-absent field as a baseline cell | Drop the `0.0` default → `entry.get("perturbation_strength")` (`kb_produce_registry.py:243`), so absent stays `None` and flows through as unmeasured | `tests/test_kb_produce_registry.py::test_summary_entry_absent_perturbation_strength_stays_none`, `test_summary_entry_present_perturbation_strength_is_preserved` | **PASS** |

---

## Fix notes

### BUG-1 — `observed_at` round-trip (option (b) from `bugs.md`)

Chose bugs.md's option (b) — carry `observed_at` on the pointer event — over option (a)
(fold it into `content_hash`), because option (a) would break producer idempotence:
`_observed_at` falls back to the producer clock when an entry has no stamped timestamp
(the current `_results_summary.json` case), so folding it into the hash would make
`content_hash`/`knowledge_id` re-derivation-dependent. The pointer carries the real
measurement time; the artifact keeps blanking it so `content_hash` stays a pure function
of stable content.

`occurred_at` is unchanged in meaning — it stays the producer wall-clock used to measure
end-to-end lag. `valid_from` continues to reconstruct from `occurred_at` (the producer
derivation pass); only `observed_at` now prefers `event.observed_at`.

### BUG-4 / R5 — structured `subject_id` / `subject_status`

Followed R5's "promote the fact, don't standardize the parse" guidance verbatim (and
restructure.md §5.1's explicit *do-not*: never promote the text-parsing into a shared
convention). The two fields use the same trailing-default backward-compat pattern as
`causes`/`supersedes`, so every pre-existing serialized artifact still parses via
`from_dict()`'s `.get()`-based construction.

For an observation record the subject is the assessed cell (`subject_id=cell_id`); for a
flag the subject is the flagged session (`subject_id=session_id`). Since `cell_id` and
`session_id` are the same string in this codebase, the auto-clear correlation reads both
sides from the same structured field. The in-process flag index keys on
`record.subject_id or record.logical_locator` so a pre-fidelity flag (empty `subject_id`)
still resolves via its `logical_locator` session id.

### BUG-7 — `perturbation_strength` `None`-not-`0.0`

One-line fix, matching every other producer in the package (`story_ingestion` already
passes `story_result.get("perturbation_strength")` with no default). An absent field now
flows through as `None` (unmeasured) instead of a fabricated baseline.

---

## Verification

### Targeted gate

```
pytest tests/test_knowledge.py tests/test_knowledge_ingestion.py \
       tests/test_observation_ingestion.py tests/test_kb_worker.py \
       tests/test_kb_produce_registry.py -q
# 145 passed
```

### Full gate

```
pytest tests/ -m "not external" -q
# 1035 passed, 101 deselected, 19 warnings
```

The 101 deselected are `external`-marked integration tests (live Redis/Neo4j) — no
regressions. The one pre-existing assertion touched was
`test_structured_signals_round_trip_to_dict_from_dict_and_artifact`, tightened to assert
the stronger post-fix guarantee (`extracted.observed_at == record.observed_at ==
event.observed_at`) instead of the old `== event.occurred_at`.

### 1,913-artifact backward-compat invariant

Every durable artifact under `experiments/results/kb/` was re-loaded and parsed through
`KnowledgeRecord.from_dict`:

```
total artifacts: 1913
parse failures: 0
artifacts lacking subject_id key: 1913   # all legacy — none carry the new fields
BACKWARD-COMPAT OK
```

All 1,913 legacy artifacts (none of which carry `subject_id`) still parse, because the new
`subject_id`/`subject_status` fields use `.get(..., "")` trailing defaults. The analogous
event-level guarantee is asserted by
`tests/test_knowledge.py::test_event_from_dict_accepts_fixture_with_no_observed_at_key`
(a legacy stream message without `observed_at` decodes to `""` and falls back to
`occurred_at` at extraction).
