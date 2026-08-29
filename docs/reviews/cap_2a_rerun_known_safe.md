---
status: accepted
---

# cap_2a_rerun — known-safe register

Every entry is an attack that was actually attempted and did **not** falsify the campaign, with the concrete evidence (artifact path / code line) that makes it safe. This is not a generic checklist; each item names what was tried and why the tree says it's safe.

## Attacks that did not falsify the campaign

### A. Independent test evidence (F2) — not a self-report
- **Tried:** check whether any `test_executed_success=True` could be a model self-report rather than the independent runner.
- **Evidence:** `src/agentic_dynamics/runtime/workflow_runner.py:762` (`suite = run_suite(...)`) and `:765` (`pr.test_executed_success = suite_succeeded(suite)`); the `kind:test` branch never reads the agent's response. Ledgers show `3/3`, `3/3`, `4/4` from the test phase.
- **Why safe:** the sole source of the verdict is `runtime.test_runner.run_suite`, and it is exercised for every ran cell.

### B. KB fact auto-emit present (F3)
- **Tried:** look for a run whose `derive_run_facts`/`publish_event` silently dropped a phase.
- **Evidence:** run logs `workflow facts: emitted=30 skipped=0`, `emitted=28 skipped=0` (×2); `experiments/results/registry_index.jsonl` and `experiments/results/kb/*.json` are committed.
- **Why safe:** no phase's facts are absent.

### C. Verifier and baseline on the same worktree
- **Tried:** mismatch each proposal's `baseline_revision`/`analyzed_revision` against the worktree `git log`.
- **Evidence:** each worktree logs `seed → [workflow] implement → [workflow] test → [workflow] verify`; proposal `baseline_revision` = the seed commit and `analyzed_revision` = the implement commit in the *same* worktree (p2 `4c9d8525`/`f5547d56`, p3a `e8339c05`/`790eb68b`, p3b `17142923`/`e136ce25`).
- **Why safe:** the verifier's input and the baseline's output share one worktree and one input; no cross-worktree contamination.

### D. No cherry-picking / no unlisted cells
- **Tried:** confirm every scored cell appears in a committed manifest and none was added after the fact.
- **Evidence:** scored cells = `cap2a_p2_bespoke` (in `p2_cell_manifest.json`), `cap2a_p3a` + `cap2a_p3b` (in `p3_execution_manifest.json`, committed *before* execution); `n_not_run=0`.
- **Why safe:** the cell set is fixed and immutable before any run.

### E. Proposals validated against outcomes
- **Tried:** check for a proposal that was never joined to a realized outcome.
- **Evidence:** `cap_2a_rerun_score_*.json` `cells[]` carries `proposal_action`, `outcome`, `hit`, and `reason` for all three; each proposal passed `validate_verify_proposal`.
- **Why safe:** every proposal is scored, none orphaned.

### F. Analyzer-down cells retained and honestly flagged
- **Tried:** see whether lsp-unavailable cells were dropped or mislabeled as available.
- **Evidence:** all 3 cells `lsp_analysis_status=unavailable`, `new_lsp_error_count` omitted (null-not-zero); risk still minted from sonar + impacted + tests_ratio. Graph `available` on all three.
- **Why safe:** no cell dropped; the unavailable analyzer is a measured status, not a fabricated zero.

### G. Sonar revision identity is genuine (no stale-refused smuggled through)
- **Tried:** confirm `analysis_revision_matches=true` is earned, not defaulted.
- **Evidence:** `_sonar_evidence` passes `revision=<full sha>` → revision-scoped project key; `sonar.run_sonar_analysis` sets `status=available` only after `_revision_confirmed`, else `stale-refused`. All three cells: `available` + `revision_matches=true`.
- **Why safe:** a stale or unconfirmable analysis would be refused, not stamped.

### H. Risk weights match the [P] provenance
- **Tried:** recompute the risk from first principles and compare to the reducer's documented weights.
- **Evidence:** `RISK_WEIGHTS = (0.35, 0.25, 0.20, 0.20)` (`code_change_facts.py:104`); p3b recomputation `(0.35·0.1 + 0.20·0.6667 + 0.20·0.4)/0.75 = 0.3311` matches the ledger.
- **Why safe:** the reported risk is exactly the deterministic formula, no drift.

