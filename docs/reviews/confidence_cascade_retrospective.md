---
status: accepted
---

# Confidence-cascade retrospective — Phase A of `confidence_cascade_study`

**Role:** Phase A `execute` of the workflow `workflows/repository/confidence_cascade_study.yaml`
(version `0.1`). **Scope:** analysis-only (`proposal_write`) — no `src/`, `scripts/`, or `tests/`
change. **Deliverable partner:** `docs/designs/proposed/confidence_cascade_study.md` (the
pre-registered grid).

**Question this answers.** The machine's load-bearing rule is *to make policies we need
information*. `confidence` is now instrumented ([H], per attempt — `AgenticResult.confidence`,
`src/agentic_dynamics/adapters/opencode.py:113`), so the compiler will accept a `model_cascade`
arm that `requires: [confidence]`. But *instrumented* is not *informative*. This retrospective
asks, from data that already exists and **before** a dollar is spent on a grid:

1. Is `confidence` calibrated against outcomes, at the sample sizes actually available?
2. Is there any escalation history from which to estimate an escalation-ROI curve?
3. How much power does the corpus give a pre-registered grid?

**Honesty rule (binding, from the spec).** If the ledger cannot answer the calibration
question, this document says so and the grid pauses. A null feasibility result is a
first-class finding, not a failure.

> **VERDICT — NULL FEASIBILITY [M].** The measured `confidence` signal carries **no usable
> ordinal information above the single value `0.0`**, and the `0.0` cell is **partly
> definitional** (the same run computes both the signal and the outcome). `P(phase_status =
> "ok" | confidence bin)` is **flat and non-monotone** above `0.0` — 0.917–0.985 across every
> bin with n ≥ 5; the AUC of confidence as a predictor of the completion outcome **excluding the `0.0`
> cell is 0.488** (worse than a coin flip) with a Spearman ρ of **−0.009**. Confidence is also
> **missing differentially by outcome** (present on **60.2%** of `ok` phases vs **26.1%** of
> `failed` ones — risk ratio **2.31**), so the calibration subsample is success-biased. There
> is **zero escalation history** (0 `escalation_from`/`escalation_to`/`parent_attempt_id`
> across 388 run ledgers), so no retrospective ROI is measurable. The pre-registered grid in
> the partner document is therefore **PAUSED** pending the smallest instrumentation that would
> make the calibration question answerable (§7).

---

## 0. Reproducibility contract and the pinned snapshot

**Every number below is produced by a recorded command.** The analysis is collected in one
script (a *process* artifact — `experiments/results/` is gitignored, so it is not a tracked
deliverable but it *is* durable on the data root):

```bash
# 0. Pin the snapshot FIRST. The live registry is unversioned and MUTATING — see the drift note.
sha256sum /app/experiments/results/registry_index.jsonl
wc -l /app/experiments/results/registry_index.jsonl
ls /app/experiments/results/kb/*.json | wc -l

# 1. The whole retrospective (queries Q1-Q6) + the machine artifact it cites
cd /app && python3 experiments/results/confidence_cascade/retrospective_analysis.py
#   writes experiments/results/confidence_cascade/retrospective.json
#   (schema confidence_cascade_retrospective/v1; carries the raw per-attempt rows so any
#    aggregate below can be recomputed independently)

# 2. The negative control: the story/session parquet (USE THE FLAG, never positional "check")
cd /repo && python3 scripts/sync_data.py --check

# 3. The prior baseline is CITED, not recomputed (Q4)
python3 -c "import json;d=json.load(open('/app/experiments/results/cap_cascade_retrospective.json'));print(d['baseline'])"
```

**Pinned snapshot** [M]. Every count in this document is *as of this snapshot*:

| field | value |
|---|---|
| registry path | `/app/experiments/results/registry_index.jsonl` |
| **registry sha256** | `7eaf225239a53daa2ac047de04f11839cab0d79c6f46f21cc5bf3324b80b7c7a` |
| registry lines | **55,079** |
| kb artifacts (`experiments/results/kb/*.json`) | **24,263** |
| run ledgers (`experiments/results/workflows/**/*.json`) | **388** |
| confidence observation window (min–max `observed_at`) | **2026-08-15 → 2026-09-21** (n=1,328 dated of 1,345) |

