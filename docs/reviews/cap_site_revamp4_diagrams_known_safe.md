---
status: accepted
---
# Known-safe — cap_site_revamp4_diagrams (p5_adversarial)

What the adversarial verification ATTACKED and could NOT falsify. Each item below was
probed with evidence and stands verified as of the final deployed build
(`feature/site-revamp4-diagrams`, deployed to both hosts 2026-08-27).

## Rendering (the p1 repair holds, deployed)

- **No collapsed figures.** All 22 diagram SVGs across all 9 pages render ≥ 100px on
  both axes at 1440x900 and 390x844 — including the formerly-collapsed OPERATING MODEL /
  SHARED EXECUTION figure (now `diagram-map workflow-map`, 1034x546 / 900x475) and the
  pre-fix `architecture-map` (was 0x0; the class no longer exists — replaced by the
  diagram-map grammar). Verified against the DEPLOYED canonical URL.
- **Aspect-correct.** Every rendered box matches its viewBox within 8% tolerance at both
  viewports (the p1 `width:100%;height:auto` sizing holds).
- **No overflow.** No figure breaks out of the document scroll area (the 390px figures
  live in the horizontal `diagram-scroll` well without inflating the page).
- **Visible on first paint.** PAINT check (client rects, opaque, non-zero box) passes
  for every figure; console is clean on every page.
- **Text paints.** Pixel-level glyph verification: every `<text>` in every figure paints
  pixels of its fill color (confirmed for the four box-quirk suspects via region color
  histograms).

## Contrast (WCAG AA, the p3b gate, both themes)

- **Dark theme (default):** every text fill vs its computed background ≥ 4.5:1; deployed
  minimum 8.37:1 across all figures (gradient/pattern fills resolved, stroke halos
  count as the background, alpha composited).
- **Dark-theme surfaces (the "black boxes" review, commit `2fff4ca83`):** the diagram
  surfaces (`.mode-surface`, `.rail`, `.human-surface`, `.mode-tab`,
  `.outcome-surface`, `.workflow-node`, `.plane-surface`) now use `--bg3` with
  0.5-alpha borders in dark mode, so the figure boxes are legible against the page
  (previously `--bg2` on `--bg` was a ~1.05:1 boundary). Verified: rendering gate
  22/22 and contrast AA PASS in both themes after the fix.
- **Light theme (the p5 finding's fix):** after `body.light` accent-text overrides
  (commit `958f99915`), the real gate's contrast logic passes in light mode on both
  deployed hosts — the previously-failing `.map-kicker`, `.scale-symbol`, and `--fw-*`
  node-index labels are now AA-passing dark shades.
- The 3%-alpha amber panel in the envelope figure (svg#4) is correctly alpha-blended to
  near-white by the gate; its inline `fill:var(--am)` kickers pass in both themes.

## Craft (the p2/p3b claims, verified in the DOM)

- **Text/shape balance:** every figure's text length ≤ 1.5× its shape markup; worst
  ratio 0.39 (framework svg#4). No figure is a text wall or an empty shell.
- **One legible message per figure:** execution-engine ("one workflow engine operating as
  a single cell or an experimental grid"), eight-planes ("eight planes, one dependency
  direction" — 01→09 chain, CONTROL glowing, APPS amber), instrument cycle
  (instrument → derive → ✕ write policy → grid → campaign ring), one-engine-two-modes
  (operate 1 cell / experiment G cells → one engine → record vs compare+adapt). The four
  p3b re-crafts reuse the approved workflow-map grammar (classes/structure/color/type).
- **Five-second legibility:** the operator's own figure-by-figure review is the gate; the
  p3b re-craft answered the REJECT and was APPROVED (2026-08-27).
- **Example-library adaptation now cited:** the restored `apps/website/references/`
  (MDN-CC0 samples) are cited at the grammar source (base.css `.diagram-map` block +
  `framework.html` field-layer comment).

## Collapse regression (attack 3)

- The p1 CSS fixes hold across **theme toggle** (dark + light), **reduced-motion**
  (`prefers-reduced-motion`), and the **390px narrow viewport**: 0 collapsed figures,
  0 text boxes lost, 0 occluded texts in every combination, on the deployed pages.
- The pre-fix build failed this probe; the repaired build passes everywhere.

## The operator approval

- Genuine and non-placeholder: `[x] APPROVE`, operator `peparhugo`, dated 2026-08-27,
  committed as `7bd1528e1` **after** the p3b checkpoint `b81413c7b`. The p4 first run
  correctly FAILED before the approval existed (recorded in the deploy-gate doc) and the
  deploy ran only after the signed approval.

## Deploy integrity

- Both hosts deployed from the same `apps/website/`: `ai-finops-rulebook` (canonical)
  and `agentic-dynamics` (mirror) — `✔ Deploy complete` on both.
- All 9 pages are **sha256-identical** across the two hosts (no drift).
- Deployed-URL gates pass on both hosts: 22/22 rendering, dark+light contrast AA.
- The deployed build carries the approved data.js (`generated 2026-08-27T19:16:59Z`).

## The instrument

- Census gate (`scripts/site_census_check.py`) PASS on all 12 headline axes vs the
  incumbent baseline (sliders 15≥14, canvas 6≥6, tables 38≥38, handler sites 50≥50,
  theme toggle 1≥1, data-stat/anal keys preserved).
- No instrument source (`src/agentic_dynamics/`, experiment configs, measurement
  scripts) was touched by any campaign commit — only `apps/website/`, `docs/reviews/`,
  and the data-chain outputs.

## Environment note (not a site defect)

- The headless verification sandbox initially had no fonts, making SVG text boxes
  report 0x0 (environment artifact). Pixel-painted glyphs confirm real visibility;
  with DejaVu fonts installed, all layout probes pass. This does not affect the site's
  gate (which is box-independent) or any real-browser rendering.
