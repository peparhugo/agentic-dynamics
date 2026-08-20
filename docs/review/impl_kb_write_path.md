---
status: implemented
implemented_by: feature/kb-write-path
---
# Implementation trace — R4 / R6 / R8 (KB write-path dedup)

This is the *implementation trace* companion to `docs/review/restructure.md` §3
(recommendations R4, R6, R8). It maps each recommendation to the file(s) that now carry
the change, with a PASS/FAIL verdict and the pytest result that backs it.

Goal: one `register_records` helper, one `paths` module, one `StoryResult` adapter — the
"one write path" for the runtime-RAG knowledge base.

| # | Recommendation | Verdict | Primary file(s) |
|---|---|---|---|
| R4 | One shared write-path helper `register_records(records, *, fail_loud)` | **PASS** | `src/instrument/knowledge_stream.py:197`, 4 call sites |
| R6 | Single `paths` module (`REGISTRY_INDEX_PATH`, `KB_ARTIFACT_DIR`) | **PASS** | `src/instrument/paths.py`, 6 importers |
| R8 | One `adapt_to_story_result(source, *, kind)` adapter | **PASS** | `src/instrument/story_ingestion.py:232`, 2 call sites |

**Gate result (full suite):** `pytest tests/ -m "not external" -q` →
`1026 passed, 101 deselected` — green, no failures, no regressions.

---

## R4 — One shared write-path helper (finish DeepSeek's D1)

**Recommendation** (`restructure.md` R4): replace the four inline emit blocks with one
`register_records(records, *, fail_loud: bool)` that does
`derive → record_to_event → publish_event(authorized=True)`, with a single "raise vs
swallow a downed stream" knob. Each call site keeps only its *derivation* (which producer
function, which input).

### The helper — `src/instrument/knowledge_stream.py:197`

`register_records(records, *, fail_loud)` is the single factored write path:

- Connects once via the module-global `connect()` (so test doubles monkeypatch it exactly
  as they did before), then per record calls
  `publish_event(r, record_to_event(record), authorized=True, source_type=record.source_type)`.
- `record_to_event` is imported **lazily inside the function** (`from
  .knowledge_ingestion import record_to_event`) — the same function-local-import
  circular-import dodge the old call sites used, so `knowledge_stream` gains no module-level
  dependency on `knowledge_ingestion` (and therefore no import cycle).
- `fail_loud=True` re-raises a connection or per-record failure; `fail_loud=False` swallows
  it (returning the surviving entry ids). This is the one knob the four call sites used to
  encode *separately* as "loud" vs "best-effort".

### The four call sites (before → after)

| Call site | `fail_loud` | Posture |
|---|---|---|
| `src/instrument/story.py:945` `save_story_result` → `:976` | `True` | one-shot persistence; a downed stream must be visible |
| `scripts/run.py:372` `_save_results` → `:393` | `True` | one-shot; same loud-failure guarantee |
| `scripts/finalize_reviews.py:28` `_finalize_story` → `:81` | `True` | one-shot; same loud-failure guarantee |
| `scripts/supervise.py:221` `emit_flag` → `:269` | `False` | live loop; never cost the durable flags.jsonl write |
| `scripts/supervise.py:333` `supervise_once` → `:387` | `False` | live loop; never take down the assessment pass |

Each call site retains its derivation only (e.g. `derive_story_records(...)`,
`derive_story_records_from_run_output(...)`, `derive_review_records(...)`,
`derive_flag_record(...)`, `derive_observation_record(...)`) and passes the resulting
`KnowledgeRecord` list to `register_records`. The `FINOPS_KB_WRITE == "1"` gate at each
site is unchanged — `register_records` still publishes under `authorized=True`.

### Exports

- `src/instrument/__init__.py:337` imports `register_records` from `.knowledge_stream`;
  `:508` adds it to `__all__`.

### Verdict: **PASS**

The four inline copies (actually five emit blocks across four files) are gone; the emit
contract now lives in one function. Tests that monkeypatch `ks.connect` / `ks.publish_event`
still intercept correctly because `register_records` resolves both through the
`knowledge_stream` module globals.

---

## R6 — Stop hand-syncing `REGISTRY_INDEX_PATH` and `KB_ARTIFACT_DIR`

**Recommendation** (`restructure.md` R6): a single `paths.py` that the producers and
consumers import, removing the "duplicated, not imported, keep in sync by hand" comments and
the data-loss vector of a producer/consumer path drift.

### The module — `src/instrument/paths.py` (new, leaf, redis-free)

- `src/instrument/paths.py:20` — `PROJECT_ROOT` (resolved from `__file__`, repo root).
- `src/instrument/paths.py:26` — `KB_ARTIFACT_DIR_REL = "experiments/results/kb"` (the
  repo-root-relative form, kept separate because `knowledge_ingestion.artifact_uri` builds a
  `file://` URI from it).
