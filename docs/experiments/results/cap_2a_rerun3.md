---
status: accepted
---

# cap_2a_rerun3 — the FIRST control-experiment verdict (value, not prediction)

**Status: accepted** · Supersedes: `cap_2a_rerun2@0.1` (verdict `docs/experiments/results/cap_2a_rerun2.md`)
· Predecessor data: `cap_2a_rerun2` score (`cap_2a_rerun2_score_20260826T015846Z.json`) + the
rerun3 p4 score below. This is a **descriptive-only** verdict at **n = 3 pairs** — it clears no
gate and authorizes nothing.

## Provenance (every number below cites a field of the p4 score JSON)

- **Source revision:** `83b65e9f58e60991acbc5500f0d6688fa7c32fe5` (`spec` `source_revision`).
- **Spec version:** `cap_2a_rerun3@0.1` (`spec_version`).
- **Candidate manifests:** p1 `c396303e…` · p2 `f3910a4a…` · p3 `5750a98f…` (full SHA256s in the
  score JSON `candidate_manifests`).
- **p4 JSONs:**

| File | SHA256 |
|---|---|
| `experiments/results/cap_2a_rerun3/cap_2a_rerun3_score_20260826T050000Z.json` (schema `cap_2a_rerun3_score/v1`) | `08b6fb3297a5a41a3b81b4abc69b68cf86dde108918a244b4cf4fe6689a66a09` |
| `experiments/results/cap_2a_rerun3/p4_validation.json` (schema `cap_2a_p4_validation/v1`) | `217fe93e5ec598a284e9a66b662d4e21d9ea24baddbf615ddfbb9e2bd8340d4a` |

- **Join validation:** `valid=true`, `0` errors (`join_validation`) — all 6 cells carry full-SHA
  baseline/analyzed revisions, matching `proposal_id`, `verify_code_change/v1` contract, and the
  ARM invariant (baseline → `not_applicable`; gate → `applied` or `null`).

## The paired table (design §2.3 — per stimulus, both arms)

| stimulus | baseline cost | baseline value | gate cost | gate value | **Δ value** | gate application (proof id) |
|---|---|---|---|---|---|---|
| clean | $0.008509 | −$0.008509 | $0.00845 | −$0.00845 | **+$0.000059** | null — `c28eb202d27da59a` (continue/d0; commit trail seed→implement, no extra pass) |
| critical | $0.008949 | −$0.008949 | $0.014668 | **+$0.09792** | **+$0.106869** | applied — `03962721aea0655c` (rework/d3 → one rework pass, commit `33211ed769f948753e1d3a141fb890cdaaf35294`) |
| style | $0.008437 | −$0.008437 | $0.008359 | −$0.008359 | **+$0.000078** | null — `b4c91ccfbdabeef2` (continue/d0; no extra pass) |

Sources: `paired_value_delta[]` (`baseline_cost_usd`, `gate_cost_usd`, `baseline_value`,
`gate_value`, `delta_value_usd`, `gate_applied_or_null`); `cell_value` on `cells[]`.
`cell_value = −(run cost) + Δdurable_value`, where `Δdurable_value` credits the downstream
defect cost ($0.112588, `value_model.downstream_defect_cost_usd`) to a gate cell whose applied
rework fixed the critical defect, 0 otherwise (`value_model.delta_durable_value_definition`).

## Asymmetric-loss comparison (design §2.4)

Eₓ = **28×** — the site's own escalation economics (DeepSeek → GPT-5.6), stated at
`value_model.E_x_source` and `asymmetric_loss.E_x`. `rework_pass_cost` = $0.004021 (measured
critical-gate rework pass), so `downstream_defect_cost` = 28 × $0.004021 = **$0.112588**.

| arm | Σ asymmetric loss | what it is |
|---|---|---|
| **baseline** | **+$0.112588** | the critical-baseline cell ignored its correct `rework` proposal → the defect propagated downstream (`false_continue_cost`) |
| **gate** | **−$0.112588** | the critical-gate cell applied the `rework` → defect fixed pre-propagation (`true_rework_value`) |

