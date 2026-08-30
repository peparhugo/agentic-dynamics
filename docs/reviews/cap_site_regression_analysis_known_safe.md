---
status: accepted
---
# CAP Site Regression Analysis — Known-Safe List

**Reviewer role:** adversarial verifier — attempted non-falsifying attacks.
**Date:** 2026-08-27. **Campaign:** cap_site_regression_analysis, phase p5.

Every attack below was attempted and did NOT falsify the analysis. Each entry records the
attack, the evidence, and why it is safe.

---

## K1 — "The revamps are a legitimate editorial direction, not a regression"

- **Attack:** the revamp's research doc *intended* the anti-SaaS field-establishment
  direction; the operator commissioned it, so the content collapse is the commission, not a
  failure.
- **Evidence against:** the operator's own ground truth is data ("the current site is more
  impressive. Terra was making it worse.") and the followup post-mortem calls revamp1
  "trash" and records the redeploy to main twice. The operator commissioned a field-framing
  *direction*, not a *loss of interactivity* — the research doc's own IA said "Model formulas
  may return as [C] explorable with explicit inputs" (i.e. the interactivity was supposed to
  survive in [C] form) and it degraded to exactly one slider.
- **Why safe:** the analysis distinguishes intended *editorial reframing* (accelerator →
  Open questions; question.html added; provenance added — all credited as additions) from
  *unintended loss* (calculator, charts, tables, OG metadata, GitHub links, labs corpus). The
  operator's verdict adjudicates the difference, and the analysis never argues with it.

## K2 — "The 'interactive layer' was overcounted — main's charts don't actually render"

- **Attack:** if main's data.js `labs` were empty and `correctness_escape_quadrants` empty,
  the snowball chart and Grit matrix would render nothing, making main's "6 charts" a fiction.
- **Evidence against:** main's data.js is **populated** — `labs` carries cache_economics,
  condition_effects, grit, quality_frontier, and story_arc with 215 sessions. The snowball
  chart, cost-bar, narration, and LOC-vs-cost charts all have live data. The Grit matrix is
  inert on current data (quadrants `[]`), and the analysis now records the render-state
  nuance (4 of 5 evidence charts render). Even at 4 charts + 14 sliders, main dwarfs
  revamp2's 1 slider + 0 charts.
- **Why safe:** the error was found, corrected, and the correction *strengthened* main.

## K3 — "Attribution is wrong: the calculator was removed by an earlier workflow, not terra"

- **Attack:** maybe a pre-revamp workflow (sol facelift or deepseek repoint) deleted the
  calculator.
- **Evidence against:** `git log -S 'input type="range"' -- apps/website/framework.html main`
  returns ONLY `ee2f35ec8` (move_apps) — the range inputs survived every main workflow.
  `framework_facelift`'s spec explicitly required preserving the calculator; the range-input
  count is unchanged through f3c12046d/2029ad594. The 14→0 transition happens only in
  `54201491a` on the revamp branch.
- **Why safe:** commit-level verification rules out earlier removal.

## K4 — "The revamp2 diagrams exist and are 'implemented' — so the visual system was delivered"

- **Attack:** revamp2's diagram_inventory.json lists 9/9 implemented and DOM verification
  passed; claiming "no visuals" is false.
