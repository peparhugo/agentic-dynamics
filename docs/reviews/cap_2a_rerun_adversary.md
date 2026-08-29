---
status: accepted
---

# cap_2a_rerun — adversarial verification

Every finding below was re-verified against the tree (artifact paths + code lines), not imagined. Result legend: **SAFE** (did not falsify) / **ACCEPTED** (limitation recorded with residual risk). No p4 JSON or the p5 verdict was rewritten; where a correction is noted, the corrected artifact and its hashes are cited.

## Re-stated verdict (unchanged)

The 2b calibration threshold (hit-rate >= 0.6) is **NOT met**: hit-rate **0/3**, Wilson 95% **[0.0, 0.5615]**, n=3 (descriptive-only). `risk_mint_rate = 1.0` proves p1's wiring worked (the first campaign's blocker is fixed); the remaining blocker is that the verifier over-predicts intervention (`verify`/`rework` against `no_rework` in all 3 cells). This verdict survives adversarial attack.

---

## Findings

### 1. (F1) Duplicate qualified names collapsing in the CALLS edge — **ACCEPTED (does not bite)**

- **Attack:** does any scored number (impacted/neighborhood) derive from an expansion over same-named symbols, where a duplicate-name collapse would fabricate a count?
- **Evidence:** the seeded app has unique symbol names in every cell — p3a `calc.py` = `add`, `multiply`, `subtract` (1 each, `grep -oE '^def [a-z_]+' /tmp/cap2a_cell_p3a/calc.py | sort | uniq -c`); the p3a implement neighborhood is `['add','subtract','test_add','test_subtract']`, `impacted_count=4`, and `len(set)==len` (unique). Same for p2 and p3b.
- **Result:** the F1 limitation (duplicate qualified names would collapse in the CALLS/impact edge) is **real in general but does not affect this campaign's scored numbers** — the seeded app never has two symbols of the same name.
- **Fix:** none needed for this campaign. Residual risk: a future cell over a codebase with same-named symbols in different modules would need the F1 fix (version-entity-id-qualified names, not bare `qualified_name`) before its impacted count is trusted.

### 2. (F2) Cells without independent test_runner evidence — **SAFE**

- **Attack:** is any `test_executed_success` a model self-report rather than the independent `runtime.test_runner`?
- **Evidence:** all 3 cells have a `kind: test` phase. `workflow_runner.py:762-765` sets `suite = run_suite(...)` → `pr.test_executed_success = suite_succeeded(suite)` — the sole source is `runtime.test_runner`, never `ar.final_response`. Ledgers: p2 `test_executed_success=True (3/3)`, p3a `True (3/3)`, p3b `True (4/4)`.
- **Result:** SAFE. Every ran cell has independent test evidence (hard rule 14 satisfied).

### 3. (F3) Canonical KB facts silently absent — **SAFE**

- **Attack:** did any run's fact auto-emit silently drop a phase's facts?
- **Evidence:** run logs `workflow facts: emitted=30 skipped=0`, `emitted=28 skipped=0` (×2) for the three runs; the kb registry (`registry_index.jsonl`) and `experiments/results/kb/*.json` artifacts are committed.
- **Result:** SAFE. No phase's fact auto-emit is missing.

### 4. Wrong baseline (verifier and baseline on different inputs/worktrees) — **SAFE**

