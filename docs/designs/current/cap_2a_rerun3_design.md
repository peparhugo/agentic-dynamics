# cap_2a_rerun3 — design: the FIRST control experiment (the grid, not the fourth prediction study)

**Status: accepted** · Supersedes: `cap_2a_rerun2@0.1` (verdict `docs/designs/current/cap_2a_rerun2.md`)
· Predecessor data: `cap_2a_rerun2` score JSON (`cap_2a_rerun2_score_20260826T015846Z.json`) + the
registry findings (`cap_2a:cap_2a_rerun2`, `scripts/registry.py`)

## 1. Why this campaign exists (the review's conclusion, not a hunch)

The rerun2 deep review established three things:

1. **The prediction studies are done.** Three campaigns measured the action classifier
   (0 → refused → 0/3 → 2/3), fixed the measurement (severity-filtered, change-introduced
   counts), and produced the first calibration table. Continuing with more synthetic
   prediction cells would be the fourth prediction study — the wrong thing to measure.
2. **The verifier's predictions were validated against nothing but hit/miss.** The proposal's
   own `expected_effect` claims were never checked (now checkable:
   `validate_expected_effects`, `verify_proposal.py` — merged `4fa22047c`); the scope
   excluded the changed symbol (fixed structurally, `cc66efd30`); the blast-radius metric was
   a constant by construction.
3. **Control value was never measured.** `applied=false` by design — so the question the
   framework page actually promises ("does the gate improve value per dollar?") has no data.
   A prediction with no value measurement is a classifier, not a policy.

**This campaign is the grid the design always intended**: two arms on the same cells, the
policy actually applied in one arm, asymmetric losses, and outcome = cost-per-accepted-outcome
(value), not test-pass adjacency.

## 2. The experiment

### 2.1 Arms (the factor)

