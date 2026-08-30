---
status: accepted
---

# workflow_metrics — adversarial verification

**Role:** adversarial verifier (p4). **Source revision:** `workflows/repository/workflow_metrics.yaml`
SHA256 `2cd4bb1105c915f3b9ae5e4e835c4277eddb6ba6da58ac7b7d8efd31498768d1`. **Findings:**
`docs/reviews/workflow_metrics_findings.md`. **Aggregator:** `scripts/aggregate_workflow_metrics.py`
(+ `tests/test_aggregate_workflow_metrics.py`, 18 passing).

## Findings table

| # | Attack (order) | Result | Disposition |
|---|---|---|---|
| F1 | (1) metric definitions — pinned §3 applied exactly | **PASS** | no finding; the 8 definitions are byte-verbatim in `PINNED_METRIC_DEFINITIONS` |
| F2 | (2) arithmetic — re-derive r, WOC, escalation, checkpoint latency | **PASS** | no finding; r=0.125 and cost-per-accepted=$27.715817 recompute; WOC/escalation/checkpoint are field-absent, not 0 |
| F3 | (3) measured-not-estimated rule | **PASS** | no finding; every figure traces to a ledger field or is reported `not_measurable` |
| F4 | (4) coverage — complete-ledger table exact | **PASS** | no finding; 118 referenced / 0 present / 118 absent recomputed |
| F5 | (5) citations — every finding resolves to its rows | **PASS** | no finding; each number re-derived from the named ledger |
| F6 | (6) WFM scoping — implications derive from measured metrics | **PASS** | no finding; T_max/batch/escalation are scoped to what is (and is not) measured |

No attack falsified a claim. The findings' one load-bearing conclusion — the instrument is
correct, the data is absent — is *strengthened* by every attack, not weakened.

---

## Attack-by-attack

### (1) Metric definitions — pinned §3 applied exactly — **PASS**

Diffed `PINNED_METRIC_DEFINITIONS` (the eight keys + their strings) against hard-rule §3 of the
spec. The eight definitions are byte-for-byte the spec's wording; the computation functions
(`compute_retry_rate` … `compute_sla_behavior`) implement the §3 formula, not a paraphrase. The
guard `test_pinned_definitions_cover_all_eight_metrics` asserts the key set is exactly the eight
and that every metric has a registered computer. No deviation.

### (2) Arithmetic — re-derive from raw ledger fields — **PASS**

Re-derived `r` and cost-per-accepted for `cap_grit_strength_grid` from
`experiments/results/cap_grit_grid_ledger.json`:

- 8 cells, 9 attempts. One cell (`…bad_seed_high_policy_arm_grit_retry…`) carries 2 attempts —
  attempt 1 (`retry_reason=""`) and attempt 2 (`retry_reason="first_attempt_test_failure"`).
  **r = 1/8 = 0.125** — matches `aggregate.json`.
- Accepted cells: 7, `realized_cost` = `[3.100918, 3.45629, 3.27221, 3.867819, 4.129614, 3.069419,
  6.819547]` → **sum = 27.715817**, mean $3.9594 — matches.
- WOC: `first_pass` is declared-not-written (`control/checkpoint.py:85`); no ledger field carries
  it → the aggregator reports `not_measurable`, not a fabricated ratio. **Correct.**
- Escalation: `escalation_from`/`escalation_to` are absent from every committed ledger → `not
  measurable`. **Correct.**
- Checkpoint latency: `grep -rl '"checkpoints"' experiments/` finds zero committed files with a
  non-empty `checkpoints` array; the aggregator reports 0 records, `not_measurable`. **Correct.**

### (3) Measured-not-estimated rule — **PASS**

Traced every `measurable=True` value to a ledger field: `r` → `attempts[].attempt_number`;
throughput → `phases[].duration`/count + `started_at`/`ended_at`; cost-per-accepted →
`cells[].status` + `cells[].realized_cost`. Every `measurable=False` value is `None` with a
`reason` naming the missing field. No imputed figure anywhere in the output.

### (4) Coverage — complete-ledger table exact — **PASS**

Recomputed the run-ledger coverage independently: `experiments/specs/index.json` carries 118
`results_pointer` entries; `os.path.exists` on each returns **0 present, 118 absent**. `.gitignore:28`
excludes `experiments/results/workflows/`. The aggregator's `run_ledger_coverage` block returns
`{"referenced": 118, "present": 0, "absent": 118}` — exact, never imputed.

### (5) Citations — every finding resolves to its rows — **PASS**

Each number in the findings resolves to a named file: `r=0.125` → `cap_grit_grid_ledger.json`
(`cells[].attempts`); `$27.715817` → the same ledger's `realized_cost` column; `E_x = 11.4671 /
12.5134` → `cap_escalation_measurement_score_20260826T125726Z.json` (`per_model[].E_x`); the
28.2×/68.7× price ratios → `framework.html:748`. No uncited claim.

### (6) WFM scoping — implications derive from measured metrics — **PASS**

The findings scope `T_max` to "no committed `C_job`", batch to "no measured `b`", and escalation to
"E_x ≈ 11.5-12.5, n=1, descriptive" — each implication is explicitly derived from (or blocked by)
the measured metric, with the status quo as the baseline. No implication overreaches the evidence.

**LOG: PASS.**