- **Evidence against:** the analysis never claims revamp2 lacks diagrams — it credits the
  9 data-wired SVG diagrams as a genuine ADDITION (A5). The finding is that (a) they are
  JS-injected into empty committed placeholders (zero literal `<svg>` in committed HTML — a
  structural fragility, confirmed by the independent reviewer and by
  dom_verification_report.md's own "checked after the inline-SVG renderer executes"), and
  (b) they did not replace the *interactive layer* that was lost. Both are verified.
- **Why safe:** additions and losses are tracked separately; the JS-skeleton fragility is a
  measured structural property, not an opinion.

## K5 — "H5 (capability) is too easily refuted — maybe terra just can't"

- **Attack:** the "process not model" claim could hide a capability gap.
- **Evidence against:** terra demonstrably implements interactivity when asked: the beta
  slider (`bindCostCurveControl`), the 10 rule-card toggles, the data-wired diagrams. And a
  same-tier model (gpt-5.6-sol) preserved the calculator when its gate said "preserve". The
  residual (that terra under a fully-iterative operator-directed process might still lag) is
  explicitly recorded as an unfalsifiable residual, not claimed as measured.
- **Why safe:** the verdict is scoped to "not the demonstrated cause of THIS regression";
  the residual is acknowledged.

## K6 — "The recommendations are platitudes / unactionable"

- **Attack:** "preserve the interactive layer" and "review independently" are obvious.
- **Evidence against:** each recommendation is mechanical and was walked against the actual
  revamp2 process (A4): R1 = a machine-checkable feature-diff gate (the pattern
  diagram_inventory.json already proved in this repo); R2 = a `reviewer` field in run_shape
  (different model/session, no authoring-session access); R3 = a compare phase computing the
  p1 delta table; R5 = count `<input type=range>`, `<canvas>`, Chart instances pre/post (a
  five-line census). All fire.
- **Why safe:** they are testable artifacts, not aspirations.

## K7 — "The operator's judgment might just be aesthetic preference — not evidence"

- **Attack:** "more impressive" is taste, and the analysis elevated it to data.
- **Evidence against:** the campaign spec itself designates the operator's judgment as
  ground truth (hard_rule 3 "THE OPERATOR'S JUDGMENT IS DATA"); the analysis then explains
  that judgment with a measurable feature delta (14 vs 1 sliders, 6 vs 0 charts, 30 vs 0
  tables, 455 vs 44 KB), so it is not asserted, it is *explained*. The operator also acted on
  it (redeployed main twice) — revealed preference.
- **Why safe:** the judgment is the question's premise, used as data per the spec.

## K8 — "The analysis modified the site / violated 'analysis only'"

- **Attack:** did the campaign touch apps/website?
- **Evidence against:** the only commits in this campaign touch
  `experiments/results/cap_site_regression_analysis/` and
  `docs/experiments/results/cap_site_regression_analysis.md` + `docs/reviews/*`. No apps/website
  file is written; the revamp branches were read-only. git status of the campaign branch
  confirms analysis-only files.
- **Why safe:** verified by the commit list.

## K9 — "revamp2's data.js is actually complete — the labs were never 'supposed' to ship"

- **Attack:** maybe the labs corpus is not part of the site's contract, so dropping it is a
  non-issue.
- **Evidence against:** main's data.js ships a populated labs corpus and main's evidence.html
  renders lab-driven figures (snowball chart, arc tables, grit tables) from it. The revamp's
  own hard rule says "data.js stays THE data door — a new finding updates data.js" — the
  labs payload is part of that door. The drop is classified as accidental (build-gate
  artifact, `_load_labs()` byte-identical), which is the honest framing.
- **Why safe:** the classification distinguishes intent (none) from consequence (loss).

## K10 — "The independent reviewer just echoed the author because it was given the same framing"

- **Attack:** the p5 subagent prompt could have leaked the analysis's conclusions.
- **Evidence against:** the subagent was given ONLY the three file trees and a generic task
  ("independently audit the revamp2 build; list what you'd flag; be skeptical; verify each
  claim; note additions too"). It was not given the feature matrix, the attribution, the
  mechanism document, or any loss list. It produced its own counts (30 tables, 15 glossary
  cards, 0 literal SVG, "not loaded" placeholders — all independently measured) and its own
  additions list (question.html, campaign receipts, provenance, a11y). Its only
  "leak" was the operator's ground-truth statement, which is the question itself.
- **Why safe:** the reviewer's measurements were independently reproduced and it found things
  the author missed, which is the opposite of echoing.

---

## Summary

Ten non-falsifying attacks were attempted. Every one either (a) required a count correction
that, when applied, favored main and strengthened the conclusion, or (b) was already covered
by the analysis's honest framing (additions credited, residual limitations recorded, the
operator's judgment treated as data). The adversarial pass failed to falsify the regression
analysis; the four genuine errors found were all corrected in
`feature_matrix.json` / `attribution.json` / `mechanism.md`.
