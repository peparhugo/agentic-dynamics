---
status: accepted
---

# Adversarial review: confidence-cascade study

**Scope.** This review reads the Phase A retrospective, the Phase B pre-registration, the
recorded sources inventory, and the Phase A posterior. It evaluates whether their claims are
identified by the cited evidence, not whether a confidence cascade would be valuable in
principle. The study is correctly **paused**; no result below licenses the grid.

## Materials and reproducibility

The review used these Phase-A materials:

- `docs/reviews/confidence_cascade_retrospective.md`
- `docs/designs/proposed/confidence_cascade_study.md`
- `notes/sources.jsonl` and `notes/posterior.md` from commits `560101864` and `c90440555`,
  respectively; `notes/` is intentionally untracked, so their committed phase artifacts are
  historical blobs rather than checkout files.
- `workflows/repository/confidence_cascade_study.yaml` and
  `experiments/specs/STATUS.md`

The source inventory identifies a material contract error: the workflow context says to filter
`source_type == "ledger_attempt"`, but the retrospective shows that filter has zero live rows.
The analyzed confidence signal is instead emitted as current `source_type == "fact"` records
with `fact://attempt/.../attempt_confidence` URIs. A future rerun that follows the workflow
literally would conclude, incorrectly, that the data do not exist.

The workflow context also says `python3 scripts/sync_data.py check`. That positional argument
runs a sync rather than validation; the valid check form is `python3 scripts/sync_data.py
--check`. The latter currently fails because the checked-in parquet has 1,027 session and 207
story rows while the available source resolves to zero rows. Therefore parquet is neither an
independent replication nor a usable source for confidence, independent test success,
`first_pass`, accepted, or lineage.

### Independent recomputation

I re-ran the posterior's recorded live-registry query, joining current `fact` rows to their KB
artifacts and counting `attempt_confidence == 1.0`:

```bash
python3 - <<'PY'
import collections, json
by = collections.defaultdict(dict)
for line in open('/app/experiments/results/registry_index.jsonl'):
    row = json.loads(line)
    if row.get('source_type') != 'fact' or row.get('lifecycle_state') != 'current':
        continue
    uri = str(row.get('source_uri') or '')
    if uri.startswith('fact://attempt/'):
        attempt, predicate = uri[len('fact://attempt/'):].rsplit('/', 1)
        by[attempt][predicate] = row['knowledge_id']
values = []
for predicates in by.values():
    key = predicates.get('attempt_confidence')
    if key:
        artifact = json.load(open(f'/app/experiments/results/kb/{key}.json'))
        values.append(float(json.loads(artifact['text'])['value']))
counts = collections.Counter(values)
print(len(by), len(values), counts[1.0], f'{counts[1.0] / len(values):.6%}')
PY
```

It produced **2,510** attempt keys, **1,348** confidence values, **869** exact `1.0` values,
and **64.465875%**. The retrospective's pinned artifact reported 2,505 / 1,345 / 868 /
64.535316%. This does not disprove its rounded 64.5% point-mass finding, but it does prove the
recorded command is not byte-reproducible from the mutable live store. The posterior anticipated
this risk. A hash written in prose is an identifier, not a recoverable snapshot; a reviewable
analysis needs the registry and resolved artifacts retained together at that hash.

## Claim 1: confidence is not calibrated for a graded threshold

**Assessment: supported only as a narrow, conditional negative result.** The retrospective's
positive-confidence AUC of 0.488 and Spearman rho of -0.009 are appropriate warnings against
fitting a threshold from this snapshot. They are not estimates of prospective calibration for
the entire attempt population or of independent correctness.

