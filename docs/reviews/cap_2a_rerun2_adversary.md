# cap_2a_rerun2 — adversarial review

**Reviewed commit:** `5d8ad4841` (p5 verdict; the campaign HEAD). Attacks run in the design-doc §4 p6 order. Evidence is a path/line + a live probe where a claim about the instrument is involved. Every finding is either fixed here or recorded as an accepted limitation with residual risk.

## Attack 1 — severity conflation REGRESSED?

**Attack:** a cell whose only sonar finding is a MAJOR (e.g. `python:S1244`) must mint `new_sonar_critical_count=0` and must never produce a `rework` proposal.

**Evidence:**
- `experiments/results/cap_2a_rerun2/cap_2a_rerun2_score_20260826T015846Z.json` → `cells[]` row `cap2a_p3_style`: `new_sonar_critical_count=0`, `proposal_action=continue`.
- Live probe (server `127.0.0.1:9000`, project `exp_cap2a_cell_style_rerun2_9b5f39e75b2c`): `api/issues/search` (all severities) returns 5× `python:S1244` MAJOR (`calc.py:18/20/22`, `test_calc.py:13/14`); with `severities=BLOCKER,CRITICAL` it returns **0**.
- Reducer wiring: `src/agentic_dynamics/runtime/workflow_runner.py:392-394` fetches both revisions with `severities="BLOCKER,CRITICAL"` then `new_issue_count(before, after)`.

**Result: NOT regressed.** The style cell (5 MAJOR findings) mints 0 and continues — the rerun's p3b minted 1 for the identical `python:S1244` finding and proposed rework. This is a **verified safe** attack, not an accepted limitation: the fix is live data, not prose.

## Attack 2 — novelty rule bypassed?

**Attack:** is a pre-existing BLOCKER in an untouched file counted as new, or the `(rule,file,line)` before/after identity misapplied?

**Evidence:**
- The three before-revision (seed) projects were freshly scanned by the seam's parent leg. Live probe: `api/issues/search?severities=BLOCKER,CRITICAL` on `exp_cap2a_cell_{clean,critical,style}_rerun2_<seed12>` returns **0** for all three — the seeds carry no BLOCKER/CRITICAL, so the critical cell's `new_sonar_critical_count=1` is exactly the one change-introduced `python:S3776` (`calc.py:9`), not a pre-existing issue.
- Identity rule: `src/agentic_dynamics/measurement/sonar.py` `issue_identity` = `(rule, file_path, line)` (`:511`), `new_issue_count` = `|identity(after) − identity(before)|` (`:528`). `file_path` is repo-relative (`component.split(":",1)[1]`), so identities are comparable across the two revision-scoped project keys.

**Result: NOT bypassed — with one recorded gap (accepted limitation).** The live cells never carry a *pre-existing* BLOCKER (the seeds are intentionally clean add/subtract), so the "pre-existing excluded" branch of the novelty rule is covered by the hermetic unit tests (`tests/test_sonar.py::test_new_issue_count_pre_existing_blocker_counts_zero`, `test_new_issue_count_mixed_pre_existing_and_introduced`) but not by a live cell. **Accepted limitation**, residual risk low: the identity diff is a pure set-difference over `(rule,file,line)`, unit-tested in both directions.

## Attack 3 — calibration-table provenance

**Attack:** every calibration row must trace to a p4 JSON field, and the fitted-mapping statement must be derivable from the table.

