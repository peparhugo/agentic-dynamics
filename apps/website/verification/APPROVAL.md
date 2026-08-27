# Visual approval — site revamp4 diagrams (p3b craft-UX redesign)

**Status: AWAITING operator re-review (2026-08-27). No deploy.**
The first repair pack was **REJECTED by operator review on 2026-08-27** — figure-by-figure:
eight-planes unclear, instrument-cycle bad contrast, one-engine-two-modes "UI not UX".
That REJECT stays on record. This artifact is reset to awaiting for the p3b redesign
(review pack + screenshots regenerated in this directory).

Hard rule 5: the repaired build is not deployed until the operator visually
approves it. Review the screenshots in this directory (and the per-figure table
in `index.md`), then sign below. Deployment targets BOTH Firebase hosts:
`ai-finops-rulebook` (canonical, never retire) + `agentic-dynamics` (mirror).

## What is being approved (the p3b response to the REJECT)

- **Eight planes, one dependency direction** — re-drawn as a one-direction dependency
  flow in the EXACT visual language of the approved execution-engine figure: 9 numbered
  node cards in the canonical chain (core → … → control → apps) with flow arrows, CONTROL
  glowing as the only consumer, APPS amber, plus a tier rail and the status line.
- **The instrument cycle** — the load-bearing rule as a real ring (instrument → derive →
  write policy → grid → campaign → repeat) with a red ✕ gate on the derive→policy arrow:
  "unmeasured requirement blocks policy". No more color-on-color; every fill/text pair
  clears WCAG AA.
- **One engine, two operating modes** — converge → one engine → diverge: operate (1 cell)
  and experiment (G cells) feed one glowing engine pill, then split to record vs
  compare+adapt. The shared engine is structurally legible.
- **Every figure with the same disease** (bounded-autonomy envelope, index instrument
  cycle, question N×M map, evidence escalation + calibration arc) was re-drawn in the same
  shared grammar. The approved maps keep their composition untouched.
- **The contrast gate** — `apps/website/verify_svg_rendering.py` now computes WCAG AA
  contrast for every text fill vs its computed background (≥ 4.5:1), resolving
  gradients/patterns/stroke-halos and compositing alpha. PASS on all figures, min 8.37:1.

## Gate (both viewports, all 9 pages)

SIZE >100px both axes · zero OVERFLOW · ASPECT-correct · BALANCE (text ≤ 1.5× shape
markup) · CONTRAST ≥ 4.5:1 every text fill · PAINT (first-paint visibility) · CONSOLE
clean. **22/22 PASS** at 1440x900 and 390x844, exit 0. Full table:
`gate_report_full.md` / `gate_report_full.json`.

## Screenshots (operator-visible output)

| page | 1440x900 | 390x844 |
|---|---|---|
| index | `revamp4_index_1440x900.png` | `revamp4_index_390x844.png` |
| framework | `revamp4_framework_1440x900.png` | `revamp4_framework_390x844.png` |
| question | `revamp4_question_1440x900.png` | `revamp4_question_390x844.png` |
| evidence | `revamp4_evidence_1440x900.png` | `revamp4_evidence_390x844.png` |
| methodology | `revamp4_methodology_1440x900.png` | `revamp4_methodology_390x844.png` |
| story | `revamp4_story_1440x900.png` | `revamp4_story_390x844.png` |
| accelerator | `revamp4_accelerator_1440x900.png` | `revamp4_accelerator_390x844.png` |
| databricks | `revamp4_databricks_1440x900.png` | `revamp4_databricks_390x844.png` |
| glossary | `revamp4_glossary_1440x900.png` | `revamp4_glossary_390x844.png` |

Per-figure table and the REJECT→redesign mapping: `index.md` · gate data:
`gate_report_full.md` / `gate_report_full.json`.

## Signature

I have visually reviewed the p3b redesign's screenshots and the per-figure table, and I
approve deploying this build to BOTH Firebase hosts.

```
Decision (check one):
  [x] APPROVE  — proceed to deploy (firebase deploy --only hosting
                 and firebase deploy --only hosting --project agentic-dynamics)
  [ ] REJECT   — do not deploy; changes requested below

Operator name:   peparhugo
Role / title:    Operator
Date (YYYY-MM-DD): 2026-08-27
Signature / token: peparhugo
Approval ref (branch + commit): feature/site-revamp4-diagrams (p3b re-craft reviewed)
Changes requested (if REJECT):
  1. ____________________________________________________
  2. ____________________________________________________
  3. ____________________________________________________
```

Prior record: REJECTED 2026-08-27 (figure-by-figure: eight-planes unclear,
instrument-cycle contrast, one-engine-two-modes "UI not UX"). This template is the
approval gate — the signed copy (or the signed decision line) is required before any
`firebase deploy` on this branch.
