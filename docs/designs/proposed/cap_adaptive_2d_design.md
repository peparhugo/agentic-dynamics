---
status: proposed
---

# cap_adaptive_2d — design: the informational-abstention rule (the application-policy design review)

**Status: PROPOSED — the design-review deliverable 2c authorized. NOT a preregistration; nothing
below commits a campaign. The verifying campaign (2d) runs only after the operator approves
this design (on approval it moves to ``docs/designs/current/`` as accepted); its
preregistration then fixes every number (§5) before any cell runs.**

**Authorization chain:** the 2c verdict (`docs/designs/current/cap_adaptive_2c.md`, accepted)
decided NON-INFERIOR under proposal heterogeneity (cpvo ratio 0.6537 ≤ 1.10, success gap
−0.3333 ≤ 0.05, n=12/arm, 7 defect-bearing/arm) and — pre-registration §6 — authorized **a
design change to the gate's application policy, and nothing else**. This document is that
design review. Its conclusion is a single design-change proposal (the informational-abstention
rule, §2) plus the campaign design that would verify it.

**Predecessor artifacts (all cited in 2c's verdict header):** the 2c preregistration
(`cap_adaptive_2c_preregistration.md`, SHA256 `0f3a5de7…`) and verdict (`cap_adaptive_2c.md`);
the 2b preregistration + verdict (`cap_2b_preregistration.md` SHA256 `21fc3b41…`,
`cap_2b.md` SHA256 `3153f1a8…`); the measured-E_x campaign score
`experiments/results/cap_escalation_measurement/cap_escalation_measurement_score_20260826T125726Z.json`
SHA256 `6d3c7a7c…`; the measurement-design pins
`docs/designs/current/cap_2a_rerun2_measurement_design.md` SHA256 `8b9dcf7a…`; the 2c score JSON
`experiments/results/cap_adaptive_2c/cap_adaptive_2c_score_20260827T180241Z.json` SHA256
`076751e4…` + its validation JSON SHA256 `17093d85…`.

---

## 1. The finding this design responds to (measured, 2c)

The 2c boundary verdict's bottom line: **the gate should decline when it has NO information to
act on — not when it is uncertain about what it already sees.** The evidence, from the 2c
verdict (all fields cited to `cap_adaptive_2c_score_…Z.json`):

| measured fact | value | where |
|---|---|---|
| confidence-gated abstention improves value at any θ ∈ (0,1) | **NO** (`improving_threshold_exists=false`) | `score.abstention_analysis` — θ=1.0 (decline the six 0.6667-confidence cells) drops accepted 14→10 and RAISES harm 0.0549→0.1029 |
| the low-confidence decile's cells | exactly the defect-bearing correct/competing/unseen-family cells — where adaptive adds its value | `per_decile` — value(apply) $0.016392 finite vs value(abstain) undefined (0 accepted) |
| wrong-continue harm when the gate had no information (absent-defective) | 1 escaped defect per arm = **$0.046109 @11.47 / $0.112588 @28** | `per_class.absent` + `harm_table` |
| wrong-continue harm on the unseen family (a defect outside the calibrated families) | 2 escaped per arm = **$0.092218 @11.47 / $0.225176 @28 per arm** | `per_class.unseen_family` |
| measured wrong-apply (false-positive verify) | **$0.00 — unmeasured**: all 4 incorrect cells emitted `continue`, not `verify` (construction failure, `impacted=0`) | `flags.construction_failures` — the false-positive-apply harm remains unmeasured in 2c |

The two harm-paying states are exactly the states where the seam's facts were
**low-information**:

1. **absent-defective** — the seam REFUSED (no risk term measurable: sonar + lsp unavailable +
   graph unavailable → `code_change_risk` omitted → `build_verify_proposal` raises). The gate
   had no information and paid the full escape cost.
2. **unseen-family** — the change was fully test-visible but the defect's family produced NO
   severity signal and a deferral-free clean risk: `new_sonar_critical_count = 0`,
   `new_lsp_error_count = 0`, `changed_symbols_with_tests_ratio = 1.0` → risk ≈
   `0.20·min(1, impacted/10)` → `continue` (wrong). The gate "had information" in the countable
   sense but **nothing it can act on** — no severity signal, and the tests term says "tested".

Both are distinct from "confident but wrong" — which 2c could not measure (the incorrect class
failed to instantiate) and which the confidence signal does not point at anyway.

---

## 2. The design-change proposal — the informational-abstention rule

**The proposal (one sentence):** the application policy treats **"the seam cannot measure risk"**
and **"the seam's analysis does not match the change under review"** as a DECLINE condition —
the proposal records `abstain`, the application does not proceed as `apply`/`continue`, and the
cell/change is routed to operator review — instead of the current pass-through behavior.

**The rule, expressed in the compiler's vocabulary (a control rule whose `requires_facts`
resolve to the FACT_PREDICATES of `control.facts` — the gate admits it only because every
predicate is measured by `code_change_facts/v2`):**

