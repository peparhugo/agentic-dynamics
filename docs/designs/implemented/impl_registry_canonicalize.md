---
status: implemented
implemented_by: feature/registry-canonicalize
---
# Implementation trace — corpus canonicalization

Implements `docs/verification/data_integrity_findings.md`'s four treatment rules against the
canonical-state registry producers. Each rule below is traced to its exact code, the test
that pins it, and its PASS/FAIL result, followed by the dry-run counts and a drift check
against the canonical doc. Read at commit `HEAD` of `feature/registry-canonicalize`.

The canonical record (`docs/verification/data_integrity_findings.md`) states the boundary once: the old
cells *really ran* (cost + code-quality stay valid) but their *perturbation labels* were
no-ops — the mutation silently fell back to the clean spec (P0-7) or never degraded. The
treatment is therefore **relabel, don't delete**, except for the 77 contaminated cells
(quarantined → tombstone) and the 144-entry summary (retire, replace with the clean re-runs).

---

## Trace table

| # | Rule | Where it lives | What it does | Verifying test(s) | Result |
|---|---|---|---|---|---|
| 1 | **RELABEL** — no-op `early_degrade`/`bad_seed` → `clean` | `src/instrument/story_ingestion.py:74` (`NOOP_CONDITIONS`), `:78` (`CLEAN_CONDITION`), `:100` (`_is_noop_condition`), `:115` (`_effective_condition`), `:133` (`_render_text`) | A story whose `perturbation_condition ∈ {early_degrade, bad_seed}` **and** whose `test_executed_success` is not a bool (non-instrumented, pre-fix) is relabeled `clean` with a `no-op` caveat rendered into the text; instrumented cells keep their label | `tests/test_story_ingestion.py::test_noop_early_degrade_relabeled_to_clean_with_caveat`, `::test_noop_bad_seed_relabeled_to_clean`, `::test_instrumented_early_degrade_keeps_its_label`, `::test_genuinely_clean_cell_is_untouched`, `::test_non_instrumented_early_degrade_relabels_to_clean_with_caveat`, `::test_non_instrumented_bad_seed_relabels_to_clean`, `::test_instrumented_early_degrade_keeps_condition`, `::test_late_degrade_is_not_a_noop_and_keeps_condition` | **PASS** |
| 2 | **SINGLE-TASK** — register the clean re-runs as `finding` records | `scripts/kb_produce_registry.py:82` (`SINGLE_TASK_DIR`), `:86` (`SINGLE_TASK_PREFIXES`), `:91` (`INVALID_GPT56_MODEL`), `:217` (`_iter_single_task_files`), `:231` (`_is_invalid_gpt56`), `:242` (`_run_to_entry`), `:269` (`derive_single_task_pass`), `:438` (`_SOURCES["single-task"] = ("finding", …)`) | Derives one MEASURED `finding` record per run in `task_manager_*.json` + `process_perturbation_resample_*.json`, skipping the invalid plain-`gpt-5.6` file, with each file's own `file://` locator as `source_uri` | `tests/test_kb_produce_registry.py::test_derive_single_task_pass_emits_finding_records`, `::test_derive_single_task_pass_skips_invalid_gpt56`, `::test_run_to_entry_renames_cost_and_escape_and_worktree`, `::test_run_to_entry_falls_back_to_file_model`; `tests/test_knowledge_ingestion.py::test_build_record_source_uri_override_changes_identity`, `::test_derive_records_source_uri_threads_through` | **PASS** |
| 3 | **RETIRE** — remove `summary-recovery` + `--since-sha` | `scripts/kb_produce_registry.py` (removed `derive_summary_recovery_pass`, `_historical_results_summary`, `_summary_entry_to_story_result`, `RESULTS_SUMMARY_PATH`, the `--since-sha` flag, and its `main()` branch) | The flawed 144-entry summary fold is gone — no source reads `_results_summary.json` anymore, so those entries are never re-emitted | `tests/test_kb_produce_registry.py::test_summary_recovery_is_retired`, `::test_cli_rejects_the_retired_summary_recovery_source` | **PASS** |
| 4 | **TOMBSTONE** — keep the 77 contaminated cells | `scripts/kb_produce_registry.py:307` (`CONTAMINATED_REASON`), `:313` (`derive_contaminated_tombstone_pass`), `:523` (`emit_records(…, operation="delete", reason=CONTAMINATED_REASON)`) | Unchanged: the contaminated source still derives one record per cell and `main()` publishes it under `operation="delete"` + the forensic reason | `tests/test_kb_produce_registry.py::test_derive_contaminated_tombstone_pass_reads_the_contaminated_subdir` | **PASS** |

