---
status: implemented
implemented_by: feature/website-registry-repoint
---
# Phase 2 audit — summary→canonical mapping for the website registry repoint

**Status:** implementation input for phase 2. This document is the *mapping contract*:
it enumerates every `data.js` section `build_data.py` derives from
`_results_summary.json` entries, and names the canonical-state source each one must be
re-pointed at (or marks it "historical" when no canonical replacement exists). Every
count in here is measured against the current `experiments/data_manifest.json` registry
array — not inferred from prose.

**Authoritative grounding:** `docs/verification/data_integrity_findings.md` (the canonical record) +
the canonical-state registry produced by `scripts/generate_manifest.py` and read by
`scripts/registry.py` (`load_registry`). The registry row is the *index*; the payload is
the source artifact pointed at by `source_uri`.

---

## 1. Why the repoint exists

The current site (and the lab books) are fed by `_results_summary.json` — 144 entries
whose condition labels are not backed by real perturbations (`docs/verification/data_integrity_findings.md`).
The remediation retired those 144 entries and replaced them with the clean re-runs, now
registered as canonical-state `finding` records. The site must stop reading the summary and
start reading the registry, so the same number the Control Room's `/api/registry` shows is
the number the site shows.

**Two canonical record families feed the site post-repoint:**

| Registry `source_type` | What it represents | `source_uri` form | Payload |
|---|---|---|---|
| `finding` (64) | clean single-task perturbation cells — **the replacement for the retired 144 summary entries** | `file://experiments/results/task_manager_<model>.json` / `file://experiments/results/process_perturbation_resample_<model>.json` | JSON with top-level `experiment`, `model`, `runs[]` |
| `story` (302) | multi-session story cells | `story:<story_id>` | `experiments/results/stories/*.json` (a `StoryResult.to_dict()` shape) |
| `review` (242) | review-agent verdicts | `review:<story_id>` | (not a summary-entry consumer; listed for completeness) |
| `meta_session` (27) | session-level metadata | `meta_session:<…>` | (not a summary-entry consumer) |

The registry rows themselves are **pointer-only** (identity + lifecycle, no metric vector).
Phase 2 joins `source_uri` → payload file → the specific run/cell via `logical_locator`.

---

## 2. Registry counts (measured)

Measured directly from `experiments/data_manifest.json` (generated 2026-08-19), the
`registry` array — 635 rows total:

| `source_type` | current | tombstoned | total |
|---|---|---|---|
| `story` | **225** | **77** | 302 |
| `finding` | **64** | 0 | 64 |
| `review` | 242 | 0 | 242 |
| `meta_session` | 27 | 0 | 27 |
| **total** | **558** | **77** | 635 |

The 77 tombstones are all `story` records whose `reason` begins
`"contaminated: ran as CLEAN due to the P0-7 mutation fallback…"` — exactly the
quarantined corpus `docs/verification/data_integrity_findings.md` treatment rule 3 mandates.

### Exact counts the site must show post-repoint

- **Story — 225 current.** The raw story row count is 302, but 77 of those are tombstoned
  and MUST be excluded from every site surface. (The task brief's "story 302" is the
  pre-exclusion raw count; the number the site renders is 225.)
- **Finding — 64 current.** All 64 finding records are `current`; nothing is excluded.
- **Tombstoned — 77, excluded** from every metric, table, and chart. If the site wishes
  to *acknowledge* them (e.g. a "77 quarantined cells" footnote), that is a separate,
  explicitly-labeled historical counter — never folded into a live metric.

Derived site totals (post-repoint, canonical only): **289 current measurement cells
(225 story + 64 finding)**, with 77 tombstones quarantined. Reviews (242) and meta
sessions (27) remain independently surfaced if the site keeps those sections.

---

## 3. Every summary-derived `data.js` section, and its canonical replacement