```yaml
- name: informational_abstention
  plane: control
  evidence_class: "[C]"          # derived from measured facts; policy decision [P] weights
  requires_facts:
    - analysis_revision_matches  # bool; OMITTED when the analysis did not run
    - code_change_risk           # float; OMITTED when no term is measurable
    - changed_symbols_with_tests_ratio  # float; DEFERRED when no changed symbol is test-linked
    - new_sonar_critical_count   # int; OMITTED when sonar did not run
  produces_facts:
    - abstention_decision        # decline | apply | apply-null  (the application-policy decision)
```

**The decision table (the application-policy change):**

| seam state (measured facts) | today (2c behavior) | proposed (informational abstention) |
|---|---|---|
| `analysis_revision_matches` **false or absent** (stale/refused analysis — the facts do not correspond to the change under review) | seam refuses on unparseable facts; otherwise continues on whatever stale risk was minted | **DECLINE** — no proposal-to-change correspondence means no information; route to operator review |
| `code_change_risk` **absent** (all terms unmeasurable — the absent-class state) | seam refuses (`ValueError`) → pass-through | **DECLINE** — record `abstain` + the facts present; route to operator review (the 2c absent-defective escape, $0.046109/escape, is the harm this leg targets) |
| risk measurable, ≥ `VERIFY_RISK_THRESHOLD` 0.2 | apply (verify/rework per the action tree) | unchanged — **APPLY** (the correct/competing value, 4/4 defect-bearing cells fixed) |
| risk measurable, < 0.2, severity signals present | `continue` | unchanged — **APPLY-NULL** (the irrelevant class: value-neutral) |
| risk measurable, < 0.2, NO severity signal, `changed_symbols_with_tests_ratio` **deferred or = 1.0** (the unseen-family state: a defect with no countable signal on a test-visible surface) | `continue` (wrong) | **DECLINE** — "fully tested + zero severity signal" is the null only when the defect family is within the calibrated set; a change that is *all* signal-free and *all* "tested" is low-information for the calibrated families → operator review (the unseen-family escape, $0.092218/arm @11.47, is the harm this leg targets) |

**What DECLINE is, and is not (the control-plane discipline):**

- DECLINE is **flag-only + operator review** in the pilot: it records the abstention decision,
  refuses the automatic apply, and surfaces the change in the operator-review channel (the
  checkpoint/approval machinery, not new actuation). It is NOT a silent no-op (that is today's
  pass-through) and NOT a new autonomous arm.
- DECLINE costs the measured pass delta when the change turns out clean (the 2c absent-clean
  result: refusal cost the gate nothing) — the design's falsifiability target is: **abstention
  must capture the absent-defective + unseen-family escapes at a lower total (cost + harm) than
  the status quo, without flagging so many clean cells that the flag cost exceeds the escape
  harm saved.**
- **Confidence plays no role in the rule.** The 2c abstention result is a hard constraint on
  this design: no θ on the measured confidence axis improves value, and the signal is inverse to
  where adaptive adds value. The design therefore excludes confidence from the decline
  condition. (The campaign's exposure set — §5 — includes high-confidence-wrong and
  low-confidence-correct proposals to RE-CHECK this constraint; a rule that needed confidence
  would require re-opening the 2c verdict.)

**Why "no information" is the honest boundary (the two-leg argument):**

1. The 2c harm is paid exactly where the facts cannot distinguish defect from clean
   (absent-defective: no terms at all; unseen-family: no severity signal + "tested" reads as
   clean). In both states the countable facts are silent — the gate's `continue`/refusal
   behavior is a **wrong-continue in expectation** whenever the base defect rate is non-zero
   and the E_x multiplier is real (measured 11.47, sourced 28).
2. The apply states (risk ≥ 0.2 with severity signals) are where adaptive is strictly superior
   (correct + competing: 4/4 fixed vs 0 accepted static). Abstention must not touch those —
   and the rule above does not.