### I. Hit-rate denominator is complete (no games)
- **Tried:** re-derive the denominator and hunt for silent exclusions.
- **Evidence:** `n_scored=3`, `n_unknown_outcome=0`, `n_invalid_join=0`, `n_not_run=0`; `3+0+0+0 == n_ran=3`.
- **Why safe:** no cell is dropped from the denominator; unknown/invalid would be printed, not removed.

### J. p1 byte-identical without `--change-analysis`
- **Tried:** diff the no-analyzer execution path against the pre-campaign HEAD.
- **Evidence:** `_git_commit` is byte-identical to `21ea701ed`; `run_sonar_analysis`/`run_diagnostics` are reached only through `_run_change_analysis`, gated by `change_analyzer is not None` (`workflow_runner.py:905`).
- **Why safe:** without injection the seam is inert — no prompt, no ledger, no sonar/lsp call changes.

### K. Live-probe ledger row is real
- **Tried:** falsify `p1_live_probe_ledger.json` against the probe's observed output.
- **Evidence:** the probe's own stdout was `code_change_risk = 0.08`; the ledger records `"0.08"` with the matching term arithmetic.
- **Why safe:** the blocker-chain proof is a measured row, not a hand-authored claim.

### L. No actuation, no applied=true
- **Tried:** grep for `applied=true`, actuation records, and actuation-seam flags in the campaign's cells.
- **Evidence:** all 3 proposals `applied=false`; bespoke specs have no `control_route`/`cap_shadow`/`cap_snapshot`; the only `source_type:actuation` kb rows belong to a *different* campaign (`self-wf_cap_shadow_campaign_anthropic_claude_sonnet_5`); the proposal seam is AST-verified artifact-only (`test_proposal_seam_never_actuates_or_steers`).
- **Why safe:** the shadow seam emitted and never applied; no actuation event, no route flip.

### M. Neo4j driver closed
- **Tried:** trace the graph client lifecycle in the composition root.
- **Evidence:** `scripts/run_workflow.py:306-308` closes `graph_client` in a `finally` even on exception.
- **Why safe:** no leaked driver.

### N. No leaked credentials
- **Tried:** scan the campaign artifacts + the two docs for secrets.
- **Evidence:** no `password=`/`password123`/`sk-…`/`api_key=…` match in `experiments/results/cap_2a_rerun/**` or `docs/designs/current/cap_2a_rerun.md`.
- **Why safe:** nothing secret reached a committed artifact.

### O. Verdict hash citations are exact
- **Tried:** recompute every SHA256 cited in the p5 verdict and compare to disk.
- **Evidence:** all six hashes match byte-for-byte (score `59bd15d8…`, validation `690e0878…`, p2 outcome `1307c0ca…`, p2 ledger `ab0bf334…`, p3 manifest `2cf106b6…`, candidate manifest `62af69cd…`).
- **Why safe:** the verdict's provenance is verifiable and current.

### P. Duplicate-qname collapse did not fabricate the impacted count (F1)
- **Tried:** check whether the scored `impacted_count=4` could be a same-name collapse.
- **Evidence:** the seeded app has unique symbol names (`calc.py`: `add`,`multiply`,`subtract`, 1 each); the p3a neighborhood `['add','subtract','test_add','test_subtract']` is 4 distinct qualified names with `len(set)==len`.
- **Why safe:** the F1 limitation exists in general but is not exercised by any scored cell, so the impacted counts are not corrupted by it.

## Summary

Sixteen attacks were attempted and none falsified the campaign. The two things that *did* shape the result — `new_sonar_critical_count` severity conflation (S1244 → spurious `rework`) and single-agent outcome adjudication — are recorded as accepted limitations in `cap_2a_rerun_adversary.md`, with residual risk and the fix path. The 2b-gate NOT-met verdict is a real, reproducible measurement, not an artifact of the campaign's own accounting.

**LOG:** 16 attacks, 0 falsified; 2 accepted limitations cross-referenced. **PASS.**
