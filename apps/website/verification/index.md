# Operator review pack — site revamp4 diagrams

**STOP: campaign halted — awaiting operator visual approval. No deploy.**
Sign `APPROVAL.md` before any `firebase deploy`.

Gate: `apps/website/verify_svg_rendering.py` — full criteria: SIZE (>100px both axes),
OVERFLOW (none beyond scroll area), ASPECT (rendered ≈ viewBox), BALANCE (rendered
`<text>` ≤ 1.5× shape markup), PAINT (first-paint visibility, opaque, laid out),
CONSOLE (no console error / page exception).

Result: **PASS** — 22/22 SVGs across all 9 pages at 1440x900 and 390x844, exit 0.

## Per-figure rendering table (1440x900; mobile sizes in the full gate report)

| page | figure | viewBox | rendered | text | shape markup | verdict |
|---|---|---|---|---|---|---|
| index | instrument cycle | 0 0 720 320 | 1120x499 | 142 | 592 | PASS |
| framework | OPERATING MODEL map | 0 0 1440 760 | 1034x546 | 1140 | 2633 | PASS |
| framework | eight planes | 0 0 760 360 | 1100x522 | 217 | 1512 | PASS |
| framework | instrument cycle | 0 0 760 190 | 1100x277 | 79 | 622 | PASS |
| framework | ONE ENGINE / TWO MODES | 0 0 760 200 | 1100x291 | 128 | 676 | PASS |
| framework | bounded-autonomy envelope | 0 0 760 260 | 1100x378 | 136 | 789 | PASS |
| framework | autonomy map | 0 0 1440 760 | 1034x546 | 1005 | 2392 | PASS |
| question | N × M measurement map | 0 0 720 340 | 549x260 | 247 | 1127 | PASS |
| evidence | escalation E_x | 0 0 720 260 | 628x228 | 148 | 551 | PASS |
| evidence | calibration arc | 0 0 720 220 | 628x193 | 156 | 566 | PASS |
| methodology | N² cost curve | 0 0 720 360 | 668x335 | 36 | 546 | PASS |

All figures sit under the 1.5× label-wall flag (max 0.433, the OPERATING MODEL map).
Full per-SVG table (both viewports) + JSON: `gate_report_full.md` / `gate_report_full.json`.

## Before → After (the 'low brow' complaint vs the repaired figures)

| Complaint (before) | Repair (after) |
|---|---|
| OPERATING MODEL figure collapsed — its container classes had **no rules in base.css** (page-local only) | DIAGRAM SYSTEM wired into `apps/website/base.css`: `.system-figure`, `.diagram-scroll`, `.diagram-map`/`.workflow-map`, `.redesigned` grids + a `svg[viewBox]{max-width:100%;height:auto}` collapse-proof floor. Layout shared, never page-local |
| dead 0x0 architecture-map rendered in the DOM | removed (it was `hidden aria-hidden` dead code) |
| wide-aspect figures crushed to 358x91 / 358x96 on mobile (unreadable strips) | shared `.diagram-scroll` wells + `min-width:520px` floor → 520x132 / 520x138, horizontally scrollable |
| text walls — OPERATING MODEL header 83 chars, autonomy map had a 78-char title list + 100-char paragraph + 80-char header | trimmed to short labels + color-coded zones + numbered callouts; full wording preserved in `<desc>` + page copy. text 1176→1140 (map), 1149→1005 (autonomy) |
| example-library reference `svg-filter-focus.html` cited but not applied | planes figure now glows the control plane; envelope now glows the PROPOSED cell — references genuinely adapted |
| aspect/scaling could distort (viewBox-only SVGs) | `width:100%;height:auto` + min-width floors; gate asserts rendered ≈ viewBox |

## Screenshots

All 9 pages × 2 viewports in this directory (`revamp4_<page>_<width>x<height>.png`).
Index page: `revamp4_index_*.png` · framework: `revamp4_framework_*.png` · question:
`revamp4_question_*.png` · evidence: `revamp4_evidence_*.png` · methodology:
`revamp4_methodology_*.png` · story: `revamp4_story_*.png` · accelerator:
`revamp4_accelerator_*.png` · databricks: `revamp4_databricks_*.png` · glossary:
`revamp4_glossary_*.png`.

## Next action

Operator: review the screenshots + this table, then sign `APPROVAL.md`
(APPROVE / REJECT). No deploy runs until the signed approval lands.
