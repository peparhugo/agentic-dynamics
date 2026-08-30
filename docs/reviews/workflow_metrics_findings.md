---
status: accepted
---

# Workflow-metrics findings — the machine's ledgers consolidated into Rules 6-10

**Role:** p0 (pin + verify) + p3 (findings). **Spec:** `workflows/repository/workflow_metrics.yaml`.

## Pinned header (p0)

- **Spec SHA256:** `2cd4bb1105c915f3b9ae5e4e835c4277eddb6ba6da58ac7b7d8efd31498768d1`
  (`sha256sum workflows/repository/workflow_metrics.yaml`; git blob `23044430889a7290a13b4a642646f2e2dd45f3a9`).
- **Metric-definition verification (hard rule §3):** the pinned definitions are **complete** — all
  eight operating metrics are named with their formulas, reproduced verbatim below. **PASS.**

| metric | pinned §3 definition |
|---|---|
| `r` (retry rate) | attempts with `attempt_count > 1` / total attempts (per campaign) |
| `WOC` (first-call resolution) | `first_pass` / total |
| escalation rate | the escalations / total |
| `b` (batch fraction) | batch-mode jobs / total |
| throughput | cells or phases per hour per campaign |
| cost-per-accepted | the accepted outcomes' cost |
| checkpoint latency | `decided_at − reached_at` per approval |
| SLA | the timeouts/deadline breaches / total |

The aggregator (`scripts/aggregate_workflow_metrics.py`) holds these verbatim in
`PINNED_METRIC_DEFINITIONS`; `tests/test_aggregate_workflow_metrics.py::test_pinned_definitions_cover_all_eight_metrics`
locks the set. **LOG: PASS.**

---

## 1. Methodology

**Instrument.** `scripts/aggregate_workflow_metrics.py` walks `experiments/results/**/*.json`,
classifies each file into one of three ledger kinds — *attempt* (a `cells[].attempts` array),
*workflow-run* (`spec_name` + `phases`), *campaign-phase* (`campaign` + `phases`) — and computes
each pinned metric per campaign and pooled. A metric whose backing field is absent is reported
`not_measurable` with the missing field named, never imputed (hard rule 2). Outputs land in
`experiments/results/workflow_metrics/` (`aggregate.json`, `aggregate.csv`, `coverage.csv`).

**Coverage (exact).** The derived spec index (`experiments/specs/index.json`) references **118**
workflow run ledgers via `results_pointer`. Of those, **0 are present** in the committed tree and
**118 are absent** — `.gitignore:28` excludes `experiments/results/workflows/` as "machine-local,
not provenance", so the canonical run-ledger directory is untracked. The committed ledger-shaped
corpus the aggregator *can* read is **45 files across 9 campaigns**: 1 attempt ledger
(`cap_grit_grid_ledger.json`), 44 phase ledgers (2 escalation + 26 session-routing + 16 cap_2a/2b/2c
wrappers), and **0 non-empty `checkpoints` arrays**.

## 2. Measured operating metrics

| metric | measured value | basis / source fields | note |
|---|---|---|---|
| `r` (retry rate) | **0.125** (1 / 8) | derived from `attempts` array (`cap_grit_strength_grid`) | `attempt_count` field is declared-not-written |
| `WOC` (first-call resolution) | **not measurable** | — | `first_pass` declared-not-written |
| escalation rate | **not measurable** | — | `escalation_from`/`escalation_to` not written |
| `b` (batch fraction) | **not measurable** | — | no batch-mode field |
| throughput (phases/hr) | **73.43** (escalation campaign), **61.61** (session-routing) | `phases` + `started_at`/`ended_at` | the 16 cap_2a/2b/2c phase ledgers carry phases but no timestamps |
| cost-per-accepted | **$27.716** over 7 accepted jobs (mean **$3.959**) | `status` + `realized_cost` | the grit grid only |
| checkpoint latency | **not measurable** (0 records committed) | — | no `checkpoints` arrays carry `reached_at`/`decided_at`; the decisions/reasons/approval-evidence distributions are reported empty |
| SLA | **not measurable** | — | the breach fields (`stall_evidence`/`deploy_gate`/`commit_gate`/`relabel_gate`) are defined by the runner but **absent from every committed phase ledger** (all predate the runner hardening) |

