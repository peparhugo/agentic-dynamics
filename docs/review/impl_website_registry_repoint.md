# Website registry repoint — implementation trace & verification

**Status:** implementation verified. Every hard rule in the repoint is traced below to
its file + line, with PASS/FAIL and the pytest result. This document is the proof that
the site now counts the canonical-state registry — not the retired 144-entry summary.

**Run this phase (all commands re-run from scratch):**
`python scripts/build_data.py` (writes `firebase/public/data.js`),
`python scripts/generate_manifest.py` (regenerates `experiments/data_manifest.json`),
`python scripts/registry.py query` (read-only verification),
`pytest tests/ -m "not external" -q`.

---

## 1. The one number that matters: data.js == registry

`scripts/registry.py query` (the read-only index read — `scripts/registry.py:74`
`load_registry`, `:176` `cmd_query`, `:181` lifecycle filter) reports, against the
freshly-regenerated manifest:

| source_type | current | tombstoned | total |
|---|---|---|---|
| `story` | **225** | **77** | 302 |
| `finding` | **64** | 0 | 64 |
| `review` | 242 | 0 | 242 |
| `meta_session` | 27 | 0 | 27 |
| **registry total** | **558** | **77** | 635 |

`firebase/public/data.js` (parsed from the `window.DYNAMICS_DATA = {...}` literal) carries,
in its `summary` block:

| data.js key | value | matches registry? |
|---|---|---|
| `summary.canonical_stories` | **225** | ✅ `story` current |
| `summary.canonical_findings` | **64** | ✅ `finding` current |
| `summary.tombstoned_excluded` | **77** | ✅ `story` tombstoned |

**PASS** — the live site counts are the registry counts, tombstoned excluded.

### The "366" reconciliation (precision note)

The task brief's "366 current experiment records" is the **pre-exclusion** total, not the
live count. 366 = `story` 302 (raw, *including* the 77 tombstones) + `finding` 64. The
phrase "current … tombstones excluded" is internally inconsistent: once the 77 tombstones
are excluded, the live experiment-cell count is **289** (225 story + 64 finding). Both
numbers are consistent with the registry:

```
story(302) + finding(64) = 366 registered experiment records      ← the "366"
  − tombstoned story(77)                                          ← "tombstones excluded"
  = 225 current story + 64 current finding = 289 live cells       ← what data.js shows
```

`data.js` renders 225 / 64 / 77; it never renders 366 or 302 or any summary-derived
number in a live section.

---

## 2. Hard-rule trace (rule → file → PASS/FAIL)

### R1. Retire `_results_summary.json` as a build input

- **Code:** `scripts/build_data.py` — the `SUMMARY_PATH` constant and `load_summary()`
  function are gone; `MANIFEST_PATH = ROOT / "experiments" / "data_manifest.json"`
  (`build_data.py:31`) is the only index the build reads. The `_meta` provenance key is
  now `source_registry` (manifest), not `source_summary`.
- **Verify:** `grep -n "SUMMARY_PATH\|_results_summary" scripts/build_data.py` → no matches.
  The `generate_manifest.py` `files{}` block still *hashes* the summary file (it is a
  separate audit-trail script, and the file still exists on disk), but it is not a
  build_data input.
- **PASS.**

### R2. Load the manifest index; keep `current` + `source_type ∈ {story, finding}`

- **Code:** `CANONICAL_SOURCE_TYPES = frozenset({"story", "finding"})`
  (`build_data.py:49`); `load_canonical_corpus()` (`build_data.py:292`) calls
  `registry.load_registry(path)` (`build_data.py:306`) and filters
  `lifecycle_state == "current" and source_type in CANONICAL_SOURCE_TYPES`
  (`build_data.py:309–321`). `review`/`meta_session` are deliberately not build_data
  inputs (same as the pre-repoint boundary).
- **Test:** `test_finding_row_joins_to_its_run`, `test_tombstoned_*_records_are_excluded`.
- **PASS.**

### R3. Join measurement payloads from the `source_uri` names

- **Code:** findings — `_resolve_finding_entry()` (`build_data.py:220`) resolves the
  `file://` URI via `_resolve_file_uri()` (`build_data.py:116`) and joins the run by
  `basename(run["workdir"]) == logical_locator` (`build_data.py:238`), then
  `_finding_entry_from_run()` (`build_data.py:165`) remaps `cost_usd→cost`,
  `lines_of_code→code_lines`, `escape_score→escape`, etc. Stories —
  `_resolve_story_payload()` (`build_data.py:141`) resolves `story:<id>` via
  `_find_story_file()` (`build_data.py:128`, glob `stories/*_<id>.json`).
- **Test:** `test_finding_row_joins_to_its_run` (asserts the workdir-basename join + field
  remap). **PASS.**

### R4. Tombstoned rows excluded

