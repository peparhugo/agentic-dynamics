# cap_2b — pre-registration (p0): the randomized static-vs-adaptive pilot

**Status: accepted · PRE-REGISTERED — committed BEFORE any cell runs.**
**Campaign:** `cap_2b` (`workflows/repository/cap_2b.yaml`, SHA256
`470b6a87b249fb40db6de58f3a28e8238f2a8c65a864090bcf599c1efd51ffa2`).
**Design:** `docs/designs/current/cap_2b_design.md` §2 (SHA256 `218fbd9b20c8512ad0d27797e7fe0234417ab66a9384dbc7675173920b13c0a5`).
**Predecessor data (all measured):** the rerun3 control verdict
(`cap_2a_rerun3.md`, SHA256 `b54958718cd57af2c6036b6d51d9c7dff865f80f0c481c529bc69d42dec422d4`;
score JSON `experiments/results/cap_2a_rerun3/cap_2a_rerun3_score_20260826T050000Z.json`, SHA256
`08b6fb3297a5a41a3b81b4abc69b68cf86dde108918a244b4cf4fe6689a66a09`) and the measured-E_x verdict
(`cap_escalation_measurement.md`, SHA256 `fc9d4f48d6440010177620ffaf9a25b2e04e058ff0f5ba698f9afe7691458b61`;
score JSON `experiments/results/cap_escalation_measurement/cap_escalation_measurement_score_20260826T125726Z.json`,
SHA256 `6d3c7a7c48ba718b0ccd7d9e1f3a9898336ed89c83ba791274dca7330b890329`).
**Stimulus set:** `cap_2a_cell_clean@0.1` (SHA256 `65730a228e238513747fdd658679d4b89389140f92f2a26021170cab338cbba0`),
`cap_2a_cell_critical@0.1` (SHA256 `6ecb2bd93e8718c8c42382f648e859672c649de761e46ba74c2d7a460721e4d7`),
`cap_2a_cell_style@0.1` (SHA256 `eaf7e806ce8f3b7f49f3f804904df513887e58387a73e1dc2ffe1337fd994ab4`).
**Cell model:** `deepseek/deepseek-v4-pro` (the stimulus set's model — unchanged from rerun3).

> **The registration rule:** nothing in §1–§6 may be redefined after this commit. A deviation
> from this pre-registered plan — a redefined margin, a reseeded assignment, a dropped cell — is
> a **FAILED finding** in p5, not a limitation. The assignment table (§4) is the canonical
> record; the seed is the reproducibility key.

---

## 1. Primary outcome metric + secondary

**Primary — cost-per-accepted-outcome (cpvo) per arm.** The site's own KPI
(`cost_per_outcome_definition` in the rerun3 score JSON):

```
cpvo_arm = (Σ measured cell cost over the arm) / (Σ accepted outcomes over the arm)
```

- **Total cost** = Σ `cost_usd` per cell (the measured, ledgered run cost).
- **Accepted outcome** (per cell) = `test_executed_success == true` (the independent
  `runtime.test_runner` verdict on the final commit) **AND**
  `defect_present_on_final_commit == false` (the post-hoc evaluator's defect determination on
  the same immutable commit). Both must hold; a cell failing either is **not accepted**.
  This is the rerun3 `accepted_outcome_definition`, verbatim.

**Secondary — verified-success rate per arm.**

```
verified_success_rate_arm = (accepted outcomes in the arm) / (cells in the arm)
```

Denominator discipline (from the rerun3/rerun2 practice, carried forward): a cell that was
stopped by the budget/SLA guard or flagged (graph-down/analyzer-down) is reported **in its
denominator** with its status printed, never silently dropped; a cell scored under a different
arm than its assignment is **invalid** (p3 guard).

---

## 2. Non-inferiority margin + justification (the measured effect prior)

**Margin (both legs must hold for non-inferiority):**

```
NI  ⟺  cpvo_adaptive ≤ 1.10 × cpvo_static
   AND  verified_success_rate_adaptive ≥ verified_success_rate_static − 5 percentage points
```

(equivalently: cpvo ratio `r = cpvo_adaptive / cpvo_static ≤ 1.10`, and the success-rate gap
`succ_static − succ_adaptive ≤ 0.05`.)

**Justification from the measured effect prior** (all four quantities are MEASURED):

| quantity | value | derivation | artifact field |
|---|---|---|---|
| applied-rework cost premium | **$0.005719** | `0.014668 − 0.008949` (critical-gate minus critical-baseline cell cost) | rerun3 score JSON `cells[]` |
| downstream defect cost base | **$0.004021** | `0.112588 / 28.0` (re-derived, not copied) | escalation score JSON `base_downstream_defect_cost_usd` |
| avoided escalation at E_x = 11.47 | **$0.046109** | `11.4671 × 0.004021` | escalation score JSON `loss_table` row `E_x=11.4671` |
| value/premium ratio | **8.06×** | `0.046109 / 0.005719` | — |

One applied rework converts a rejected outcome into an accepted one at a **$0.005719** premium
that avoids **~$0.0461** of downstream escalation — an **~8×** value/premium ratio. The margin
is chosen so that the adaptive arm must be *materially* worse before we decline non-inferiority,
and the measured prior puts the arms far from that boundary:

- **Cost leg.** Under the measured effect the cpvo ratio is **0.8104** (adaptive ~19% *cheaper*:
  `$0.031477 / 3 accepted` = $0.010492 vs `$0.025895 / 2 accepted` = $0.012948, rerun3
  `cost_per_outcome`). The margin allows the ratio to rise to **1.10** — **0.29 of headroom** on
  the ratio axis (a 29-percentage-point band where the adaptive arm would still be judged
  non-inferior). Because the value the conversion creates (8.06× the premium) is an order of
  magnitude larger than the 10% cost allowance, a 10% cpvo inflation would require the adaptive
  arm to lose most of its conversion value — the exact failure the ~8× ratio says is
  implausible.
- **Success leg.** Under the construction (only the critical stimulus bears a defect, base rate
  1/3) static success is 2/3 and adaptive success is `2/3 + q/3` with `q` the conversion
  probability on defect-bearing cells. For any `q ≥ 0` the gap `succ_static − succ_adaptive =
  −q/3 ≤ 0`, so adaptive is never *worse* on success in expectation; the 5pt margin is the
  allowance for a rework that breaks something. The measured effect (`q = 1.0`, the 1/1 applied
  rework hit) puts adaptive **33.3pts ahead** — **38.3pts of slack** to the margin.

The 10% cost leg and the 5pt success leg are the registered, unchangeable margin.

---

## 3. Power analysis (n of DEFECT-BEARING cells, 80% power, α = 0.05 one-sided)

**Base rate:** the stimulus family is `{clean, critical, style}` with the defect base rate
**1/3 by construction** — only `cap_2a_cell_critical@0.1` deliberately introduces one real
defect (cell-spec YAMLs; confirmed in rerun2/rerun3: clean/style cells are defect-free nulls,
critical cells carry the inverted-boundary defect). The rerun3 verdict is explicit that the
value signal concentrates in **defect-bearing changes**, so the pilot's **n is counted in
defect-bearing cells, not in all cells**.

**Model.** Per the construction, only defect-bearing (critical) cells differentiate the arms:
static critical cells are rejected (defect present, no rework), adaptive critical cells apply
the rework proposal (one bounded pass) and convert to accepted with probability `q`. Non-defect
cells are provable nulls. The power of the decision rule is therefore driven by the **cpvo
ratio leg**; the success leg never binds (`succ_static − succ_adaptive = −q/3 ≤ 0 < 0.05` for
all `q ≥ 0`, confirmed at `0.00000` binding rate in simulation).

**Parameters (all measured):**

| parameter | value | source |
|---|---|---|
| adaptive critical-cell cost mean | $0.014668 = $0.008949 + $0.005719 | rerun3 `cells[]` |
| static critical-cell cost mean | $0.008949 | rerun3 `cells[]` |
| non-defect cell cost mean | $0.0085 (clean) / $0.0084 (style) | rerun3 `cells[]` (both arms) |
| conversion probability `q` | **1.0 (measured 1/1)** — sensitivity 0.8 / 0.5 | rerun3 `cap2a_r3_critical_gate` applied rework → defect fixed |
| cost noise | LogNormal σ = 0.25 (pooled CV across rerun2+rerun3 measured cells: 0.255 clean / 0.297 critical / 0.180 style, pooled 0.249) — sensitivity σ = 0.35 | rerun2 + rerun3 cell costs |

**Power simulation** (100,000–300,000 trials per cell; probability the pre-registered decision
rule concludes NI under the measured-effect alternative; α = 0.05 one-sided per leg):

| defect-bearing cells (`2m`) | total cells (`6m`) | power, measured effect (q=1.0, σ=0.25) | power, q=0.8 | power, conservative q=0.5 | power, q=0.5 σ=0.35 |
|---|---|---|---|---|---|
| 4 | 12 | 0.997 | 0.922 | 0.725 | 0.703 |
| **6** | **18** | **0.999** | **0.959** | 0.779 | 0.749 |
| 8 | 24 | 1.000 | 0.977 | 0.815 | 0.784 |

**Registered commitment:** **n ≥ 6 defect-bearing cells → ≥ 18 total cells** (base rate 1/3),
**repetitions per block = 3 per arm** (6 cells per stimulus block). Under the measured effect
this achieves **power 0.999 ≥ 0.80** at α = 0.05 one-sided; the ≥0.80 threshold holds through
the q = 0.8 sensitivity (0.959) and is only missed under the deliberately-halved conversion
assumption (q = 0.5 → 0.779). The pre-registered contingency (§5) covers the "rule does not
decide" case by extending defect-bearing cells under the same block scheme — never by changing
the margin.

**Analytic boundary (for audit):** with the measured costs and no noise, the cpvo ratio is
`(0.031477/0.025895) × 2/(2+q)`; it crosses the 1.10 margin at **q ≈ 0.21**. The pilot has
~5× that margin of safety at the measured q = 1.0.

---

## 4. Randomization scheme

**Design:** block-randomized by **stimulus** (three blocks: clean / critical / style). Within
each block, **exactly 50% static / 50% adaptive** (3 static + 3 adaptive cells). Cell model and
stimulus spec are identical within each arm — the only difference between arms is the treatment
(§0: static = proposals recorded, NEVER applied; adaptive = proposals applied exactly as
proposed).

**Committed seed (hex):** `fa74bbe6f9d4a67a019799ebfa61ac9e`

**Reproducibility key (p5 must re-derive the table from this):**

```python
import random
random.seed("fa74bbe6f9d4a67a019799ebfa61ac9e")
for stimulus in ("clean", "critical", "style"):
    arms = ["static"] * 3 + ["adaptive"] * 3
    random.shuffle(arms)          # slot i (1..6) -> arms[i-1]; within-arm repetition label =
                                  # occurrence order of that arm in the block's permutation
```

**Repetition labels:** within each (stimulus, arm), cells are labelled `r1`, `r2`, `r3` (the
occurrence order of that arm in the block's seeded permutation). Cell ids:
`cap2b_<stimulus>_<arm>_r<k>`.

**The exact assignment table — pre-computed, canonical, committed here** (slot # = seeded
permutation position within the block; the execution order):

| cell_id | block (stimulus) | arm | repetition | slot # |
|---|---|---|---|---|
| `cap2b_clean_static_r1` | clean | static | r1 | 1 |
| `cap2b_clean_adaptive_r1` | clean | adaptive | r1 | 2 |
| `cap2b_clean_adaptive_r2` | clean | adaptive | r2 | 3 |
| `cap2b_clean_static_r2` | clean | static | r2 | 4 |
| `cap2b_clean_static_r3` | clean | static | r3 | 5 |
| `cap2b_clean_adaptive_r3` | clean | adaptive | r3 | 6 |
| `cap2b_critical_static_r1` | critical | static | r1 | 1 |
| `cap2b_critical_static_r2` | critical | static | r2 | 2 |
| `cap2b_critical_static_r3` | critical | static | r3 | 3 |
| `cap2b_critical_adaptive_r1` | critical | adaptive | r1 | 4 |
| `cap2b_critical_adaptive_r2` | critical | adaptive | r2 | 5 |
| `cap2b_critical_adaptive_r3` | critical | adaptive | r3 | 6 |
| `cap2b_style_static_r1` | style | static | r1 | 1 |
| `cap2b_style_static_r2` | style | static | r2 | 2 |
| `cap2b_style_adaptive_r1` | style | adaptive | r1 | 3 |
| `cap2b_style_adaptive_r2` | style | adaptive | r2 | 4 |
| `cap2b_style_adaptive_r3` | style | adaptive | r3 | 5 |
| `cap2b_style_static_r3` | style | static | r3 | 6 |

Totals: **18 cells · 9 static · 9 adaptive · 6 defect-bearing (all in the critical block, 3 per
arm)**. Arm labels come from this committed seed + block scheme, **never** from the model's
choice and never post-hoc. **E4** (the p1 measurement cell) = the first static-arm cell in the
table by slot order: **`cap2b_clean_static_r1`**. Every cell runs in a fresh worktree with a
unique `FINOPS_CELL_ID`; the proposal is emitted and validated BEFORE the outcome is recorded;
p2's execution manifest lists every cell of this table and no others.

---

## 5. Analysis plan

**Inputs:** only immutable p1/p2 artifacts; join validated on `(cell_id, arm, stimulus,
repetition)` against §4's table. A cell scored under a different arm than its assignment is
**invalid**, not corrected.

**Per-arm estimates (with n + CI):**

| quantity | estimator | CI |
|---|---|---|
| cpvo per arm | `Σ cost / Σ accepted` over the arm's cells | bias-corrected percentile bootstrap, 10,000 resamples of cells **within the arm, stratified by stimulus block**; 95% |
| cpvo ratio `r` | `cpvo_adaptive / cpvo_static` | bootstrap percentile, 95% (reported as uncertainty; the decision uses the point estimate) |
| verified-success rate per arm | `accepted / cells` | Wilson 95% (standard for proportions) |

**Decision rule (pre-registered, §2):**

```
non-inferior  ⟺  cpvo_adaptive ≤ 1.10 × cpvo_static   AND   succ_adaptive ≥ succ_static − 5pts
```

The decision is made on the point estimates; the CIs are reported alongside (never to
renegotiate the margin). Output JSON (`experiments/results/cap_2b/cap_2b_score_<ts>.json`)
carries per-cell rows, per-arm aggregates with n + CI, the **defect-bearing breakdown** (the
pilot's n), the decision-rule computation (cpvo ratio, success gap) with the margin cited by
this section, and the asymmetric-loss table below.

**Sensitivity — asymmetric-loss table at the measured E_x and the sourced 28**
(base downstream defect cost $0.004021; loss = E_x × $0.004021; static arm records the
false-continue cost of an ignored rework, adaptive arm records the true-rework value as a gain):

| E_x | static arm loss | adaptive arm value | swing | source |
|---|---|---|---|---|
| **11.4671** | +$0.046109 | −$0.046109 | $0.092218 | **MEASURED** (openai/gpt-5.6-sol escalation fix) |
| 12.5134 | +$0.050316 | −$0.050316 | $0.100632 | **MEASURED** (anthropic/claude-sonnet-5 escalation fix) |
| **28.0** | +$0.112588 | −$0.112588 | $0.225176 | sourced (DeepSeek → GPT-5.6 pricing ratio) |

All values from the escalation score JSON `loss_table` (rows 11.4671, 12.5134, 28.0).

**Expected-effect checks:** every adaptive-arm proposal's expected effects are checked against
the post-application change analysis (rerun3 `expected_effects` structure); the check/held rate
is reported with its denominator.

**Pre-registered contingency:** if the decision rule does NOT decide (defect-bearing n below the
power analysis, or the CI straddling the margin), the plan states exactly how many additional
defect-bearing cells the §3 power table requires and extends the grid under the **same** block
scheme + a documented seed extension — the margin and outcome metric are not re-opened.

---

## 6. Authorization boundary

**Non-inferiority in this pilot authorizes DESIGN REVIEW of continuing adaptive selection —
and nothing else.** Concretely, this pre-registration and any subsequent verdict:

- authorizes a design-review conversation about whether to continue adaptive selection on live
  cells;
- does **not** launch the continuing regime itself — 2b never flips `control_route`, never arms
  actuation, never writes a policy that applies proposals outside this pilot, and never
  escalates adaptive control into production;
- does not clear any other gate (prediction, routing, or escalation) and does not modify the
  treatment (`verify_proposal.py`, `_risk_depth`, `VERIFY_RISK_THRESHOLD`, or the risk weights
  stay code-unchanged).

If the pilot is non-inferior, the design review receives: the per-arm cpvo and success with n +
CI, the decision-rule computation, the asymmetric-loss table, and this authorization statement.
If the pilot is NOT non-inferior, that is a FAILED finding for continuing adaptive selection as
designed.

---

## Guard (provenance of every number)

Every number in §1–§5 is derived from a cited artifact with its SHA256 (header), and the
derivations are shown inline:

- **$0.005719** = 0.014668 − 0.008949 (rerun3 score JSON `cells[]`: critical-gate vs
  critical-baseline `cost_usd`).
- **$0.046109 / $0.004021 / E_x 11.4671 / 28.0** = escalation score JSON `loss_table`,
  `base_downstream_defect_cost_usd`, `per_model[0].E_x`, and the rerun3 `value_model.E_x`.
- **8.06×** = 0.046109 / 0.005719; **ratio 0.8104** = 0.010492 / 0.012948 = (0.031477/3)/(0.025895/2)
  (rerun3 `cost_per_outcome`); **break-even q ≈ 0.21** and **power table** = the §3 simulation,
  parameters cited in the table.
- **Base rate 1/3** = the stimulus family construction (`cap_2a_cell_*` specs; only the
  critical variant carries a defect).
- **Seed + assignment table** = concrete hex `fa74bbe6f9d4a67a019799ebfa61ac9e` with the
  one-line reproducibility key and the full 18-row table committed above — no placeholders, no
  run-time randomization.

## LOG

Pre-registration complete and internally consistent: margin, outcome metric, power analysis (n
defect-bearing ≥ 6 → ≥ 18 cells, 3 repetitions per block), committed seed, full 18-cell
assignment table, analysis plan with the decision rule + CI + asymmetric-loss sensitivity (E_x
11.47 / 28), and the authorization boundary all stated with derivations. **PASS** — committing
before any cell runs.