- **Attack:** does a proposal's `baseline_revision` differ from the worktree the cell actually ran in?
- **Evidence:** each worktree's `git log` is `seed → [workflow] implement → [workflow] test → [workflow] verify`. The proposal `baseline_revision` equals that cell's seed commit (p2 `4c9d8525`, p3a `e8339c05`, p3b `17142923`) and `analyzed_revision` equals its implement commit, all in the same worktree.
- **Result:** SAFE. (Note: `source_baseline_revision` in the manifests is the *finops repo* revision `ec9f1b8a6`/`1adb6458` — the campaign code provenance, a different axis than the cell's seed-commit baseline; both are recorded and the scoring joins on the cell baseline.)

### 5. Cherry-picked cells / unlisted cells — **SAFE**

- **Attack:** is any scored cell absent from the p2 cell manifest / p3 execution manifest?
- **Evidence:** the 3 scored cells are `cap2a_p2_bespoke` (p2 cell manifest), `cap2a_p3a` and `cap2a_p3b` (p3 execution manifest). No unlisted cell was run; `n_not_run=0`.
- **Result:** SAFE.

### 6. Proposals recorded but never validated against realized outcomes — **SAFE**

- **Attack:** are proposals present without a validated hit/miss against the realized outcome?
- **Evidence:** p4 score JSON `cells[]` carries `proposal_action`, `outcome`, `hit` (0/1) and `reason` for each; every proposal was `validate_verify_proposal`-validated (applied=false, schema `verify_code_change_proposal/v1`, contract `verify_code_change/v1`).
- **Result:** SAFE.

### 7. Graph-down / analyzer-down cells silently dropped or mislabeled — **SAFE**

- **Attack:** is any unavailable analyzer silently treated as available, or any cell dropped?
- **Evidence:** graph `available` on all 3; lsp `unavailable` on all 3 (pyright/mypy not installed), recorded as `lsp_analysis_status=unavailable` with `new_lsp_error_count` omitted (never zero) — the null-not-zero rule. No cell was dropped; lsp-down cells still contributed (risk minted from sonar + impacted + tests_ratio).
- **Result:** SAFE.

### 8. Stale sonar facts (analyzed_sha mismatch / stale-refused ignored) — **SAFE**

- **Attack:** is any `sonar_analysis_status=available` actually a stale/refused analysis mislabeled?
- **Evidence:** `_sonar_evidence` (`workflow_runner.py:306`) passes `revision=<full sha>` to `run_sonar_analysis`, which builds a revision-scoped project key; `run_sonar_analysis` sets `status=available` only after `_revision_confirmed` (fresh scan under the revision-scoped key) and `stale-refused` otherwise. All 3 cells: `sonar_analysis_status=available`, `analysis_revision_matches=true`. The stale-refused→omit path is unit-tested (`test_stale_refused_sonar_emits_status_and_marks_revision_mismatch`).
- **Result:** SAFE.

### 9. Risk weights drifting from the [P] provenance — **SAFE**

- **Attack:** do the runtime risk weights differ from the reducer's documented `[P]` weights?
- **Evidence:** `RISK_WEIGHTS = (new_sonar_critical 0.35, new_lsp_error 0.25, tests_ratio 0.20, impacted 0.20)` (`code_change_facts.py:104-109`), matching the docstring. Re-computed p3b risk independently: `(0.35·0.1 + 0.20·0.6667 + 0.20·0.4)/0.75 = 0.3311` — matches the ledger.
- **Result:** SAFE.

### 10. Hit-rate denominator games — **SAFE**

- **Attack:** are any cells silently excluded from the denominator?
- **Evidence:** `n_scored=3`, `n_unknown_outcome=0`, `n_invalid_join=0`, `n_not_run=0`; `n_scored + unknown + invalid + not_run == n_ran = 3`. Every ran cell is scored.
- **Result:** SAFE.

### 11. p1 wiring changing no-analyzer behavior (byte-identical claim) — **SAFE**

- **Attack:** does the p1 diff alter the no-`--change-analysis` execution path?
- **Evidence:** `_git_commit` is byte-identical to the pre-campaign HEAD `21ea701ed` (`diff` on the function body is empty). `run_sonar_analysis`/`run_diagnostics` are invoked only from `_sonar_evidence`/`_lsp_evidence`, which are called only inside `_run_change_analysis` (lines 411-412), which is entered only when `change_analyzer is not None` (`workflow_runner.py:905`). No analyzer injected → no sonar/lsp call → byte-identical.
- **Result:** SAFE.

### 12. Risk minted but the live-probe ledger row falsified — **SAFE**

- **Attack:** is `p1_live_probe_ledger.json` a fabricated row?
- **Evidence:** the p1 probe was a real run (real git + real sonar-scanner + real Neo4j + real reducer) over a symbol change; its observed output was `code_change_risk = 0.08`, and the ledger records `code_change_risk = "0.08"` with the matching risk-term arithmetic `(0.35·0.0 + 0.20·0.0 + 0.20·0.3)/0.75 = 0.08`.
- **Result:** SAFE.

### 13. Proposal/outcome circular labeling — **ACCEPTED (single-agent adjudication)**

- **Attack:** is the realized outcome derived from the proposal (circular)?
- **Evidence:** outcomes were adjudicated from the baseline's immutable implement commit + the `runtime.test_runner` verdict (e.g. p3b `outcome=no_rework` because `divide()` guards `b==0` and 4/4 tests pass), NOT from the proposal. The proposal (risk-driven `rework`) is opposite the outcome (`no_rework`) — the two disagree, which itself disproves circularity.
- **Fix/accepted limitation:** the same agent emitted proposals and adjudicated outcomes. Independence is *procedural* (outcome is deterministically derivable from the immutable commit + test result, and is opposite the proposal), not *separate-agent*. Residual risk: low for this campaign, since the outcome evidence (commit diff + `test_executed_success`) is objective and re-verifiable; a future campaign should use a distinct adjudicator for the adversarial standard.

### 14. Malformed or stale proposal accepted — **SAFE**

- **Attack:** did any invalid/stale proposal get recorded?
- **Evidence:** all 3 proposals were emitted via `emit_verify_proposal` → `validate_verify_proposal` (refuses `applied=true`, unknown action, bad schema, empty revision, negative depth). All record `applied=false`, schema `verify_code_change_proposal/v1`, contract `verify_code_change/v1`.
- **Result:** SAFE.

### 15. `applied` true or any actuation call — **SAFE**

- **Attack:** did anything actuate (apply a proposal / emit an actuation record / flip control_route)?
- **Evidence:** all 3 proposals `applied=false`. The bespoke specs declare no `control_route`/`cap_shadow`/`cap_snapshot` (grep: none). The 11 `source_type:actuation` kb artifacts are from a *different* pre-existing campaign (`repository_id self-wf_cap_shadow_campaign_anthropic_claude_sonnet_5`), not from any `cap_2a_rerun` cell. The proposal seam is AST-verified artifact-only (`tests/test_code_change_facts.py::test_proposal_seam_never_actuates_or_steers`).
- **Result:** SAFE.

### 16. Unclosed Neo4j driver — **SAFE**

- **Attack:** is the graph driver leaked?
- **Evidence:** `scripts/run_workflow.py:306-308` closes `graph_client` in a `finally` even when `run_workflow` raises.
- **Result:** SAFE.

### 17. Leaked credentials — **SAFE**

- **Attack:** do any committed artifacts/docs carry credentials?
- **Evidence:** grep for `password=`, `password123`, `sk-…`, `api_key=…` across `experiments/results/cap_2a_rerun/**`, the score JSON, and the verdict doc returns nothing. The single kb record that contains `password123` (`ca10ae4eb…`) is a pre-existing code-structure record of the *source signature* `password: str = "password123"`, not a captured secret.
- **Result:** SAFE.

### 18. p4 JSON hashes not matching the verdict citations — **SAFE**

- **Attack:** does any SHA256 cited in `docs/designs/current/cap_2a_rerun.md` disagree with the file on disk?
- **Evidence:** all six cited hashes re-computed and match exactly (score `59bd15d8…`, validation `690e0878…`, p2 outcome `1307c0ca…`, p2 ledger `ab0bf334…`, p3 manifest `2cf106b6…`, candidate manifest `62af69cd…`).
- **Result:** SAFE.

---

## Two genuine (accepted) limitations that shaped the result

1. **`new_sonar_critical_count` conflates severity.** The p1 mapping counts `bugs + vulnerabilities` (any severity, including `MAJOR` bug-type rules). p3b's `rework` was triggered by `python:S1244` ("do not compare floats with `==`", a *test*-style MAJOR finding), which is a bug-type issue but not a release-blocking defect. This is the root cause of the verifier's over-prediction. It is a documented `[P]` decision, so it is recorded (not silently rewritten); the fix — severity-filter `new_sonar_critical_count` to BLOCKER/CRITICAL, or count only issues *newly introduced by the change* — is a reducer-version change for the next campaign.
2. **Blast-radius metric compares "predicted impacted" to "realized rework set".** `abs(predicted_impacted_symbol_count − len(realized_symbol_set))` is applied verbatim from hard rule 15, but "impacted" (1-2 hop reachable set) and "rework-needed" are different quantities, so a `no_rework` outcome always yields `error = predicted_impacted`. Not a scoring error (the formula is the campaign's definition); noted for metric interpretation.

## Re-stated verdict (final)

2b gate **NOT met** — hit-rate 0/3 (Wilson [0.0, 0.5615], n=3 descriptive-only). The p1 fix is confirmed (`risk_mint_rate=1.0`); the campaign's measured result (verifier over-predicts) is real, not a scoring artifact, and its root cause (criticality conflation + MAJOR test-style findings) is identified. No artifact was falsified, no actuation occurred, no credential leaked.

**LOG:** 18 attacks re-verified: 16 SAFE, 2 accepted limitations (F1-doesn't-bite, single-agent adjudication) + 2 metric-interpretation notes (criticality conflation, blast-radius semantics). **PASS.**
