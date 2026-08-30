---
status: accepted
---

# cap_2a_rerun2 — known-safe (non-falsifying attacks)

Every attack below was actually attempted and failed to falsify the campaign. For each: what was tried, the artifact/tree evidence, and why it is safe. Not a generic checklist.

## 1. Severity filter is a no-op (server not actually filtering)

**Tried:** claim that `new_sonar_critical_count=0` on the style cell is an artifact of an empty issue surface, not the severity filter.

**Evidence:** live probe `api/issues/search` on `exp_cap2a_cell_style_rerun2_9b5f39e75b2c` — *all* severities returns **5** issues (`python:S1244` MAJOR ×5), while `severities=BLOCKER,CRITICAL` returns **0**. The inverse probe on the critical cell returns `python:S3776` CRITICAL under both. The filter demonstrably removes MAJOR and keeps CRITICAL.

**Why safe:** the severity filter is applied server-side and verified against the live instrument, not assumed. Hermetic coverage: `tests/test_sonar.py::test_fetch_sonar_issues_passes_severities_filter`.

## 2. The reducer v2 is just a renamed v1 (semantics unchanged)

**Tried:** claim the `code_change_facts/v1 → /v2` bump relabeled the reducer without changing the measurement.

**Evidence:** `workflow_runner.py:392-394` now computes the count from `fetch_sonar_issues(…, severities="BLOCKER,CRITICAL")` + `new_issue_count(before, after)` (before/after identity diff) — the v1 seam computed `bugs + vulnerabilities` at one revision with no severity dimension. The live probe ledger (`p1_live_probe_ledger.json`) shows clean→0 and critical→1, exactly what the v2 semantics predict.

**Why safe:** the version bump is backed by a changed producer (the seam), and the live probe reproduces the two boundary cases. `verify_proposal.py` (the treatment) is untouched since `e61c709eb`.

## 3. The critical cell was "forced" into rework by a planted prompt

**Tried:** claim the rework outcome is circular because the implement prompt literally instructs a defect.