**The unresolved design decision the operator must make before preregistration (§6):** the
decline-leg-3 trigger ("fully tested + zero severity signal") trades off against the 2c
irrelevant class: a *truly* trivial fully-tested change (the irrelevant class: `continue`,
value-neutral) is indistinguishable from the unseen-family state at the countable-facts level
except by the family audit that runs AFTER scoring. The design options:

- **Option A — decline-leg-3 only when the risk is EXACTLY the tests-term remainder**
  (`0.20·min(1, impacted/10)` — no other term contributed), i.e. the signal-free + fully-tested
  combination; the irrelevant class (ratio 0.5, impacted 4, risk 0.18) pays `0.10 + 0.08` and is
  NOT flagged. This is the design's preferred reading: "the ONLY information is the tests term"
  is the low-information fingerprint.
- **Option B — decline on any risk < 0.2 with ratio ≥ 1.0** (fully tested, no criticals): wider
  net, flags the irrelevant class too — cheaper to implement, higher flag false-positive rate.
- **Option C — no leg 3 in the pilot**: abstention covers only legs 1–2 (unmeasurable/stale);
  unseen-family stays a recorded blind spot until new measurement exists (the 2c verdict's
  own question: is the escape reachable by any application-policy change short of new
  measurement?). Option C tests the abstention mechanism without the fuzzy leg; leg 3 becomes a
  follow-up.

The campaign (§5) is designed so the operator's choice among A/B/C is a **pre-registered
parameter**, not a post-hoc knob.

---

## 3. What the campaign must expose (the review's treatment-exposure list, mapped to the 2c machinery)

The next study's exposure set — each class must actually instantiate its treatment (the 2c
construction-failure lesson: a class that cannot instantiate is a non-measurement, recorded
honestly):

