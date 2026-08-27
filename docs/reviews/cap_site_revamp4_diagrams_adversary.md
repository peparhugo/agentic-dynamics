# Adversary — cap_site_revamp4_diagrams (p5_adversarial)

**Verdict: PASS.** The adversarial verifier attacked the repair in the spec's order;
two genuine findings were surfaced and FIXED (light-theme WCAG AA contrast;
example-library citations). The instrument census holds; the deploy gate was verified
on the DEPLOYED pages; the operator approval is genuine.

**Role:** adversarial verifier — try to falsify the repair. Attack order:
(1) rendering evasion, (2) craft claim, (3) collapse regression, (4) approval
genuineness, (5) deployed-pages gate, (6) instrument untouched.

---

## Attack (1) — Rendering evasion (a figure that passes the gate but is invisible)

Probe surface: all 22 diagram SVGs on all 9 pages of the DEPLOYED canonical host
(`https://ai-finops-rulebook.web.app`), 1440x900, plus pixel-level verification of
every `<text>`.

| Check | Result | Evidence |
|---|---|---|
| White-on-white / same-fill-as-background | **PASS** — impossible undetected: the gate's CONTRAST check (WCAG AA, every text fill vs computed background, alpha-composited, gradients/patterns/stroke-halos resolved) fails any fill≈background (ratio 1:1 < 4.5:1). Deployed min contrast 8.37:1 (dark), every figure | `verify_svg_rendering.py` CONTRAST; deployed gate report |
| Zero / near-zero opacity | **PASS** — chain-opacity walk of every text and shape (computed opacity × fillOpacity × ancestor chain): no element < 0.9, no empty shells (sized shape with fill `none` AND stroke `none`) | custom playwright probe, 0 findings |
| Off-canvas / outside viewBox | **PASS** — per-text screen-CTM→viewBox inversion: no text center outside its viewBox; no negative-left svg; overflow checks (doc scroll area, scroll-context-aware) pass | gate OVERFLOW/OFFSCREEN + probe |
| Behind another element (occlusion) | **PASS** — scroll-into-view + `elementFromPoint` hit-test at every text's center: no text occluded by a later-painted element | probe, 0 occluded |
| Painted glyphs (the decisive evasion test) | **PASS** — pixel analysis of element screenshots: every text box region contains glyph pixels of its fill color (antialiased blends, confirmed by region color histograms, e.g. `01 / BASELINE CELL` shows bg `[16,23,34]` + antialiased glyph shades) | pixel probe; 4 suspicious boxes re-checked → all painted (getBoundingClientRect offset is a headless-shell box quirk, see Accepted limitation L1) |
| First-paint / laid out | **PASS** — PAINT check (client rects, non-zero box) + CONSOLE clean on every page | gate PAINT/CONSOLE |

**No rendering evasion found.**

### Accepted limitation L1 — the headless verification environment has no fonts
This sandbox's Chromium had **zero installed fonts** (`fc-list` = 0), so SVG text
`getBoundingClientRect()`/`getBBox()` returned 0x0 for ALL text (control test:
a bare `<text>` in an empty page returned 0x0). This is an environment artifact, not a
site defect. Resolution: (a) a pixel-level glyph-paint check proved the text is painted;
(b) after installing DejaVu core fonts, all text lays out with real boxes and every
probe (occlusion, collapse, no-box) passes. The gate's own checks do not depend on text
boxes (they use computed styles + viewBox geometry), which is why the committed gate
passed in the font-less environment while remaining sound.

---

## Attack (2) — The craft claim (a text wall swapped for an empty visual)

| Check | Result | Evidence |
|---|---|---|
| Text/shape balance holds | **PASS** — gate BALANCE: per figure, text length ≤ 1.5× shape markup length. Worst figure `framework svg#4` (envelope): 510 text vs 1301 shape chars (ratio 0.39); every figure's shape markup exceeds its text | deployed gate report columns text / shape markup |
| No empty shell (shapes with no labels) | **PASS** — every figure carries its title/kicker (`.map-kicker`, `.map-title`) and labelled node cards (`.node-index`, `.node-title`, `.node-copy`); the pixel probe confirmed the labels paint | markup + pixel probe |
| One legible idea per figure | **PASS** — the four p3b re-crafted figures each carry one message in the approved execution-engine grammar: `workflow-map` = "one workflow engine operating as a single cell or an experimental grid"; `svg#1` (planes) = "eight planes, one dependency direction" (numbered 01→09 chain, control glowing, apps amber); `svg#2` (cycle) = instrument→derive→policy→grid→campaign ring with the red ✕ gate on derive→policy; `svg#3` (two modes) = converge→one engine→diverge (operate 1 cell / experiment G cells feeding one engine pill). Titles are human-verifiable in the deployed DOM (`<title>` + visible kicker/title) | deployed framework.html |
| Five-second legibility | **PASS (operator-gated)** — the operator's own figure-by-figure review is the gate; REJECT (2026-08-27) was answered by the p3b re-craft in the approved figure's exact grammar, and the operator subsequently APPROVED | `verification/APPROVAL.md` + `7bd1528e1` |
| Contrast (the p3b gate) | **PASS (dark)** — min 8.37:1, every text fill; **FIXED for light** (finding F1 below) | gate CONTRAST |