Alongside the pinned metrics the instrument reports two measured quantities: **W (workload volume)**
= 8 jobs (the grit grid only; every other campaign is phase-only, so W=0), and the **phase-cost
structure** (agent vs test vs other): pooled **$0.5047** agent-phase cost + **$0.00** test-phase
cost + **$0.2024** untyped-phase cost across the phase ledgers — the agent/test split, not the 2b
"wrapper vs cell" split (which lives in the campaign's own score artifacts, cited below).

Pooled over the corpus: the only pooled figures that survive the measured-not-estimated rule are
throughput (two campaigns contribute) and cost-per-accepted (one campaign contributes). Every
other pinned metric is pooled as "0 of N campaigns measurable" — see `aggregate.json`.

## 3. Framework correction / confirmation

1. **Retry rate — the website's "it now IS measured" is not supported by a committed
   autonomous-workload ledger.** The nearest committed attempt ledger (`cap_grit_grid_ledger.json`)
   is the grit *story* grid (the Rules 1-5 perturbation corpus, `task_manager_api`), n=8, whose
   derived `r = 0.125` happens to sit near the 11.5% scenario. But the framework's `r` lever is for
   **autonomous workloads (Rules 6-9)**; that attempt ledger — with `attempt_count`, `retry_reason`,
   `first_pass`, `accepted` — is **not in the repository** (118 referenced ledgers absent). The
   claim "retry rate … it now IS measured (the attempt ledger)" (`framework.html:726,747`) is not
   backed by a committed autonomous-workload attempt ledger.
2. **Escalation — the measured E_x is ~11.5-12.5, not 28.2×/68.7×.** The escalation measurement
   campaign (`cap_escalation_measurement_score_20260826T125726Z.json`) measured the escalation-fix
   multiplier directly: **E_x = 11.4671** (DS→GPT-5.6-sol) and **12.5134** (DS→Claude-sonnet-5),
   computed as fix-cost / original-cell-cost ($0.102619/$0.008949 and $0.111982/$0.008949). The
   website's "28.2× (DS→GPT-5.6), 68.7× (DS→Claude)" are **price ratios [X]**, not measured
   escalation cost. The "<1% escalation to human" is a **policy target, not a measured rate** — no
   escalation-rate field exists to measure it against. *(The spec's own `domain_context` repeats the
   28.2×/68.7× as "measured" — that is the price ratio, corrected here.)*
3. **Confirmed unchanged:** `WOC = 1/(1+r)`, `T_max = Budget/C_job`, `C_job = C₀·EPM·(1−b·0.5)·(1+r·E_x)`
   remain the framework equations; nothing here contradicts them — but `r`, `b`, and the autonomous
   `C_job` that feed them are still unmeasured in the committed corpus.

## 4. WFM implications (scoped to the evidence)

- **T_max = Budget / C_job.** The measured cost-per-accepted ($3.959/attempt) is the grit story
  grid's per-attempt cost (Claude sonnet, n=8), **not** an autonomous job cost; the phase-ledger
  costs (~$0.003-0.10/phase) are per-phase, not per-job. There is no committed `C_job` to divide a
  budget by — so `T_max` cannot yet be computed from the ledger, and the website's "~667K max
  jobs/day" remains a worked example, not a measurement. **Status quo is the baseline.**
- **Batch scheduling.** `b` is unmeasured (no batch-mode field); the 50%-discount batch lever and
  the peak/off-peak interaction remain modeled. No measured `b` to schedule against.
- **Escalation design.** If the measured E_x ≈ 11.5-12.5 (rather than 28.2) held at scale, the
  retry-cost term `r·E_x` would be ~2.4× cheaper than the site's default for the DS→GPT tier —
  but n=1 per model, descriptive only; the <1% design target is untouched.

## 5. Honest limits

- **118 run ledgers absent** (gitignored `experiments/results/workflows/`). The coverage table is
  exact: 0 of 118 referenced ledgers present.
- **The only attempt ledger is a story grid** (n=8), not an autonomous workload; small-n.
- **Declared-not-written fields** (`attempt_count`, `first_pass`, `accepted`, `escalation_from/to`)
  close off `r`-by-field, `WOC`, and escalation-rate under the pinned definitions.
- **Zero checkpoint records** are committed — the checkpoint behavior the spec's question names
  ("the approval flow the machine just lived through") is not in the committed corpus, so the I10
  `reached_at`/`decided_at`/decision metrics are unmeasurable here.

**The single load-bearing finding:** the instrument is correct and the arithmetic is pinned; the
**data is not there**. The framework's autonomous-workload metrics (`r`, `WOC`, `b`, escalation
rate, `C_job`) require the workflow-run attempt ledger to be *committed* before any of them can be
measured — today they are machine-local and gitignored.
