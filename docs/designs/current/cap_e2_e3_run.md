---
status: accepted
---
# CAP E2/E3 Run — Confidence-Cascade Retrospective + Coverage-Impact Re-run

**Spec:** `workflows/repository/cap_e2_cascade_run.yaml`
**Branch:** `feature/cap-e2_cascade_run`
**Model:** deepseek/deepseek-v4-flash (single-model orchestrator, `--backend opencode`)
**Sources:** `experiments/results/workflows/**/*.json` (the backfilled fact store's workflow-run
corpus; F1-sanitized costs), `experiments/definitions/cap_confidence_cascade.yaml` (E2),
`experiments/definitions/cap_coverage_routing_impact.yaml` (E3), the coverage census
(`docs/designs/current/cap_fact_backfill_coverage.md`).

**Machine-readable artifacts:** `experiments/results/cap_cascade_retrospective.json` (E2, this
section); E3's change-rate table lands in its own section below as the workflow progresses.

**GUARD:** retrospective only — every cascade arm below is a counterfactual; no attempt was ever
actually escalated by a confidence-gated policy, no model is called by this analysis, and no
number below is fabricated. Null-not-zero: uncaptured cost/confidence is `null` with zero
coverage, never a zero-cost or non-escalating assumption.

---

## 1. E2 — confidence-gated cascade retrospective (e1_cascade_simulation)

### 1.1 Hypothesis

Does a confidence-gated `model_cascade` control arm — escalate to a stronger model whenever
`attempt_confidence < theta`, for theta in {0.3, 0.5, 0.7} — improve cost-per-verified-outcome
over the single-model baseline already recorded in the corpus?

### 1.2 Null hypothesis (stated explicitly, per the spec)

> **No threshold improves cost-per-verified-outcome over baseline.**

As predicted by the spec's finding 2, **this null is structurally untestable from this corpus by
construction**, not merely under-powered: no attempt in the recorded corpus was ever ACTUALLY
escalated (`model_cascade` has no implementation and no call site — grepped), so the
post-escalation cost/outcome of every would-be-escalated attempt is genuinely unknown. This run's
headline result is that honest verdict, not a confirmed non-improvement.

### 1.3 Method

- **Source:** 126 workflow-run ledgers (462 phases: 455 agent-kind + 7 test-kind) under
  `experiments/results/workflows/**/*.json`, read as raw typed run artifacts (per the spec's
  finding 5, never through a live authority-gated FactStore — a retrospective read).
- **Costs:** F1-sanitized — a failed-before-call phase's structural `0.0` is recorded `None`
  (uncaptured, never a measured zero), matching the backfilled fact store.
- **"Verified success"** = `phase_status == "ok"` (completion signal, 100% covered), per the
  spec's explicit substitution. `phase_test_verified` (independently-tested correctness) is
  confirmed ~0% on agent phases and out of this spec's fixed `requires_facts` scope.
- **Coverage pre-check first** (the n=0 lesson): confidence coverage reported before any
  downstream metric is trusted.
- **Arms:** baseline (as actually run) vs. cascade_theta_X (counterfactual "escalate below X").
  Per theta, the confidence-captured set splits into the non-escalated subset (confidence ≥ theta,
  where the cascade is byte-identical to baseline — a **baseline-equivalent tautology**, not a
  measurement of escalation) and the escalated subset (confidence < theta, whose true outcome is
  **unmeasured and excluded, never fabricated**).
- **Confound control (spec finding 4):** the comparison is stratified by `job_status`
  (job_ok True/False) and a per-model escalation-trigger-range indicator tracks the
  model×threshold confound (confidence is a self-report).

### 1.4 Coverage pre-check (FIRST)

| Signal | n_available / n_total | Coverage |
|---|---|---|
| `attempt_confidence` | 362 / 462 | **78.3%** — not near-zero; **EVALUABLE_WITH_CAVEAT** |
| `phase_status` (verified-success proxy) | 462 / 462 | 100% |
| `job_status` (run-level `ok`) | 126 / 126 | 100% |

The caveat is the spec's own: the 100 confidence-less phases (failed-before-call +
pre-instrumentation runs) make the confidence-gated comparison **inconclusive-by-design for that
22%** (selection-on-confidence bias). The pre-check verdict is **EVALUABLE_WITH_CAVEAT** — NOT
INCONCLUSIVE, because 78.3% coverage is far from the n=0 lesson that would force the spec's
honest INCONCLUSIVE default. Reproducible via `python3 scripts/cap_cascade_retrospective.py`.

### 1.5 Per-threshold table (captured-only intersection; coverage-adjusted)

| θ | Escalation trigger rate | Would-escalate n (unmeasured) | Cascade cost/verified (non-escalated subset) | Non-escalated subset n | Verified-success rate (non-escalated subset) | Per-model trigger-range |
|---|---|---|---|---|---|---|
| 0.3 | 1.66% | 6 | 1.8713 | 356 | 99.16% | 0.2857 |
| 0.5 | 3.59% | 13 | 1.8932 | 349 | 99.14% | 0.2857 |
| 0.7 | 10.77% | 39 | 1.7755 | 323 | 99.38% | 0.5 |
| **Baseline** | — | — | **1.8109** (452/462 cost-captured, 434 verified) | 462 | **93.94%** | — |