**Data-drift note (load-bearing).** The *prior* phase's inventory pinned this registry at
`cf64fc97…` / 55,077 lines. At execute time it is `7eaf2252…` / 55,079 lines. The registry is
**unversioned and grew by two rows between phases**. `7eaf2252…` is a *snapshot identifier*, not
a durable guarantee: a re-run tomorrow will differ. This is why the machine artifact records
`generated_at` and the sha, and why the grid design (§5 of the partner doc) cannot treat
Phase A's exact counts as a fixed fixture.

### How the two data roots fit together

| root | role | tracked? |
|---|---|---|
| `/repo` | the git checkout this phase commits into — specs, docs, the **parquet**, `data_manifest.json`, the fixture registry | yes |
| `/app` | the live data root — the **registry index**, the **kb artifacts** (the values), the **run ledgers** | **no** |

The domain context names `experiments/results/registry_index.jsonl` filtered to
`source_type == 'ledger_attempt'`. That path is absent from `/repo` (gitignored) and, more
importantly, **the filter matches zero rows even in the live registry** [M]:

| query (Q1) | result |
|---|---|
| `source_type == 'ledger_attempt'` | **0 rows** |
| `source_type == 'fact'` (the layer that actually carries attempt signals) | **46,401 rows** |

The attempt-level signal is emitted by the newer `attempt_facts/v1` reducer
(`src/agentic_dynamics/control/reducers/attempt_facts.py`) as `source_type == "fact"`, **not**
by the `ledger_ingestion` producer the spec context named. Both facts are reported here as
findings so no future reader concludes "no data" from the empty filter. Registry `source_type`
counts (Q1): `fact` 46,401 · `finding` 4,093 · `None` 1,470 · `code` 1,073 · `spec` 455 ·
`story` 330 · `meta_session` 261 · `review` 242 · `decision` 197 · `reflection` 124 ·
`wave_verdict` 123 · `report` 120 · `flag` 102 · `policy` 34 · `pattern` 32 ·
`context_snapshot` 11 · `actuation` 11.

### The join (values are NOT in the index)

The registry index carries **identities and content hashes only** — never values. A row's
`knowledge_id` names a durable artifact
`/app/experiments/results/kb/<knowledge_id>.json` whose `text` field is a JSON *string*; the
value is `json.loads(artifact["text"])["value"]`. An attempt key is parsed from
`source_uri == fact://attempt/<cell>:<phase>:<runhash>/<predicate>`. The analysis script builds
`attempt_key -> {predicate: knowledge_id}` then resolves each predicate through its artifact.
**Null-not-zero:** an attempt whose artifact is missing or unparseable is *absent* (reported as
a coverage gap), never imputed as `0.0` confidence and never as a failed outcome.

---

## 1. Coverage — the sample sizes actually available (Q1, Q2)

Before any metric, the coverage. Q1 counts distinct attempts whose current `fact` rows carry
each predicate; Q2 resolves each predicate to a value through its kb artifact.

| predicate | attempts (Q1) | resolved to a value (Q2) |
|---|---|---|
| `attempt_model` | 2,369 | 2,361 |
| `phase_status` | 2,361 | **2,353** (`ok` 2,140 · `failed` 211 · `awaiting` 2) |
| `attempt_cost_usd` | 2,315 | 2,315 |
| **`attempt_confidence`** | **1,345** | **1,345** |
| `phase_test_verified` (the *independent* outcome) | **132** | **132** |
| `attempt_confidence` + `phase_status` (the calibration sample) | **1,345** | **1,345 (100% paired)** |
| `attempt_confidence` + cost + model + status | 1,337 | 1,337 |
| `phase_test_verified` + `attempt_confidence` | **4** | **4** |

The distinct attempt universe is **2,505**. Three facts drive the rest of this document:

1. **The calibration sample is n = 1,345**, and it is 100% paired with the completion outcome —
   good, in the sense that nothing is silently dropped from the pairing.
2. **The independent outcome is unusable at scale:** `phase_test_verified` reaches 132 attempts,
   but only **4** of those also carry `confidence`. Calibration against *test-executed
   correctness* is **infeasible** from this corpus. Only calibration against *completion*
   (`phase_status`) is possible.
3. **The completion outcome is partly the same run that computes the signal** (see §2.3).

---

## 2. Calibration — confidence vs outcome (Q2)

### 2.1 The pooled calibration table [M]

Bins are left-open/right-closed; the `[0.0]` singleton is separated because it is the only
candidate separating cell and because of the definitional coupling in §2.3. `P(ok)` is
`phase_status == "ok"`.

| confidence bin | n | ok | P(ok) |
|---|---:|---:|---:|
| `[0.0]` | 14 | 0 | **0.000** |
| `(0.0, 0.2]` | 4 | 4 | 1.000 |
| `(0.2, 0.3]` | 0 | 0 | — |
| `(0.3, 0.4]` | 5 | 5 | 1.000 |
| `(0.4, 0.5]` | 12 | 11 | 0.917 |
| `(0.5, 0.6]` | 19 | 18 | 0.947 |
| `(0.6, 0.7]` | 66 | 65 | 0.985 |
| `(0.7, 0.8]` | 94 | 91 | 0.968 |
| `(0.8, 0.9]` | 165 | 160 | 0.970 |
| `(0.9, 1.0]` | 966 | 934 | 0.967 |

**Read plainly.** Only the `[0.0]` cell separates (0/14). Above `0.2`, `P(ok)` is flat in the
band **0.917–0.985** and **non-monotone** (it rises to 0.985 at `(0.6,0.7]`, then *falls* at
`(0.7,0.8]` and again at `(0.9,1.0]`). A threshold policy needs *monotone* separation to have
anything to act on; this signal does not have it.

### 2.2 Discrimination, with and without the 0.0 cell [C]

| statistic | including `0.0` | excluding `0.0` |
|---|---:|---:|
| n | 1,345 | 1,331 |
| **AUC** (confidence as a score for `ok`) | 0.614 | **0.488** |
| **Spearman ρ** | +0.093 | **−0.009** |

The AUC of 0.614 *including* the zero cell is entirely the 14 error cases. Remove them and the
signal is **worse than chance** (0.488) with essentially zero rank correlation (ρ = −0.009).
This is the most compact statement of the null: **confidence contains no ordinal information
about the completion outcome above `0.0`.**

### 2.3 The `0.0` cell is partly definitional [H]

`opencode.py:113` computes `confidence` as `0.0` on session error, else `tests_passed/tests_total`
when tests ran, else the tool-call success fraction, else `None`. A phase that errored therefore
tends to receive *both* `confidence == 0.0` **and** `phase_status == "failed"` **by construction**.
All 14 `confidence == 0.0` paired attempts are `failed`; and of the 18 attempts below `0.3`, only
4 are `ok` (and those sit in `(0,0.2]`, not at 0). So the one "calibrated" cell is largely
arithmetic coupling, not prediction. The honest claim is: **confidence is a fault flag, not a
probability.** Above the fault flag it carries no signal.

### 2.4 The signal is missing differentially by outcome — a selection bias [M]

The calibration subsample is *not* representative of the outcome universe:

| outcome class | total attempts | with confidence | confidence-present rate |
|---|---:|---:|---:|
| `ok` | 2,140 | 1,288 | **0.602** |
| `failed` | 211 | 55 | **0.261** |
| `awaiting` | 2 | 2 | 1.000 |
| **risk difference (ok − failed)** | — | — | **+0.341** |
| **risk ratio (ok / failed)** | — | — | **2.31** |

`confidence` is **2.3× more likely to be present on a completed phase than on a failed one** —
156 of the 211 failures (74%) carry **no** confidence value at all. Any calibration, and any
policy trained on the confidence-bearing subset, is therefore conditioned on a
success-correlated selection. This is a second, independent reason the signal cannot support a
retrospective threshold fit.

