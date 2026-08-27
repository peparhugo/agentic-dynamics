# SVG rendering gate — PASS (site revamp4 diagrams, p3b craft-UX redesign)

Gate: `apps/website/verify_svg_rendering.py` — playwright rendering gate for the site's
inline SVGs. Criteria per SVG:

- **SIZE** — rendered box > 100px both axes (no 0x0, no collapse)
- **OVERFLOW** — none beyond the scrollable area (scroll-well-contained maps don't count)
- **ASPECT** — rendered ratio ≈ viewBox (aspect-correct, no distortion)
- **BALANCE** — rendered `<text>` label wall ≤ 1.5× shape markup length (a figure with
  more text than 1.5× its shapes is flagged and redesigned); never an empty shell.
- **CONTRAST** — WCAG AA: every text fill vs its computed background ≥ 4.5:1 (the p3b
  addition; gradient/pattern fills resolve to their stops/paint, a paint-order stroke
  halo counts as the background, alpha is composited; the site's default dark theme is
  the review surface).
- **PAINT** — first-paint visibility: the page reports a first paint and every visible
  svg is painted (opaque, non-zero box, laid out).
- **CONSOLE** — the page loads console-clean: no console error or page exception.

Intentionally hidden SVGs are reported SKIP. Exit 0 = PASS.

Run (from `apps/website/`, viewports 1440x900 and 390x844):

```bash
python3 verify_svg_rendering.py --mobile --pages index,framework,question,evidence,methodology,story,accelerator,databricks,glossary
```

Result: **22/22 PASS, 0 FAIL, exit 0** — all 9 pages at both viewports, console clean,
first paint present on every page, every text fill ≥ WCAG AA. Screenshots + gate data +
the approval template live in `apps/website/verification/`.

## Per-SVG table (rows 1–11 desktop, 12–22 mobile)

| page | svg | viewBox | rendered | text | shape markup | contrast | verdict |
|---|---|---|---|---|---|---|---|
| index.html | svg#0(diagram-map) instrument cycle | 0 0 1440 580 | 1120x452 | 499 | 1588 | 9.95:1 | ✔ PASS |
| framework.html | svg#0(diagram-map workflow-map) | 0 0 1440 760 | 1034x546 | 1140 | 2629 | 10.97:1 | ✔ PASS |
| framework.html | svg#1(diagram-map) eight planes | 0 0 1440 560 | 1100x429 | 682 | 1931 | 9.95:1 | ✔ PASS |
| framework.html | svg#2(diagram-map) instrument cycle | 0 0 1440 580 | 1100x444 | 499 | 1588 | 9.95:1 | ✔ PASS |
| framework.html | svg#3(diagram-map) two modes | 0 0 1440 520 | 1100x399 | 572 | 1164 | 9.95:1 | ✔ PASS |
| framework.html | svg#4(diagram-map) envelope | 0 0 1440 560 | 1100x429 | 510 | 1301 | 8.37:1 | ✔ PASS |
| framework.html | svg#5(diagram-map autonomy-map) | 0 0 1440 760 | 1034x546 | 1005 | 2389 | 9.23:1 | ✔ PASS |
| question.html | svg#0(diagram-map) N×M map | 0 0 1440 520 | 980x355 | 433 | 1556 | 9.95:1 | ✔ PASS |
| evidence.html | svg#0(diagram-map) escalation E_x | 0 0 1440 420 | 980x287 | 336 | 819 | 9.95:1 | ✔ PASS |
| evidence.html | svg#1(diagram-map) calibration arc | 0 0 1440 360 | 980x247 | 406 | 820 | 9.95:1 | ✔ PASS |
| methodology.html | svg#0:cc-plot | 0 0 720 360 | 668x335 | 36 | 546 | 17.19:1 | ✔ PASS |
| index.html | svg#0(diagram-map) instrument cycle | 0 0 1440 580 | 520x211 | 499 | 1588 | 9.95:1 | ✔ PASS |
| framework.html | svg#0(diagram-map workflow-map) | 0 0 1440 760 | 900x475 | 1140 | 2629 | 10.97:1 | ✔ PASS |
| framework.html | svg#1(diagram-map) eight planes | 0 0 1440 560 | 520x203 | 682 | 1931 | 9.95:1 | ✔ PASS |
| framework.html | svg#2(diagram-map) instrument cycle | 0 0 1440 580 | 520x211 | 499 | 1588 | 9.95:1 | ✔ PASS |
| framework.html | svg#3(diagram-map) two modes | 0 0 1440 520 | 520x189 | 572 | 1164 | 9.95:1 | ✔ PASS |
| framework.html | svg#4(diagram-map) envelope | 0 0 1440 560 | 520x203 | 510 | 1301 | 8.37:1 | ✔ PASS |
| framework.html | svg#5(diagram-map autonomy-map) | 0 0 1440 760 | 900x475 | 1005 | 2389 | 9.23:1 | ✔ PASS |
| question.html | svg#0(diagram-map) N×M map | 0 0 1440 520 | 520x189 | 433 | 1556 | 9.95:1 | ✔ PASS |
| evidence.html | svg#0(diagram-map) escalation E_x | 0 0 1440 420 | 520x153 | 336 | 819 | 9.95:1 | ✔ PASS |
| evidence.html | svg#1(diagram-map) calibration arc | 0 0 1440 360 | 520x132 | 406 | 820 | 9.95:1 | ✔ PASS |
| methodology.html | svg#0:cc-plot | 0 0 720 360 | 356x179 | 36 | 546 | 17.19:1 | ✔ PASS |

All figures sit well under the 1.5× label-wall flag (max 0.433, the workflow-map) and every
text fill clears WCAG AA (min 8.37:1, the envelope's amber kicker).

## p3b — the operator's figure-by-figure REJECT (2026-08-27), addressed

| Figure (operator finding) | p3b redesign | Contrast before → after |
|---|---|---|
| eight planes — "hard to understand, does not match the execution-engine figure" | re-drawn as a ONE-DIRECTION dependency flow in the exact workflow-map grammar: 9 numbered node cards (core → … → control → apps) with flow arrows, CONTROL glowing as the only consumer, APPS amber, a tier rail (0/1/2/3) and the status line. The figcaption's canonical chain is now the figure itself. | text 217→682 · min 4.47→9.95:1 |
| instrument cycle — "terrible contrast and an unclear message" | the load-bearing rule as a 5-node ring (instrument → derive → write policy → grid → campaign → repeat) with color-coded stages, an animated return tracer, and a red ✕ gate on the derive→policy arrow ("unmeasured requirement blocks policy"). The one message: derive is the only path into policy. | text 79→499 · min 3.84→9.95:1 |
| one engine, two operating modes — "UI but not UX" | a converge→one-engine→diverge composition: operate (1 cell) and experiment (G cells) inputs feed ONE glowing engine pill (cell → compile → jobs → attempts → ledger), then split to operate-path (record) and experiment-path (compare + adapt); the bottom line names the single difference. | text 128→572 · min 3.84→9.95:1 |
| ANY other figure with the same disease | the bounded-autonomy envelope (hardcoded `#287271/#9b6a28/#8a2f2f`, pattern-fill text), the index instrument cycle (unstyled flow-node text), the N×M measurement map, the escalation E_x figure and the calibration arc were ALL re-drawn in the shared grammar. The two approved maps (workflow-map, autonomy-map) keep their composition and simply inherit the shared classes. | envelope min 2.17→8.37:1 · all others ≥ 8.37:1 |

Shared figure grammar (the "exact visual language of the good figure") now lives in
`apps/website/base.css` (DIAGRAM SYSTEM → map internals): `.map-ground/.map-grid/
.map-kicker/.map-title/.map-copy/.map-node(.cyan/.blue/.amber/.danger)/.node-index/
.node-title/.node-copy/.flow(.cyan/.blue/.amber)/.flow-note/.mode-surface/.rail/
.scale-*/.tracer` + `@keyframes diagram-trace`, with standardized defs ids
(`diagram-grid` / `diagram-ground` / `diagram-core` / `diagram-glow` / `diagram-arrow*`).
Every page figure reuses these classes — the framework page-local duplicates were removed.

Per-figure before/after + contrast detail: `apps/website/verification/index.md`.
