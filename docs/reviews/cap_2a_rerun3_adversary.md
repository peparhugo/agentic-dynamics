---
status: accepted
---

# cap_2a_rerun3 — adversarial verification

**Role:** adversarial verifier (p6). **Source revision:** `83b65e9f58e60991acbc5500f0d6688fa7c32fe5`.
**p4 score JSON:** `cap_2a_rerun3_score_20260826T050000Z.json` (SHA256 `08b6fb3297a5a41a3b81b4abc69b68cf86dde108918a244b4cf4fe6689a66a09`).
**p5 verdict:** `docs/designs/current/cap_2a_rerun3.md` (SHA256 `ae90187d6aaa6835253c063261eaed7be8235e44fbe2439b2ec538366331906d`).

## Findings table

| # | Attack (order) | Result | Disposition |
|---|---|---|---|
| F1 | (4) expected-effect next-phase facts were machine-local, not an immutable artifact | **FAIL** | **fixed** — committed `cap2a_r3_critical_gate_rework_analysis.json` (`e1245966…`) |
| F2 | (5) single-operator adjudication of outcome class | accepted | limitation (deterministic test_runner is independent; the `defect present`/`realized class` call is one operator) |
| F3 | (1)+(6) value direction depends on the escalation multiplier Eₓ | accepted | limitation (break-even Eₓ ≈ 1.42; Eₓ=28 is sourced) |
| F4 | (5)+(6) `continue` expected-effect claims are structurally unmeasurable | accepted | limitation (null gate leaves no next-phase facts) |

No finding falsified the campaign's core claim (the applied gate's rework is real and fixed the
defect). The four findings are provenance/limitation items, not falsifications.

---

## Attack-by-attack

### (1) The gate arm's application is real — **PASS** (after F3 caveat)

- **critical-gate (rework applied):** `git -C /tmp/cap2a_cell_critical_rerun3_gate log --oneline --all`
  shows `f451cfc (seed) → df14d9d (implement) → 33211ed (rework)`. The rework commit
  `33211ed769f948753e1d3a141fb890cdaaf35294` is a real commit: `calc.py | 2 +-` with the single
  diff `- if value > 10:` / `+ if value >= 10:`. **Not narrated — executed.**
- **clean-gate / style-gate (`continue` nulls):** both commit trails are exactly 2 commits
  (seed → implement); no rework/verify pass exists. `extra_passes=0` holds.
- **Re-test:** `python3 -c "import calc; print(calc.classify(10.0))"` in the gate worktree returns
  the correct `[10,20)` label; `python -m pytest test_calc.py -q` → `3 passed`.
- **Result: PASS.** The applied rework is provable in the commit trail; the `continue` cells are
  provable nulls.

### (2) The pairing is paired — **PASS**

- Every stimulus pair shares the same `spec_path_sha256`, `goal_sha256`, and
  `source_baseline_revision = 83b65e9f5…` (from the six committed cell manifests). The two arms
  differ only in `seeded_app_worktree` (`…/X_rerun3` vs `…/X_rerun3_gate`) and `finops_cell_id`.
- **Same seed:** the root-commit `calc.py` content is byte-identical across all 6 worktrees
  (SHA256 `b0b445d76049f150…`); `test_calc.py` likewise (`df8b167fd5d98a9f`). Seed *commit SHAs*
  differ only because each worktree is an independent git repo — the seeded *content* is identical.
- **No arm contamination:** each cell ran in its own fresh `/tmp` worktree; a baseline cell never
  consumed the gate arm's worktree. No cross-cell artifact copies observed.
- **Result: PASS.**

### (3) The value scoring is independent — **PASS** (subject to F2)

- The proposing agents are `deepseek/deepseek-v4-pro` opencode sessions (implement/verify/rework).
  The outcome evaluation is the **deterministic `runtime.test_runner`** (`run_suite`, pytest) plus
  deterministic inspection of the **immutable commits** (`git show`, direct `import calc`). No
  model narrative is used as an outcome input. `test_executed_success` in every outcome record
  comes from `run_suite`, not a self-report.
- **Result: PASS** — the evaluator is distinct from the proposing agents and its inputs are
  immutable commits; the residual single-operator judgment is recorded as F2.

### (4) Expected-effect checks use real next-phase facts — **FAIL → FIXED (F1)**

- The critical-gate rework's next-phase facts (`new_sonar_critical_count=0`,
  `new_lsp_error_count=0`, `code_change_risk=0.1`) were **measured** by re-running the
  `EvidenceChangeAnalyzer` (sonar + lsp + graph legs) on the rework commit vs the implement commit
  — not authored. However, that measurement lived only in `/tmp/cap2a_r3_critgate_rework_analysis.json`,
  outside the immutable artifact set.