- **Code:** the `current`/`tombstoned` split in `load_canonical_corpus`
  (`build_data.py:309–321`) — only `current` rows ever reach `_resolve_*`; tombstoned rows
  contribute only to `tombstoned_count`.
- **Test:** `test_tombstoned_story_records_are_excluded`,
  `test_tombstoned_finding_records_are_excluded` (both assert the payload is never built
  from a tombstoned row and the count is reported separately). **PASS.**

### R5. No-op story condition relabeled `clean`

- **Code:** `_effective_story_condition()` (`build_data.py:100`) mirrors
  `instrument.story_ingestion._effective_condition`: `perturbation_condition ∈
  {early_degrade, bad_seed}` **and** `test_executed_success` is not a bool → `clean`
  (`NOOP_CONDITIONS`, `build_data.py:55`). The relabeled value is written to the payload's
  `_canonical_condition` in `_resolve_story_payload` (`build_data.py:151`).
- **Test:** `test_noop_story_condition_is_relabeled_clean` (no-op → `clean`),
  `test_instrumented_story_keeps_its_condition` (instrumented → label preserved),
  `test_genuinely_clean_story_is_untouched`. **PASS.**

### R6. Missing manifest degrades with a warning

- **Code:** `load_canonical_corpus` prints a `WARNING` to stderr and returns an empty
  `CanonicalCorpus` when `load_registry` returns `[]` (`build_data.py:307–315`); the empty
  case is never a hard failure (mirrors `registry.load_registry`'s file-fallback posture).
- **Test:** `test_missing_manifest_degrades_with_a_warning`. **PASS.**

### R7. Never fabricate a pass rate; null renders as em-dash

- **Code:** `compute_model_data()` (`build_data.py:396`) derives `pass_rate` **only** from
  measured `test_results` — `pass_rate_val = None` (`build_data.py:432`) when
  `total_tests == 0`, never the old `correctness`-average `[H]` fallback. Historical
  sub-fields are emitted `None` (renders `null`/em-dash) with an `_historical_fields`
  list (`build_data.py:496–519`). The story path's `_honest_pass_rate`
  (`build_data.py:1054`) already returns `"unknown"` (not a fabricated %) for untested
  cells.
- **Test:** `test_pass_rate_is_none_when_no_measured_tests`,
  `test_pass_rate_derived_from_measured_tests`. **PASS.**

### R8. Sections with no canonical replacement marked "historical" with a `[P]` note

- **Code:** `_compute_sonar()` (`build_data.py:362`) returns
  `{"models": {}, "_historical": True, "_note": "[P] SonarQube per-cell aggregates retired
  … no canonical replacement in the registry."}` instead of zero-filled per-model
  aggregates. Verified live: `data.js`'s `sonar` key is exactly this marker.
- **Test:** `test_sonar_section_is_marked_historical`. **PASS.**

### R9. Site counts == registry (the load-bearing claim)

- **Code:** the `summary` block in `build()` writes `canonical_stories` /
  `canonical_findings` / `tombstoned_excluded` straight from `corpus` counts
  (`build_data.py:1309–1311`).
- **Verify:** §1 table — data.js = registry (225 / 64 / 77). **PASS.**

### R10. No stale 144-entry summary numbers leak into any live section

- **Verify:** `grep -c "144" firebase/public/data.js` → 4 hits, but none is the retired
  144-entry count: three are substring coincidences (`tokens_total 61442`, `loc 1446`,
  `avg_duration_s 1449`), and the only bare `144` is `/grit_matrix[26]/loc` — a
  lines-of-code value from `lab_grit_matrix.json`, unrelated to the summary. No
  `source_summary`/`_results_summary` key appears in data.js. `perturbation_models` are
  the 64 finding re-runs (7 model groups summing to 64), not 144.
- **PASS.**

---

## 3. pytest result

```
$ pytest tests/ -m "not external" -q
1079 passed, 121 deselected, 19 warnings in 17.50s
```

Targeted:

```
$ pytest tests/test_build_data.py -q
11 passed in 0.15s
```

No test was weakened: the 11 new `test_build_data.py` cases are additive; the 1079-pass
run confirms no regression in the existing 66-file suite. The only warnings are
pre-existing (a deprecation in `test_adapter.py` and `tree_sitter` FutureWarnings), not
introduced by this repoint.

---

## 4. Build log (verbatim)

```
$ python scripts/build_data.py
Building data.js...
  Loaded inventory: 1078 experiment sessions
  Loaded canonical corpus: 64 finding + 225 story current records (77 tombstoned excluded); 64 perturbation entries
  Game reports on disk: 344
  Computed: 7 perturbation models
  Story models: 7 (from stories.parquet)
Wrote firebase/public/data.js (178518 bytes)

$ python scripts/generate_manifest.py
  … registry: 635 entities (compacted from registry_index.jsonl)
```

The 64 perturbation entries are the 64 `finding` re-runs; the 225 story cells and 77
tombstones match `registry.py query` exactly.