**Evidence:** the prompt (`cap_2a_cell_critical.yaml`) instructs the *defect*, but the *measurement* (the verifier's `rework` proposal) is produced independently by the seam from the sonar facts — the proposal is `build_verify_proposal` over the committed facts (`new_sonar_critical_count=1`), not the prompt text. The realized outcome is adjudicated separately from the commit (`classify(10.0)=='twenties'`) + `test_executed_success=False` (2/3).

**Why safe:** this is the design doc's §RC5 deterministic-stimulus control — the defect is a controlled input, the verifier's reaction is the measured output. No circularity.

## 4. mypy invocation is broken / misclassifies errors

**Tried:** claim the LSP leg silently returns unavailable or misclassifies errors (the pyright `libatomic.so.1` failure the rerun hit).

**Evidence:** `lsp_analysis_status=available` on all 3 cells; `lsp_diagnostics.py` invokes `sys.executable -m mypy --show-column-numbers …` (the measured fix); the p1 live probe ledger shows mypy ran and minted `new_lsp_error_count=0` (a real measured zero, not a fabricated one — the status is `available`). `tests/test_lsp.py` covers `_parse_mypy` on the column-numbered format.

**Why safe:** the tool is pinned, runnable (`mypy 2.3.1` installed), and its availability is measured per cell, never assumed.

## 5. The score was computed by hand, not from the artifacts

**Tried:** claim the hit-rate/aggregates are operator-invented rather than read from immutable artifacts.

**Evidence:** `p4_validation.json::verdict_number_to_field` traces every aggregate to a `cells[]`/`aggregates` field of the score JSON, which itself joins the committed proposals (SHA256-indexed) and outcomes. `hit` is recomputed by a pure function over `proposal_action/depth/scope` vs `realized_outcome/depth/realized_symbol_set` — reproducible from the JSON.

**Why safe:** the scoring is deterministic and traceable to committed JSON; no number is asserted without a field path.

## 6. Blast-radius error is fabricated (graph actually down)

**Tried:** claim `impacted_symbol_count=4` was invented and the graph leg was unavailable.

**Evidence:** `graph_status=available`, `graph_updated=true`, `impacted_count=4` on the implement phases of all three cells; Neo4j `bolt://localhost:7687` was reachable (the p2/p3 runs used `--change-analysis-graph`). `blast_radius_error` is computed `abs(impacted − len(realized_symbol_set))`, with `n_available=3`.

**Why safe:** the graph leg ran and its status is recorded per phase; the blast-radius errors (4/3/4) follow from the recorded counts, not a guess.

## 7. Proposals predate the outcome (look-ahead leakage)

**Tried:** claim the proposals were written after the outcomes were known.

**Evidence:** each proposal's `recorded_at` = the implement phase's `change_analysis.observed_at` (e.g. critical `2026-08-26T01:37:13Z`), which precedes the outcome adjudication; the proposal is emitted from the implement-phase facts alone (before the test phase's verdict). The critical cell's proposal (`rework/d3`) was emitted before the post-hoc evaluator ran (`classify(10.0)=='twenties'` was checked after emission).

**Why safe:** the proposal is produced from the implement phase's `change_analysis`, recorded before the outcome; the outcome record is a separate artifact with its own adjudication note.

## 8. Applied=true or an actuation slipped through

**Tried:** search the tree and artifacts for an `applied=true` stamp, a `control_route` flip, or an actuation record.

**Evidence:** all three proposal artifacts carry `"applied": false` and schema `verify_code_change_proposal/v1`; `verify_proposal.py` refuses `applied=true` (`tests/test_code_change_facts.py::test_proposal_schema_validation_with_applied_false`); no `actuation`/`control_route` write exists in the campaign artifacts.

**Why safe:** hard-rule 2 (APPLY STAYS OFF) held — shadow-only proposals, never applied.

## 9. The p1 "byte-identical without --change-analysis" claim is false

**Tried:** diff the non-analysis path to see if the measurement changes leak into plain runs.

**Evidence:** `workflow_runner.py:962-963` gates `_run_change_analysis` on `change_analyzer is not None` (only set by `--change-analysis`); the sonar/lsp legs live inside that function; the `scripts/run_workflow.py` edit is a help-text string (`:206`). Without the flag, the sonar/lsp imports are never exercised.

**Why safe:** the seam is opt-in; a plain run is indistinguishable from pre-p1 main (the reducer/registry changes are static declarations, inert without a change-analysis run).

## 10. Credentials leaked in artifacts

**Tried:** grep every campaign artifact + the two design docs for secrets.

**Evidence:** the only `admin`/`password` string is `cap_2a_rerun2_measurement_design.md:13`, which documents the **local** SonarQube scanner default (`SONAR_USER_DEFAULT`/`SONAR_PASSWORD_DEFAULT` already committed in `sonar.py`) — a documented local-dev default, not a secret. No token/key in `experiments/results/cap_2a_rerun2/`.

**Why safe:** nothing beyond the already-committed local default is present; no external credential appears.

## 11. p4 hashes don't match the verdict's citations

**Tried:** recompute the two p4 JSON SHA256s and compare to `docs/experiments/results/cap_2a_rerun2.md`.

**Evidence:** `cap_2a_rerun2_score_20260826T015846Z.json` → `ef42f8b0ae07704cc693c51243dc755807586b0b745365d606e76410b19dd1ec`; `p4_validation.json` → `a2fd71fde21ef2563debd497fbd6224761c89365a05cbca64bf89ac87dd3375b` — both equal the verdict's citations.

**Why safe:** the verdict's provenance is exact.

## 12. The critical cell's `ok=False` is a hidden campaign failure

**Tried:** claim the critical cell "failed" and should have been dropped or re-run.

**Evidence:** the run's `ok=False` is the *measured* outcome — the deliberate boundary defect made the independent test phase fail (2/3). The cell's proposal + outcome + cost were all recorded and scored (it is the campaign's required `targeted_rework` row). No cell was dropped or re-run.

**Why safe:** a test failure on the defect-bearing variant is the calibration signal, not a failure to measure; the p3 outcome-spread requirement (≥1 targeted_rework) is satisfied precisely by this cell.

**LOG — known-safe list:** 12 non-falsifying attacks, each with artifact/tree evidence and a why-safe statement. No bare PASS.
