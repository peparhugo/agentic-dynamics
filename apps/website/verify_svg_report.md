# SVG rendering gate — PASS (site revamp4 diagrams)

Gate: `apps/website/verify_svg_rendering.py` — playwright rendering gate for the site's
inline SVGs. Criteria per SVG: **SIZE** (rendered box > 100px both axes), **OVERFLOW**
(none beyond the scrollable area), **ASPECT** (rendered ratio ≈ viewBox), **BALANCE**
(text/shape — no empty shell, no text wall). Intentionally hidden SVGs are reported SKIP.

Run (from `apps/website/`, viewports 1440x900 and 390x844):

```bash
python3 verify_svg_rendering.py --mobile
```

Result: **20/20 PASS, 0 FAIL, exit 0** (before the fix: 1 FAIL — the 0x0 hidden
architecture-map — plus two wide-aspect figures crushing to <100px height on mobile).

## Per-SVG table

| page | svg | viewBox | rendered | aspect | text | shapes | verdict |
|---|---|---|---|---|---|---|---|
| framework.html | svg#0(diagram-map workflow-map) | 0 0 1440 760 | 1034x546 | 0.001 | 2260 | 36 | ✔ PASS |
| framework.html | svg#1 (eight planes) | 0 0 760 360 | 1100x522 | 0.002 | 467 | 16 | ✔ PASS |
| framework.html | svg#2 (instrument cycle) | 0 0 760 190 | 1100x277 | 0.007 | 231 | 6 | ✔ PASS |
| framework.html | svg#3 (two modes) | 0 0 760 200 | 1100x291 | 0.005 | 302 | 7 | ✔ PASS |
| framework.html | svg#4 (autonomy envelope) | 0 0 760 260 | 1100x378 | 0.004 | 324 | 7 | ✔ PASS |
| framework.html | svg#5(diagram-map autonomy-map) | 0 0 1440 760 | 1034x546 | 0.001 | 2112 | 32 | ✔ PASS |
| question.html | svg#0 (N×M map) | 0 0 720 340 | 549x260 | 0.003 | 563 | 12 | ✔ PASS |
| evidence.html | svg#0 (escalation E_x) | 0 0 720 260 | 628x228 | 0.005 | 326 | 6 | ✔ PASS |
| evidence.html | svg#1 (calibration arc) | 0 0 720 220 | 628x193 | 0.006 | 310 | 6 | ✔ PASS |
| methodology.html | svg#0:cc-plot (N² curve) | 0 0 720 360 | 668x335 | 0.003 | 36 | 3 | ✔ PASS |
| framework.html | svg#0(diagram-map workflow-map) | 0 0 1440 760 | 900x475 | 0.000 | 2260 | 36 | ✔ PASS |
| framework.html | svg#1 (eight planes) | 0 0 760 360 | 358x171 | 0.008 | 467 | 16 | ✔ PASS |
| framework.html | svg#2 (instrument cycle) | 0 0 760 190 | 520x132 | 0.015 | 231 | 6 | ✔ PASS |
| framework.html | svg#3 (two modes) | 0 0 760 200 | 520x138 | 0.008 | 302 | 7 | ✔ PASS |
| framework.html | svg#4 (autonomy envelope) | 0 0 760 260 | 358x124 | 0.012 | 324 | 7 | ✔ PASS |
| framework.html | svg#5(diagram-map autonomy-map) | 0 0 1440 760 | 900x475 | 0.000 | 2112 | 32 | ✔ PASS |
| question.html | svg#0 (N×M map) | 0 0 720 340 | 352x167 | 0.005 | 563 | 12 | ✔ PASS |
| evidence.html | svg#0 (escalation E_x) | 0 0 720 260 | 356x130 | 0.011 | 326 | 6 | ✔ PASS |
| evidence.html | svg#1 (calibration arc) | 0 0 720 220 | 356x110 | 0.011 | 310 | 6 | ✔ PASS |
| methodology.html | svg#0:cc-plot (N² curve) | 0 0 720 360 | 356x179 | 0.006 | 36 | 3 | ✔ PASS |

Rows 1–10: 1440x900 viewport. Rows 11–20: 390x844 viewport.

## Before → After

| Defect (before) | Fix | After |
|---|---|---|
| framework.html architecture-map rendered 0x0 (dead `<figure hidden aria-hidden="true">`) | removed the dead hidden figure | gone — 0 defects |
| fw-cycle / twomodes crushed to 358x91 / 358x96 on mobile (unreadable) | wrapped in the shared `.diagram-scroll` well; base.css gives wide figure-edit maps a readable `min-width:520px` on narrow screens | 520x132 / 520x138 |
| `.system-figure` / `.diagram-scroll` / `.diagram-map` / `.workflow-map` / `.redesigned` grids had **no rules in base.css** | DIAGRAM SYSTEM section wired into `apps/website/base.css` (shared layout + `svg[viewBox]{max-width:100%;height:auto}` collapse-proof floor) | containers can never collapse; layout is shared, not page-local |