### Finding F1 (FIXED) — light-theme diagram accent text was below WCAG AA
The contrast gate validates the **default dark theme** (its docstring says so: "the site's
default dark theme is the review surface"). Under the **light** theme toggle (`body.light`),
the accent text fills are mid-tones on light surfaces and fail AA:

| Class | Light fill | bg | ratio | figures |
|---|---|---|---|---|
| `.map-kicker` | `--ac` #0891B2 | white / `--bg2` / cyan panel | 3.52–3.68:1 | all 8 figures' titles |
| `.scale-symbol` | `--ac` #0891B2 | `--bg2` | 3.30:1 | framework svg#0/1, question |
| `.node-index` inline `--fw-what` / `--fw-how` | #0284C7 / #0891B2 | `--bg2` | 3.52–3.91:1 | framework svg#5 (autonomy map) |

**Fix (committed `958f99915`):** `body.light` overrides pin the diagram TEXT accents to
AA-passing dark shades — `.map-kicker`/`.scale-symbol` → #155E75 (cyan-800, ≥ 7:1 on
white, ~5:1 on the cyan panel), and `body.light.framework-page` re-pins
`--fw-why` #92400E / `--fw-how` #155E75 / `--fw-what` #0E7490. Dark theme untouched
(default var fills). **After the fix, the real gate's contrast logic passes in BOTH
themes on both hosts** (min 4.5+; re-run against the deployed URLs).

### Finding F2 (FIXED) — the example-library citations were absent
Hard rule 3 required the figures to "genuinely adapt (cited in the source)" the
example library (`apps/website/references/`). The reference files existed only on the
unmerged revamp editorial-audit commit `47f639201`; the shipped figures cited "the
reused example library" without naming files, and the directory was absent.

**Fix (committed in the p5 commit):** restored the 14 MDN-CC0 reference samples
(`apps/website/references/*.html`, attribution headers preserved) and cited the adapted
files at the grammar source — `base.css` `.diagram-map` block (`svg-marker-flow.html`
marker flows, `svg-filter-focus.html` glow, `svg-pattern-surface.html` grid,
`svg-animated-status.html` reduced-motion tracer, `d3-labeled-scatter.html` node cards)
and the `framework.html` field-layer comment. `references/` now resolves on the deployed
site (200) and the citations are greppable.

---

## Attack (3) — Collapse regression (the p1 CSS fixes hold across toggles)

Probe: every diagram SVG on all 9 pages × {dark, light} × {1440, 390} × {motion,
reduced-motion} against the deployed canonical host, checking for collapsed figures
(≤100px), text with 0x0 boxes, and occlusion.

| Surface | Collapsed | No-box text | Occluded | Result |
|---|---|---|---|---|
| dark @ 1440x900 | 0 | 0 | 0 | PASS |
| dark @ 390x844 | 0 | 0 | 0 | PASS |
| light @ 1440x900 | 0 | 0 | 0 | PASS |
| light @ 390x844 | 0 | 0 | 0 | PASS |
| reduced-motion @ 390x844 | 0 | 0 | 0 | PASS |

