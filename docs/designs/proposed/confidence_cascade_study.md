---
status: proposed
---

# Confidence-cascade study — pre-registered grid (Phase B)

**Status: PROPOSED — PAUSED.** This is the pre-registration the workflow
`workflows/repository/confidence_cascade_study.yaml` owes. Its Phase A retrospective
(`docs/reviews/confidence_cascade_retrospective.md`) returned a **null feasibility** result:
the `confidence` signal is a fault flag at `0.0` and flat/non-monotone above it, there is no
escalation history, and the independent outcome is available on 4 attempts. Per the spec's
honesty rule, **the grid is paused**, the narrowing is pre-registered as a consequence, and
the smallest instrumentation that would unblock it is named (§9). The grid itself is fully
specified below so that — once the instrumentation lands — it is a *submission*, not an
authoring exercise.

**Spec:** `workflows/repository/confidence_cascade_study.yaml` (v0.1). **Phase A:**
`docs/reviews/confidence_cascade_retrospective.md`. **Machine artifact:**
`experiments/results/confidence_cascade/retrospective.json`.

> **Pre-registration discipline.** Arms, factor levels, metrics, the comparison, the stopping
> rule and the falsifiers are fixed **now**, before any cell runs. A change to any of them is a
> recorded deviation on the run ledger, not a silent edit. The only currently-open decision is
> the *repetition count*, which §6 derives from the power table; it is fixed at submission.

---

## 1. Question and null hypothesis

**Question.** Does a **confidence-gated cascade** policy — run cheap by default, escalate to a
stronger model when the attempt's own `confidence` falls below a threshold θ — buy **quality
per dollar** over the single-model baselines, on a controlled story grid?

**Null (H₀).** For every arm, quality-per-dollar is no better than `always_fast`. The study is
a **non-inferiority-flavoured** comparison in which `always_strong` is the "buy quality" arm
and the cascades are attempts to buy *most* of that quality at *fast* cost.

**Why "quality per dollar" is the right target.** Phase A established the **baseline cost
shape** ([M], retrospective §5.3): per-attempt cost on the registry is mean **$0.886**,
median **$0.076**, p90 **$1.885** — a heavily right-skewed distribution. An arm that lifts
quality by a few points at a median-cost increase can be Pareto-dominated or Pareto-dominant,
and only a two-dimensional (quality, cost) comparison makes that visible. A single success-rate
number hides it.

**The information requirement (load-bearing rule).** This grid consumes `confidence` as the
causal trigger for the cascade arm. The compiler's `requires`/`produces` gate is satisfied
because `confidence` is measured ([H], `AgenticResult.confidence`,
`src/agentic_dynamics/adapters/opencode.py:113`). Phase A's job was to check that the measurement
is *informative*, not merely *present*; it is not informative today, hence the pause.

---

## 2. What Phase A fixes as given (the pre-registered inputs)

Every number below is from the retrospective's machine artifact
(`confidence_cascade_retrospective/v1`, snapshot
`7eaf225239a53daa2ac047de04f11839cab0d79c6f46f21cc5bf3324b80b7c7a`; query tags Q1–Q6 there).
These are the **only** Phase-A numbers the power and stopping rules may use.

| input | value | provenance |
|---|---:|---|
| baseline `first_pass` rate (all 394 run-ledger attempts) | **0.848** (334/394) | retrospective §2.5 [M] |
| baseline `accepted` rate (all 394 run-ledger attempts) | **0.845** (333/394) | retrospective §2.5 [M] |
| (reference) `first_pass` / `accepted` on the 327 confidence-bearing attempts | 0.914 / 0.911 | retrospective §2.5 [M] |
| baseline completion (`phase_status == "ok"`) rate, pooled | **0.958** (1,288/1,345) | retrospective §5.1 [M] |
| `P(ok)` spread over positive confidence bins | **0.083** | retrospective §5.3 [C] |
| confidence non-monotone above `0.0`? | **yes** | retrospective §2.1 [C] |
| AUC of confidence for `ok`, excluding `0.0` | **0.488** | retrospective §2.2 [C] |
| trigger fraction, θ = 0.3 / 0.5 / 0.7 (registry) | **1.34% / 2.01% / 8.40%** | retrospective §5.2 [C] |
| per-attempt cost, mean / median / p90 | **$0.886 / $0.076 / $1.885** | retrospective §5.3 [M] |
| escalations observed in history | **0** | retrospective §3.1 [M] |
| independent outcome (`test_executed_success`) on confidence-bearing attempts | **4** | retrospective §1 [M] |
| confidence present on `ok` vs `failed` phases | **60.2% vs 26.1%** | retrospective §2.4 [M] |