Sources: `asymmetric_loss.sum_baseline_loss_usd`, `sum_gate_loss_usd`, `per_cell[]`. Net loss is
a cost (positive = bad); the −$0.112588 is a gain. The rework pass cost ($0.004021) is already
inside the gate arm's run cost, not double-counted (`asymmetric_loss.note`).

## Expected-effect check/held rates (design §2.5)

- **check_rate = 1.0** (`4/4` claims submitted to the validator) — `expected_effects.aggregates.check_rate`.
- **held_rate = 0.25** (`1/4`) — `expected_effects.aggregates.held_rate`.
- The one held claim: critical-gate `new_sonar_critical_count decrease` (**1 → 0**, held).
- The not-held: critical-gate `new_lsp_error_count decrease` (0 → 0, not a decrease); the two
  `continue` `unchanged` claims are **unmeasurable** (`observed=null` — the null application
  produced no next-phase change_analysis, so there is nothing to re-measure). `expected_effects.per_gate_cell[]`.

## Flagged cells

**None.** No graph-down, no analyzer-down, no invalid-join cells (`join_validation.errors=[]`;
`denominators.n_invalid_join=0`; `n_scored=6`). Graph (`bolt://localhost:7687`), sonar
(`127.0.0.1:9000`), and lsp (`mypy 2.3.1`) were available on every cell.

## Verdict

### (1) Does applying the gate improve value per dollar? — Yes, descriptively; the direction is positive on all three pairs.

