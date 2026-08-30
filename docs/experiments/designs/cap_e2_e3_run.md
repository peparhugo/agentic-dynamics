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
(`docs/experiments/results/cap_fact_backfill_coverage.md`).

**Machine-readable artifacts:**
- `experiments/results/cap_cascade_retrospective.json` (E2, §1)
- `experiments/results/cap_coverage_routing_impact.json` (E3, §2)
- full synthesis: §3 below.

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
   trigger is also concentrated in failed jobs (e.g. θ=0.7: 37.5% (9/24) of confidence-captured phases
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

## 2. E3 — coverage-impact re-run (e2_coverage_impact)

### 2.1 Question

Does `control.routing`'s current coverage-corrected `recommend_route`/`compute_routing`
(excludes uncaptured cost/correctness, never zero-defaults) recommend a DIFFERENT model than the
legacy zero-default formula (`lab_task_routing.py`'s own, quarantined — coerces a missing
cost/correctness to 0 and averages over all n), when BOTH are applied to the SAME corpus —
`canonical_corpus.resolve_findings()` (the 64 current `finding` rows, the live registry-governed
replacement for the retired `_results_summary.json`)? Now that the store is backfilled, does the
finding-economics fix move real decisions?

**Null hypothesis: zero changes.** A null here is a result, not a failure.

### 2.2 Method

- **Corpus:** `resolve_findings()` — 64 current finding rows, 2 eligible tasks after
  `min_models=2` (`task_manager`: 7 models / 49 entries; `process_perturbation_resample`:
  3 models / 15 entries). The spec's finding 1 checked `resolve_stories` is the WRONG population
  and `resolve_findings` is the correct one — both verified here by the resolver's own contract.
- **Coverage-corrected arm:** `control.routing.compute_routing` called as-is (no re-derivation).
- **Legacy arm:** `lab_task_routing.py`'s aggregation formula re-derived
  (`avg = sum(e.get("x", 0))/n` over ALL n — the historical zero-default defect), applied to the
  SAME entries with the same eligibility filter and the same decision surface — isolating the
  aggregation-method variable from the corpus-source variable.
- **Evaluation:** per-task recommendation diff (default_model + routing) + direction analysis.

### 2.3 Entry coverage pre-check (FIRST)

| Signal | n_available / n_total | Coverage |
|---|---|---|
| `cost_usd` (raw key presence) | 64 / 64 | 100% |
| `correctness` | 64 / 64 | 100% |
| **cost, operational** (`cost_captured`: positive finite only; `0.0` = no billable work — what `recommend_route` actually consumes) | **53 / 64** | **82.8%** |

The operational row is the honest mechanism check (see 2.5): 11 entries carry `cost_usd == 0.0`
(concentrated in `anthropic/claude-haiku-4-5` 1/7 and `anthropic/claude-sonnet-5` 2/7 within
`task_manager`). The spec's finding 2 ("coverage is 100% … the formulas are MATHEMATICALLY FORCED
TO AGREE") measured raw key presence; the operational view shows the divergence surface is NOT
empty.

### 2.4 Change-rate table (DELIVERABLE)

| Task | Coverage-corrected recommendation | Legacy zero-default recommendation | Changed? |
|---|---|---|---|
| `task_manager` | default `deepseek-v4-flash`, escalate to `claude-haiku-4-5` | default `deepseek-v4-flash`, escalate to `claude-haiku-4-5` | **no** |
| `process_perturbation_resample` | default `deepseek/deepseek-v4-pro` | default `deepseek/deepseek-v4-pro` | **no** |

| Metric | Value |
|---|---|
| changed_recommendation_count | **0** |
| changed_recommendation_rate | 0.0% (0/2 tasks) |
| changed_by_model | {} (no model appears in a changed recommendation) |
| moved_to_lower_cost_count | 0 (n/a — no changes to move) |

### 2.5 The honest mechanism finding (deviates from the spec's prediction)

The spec's finding 2 predicted the null would hold because coverage is 100% — "the two formulas
are mathematically forced to agree." **That mechanism is wrong; the null still holds for a
different, more informative reason.** Measured live:

| task | model | corrected avg_cost (captured-only) | legacy avg_cost (zero-default) | n_cost_operational / n |
|---|---|---|---|---|
| `task_manager` | `anthropic/claude-haiku-4-5` | **$0.3097** | **$0.0442** (7× underpriced) | 1 / 7 |
| `task_manager` | `anthropic/claude-sonnet-5` | **$0.6480** | **$0.1851** (3.5× underpriced) | 2 / 7 |

The per-model stats DID diverge — exactly the divergence the coverage correction was built to
close (a partially-priced model looks artificially cheap under zero-defaulting). **But zero
recommendations changed**, because the diverging models sit off the decision boundary:

- `task_manager`'s default is anchored by `deepseek-v4-flash` — fully cost-captured (7/7), so its
  avg_cost is IDENTICAL under both formulas — and it remains the cheapest qualified model either
  way. The escalate target is `claude-haiku-4-5` by BEST CORRECTNESS (1.0), which is unchanged by
  the cost correction (correctness is 100% covered).
- `process_perturbation_resample`'s models are all fully cost-captured (0 divergence), so both
  formulas agree trivially.

### 2.6 Null interpretation

**Zero changes is information, not failure.** The finding-economics fix does NOT move a real
decision on the currently-populated store — the recommendation surface is robust to the
cost-coverage correction on this corpus. But the fix is demonstrably NOT inert: it changes the
measured per-model economics of two partially-covered models (haiku-4-5's true cost is 7× its
zero-defaulted figure). It gains decision teeth the moment a partially-covered model competes for
the default or escalate slot — and the leading indicator for when that happens is
`entry_coverage_precheck.operational.cost_coverage_ratio`, currently **82.8%** (not 100%). The
spec's raw-key-presence pre-check (100%) would MISS that trigger; the operational view does not.

### 2.7 E2 LOG (coverage-impact phase)

| Check | Result |
|---|---|
| Coverage pre-check reported FIRST (raw + operational) | **PASS** — cost 64/64 raw (100%), operational cost 53/64 (82.8%), correctness 64/64 |
| Coverage-corrected recommendations computed | **PASS** — `compute_routing` as-is, 2 eligible tasks |
| Legacy zero-default recommendations computed (same corpus) | **PASS** — re-derived formula, same 2 tasks |
| Change-rate table | **PASS** — 0/2 tasks changed (0.0%), no per-model changes |
| Mechanism honesty | **PASS** — per-model stat divergence recorded (haiku-4-5 7×, sonnet-5 3.5×) even though no decision flipped; spec's "forced to agree" mechanism corrected |
| Null-not-zero / null-is-result | **PASS** — 0 changes recorded as information, not failure |
| Machine artifact | **PASS** — `experiments/results/cap_coverage_routing_impact.json` |
| Script committed + CLI-reachable | **PASS** — `scripts/cap_coverage_routing_impact.py`, `agentic-dynamics analyze coverage-routing-impact` |
| **Overall E3** | **PASS** — null confirmed; mechanism finding recorded (divergence without decision change) |

---

## 3. Writeup — full synthesis (e3_writeup)

This section is the consolidated writeup of the two retrospective experiments (E2 §1, E3 §2) —
hypothesis, null, method, coverage pre-check, per-threshold table, change-rate table, null
interpretation, limitations, and the routing implication for the shadow-#2 chain. **GUARD: every
number below traces to the two machine artifacts (and through them to the raw workflow-ledger and
registry corpora); honest nulls are reported as such, never as confirmed effects.**

### 3.1 Hypothesis (both experiments)

- **E2** (`cap_confidence_cascade`): does a confidence-gated `model_cascade` control arm
  (escalate to a stronger model when `attempt_confidence < theta`, θ ∈ {0.3, 0.5, 0.7}) improve
  cost-per-verified-outcome over the single-model baseline already in the corpus?
- **E3** (`cap_coverage_routing_impact`): does `control.routing`'s coverage-corrected
  `recommend_route`/`compute_routing` recommend a DIFFERENT model than the legacy zero-default
  formula, when both are applied to the SAME registry-governed corpus?

### 3.2 Null hypotheses (stated explicitly, per both specs)

- **E2:** no threshold improves cost-per-verified-outcome over baseline.
- **E3:** zero changes — no task/model pair's routing recommendation differs between the formulas.

Both nulls are treated as *information when confirmed*: a null is never failure. E2's null is
additionally **untestable-by-construction** from this corpus (see §3.6) — which is itself the
headline result, not a defect in the spec.

### 3.3 Method (one sentence each; details in §1.3 and §2.2)

- **E2:** replay the F1-sanitized workflow-run corpus (126 runs / 462 phases) as counterfactual
  arms — baseline as-recorded vs cascade_theta_X ("escalate below X") — computing what CAN be
  measured retrospectively (baseline cost/verified; each θ's escalation trigger rate) and
  explicitly marking what cannot (the would-be-escalated subset's true post-escalation outcome).
- **E3:** apply the coverage-corrected formula (as-is `compute_routing`) and the re-derived legacy
  zero-default formula (`lab_task_routing.py`'s aggregation) to the SAME
  `canonical_corpus.resolve_findings()` corpus (64 current finding rows), and diff the
  recommendations per task and per model.

### 3.4 Coverage pre-check results (FIRST, in both experiments)

| Signal (E2) | n_available / n_total | Coverage | Signal (E3) | n_available / n_total | Coverage |
|---|---|---|---|---|---|
| `attempt_confidence` | 362 / 462 | **78.3%** — EVALUABLE_WITH_CAVEAT | `cost_usd` (raw presence) | 64 / 64 | 100% |
| `phase_status` (verified-success proxy) | 462 / 462 | 100% | `correctness` | 64 / 64 | 100% |
| `job_status` (run-level `ok`) | 126 / 126 | 100% | **cost, operational** (`cost_captured`: `0.0` = no billable work) | **53 / 64** | **82.8%** |

Neither experiment is INCONCLUSIVE at the pre-check: E2's confidence coverage is far from the
n=0 lesson (78.3%), and E3's cost/correctness are fully present. The honest caveats live in the
mechanism, not the pre-check (see §3.6 and §3.7).

### 3.5 Result tables

**E2 per-threshold table** (captured-only intersection, F1-sanitized, coverage-adjusted):

| θ | Escalation trigger rate | Would-escalate n (unmeasured) | Cascade cost/verified (non-escalated subset) | Non-escalated subset n | Verified-success rate (subset) | Per-model trigger-range |
|---|---|---|---|---|---|---|
| 0.3 | 1.66% | 6 | 1.8713 | 356 | 99.16% | 0.2857 |
| 0.5 | 3.59% | 13 | 1.8932 | 349 | 99.14% | 0.2857 |
| 0.7 | 10.77% | 39 | 1.7755 | 323 | 99.38% | 0.5 |
| **Baseline** | — | — | **$1.8109** (452/462 cost-captured; 434 verified) | 462 | **93.94%** | — |

**E3 change-rate table:**

| Task | Coverage-corrected recommendation | Legacy zero-default recommendation | Changed? |
|---|---|---|---|
| `task_manager` | default `deepseek-v4-flash`, escalate to `claude-haiku-4-5` | default `deepseek-v4-flash`, escalate to `claude-haiku-4-5` | **no** |
| `process_perturbation_resample` | default `deepseek/deepseek-v4-pro` | default `deepseek/deepseek-v4-pro` | **no** |

changed_recommendation_count = **0** (0.0%, 0/2 tasks); changed_by_model = {}; moved_to_lower_cost = n/a.

### 3.6 Null interpretation (inconclusive is valid)

**E2 — the null is untestable-by-construction, recorded honestly, NOT a confirmed null.**
`routing_arm_regret = 0.0` at every θ is a TAUTOLOGY (on the non-escalated subset the cascade is
byte-identical to baseline), and `null_testable = false` at every θ because the would-be-escalated
subset (6/13/39 attempts) was never actually escalated — its true post-escalation cost/outcome is
genuinely unknown, never fabricated. **Inconclusive-by-construction is the valid, honest outcome
here.** What IS soundly measured: (1) baseline's real cost/verified = **$1.8109** over the
captured-only intersection; (2) the escalation trigger rates (**1.7% / 3.6% / 10.8%** at θ =
0.3/0.5/0.7) — how often a live cascade would fire today, trustworthy because confidence coverage
is 78.3%, not near-zero; (3) the job_status confound is real (ok-true cost/verified **$1.37** vs
ok-false **$7.57**, and low-confidence phases concentrate in failed runs) — pooling would conflate
threshold performance with run health.

**E3 — the null is confirmed (zero changes), which is a result, not a failure — but the spec's
predicted MECHANISM is wrong.** Raw cost-key coverage is 100%, yet operational cost coverage
(`cost_captured`) is only 82.8% (53/64), so the two formulas DID diverge on per-model stats
(haiku-4-5 corrected **$0.31** vs legacy **$0.044** = 7× underpriced; sonnet-5 **$0.65** vs
**$0.19** = 3.5× underpriced) — yet zero recommendations flipped, because the diverging models sit
off the decision boundary (default anchored by fully-captured flash; escalate target chosen by
fully-covered best-correctness). The finding-economics fix is demonstrably non-inert but has zero
decision teeth on the currently-populated store.

### 3.7 Limitations

1. **E2: no real escalations exist in the corpus** — the fundamental untestability above. Escalation
   is counterfactual only; nothing licenses reading any regret/cost number as an escalation effect.
2. **E2: selection-on-confidence bias** — 100 of 462 phases (22%) carry no confidence
   (failed-before-call + pre-instrumentation); they are excluded, never assumed non-escalating.
3. **E2: confidence is a self-report ([H]/advisory)** — the model×threshold trigger-range indicator
   (0.29–0.50) shows different models self-report on different distributions; pooled trigger rates
   partly reflect corpus model mix.
4. **E2: F1 structural zeros** (10 phases) are excluded from cost as uncaptured — never counted as
   zero-cost outcomes.
5. **E3: coverage saturation** — at 100% raw / 82.8% operational cost coverage the comparison is
   near-boundary; the informative signal is the operational coverage ratio, the leading indicator
   for when the comparison gains teeth. A partially-covered model on the decision boundary is the
   scenario this corpus does not yet contain.
6. **E3: corpus is small** — 2 eligible tasks (64 findings; `task_manager` 49, `process_perturbation_resample` 15).
7. **Both: workflow-run ledgers are gitignored** (`experiments/results/workflows/`); the corpus
   lives only in the main worktree (per the census doc's §0) and was copied into this worktree for
   the run — a fresh checkout cannot reproduce without that step.

### 3.8 Routing implication for the shadow-#2 chain

The shadow-#2 chain is the sequence of measurement campaigns that gate the I7 apply seam: shadow-#1
(the CAP I6 shadow loop, `docs/experiments/results/cap_shadow_measurement.md`) measured shadow_rule vs
step_routing at n=11 decisions and returned **"apply may NOT flip yet"** — every snapshot was
inadmissible at C2 because the fact plane was unpopulated. This run (E2 + E3) is the next link: it
uses the now-backfilled store to answer two questions that shadow-#1 could not, and it changes the
recommendation for shadow-#2 in two ways:

1. **Confidence-gated cascade is NOT yet writable as a live policy — a shadow-#2 that assumes it
   is would be unfounded.** E2 measured trigger rates (1.7% / 3.6% / 10.8%) but the escalated
   branch's cost/outcome is unmeasured. The load-bearing rule (measure before policy) therefore
   still forbids a live `model_cascade` arm. Shadow-#2's mandate should be a **live pilot of the
   highest-uncertainty threshold (θ=0.7, 39 would-be-escalated attempts)** in an E4-style grid
   where cascade attempts actually execute — the natural experiment that turns E2's
   untestable-by-construction null into a testable one.

2. **Routing recommendation machinery is safe to keep running, but its current output is
   coverage-saturated — a shadow-#2 flip would be a no-op today.** E3 shows coverage-corrected
   routing does not move a single recommendation versus legacy on the populated store (0/2 tasks).
   The fix is non-inert (real per-model economics change: haiku-4-5's true cost is 7× its
   zero-defaulted figure) but no decision flips. For the shadow chain this means: the I7 flip
   decision is NOT blocked by routing-aggregation risk (both formulas agree on what to route
   today), but it is ALSO not yet *informed* by a coverage-stressed routing decision — the 
   `entry_coverage_precheck.operational.cost_coverage_ratio` (82.8%) is the indicator to watch:
   the day a partially-covered model competes for a default/escalate slot, E3's zero-change null
   stops holding and shadow-#2 would measure a real divergence.

**Net recommendation for the shadow-#2 chain:** do NOT flip I7's apply seam yet. Proceed to a live
cascade pilot (E4-style, θ=0.7) and keep monitoring the operational cost-coverage ratio; shadow-#2
should carry a cascade arm that actually escalates (making E2 testable) and a routing comparison
that is coverage-stressed (making E3 informative). Both experiments' honest nulls are the reason,
not an obstacle.

### 3.9 Writeup LOG

| Check | Result |
|---|---|
| Hypothesis + explicit null for both experiments | **PASS** — §3.1–3.2 |
| Method traced to both specs' rules | **PASS** — §3.3 (details §1.3, §2.2) |
| Coverage pre-check results (E2 + E3) | **PASS** — §3.4 (78.3% confidence; 100% raw / 82.8% operational cost) |
| Per-threshold table (E2) | **PASS** — §3.5 |
| Change-rate table (E3) | **PASS** — §3.5 (0/2 changed) |
| Null interpretation (inconclusive is valid) | **PASS** — §3.6 (E2 untestable-by-construction; E3 confirmed-null, mechanism corrected) |
| Limitations | **PASS** — §3.7 (7 recorded) |
| Routing implication for the shadow-#2 chain | **PASS** — §3.8 (no flip; live θ=0.7 pilot + monitor operational coverage) |
| Every number traces to JSON/registry | **PASS** — all figures re-verified from `cap_cascade_retrospective.json` + `cap_coverage_routing_impact.json` |
| GUARD: counterfactual only / null-not-zero / honest nulls | **PASS** — no escalation applied; uncaptured = null; untestable ≠ confirmed-null |
| **Overall e3_writeup** | **PASS** |
