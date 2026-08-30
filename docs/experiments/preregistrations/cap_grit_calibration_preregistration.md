---
status: accepted
---

# cap_grit_calibration — pre-registration: full strength-response curves + independent outcome calibration + held-out policy thresholds

**Status: accepted · PRE-REGISTERED — committed BEFORE any cell runs.**
**Campaign:** `cap_grit_calibration` (the spec `workflows/repository/cap_grit_calibration.yaml`
is authored as the next artifact; its SHA256 is appended to this header on that commit).
**Design authority:** `docs/experiments/designs/cap_grit_confidence_calibration_design.md`
(accepted 2026-08-28 — moved from proposed on the operator's acceptance with this
preregistration). **Predecessors:** the E4 grid (the measured G(s) curve, the overrun lesson —
sonnet story attempts $3.07–4.13, the flash-scaled estimate ~10× wrong), the 2c/2d/2e abstention
arc (the confidence-null on the DECLINE decision; the retry-threshold is a DIFFERENT decision).
**Cell model (primary envelope):** `deepseek/deepseek-v4-pro` (opencode); **cross-envelope
tranche:** `anthropic/claude-sonnet-5` (claude_cli, its own budget ceiling). **Stimulus:** the
E4 machinery unchanged — `task_manager_api` story (5 sessions), fresh worktree per cell, unique
`FINOPS_CELL_ID`, `enforce_pytest=True`.

## 0. The pinned machinery (verbatim from the design — nothing re-derived)

- **The response axis:** `condition_strength` s ∈ {0.0, 0.2, 0.4, 0.6} (training) ∪
  {0.3, 0.5, 0.7} (held-out — **a fixed design axis, interleaved strengths, never randomized,
  never re-negotiated after the fit**). Mechanical distinctness: s ∈ {0.2, 0.4, 0.6, 0.7} via
  verified `inject_bug` artifacts compiled per cell (`compile_mutation(spec, "inject_bug",
  strength=s)`, load-checked); s=0.5 via the standard on-disk `bad` variant
  (`CONDITION_STRENGTH=0.5`); s=0.0 clean; s=0.3/0.7 via the same artifact seam.
