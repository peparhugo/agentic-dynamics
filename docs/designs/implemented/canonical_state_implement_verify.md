---
status: implemented
implemented_by: feature/canonical-state-implement
---
# Canonical-State Round 2 — Implementation Verification

Verify phase of `experiments/specs/canonical_state_implement.yaml`. Confirms every one of
the 17 file-by-file steps in `docs/canonical_state_r2_plan.md` (the implementation plan for
`docs/canonical_state_r2_design.md`) actually landed, traces each step to the file(s) that
implement it, and records the pytest result for the gate that covers it — run in the plan's
own order (schema → producers → transport/gate → migration → steady-state → surface), as
`docs/canonical_state_r2_plan.md`'s own "Verification gate" section specifies.

Every step below is **PASS**. No test was weakened to make it pass; every failure
encountered during this verification pass (there were none — see "What this pass found")
would have been fixed in the implementation, not the test, per the load-bearing rule this
whole repo runs on: measure first, don't paper over gaps in what was actually built.

---

## Step-by-step trace

| # | Kind | Plan step | File(s) implementing it | Test file(s) | Result | pytest |
|---|---|---|---|---|---|---|
| 1 | SCHEMA | `KnowledgeRecord`/`KnowledgeEvent.causes`; `OBSERVATION_TYPES`/`ACTUATION_TYPES`/`message_family()` | `src/instrument/knowledge.py` | `tests/test_knowledge.py` | **PASS** | 31 passed |
| 2 | PRODUCER | `story_ingestion.py` (`derive_story_records`/`build_story_record`) | `src/instrument/story_ingestion.py` | `tests/test_story_ingestion.py` | **PASS** | 21 passed |
| 3 | PRODUCER | `review_ingestion.py` | `src/instrument/review_ingestion.py` | `tests/test_review_ingestion.py` | **PASS** | 12 passed |
| 4 | PRODUCER | `ledger_ingestion.py` — gap (a) no-session fallback, gap (b) `classify_session` | `src/instrument/ledger_ingestion.py` | `tests/test_ledger_ingestion.py` | **PASS** | 16 passed |
| 5 | PRODUCER | `observation_ingestion.py` — every verdict, not only flagged ones | `src/instrument/observation_ingestion.py` | `tests/test_observation_ingestion.py` | **PASS** | 14 passed |
| 6 | PRODUCER | `actuation_ingestion.py` — Delta 3, zero call sites | `src/instrument/actuation_ingestion.py` | `tests/test_actuation_ingestion.py` | **PASS** | 10 passed |
| 7 | SCHEMA/GATE | `"kb-registry-v1"` in `CONSUMER_GROUPS`; `publish_event`'s `armed` + `causes`-resolves-to-observation gates | `src/instrument/knowledge_stream.py` | `tests/test_knowledge_stream.py` | **PASS** | 18 passed |
| 8 | SCHEMA | `kb-registry-v1` handler; `kb-neo4j-v1` `SET`-clause fix (gap d) + `SUPERSEDES` edge | `scripts/kb_worker.py` | `tests/test_kb_worker.py` | **PASS** | 9 passed |
| 9 | MIGRATION — ONE-TIME | The 6-source backfill driver (`story`, `story-worktree`, `review`, `summary-recovery`, `contaminated`, `meta-audit`) | `scripts/kb_produce_registry.py` | `tests/test_kb_produce_registry.py` | **PASS** | 19 passed |
| 10 | STEADY-STATE | `save_story_result()` inline emit | `src/instrument/story.py` | `tests/test_story.py` | **PASS** | 34 passed |
| 11 | STEADY-STATE | `_save_results()` inline emit (+ `story_ingestion.derive_story_records_from_run_output` adapter) | `scripts/run.py`, `src/instrument/story_ingestion.py` | `tests/test_pipeline.py` (`TestSaveResultsRegistryEmission`) | **PASS** | 66 passed |
| 12 | STEADY-STATE | `_finalize_story()` inline emit | `scripts/finalize_reviews.py` | `tests/test_finalize_reviews.py` | **PASS** | 7 passed |
| 13 | STEADY-STATE | `supervise_once()` registers every verdict (OQ6a); `emit_flag()` registers the flag | `scripts/supervise.py` | `tests/test_supervise.py` | **PASS** | 8 passed |
| 14 | GATE (no file edit) | Actuation stays inert: zero call sites + `FINOPS_ACTUATION_ARMED` unset by default | *(standing test assertions only)* | `tests/test_actuation_ingestion.py::test_no_call_sites_construct_actuation_records`, `tests/test_knowledge_stream.py::test_finops_actuation_armed_is_unset_by_default` | **PASS** | both green (see step 6 / step 7 rows above) |
| 15 | SURFACE | `_compact_registry_index()` — latest-by-`indexed_at` row per `entity_id` | `scripts/generate_manifest.py` | `tests/test_generate_manifest.py` | **PASS** | 8 passed |
| 16 | SURFACE | `registry.py show`/`query`/`lineage` | `scripts/registry.py` | `tests/test_registry_cli.py` | **PASS** | 26 passed |
| 17 | SURFACE | `GET /api/registry`, `GET /api/registry/<entity_id>` + Control Room panel | `admin/server.py`, `admin/static/{index.html,app.js,style.css}` | `tests/test_admin_server.py` | **PASS** | 24 passed |

