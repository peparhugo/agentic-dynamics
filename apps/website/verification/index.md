# SVG craft pass — phase artifact (site revamp4)

Gate: `apps/website/verify_svg_rendering.py` (balance check added in the craft pass:
per figure, rendered `<text>` length ≤ 1.5× shape markup length; label walls are
flagged and the figure redesigned). Screenshots below are the operator-visible output.

Result: **PASS** — 20/20 on framework/question/evidence/methodology (1440x900 + 390x844),
11/11 on the full site (1440x900). Exit 0.

## Per-figure text/shape before → after (rendered `<text>` chars vs shape-markup chars)

| figure (page) | before text/markup | after text/markup | before ratio | after ratio | verdict |
|---|---|---|---|---|---|
| workflow-map — OPERATING MODEL (framework) | 1176 / 2633 | 1140 / 2633 | 0.447 | 0.433 | PASS |
| autonomy-map — bounded autonomy (framework) | 1149 / 2392 | 1005 / 2392 | 0.480 | 0.420 | PASS |
| eight planes (framework) | 217 / 1486 | 217 / 1512 | 0.146 | 0.144 | PASS |
| instrument cycle (framework) | 79 / 622 | 79 / 622 | 0.127 | 0.127 | PASS |
| ONE ENGINE / TWO MODES (framework) | 128 / 676 | 128 / 676 | 0.189 | 0.189 | PASS |
| bounded-autonomy envelope (framework) | 136 / 765 | 136 / 789 | 0.178 | 0.172 | PASS |
| N × M measurement map (question) | 247 / 1127 | 247 / 1127 | 0.219 | 0.219 | PASS |
| escalation E_x (evidence) | 148 / 551 | 148 / 551 | 0.269 | 0.269 | PASS |
| calibration arc (evidence) | 156 / 566 | 156 / 566 | 0.276 | 0.276 | PASS |
| N² cost curve (methodology) | 36 / 546 | 36 / 546 | 0.066 | 0.066 | PASS |

Every figure is well under the 1.5× flag; the two maps' label walls were reduced
and their moves preserved in `<desc>`/page copy.

## Craft changes this pass

- **OPERATING MODEL map** — header sentence wall trimmed to a short tagline
  (`FIX THE FACTORS TO OPERATE · VARY THEM TO LEARN`); the full sentence stays in the
  figure `<desc>` and the section lead.
- **autonomy map** — header sentence, the human-control-plane title list (78 chars)
  and its paragraph copy (100 chars) reduced to short labels; full wording preserved in
  `<desc>` and the `.human-plane` fallback text.
- **eight planes** — now genuinely adapts the cited `svg-filter-focus.html` reference
  (was cited but no filter existed): added a `planeFocus` glow on the control plane.
- **bounded-autonomy envelope** — now genuinely adapts the cited `svg-filter-focus.html`
  reference: added an `envFocus` glow on the PROPOSED typed-checkpoints cell (the
  "proposed, not run" distinction). `svg-pattern-surface.html` (hatch) already applied.
- Aspect/scaling unchanged — the previous pass's `width:100%;height:auto` + min-width
  floors guarantee no distortion and no collapse; re-verified by the gate.

## Screenshots (operator-visible output)

| page | 1440x900 | 390x844 |
|---|---|---|
| framework | `revamp4_framework_1440x900.png` | `revamp4_framework_390x844.png` |
| question | `revamp4_question_1440x900.png` | `revamp4_question_390x844.png` |
| evidence | `revamp4_evidence_1440x900.png` | `revamp4_evidence_390x844.png` |
| methodology | `revamp4_methodology_1440x900.png` | `revamp4_methodology_390x844.png` |

Gate data: `gate_report.md` (table) · `gate_report.json` (machine-readable).

## Status

**STOP — awaiting operator visual approval. No deploy.**
