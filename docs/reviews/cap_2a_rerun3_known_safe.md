# cap_2a_rerun3 — known-safe list (non-falsifying attacks, with evidence)

Every attack below was attempted and did NOT falsify the campaign. Each entry records what was
tried, the artifact/tree evidence, and why the result is safe. This is not a generic checklist —
each line is a specific attack with a specific answer.

## 1. The critical-gate rework is a real, applied change (not narrated)

- **Tried:** read the gate worktree's full commit trail and the rework commit's diff.
- **Evidence:** `git -C /tmp/cap2a_cell_critical_rerun3_gate log --oneline --all` =
  `f451cfc → df14d9d → 33211ed`; `git show 33211ed` = `calc.py | 2 +-` with only
  `- if value > 10:` / `+ if value >= 10:`.
- **Why safe:** the applied rework is a single real commit with the exact one-line boundary fix; no
  narration is substituted for execution.

## 2. The `continue` gate cells are provable nulls (no hidden extra passes)

- **Tried:** enumerate every commit in the clean-gate and style-gate worktrees.
- **Evidence:** both are exactly `seed → implement` (2 commits); the verify phase produced no diff
  (`change_analysis=None`, empty `commit_hash` in the run ledgers).
- **Why safe:** there is no rework/verify-pass commit to hide; `extra_passes=0`.

## 3. The pairing is a true paired comparison (same stimulus, same source, fresh worktrees)

- **Tried:** diff the six cell manifests' `spec_path_sha256`, `goal_sha256`, and
  `source_baseline_revision`; hash the seed content in every worktree.
- **Evidence:** each stimulus pair shares identical `spec_path_sha256`/`goal_sha256`/
  `source_baseline_revision=83b65e9f5…`; root-commit `calc.py` is byte-identical across all 6
  worktrees (`b0b445d76049f150…`) and `test_calc.py` too (`df8b167fd5d98a9f`); the two arms use
  distinct `/tmp/…_rerun3[_gate]` worktrees and `FINOPS_CELL_ID`s.
- **Why safe:** no arm shares a worktree or consumes the other's work.

## 4. No arm contamination / cross-cell artifacts

- **Tried:** look for any baseline artifact referencing the gate arm's worktree or rework commit.
- **Evidence:** baseline outcome records reference only their own seed + implement revisions; the
  gate's rework commit `33211ed` appears only in the critical-gate artifacts.
- **Why safe:** the cells are hermetic by construction (fresh worktrees, `self-<cell_id>` scopes).

## 5. The value scoring is independent (deterministic evaluator, immutable inputs)

- **Tried:** confirm the outcome inputs are not model narratives.
- **Evidence:** every `test_executed_success` comes from `runtime.test_runner.run_suite` (pytest);
  defect presence was verified by running `import calc; calc.classify(10.0)` against the committed
  revision, and by `git show <rev>:calc.py`.
- **Why safe:** the evaluator is deterministic code, distinct from the proposing LLM sessions, over
  immutable commits.

## 6. No hash mismatch between the p4 JSONs and the verdict citations

- **Tried:** re-hash all 26 `input_artifacts` and the three candidate manifests against the score
  JSON's recorded values; recompute the verdict-file SHA.
- **Evidence:** 0 mismatches across 26 artifacts; candidate-manifest hashes match; the verdict's
  cited `paired_value_delta[].delta_value_usd` (`+$0.000059`/`+$0.106869`/`+$0.000078`),
  `asymmetric_loss.sum_baseline/usd_gate` (`+$0.112588`/`−$0.112588`), `held_rate` (`0.25`),
  and `cost_per_outcome.*` (`$0.012948`/`$0.010492`) all match the p4 JSON fields exactly.
- **Why safe:** no number in the verdict is unbacked or drifted.

## 7. The treatment is code-unchanged (no weight drift)

- **Tried:** `git diff 83b65e9f5… -- src/` and a targeted diff of `verify_proposal.py`,
  `evidence_analyzer.py`, `workflow_runner.py`.
- **Evidence:** empty diff — `build_verify_proposal`, `_risk_depth`, `VERIFY_RISK_THRESHOLD`, the
  risk weights, and the scope seed are untouched by this campaign.
- **Why safe:** the measured value difference is the arm treatment, not a code change.

## 8. No severity-conflation regression (the MAJOR-only style stimulus)

- **Tried:** confirm the style stimulus (float `==`, S1244 MAJOR) mints `new_sonar_critical_count=0`.
- **Evidence:** both style cells' `facts.new_sonar_critical_count="0"`; proposals `continue`.
- **Why safe:** the severity filter (`BLOCKER,CRITICAL` only) still excludes the MAJOR finding.

## 9. The scope fix is present in the data (rework leg is hittable)

- **Tried:** check the critical proposals' scope contains the changed symbol.
- **Evidence:** both critical proposals' scope is `[add, classify, subtract, test_add, test_classify,
  test_subtract]` — `classify` is present (rerun2's miss resolved by `cc66efd30`).
- **Why safe:** the rework leg that failed in rerun2 is now structurally hittable, and it fired.

## 10. No credentials in committed artifacts

- **Tried:** grep the committed `cap_2a_rerun3` artifacts for key/secret/token/private-key material.
- **Evidence:** no matches.
- **Why safe:** nothing secret was committed.

## 11. No stale-sonar reuse

- **Tried:** confirm the rework analysis scanned a distinct revision key from the implement scan.
- **Evidence:** sonar projects are revision-scoped (`project_key_for(wd, revision)`); the rework
  scan (`33211ed`) is a different key from the implement scan (`df14d9d`), and the rework evidence
  records `analyzed_sha=33211ed…`.
- **Why safe:** the expected-effect check compares distinct, fresh scans.

## 12. No wrong baseline (seed content is the true pre-change state)

- **Tried:** inspect the root commit of each worktree.
- **Evidence:** every root commit is `calc.py` (add/subtract) + `test_calc.py` (test_add/test_subtract),
  byte-identical across worktrees; no cell starts from a prior cell's output.
- **Why safe:** the "before" snapshot for every change is the minimal seed, so every
  `new_sonar_critical_count` is genuinely change-introduced.

## 13. The empty `[workflow] pN` commits from the orchestrator are harmless

- **Tried:** inspect the interleaved empty commit `2ec2baffd` (`[workflow] p3_run_remaining_cells`).
- **Evidence:** it is a 0-insertion/0-deletion commit authored by the campaign orchestrator
  (`run_workflow.py --spec workflows/repository/cap_2a_rerun3.yaml --workdir /tmp/wt_cap_2a_rerun3`,
  visible as a live process) after the phase agent already committed its artifacts.
- **Why safe:** the commit changes no file, carries no secret, and cannot alter any artifact hash.