### 2.5 Ledger corroboration — a second data path says the same thing [M]

The run ledgers are the runner's typed `AttemptRecord`s — a different artifact from the fact
layer. They carry 394 attempt rows (327 with confidence) and, crucially, the **quality fields
the grid wants**: `first_pass` and `accepted` (394/394 present), `status` (394/394), `cost_usd`
(394/394), and `test_executed_success` (**only 4**).

The same flat, non-monotone shape reproduces:

| confidence bin | n | P(status=ok) | P(first_pass) | P(accepted) |
|---|---:|---:|---:|---:|
| `[0.0]` | 8 | 0.000 | 0.000 | 0.000 |
| `(0.0, 0.2]` | 4 | 1.000 | 1.000 | 1.000 |
| `(0.3, 0.4]` | 1 | 1.000 | 1.000 | 1.000 |
| `(0.4, 0.5]` | 3 | 0.667 | 0.667 | 0.667 |
| `(0.5, 0.6]` | 1 | 1.000 | 1.000 | 1.000 |
| `(0.6, 0.7]` | 12 | 1.000 | 1.000 | 1.000 |
| `(0.7, 0.8]` | 24 | 0.917 | 0.917 | 0.917 |
| `(0.8, 0.9]` | 29 | 0.897 | 0.931 | 0.897 |
| `(0.9, 1.0]` | 245 | 0.939 | 0.939 | 0.939 |

The table is over the **327 confidence-bearing attempts**; pooled there, `first_pass` =
**0.914** (299/327) and `accepted` = **0.911** (298/327). Over **all 394** attempts the rates
are **0.848** (334/394) and **0.845** (333/394). The gap is the *same selection bias* as §2.4 —
the confidence subset is the more successful one — which is why the partner design's power
baseline uses the conservative **all-attempts 0.848**, not 0.914. Neither rate moves with
confidence above `0.0`. `test_executed_success` is `True` on 4 attempts and `None` on 390, so
the independent-correctness calibration is infeasible here too. The two paths agree, which
raises confidence in the *negative* result.

---

## 3. Escalation economics — a zero-history finding (Q3, Q4)

### 3.1 There is no escalation history at all [M]

Across all **388** live run ledgers (394 typed `attempts` rows):

| field | rows with a value |
|---|---:|
| `escalation_from` | **0** |
| `escalation_to` | **0** |
| `parent_attempt_id` | **0** |
| `attempt_number > 1` (a retry, not an escalation) | **0** |

