---
status: accepted
---

# Control Room Facelift Repair - Design Adversary (r3)

**Reviewer:** `openai/gpt-5.6-luna`
**Date:** 2026-09-11
**Scope:** the resting desktop capture `apps/control_room/verification/F-0_desktop_dark_1440x900.png`
**Method:** screenshot-only stranger test; no implementation prose, source code, hover, selection, or
drill-down was used to form the verdict.

## Verdict

**PASS - the four required stranger statements are each true from the desktop screenshot alone.**

The resting composition reads as an agent-run roster rather than a service dashboard. The session
identity band is the primary object, the decision queue is visibly coupled to the first run, the
lease constraint is attached to every run, and the claim/proof/source/receipt materials are visible
before selection.

## Blind Stranger Test

| Required statement | Screenshot carrier | Result |
|---|---|---|
| These are live CLI agent sessions, not services. | The repeated run identity bands visibly pair `session agent-01`, `target wt/control-room`, `command pytest`, `model openai/gpt-5.6-sol`, `attempt 1`, and the live status mark. | **PASS** |
| That run needs a decision. | The left work queue visibly says `DECISION`, `state pending`, `kind approve`, and `eligible approve`; the matching first row repeats `eligible approve` beside `controller`. | **PASS** |
| Spend is against a hard budget. | Each run shows a reserved/cap pair such as `$3.40/$5.00`, a settlement/source token, and an attached headroom bar. The COST constraint ledger independently shows quota and its headroom bar. | **PASS** |
| Evidence is inspectable. | Each row visibly separates italic `said claimed pass` from green `measured tests pending`, then shows `source abc1234` and `receipt recorded`. The row is an addressable run object, not an unscoped status tile. | **PASS** |

## Selector Crosswalk

These selectors identify the screenshot carriers for the audit trail. They are not required reading for
the blind verdict above.

| Claim | Exact selector |
|---|---|
| Live CLI agent session | `.run-row[data-run-id] .session-band[data-agent]` |
| Run needs a decision | `[data-answer="ON-G5"] [data-field="decision.state"]` plus `[data-answer="ON-G5"] [data-field="decision.eligibility"]` |
| Spend against hard budget | `.run-row[data-run-id] .row-lease[data-budget-state]` plus `.run-row[data-run-id] [data-budget-cap]` |
| Evidence is inspectable | `.run-row[data-run-id] .row-evidence [data-evidence-class="advisory"]` plus `.run-row[data-run-id] .row-evidence [data-evidence-class="measured"]` |

## Eight-Move Check

The screenshot retains the eight distinctive moves required by the direction brief:

1. Session identity leads each row.
2. The selected inspector has an attempt-scoped causal ladder.
3. Eligibility and receipt are visible decision-object tokens.
4. ADVISORY and MEASURED evidence use different visual materials.
5. Rows carry typed run/spec/phase/attempt information on a persistent roster.
6. Cost is attached to the attempt through the lease bar and reserved/cap pair.
7. The selected inspector has one bounded attempt feed with follow/pause.
8. Attention is a ranked work queue with reserved decision and risk capacity.

## Disposition

No design finding remains open for this pass. The mechanical render gate and semantic glance gate are
the supporting evidence; the design verdict itself is based on the pixels in the resting desktop
capture.