The calibration sample is selected after outcome-associated recording: confidence is present on
1,288/2,140 `ok` attempts (60.2%) but only 55/211 failed attempts (26.1%), a recorded risk ratio
of 2.31. Conditioning on having confidence can alter both the failure prevalence and the score
distribution. The `0.0` cell is worse: the score is assigned as zero on session error, while the
completion outcome is failed in the same execution path. Its apparent discrimination is outcome
leakage, not forecast skill. Excluding that cell avoids the tautology but leaves a selected,
high-success sample, where only four confidence-bearing attempts have the independent
`test_executed_success` verdict.

The score's 64.5% point mass at `1.0` also makes threshold calibration intrinsically coarse. A
bin table may reveal non-monotonicity, but it is not a calibration assessment without a proper
outcome, uncertainty intervals, and an observation rule that applies to failures as well as
successes. Reporting a Brier score, calibration intercept/slope, and reliability intervals on a
prospectively complete test-outcome cohort would be more informative than ranking completion
status in the selected retrospective cohort.

**Falsifier.** This narrow null is falsified if the instrumentation probe emits confidence and a
reason code for every attempt, attaches independent test verdicts to at least the stated 300
attempts across two models and two conditions, and then shows a monotone held-out reliability
curve with confidence intervals excluding the present flat pattern. Until then, the correct
claim is “not established and not usable for a graded policy,” not “confidence can never help.”

## Claim 2: historical escalation ROI is unavailable

**Assessment: correct, but the proposed ROI endpoint is still not operational.** Zero observed
`escalation_from`, `escalation_to`, `parent_attempt_id`, and retry lineage mean no historical
treated outcomes exist. No matching, regression, or counterfactual cost simulation can recover
the strong-model outcome for the would-escalate cases from these records. The prior $1.8109 cost
per completed phase and the `E_x` defect-fix multipliers do not estimate a cascade return; the
latter is n=1 per model and measures later repair, not an escalated decision.

The pre-registration correctly includes `rework_cost_usd` in the quality-per-dollar denominator
and makes its absence G-F7. However, it does not define the lineage window or attribution rule:
which later attempt is a repair of which initial attempt, how costs are allocated when one commit
fixes several defects, and how censored unresolved work is charged. Without those rules, zero
recorded rework will be indistinguishable from missing lineage and will bias a cascade toward
looking cheaper. The denominator must include all pre-registered linked retry, escalation, and
downstream repair costs, including unresolved chains reported as censored rather than zero.

**Falsifier.** The “no historical ROI” claim is falsified by a versioned ledger containing a
nontrivial number of linked escalations with both model costs, independent outcomes, and the
pre-specified rework attribution fields. The prospective “quality per dollar” claim is falsified
for publication if any arm lacks those lineage fields or if a sensitivity analysis that charges
plausible unresolved rework reverses its conclusion.

## Claim 3: the proposed grid can identify a cascade advantage

**Assessment: not yet identified by the stated design.** Full factorial `policy x story x
condition` coverage and stratified reporting are necessary controls for task difficulty, but
they do not by themselves make a conditional escalation arm comparable with static-model arms.
The cascade's strong-model calls occur only after a fast attempt has produced a low score. That
subset is selected by post-attempt behavior, is expected to differ sharply by condition and task
difficulty, and is not exchangeable with the `always_strong` cohort. An escalated versus
non-escalated within-cascade comparison would therefore be a selection comparison, not a model
effect.

There is also an endpoint contradiction. `first_pass` is defined as success on session 1, yet a
cascade can only escalate after the fast attempt's own confidence is observed. If escalation
means another model attempt, it cannot improve the original attempt's first-pass status. As
currently written, the primary endpoint mechanically penalizes the treatment or changes its
denominator, depending on whether the escalation is counted as a new attempt. The protocol must
define one decision unit before any run: for example, a story-session episode beginning with the
fast call and ending after any allowed escalation, with cost and independent test outcome
aggregated over that episode. `first_pass` can remain a diagnostic, but cannot be the primary
effect endpoint for a post-first-attempt treatment.

