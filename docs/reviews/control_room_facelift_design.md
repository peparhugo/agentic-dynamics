---
status: accepted
---

# Control Room facelift - screenshot design adversary (a5)

**Reviewer:** `openai/gpt-5.6-luna`  
**Date:** 2026-09-11  
**Scope:** the retained screenshots in `apps/control_room/verification/`, the gate report, and the
rendered Control Room surface. This is a screenshot-level design review, not a code-quality review.

## Verdict

**FAIL - REWORK REQUIRED.**

The surface is a careful, readable run dashboard, but it does not yet pass the brief's stranger test.
The desktop screenshot can communicate that rows represent agent sessions and that claims differ from
measured results. Its primary visual grammar is still:

```text
truth bar -> alert cards -> service-style run table -> KPI rail
```

That is the exact thesis-failure description prohibited by the brief
(`docs/research/control_room_direction.md:480-492`). Removing the logo would leave a familiar
observability console. The screenshots therefore do not prove a distinctive multi-CLI-agent control
surface, even though the render gate reports **PASS** for geometry, contrast, first paint, and console
cleanliness.

## Review Method

I inspected the representative resting captures for F-0, F-1, F-5, F-7, and live mode at desktop and
mobile, plus the selected evidence, trends, visuals, and style captures. I assessed the pixels before
using the brief to name the expected carrier. No selection, hover, tooltip, color-only inference, or
explanatory prose was used for the resting-screen judgment.

The machine gate is useful evidence for rendering invariants, but it is not a semantic recognizability
test. `gate_report.md` records 36 dark-theme captures and zero mechanical violations; it records no
blind five-answer score and no generic observability comparator result.

## Findings

| ID | Severity | Finding | Screenshot evidence | Required disposition |
|---|---|---|---|---|
| A5-D1 | **BLOCKER** | The resting composition is still dashboard costume. | `F-0_desktop_dark_1440x900.png` has a top trust bar, a boxed ATTENTION stack, a boxed RUN LEDGER made of repeated cards, and boxed COST/HEALTH/MODEL panels. `F-0_mobile_dark_390x844.png` preserves the same dashboard stack vertically. | Recompose the first screen around the run object, not around panels. Make the session identity band and the coupled evidence/decision boundary the dominant axis. Demote or remove the boxed KPI-style side rail, repeated empty attention cards, and generic alert-card treatment. Re-run a blind comparison against a Grafana/Datadog-like screen and require the Control Room to be identifiable without its title. |
| A5-D2 | **CRITICAL** | The required hard-budget carrier is absent from actionable run rows. | In `F-0_desktop_dark_1440x900.png`, each row exposes only `cost metered`; reserved/settled values, `cost_source`, hard cap, and headroom live separately in COST. The row is not visibly a spend-against-budget object. The live screenshot makes the failure clearer with `cost unknown` and an unrelated unknown COST panel. | Attach a compact lease/cost band to every actionable row: reserved, settled, source class, cap/headroom, and settlement state. Keep R3a as a bounded exception summary, not the sole carrier. Add a fixture with a known hard cap and assert that a stranger can identify budget risk from the row alone. |
| A5-D3 | **HIGH** | Mobile fails the identity-band recognizability requirement through truncation and label removal. | In `F-0_mobile_dark_390x844.png` and `live_mobile_dark_390x844.png`, session, target, and model values are ellipsized (`agent...`, `wt/control-r...`, `openai/gpt-5.6...`), while field labels disappear. The evidence line is compressed to values such as `claimed` and `pending`, so the authority classes are no longer self-identifying. | Give mobile rows a deliberate two-line identity band with a stable short session token, target basename, current command, provider/model, and attempt. Preserve the text labels or use explicit semantic marks; never make the stranger reconstruct field meaning from order or color. Add a mobile blind comprehension assertion, not only a box/overflow assertion. |
| A5-D4 | **HIGH** | Move 2 is not visibly an attempt-scoped causal ladder. | `visuals_desktop_dark_1440x900.png` and `visuals_mobile_dark_390x844.png` show a flat field list beside a horizontal sequence of `session`, `control`, model, `verify`, and `projections` nodes. The node strip reads as dependency health, not `session -> phase -> attempt -> narration/measured/source/cost/decision/record`. Attempts have no visible timestamps or nested causal boundary. | Make the selected inspector structurally causal: session, phase, and attempt must be nested boundaries, with typed evidence rungs and timestamps beneath the attempt. Separate the dependency-health link from the run's evidence ladder. Capture a selected-run adversary screenshot that proves the distinction without relying on the code or labels in this review. |
| A5-D5 | **HIGH** | Move 7, the bounded selected-attempt feed with follow/pause, is not present in the reviewed surface. | The selected evidence captures contain the ladder and an `Open dependency health` link, but no bounded attempt feed, follow state, pause control, or aged stream content. The static client only follows the global `/api/events` stream for transitions (`apps/control_room/static/app.js:706-732`). | Implement or explicitly defer the selected-attempt feed. If implemented, show bounded output, age, follow/pause state, and ADVISORY/MEASURED material. Add a screenshot and browser assertion for the control. If deferred, remove Move 7 from the claimed completed-move set rather than treating global SSE as equivalent. |
| A5-D6 | **HIGH** | The typed address grammar is asserted in field labels, not carried as an addressable operating grammar. | Rows show `session`, `target`, `command`, `model`, and `attempt`, but there is no compact stable `run`, `phase`, `attempt`, `session`, `worktree`, `lease`, or `record` address token. On mobile, the same fields become unlabeled truncated values. | Add a visible, copyable address band such as `run/<id> phase/<n> attempt/<n>`, with worktree and lease targets adjacent. Keep the roster persistent during selection and show the same address in the inspector. Test that a stranger can point to the object they would inspect or govern. |
| A5-D7 | **MEDIUM-HIGH** | Attention is technically ranked but visually falls back to generic alert cards and filler rows. | `F-0_desktop_dark_1440x900.png` uses colored left borders for DECISION/RISK/NEXT and then repeats `NO FURTHER ATTENTION` cards. The result resembles a generic alert queue and spends visual area on empty cards, despite the brief's rejection of generic red alert tiles and repeated status marks. | Render real attention items as run-linked work-queue entries with lifecycle, owner/authority, and next governed action. Use one compact empty state instead of repeated empty cards. Distinguish decision, operational risk, and advisory observation by structure and authority, not only border color. |
| A5-D8 | **MEDIUM** | The screenshot evidence does not support the report's full theme claim. | `gate_report.md:5-10` says dark, light, and forced-colors were run, but the retained capture index lists dark captures only. Light and forced-colors were mechanically exercised for contrast, not visually reviewed as screenshot adversaries. | Keep the mechanical theme run, but retain light and forced-colors captures for the required resting and selected adversary cases, or narrow the report language. A theme that changes truncation, hierarchy, or authority legibility needs visual review rather than a contrast-only pass. |