- `src/instrument/paths.py:29` — `KB_ARTIFACT_DIR = PROJECT_ROOT / KB_ARTIFACT_DIR_REL`
  (absolute, for on-disk writers).
- `src/instrument/paths.py:34` — `REGISTRY_INDEX_PATH`.

It imports only `pathlib` — no redis/chromadb/neo4j — so it can be imported by the
dependency-light `generate_manifest.py` without pulling the heavy `instrument/__init__.py`.

### The importers (before → after)

| Consumer | Import | Notes |
|---|---|---|
| `src/instrument/knowledge_ingestion.py:48` → `:71` | `from .paths import KB_ARTIFACT_DIR_REL`; `ARTIFACT_DIR = KB_ARTIFACT_DIR_REL` | `ARTIFACT_DIR` stays a **relative string** (the `file://` URI contract) |
| `scripts/kb_worker.py:39` | `from instrument.paths import KB_ARTIFACT_DIR, REGISTRY_INDEX_PATH` | module-level names → still monkeypatchable by `tests/test_kb_worker.py` |
| `scripts/kb_produce.py:38` | `from instrument.paths import KB_ARTIFACT_DIR` | replaces the local `Path(...) / "kb"` literal |
| `scripts/kb_produce_registry.py:58` | `from instrument.paths import KB_ARTIFACT_DIR` | replaces `REPO_ROOT / "experiments/results/kb"` |
| `scripts/kb_produce_sources.py:45` | `from instrument.paths import KB_ARTIFACT_DIR` | a 6th copy the review's module/seam list missed — also folded in |
| `scripts/generate_manifest.py:23` | `from paths import REGISTRY_INDEX_PATH` (leaf) | value-only import: `sys.path` pointed at `src/instrument`, imports the top-level `paths` module — **not** `instrument.paths` — so `instrument`/`redis` never load |

### Verdict: **PASS**

Verified that `import generate_manifest` does **not** put `instrument` or `redis` in
`sys.modules` (it loads only the pure-pathlib `paths` leaf). All importers resolve to the
same absolute location; a path change is now a one-line edit.

---

## R8 — Collapse the two "reshape a non-StoryResult into a StoryResult" adapters

**Recommendation** (`restructure.md` R8): one `adapt_to_story_result(source, *, kind)`
helper; the two call sites pass `kind` and share the identity formula.

### The helper — `src/instrument/story_ingestion.py:232`

`adapt_to_story_result(source, *, kind)` owns "what is the canonical story_id for a
non-story artifact" with a `kind` dispatch:

- `kind="run"` — `scripts/run.py`'s `_save_results` output. `story_id = f"{name}_{model_slug}"`
  (the **exact** string `_save_results` uses for its output filename). Raises `ValueError`
  on a missing `experiment` key.
- `kind="summary"` — a recovered `_results_summary.json` entry. `story_id = worktree_name`
  (else `run_id`), empty when neither is present (batch skip, not raise).

### The two call sites (before → after)

| Call site | Passes | Notes |
|---|---|---|
| `src/instrument/story_ingestion.py:308` `derive_story_records_from_run_output` | `kind="run"` | now a thin wrapper: `adapt_to_story_result(out, kind="run")` → `derive_story_records(...)` |
| `scripts/kb_produce_registry.py:225` `_summary_entry_to_story_result` → `:238` | `kind="summary"` | now a thin wrapper delegating to `si.adapt_to_story_result(entry, kind="summary")` |

Both previously hand-rolled field-renaming + identity logic; both now share the one helper,
so the synthetic-story identity cannot drift out of sync with the call site that derives its
own filename from it.

### Exports

- `src/instrument/__init__.py:265` imports `adapt_to_story_result` from `.story_ingestion`;
  `:528` adds it to `__all__`.

### Verdict: **PASS**

`tests/test_story_ingestion.py` (run-output adapter: `logical_locator ==
"task_manager_api_deepseek_v4_flash"`, `source_uri == "story:task_manager_api_deepseek_v4_flash"`,
idempotence, changed-runs→new-id, missing-`experiment`→raise) and
`tests/test_kb_produce_registry.py` (summary recovery: `logical_locator == "long_lost"`) both
still pass unchanged — the two `kind` branches reproduce the exact prior behavior.

---

## Verification

Targeted (the seven files named in the implement phase):

```
pytest tests/test_knowledge_stream.py tests/test_story.py tests/test_pipeline.py \
  tests/test_finalize_reviews.py tests/test_supervise.py tests/test_kb_produce_registry.py \
  tests/test_generate_manifest.py -q
→ 171 passed
```

Full gate (excluding external-service tests):

```
pytest tests/ -m "not external" -q
→ 1026 passed, 101 deselected, 19 warnings
```

No failures, no weakened tests, no regressions. The `restructure.md` "five scripts" count is
six importers in practice — `scripts/kb_produce_sources.py` carried the same `KB_ARTIFACT_DIR`
literal and was folded into `paths.py` as well (a superset of the recommendation, same
dedup goal).