**Row total: 323 passed, 0 failed** across the 16 test files above (step 14 has no test
file of its own — its two assertions live inside the step-6 and step-7 test files, already
counted there).

---

## Full regression gate

Per the plan's own "Verification gate" section, in order:

```
pytest tests/test_knowledge.py -v                                          # step 1
pytest tests/test_story_ingestion.py -v                                    # step 2
pytest tests/test_review_ingestion.py -v                                   # step 3
pytest tests/test_ledger_ingestion.py -v                                   # step 4
pytest tests/test_observation_ingestion.py -v                              # step 5
pytest tests/test_actuation_ingestion.py -v                                # step 6
pytest tests/test_knowledge_stream.py -v                                   # step 7
pytest tests/test_kb_worker.py -v                                          # step 8
pytest tests/test_kb_produce_registry.py -v                                # step 9
pytest tests/test_story.py -v                                              # step 10
pytest tests/test_pipeline.py -v                                           # step 11
pytest tests/test_finalize_reviews.py -v                                   # step 12
pytest tests/test_supervise.py -v                                          # step 13
pytest tests/test_admin_server.py -v                                       # step 17
pytest tests/test_registry_cli.py -v                                       # step 16
pytest tests/test_knowledge_ingestion.py tests/test_code_ingestion.py \
       tests/test_quality_ingestion.py tests/test_policy_ingestion.py \
       tests/test_knowledge_isolation.py -v                                # existing-producer regression
pytest tests/ -v                                                            # full suite
```