Every paired Δ is positive (`paired_value_delta[].delta_value_usd`): clean **+$0.000059**,
critical **+$0.106869**, style **+$0.000078**. The **cost-per-accepted-outcome** (the site's own
KPI, `cost_per_outcome`) moves in the gate's favour: baseline `$0.025895 / 2 accepted =
$0.012948`, gate `$0.031477 / 3 accepted = $0.010492` — the gate arm spends $0.005719 more but
converts the critical outcome from rejected to accepted, yielding **3 accepted outcomes at a
lower per-outcome cost**. This is **descriptive-only** (n = 3 pairs); no gate-clearing claim.

### (2) Asymmetric loss — the gate arm wins by $0.225176 on the loss axis.

Σ asymmetric loss: baseline **+$0.112588** vs gate **−$0.112588** — a $0.225176 swing. The number
the symmetric hit-rate could never produce: the baseline arm's "correct but ignored" rework
proposal costs the downstream escalation; the gate arm's "correct and applied" rework avoids it.

### (3) Expected-effect held rate — 0.25 (1/4), with two unmeasurable null-gate claims.

Every proposal claim was checked (check_rate 1.0); one held (the rework's sonar-decrease claim),
one did not (lsp-decrease — the rework fixed the defect, not an LSP error), and two were
unmeasurable by construction (the null-gate `continue` claims). The held rate is a first, honest
measurement of the proposals' own falsifiable claims — and it exposes a structural limit: the
`continue` null-gate leaves no next-phase facts to check against.

### (4) The critical-gate applied-rework result (the money cell) — defect fixed, at a $0.005719 premium.

The critical-baseline cell's final commit carries the defect (test 2/3, `defect_present_on_final_commit=true`);
its correct `rework` proposal was recorded but ignored. The critical-gate cell **applied** the
same proposal as ONE bounded rework pass — commit `33211ed769f948753e1d3a141fb890cdaaf35294`, a
single one-line fix — and the independent test_runner on the final commit records **3/3**
(`defect_present_on_final_commit=false`). Cost: gate $0.014668 vs baseline $0.008949 →
**rework premium $0.005719** (`cells[]`), which bought an asymmetric-loss swing of $0.225176.
The rework fixed the *boundary defect* it was pointed at; the S3776 cognitive-complexity finding
that *triggered* the proposal persists (noted in `cap2a_r3_critical_gate_outcome.json`).

### (5) The n this feasibility probe implies, and 2b eligibility.

This campaign is 2b's **feasibility probe** (design §2.6), not 2b. What the probe implies for 2b:

1. **The value signal exists and is positive** — a per-defect effect: one applied rework converts
   a rejected outcome into an accepted one worth $0.112588 of avoided escalation for a $0.005719
   premium. That is the effect-size prior a 2b power analysis needs.
2. **The signal concentrates in the rework leg.** The two no-defect stimuli (clean, style) are
   provable nulls — their Δ (≈$0) carries essentially no information about value. So 2b's n must
   be counted in **defect-bearing changes**, not in all changes; a power calculation run on a
   defect-free stream would never see the effect.
3. **n = 3 pairs is far too small to size 2b**, and this probe does not deliver a precise n —
   the base rate of defect-bearing changes in the live stream is not measurable from a 3-stimulus
   synthetic set. 2b's n is therefore a **pre-registered power analysis** over that base rate and
   the non-inferiority margin, using the effect-size prior above — a materially larger randomized
   n than 3, not a fixed number this campaign can state.

**Eligibility:** 2b remains **eligible for design review** (it has NOT run, and this verdict does
not launch it). Its five prerequisites (rerun2 verdict §6) are unchanged and none are met by this
campaign: randomized static-vs-adaptive assignment, pre-registered non-inferiority margin +
outcome metric, independent test execution, budget/SLA guard, outcome non-inferiority under
adaptive control. This verdict supplies the feasibility evidence (the positive paired-Δ direction
and the effect-size prior) that the design review consumes; it authorizes nothing.

## Comparison with the prediction studies (explicit)

The three prediction campaigns measured the gate's **decisions** — the action classifier
(0/3 → 0/3 → 2/3), then the severity fix, then the scope fix (rerun2: hit-rate 2/3, Wilson
[0.2077, 0.9385], descriptive-only). The rerun2 residual defect was a **scope** miss (the rework
proposal excluded the changed symbol). This campaign is the first to measure the gate's **VALUE**:

- **The scope fix is confirmed as data**: both critical proposals' scope now contains `classify`
  (rerun2's miss resolved; `cells[].proposal_action=rework` with the changed symbol in scope), and
  the applied rework leg was therefore **hittable for the first time** — it fixed the defect.
- **Decisions were measured before; value is measured here.** The prediction studies could only
  say "the gate mostly proposes the right action." This campaign says the applied gate **improves
  value per dollar on the stimulus set** (positive paired Δ on all three, asymmetric-loss swing
  $0.225176 in the gate's favour) — at n = 3 pairs, descriptive-only, with the effect carried
  entirely by the one defect-bearing stimulus.

## Guard

Every number above cites a field of the p4 score JSON (paths named inline). No recommendation is
made without n, denominator, uncertainty, and flagged-cell treatment (n = 3 pairs; denominators
printed at `denominators`; flagged cells = none). No 2b authorization is implied; the verdict is
descriptive-only and states the n-feasibility implication, not a clearance.

**LOG:** paired Δ clean +$0.000059 / critical +$0.106869 / style +$0.000078; asymmetric-loss
Σ baseline +$0.112588 vs Σ gate −$0.112588; expected-effect check_rate 1.0, held_rate 0.25;
cost-per-accepted-outcome $0.012948 → $0.010492; flagged cells none. **PASS** — the descriptive
verdict is issued, the applied-gate value is measured for the first time, and no gate is cleared.

## Supplement (E_x sensitivity, p6 limitation F3 — the loss table at both multipliers)

The asymmetric-loss table scales linearly with the escalation multiplier E_x. The p4 score JSON
records the base downstream defect cost (the E_x=28 figure divided out): **$0.004021**. The same
loss table at the two sourced values:

| E_x | baseline arm loss | gate arm value | swing | source |
|---|---|---|---|---|
| 3.1 | +$0.012465 | -$0.012465 | $0.024930 | measured escalation figure (handoff corpus) |
| 28.0 | +$0.112588 | -$0.112588 | $0.225176 | pricing ratio DeepSeek -> GPT-5.6 (site economics) |

Both multipliers keep the gate arm ahead on the loss axis (the break-even is ~1.42); the
DIRECTION of the control result is robust, the MAGNITUDE spans ~$0.025-$0.225 pending a measured
E_x. The escalation-measurement campaign (cap_escalation_measurement) measures the actual
downstream cost of the critical-baseline's escaped defect in dollars.