Task difficulty is additionally unresolved in the power calculation. The document treats about
five phase attempts from a story-run as independent while the outcome, seed, repository state,
and prior session changes are clustered. Its two-proportion MDE ignores intraclass correlation,
repeated-session dependence, arm-by-condition interaction, and the stated per-condition/per-story
reporting. Thus 1,033 attempts per arm is an optimistic IID count, not a sufficient design size.
Randomized, blocked assignment of policy within story, condition, seed, and repetition is needed;
analysis should use the episode as the unit or cluster-robust/cluster-bootstrap intervals at the
story-run level. The probe must estimate this clustering before it fixes R.

Finally, quality-per-dollar must be an explicitly aggregated estimand. Averaging individual
`quality / cost` ratios over a cost distribution with a $0.076 median and $43.17 maximum can
give a different answer from `sum(quality) / sum(cost + rework)`. The latter, with uncertainty
resampled by randomized story-run block, is the more decision-relevant default. The current
scalar loss also relies on a mean cost that is unknown until the probe and mixes a five-point
quality exchange rate with dollar cost without documenting a scale-invariant estimand.

**Falsifier.** The grid-identification claim is falsified if allocation is not randomized and
blocked before outcomes are known, if any story/condition stratum has material arm imbalance, if
the episode-level test outcome or cost denominator is absent, or if the cluster-aware probe makes
the required R exceed the admitted budget. A cascade-benefit claim is separately falsified if
`always_strong` fails to improve independent test success or costs no more than 1.25 times
`always_fast`; in either case there is no quality or cost margin to arbitrage.

## Claim 4: Phase A powers a future full grid

**Assessment: rejected as phrased; only an MDE scenario is supplied.** The retrospective has no
treated escalation outcomes, so it cannot estimate the policy effect needed for conventional
power. The design is appropriately candid about this, but labels the 694/1,033 IID
two-proportion counts “power” while leaving repetition count, budget, cost gap, outcome
availability, and cluster variance for a later probe. The result is a conditional planning
calculation, not a fully pre-registered powered trial. It should be described that way.

The projection of 6,480 attempts and $5,741 is also only an inference-cost floor. It assumes the
historical task-mixed mean, omits strong-model and rework costs by construction, and cannot
establish the stated quality-per-dollar target. The posterior's observation that flash averaged
$0.1037 while pro averaged $0.0927 in the artifact makes the proposed pair's “fast versus
strong cost premium” an unverified premise, not a baseline fact.

**Falsifier.** The planning scenario is falsified if the probe's blocked, cluster-aware estimate
requires more than the approved budget, if the measured pair lacks both a quality and a cost
gap, or if the independent outcome and lineage coverage gates fail. In that event the full grid
must not be submitted; it is not evidence for a null cascade effect.

## Required disposition before any submission

1. Correct the workflow's registry filter and parquet check command so the documented analysis
path reaches the data it names.
2. Preserve a versioned registry-plus-artifact snapshot for each analysis run, rather than only
recording a live-file hash.
3. Complete I1-I4, then rerun calibration on an unconditional, independently tested cohort.
4. Define randomization blocks, the episode-level estimand, lineage/rework attribution, and
cluster-aware analysis before a probe or grid consumes model budget.
5. Make the probe a formal gate: it must establish the strong model's quality benefit, cost
premium, confidence coverage, trigger rate, and intracluster correlation before R or the budget
is set.

## FINDING

Phase A's null-feasibility decision is justified: the available confidence-completion analysis is
selected, partly outcome-defined, and lacks independent correctness; historical escalation ROI
is unidentified; and the parquet is not a substitute. The current pre-registration is a useful
pause record, but it does not yet define an identifiable or powered cascade experiment because
the primary endpoint precedes the treatment, rework attribution is unspecified, and IID power
ignores task/session clustering. Do not run the grid until the instrumentation, versioned-data,
episode-definition, randomization, and probe gates above are met; otherwise any apparent
quality-per-dollar advantage would be confounded or mechanically constructed rather than
measured.