---

## 3. The grid — factors and arms

**Design:** full factorial over `policy × story × condition`, with `model_pair` pinned (not a
factor) to keep the comparison clean. `policy` is the **arm factor**.

### 3.1 Policy arms (the treatment)

| arm | definition | cost expectation | rationale |
|---|---|---|---|
| `always_fast` | single fast model, no escalation | lowest | the cheap reference |
| `always_strong` | single strong model, no escalation | highest | the quality reference (the ceiling a cascade tries to approach) |
| `cascade_0.3` | fast; escalate to strong iff `confidence < 0.3` | fast + 1.34% escalations* | aggressive trigger |
| `cascade_0.5` | fast; escalate to strong iff `confidence < 0.5` | fast + 2.01% escalations* | median trigger |
| `cascade_0.7` | fast; escalate to strong iff `confidence < 0.7` | fast + 8.40% escalations* | the θ that touches the flat region |
| `cascade_error_gate` **(narrowed)** | fast; escalate to strong iff `confidence == 0.0` | fast + ~1% escalations | the **only** defensible arm Phase A licenses: a fault-handling gate, not a confidence cascade |

\* Trigger fractions are the **retrospective, clean-corpus** rates (Q6). Under perturbation
conditions (§3.3) they are expected to be higher — deliberately, so that the escalation channel
is actually exercised; the pre-registered expectation is stated in §8, not fitted.

**Model pair (pinned):** `fast = deepseek/deepseek-v4-flash`, `strong = deepseek/deepseek-v4-pro`.
Both are `per_token` (dollar-metered) so the run settles through the admission/settlement path
(`experiments/results/settlement/settlements.jsonl`) and the cost term is a **reconciled** number,
not an estimate. This deliberately avoids the subscription-window arms that muddy a dollar
comparison.