**Evidence:**
- p4 `calibration.per_cell_rows[]` maps 1:1 to `cells[]` (same `cell_id`, `action`, `depth`, `code_change_risk`, `new_sonar_critical_count`, `realized_outcome`, `realized_depth`, `hit`).
- `calibration.risk_buckets` and `calibration.finding_outcome` are aggregates over `cells[]`; `calibration.severity_strictness` lists the live-probed rule/severity/file/line sets (Attack 1's probe).
- p5 `docs/designs/current/cap_2a_rerun2.md` fitted-mapping items 1–4 each cite a `calibration` field (`finding_outcome`, `severity_strictness`, `risk_buckets`, and the scope miss read off `cells[cap2a_p3_critical].proposal_scope` vs `.realized_symbol_set`).

**Result: traceable.** `p4_validation.json` `verdict_number_to_field` maps each aggregate to its source field. **Verified safe.**

## Attack 4 — rerun's carried limitations re-attacked

**(a) Duplicate qualified names in the CALLS edge.** Not exercised here: `classify`/`rate_for`/`product` are pure functions with no intra-package calls, so no CALLS edge is minted for the changed symbols (the neighborhoods come from module CONTAINS + TESTED_BY edges only). **Residual risk unchanged**, not newly triggered.

**(b) Single-agent adjudication.** The realized outcome is not the model's narrative: it is derivable from the immutable implement commit + the independent `runtime.test_runner` verdict + the post-hoc evaluator. Critical cell: the committed `classify` uses `elif value > 10 and value < 20` (a live code inspection shows `classify(10.0) == 'twenties'` against the documented `[10,20) → 'teens'` contract), and `test_executed_success=False` (2/3) is the independent runner's verdict → `targeted_rework` is a derivable fact, not an assertion. **Accepted limitation** (adjudication is procedural, single-operator), residual risk: a second independent adjudicator was not run.

**(c) Canonical KB facts absent on killed runs.** The critical cell's run ended `ok=False` (the deliberate test failure stops the workflow at the test phase), and `--no-fact-emit` was passed for all three calibration cells, so **no** ledger facts were ingested to the KB for any cell (the spec lifecycle records were still emitted — `spec:cap_2a_cell_{clean,critical,style}` upserts are committed under `experiments/results/kb/`). The campaign's scoring is grounded in the committed ledger/outcome/proposal artifacts, not the KB, so the score is unaffected. **Accepted limitation** (recorded deviation from the rerun, which ran fact-emit on), residual risk: the calibration cells contribute no `ledger_attempt` KB facts to the canonical corpus.

## Attack 5 — the usual suite

| Attack | Evidence (path/line) | Result |
|---|---|---|
| Wrong baselines | proposals + outcomes agree on `baseline_revision` = seed (`00193d8b…` clean, `6c871900…` critical/style); `p4_validation.json` `join_validation.errors=[]` | safe |
| Cherry-picked cells | exactly 3 cells ran — one per design-doc §RC5 class (clean/critical/style); `n_not_run=0`, `n_unknown_outcome=0` | safe |
| Proposals recorded but never validated | `proposal_validation_rate=1.0`; all 3 artifacts `applied=false`, schema `verify_code_change_proposal/v1` | safe |
| Graph/analyzer-down dropped or mislabeled | `graph_unavailable_rate=0.0`; graph/sonar/lsp all `available` on all 3 cells | safe |
| Stale sonar facts (analyzed_sha mismatch) | `analysis_revision_matches=true` on every scored row; project key embeds `rev[:12]` (`sonar.py::project_key_for`) | safe |
| Risk weights drifted from [P] provenance | `code_change_facts.py:117` `RISK_WEIGHTS = (0.35, 0.25, 0.20, 0.20)` — unchanged | safe |
| Denominator games | `n_scored=3` = `n_hits(2)` + misses(1); `n_unknown=0`, `n_invalid=0`, `n_not_run=0` printed | safe |
| p1 byte-identical claim falsifiable by diff | `workflow_runner.py:962` — `_run_change_analysis` runs only when `change_analyzer is not None` (i.e. `--change-analysis`); `scripts/run_workflow.py` change is a help-text string only | safe |
| applied=true / any actuation | all `applied=false`; `verify_proposal.py` untouched since `e61c709eb` (pre-campaign); no `control_route`/`actuation` | safe |
| Unclosed drivers | graph client closed in `scripts/run_workflow.py:305-308` `finally`; sonar/lsp legs under `ANALYZER_LEG_TIMEOUT_SECONDS=360` with worker-pool `shutdown` | safe |
| Leaked credentials | no credential in any campaign artifact; the only `admin`/`password` string is the design doc documenting the local server's default scanner creds (already `SONAR_USER/PASSWORD_DEFAULT` in `sonar.py`) | safe |
| p4 hashes not matching verdict citations | `cap_2a_rerun2_score_…json` → `ef42f8b0…` and `p4_validation.json` → `a2fd71fd…`, both match `docs/designs/current/cap_2a_rerun2.md` | safe |

## Re-stated verdict (after attack)

Hit-rate **2/3 = 0.6667** (Wilson 95% `[0.2077, 0.9385]`), `risk_mint_rate=1.0`, no graph/analyzer-down, no invalid/unknown/not-run cells. The severity-conflation fix **survives adversarial re-attack** (Attack 1: 5 MAJOR findings → count 0, no rework). The novelty identity rule is correctly applied (Attack 2). The two residual defects are **measured and named**, not hidden: (i) the rework scope is the executor neighborhood and excludes the changed symbol `{classify}`, so the one rework cell is a scope miss (fitted-mapping item 4 — prescription for the next campaign, not a code fix this campaign); (ii) the risk→depth ramp remains unfitted (n=3, all in `[0.15,0.3)`, no `verification_only` realized). **2b gate: descriptively met (0.667 ≥ 0.6), not a statistical clearance (n=3, interval straddles 0.6).**

**LOG — findings:** 0 FAILED; 3 accepted limitations (live novelty "pre-existing" branch untested; single-operator adjudication; `--no-fact-emit` KB gap) + 2 measured residual defects carried into the next campaign (scope miss; unfitted risk→depth ramp). **PASS.**