- **Fix:** committed as `experiments/results/cap_2a_rerun3/cap2a_r3_critical_gate_rework_analysis.json`
  (schema `cap_2a_rework_analysis/v1`, SHA256 `e12459660240c2613d07063d3af8102768f154c9e15350d82bcab363bc14de14`),
  carrying the sonar + lsp evidence and the rework `change_analysis`. The p4 score JSON was NOT
  rewritten — its expected-effect results were already correct; this artifact is the provenance
  the check points to.
- **Re-test:** the committed artifact's `sonar_evidence.new_critical_count == 0` and
  `lsp_evidence.new_error_count == 0` match the p4 `expected_effects.per_gate_cell.cap2a_r3_critical_gate.checks[].observed`.

### (5) rerun2 limitations re-attacked

- **Novelty pre-existing branch:** rerun2's concern was that the S3776 CRITICAL might be a
  pre-existing finding. Here the seed is minimal (`add`/`subtract` only), so the `classify`
  S3776 is genuinely change-introduced; the `new_issue_count` reducer keys on `(rule, file, line)`
  identity. **FIXED by construction.** The S3776 persists on the rework commit (the rework fixed
  the *defect*, not the complexity finding) — recorded, not hidden (see outcome record).
- **Single-operator adjudication:** still present (F2). The deterministic test_runner is
  independent, but the `defect present` / `realized class` determination is one operator.
- **KB fact gaps:** cell facts were complete (0 omitted in every cell); the one gap — the rework
  analysis not being a durable artifact — is F1.

### (6) The usual suite

- **Wrong baselines:** each cell's `baseline_revision` is its seed commit, `analyzed_revision` its
  implement commit — full 40-char SHAs in every manifest. Correct.
- **Cherry-picked cells:** all 6 cells run, none dropped (`denominators.n_scored=6`,
  `n_invalid_join=0`, no `not-run` cells).
- **Denominators:** printed (`n_cells=6`, `n_pairs=3`, `n_accepted_baseline=2`, `n_accepted_gate=3`).
- **Stale sonar:** each revision is scanned under a revision-scoped project key; the rework scan
  (33211ed) is a distinct key from the implement scan (df14d9d) — no stale reuse.
- **Weight drift / treatment change:** `git diff 83b65e9f5… -- src/` is empty — `verify_proposal.py`,
  `evidence_analyzer.py`, `_risk_depth`, `VERIFY_RISK_THRESHOLD`, and the risk weights are
  code-unchanged.
- **applied=false in a gate cell:** none — gate cells are `applied` (critical) or `null`
  (clean/style); baseline cells are `not_applicable`.
- **Credentials:** no secret material in any committed `cap_2a_rerun3` artifact.
- **Unclosed drivers:** the `run_workflow.py` composition root closes the graph client in a
  `finally`; the p4 rework analysis closed its client. The only live processes are the campaign
  orchestrator (`run_workflow.py --spec cap_2a_rerun3.yaml --workdir /tmp/wt_cap_2a_rerun3`) and
  the current agent session — expected, not leaks.
- **Hash mismatches:** all 26 `input_artifacts` re-hash to their recorded SHA256 (0 mismatches);
  the verdict's cited numbers (`paired_value_delta[].delta_value_usd`, `asymmetric_loss.sum_*`,
  `expected_effects.aggregates.held_rate`, `cost_per_outcome.*`) match the p4 JSON exactly.

---

## F3 detail — the Eₓ sensitivity of the value direction

The critical paired delta is `Δ = Eₓ × rework_pass_cost − rework_premium = 28 × $0.004021 − $0.005719 = +$0.106869`.
The sign of Δ is Eₓ-dependent: break-even at `Eₓ ≈ $0.005719 / $0.004021 ≈ 1.42`. For any
`Eₓ < 1.42` the gate arm would be *worse* on the critical stimulus (it spends $0.005719 fixing a
defect worth less than that downstream). The verdict's positive direction therefore rests on the
sourced `Eₓ = 28` (site economics, DeepSeek → GPT-5.6); at the stated value the direction is
robust, but the magnitude scales linearly with Eₓ. Recorded as an accepted limitation with the
residual risk that the verdict's *direction* holds only for Eₓ ≳ 1.4.

## Re-stated verdict (unchanged)

Applying the verify_code_change gate improves value per dollar on the stimulus set, descriptively
(n = 3 pairs): positive paired Δ on all three stimuli, cost-per-accepted-outcome $0.012948 → $0.010492,
asymmetric-loss swing +$0.112588 → −$0.112588, and the critical-gate applied rework provably fixed
the defect (3/3) at a $0.005719 premium. Expected-effect held rate 0.25 (1/4). This authorizes
nothing; 2b remains eligible for design review only, and the value direction carries the Eₓ
sensitivity caveat (F3). **The campaign survives adversarial verification** with four
provenance/limitation findings, none falsifying.

**LOG:** findings F1 (fixed), F2–F4 (accepted limitations); known-safe list in
`docs/reviews/cap_2a_rerun3_known_safe.md`. **PASS** — findings re-verified against the tree and
committed artifacts; no bare PASS.