The pre-fix deployed build fails this probe (framework svg#1 `architecture-map`
rendered **0x0**, SIZE + PAINT fail); the repaired build passes everywhere. The 390px
figures keep aspect (svg min-width 900px inside the horizontal `diagram-scroll` well;
the gate's scroll-context-aware overflow check confirms no page-level overflow).

---

## Attack (4) — The operator approval is genuine

| Check | Evidence | Result |
|---|---|---|
| Non-placeholder signature | `[x] APPROVE`, operator name `peparhugo`, role `Operator`, date `2026-08-27`, signature token `peparhugo` — no blank placeholders remain | PASS |
| Committed after the checkpoint | approval commit `7bd1528e1` is the HEAD child of the p4-fail commit `9b982306f`, which sits on the p3b checkpoint `b81413c7b` (REJECT is on record in the same artifact) | PASS |
| Deploy only after approval | p4's FIRST run at `b81413c7b` FAILED the approval-absent condition (deploy gate doc); the deploy ran only after `7bd1528e1` | PASS |
| Approval is the visual artifact, not the p2 design approval | the p3b `verification/APPROVAL.md` (visual) is distinct from `approvals/cap_site_revamp4/p2_design_with_human_checkpoint_approval.md` (design) | PASS |

---

## Attack (5) — The deploy gate ran on the DEPLOYED pages

All post-deploy gates ran against the **live URLs**, not the local build:

| Gate | ai-finops-rulebook.web.app (canonical) | agentic-dynamics.web.app (mirror) |
|---|---|---|
| Rendering (22 SVGs, 2 viewports) | **PASS** 22/22 | **PASS** 22/22 |
| Contrast AA — dark + light (real gate logic) | **PASS** | **PASS** |
| Collapse regression probe (dark/light/reduced × 390/1440) | **PASS** | — (mirror is byte-identical, below) |
| Mirror identity (9 pages sha256) | — | **IDENTICAL** on all 9 pages |
| Deployed content | framework.html serves the 6-diagram approved set (no `architecture-map`); `data.js` generated 2026-08-27T19:16:59Z | same |

Before/after on the live URL: pre-deploy `ai-finops-rulebook.web.app/framework.html`
FAILED the gate (svg#1 `architecture-map` 0x0); post-deploy it passes 22/22. The `deploy
gate` doc records the p4 FAIL (approval absent) then the PASS (approval + deploy +
deployed gate).

---

## Attack (6) — The instrument untouched

| Check | Result |
|---|---|
| Census gate (`scripts/site_census_check.py` vs the incumbent baseline) | **PASS** on all 12 headline axes — sliders 15≥14, canvas 6≥6, chart sites 7≥6, tables 38≥38, handler sites 50≥50, theme toggle 1≥1, data-stat 72≥64 (unique keys 22=22), data-stat-fmt 3=3 (supported 33=33), data-anal 84=84 (unique 12=12) |
| Files touched by the campaign's commits | only `apps/website/` (html/css/js/py + verification/ + references/), `docs/reviews/`, and the data-chain outputs (`experiments/data/`, `experiments/inventory.json`) — no `src/agentic_dynamics/`, no `scripts/` instrument logic, no experiment configs |
| Live census surfaces | the field-layer additions are additive; every incumbent feature count is ≥ baseline (no removal) |

---

## Finding disposition

| # | Finding | Severity | Disposition |
|---|---|---|---|
| F1 | Light-theme diagram accent text below WCAG AA (map-kicker/scale-symbol/--fw-*: 3.3–3.9:1) | Medium (AA is mandatory per the campaign gate) | **FIXED** — `body.light` accent-text overrides; committed `958f99915`; real-gate contrast now PASS in both themes on both hosts |
| F2 | Example-library references not cited in source + directory absent | Low (hard rule 3) | **FIXED** — 14 reference files restored from the revamp audit commit `47f639201` + citations added at the grammar source (base.css + framework.html); deployed `references/` returns 200 |
| L1 | Headless environment font-less (SVG text boxes 0x0) | — (environment) | **ACCEPTED LIMITATION** — pixel-painted glyphs prove visibility; DejaVu install makes all probes lay out; the gate's checks are box-independent |

## LOG

- (1) rendering evasion: PASS (pixel-verified glyphs; no opacity/occlusion/off-canvas/white-on-white).
- (2) craft claim: PASS after F1/F2; text/shape balance holds on every figure; one message per figure.
- (3) collapse regression: PASS across theme toggle + reduced-motion + 390px (0 collapsed, 0 no-box, 0 occluded).
- (4) operator approval: PASS (genuine, committed after the checkpoint).
- (5) deploy gate: PASS on the DEPLOYED pages (both hosts, both themes, mirror identical).
- (6) instrument untouched: PASS (census all axes ≥ baseline).
- Phase verdict: **PASS** — two findings surfaced, both fixed; no bare PASS.
- Commits: `958f99915` (F1), p5 commit (F2), prior p4 `3f08b3be4` + `4db83…` (data chain + deploy-gate doc).