Supporting change (rule 2's plumbing, not a rule itself): `src/instrument/knowledge_ingestion.py:222`
and `:384` add a keyword-only `source_uri` parameter to `build_record` / `derive_records`
(default `SOURCE_URI`), so the single-task producer can key `entity_id` off the individual run
file instead of the retired aggregate summary.

---

## Rule notes

### 1 — Relabel (relabel, don't delete)

The signal for "non-instrumented" is `test_executed_success` **not being a bool** — the exact
test in `docs/verification/data_integrity_findings.md` treatment rule 1 ("lacks `test_executed_success`").
This mirrors the canonical record's own forward-looking note: a condition label without that
evidence is a no-op. The relabel is confined to `early_degrade` and `bad_seed`; `late_degrade`
(session-4 spec corruption, a real perturbation) is deliberately **not** in `NOOP_CONDITIONS`
— `tests/test_story_ingestion.py::test_late_degrade_is_not_a_noop_and_keeps_condition` pins that
so a future broadening can't silently swallow it.

The caveat travels in the rendered `text` (the retrieval-facing evidence line), not a new
structured field — `KnowledgeRecord` carries no condition/caveat column, and the cost/code-quality
measurements (the reason these records are kept at all) already flow through the existing
`perturbation_strength` / `test_executed_success` fields unchanged.

**Real-corpus effect:** 48 cells relabeled (`early_degrade` × 11 + `bad_seed` × 37), 80
instrumented `early_degrade` re-runs kept. The 48 + 80 = 128 is the perturbed-arm accounting;
the clean baseline (83 clean + 48 relabeled no-op) and the 80 re-runs match the canonical
record's inventory modulo the 4 `bad_seed` cells that had already left the directory.

### 2 — Single-task (register the clean re-runs)

The clean re-runs live as *run files*, not `_results_summary.json` entries, so they need a
small field-renaming adapter (`_run_to_entry`) before `knowledge_ingestion.derive_records` can
consume them: `cost_usd → cost`, `escape_score → escape` (the basin-escape signal
`build_evidence_cards`' `_derive_flail` falls back to), and the `workdir` basename → the durable
`worktree_name`/`run_id` locator. Each record is `source_type=finding` (never `story`), authority
`MEASURED`, evidence class `[M]` — the same finding shape the summary corpus uses.

The invalid file is identified by the plain model id `"gpt-5.6"` (top-level `data["model"]`),
not the `-luna`/`-sol`/`-terra` variants, which are valid and kept. A logged reason accompanies
the skip, per the spec's rule 2.

### 3 — Retire (the flawed 144 are never re-emitted)

Retirement is structural, not conditional: the source key, its derive function, its two helpers
(`_historical_results_summary`, `_summary_entry_to_story_result`), its path constant
(`RESULTS_SUMMARY_PATH`), and the `--since-sha` plumbing are all deleted. Because nothing in
`_SOURCES` references `_results_summary.json` anymore, the 144 entries have no derive path at
all — `test_summary_recovery_is_retired` asserts the absence of each symbol, and
`test_cli_rejects_the_retired_summary_recovery_source` asserts `--source summary-recovery` is no
longer an accepted argparse choice and `--since-sha` no longer exists.

### 4 — Tombstone (contaminated unchanged)

No code changed here beyond the single-task/summary edits around it. The 77 cells under
`stories/_remediation_contaminated/` still derive one story record each, and `main()` still
publishes them under `operation="delete"` with `CONTAMINATED_REASON`
("contaminated: ran as CLEAN due to the P0-7 mutation fallback …").

---

## Dry-run counts

```
python3 scripts/kb_produce_registry.py --dry-run
```

| source | label | derived |
|---|---|---|
| story | story | 215 |
| story-worktree | story | 437 |
| review | review | 242 |
| single-task | finding | 64 |
| contaminated | story | 77 |
| meta-audit | meta_session | 27 |

Total would-emit: **1062**. The `single-task` count decomposes exactly: 7 `task_manager_*` files
× 7 runs = 49, plus 3 valid `process_perturbation_resample_*` files × 5 runs = 15 → 64; the one
invalid `process_perturbation_resample_gpt-5.6.json` (5 all-zero runs) is skipped with a logged
reason, so it contributes nothing. `contaminated` is 77 — unchanged. `summary-recovery` is absent
from the source list entirely.

---

## Drift check — `docs/verification/data_integrity_findings.md` vs implemented behavior

| Treatment rule (canonical doc) | Implemented behavior | Drift? |
|---|---|---|
| 1. Relabel, don't delete, the no-op cells (`early_degrade`/`bad_seed` + no `test_executed_success`) → `clean` + caveat; cost/code-quality stay valid | `story_ingestion._effective_condition` relabels exactly these; caveat rendered in text; `perturbation_strength`/`test_executed_success` untouched | **None** |
| 2. Only instrumented cells carry a perturbation signal; the `task_manager_*` + `process_perturbation_resample_*` results are the clean single-task arm | 80 instrumented `early_degrade` keep their label; single-task re-runs registered as `finding` | **None** |
| 3. The 77 contaminated cells are tombstoned (`delete` + reason) | `derive_contaminated_tombstone_pass` + `operation="delete"` + `CONTAMINATED_REASON` | **None** |
| 4. The 144-entry `_results_summary.json` is retired, not recovered — the clean re-runs replace it | `summary-recovery` source + `--since-sha` plumbing removed; nothing folds into the summary | **None** |

One deliberately-minor divergence from the doc's *inventory table counts* (not its rules): the
table lists 41 `bad_seed` no-op cells, but the directory now holds 37 — four `bad_seed` cells had
already left `experiments/results/stories/` before this pass. The **rule** is honored (every
remaining non-instrumented `bad_seed` is relabeled); the count reflects current on-disk state,
not a rule deviation.

---

## Verification

### Targeted gate

```
pytest tests/test_kb_produce_registry.py tests/test_story_ingestion.py \
       tests/test_knowledge_ingestion.py -q
# 97 passed
```

### Full gate

```
pytest tests/ -m "not external" -q
# 1087 passed, 101 deselected, 19 warnings
```

The 101 deselected are `external`-marked integration tests (live Redis/Neo4j) — no regressions.
No test was weakened; the implement phase added relabel, single-task, retire, and `source_uri`
override tests, and the test phase added the `late_degrade` non-no-op guard and the
`[early_degrade] not in text` precision assertion on top of them.