## Eight-Move Disposition

| Move | Verdict | Pixel judgment |
|---|---|---|
| 1. Session/agent identity is the row primary key | **PARTIAL** | Clearly visible on desktop rows; mobile truncation and hidden labels prevent stranger recognition in the required 390px capture. |
| 2. Inspector is an attempt-scoped causal ladder | **PARTIAL** | A selected ladder exists, but its horizontal dependency strip and flat field list do not make the required causal nesting visible. |
| 3. Consequential acts are decision objects | **PASS WITH CAVEAT** | `eligible approve`, `controller`, and `receipt recorded` are adjacent on the desktop row and in the attention item. The preview remains selection-only, as required. |
| 4. Narration and verification are different materials | **PASS DESKTOP / PARTIAL MOBILE** | Desktop pairs `said claimed pass` with `measured tests pending`; mobile drops the labels and relies too heavily on compact styling. |
| 5. Objects use a typed grammar on a persistent roster | **PARTIAL** | The roster persists, but the screenshot carries ordinary field labels rather than stable typed addresses. |
| 6. Cost is attached to attempt and lease | **FAIL** | The row has `cost metered`, while the budget numbers remain in a separate KPI-like COST panel. No row headroom or reserved/settled pair is visible. |
| 7. One selected evidence feed has follow/pause | **FAIL** | No selected-attempt feed or follow/pause control is visible in the retained selected captures. |
| 8. Attention is a durable state machine | **PARTIAL** | Decision/risk/next states are visible, but repeated alert cards and empty fillers make the result read as a generic alert panel rather than a run work queue. |

## Stranger Test

The brief requires all five statements to be identified and pointed to in both 1440px and 390px
resting captures. The current evidence does not meet that bar:

| # | Required statement | 1440px | 390px | Reason |
|---|---|---|---|---|
| 1 | These are AI agent sessions, not services. | **PARTIAL PASS** | **FAIL** | Desktop has session/target/command/model text; mobile truncates the identity band and removes labels. |
| 2 | That run is waiting on a person. | **PASS** | **PASS** | `approve` plus `controller` and the waiting decision item are visible. |
| 3 | This is spend against a hard budget. | **FAIL** | **FAIL** | Budget is a separate COST panel; rows do not show hard cap/headroom or reserved vs settled. |
| 4 | The agent claimed it passed, but that is not the verified result. | **PASS** | **FAIL** | Desktop explicitly says `said claimed pass` and `measured tests pending`; mobile removes the authority labels. |
| 5 | I can act from here, and it will be recorded. | **PASS WITH CAVEAT** | **PARTIAL** | Desktop shows eligibility, controller, and receipt; mobile keeps the words but the compressed row makes the relationship harder to parse. |

Because the required test must hold at both viewports, the overall recognizability result is **FAIL**.
This is a design failure, not a copy fix: the generic dashboard comparator was not supplied, and the
current screenshot itself already matches the brief's prohibited `truth bar + alert cards + service
table + KPI rail` description.

## What To Retain

- The run roster is the central data surface rather than four peer boards.
- Desktop rows visibly separate `said`/ADVISORY from `measured`/MEASURED.
- Eligibility is represented as a token, not an automatic action button.
- The selected evidence view preserves the roster and exposes source, cost, decision, and receipt.
- The geometry, no-scroll, contrast, first-paint, and console-clean checks are valuable regression rails.

## Required Disposition Order

1. Resolve **A5-D1/A5-D2** together: make the run identity, evidence authority, lease constraint, and
   governed action the primary composition; remove the dashboard shell and attach budget evidence to
   rows.
2. Resolve **A5-D3/A5-D6** at 390px: preserve a legible agent/worktree/command/model/attempt/address
   grammar without color-only inference or truncation that destroys recognition.
3. Resolve **A5-D4/A5-D5** in the selected state: implement the typed causal ladder and bounded
   follow/pause feed, or explicitly remove those moves from the claimed acceptance scope.
4. Resolve **A5-D7/A5-D8**: replace filler alert cards and retain screenshot evidence for every theme
   whose visual hierarchy is part of acceptance.
5. Add the actual blind five-answer test and a generic observability comparator. Do not upgrade the
   design verdict to PASS until a stranger identifies all five carriers at both required viewports.

**Disposition:** keep the current render gate as a mechanical regression suite, but do not treat its
`PASS` as the facelift design verdict. The facelift remains **REWORK REQUIRED**.