> **A pre-registered caution on the model pair.** Phase A's registry costs for these two models
> are nearly identical on workflow attempts (flash mean **$0.1037**, pro mean **$0.0927**, over the
> machine artifact's `per_attempt` rows). If that holds on story attempts, then `always_strong` may not cost
> meaningfully more than `always_fast`, and a cascade has **nothing to arbitrage** — one of the
> grid's own falsifiers (§8, G-F4). The story-run costs must be re-measured by a probe before
> the full grid is submitted (see the overrun lesson below).

### 3.2 Story factor

`story ∈ {task_manager_api, static_site_gen, notification_service}` — the built-in stories
(`src/agentic_dynamics/runtime/story/builtins.py`, `BUILTIN_STORIES`), chosen to span the task
families the corpus already covers. **Pinned** to these three; adding a fourth story changes the
grid revision and requires a recorded deviation.

### 3.3 Condition factor (the escalation-channel stimulator)

`condition ∈ {clean, bad_seed, early_degrade, late_degrade}` — the four `PerturbationCondition`
levels (`src/agentic_dynamics/runtime/story/conditions.py`). `bad_seed` / `early_degrade` / `late_degrade` exist **precisely to
manufacture the low-confidence attempts that make a cascade non-vacuous**; a grid on `clean`
alone would exercise no escalation at all (Phase A: 1.3% trigger). This is a design commitment,
not a post-hoc filter.

### 3.4 Cells

```
cells = arms(6) × stories(3) × conditions(4) × repetitions(R)
```

`R` is the only free parameter, fixed by §6. The **unit of the primary endpoint is the attempt
(phase)**, not the story; each story-run contributes ≈ 5 phase attempts (5 sessions). That
matters for translating the power table into cells.

---

## 4. Metrics

| metric | definition | instrument | evidence class |
|---|---|---|---|
| **`first_pass`** (primary) | fraction of phase attempts that succeed on session 1 | ledger `attempts[].first_pass` (394/394 present) | [M] |
| **`accepted`** | fraction of attempts accepted | ledger `attempts[].accepted` (394/394) | [M] |
| **`test_executed_success`** | fraction of attempts whose tests, run by the **independent** runner, pass | `runtime/test_runner` — sole source of truth | [M] |
| **`cost_inference_usd`** | per-attempt metered inference cost | `attempts[].cost_usd` + settlement | [M] / [C] reconciled |
| **`rework_cost_usd`** | cost to repair an attempt's defect in a later attempt | escalation/retry lineage + commit analysis | [M] |
| **`quality_per_dollar`** | `quality / (cost_inference + rework_cost)`, quality = the chosen endpoint (primary: `first_pass`) | derived | [C] |

**Why `test_executed_success` is the metric that matters.** `phase_status == "ok"` is a
*completion* signal and is partly the same event as `confidence == 0.0` (retrospective §2.3).
`test_executed_success` is the *independently tested* outcome and breaks that coupling. Phase A
showed it is available on only 4 attempts; the grid's first prerequisite (§9) is that it be
emitted on every attempt. **Without it, the grid measures completion, not correctness** — and
the retrospective has already shown completion cannot distinguish the arms.

**Rework cost is required, not optional.** The prior `cap_escalation_measurement` found
`E_x ≈ 11.47/12.51` (n=1) — a downstream defect can cost an order of magnitude more than the
cell. A quality-per-dollar comparison that counts only first-attempt inference cost is
incomplete; the design pre-registers `rework_cost_usd` as part of the denominator and names its
absence a falsifier (§8, G-F7).

---

## 5. Comparison

```yaml
comparison:
  kind: effect_size          # Pareto in (quality, cost); the loss is a scalarized tie-break
  arm_factor: policy         # the arm factor, per the task contract
  loss:
    cost:    1.0             # $ per attempt, normalized by the mean per-attempt cost
    quality: -5.0            # 5 quality units (points of first_pass) are worth 1 mean attempt-cost unit
```

**Pre-registered interpretation.** `loss = cost + (quality term)`; `quality: -5.0` fixes the
exchange rate at **5 percentage points of `first_pass` per mean per-attempt dollar** — stated up
front so the scalarization cannot be tuned after the results. The **primary presentation is the
Pareto plot** (mean quality vs mean cost per arm with bootstrap CIs); the scalar loss is a
tie-break only. An arm is "better" if it is not Pareto-dominated.

**Confound controls (pre-registered):**
- **Stratify by condition.** Perturbation levels change both the base success rate and the
  trigger rate; a pooled arm mean would mix them. Every arm metric is reported per condition.
- **Stratify by story.** Task difficulty differs; report per story.
- **Stratify by model for the cascade arms' escalated subset.** The escalated attempts run on
  the strong model, so an unstratified cascade mean mixes two models — report the
  escalated/non-escalated split explicitly.
- **The differential-missingness control.** If `confidence` remains outcome-dependent, the
  cascade arm's trigger set is selection-biased. Report the `ok`-vs-`failed` confidence-present
  rates per arm and refuse to interpret a cascade whose skew exceeds a pre-registered margin.

---

## 6. Power — what Phase A licenses, and what it does not

**The hard limit.** Phase A **cannot** supply a treatment effect size, because the treatment
(escalating the low-confidence arm) **has never executed** in the corpus (0 escalations, §3.1).
The grid measures its own treatment effect; §6 can only state the **minimum detectable effect**
(MDE) that a given cell count can resolve against the measured baseline.

**Power baseline.** The conservative, all-attempts baseline is `first_pass = 0.848` (334/394).
The confidence-subset rate (0.914) is higher **because of the differential missingness** the
retrospective measured (§2.4) — using it would understate the required n. The pre-registration
uses **p₁ = 0.848**.

**Per-arm attempt counts for a two-proportion test** (`first_pass`, α = 0.05 two-sided,
power = 0.80; standard normal approximation):

| MDE (absolute lift) | target `p₂` | n per arm (attempts) |
|---|---:|---:|
| +2.0 pt | 0.868 | **4,786** |
| +3.0 pt | 0.878 | **2,062** |
| +5.0 pt | 0.898 | **694** |
| +7.5 pt | 0.923 | **280** |
| +10.0 pt | 0.948 | **141** |

At the family-wise α = 0.05 across the grid's 5 comparisons against the `always_fast` reference
(α = 0.01 per comparison), the +5-pt MDE rises to **≈ 1,033 attempts per arm** (and +7.5 pt to
**417**). With ≈ 5 phase attempts per story-run, that is **≈ 207 story-runs per arm** — and the
grid has **6 arms × 3 stories × 4 conditions**, so the repetition count `R` that reaches
≈ 1,033 attempts/arm is **R ≈ 18** (6 arms × 3 stories × 4 conditions × 18 reps × 5 attempts
≈ **6,480 attempts total** = **1,296 story-runs** across the grid; **216 story-runs / 1,080
attempts per arm**).

**The honest power verdict.** Even at a *pairwise* α (no multiplicity correction) the grid needs
**694 attempts/arm** to resolve a +5-point `first_pass` lift; with the correction it needs
**1,033** — i.e. **≈ 1,296 story-runs**. Phase A's measured `P(ok)` spread over the confidence
bins is **0.083**, the *entire* range of the trigger signal is under 9 points, and it is
non-monotone. There is no a-priori reason to expect a cascade to capture even the +5-point MDE.
The grid is therefore **paused not for lack of budget alone, but because the information lever
it depends on is too weak to produce a detectable effect** (retrospective §6, F2/F3/F5).

**Cost envelope [C].** At the measured per-attempt mean **$0.886** (Q6), ≈ 6,480 attempts is
**≈ $5,741 of inference** as a floor — before the strong-model premium, before rework, and
before the campaign's orchestration overhead. The plan's own risk register records that the
prior E4 grid overran its ceiling **3.1×**; **the repetition count must not be scaled from
another model's per-story cost.** Phase B must run a **probe** (a handful of full story-runs per
arm) to re-baseline per-story cost, then set `R` from the measured probe variance — never from
this floor.

