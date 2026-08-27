# Operator review pack — site revamp4 diagrams (p3b craft-UX redesign)

**STOP: campaign halted — awaiting operator re-review. No deploy.**
Sign `APPROVAL.md` before any `firebase deploy`.

History: the first repair pack was **REJECTED by operator review on 2026-08-27**
("it's not really better, it has a lot of visual problems"; figure-by-figure:
eight-planes unclear, instrument-cycle bad contrast, one-engine-two-modes "UI not UX").
The REJECT stays on record; this pack is the p3b response. The approval artifact has
been reset to **awaiting**.

Gate: `apps/website/verify_svg_rendering.py` — SIZE (>100px both axes), OVERFLOW (none
beyond scroll area), ASPECT (rendered ≈ viewBox), BALANCE (text ≤ 1.5× shape markup),
**CONTRAST (every text fill vs its computed background ≥ 4.5:1 — the new WCAG AA gate)**,
PAINT (first-paint visibility, opaque, laid out), CONSOLE (no console error).

Result: **PASS** — 22/22 SVGs across all 9 pages at 1440x900 and 390x844, exit 0. Minimum
text contrast across every figure: **8.37:1** (the envelope's amber kicker); every other
figure ≥ 9.23:1.

## The four flagged figures — re-drawn in the template's visual language

The execution-engine / workflow-map composition (approved, "BEAUTIFUL") is now a **shared
figure grammar** in `apps/website/base.css`: numbered node cards, color-coded flows
(cyan = operate/measure, blue = control/decide, amber = campaign/proposed), haloed
flow-notes, a scale rail, and the glow/tracer accents. Every page figure reuses it.

| Flagged figure | Operator finding | Redesign (one legible message) | Before → After |
|---|---|---|---|
| Eight planes | "hard to understand, doesn't match the good figure" | One dependency-direction **flow**: 9 node cards in the canonical chain core → experiment → measurement → runtime → adapters → knowledge → reporting → **control** (glowing, "the only consumer") → **apps** (amber), arrowed left-to-right, with a tier rail (0/1/2/3) and the INSTRUMENTED/PROPOSED/DECIDED status line | text 217→682 · contrast min 4.47→9.95:1 |
| Instrument cycle | "terrible contrast, unclear message" | The load-bearing rule as a 5-node **ring**: instrument → derive → write policy → grid → campaign → repeat, with a red ✕ gate on the derive→policy arrow — "unmeasured requirement blocks policy". One message: derive is the only path into policy | text 79→499 · contrast min 3.84→9.95:1 |
| One engine, two modes | "UI but not UX" | **Converge → one engine → diverge**: operate (1 cell) and experiment (G cells) feed one glowing engine pill (cell → compile → jobs → attempts → ledger), then split to record (operate) vs compare+adapt (experiment). One message: the engine never changes, only the grid adds compare+adapt | text 128→572 · contrast min 3.84→9.95:1 |
| Bounded-autonomy envelope | same disease (hardcoded hex, pattern-fill text, red-on-dark) | Human policy boundary (amber dashed) wraps declared constraints + independent verification, with the PROPOSED typed-checkpoints cell glowing amber ("designed capability — NOT RUN") and the accept / reject·rework / halt·escalate exits; PROPOSED ≠ RUN stated at the foot | text 136→510 · contrast min 2.17→8.37:1 |

The same disease was also fixed on the **index instrument cycle**, the **question N×M
measurement map**, the **evidence escalation E_x** figure and the **calibration arc** — all
re-drawn in the shared grammar (data-driven ids preserved: `esc-*`, `cal-*`). The two
approved maps (workflow-map, autonomy-map) keep their composition and inherit the shared
classes untouched. The contrast gate is new in this pass and checks every text fill on
every figure, resolving gradients/patterns/stroke-halos and compositing alpha.

## Per-figure rendering table (1440x900; mobile sizes in `gate_report_full.md`)

| page | figure | viewBox | rendered | text | shape markup | contrast | verdict |
|---|---|---|---|---|---|---|---|
| index | instrument cycle | 0 0 1440 580 | 1120x452 | 499 | 1588 | 9.95:1 | PASS |
| framework | OPERATING MODEL map | 0 0 1440 760 | 1034x546 | 1140 | 2629 | 10.97:1 | PASS |
| framework | eight planes | 0 0 1440 560 | 1100x429 | 682 | 1931 | 9.95:1 | PASS |
| framework | instrument cycle | 0 0 1440 580 | 1100x444 | 499 | 1588 | 9.95:1 | PASS |
| framework | ONE ENGINE / TWO MODES | 0 0 1440 520 | 1100x399 | 572 | 1164 | 9.95:1 | PASS |
| framework | bounded-autonomy envelope | 0 0 1440 560 | 1100x429 | 510 | 1301 | 8.37:1 | PASS |
| framework | autonomy map | 0 0 1440 760 | 1034x546 | 1005 | 2389 | 9.23:1 | PASS |
| question | N × M measurement map | 0 0 1440 520 | 980x355 | 433 | 1556 | 9.95:1 | PASS |
| evidence | escalation E_x | 0 0 1440 420 | 980x287 | 336 | 819 | 9.95:1 | PASS |
| evidence | calibration arc | 0 0 1440 360 | 980x247 | 406 | 820 | 9.95:1 | PASS |
| methodology | N² cost curve | 0 0 720 360 | 668x335 | 36 | 546 | 17.19:1 | PASS |

Every figure sits under the 1.5× label-wall flag (max 0.433, the OPERATING MODEL map) and
clears WCAG AA on every text fill. Full per-SVG table (both viewports) + JSON:
`gate_report_full.md` / `gate_report_full.json`.

## Screenshots

All 9 pages × 2 viewports in this directory (`revamp4_<page>_<width>x<height>.png`).
Index page: `revamp4_index_*.png` · framework: `revamp4_framework_*.png` · question:
`revamp4_question_*.png` · evidence: `revamp4_evidence_*.png` · methodology:
`revamp4_methodology_*.png` · story: `revamp4_story_*.png` · accelerator:
`revamp4_accelerator_*.png` · databricks: `revamp4_databricks_*.png` · glossary:
`revamp4_glossary_*.png`.

## Next action

Operator: re-review the screenshots + this table, then sign `APPROVAL.md` again
(APPROVE / REJECT). No deploy runs until the signed approval lands; the previous REJECT
stays on record until then.