- **The arms:** `baseline` (max_attempts=1) · `grit_retry` (retry iff first
  `test_executed_success == false`, max_attempts=2) on ALL training cells · `grit_retry@θ*`
  (retry iff first failed AND the attempt's [H] confidence ≥ θ*) on ALL held-out cells —
  θ* ∈ {0.4, 0.6, 0.8} pre-registered, selected on the TRAINING cells only (argmin of
  cpvo_harm; tie-break by verified success rate; θ=0/θ=1 read off the training grid's
  unconditional/never-retry arms as the bounds). **A live arm on held-out cells** — retry
  counterfactuals are not estimable shadow-style (the cap_confidence_cascade tautology
  lesson); θ* executes on the cells it is evaluated on.
- **The [H] confidence field:** every attempt row carries the measured per-attempt
  execution-confidence (opencode.py:113) — E4's `build_attempt_row` omitted it; a row without
  it is flagged, never imputed, excluded from the calibration bins with the count reported
  (the 2c §7 requirement extended to the grit ledger).
- **The harm model:** escaped-defect harm = E_x × $0.004021 = **$0.046109 @11.47 /
  $0.112588 @28** (escalation score JSON `loss_table`, the E_x machinery reused verbatim);
  retry cost = the measured attempt-2 `actual_cost` + any `rework_cost` (measured — E4's
  rework axis was constant-zero; recorded honestly, never assumed).
- **The retry's value condition:** `P(success | failure, s, c) × value(success) >
  cost(attempt 2)` — every component measured (posterior from the live retry arms, cost from
  the ledger, harm from the E_x loss table).

## 1. The grid — 84 cells (48 training + 36 held-out)

**Committed seed (hex):** `6b7df859b2f1a727de745051d88fac1268e2a268ae1522ac4aefdcbd13ef4bce`
(derived as `sha256("cap_grit_calibration|train{0.0,0.2,0.4,0.6}-heldout{0.3,0.5,0.7}|baseline-grit_retry-theta|20260828")`).

**The canonical assignment table (generated, deterministic from the seed — the generator IS
the table):**

```python
import hashlib, random
random.seed(hashlib.sha256(b"cap_grit_calibration|train{0.0,0.2,0.4,0.6}-heldout{0.3,0.5,0.7}|baseline-grit_retry-theta|20260828").hexdigest())
models = ["deepseek-v4-pro", "claude-sonnet-5"]
for m in models:
    for s in (0.0, 0.2, 0.4, 0.6):                      # training
        arms = ["baseline"] * 3 + ["grit_retry"] * 3
        random.shuffle(arms)
        for rep, arm in enumerate(arms, 1):
            yield f"grit_{m}_s{s}_train_{arm}_r{rep}"
    for s in (0.3, 0.5, 0.7):                           # held-out
        arms = ["baseline"] * 3 + ["grit_retry@theta*"] * 3
        random.shuffle(arms)
        for rep, arm in enumerate(arms, 1):
            yield f"grit_{m}_s{s}_heldout_{arm}_r{rep}"
```

**Arm totals (the canonical count):** training 48 = per (model × strength) block 3×baseline +
3×grit_retry; held-out 36 = per (model × strength) block 3×baseline + 3×grit_retry@θ*;
total **84 = 42 baseline + 24 grit_retry + 18 grit_retry@θ***. **E1** (the first cell by
generator order) = `grit_deepseek-v4-pro_s0.0_train_grit_retry_r1` — the p1 probe also fixes
the budget (below). Arm labels come from this committed generator + seed, never from the
model's choice and never post-hoc; the training/held-out split is the design axis, never the
randomization.

## 2. The decision rule (pre-registered — per model, on the HELD-OUT cells)

**Primary:** `cpvo_harm(arm) = (Σ cost + Σ harm) / Σ accepted` at E_x = 11.4671 (sensitivity
at 28), accepted = `test_executed_success == true` on the final commit (independent
`runtime.test_runner`), cost = measured ledgered actual cost, harm = escaped defects ×
$0.046109 @11.47.

**SUPPORT ⟺ all of, per model, on the held-out cells:**

| leg | requirement |
|---|---|
| **A — held-out threshold win** | `cpvo_harm(grit_retry@θ*) < cpvo_harm(baseline)` @11.47 |
| **B — non-flat response curve** | measured G(s) over the full 7-strength axis (pooled, n ≥ 3 per strength) has range > 0.15 between any two strengths |
| **C — calibration estimable + predictive** | P(test_executed_success \| confidence bin) over the pooled attempt ledger (bins over the recorded [H] confidence, n ≥ 5 per bin) is defined and monotone non-decreasing |
| **D — fidelity + coverage** | retry fidelity 0 violations (retry never fires on a passed attempt; baseline never retries); cost + test-verification coverage = 1.0 on both axes |

**The abstention re-check (EXPLORATORY, not a decision leg):** re-reports the 2c/2d abstention
curve over the new confidence distribution and asserts the confidence-free constraint on the
DECLINE decision — never fixes a threshold on it, never lets θ* touch it (the 2d prereg §1
pattern).

**Pre-registered contingency:** if the deepseek p1 probe exceeds the envelope (below), the
contraction drops repetitions 3→2 (84 → 56 cells: 32 train + 24 held-out) — arms, strengths,
and the threshold rule are never re-opened. A cell stopped by the SLA guard is reported in its
denominator, never dropped.

## 3. The budget (the E4 overrun lesson — probes fix the ceilings, never scaled estimates)

- **p1 probes:** ONE story attempt per model on the anchor strengths (s=0.0 and s=0.4),
  measured BEFORE the grid — the budget's only input. The pre-registered ceilings:
  - **Primary envelope (deepseek-v4-pro):** 84 cells within the $30 stop
    (`stop.budget_usd`, the 2b–2e pattern). If the probe ≈ $0.05–0.15/attempt (deepseek story
    scale), 84 × (probe × ≤2 attempts) fits; if higher → the §2 contraction to 56 cells.
  - **Cross-envelope tranche (sonnet-5):** parallel on the anthropic envelope with its OWN
    ceiling computed at p0 as `12 cells × probe × 2 attempts` (the 2 models... the tranche's
    36 held-out cells at r=3; if the sonnet probe holds at the E4-measured $3.07–4.13/story,
    the tranche's ceiling is derived at p0 and the tranche contracts to r=1 (12 cells) if
    needed — a separate envelope budget, never shared with the deepseek stop (the 2d §6
    parallel-vehicles precedent: separate rate limits, data chain single-writer).
- **Run shape:** 4-wide concurrency on the deepseek envelope; the sonnet tranche on the
  anthropic envelope concurrently (claude_cli backend, the E4 machinery). The wrapper
  phases (p0–p5) are flash sessions; the data chain stays single-writer.

## 4. The analysis plan

p1 (probes + E1) → p2 (grid, 4-wide; sonnet tranche parallel) → p3 (score: per-model G(s)
curves with Wilson intervals per strength, the calibration curve, θ* selection on training +
evaluation on held-out, cpvo_harm per arm, the four decision-rule legs, the abstention
re-check, fidelity/coverage guards) → p4 (verdict doc
`docs/experiments/results/cap_grit_calibration.md` — SUPPORT/REFUTE per §2 with each leg's n + CI)
→ p5 (adversarial: θ* re-selection from the training cells only, the curve arithmetic
re-derived from the recorded facts, the fidelity guards re-checked in the commit trails).
Output: `experiments/results/cap_grit_calibration/cap_grit_calibration_score_<ts>.json`
(schema `cap_grit_calibration_score/v1`) + a validation JSON tracing every verdict number.
The attempt ledger extends `experiments/results/cap_grit_grid_ledger.json` (the E4 ledger —
ADDITIVE: the confidence field + the strength/arm columns; never rename existing keys).

## 5. Authorization boundary

The accepted design + this preregistration authorize: the p1 probes, the 84-cell grid (or the
§2 contraction), the θ* selection on training + the live θ* arm on held-out, the budget
ceilings above, and the wrapper phases. NOT authorized: any change to the verify gate /
abstention rule (shadow-only stays), any threshold fitted on the 2c/2d confidence
distribution, any production activation, or re-opening the 2d/2e verdicts. The data chain
stays single-writer; the deepseek envelope is owned by this campaign until its verdict.

## Guard

Every number derives from the cited artifacts (the design doc's E4/G(s)/cost citations, the
escalation `loss_table`, the 2d/2e score JSONs) or the arithmetic above. The seed, the
generator table, the arms, the decision rule, and the budget ceilings are fixed here; the spec
SHA256 is appended on the spec commit; no cell runs before this document is on main.

**LOG:** the design's grid/arms/decision rule restated as the committed preregistration; the
seed `6b7df859…` + the deterministic generator table (84 = 42 baseline + 24 grit_retry + 18
grit_retry@θ*); the four-leg decision rule (held-out win / non-flat curve / estimable+monotone
calibration / fidelity+coverage) per model; the E4-driven budget (p1 probes fix the ceilings;
the 84→56 contraction; the sonnet tranche's own ceiling); the abstention re-check marked
EXPLORATORY; the analysis plan p1–p5; the authorization boundary. **PASS — committing before
any cell runs.**