---

## 7. Stopping rule

```yaml
stop:
  budget_usd: <set at submission from the probe, not before>
  max_attempts: 1              # one grid, no auto-adaptation until it completes
  uncertainty_threshold: 0.2   # the +5-pt MDE is the operative gate; if the probe variance
                               # cannot support ≤0.2 loss-CI width at R_max, the grid does not run
```

The grid runs **once** and does not adapt within the run (`max_attempts: 1`). `adapt` is left
`manual`: because the arms are pre-registered and the campaign is one grid, coordinate descent
would tune the design against itself. A follow-up campaign (a **separate submission**) may adapt
on the arm with the highest measured uncertainty.

---

## 8. Falsifiers (pre-registered)

Each is a stated kill condition. If it fires, the named claim dies and the grid's interpretation
is constrained to what remains.

| # | claim under test | falsifier (fires ⇒ claim refuted) |
|---|---|---|
| **G-F1** | a stronger model buys quality | `P(test_executed_success)` in `always_strong` is not better than `always_fast` beyond the pre-registered MDE. If so, cascading to it cannot help — the whole rationale collapses. |
| **G-F2** | the cascade improves quality per dollar over `always_fast` | the cascade arm is **Pareto-dominated** by `always_fast` (≤ quality, ≥ cost) at every θ, with non-overlapping bootstrap CIs. |
| **G-F3** | the trigger set is large enough to be identified | the realized trigger fraction at θ = 0.5 is below **5%** on every condition — the cascade arm then differs from `always_fast` on too few attempts to estimate an effect (Phase A already measured **2.0%** on the clean corpus; this falsifier is the pre-registered guard). |
| **G-F4** | there is a cost gap to arbitrage | `always_strong`'s mean per-attempt cost is within the pre-registered margin (≤ 1.25×) of `always_fast`'s — a cascade has nothing to save; the correct policy is simply `always_strong`. |
| **G-F5** | the retained confidence signal is monotone | after the §9 instrumentation fix, `P(outcome \| confidence bin)` remains non-monotone above `0.0` — the signal is still not a probability and the cascade is unwritable in substance. |
| **G-F6** | the arms are not selection-biased | the confidence-present rate stays outcome-dependent (risk ratio `ok`/`failed` > 1.5) within arms; then the trigger set is a biased subsample and no arm comparison is valid. |
| **G-F7** | the cost term is complete | `rework_cost_usd` is unmeasured (no escalation/retry lineage is recorded for the grid) — quality-per-dollar has an unmeasured denominator and cannot be published as a decision number. |

**Disposition rule.** If **G-F1** or **G-F4** fires, the cascade question is closed without a
quality verdict (there is no better or no more expensive model to arbitrage). If **G-F3/G-F5/G-F6**
fire, the grid is **unidentifiable** and reports that, not a null result. If **G-F2** fires
cleanly, the cascade is refuted *on this grid* and the disposition is to prefer `always_fast`.

---

## 9. The smallest instrumentation that would unblock the grid

The grid is blocked by four measurable gaps (retrospective §7). It does **not** need a new
subsystem — it needs these emitted on the same attempt row, which is the **prerequisite gate for
Phase B's submission**:

| # | gap today (measured) | smallest fix | unblocks |
|---|---|---|---|
| I1 | `test_executed_success` on **4** attempts | propagate `runtime/test_runner`'s verdict onto every attempt record | the independent outcome (G-F1, the primary metric) |
| I2 | `confidence == 0.0` **is** the error flag (14/14 failed) | emit `confidence = None` on error and log `error: true` separately, or keep both fields | removes the definitional coupling (G-F5, §2.3) |
| I3 | confidence present on **60.2%** of `ok` vs **26.1%** of `failed` | emit confidence **unconditionally**, with a reason code when unavailable | removes the selection bias (G-F6) |
| I4 | **64.5%** of confidence values are exactly `1.0` | record a variance-bearing score (calibrated or binned self-report) | gives any threshold room to act (G-F3, §5.2) |

**Gate for Phase B:** I1 and I3 must hold on **≥ 300 attempts spanning ≥ 2 models and ≥ 2
conditions**, and I2 or I4 must restore monotone separation (i.e. G-F5 must *not* fire on the
pre-grid corpus). Until then the grid is paused. The gate is itself a measurement: it is run as
an **instrumentation probe**, not as the grid, so no policy is fitted to it.

---

## 10. The narrowed fallback (pre-registered consequence of Phase A)

If the operator chooses to run **something** before the full instrumentation lands, Phase A
licenses **exactly one** arm: `cascade_error_gate` — escalate to the strong model **only when
`confidence == 0.0`** (the error case). This is pre-registered here so it is not a post-hoc
narrowing:

- It is **fault handling**, not a confidence cascade: it acts on the definitional error flag,
  the only cell Phase A found to separate (0/14 `ok`). It is also the **closest existing
  machinery**: `runtime/escalation.py` (opt-in, default OFF, wired into
  `runtime/workflow_runner.py:164`) already escalates on a *failed* attempt along a
  spec-declared ladder; this arm is that ladder gated on a confidence score instead of on
  failure. No spec currently declares a ladder (0 of 388 ledgers), so the arm is a real
  treatment, not a replay.
- Its arms are `{always_fast, always_strong, cascade_error_gate}` and its primary endpoint is
  `test_executed_success` (once I1 lands), because the completion endpoint is what the error
  gate is mechanically coupled to.
- It **cannot** answer the study's original question (does a *graded* confidence threshold buy
  quality per dollar); it can only measure whether catching the error case is cheaper than
  always-strong. The document's headline verdict is unaffected.

---

## 11. Status and gates

| gate | condition | state |
|---|---|---|
| Phase A calibration | confidence separates monotonically above `0.0` | **FAILED** — flat/non-monotone, AUC 0.488 excl. `0.0` |
| Phase A escalation history | ≥ some realized escalations to estimate ROI | **FAILED** — 0 observed |
| Phase A independent outcome | `test_executed_success` on the confidence subset | **FAILED** — n = 4 |
| Phase B instrumentation gate (§9) | I1 + I3 on ≥ 300 attempts, I2/I4 restores separation | **OPEN** |
| Phase B submission | instrumentation gate passed + probe re-baselined `R` and budget | **PAUSED** |

**Deliverables:** this pre-registration (`docs/designs/proposed/`) and the retrospective
(`docs/reviews/confidence_cascade_retrospective.md`). No `src/`, `scripts/`, or `tests/` change
is proposed by Phase A — the §9 fixes are a **separate instrumentation phase**, named here as
the smallest sufficient change, not smuggled into an analysis-only phase.

---

## 12. Reproducibility

The Phase-A inputs in §2 are recomputable from the retrospective's recorded command:

```bash
# pin the snapshot, then run the retrospective (writes the machine artifact cited throughout)
sha256sum /app/experiments/results/registry_index.jsonl   # 7eaf225239a53daa…
cd /app && python3 experiments/results/confidence_cascade/retrospective_analysis.py
```

The MDE table in §6 is recomputable from

```python
from scipy.stats import norm; import math
z_b = norm.ppf(0.80)
p1 = 0.8477157360406091                      # all-attempts first_pass baseline (334/394)
za_pw = norm.ppf(0.975)                      # pairwise, alpha=0.05
za_fw = norm.ppf(1 - 0.05 / (2 * 5))         # family-wise across 5 comparisons, alpha=0.01
for label, za in (("pairwise", za_pw), ("family-wise", za_fw)):
    for d in (0.02, 0.03, 0.05, 0.075, 0.10):
        p2 = p1 + d
        n = math.ceil((za + z_b) ** 2 * (p1 * (1 - p1) + p2 * (1 - p2)) / d ** 2)
        print(label, f"+{d*100:g}pt", n)
```

Every §2 figure carries its retrospective query tag (Q1–Q6) and the pinned registry sha; none is
re-derived here.