| Arm | The cell does | Applied? |
|---|---|---|
| **baseline** | Phase completes; the verifier's proposal is recorded (shadow) but NOT executed. The cell proceeds as today. | `applied=false` |
| **gate** | Phase completes; the verifier's proposal IS executed: `rework` triggers one bounded rework pass over the proposal's scope, `verify` triggers one verification pass (run the change's tests + a bounded review), `continue` changes nothing. | `applied=true` |

`arm` is the campaign's ONE varied factor (the "tweak one variable" of the campaign loop).
Everything else — cell spec, model, seed, worktree creation rules — is fixed across arms.

### 2.2 Cells

The three rerun2 variants (clean / critical / style) remain the stimulus set — they now serve a
different purpose: the SAME stimulus under two arms. Each cell runs twice (baseline arm + gate
arm) on fresh worktrees from the same recorded source revision. Cell count: 3 stimuli × 2 arms =
6 cells (per the E4 discipline, p2 measures ONE cell first and p3 scales with the measured cost).

### 2.3 The outcome metric — VALUE, not test-pass adjacency

The site's own KPI: **CostPerOutcome = total cost / accepted outcomes**, where for a change:

```
cell_value = −(cost_baseline_or_gate_run)
            + Δdurable_value(commit, next_inherited_state)
```

Δdurable_value is scored by an INDEPENDENT post-hoc evaluator on the immutable commits:

| component | measured how | direction |
|---|---|---|
| verification surface | tests authored/executed on the final commit (test_runner) | more is better |
| static quality | sonar/lsp on the final commit (severity-filtered counts) | fewer criticals is better |
| rework cost | rework/verify passes actually executed in the gate arm | fewer wasted passes is better |
| defect presence | the critical cell's defect present on the final commit? (post-hoc evaluator) | absent is better |

The **arm comparison**: per stimulus, `gate_value − baseline_value` (Δ). The verdict question:
does applying the gate improve value per dollar on the stimulus set, and at what asymmetric
cost? This is a paired comparison (same stimulus, two arms), n=3 pairs — descriptive-only,
exactly like the prediction studies; it is the FIRST value measurement, not the last.

### 2.4 Asymmetric loss (the framework page's own economics, applied)

The scoring ALSO reports the misprediction cost table per cell — the thing the symmetric
hit-rate never saw:

```
false_continue_cost  = Eₔ × (cost of the defect's downstream consequences)   # Eₔ ≈ 28× (site)
false_rework_cost    = one wasted rework/verify pass (measured in the gate arm)
true_rework_value    = defect fixed before it propagated (measured Δ)
```

The verdict reports `Σ asymmetric loss (gate) vs Σ asymmetric loss (baseline)` — the number the
hit-rate could never produce.

### 2.5 Expected-effect checks (the proposal's own falsification, finally used)

Every gate-arm cell validates its proposal's `expected_effect` against the NEXT phase's facts
via `validate_expected_effects` (merged helper): `continue` → risk unchanged, `verify` → lsp
errors decrease. For the gate arm, `rework`'s effects ("critical count decreases") ARE
checkable — rework was applied, so the next phase's facts are the applied outcome. The
expected-effect check rate + held rate is a third verdict column (prediction quality measured
on its own claims).

### 2.6 What is NOT in this campaign

- NOT reweighting risk or re-fitting `_risk_depth` (the unfitted ramp stays unfitted — this
  campaign measures the CURRENT v1 mapping under application; the fitted mapping remains the
  rerun2 verdict's deliverable).
- NOT changing `build_verify_proposal` (the treatment is code-unchanged; the scope fix
  `cc66efd30` is a measurement correction already merged, not a treatment change).
- NOT running 2b (randomized, pre-registered, larger n — the design is unchanged and this
  campaign's paired Δ is its feasibility probe).

## 3. Phases (work order)

- **p1_measure_baseline_cell** — E4: run the `clean` stimulus in the baseline arm (shadow,
  applied=false), measure cost/duration/facts, emit the candidate manifest FIRST, set the p3
  forecast budget. Proposals must emit (a refusal here is a regression — fail the phase).
- **p2_measure_gate_cell** — E4: run the `clean` stimulus in the gate arm (applied=true: the
  proposal IS executed — `continue` changes nothing, so this is the null gate). Measures the
  gate arm's overhead (proposal recording + any verify pass) and validates the expected-effect
  check on the next phase.
- **p3_run_remaining_cells** — the critical + style stimuli × both arms (4 cells) from the p2
  candidate manifest; fresh worktrees, unique FINOPS_CELL_IDs, proposals recorded before
  outcomes, independent outcomes (test_runner + post-hoc evaluator on the immutable commits),
  flagged cells never dropped. The critical-gate cell is the money cell: does the applied
  `rework` fix the defect and at what cost vs baseline?
- **p4_score_value** — paired Δ per stimulus: `gate_value − baseline_value`, asymmetric loss
  table (false-continue/false-rework costs), expected-effect check rate, per-cell rows + the
  aggregates, all citing artifact SHA256s. The score JSON schema: `cap_2a_rerun3_score/v1`.
- **p5_verdict** — `docs/designs/current/cap_2a_rerun3.md`: the paired table, the Δ direction
  per stimulus, the asymmetric-loss comparison, the expected-effect held rate, and the
  eligibility statement for 2b (the randomized design — this is its feasibility probe, and the
  n it needs). Descriptive-only; no gate-clearing claim at n=3 pairs.
- **p6_adversarial** — attack in order: (1) the gate arm's rework actually executed
  (applied=true provable in the ledger/commit trail, never narrated); (2) the paired
  comparison is paired (same stimulus, same seed, fresh worktrees, no cross-contamination);
  (3) the value scoring is independent (post-hoc evaluator ≠ the proposing agent); (4) the
  expected-effect checks are computed from real next-phase facts; (5) the rerun2 limitations
  re-attacked (novelty pre-existing branch, single-operator adjudication, KB gaps); (6) the
  usual suite (baselines, denominators, credentials, hashes, actuation-only-in-gate-arm).

## 4. Acceptance criteria ("working")

1. Every gate-arm cell's proposal is provably applied or provably null (`continue`) — the
   ledger/commit trail shows it; p6 verifies.
2. The critical-gate cell's defect is fixed or unfixed on the final commit (post-hoc
   evaluator) — the rework leg has its first APPLIED data point.
3. The paired Δ table exists with all six cells' rows.
4. The asymmetric-loss table exists with Eₔ sourced and stated.
5. Expected-effect check rate ≥ the proposal count (every proposal's claims checked).
6. No gate-clearing claim; the verdict states the n the 2b feasibility probe implies.

## 5. Data lineage

Cells: `cap_2a_cell_clean/critical/style@0.1` (rerun2, unchanged — the stimulus set).
Measurement: the merged fixes (scope `cc66efd30`, expected-effects `4fa22047c`, severity
`0e24d6985`). Prior rows: the rerun2 registry findings (`cap_2a:cap_2a_rerun2`, 4 records) —
the rerun3 score JSON will carry the same campaign-evidence ingestion.
