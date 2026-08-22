---
status: accepted
---
# Investing Domain — Adversarial Compliance + Feasibility Review (Stage-0)

**Role:** adversarial compliance + feasibility critic. This review attacks the three Stage-0
audits — `audit_observable.md` (d1), `audit_policies.md` (d2), `audit_gap_map.md` (d3) — the way
`docs/review/finding_economics_review.md` attacked the measurement release. Every finding below is
**re-verified against both the docs and the framework**; each is resolved in the docs (amended, or
recorded as an accepted limitation with reasoning). Six attack vectors are worked in full; the
LOG at the foot gives one evidence line per vector.

**Framework ground truth used throughout** (verified): the fact plane is a **reserved stub** —
`src/agentic_dynamics/control/facts.py:1-8` ("Frozen until post-consolidation CAP implementation"),
zero call sites; the CAP spec is **paused** — `workflows/repository/context_abstraction_implement.yaml:2-10`
(freeze_reason `consolidation_release/stage_map`, resume_after `consolidation S6`); and
`knowledge.SOURCE_TYPES` (`knowledge.py:125-149`) has **no** `market`/`portfolio`/`trade`/`thesis`
rows — the domain's producers are prospective, not present.

## Amendment A — operator-policy confirmation (2026-08-22)

The operator confirmed the actual constraint set after this review was written. It replaces the
draft invariant ("long calls + covered calls only") and re-scopes three findings:

- **Confirmed policy `[P]`:** buy-to-open calls and puts; **sell-to-close only**; long straddles
  permitted (both legs bought); **no sell-to-open** — so no naked puts/calls, and covered calls are
  excluded (a covered call requires selling-to-open). The broker additionally permits options only
  "with some restrictions" and straddles on *some* underlyings — a broker-capability `[M]` axis to
  enumerate during instrumenting.
- **Consequence for F2 (sign contract):** still material, re-keyed — the close-only matcher needs
  **side-qualified fills** (`EX-1`) and series-keyed signed positions (`PS-1`); the one-way failure
  is now a broker export that drops the fill *side*, not the long/short sign.
- **Consequence for F3 (USD-settled assignment):** narrowed — with no short legs, there is no
  short-assignment / "called away" event; the USD-settlement concern now applies to *exercising a
  long US-listed option*, which still settles USD and flows into PS-10 / the FX position. The
  `[X]` to-verify caveats stand.
- **Consequence for F5 (fixed-100 multiplier):** narrowed but not removed — the deliverable
  multiplier now keys **lot-matching on adjusted series** in `close_only_holds` (a split-adjusted
  series must match against the adjusted deliverable), rather than a share-coverage threshold.
  CX-6 remains the source.

`audit_policies.md` §5(a) and `audit_gap_map.md` §2C/§3a are amended accordingly.

## Verdict

The three audits are disciplined on the compliance axis (every signal tagged, no `[H]`-as-measured,
sources named-not-connected) but **over-claim feasibility on the "writable / declarable now" axis**:
they mark arms and predicates as produced when the producers are prospective, and they silently
assume single-currency arithmetic and a fixed option-contract multiplier that the domain does not
guarantee. Six findings follow; all six are resolved in the docs (five amendments + one accepted
limitation).

| Area | Assessment |
|---|---|
| Provenance-tag discipline (d1) | 9/10 |
| Policy gate literalness (d2) | 8.5/10 |
| Framework mapping honesty (d3) | 7/10 |
| Registered-account traps | 6.5/10 |
| Arithmetic / reducer correctness | 6.5/10 |
| **Overall** | **7.5/10** |

---

## F1 — "writable today" / "declarable now" writes a prospective producer as a present fact (V1 + V6)

**Claim under attack.** d1 §7 asserts "8 of 11 arms writable **today**" (P-1, P-2, P-4, P-5, P-6,
P-7, P-8, P-9) with producer chains that are `[X]` external (`CX-1`, `CX-2`, `MD-1`, `MD-8`,
`MD-10`). d3 §2A labels 15 predicates "**declarable now**" whose `produced_by` are reducers
(`market_facts/v1` etc.) over producers (`market`/`portfolio`/`trade`/`thesis`) that are themselves
`NEW` and unbuilt (d3 §1).