`build_data.py` touches `_results_summary.json` through exactly six sites. Five consume
`summary["entries"]` (the 144 rows); one consumes a pre-aggregated summary block. The
`by_model` and `by_operator` summary blocks are **not** read by `build_data.py` (verified)
and are out of scope.

For each section: the canonical source, the join key, and the replacement verdict.

### 3.1 `perturbation_models` — `compute_model_data(inventory, summary, …)` (line 180, emitted line 1104)

- **What it is:** per-model aggregate metrics over the single-task perturbation cells
  (avg_cost, total_cost, pass_rate, strategy counts, avg_loc, avg_thinking_ratio,
  avg_escape, avg_narration_penalty, divergence metrics, composite/code-quality scores,
  energy, correctness-per-dollar, AST aggregates, cost/token breakdowns, narration_rate).
- **Canonical source:** `finding` payload (via registry). The 64 finding records are the
  clean single-task re-runs that replace the 144 summary entries
  (`docs/verification/data_integrity_findings.md` treatment rule 4).
- **Join key:** registry `source_uri` (→ the `task_manager_*` / `process_perturbation_resample_*`
  JSON file) **then** `logical_locator` == `basename(run.workdir)` to select the specific
  `runs[]` entry inside that file. (Example: finding row `logical_locator = "exp_jgikdggu"`,
  `source_uri = "file://experiments/results/task_manager_deepseek-v4-pro.json"` → the run
  whose `workdir == "/tmp/exp_jgikdggu"`.)
- **Verdict:** repoint to `finding` payload; **partial** — see §4 for sub-fields with no
  finding-payload equivalent (narration, AST, basin structure divergence, cost split, sonar).

### 3.2 `operator_comparison` — from `summary["by_operator_model"]` (line 995)

- **What it is:** per-operator × per-model matrix (n, avg_cost/cost_ci95, avg_escape/escape_ci95,
  avg_correctness/correctness_ci95, avg_thinking_ratio, avg_energy_j).
- **Canonical source:** `finding` payload — each `runs[]` entry carries `operator`
  (`baseline` + the 6 perturbation operators) and `perturbation_class`.
