---
status: accepted
---

# Control Room Facelift Repair - Canonical Glance IA Adversary (r4)

**Reviewer:** `openai/gpt-5.6-sol`
**Date:** 2026-09-11
**Scope:** the retained resting captures in `apps/control_room/verification/`, at desktop
`1440x900` and mobile `390x844`.
**Method:** screenshot-first inspection of F-0 and the forcing captures F-1 through F-7. The
screenshots were judged before consulting the semantic gate report. No selection, hover, link,
tooltip, or drill-down was used to supply an answer.

## Verdict

**PASS - every `ON-G1..G7` answer is an actual inline value or state at rest, with all seven
answers visible in one viewport at both required breakpoints.**

No answer is represented only by a link, placeholder, icon, or instruction to open another
surface. The desktop and mobile captures contain the same seven answers; mobile changes density,
not the information model.

## Canonical Answer Walk

| Answer | Desktop `1440x900` | Mobile `390x844` | Verdict |
|---|---|---|---|
| `ON-G1` system | R0 visibly states `browser up · 1s`, `control up · 2s`, `workers up · 4s`, and `proj up · 4s`. | The same four dimensions and ages are visible in the two-line machine rail. | **PASS** |
| `ON-G2` fleet state | The AGENT RUNS heading visibly states `running 5`, `queued 1`, `failed 1`, `live 3`, above the bounded run sample. | The same four exact counts are visible above three bounded run rows. | **PASS** |
| `ON-G3` risk | The reserved RISK row states target `run-failed`, state `active`, and action `inspect`. | The same target, state, and action are visible in the reserved mobile row. | **PASS** |
| `ON-G4` cost | COST visibly states spend `$12.40`, burn `$0.82/h`, quota `61%`, wallet `$7.60`, and leases `$2.10`, with source/age and the budget bar. | The same five values, source/age, and budget bar are visible above HEALTH. | **PASS** |
| `ON-G5` decision | The reserved DECISION row visibly states `pending`, `approve`, `eligible approve`, epoch `42`, and authority `controller`. | The same pending/approve/authority answer occupies the first attention row. | **PASS** |
| `ON-G6` trust | R0 visibly states epoch `42`, age `4s`, projection `current`, and degraded/stale/partial/unknown counts `0`. | The same trust values wrap across two short rows without leaving R0. | **PASS** |
| `ON-G7` fleet shape | R3c visibly gives MODEL, COND, PROV, and LIFE; each states full `top`, `other`, and `unknown` buckets. | The same four marginals and full bucket words are visible at the bottom of the viewport. | **PASS** |

## Forcing-Case Check

The baseline alone proves presence; the forcing fixtures prove that each carrier shows the changed
answer rather than a fixed label or placeholder.

| Fixture | Required forced answer | Desktop | Mobile | Verdict |
|---|---|---|---|---|
| F-1 | Saturated attention queue | Reserved DECISION and RISK remain first; ranked MEDIUM/LOW work fills the remaining slots. | Reserved DECISION and RISK remain visible within the three-row capacity. | **PASS** |
| F-2 | Large fleet totals | `running 80 · queued 60 · failed 40 · live 20` is visible. | The same `80/60/40/20` values are visible above the roster. | **PASS** |
| F-3 | Near-cap money | COST states `$48.10`, `$2.40/h`, `96%`, `$1.60`, `$9.90`, plus `near cap`. | The same five values and `near cap` are visible inline. | **PASS** |
| F-4 | Unknown values | All five COST values are literal `unknown`; trust unknown is `2`; provider unknown is `2`. | The same literal unknowns and provider unknown `2` are visible. | **PASS** |
| F-5 | Stale projection | SYSTEM states projections `degraded · 901s`; TRUST states age `901s`, projection `stale`, degraded `1`, stale `1`. | The same coupled stale/degraded values are visible in R0; COST provenance also states age `901s`. | **PASS** |
| F-6 | Browser disconnected independently | SYSTEM states browser `down · 7s` while control/workers/projections remain up. | The same independent browser failure is visible in the first machine-rail row. | **PASS** |
| F-7 | No decision / no risk | DECISION states `none`, kind/eligibility `none`, `NONE PENDING`; RISK states `all-clear`, action `none`; R2 no longer mirrors approval. | The same none-pending/all-clear answer is visible without contradictory approval text. | **PASS** |

## No-Scroll Check

In both F-0 resting captures, R0, R1, R2, R3a, R3b, and R3c are all visible inside the captured
viewport. No answer is cut off below the fold, and none needs a region scroll to reveal its
canonical value. The semantic render gate independently records zero page, region, or answer-scroll
violations across all fixtures and themes.

## Gate Corroboration

`apps/control_room/verification/gate_report.md` records **PASS**, 86 captures, and zero violations.
Its semantic class compares the rendered answer values to fixture truth; its geometry class checks
non-zero/in-viewport boxes and no scroll; its contrast walker covers all resting answer text. This
machine evidence corroborates the screenshot judgment but does not replace it.

## Findings

No missing inline answer, contradictory state, or below-fold canonical carrier was found at either
required breakpoint.

## Disposition

**The canonical glance IA passes.** The previous `REWORK REQUIRED` verdict in
`docs/reviews/control_room_facelift_ia.md` is closed by the repaired screenshots and semantic gate.
