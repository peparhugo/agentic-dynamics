# SVG rendering gate — PASS (site revamp4 diagrams, craft pass)

Gate: `apps/website/verify_svg_rendering.py` — playwright rendering gate for the site's
inline SVGs. Criteria per SVG:

- **SIZE** — rendered box > 100px both axes (no 0x0, no collapse)
- **OVERFLOW** — none beyond the scrollable area (scroll-well-contained maps don't count)
- **ASPECT** — rendered ratio ≈ viewBox (aspect-correct, no distortion)
- **BALANCE** — rendered `<text>` label wall ≤ 1.5× shape markup length (a figure with
  more text than 1.5× its shapes is flagged and redesigned); never an empty shell.

Intentionally hidden SVGs are reported SKIP. Exit 0 = PASS.

Run (from `apps/website/`, viewports 1440x900 and 390x844):

```bash
python3 verify_svg_rendering.py --mobile
```

Result: **20/20 PASS, 0 FAIL, exit 0** on framework/question/evidence/methodology at
both viewports; **11/11 PASS** on the full site at 1440x900. Screenshots + gate data live
in `apps/website/verification/`.

## Per-SVG table (rows 1–10 desktop, 11–20 mobile)

| page | svg | viewBox | rendered | text | shape markup | verdict |
|---|---|---|---|---|---|---|
| framework.html | svg#0(diagram-map workflow-map) | 0 0 1440 760 | 1034x546 | 1140 | 2633 | ✔ PASS |
| framework.html | svg#1 (eight planes) | 0 0 760 360 | 1100x522 | 217 | 1512 | ✔ PASS |
| framework.html | svg#2 (instrument cycle) | 0 0 760 190 | 1100x277 | 79 | 622 | ✔ PASS |
| framework.html | svg#3 (two modes) | 0 0 760 200 | 1100x291 | 128 | 676 | ✔ PASS |
| framework.html | svg#4 (autonomy envelope) | 0 0 760 260 | 1100x378 | 136 | 789 | ✔ PASS |
| framework.html | svg#5(diagram-map autonomy-map) | 0 0 1440 760 | 1034x546 | 1005 | 2392 | ✔ PASS |
| question.html | svg#0 (N×M map) | 0 0 720 340 | 549x260 | 247 | 1127 | ✔ PASS |
| evidence.html | svg#0 (escalation E_x) | 0 0 720 260 | 628x228 | 148 | 551 | ✔ PASS |
| evidence.html | svg#1 (calibration arc) | 0 0 720 220 | 628x193 | 156 | 566 | ✔ PASS |
| methodology.html | svg#0:cc-plot (N² curve) | 0 0 720 360 | 668x335 | 36 | 546 | ✔ PASS |
| framework.html | svg#0(diagram-map workflow-map) | 0 0 1440 760 | 900x475 | 1140 | 2633 | ✔ PASS |
| framework.html | svg#1 (eight planes) | 0 0 760 360 | 358x171 | 217 | 1512 | ✔ PASS |
| framework.html | svg#2 (instrument cycle) | 0 0 760 190 | 520x132 | 79 | 622 | ✔ PASS |
| framework.html | svg#3 (two modes) | 0 0 760 200 | 520x138 | 128 | 676 | ✔ PASS |
| framework.html | svg#4 (autonomy envelope) | 0 0 760 260 | 358x124 | 136 | 789 | ✔ PASS |
| framework.html | svg#5(diagram-map autonomy-map) | 0 0 1440 760 | 900x475 | 1005 | 2392 | ✔ PASS |
| question.html | svg#0 (N×M map) | 0 0 720 340 | 352x167 | 247 | 1127 | ✔ PASS |
| evidence.html | svg#0 (escalation E_x) | 0 0 720 260 | 356x130 | 148 | 551 | ✔ PASS |
| evidence.html | svg#1 (calibration arc) | 0 0 720 220 | 356x110 | 156 | 566 | ✔ PASS |
| methodology.html | svg#0:cc-plot (N² curve) | 0 0 720 360 | 356x179 | 36 | 546 | ✔ PASS |

## Before → After (rendering defects + craft)

| Item (before) | Fix | After |
|---|---|---|
| architecture-map rendered 0x0 (dead `<figure hidden aria-hidden="true">`) | removed the dead hidden figure | gone — 0 defects |
| fw-cycle / twomodes crushed to 358x91 / 358x96 on mobile | wrapped in the shared `.diagram-scroll` well; base.css gives wide figure-edit maps a readable `min-width:520px` | 520x132 / 520x138 |
| `.system-figure` / `.diagram-scroll` / `.diagram-map` / `.workflow-map` / `.redesigned` had no base.css layout | DIAGRAM SYSTEM wired into `base.css` (+ `svg[viewBox]` collapse-proof floor) | containers can never collapse |
| OPERATING MODEL header was an 83-char sentence wall | short tagline; full wording kept in `<desc>` + section lead | text 1176 → 1140 |
| autonomy-map: 78-char title list + 100-char paragraph + 80-char header | short labels; full wording kept in `<desc>` + `.human-plane` fallback | text 1149 → 1005 |
| eight planes cited `svg-filter-focus` but had no filter | `planeFocus` glow on the control plane — reference genuinely adapted | ratio 0.146 → 0.144 |
| envelope cited `svg-filter-focus` but had no filter | `envFocus` glow on the PROPOSED cell — reference genuinely adapted | ratio 0.178 → 0.172 |

All figures sit well under the 1.5× label-wall flag (max 0.433 for the workflow-map).
Per-figure before/after detail: `apps/website/verification/index.md`.