Baseline detail: cost/verified = $785.93 / 434 = **$1.8109** per verified outcome over the
captured-only intersection (452/462 = 97.8% cost coverage; the 10 excluded phases are
F1-sanitized failed-before-call structural zeros). Verified-success rate 434/462 = 93.94%.

### 1.6 Arm comparison (the honest headline)

| θ | routing_arm_regret | null_testable | Meaning |
|---|---|---|---|
| 0.3 | **0.0 (by construction)** | **false** | escalated n = 6 > 0 — null untestable |
| 0.5 | **0.0 (by construction)** | **false** | escalated n = 13 > 0 — null untestable |
| 0.7 | **0.0 (by construction)** | **false** | escalated n = 39 > 0 — null untestable |

**Do NOT read "regret = 0" as "escalation is safe."** Regret is 0.0 because on the non-escalated
subset the cascade's executions are byte-identical to baseline's — computing the cascade's number
on that subset alone reproduces baseline's own number on the same subset (a tautology). The
would-be-escalated subset (6/13/39 attempts) was never actually escalated, so its true
cost/outcome is unknown. `null_testable = false` for every theta is the real signal this corpus
can produce: the null is untestable-by-construction until a **live** grid (E4-style) actually
executes cascade attempts, or a natural-experiment proxy from real historical escalations in
attempt lineage (parent_attempt_id / escalation_from / escalation_to) exists.

**What IS soundly measured today:**
1. **Baseline's real cost-per-verified-outcome = $1.8109** (fully-covered cost + status, n=462,
   captured-only intersection).
2. **Escalation trigger rates** — the measured fraction of the corpus a live cascade would touch:
   1.7% / 3.6% / 10.8% at θ = 0.3 / 0.5 / 0.7. Trustworthy because confidence coverage is 78.3%,
   not near-zero.
3. **job_status stratification confirms the finding-4 confound is real, not hypothetical:**

| job_status | n phases (cost-captured) | n verified | cost/verified |
|---|---|---|---|
| job_ok = True | 403 | 403 | **1.3678** (100% verified) |
| job_ok = False | 49 | 31 | **7.5714** (63.3% verified) |

   Pooling these would conflate "this threshold performed worse" with "this job failed for an
   unrelated reason" — a job whose overall run failed shows ~5.5× the cost-per-verified-outcome
   and far lower verified-success for reasons orthogonal to any routing policy. The escalation
   trigger is also concentrated in failed jobs (e.g. θ=0.7: 30.0% of confidence-captured phases
   in ok-false runs would trigger vs 8.9% in ok-true runs) — consistent with low confidence being
   informative about run health, which is exactly what a future live cascade pilot should test.

### 1.7 Uncertainty & limitations

- **Confidence is a self-report ([H]/advisory), never canonical.** The model×threshold range
  indicator (0.29–0.50 across θ) shows different models self-report on different distributions —
  a pooled trigger-rate could partly reflect corpus model mix, not pure threshold aggressiveness.
- **Selection-on-confidence bias:** the 22% of phases without confidence are excluded, never
  assumed non-escalating.
- **F1 structural zeros** (10 phases) are excluded from cost, not counted as zero-cost outcomes.
- **No real escalations exist** in the corpus — the fundamental untestability above.

### 1.8 Routing implication for the shadow-#2 chain

The measured trigger rates bound how often a live cascade would fire today, and the
job_status split shows low-confidence phases concentrate in failing jobs — but **nothing here
licenses flipping `model_cascade` on.** The load-bearing rule (measure before policy) requires
the escalated branch's cost/outcome to be MEASURED, which only a live grid or real escalation
lineage can do. The next-campaign action the spec's `adapt` already names: a **live pilot of the
highest-uncertainty threshold** (largest unmeasured_escalated_n = θ=0.7, 39 attempts) in an
E4-style grid where cascade attempts actually execute. Until then, this retrospective is the
honest placeholder: baseline measured, trigger rates measured, null recorded as
untestable-by-construction — never as a confirmed non-improvement.

### 1.9 E1 LOG

| Check | Result |
|---|---|
| Confidence coverage pre-check reported FIRST | **PASS** — 362/462 = 78.3%, EVALUABLE_WITH_CAVEAT (not INCONCLUSIVE) |
| Per-threshold table computed (θ ∈ {0.3, 0.5, 0.7}) | **PASS** — trigger 1.7% / 3.6% / 10.8%; regret 0.0 by construction; null_testable false |
| Counterfactual-only guard | **PASS** — no escalation applied, no model called |
| Null-not-zero | **PASS** — uncaptured = null; escalated subset excluded, never fabricated |
| Every number traces to the registry/corpus | **PASS** — reproduced from `cap_cascade_retrospective.json`, cross-checked by hand |
| Machine artifact written | **PASS** — `experiments/results/cap_cascade_retrospective.json` |
| Script committed + CLI-reachable | **PASS** — `scripts/cap_cascade_retrospective.py`, `agentic-dynamics analyze cascade-retrospective` |
| **Overall E1** | **PASS** — EVALUABLE_WITH_CAVEAT; null untestable-by-construction, recorded honestly |

---

## 2. E3 — coverage-impact re-run (e2_coverage_impact) — *pending*

*E3 (`recommend_route` with coverage-corrected stats vs legacy zero-default projection) lands in
this section in the next workflow phase.*
