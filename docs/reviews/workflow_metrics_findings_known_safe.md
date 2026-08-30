---
status: accepted
---

# workflow_metrics — known-safe attacks

**Role:** adversarial verifier (p4). **Source revision:** `workflows/repository/workflow_metrics.yaml`
SHA256 `2cd4bb1105c915f3b9ae5e4e835c4277eddb6ba6da58ac7b7d8efd31498768d1`.

This companion file records the non-falsifying attacks attempted — what was tried, the evidence,
and why each did not falsify the findings.

## Attempted attacks and why they did not falsify

### A1. "The aggregator folds a missing field into a 0.0" — not supported
- **Tried:** a synthetic ledger with no `attempts`/`checkpoints`/`accepted` rows through
  `compute_retry_rate`/`compute_checkpoint_latency`/`compute_cost_per_accepted`.
- **Evidence:** each returns `measurable=False`, `value=None`, with `reason` naming the missing
  field. Locked by `test_retry_rate_not_measurable_without_attempts`,
  `test_checkpoint_absent_is_covered_not_imputed`, `test_first_call_resolution_is_not_measurable`.
- **Why safe:** a missing field is a coverage gap, never a measured zero.

### A2. "The retry rate was computed from `attempt_count`, which does not exist" — not supported
- **Tried:** searching every committed JSON for `attempt_count`/`first_pass`.
- **Evidence:** zero occurrences; the fields are declared in `LEDGER_FIELDS` but declared-not-written
  (`control/checkpoint.py:85`). The aggregator derives `r` from the `attempts` array length and
  labels it `basis=derived` with the source field named.
- **Why safe:** the derivation is transparent and its basis is downgraded to `derived`, never
  presented as the (absent) `attempt_count` field.

### A3. "The E_x values were copied from the website, not the measurement" — not supported
- **Tried:** re-reading `cap_escalation_measurement_score_20260826T125726Z.json` and its
  `validation_note`.
- **Evidence:** `0.102619/0.008949 = 11.4671` and `0.111982/0.008949 = 12.5134` are computed from
  the phase-ledger `cost_usd` fields, each with a cited SHA256. The website's 28.2×/68.7× are price
  ratios; the findings cite both and distinguish them.
- **Why safe:** the findings use the measured multiplier and explicitly correct the price-ratio
  conflation (including the spec's own `domain_context`).

### A4. "The coverage claim ('118 absent') is stale or guessed" — not supported
- **Tried:** recomputing `results_pointer` presence directly from `experiments/specs/index.json`
  against the working tree.
- **Evidence:** 118 pointers, 0 present, 118 absent; `.gitignore:28` excludes
  `experiments/results/workflows/`. The aggregator recomputes this on every run (`run_ledger_coverage`).
- **Why safe:** the coverage is machine-recomputed, not authored into the doc.

### A5. "The throughput figures were imputed from a missing span" — not supported
- **Tried:** re-checking the two measurable throughput campaigns against their `started_at`/
  `ended_at`.
- **Evidence:** escalation campaign = 4 phases / 0.0545 h = 73.43/hr; session-routing = 76 phases /
  1.2336 h = 61.61/hr. The 16 cap_2a/2b/2c phase ledgers report `not_measurable` with their phase
  count (they carry no timestamps) rather than a guessed rate.
- **Why safe:** the numerator and denominator are both ledger fields; the no-timestamp campaigns
  are reported as a gap.

### A6. "The findings overclaim that the website is wrong" — not supported
- **Tried:** re-reading the framework's own wording (`framework.html:726,747,748,904`).
- **Evidence:** the site labels `r` "now IS measured (the attempt ledger)" and `E_x` "28.2×/68.7×"
  as the escalation multiplier, while the committed attempt ledger is a story grid (n=8) and the
  measured escalation multiplier is 11.47/12.51. The findings state each discrepancy as a
  *correction/confirmation*, not an accusation, and cite the exact lines.
- **Why safe:** every correction is scoped and line-cited; nothing is asserted beyond the ledger.

**LOG: PASS** — none of the attacks falsified a finding; the known-safe list records six attempted
and non-falsifying attacks.