- **Join key:** `source_uri` → file → `runs[]`; group by `operator` (and `model`, the
  run's `model` field). No per-run `logical_locator` needed for the aggregation, but the
  same `logical_locator` == `basename(workdir)` key resolves the run when enumerating.
- **Verdict:** repoint to `finding` payload (recompute the aggregate; the summary's
  pre-aggregated `by_operator_model` block is retired with the summary).

### 3.3 `perturbation_class_breakdown` — iterating `summary["entries"]` (line 1021)

- **What it is:** per `perturbation_class` × model (n, avg_cost, avg_escape,
  avg_correctness, avg_thinking_ratio, avg_loc, avg_tokens, avg_narration_penalty, low_n flag).
- **Canonical source:** `finding` payload — `runs[]` carry `perturbation_class`
  (`baseline`, `process_perturbation`, `specification_corruption`, `objective_mutation`).
- **Join key:** `source_uri` → `runs[]`; group by `perturbation_class` + run `model`.
- **Verdict:** repoint to `finding` payload; **partial** — `avg_narration_penalty` has no
  finding-payload equivalent (the clean re-runs are never "narrated"; drop the field, §4).

### 3.4 `strategy_distribution` — from `summary["strategy_distribution"]` (line 1111)

- **What it is:** counts of strategy archetypes (`conservative`/`exploratory`/`wasteful`/
  `efficient`/`?`) across the perturbation cells.
- **Canonical source:** `finding` payload — `runs[]` carry `strategy` (and `strategy_score`).
- **Join key:** `source_uri` → `runs[]`; tally the `strategy` field.
- **Verdict:** repoint to `finding` payload (recompute; the summary's pre-aggregated block
  is retired).

### 3.5 `routing` — `compute_routing(entries)` (line 1112)

- **What it is:** per-task model recommendation + strategy simulation, from
  `instrument.routing.compute_routing`. Needs, per entry: `model`, `correctness`, `cost`,
  `experiment`; drops tasks with < 2 distinct models (`min_models=2`).
- **Canonical source:** `finding` payload — the file carries `experiment` (top-level,
  e.g. `"task_manager"`); each run carries `model`, `correctness`, `cost_usd`.
  `task_manager` spans 7 models and `process_perturbation_resample` spans 3, so both
  survive the `min_models=2` gate.
- **Join key:** `source_uri` (→ file, which supplies `experiment` + `runs[]`); run-level
  `model`/`correctness`/`cost_usd`. The `experiment` field used by `normalize_task` comes
  from the payload's top-level `experiment` key, not the registry row.
- **Verdict:** repoint to `finding` payload. Note the field rename `cost`→`cost_usd` and
  that `compute_routing` must be fed run-shaped dicts (phase 2 adapts or renames).

### 3.6 `sonar` — `_compute_sonar(entries)` (line 1114)

- **What it is:** per-model SonarQube aggregates (bugs/smells/ncloc/quality-score/
  maintainability/gate-pass) over entries with `sonar_analyzed == true`.
- **Canonical source:** **none.** The finding payloads carry no `sonar_*` fields, and the
  current summary itself has 0 `sonar_analyzed` entries (measured) — this section is
  already empty. There is a `report` source-type producer (`quality_ingestion.py`) for
  Sonar/LSP code-quality signals, but it is per-signal/per-locator granularity, not the
  per-cell worktree aggregate `_compute_sonar` reads, and it is not populated in the
  registry today.
- **Verdict:** **historical — no canonical replacement.** Retire the section (or emit an
  empty `{}` with a provenance note); do not fabricate Sonar aggregates from the finding
  corpus.

---

## 4. Sub-fields with NO canonical replacement (historical)

The retired summary entries were richer per-cell records than the finding payloads. When
re-pointing `perturbation_models` / `perturbation_class_breakdown`, the following
sub-metrics have no finding-payload equivalent and must be dropped (or marked
"historical"), not zero-filled:

| Summary field | Finding-payload equivalent? | Notes |
|---|---|---|
| `narration_failure`, `narration_penalty`, `narration_rate` | none | clean re-runs are never "narrated"; the flail dimension is not measured in the finding corpus |
| `ast` block (`py_files`/`total_functions`/`total_classes`/`type_hint_pct`/`docstring_pct`) | none | finding carries only `files_created`, not a full AST profile |
| `structure_divergence` | none | finding carries `architecture_divergence` + `escape_score`, not structure divergence |
| `code_quality_score`, `comment_ratio`, `cyclomatic_complexity` | none | finding carries `composite_score` only |
| `sonar_*` (all) | none | §3.6 |
| `cost_input_usd` / `cost_output_usd` / `cost_reasoning_usd` / `cost_cache_usd` | none | finding carries `cost_usd` only |
| `tokens_cache_read` / `tokens_cache_write` | none | finding carries token split, not cache tokens |
| `energy_input_j` / `energy_output_j` / `energy_reasoning_j` | `energy_j` only | total-only in the finding payload |
| `correctness_per_dollar` | approximate | finding carries `quality_per_dollar` (composite/cost), a different ratio; recompute as `correctness / cost_usd` if desired |
| `evaluator_source` / `evaluator_independent` | `test_executed_success` | superseded by the independent test-runner boolean |

**Fields the finding payload DOES carry** (the canonical replacement surface):
`model`, `operator`, `perturbation_class`, `strength`, `perturbation_strength`,
`test_executed_success`, `correctness`, `constraints_met`/`constraints_total`,
`lines_of_code`, `composite_score`, `novelty`, `total_tokens`/`prompt_tokens`/
`completion_tokens`/`reasoning_tokens`/`answer_tokens`/`explanation_tokens`, `confidence`,
`thinking_ratio`, `cost_usd`, `energy_j`, `tool_calls`, `retries`, `iteration_depth`,
`files_created`, `duration_s`, `exit_code`, `strategy`/`strategy_score`, `escape_score`,
`architecture_divergence`, `quality_per_dollar`, `quality_per_joule`.

This is the canonical vocabulary the site's perturbation surfaces must switch to.

---

## 5. Sections NOT derived from the summary (unchanged, listed to bound the change)

These `data.js` sections already have non-summary sources and are **out of scope** for the
repoint (they are the story side, which is already canonical-state-adjacent):

| Section | Current source | Phase-2 note |
|---|---|---|
| `models` (final) | `stories.parquet` via `compute_story_models()` | already story-based; should also gate on registry `story` rows (exclude 77 tombstones) |
| `stories` | `_load_story_data()` → `sessions.parquet` + `stories.parquet` | same gate |
| `charts`, `calculator`, `derived`, `energy_ranking` | recomputed from `models` (story) | same gate |
| `summary` block | `inventory.json` counts + story totals | `worktrees_total`/`sessions_total` come from inventory, not the summary file |
| `grit_matrix` | `lab_grit_matrix.json` | unchanged |
| `reviews`, `analysis`, `labs` | `reviews/`, `analysis/`, `lab_*.json` dirs | unchanged (phase 3+ may re-point `reviews` at `review` registry rows) |
| `design_parameters`, `external_sources` | hard-coded | unchanged |

---

## 6. Join-key contract (phase 2 implementation reference)

Two-stage join, mirroring `scripts/registry.py` + `knowledge_stream.read_artifact`:

1. **File-level:** parse the registry row's `source_uri`.
   - `finding`: `file://experiments/results/<name>_<model>.json` → strip `file://`, resolve
     relative to the checkout root.
   - `story`: `story:<story_id>` → resolve `experiments/results/stories/*_<story_id>.json`
     (the payload's own `story_id` field equals `logical_locator`).
2. **Cell-level:** match `logical_locator` to the payload element:
   - `finding`: `logical_locator == basename(run["workdir"])`.
   - `story`: `logical_locator == payload["story_id"]`.

Only `lifecycle_state == "current"` rows join. A `tombstoned` row (reason =
`"contaminated: …"`) is excluded before any join.

**Resolvability (measured):** 64/64 finding rows resolve to an on-disk payload file;
215/225 current story rows resolve to a `stories/*.json` file (the remaining 10 current
story rows have no matching payload on disk — the 80 instrumented re-runs live outside the
default `stories/*.json` glob and must be located before phase 2 can surface them). This
is the one concrete gap phase 2 must close, not a schema issue.

---

## 7. Phase-2 deltas for `build_data.py`

1. Replace `load_summary()` / `SUMMARY_PATH` with a `load_registry()`-equivalent read of
   `experiments/data_manifest.json` `registry` array (import from `scripts/registry.py` or
   read the file directly; the manifest is the compacted index — no Redis/Neo4j needed).
2. Build the `entries` list that `compute_model_data`, `perturbation_class_breakdown`,
   `compute_routing`, and `_compute_sonar` consume **from the 64 current `finding` rows**,
   mapping each `runs[]` element into the summary-shaped dict (renaming `cost_usd`→`cost`,
   `lines_of_code`→`code_lines`, etc.), keeping the finding's native field names where
   §4 shows an equivalent, and dropping §4's "historical" fields.
3. Gate the story surfaces (`models`, `stories`, `summary` totals) on the **225 current**
   `story` rows, excluding the 77 tombstoned.
4. Retire `sonar` (emit `{}` or drop) and the `narration_*`/AST/structure-divergence
   sub-fields — no canonical source exists.
5. Keep `_meta.source_summary`/`_meta.source_db` cosmetic provenance updated to point at
   `data_manifest.json` instead of `_results_summary.json`.