| exposure (review list) | construction (2d) | expected proposal | the claim it tests |
|---|---|---|---|
| **correct proposal** | the 2c correct cell reused: `classify` with S3776 + the `[10,20)` `>`-for-`>=` boundary | `rework` d3 | abstention must not touch apply (leg: apply) |
| **incorrect-but-plausible** (false-positive verify on clean) | the 2c incorrect cell REBUILT — the construction-failure fix: the changed symbol must be structurally dependant (impacted ≥ 1 guaranteed by an edge the graph provably sees, e.g. the new untested module CALLS the changed function) + ratio 0.05; risk ≥ 0.2 verified pre-run | `verify` d2 | the measured wrong-apply harm 2c could not produce (0.6537 result holds only if the FP pass cost ≤ its value) |
| **harmful proposal** (apply that makes things worse) | the severity filter makes rework-on-clean unconstructible (2c filter-strength). The constructible harmful-apply: **partial_rework** — a competing-style cell where the rework pass fixes one of two defects (2c's own partial_rework outcome, harm = 1×E_x for the unfixed defect). The "harmful" claim is the partial pass's cost with the defect left in | `rework` d3 (partial) | the cost of a wrong-scope apply — abstention can't see this (the facts said rework), so the exposure measures the ceiling of what application-policy alone can prevent |
| **irrelevant** | 2c irrelevant reused verbatim | `continue` d0 | abstention legs A/B/C must not flag it (or must flag at the pre-registered rate) |
| **multiple competing** | 2c competing reused (two boundary defects, one-of-two semantics) | `rework` d3 | abstention must not touch apply |
| **no proposal (absent)** | 2c absent-clean + absent-defective reused (designed degraded state) | refusal | the abstention legs 1–2 mechanism + its cost on clean vs defective |
| **unseen defect family** | 2c unseen-family reused (mutation/aliasing) | `continue` (wrong) | the abstention leg-3 (A/B/C) capture rate — the primary abstention outcome |
| **high-confidence wrong proposal** | a clean-change cell whose implementer confidence is 1.0 and whose proposal is (rebuilt) `verify` — the confidence-vs-value re-check | `verify` (FP) | re-checks the 2c constraint: confidence must remain irrelevant to the rule |
| **low-confidence correct proposal** | a correct-class cell run under the confidence-degrading condition (e.g. a large deliberate context) | `rework` d3 | same re-check on the value side |

**The primary question (the campaign's headline):** *Does the adaptive controller know when
not to intervene?* — operationalized as: **does the informational-abstention rule capture the
absent-defective and unseen-family escapes at a lower (cost + harm) than the 2c status quo,
without flagging the value-neutral classes at a cost that exceeds the saved harm?**

---

## 4. The falsifiability contract (what refutes the design)

A verdict REFUTES the informational-abstention hypothesis if any of:

- abstention captures **no** absent-defective/unseen-family escape (capture rate 0 — the
  decline never fires on the states that paid the 2c harm);
- abstention's flag false-positive rate on the clean classes (irrelevant, absent-clean, the
  incorrect FP-verify cells) makes `Σ(cost + harm)_abstention > Σ(cost + harm)_status-quo` at
  the measured E_x = 11.47 — the flag cost exceeds the escape harm saved;
- abstention degrades the apply classes: correct/competing accepted outcomes drop, or the
  pooled cpvo ratio crosses the 2b/2c margin (1.10) — the rule bled into the states where
  adaptive is strictly superior;
- the rebuilt incorrect class STILL fails to instantiate `verify` (a second construction
  failure) — the false-positive harm remains unmeasured and the design's wrong-apply leg is
  unverifiable.

A verdict SUPPORTS the design if the decline fires on the low-information states (absent-legs
1–2 and/or leg-3 per the operator's A/B/C choice), the capture rate is pre-registered-adequate,
the clean-flag cost is below the saved escape harm, and the apply states are untouched.

---

## 5. The campaign sketch (2d — to be preregistered, not yet committed)

The preregistration (next artifact, after operator approval of this design) will fix, per the
2b/2c pattern: the committed seed + full assignment table, the denominators, the harm model
(the 2c model verbatim: wrong-apply = measured pass delta; wrong-continue = E_x × $0.004021 at
11.47/28), the abstention analysis (now the PRIMARY outcome, not exploratory), the margin
(cpvo ratio ≤ 1.10 reused; the capture-rate floor and the flag-cost ceiling pre-registered as
the abstention decision rule), the operator's A/B/C leg-3 choice, and the budget arithmetic
(2c measured per-cell $0.0039–$0.0164 × the grid; wrapper phases as in 2b/2c — total ≈
$0.5–1.0, well inside a $30 stop). **Nothing in §2–§4 that depends on a number is fixed here —
every number is fixed by the preregistration.**

Campaign shape: the 2c machinery unchanged (`workflows/repository/cap_adaptive_2c.yaml` cell
pattern — fresh worktrees, `FINOPS_CELL_ID`, proposal-before-outcome, application-proof,
p1 measurement cell → p2 grid → p3 score → p4 verdict → p5 adversarial), with the application
policy switching on the **shadow `decline` decision** (the rule records its decision; the
operator-review routing is exercised in the pilot, never in production). Treatment remains
code-unchanged: `verify_proposal.py`, `_risk_depth`, `VERIFY_RISK_THRESHOLD`, `RISK_WEIGHTS`,
the severity filter (2c hard-rule 10).

---

## 6. Authorization boundary (unchanged from 2c, restated)

- 2c authorized **a design change to the application policy — nothing else**. This document IS
  the design change proposal. It authorizes: the operator's A/B/C decision; the subsequent
  2d preregistration; the 2d campaign (cells + wrapper phases, ≤ $30).
- It does NOT: activate the abstention rule in any production path; change `control_route` or
  arm any actuation; modify the treatment; or re-open the 2c non-inferiority verdict.
- The 2d verdict (if it supports the design) authorizes the NEXT conversation — wiring
  DECLINE into the live application path — never by itself.

## Guard

Every number in this document derives from the cited 2c/2b/E_x artifacts (SHA256s in the
header + field paths inline) or is arithmetic on them, shown inline. The rule's `requires_facts`
resolve to the FACT_PREDICATES of `control.facts` (`analysis_revision_matches`, `code_change_risk`,
`changed_symbols_with_tests_ratio`, `new_sonar_critical_count` — all produced by
`code_change_facts/v2`) — the compiler's requires/produces gate admits it, so the arm is
writable the moment the design is accepted.

**LOG:** 2c's boundary finding restated (decline when the gate has NO information — the
absent-defective $0.046109/escape and unseen-family $0.092218/arm @11.47 harms, and the null
abstention curve that rules confidence OUT); the informational-abstention rule proposed in the
compiler's vocabulary (decline | apply | apply-null over the four measured predicates); the
three decline legs (stale/unmeasurable/signal-free-fully-tested) with the operator's A/B/C
decision on leg 3; the nine-class exposure set with each construction mapped to the 2c
machinery and the incorrect-class rebuild lesson (impacted ≥ 1 must be structurally guaranteed
and pre-verified); the falsifiability contract (capture rate, flag cost vs saved harm, apply
states untouched, no second construction failure); the campaign sketch with every number
deferred to the preregistration; the authorization boundary (design review only). **DRAFT —
for the operator's review; nothing is committed or run.**