**Why it is wrong.** This is the *deadline_slack* error in reverse: `LEDGER_FIELDS` declared
signals with zero writers (design §3.5 "absent and why"); here the audit declares a **producer
status** ("writable", "declarable now") that the framework has never exercised. Verified against
the framework: the CAP compiler whose `requires`/`produces` gate d1 §7 invokes is **paused**
(`context_abstraction_implement.yaml:2-10`); `facts.py` is a stub; `SOURCE_TYPES` has no
`market`/`portfolio`/`trade`/`thesis` row. So "writable today" is false on two independent grounds:
(a) no producer exists for any `[X]`-external signal (named-not-connected, d1's own convention),
and (b) the gate that would certify "writable" does not run. d2 — the literal gate — correctly
yields only 4 writable (a, c, g, h), so d1 §7 and d2 **disagree on the meaning of "writable"**.

**Resolution (amended).** d1 §7 now distinguishes "source-named" (a named producer exists) from
"instrumented" (a producer runs in this repo), and its summary cross-references d2's literal gate.
d3 §2A is retitled "Declarable **once its producer lands** (migration phase 1)" with an explicit
note that none exists in the repo today.

---

## F2 — `close_only_holds`: the sign contract d2 flags is dropped in d3, so the invariant is unenforceable as mapped (V3)

**Claim under attack.** d2 §5(a) correctly states the enforcement producer is the **signed**
open-position record and names the producer-contract risk ("if the broker export flattens option
legs without a long/short sign … unverifiable"). But d3 — the framework map — defines the reducer
as `close_only_holds = (no short put) ∧ ∀ short call: shares(underlying) ≥ 100·qty` (§2C) over a
`position_qty` predicate (§2A) that carries **no signedness contract**, and the `portfolio`
source_type (§1) is silent on sign. d3 therefore maps the *answer* (the reducer) but drops the
*precondition* (signed input) that makes the answer true.

**Why it is material.** The enforcement question the original brief posed — "does d2's mapping give
the decision engine the short_exposure fact it needs?" — is answered "yes" in d2 and "unrebuilt"
in d3. As mapped, `close_only_holds` would compute coverage against unsigned quantities and could
certify a naked short call as covered. The invariant is enforceable *if and only if* the sign
contract is carried into the reducer's input spec.

**Resolution (amended).** d3 §2C now states the input contract on `position_qty` (signed; short
legs negative) and that `EX-4` assignments re-key positions before the reducer runs.

---

## F3 — US-settled assignment in a registered account is not in the audit (V4)

**Claim under attack.** d1 EX-4 (`Assignment / exercise notice`) notes only that "short-option
assignment is only possible in permitted registered strategies." It omits the RRSP/TFSA-specific
trap: **assignment/exercise on a US-listed (USD) option settles in USD**, which (a) requires a USD
sub-account, (b) introduces FX exposure that flows into PS-10, and (c) in a TFSA may not permit a
USD short-cash balance at all (broker-specific). EX-8 (`settlement currency`) names the field but
never connects it to the assignment event or the FX position.

**Why it is material.** This is the exact class of registered-account trap the domain audit was
scoped to catch, and it changes a real portfolio state (a "called away" covered call is *not* a
clean cash credit — it is a USD cash credit subject to FX and account-eligibility constraints). A
weekly_review reconciliation that reads the assignment as CAD would misstate the outcome.

**Resolution (amended).** d1 EX-4 (and EX-8) now note USD settlement on US-underlying assignments,
the FX interaction with PS-10, and the TFSA USD-short-cash caveat marked `[X]` to-verify.

---

## F4 — CAD/USD is named but never wired into the value reducers (V5)

**Claim under attack.** d1 PS-8 is `= Σ(PS-3) + PS-4` where PS-4 is "cash balance **per
currency**"; d3's `portfolio_value` reducer is `Σ position_qty·last_price + cash` (§2C). Both sum
CAD and USD as if one numéraire. d1 PS-10 names the FX rate, and PS-3's note says "quantity `[M]`,
last price `[X]`" — but **no reducer input names the FX rate**. `position_weight`, `crypto_weight`,
and `unrealized_pnl` all inherit the same defect (a USD position divided by a CAD NAV).

**Why it is material.** Every weight and P/L number that feeds `position_size`, `crypto_cap`, and
`weekly_review` is a mixed-currency sum; the error is not a rounding noise but a systematic
CAD/USD misstatement that varies with the FX rate.

**Resolution (amended).** d3 §2C's `portfolio_value` (and the weight/pnl reducers) now specify
all-in-CAD conversion (`Σ qty·price·fx_to_cad + Σ cash·fx_to_cad`, fx from PS-10); d1 PS-8's note
is amended to state the CAD-equivalent form.

---

## F5 — corporate-action adjustment breaks the fixed-100 coverage multiplier (V5)

**Claim under attack.** d1 CX-6 lists "splits, mergers, ticker changes" and notes only "feeds PS-2
book-value adjustments." Neither d1 nor d3 notes that a **split / merger / spin-off adjusts the
option deliverable**: a 2:1 split turns a standard contract into 200 deliverable shares (or two
adjusted contracts), so the `close_only_holds` term `shares(underlying) ≥ 100·qty` is **false the
day the adjustment takes effect** even though the position is still fully covered.

**Why it is material.** The invariant the whole enforcement apparatus (§F2) protects is expressed
as a fixed-100 multiplier; a single corporate action silently invalidates it. This is a blind spot
that is both observable (d1 CX-6 has the source) and unconnected to the reducer that needs it.

**Resolution (amended).** d3 §2C's `close_only_holds` now uses the **deliverable multiplier** (not
a fixed 100) and cites CX-6 as its source; d1 CX-6's note is amended to flag the option-deliverable
adjustment.

---

## F6 — `iv_rank` is a cold-start phantom: a producer path, but an empty window for a year (V2)

**Claim under attack.** d2 `exit_rules` requires `iv_rank` → `UNINSTRUMENTED (needs the MD-6 IV
time series)`, and d3 §2B lists `iv_rank` as "blocked by `option_iv` time series … unblocked at
reducer step 5." Both treat `iv_rank` as unblocked **the moment** an IV reducer exists. They miss
that `iv_rank = (IV_now − min) / (max − min)` over a ~1-year window requires **≥52 weeks of
accumulated IV history**; after step 5 lands, the reducer emits `unknown` for the first year. It is
the `deadline_slack` class in its canonical form: a predicate whose *producer path* exists but
whose *evidence window* is empty, and whose `on_missing` would have to `classify` for a year.

**Why it is material.** It is the precise failure mode the load-bearing rule exists to catch — a
predicate that *looks* produced (reducer registered) but cannot yield a value — and it must be
declared with `volatile`/`on_missing: classify` semantics, not as a silent "writable after step 5."

**Resolution (amended + accepted limitation).** d3 §2B now records "≥52wk accumulation required
after step 5 — the first year yields no rank." **Accepted limitation (reasoning):** this is not a
defect that can be coded away — a rank over a rolling window is definitionally empty until the
window fills; the correct engineering posture is to declare the cold-start and let the contract's
`on_missing: classify` carry it, which is now stated.

---

## Attack-vector LOG

| Vector | Evidence (re-verified) | Resolution | Verdict |
|---|---|---|---|
| V1 fact/hypothesis contamination | d1 §7 "8 of 11 arms writable today" writes a producer status the framework has never exercised; `[X]` signals are named-not-connected (d1 §1/§5) | F1 — d1 §7 + d3 §2A amended | **FAIL → amended** |
| V2 `deadline_slack`-class phantoms | d3 §2B `iv_rank` "unblocked at step 5" ignores the empty 52-week window | F6 — amended + accepted limitation | **FAIL → amended** |
| V3 enforcement gaps | d2 §5(a) flags the sign contract; d3 §2C's reducer drops it | F2 — d3 §2C amended (signed `position_qty` + EX-4 re-key) | **FAIL → amended** |
| V4 RRSP-specific traps | d1 EX-4/EX-8 omit USD settlement on US-underlying assignment; TFSA USD short-cash not flagged | F3 — d1 EX-4/EX-8 amended | **FAIL → amended** |
| V5 observability blind spots | d1 PS-8 / d3 `portfolio_value` sum CAD+USD; CX-6 split/merger adjusts the option deliverable, breaking fixed-100 coverage | F4 + F5 — reducers and CX-6 amended | **FAIL → amended** |
| V6 scope honesty | d3 §3a invokes "the compiler's R1 refusal"; the CAP compiler is paused (`context_abstraction_implement.yaml:2-10`) and `facts.py` is a stub | F1 — cross-ref note added; no compiler claim asserted as running | **FAIL → amended** |

**Result: CONDITIONAL PASS** — 0 unguarded `[H]`-as-measured rows survive (the compliance axis
holds); 6 feasibility findings, all resolved in-doc (5 amendments + 1 accepted limitation). The
three audits remain truthful on provenance but are now truthful on *readiness*.

**Commit:** recorded on branch `feature/investing-domain-audit`.