**What exists, precisely (a correction to the prior spec's claim).** A **confidence-triggered**
cascade does not exist. What *does* exist is an opt-in, **failure-triggered**, ladder-bounded
escalation config — `runtime/escalation.py` (`EscalationPlan.from_params`, step 9 / G-27),
wired into `runtime/workflow_runner.py:164`: a **FAILED** agent attempt escalates to the next
model in a spec-declared `workflow.params.escalation.ladder`. It is **default OFF**; by grep,
**0** specs declare a ladder and **0 of 388** run ledgers mention one — which is exactly why
the corpus records 0 escalations. The distinction is load-bearing for this study: the existing
mechanism triggers on *failure*, whereas the cascade arm triggers on *confidence*; and the
existing ladder is itself a candidate arm (see the design's §10, `cascade_error_gate`). The
earlier `cap_confidence_cascade.yaml` comment that "`model_cascade` has no implementation" was
true when written; the failure-ladder has since landed, but it is unwired and is not a
confidence cascade.

**Consequence:** an escalation-ROI curve is **counterfactual only**. Any "ROI" presented as
*measured* from this corpus is refuted by construction: on the would-escalate subset the
stronger model was never actually run, so its cost and outcome are genuinely unknown. This
matches the independent findings in `docs/reviews/workflow_metrics_findings.md`
("escalation rate — not measurable") and `docs/reviews/retry_worthiness_findings.md`
("exactly one real retry event in the entire corpus").

### 3.2 The prior baseline (cited, not recomputed) [C]

The prior artifact `experiments/results/cap_cascade_retrospective.json` (schema
`cap_cascade_retrospective/v1`, spec `cap_confidence_cascade@0.1`, over 126 runs / 462 phases)
already established the measured half:

| quantity | value |
|---|---:|
| confidence coverage (prior corpus) | 0.7835 (362/462) |
| baseline **cost per verified outcome** (`phase_status == "ok"`) | **$1.8109** (`$785.9273` / 434) |
| baseline verified-success rate | 0.9394 (434/462) |
| escalation trigger rate at θ = 0.3 / 0.5 / 0.7 | 1.66% / 3.59% / 10.77% |
| per-model trigger range at θ = 0.3 | 0.2857 |
| `null_testable` | **false** (regret is 0 by tautology — nothing was ever escalated) |

This document **cites** that baseline rather than recomputing a competing number. What is new
here is the *calibration* and *feasibility* analysis, not a second baseline.

### 3.3 The `E_x` multiplier is not a cascade ROI [P]

`docs/experiments/results/cap_escalation_measurement.md` measures **E_x = 11.47** (sol) /
**12.51** (sonnet), **n = 1 per model**. That is the *downstream-defect-fix* multiplier (cost to
repair a defect later / original cell cost) — a **different quantity** from a cascade ROI, and
at n = 1 it cannot anchor a power calculation. It is recorded here only so it is not mistaken
for a measured escalation return.

---

## 4. The parquet cannot carry the study (Q5)

`python3 scripts/sync_data.py --check` (the **flag**; the positional `check` silently runs
`sync` and must never be used) reports the parquet **stale in this checkout**
(`resolved-input identity mismatch`; `sessions.parquet has 1027 rows, expected 0`) because the
canonical story payloads are absent from `/repo`. More fundamentally, the parquet schemas do
not carry the signal at all:

| parquet | rows | studied fields present |
|---|---:|---|
| `sessions.parquet` | 1,027 | **none** of `confidence`, `perturbation_strength`, `test_executed_success`, `first_pass`, `accepted` |
| `stories.parquet` | 207 | **none** of the above |

The parquet columns are cost/token/cache/tests aggregates (`session_id`, `story_name`, `model`,
`cost_usd`, `tests_passed`, `tests_total`, `cache_hit_rate`, …, `code_lines`). **Any design that
assumes the parquet supplies `confidence` or `test_executed_success` is refuted.** The compacted
tracked registry is also value-free by construction: `experiments/data_manifest.json`
(sha256 `bf553208…`, 18,392 rows / 17,893 current) and the test fixture
`tests/fixtures/corpus/registry_index.jsonl` (sha256 `4714ffaf…`, 19,049 rows) carry identities
and content hashes, never values.

**A structured field channel exists but is not at scale [M].** The kb artifacts carry top-level
`confidence`, `test_executed_success`, and `perturbation_strength` fields (populated by the
story/session producers, distinct from the `attempt_confidence` predicate). Non-null counts
across 24,263 artifacts:

| field | non-null |
|---|---:|
| `confidence` | **61** |
| `test_executed_success` | **165** |
| `perturbation_strength` | **144** |

This channel cannot substitute for the fact layer.

---

## 5. Available power — what a grid could and could not be sized on (Q6)

### 5.1 The confidence distribution is one dominant point mass [M]

Of the 1,345 paired attempts:

| mass | n | share |
|---|---:|---:|
| exactly `1.0` | 868 | **64.5%** |
| exactly `0.0` | 14 | 1.0% |
| distinct values | 226 | — |
| **mean `P(ok)` over all paired** | — | **0.958** |
| `P(ok)` among `confidence > 0` | 1,331 | **0.968** |

### 5.2 Trigger rates — how much a threshold would even touch [C]

Fraction of the paired sample strictly below each candidate θ (registry path; the ledger path
is shown for corroboration):

| θ | registry: below / n | registry rate | ledger: below / n | ledger rate |
|---|---:|---:|---:|---:|
| 0.3 | 18 / 1,345 | **1.34%** | 12 / 327 | 3.67% |
| 0.4 | 22 / 1,345 | 1.64% | 12 / 327 | 3.67% |
| 0.5 | 27 / 1,345 | 2.01% | 15 / 327 | 4.59% |
| 0.7 | 113 / 1,345 | 8.40% | 29 / 327 | 8.87% |
| 0.9 | 371 / 1,345 | 27.58% | 80 / 327 | 24.46% |

For every *useful* θ in the interior (`0.3`–`0.5`) a cascade would act on **1–2%** of attempts;
θ = 0.7 touches 8.4% but mostly reclassifies the flat region; θ = 0.9 begins to split the main
mass, i.e. the threshold stops meaning "low confidence". A threshold policy has almost no room
to act.

### 5.3 Separation and effect sizes actually available to size a grid [C]

| quantity | value |
|---|---:|
| bins above `0.0` carrying n ≥ 5 | 7 |
| `P(ok)` min / max over those bins | 0.917 / 1.000 |
| **`P(ok)` spread over positive mass bins** | **0.083** |
| non-monotone above `0.0`? | **yes** |
| per-attempt cost, registry, attempts with cost (n=1,337) | mean **$0.886**, median **$0.076**, p90 **$1.885**, max **$43.17** |
| per-attempt cost, run ledgers, with confidence (n=327) | mean **$0.931**, median **$0.057**, p90 **$2.185**, max **$21.91** |

**The power consequence, stated honestly.** A Phase B grid's *measured* effect size cannot be
derived from Phase A, because the grid's treatment (escalate the low-confidence arm) **has never
executed** — there is no observed treated outcome. What Phase A *can* supply, and all the
pre-registration is allowed to use, is: the **baseline** success rate (**`first_pass` 0.848** /
`accepted` 0.845 over all 394 ledger attempts; the confidence subset is higher at 0.914/0.911
only because of the selection bias in §2.4), the **trigger fraction** at each θ (§5.2), and the
**per-attempt cost distribution** (§5.3). Any Phase B power statement must be built from those
three plus an *assumed* treatment effect that Phase B itself measures — it cannot be inherited
from a retrospective that contains no treatment.

### 5.4 Stratification (pooled averages hide a mixture) [M]

The pooled curve averages over models and run vintages (10 distinct models in the paired
sample; `observed_at` spans 2026-08-15 → 2026-09-21). Per-model cells with n ≥ 5 still show no
monotone separation; e.g. `deepseek-v4-pro` (n=477) rises 1.000 → 1.000 → 1.000 → 0.963 →
0.997, and `deepseek-v4-flash` (n=429) *falls* from 0.955 to 0.934 into its top bin. One model
(`openai/gpt-6-astra`) has n = 1 and is reported as below-minimum rather than pooled. The
stratified view corroborates the pooled null; it does not rescue it.

---

## 6. Falsifier disposition (from `notes/plan.md`)

| # | hypothesis under test | disposition |
|---|---|---|
| F1 | `confidence` is calibrated against the outcome | **FIRED.** P(ok) is flat (0.917–0.985) and non-monotone across the mass bins above `0.0`; only `[0.0]` separates. |
| F2 | a threshold has room to act | **FIRED.** Trigger rate 1.34%/2.01%/8.40% at θ=0.3/0.5/0.7; 64.5% of the sample sits at exactly 1.0. |
| F3 | confidence predicts independently of the `0.0` cell | **FIRED.** AUC excluding `0.0` = 0.488, ρ = −0.009; all separation is the definitional error cell. |
| F4 | escalation economics is measurable from history | **FIRED (by construction).** 0 escalations / 0 lineage / 0 retries; ROI is counterfactual only. |
| F5 | the corpus can fit a threshold with power | **FIRED.** Paired n=1,345 but dominated by one point mass; the independent outcome has n=4; and the signal is missing differentially by outcome (RR 2.31). |
| F6 | the parquet can carry the study | **FIRED.** None of the studied fields exist in either parquet. |

**Disposition rule applied:** because F1/F3/F5 fired, this retrospective records a **null
feasibility** result, and the grid in the partner document is **paused / narrowed**, with the
narrowing stated as a pre-registered consequence.

---

## 7. The smallest additional instrumentation that would unblock the study

Per the spec's instruction — *do not fabricate a signal; design the smallest instrumentation
that would answer the question* — the gap is precise and small. Phase A does **not** need a new
subsystem; it needs **four fields emitted on the same attempt row** that today are absent, rare,
or coupled:

1. **`test_executed_success` on every attempt, not 4 of 394.** The independent outcome is
   already produced by `runtime.test_runner` (the sole source of truth) and is already a
   declared ledger field; it is simply not carried through for most attempts. Confirming it on
   the confidence-bearing subset is the single change that turns "calibration against
   completion" into "calibration against correctness". — *[M] the field exists; only its
   population is missing.*
2. **Decouple `confidence` from the `0.0` fault flag, or record the flag separately.** Either
   emit `confidence` as `None` (not `0.0`) on session error and log an explicit `error` boolean,
   or keep both — so the `0.0` cell stops being the same event as the `failed` outcome. Without
   this, any future calibration re-measures the identity in §2.3. — *[H] the coupling is read
   from `opencode.py:113`.*
3. **Report missingness, or make coverage outcome-independent.** Today confidence is present on
   60.2% of `ok` and 26.1% of `failed` phases. Emitting confidence **unconditionally** (with a
   reason code when it is unavailable) removes the selection bias that makes the calibration
   subsample unrepresentative. — *[M] measured in §2.4.*
4. **Dynamic range.** 64.5% of confidence values are exactly `1.0`. A signal that is a point mass
   at one end cannot be thresholded. The smallest useful change is to record a **calibrated**
   score (or a binned self-report) whose variance is not collapsed, or to accept that the only
   defensible policy is the `0.0`-vs-rest error gate (the narrowed arm in the partner design).

Until (1)–(3) hold on a few hundred attempts, the calibration question is **unanswerable**, and
this retrospective's verdict stands. The instrumentation is *measurement*, not policy, so it
respects the load-bearing ordering.

---

## 8. Provenance

**Machine artifact:** `experiments/results/confidence_cascade/retrospective.json`
(schema `confidence_cascade_retrospective/v1`, produced by
`experiments/results/confidence_cascade/retrospective_analysis.py`). It carries the pinned
snapshot, Q1–Q6 blocks, and the **raw per-attempt rows** (`per_attempt`, n=1,345) so any
aggregate in this document can be recomputed independently.

**Snapshot:** registry sha256 `7eaf225239a53daa2ac047de04f11839cab0d79c6f46f21cc5bf3324b80b7c7a`,
55,079 lines, 24,263 kb artifacts, 388 run ledgers — as of the `generated_at` recorded in the
artifact. **Prior phase pinned `cf64fc97…` / 55,077 lines**; the drift is itself a finding.

**Tracked sources cited:** `experiments/data_manifest.json` (`bf553208…`, 18,392 rows / 17,893
current); `tests/fixtures/corpus/registry_index.jsonl` (`4714ffaf…`, 19,049 rows);
`workflows/repository/confidence_cascade_study.yaml`; `experiments/definitions/cap_confidence_cascade.yaml`;
`docs/architecture/current/2026-08-14_experiment-spec-and-compiler-design.md`;
`src/agentic_dynamics/adapters/opencode.py:113`;
`src/agentic_dynamics/control/reducers/attempt_facts.py`;
`docs/reviews/workflow_metrics_findings.md`; `docs/reviews/retry_worthiness_findings.md`;
`docs/experiments/results/cap_escalation_measurement.md`; `docs/reviews/cap_e2_e3_review.md`.

**Live sources read:** `/app/experiments/results/registry_index.jsonl`;
`/app/experiments/results/kb/*.json`; `/app/experiments/results/workflows/**/*.json`;
`/app/experiments/results/cap_cascade_retrospective.json`.