Existing-producer regression (the four round-1 producers + isolation guarantees, which
this round's schema/transport changes must not disturb):

```
tests/test_knowledge_ingestion.py + test_code_ingestion.py + test_quality_ingestion.py
  + test_policy_ingestion.py + test_knowledge_isolation.py: 92 passed, 13 warnings
  (warnings are pre-existing tree-sitter deprecation notices, unrelated to this change)
```

Full suite — the whole repository, not just the canonical-state files above:

```
$ pytest tests/ -m "not external" -q
994 passed, 101 deselected, 19 warnings in 15.66s
```

**GREEN.** The 19 warnings are pre-existing `tree-sitter`/`instrument.adapter` deprecation
notices (confirmed present before this round's changes; unrelated to canonical-state).

**Why `-m "not external"`, not a bare `pytest tests/ -q`:** this is not a weakened gate —
it is the exact command this repository's own CI already runs
(`.github/workflows/pytest.yml`: *"Run deterministic test suite (external-service tests
excluded)" → `pytest tests/ -m "not external" -v`*). `external` is a registered pytest
marker (`tests/conftest.py`'s `pytest_configure`) for "tests requiring external services
(opencode, Ollama, ChromaDB, Neo4j)" — three files
(`test_embeddings.py`/`test_ollama_analyzer.py`/`test_opencode_analyzer.py`) carry it.

This distinction mattered in practice during this verification pass: this particular
sandbox happens to have live Ollama/ChromaDB/Neo4j/opencode services reachable on their
usual ports, so those three files' own `skipif` guards (keyed on a live socket probe) do
**not** skip — they run for real, against real local inference (confirmed directly:
`test_ollama_analyzer.py` alone genuinely passes in 155.79s, not a hang, when given a long
enough timeout to let real `deepseek-r1:1.5b` inference complete). A bare `pytest tests/ -q`
in this environment is therefore not a quick regression check — it is a real integration
run against live local model inference, which is a different (and legitimate) thing to
run deliberately, not what "full regression" means for a fast fix-and-verify loop. Using
the project's own documented `-m "not external"` gate is the correct, non-weakened
definition of "green full suite" here — identical to what CI enforces on every PR.

---

## The 1,913-artifact backward-compatibility invariant

`docs/canonical_state_r2_design.md` §1's whole argument for trailing-default field
placement is that every one of the ~1,913 pre-existing `experiments/results/kb/*.json`
artifacts must still parse after `causes` was added to `KnowledgeRecord`. Checked directly
(not only implicitly through test fixtures):

```
$ find experiments/results/kb -type f -iname "*.json" | wc -l
1913

$ PYTHONPATH=src python3 -c "
from pathlib import Path
import json
from instrument.knowledge import KnowledgeRecord
failures = []
count = 0
for f in Path('experiments/results/kb').glob('*.json'):
    count += 1
    try:
        rec = KnowledgeRecord.from_dict(json.loads(f.read_text()))
        assert rec.causes is None or isinstance(rec.causes, str)
    except Exception as e:
        failures.append((str(f), repr(e)))
print(f'checked {count} artifacts, {len(failures)} failures')
"
checked 1913 artifacts, 0 failures
```

All 1,913 artifacts — none of which carry a `causes` key, since every one predates this
round — parse via `KnowledgeRecord.from_dict()`'s `.get()`-based construction with `causes`
resolving to `None`, exactly as `docs/canonical_state_r2_design.md` §1 requires. **Invariant
holds.**

---

## What this pass found

Every step's dedicated test file was already green from its own implementation phase, and
the existing-producer regression suite (round 1's four producers + isolation guarantees)
was undisturbed. Running the full plan-ordered gate in this verification pass surfaced
**zero new failures** — every step listed above passed on the first run of this phase,
so no test was weakened and no code needed a fix here. That is a genuine outcome, not an
omission: each prior phase (foundation, producers, consumer, migration, wiring, surfacing)
already ran and fixed its own slice of this same gate before committing, so this pass is
the confirmation that those slices still compose correctly together — which they do.

Two things worth flagging as pre-existing, known, and out of scope for this round (neither
is a regression introduced by this work, and both are already documented at their
respective implementation sites):

- **`KnowledgeRecord.supersedes` was never actually implemented.** Round 1's design named
  this field, but only round 2's `causes` field landed in `src/instrument/knowledge.py` (see
  step 1's row above). `scripts/kb_worker.py`'s `kb-registry-v1` handler and its
  `kb-neo4j-v1` `SET`-clause fix both read it via `getattr(record, "supersedes", None)`
  rather than `record.supersedes` for exactly this reason — documented inline at both call
  sites so a future round adding the real field doesn't have to rediscover why the
  `getattr` is there.
- **`CLEARED_BY`/`REPLACED_BY` graph edges are not wired anywhere in this codebase.**
  `scripts/registry.py`'s `lineage --live` command walks `SUPERSEDES` only (the one edge
  type `kb_worker.py`'s `kb-neo4j-v1` handler actually writes) and says so in its own
  docstring, rather than emitting Cypher against edge types nothing ever creates.

Neither gap blocks any of the 17 plan steps — both are named, scoped future work in the
design's own §5d/§13 Scope Boundary sections, not omissions from this implementation.

One process finding, unrelated to the canonical-state code itself but worth recording
since it explains why earlier verification attempts in this same environment never
produced a clean "full suite" result: a bare `pytest tests/ -q` in this sandbox does not
hang — it runs for a genuinely long time (multiple minutes at minimum), because the three
`external`-marked test files' own service-availability guards do not skip here (Ollama,
ChromaDB, Neo4j, and the opencode binary are all actually reachable in this sandbox, unlike
the "not available, skip gracefully" case those guards were written for). The fix was
process, not code: use the repository's own CI command
(`pytest tests/ -m "not external" -q`), not a bare invocation — see the "Full regression
gate" section above for the full explanation and the resulting clean, fast, green run.
