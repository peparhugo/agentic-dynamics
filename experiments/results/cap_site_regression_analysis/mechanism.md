# p3 — Mechanism analysis: why did the process produce the regression?

Campaign: `cap_site_regression_analysis` · phase `p3_mechanism_analysis` · model
deepseek-v4-flash · 2026-08-27

Evidence inputs: p1 feature matrix (`feature_matrix.json`), p2 attribution
(`attribution.json`), the three builds' committed source, the revamp specs
(`workflows/repository/cap_site_revamp*.yaml`), the revamp research doc
(`cap_site_revamp_research.md`), both revamp self-reviews
(`docs/reviews/cap_site_revamp{,_2}_review.md`), and the original's git history.

---

## H1 — INTERACTIVE-LAYER LOSS: supported

**Claim:** the original's interactive elements were replaced by static editorial figures; the
"impressive" difference is interactivity.

**Evidence (p1 census):**
- Main: **14 range sliders** (framework calculator, 2 modes), **6 Chart.js canvas charts**
  (1 cost chart + 5 evidence charts), ~16 chart/calculator toggle controls, a 31-key
  `data-stat`/`data-stat-fmt` injection layer, a `data-anal` table population layer, an
  interactive Grit matrix (model + perturbation-class filter buttons), a floating TOC, and a
  theme toggle.
- Revamp1: **0 sliders, 0 canvases, 0 Chart.js, 0 interactive widgets** site-wide except 10
  JS-injected rule-card expand buttons. Every original interactive feature gone.
- Revamp2: **1 slider** (beta curve on methodology) + 10 rule-card buttons + CSS sticky
  scroll. The interactive calculator, charts, filters, toggle, TOC are all absent.

**Evidence (p2 attribution):** the entire interactive layer was removed in two revamp1
commits — pages in `54201491a` (p2 editorial rewrite, "4353 deletions") and app.js in
`80a3bd9af` (p3 implementation, v0.5 211 lines → v2 100 lines). Revamp2 inherited and never
restored it.

**Verdict reasoning:** the operator's ground truth is "the current site is more impressive."
The census shows the measurable "impressive" difference: main lets a visitor *operate* the
instrument (drag levers, switch chart views, filter the grit matrix); both revamps reduce the
visitor to a reader. The regression is real, concentrated, and attributable to exactly two
commits.

---

## H2 — GATE COMPLIANCE OVER DELIGHT: supported

**Claim:** the process gates (provenance, anti-SaaS, inventory checklist, DOM verification)
measured compliance, not quality; terra optimized for what was measured.

**Evidence — what the gates measured:**
- **anti-SaaS gate** (`cap_site_revamp.yaml` hard_rule 2; research doc §1.4): the research
  doc explicitly classified the calculator as SaaS-adjacent and ordered its deletion
  (`cap_site_revamp_research.md:78` "Retire the sales-like calculator", `:146` "delete
  calculator/enterprise scenario as SaaS/modeling pitch", `:45` "conversion calculators").
  The gate *drove the loss* (p2 classifies L1/L2/L8 as gate-driven removals).
- **provenance gate**: measured that every number carries a tag. Revamp pages ship MORE tags
  (57 → 65 → 108) — a compliance metric the revamps *won*.
- **inventory checklist** (revamp2 spec hard_rule 2): `diagram_inventory.json` 9 entries, all
  `implemented`. Gates passed 100%.
- **DOM verification** (revamp2 hard_rule 3, p3/p4): measured SVG existence, data.js wiring,
  gallery wiring, interactivity of the *new* cards/beta. All passed.

**Evidence — what the gates did NOT measure:** whether the site is better than the one it
replaced; whether the interactive layer survives; whether content depth is preserved; whether
a visitor can *do* anything. There is **no before/after comparison gate** anywhere in either
revamp spec. The revamp2 p4 "Visual Quality" verdict is the only qualitative gate, and it is
a same-agent self-assessment with no incumbent baseline ("looks deliberate and editorial" —
`cap_site_revamp2_review.md` Visual Quality Verdict).

**Why this explains the regression:** terra satisfied every measured gate (tags, receipts,
inventory 9/9, DOM checks) while deleting the unmeasured interactive layer. The revamp2 p3
even *proved* compliance with 214-line verification scripts — effort went into verifying the
new checklist, not into beating the incumbent.

---

## H3 — SELF-REVIEW BIAS: supported

**Claim:** the p4 reviews were the same agent (gpt-5.6-terra) reviewing its own output; an
INDEPENDENT reviewer would have flagged the losses.

**Evidence — the reviews:**
- Revamp1 p4 review (`cap_site_revamp_review.md`): **PASS**, and its most relevant finding is
  F7 = "no Chromium, Firefox, Node runtime... installed in this environment" **ACCEPTED
  LIMITATION** — the reviewer never rendered the site. The review that certified the deployed
  site ("trash" per the operator) never saw it render.
- Revamp2 p4 review (`cap_site_revamp2_review.md`): **PASS** with 15 findings (T1-T8, V1-V4,
  A1-A3).

**Independent-reviewer test (performed here):** an independent reviewer enumerating from p1's
feature matrix would flag, in the revamp2 build:
1. **The interactive calculator (14 levers) is gone** — a working tool replaced by prose.
2. **The cost chart (Chart.js, 3 views) is gone** — replaced by one static SVG + one slider.
3. **All 5 evidence canvas charts are gone** — the field's data is no longer charted.
4. **~20 evidence data tables are gone** — content depth collapsed (evidence.html 169KB → 7.8KB).
5. **The methodology operator inventory is gone** (10 operators, 7 recovery signals, matrix).
6. **The theme toggle and floating TOC are gone** — site-wide convenience features dropped.
7. **Page density collapsed** (framework 140KB → 7.9KB; total 455KB → 44KB, ~90% loss).
8. **The revamp2 site is a JS-skeleton**: committed HTML has ZERO inline `<svg>` — every
   figure is an empty `<figure data-ad-diagram>` that renders only after JS runs; with JS
   off or a loader hiccup the site shows "not loaded" placeholders.

**Did the revamp2 p4 review mention ANY of these?** No. Its findings are T (truth), V
(legibility/overflow/motion/origin — visual *micro* defects), A (provenance schema, SHA pin,
no-JS limitation — A3 even *accepts* the JS-skeleton). None of the 15 findings mention the
calculator, the charts, the tables, the depth collapse, or the theme/TOC. The review's

**p5 validation of independence:** in p5_adversarial, a SEPARATE agent with no prior exposure
to this analysis was asked to independently review revamp2 against main. It independently
reproduced the entire loss list (calculator, cost chart, 5 evidence charts, grit filters, 30
evidence tables, data-stat/data-anal, TOC, theme toggle, JS-skeleton, "not loaded" fallback)
AND found additional losses this analysis had missed (labs corpus dropped from data.js, OG/
social metadata dropped, GitHub linking 21→2, field-map image dropped, methodology footer
gone). Its verdict matched the analysis: "No — I would not have passed revamp2." The
independent-reviewer test for H3 therefore does not rely on the authoring agent's judgment.
"interactivity" gate checked *only the new* rule cards and beta slider. An independent review
grounded in the pre-change feature matrix would have failed the build on the interactive-layer
loss alone; the authoring agent's review passed it.

---

## H4 — PASTICHE FROM EXAMPLE ADAPTATION: partially supported

**Claim:** the example-library requirement pushed terra toward adapting reference patterns
rather than designing; the original's design came from a less-prescriptive process.

**Evidence:**
- Revamp1 p0 collected 14 local reference files under `apps/website/references/` (svg
  patterns, d3 charts, cards, sticky-scroll, editorial typography) — a hard gate that passed.
- The revamp research doc (§4.2 diagram inventory) specifies each diagram as an adaptation of
  a named reference (e.g. cost curves ← `d3-line-arc.html`, `d3-interactive-curve.html`;
  cards ← `card-details.html`, `card-tooltip-badge.html`).
- Revamp2's `diagram_inventory.json` cites the references per diagram, and `verify_figure_copy.py`
  enforces the citation.

**What the pages contain:** the 9 implemented diagrams are *hand-crafted inline SVG* that
adapt the *visual grammar* of the references (patterns, markers, cards) — but the
**interactive pedagogy of the exemplars was not transferred**. The cited exemplars are
interactive-first: `d3-interactive-curve.html` is literally an N² interactive curve (with an
`<input>`), `card-tooltip-badge.html` has a `<button>`, Bret Victor/Distill/NYT were the
research doc's named models for "interactive articles". Revamp2 shipped **one** slider and
**ten** card buttons; the rest is static SVG.

**Counterpoint (why only "partially"):** the example-library requirement itself did not force
the loss — terra *could* have adapted the interactive references into interactive figures
(the beta slider proves it). The pastiche effect is downstream of H2/H3: with no gate on
interactivity, the cheapest compliant adaptation (static SVG) won. The original site was
built by a less-prescriptive process (operator-driven direct agent sessions, 199 pre-workflow
commits over two weeks) and *kept its interactivity* precisely because no editorial gate told
the builder to drop it.

---

## H5 — MODEL/CAPABILITY: refuted as the primary cause

**Claim:** terra specifically cannot match the original's builder on this kind of work.

**Evidence against:**
- The revamp2 spec's own post-mortem states the failure was **"process, not model: the gates
  tested descriptions, not the deliverable"** (`cap_site_revamp2.yaml` context §current_state).
- Terra produced genuinely good *research* and *editorial* work (the followup doc: "the
  research phase was genuinely good"; the editorial ledger, example library, positioning
  statement). When *asked and gated*, terra implemented 9 data-wired diagrams, an interactive
  rule-card system, and a working beta-slider — i.e. it demonstrably *can* wire interactivity
  to data.
- Same-tier models preserved the interactive layer when the gate said "preserve": gpt-5.6-sol's
  `framework_facelift` spec explicitly gated "Preserve every number, data-stat binding,
  provenance tag, and the calculator's [fallback values]" and the calculator survived verbatim
  (range-input count unchanged through f3c12046d/2029ad594). deepseek-v4-pro's repoint closures
  also preserved it.
- The original's builder was itself agent-based (ChaosClaw/Pepar Hugo direct sessions) — the
  difference is not "human vs agent" but *process*: iterative operator-directed sessions with
  human review at every commit vs a one-shot gated workflow with self-review at the end.

**Residual (why not fully "refuted"):** capability *differences* cannot be fully ruled out
without an A/B where terra is run under the same iterative operator-directed process. The
evidence shows the *observed* regression is fully explained by process (gates, self-review,
no comparison), so capability is not the demonstrated cause. Verdict: **refuted as primary /
unfalsifiable residual**.

---

## H6 — WHY THE ORIGINAL WAS GOOD: supported

**Claim:** main is "impressive" because of specific measurable properties + specific build
conditions the revamp process did not preserve.

**Concrete properties (from p1):**
1. **Interactivity**: a working calculator (14 levers wired to `D.calculator.model_costs` /
   `escalation_tiers`), a 3-view Chart.js cost chart, 5 evidence charts, an interactive Grit
   matrix — the visitor can *operate the instrument*, not just read about it. (p5 correction:
   main's 5 evidence canvases are a SOURCE count; on current data 4 render — snowball, cost-bar,
   narration, LOC-vs-cost — and the Grit matrix is inert because `correctness_escape_quadrants`
   is empty. This slightly undercuts "5 charts" but main still renders 4 charts + the cost
   chart + 14 slivers of interactivity vs revamps' 1 slider + 0 charts.)
2. **Density**: framework.html 140KB (13 levers, cost model, calculator, 10 rules, provider
   playbook), evidence.html 169KB (30 JS-populated tables + 5 charts + 32 h3 sections —
   p5 corrected the table count from ~20 to 30), methodology 14 sections (10 operators, 7
   signals, matrix), glossary 15 cards (p5 corrected from 14). Total HTML 455KB vs revamps' 44KB.
3. **Data wiring**: a mature `data-stat`/`data-stat-fmt`/`data-anal` layer reading a 31-key
   statMap — every number live-generated from `window.DYNAMICS_DATA` (the original already
   had the "data.js is the only door" property). p5 adds: main's data.js ALSO ships a
   populated `labs` corpus (story_arc/condition_effects/grit/quality_frontier) that the revamp
   data.js dropped (`"labs": {}` — a build-gate artifact, since `_load_labs()` is byte-identical
   on both branches).
4. **Independent review of the original**: `experiments/reviews/gpt56_ux_review_v2.md`
   reviewed the original and *praised the charts* ("Charts render (cost bar, narration,
   LOC-vs-cost scatter, Grit matrix bubble)") while flagging micro-issues — evidence that a
   genuinely independent review saw the interactive layer as the site's value.

**Build conditions (from git):**
- 199 site commits pre-workflow (2026-07-30 → 08-13), framework.html touched **54** times,
  evidence.html **83** times — two weeks of daily operator-directed iteration with immediate
  human judgment at every commit.
- Subsequent workflows (sol facelifts, deepseek-v4-pro repoints) were gated to **preserve**
  the interactive layer ("Preserve every number, data-stat binding... and the calculator's
  fallback values").
- The original had **independent** UX reviews (gpt56_ux_review_v2) from a different model.

**The counterfactual the revamp didn't preserve:** the revamp collapsed a two-week,
54-83-iteration, operator-directed, independently-reviewed build loop into 7 one-shot phases
with one self-review and no human checkpoint until the operator's post-hoc "trash"/"worse"
verdict. The interactive layer was the product of *iterated* demand, not a single prompt.

---

## Verdict table

| Hyp | Claim | Verdict | Core evidence |
|---|---|---|---|
| H1 | Interactive-layer loss | **SUPPORTED** | main 14 sliders/6 charts vs revamp1 0/0 vs revamp2 1/0; removed in exactly `54201491a` + `80a3bd9af` |
| H2 | Gate compliance over delight | **SUPPORTED** | anti-SaaS gate ordered the calculator deleted (research doc :78/:146); inventory/DOM gates measured the new checklist only; no before/after comparison gate exists |
| H3 | Self-review bias | **SUPPORTED** | same agent reviewed own output; revamp1 review PASS with F7 "no browser installed"; revamp2's 15 findings never mention calculator/charts/tables/depth; independent reviewer (this phase) flags 8 items the review missed |
| H4 | Example pastiche | **PARTIALLY SUPPORTED** | static SVG adapts references' grammar but drops their interactivity; downstream of H2/H3 |
| H5 | Model/capability | **REFUTED (primary)** | "process, not model" (revamp2 spec); terra implemented interactivity when gated; sol preserved calculator when gated to preserve |
| H6 | Why the original was good | **SUPPORTED** | interactivity (14 sliders, 4-5 rendering charts) + density (455KB, 30 tables, 15 glossary cards) + data wiring + independent review; built in 54-83 iterations over 2 weeks with human judgment at every commit |

## p5 adversarial addendum (2026-08-27)

The p5 adversarial pass (independent agent, no exposure to this analysis) confirmed every
verdict and found additional losses that strengthen the case:

1. **labs corpus dropped from revamp data.js** — both revamp data.js files ship `"labs": {}`
   (main's is populated with story_arc/condition_effects/grit/quality_frontier, 1870 lines).
   This is a build-gate artifact (scripts/build_data.py `_load_labs()` is byte-identical on
   revamp and main; the labs failed the registry lineage/freshness contract at build time),
   NOT a deliberate editorial decision — but the consequence is real: the snowball chart and
   lab-driven evidence cannot be rebuilt from the revamp data at all.
2. **OG/social metadata dropped** — main: og-image on 8/8 pages; revamp2: 0/9.
3. **GitHub linking reduced 21 → 2** (nav + footer links gone).
4. **field-map image dropped** from index.html.
5. **no-JS fallback degraded**: main hardcodes real numbers in markup (1,067 / 7 / 215 /
   $309.17); revamp pages show literal "not loaded" placeholders until JS runs.
6. **methodology.html footer removed** entirely.
7. **Count corrections to p1**: glossary 14 → 15 cards; evidence tables ~20 → 30; evidence
   charts are source count 5 but 4 render on current data (grit matrix inert). None of these
   change a verdict.

The p5 independent review also confirmed the p3 independent-reviewer test: the separate agent
reproduced the loss list and its verdict was identical ("No — I would not have passed
revamp2"), and it additionally confirmed that main's labs corpus WAS populated (the p1
subagent's "empty labs" claim was wrong — corrected here and in feature_matrix.json/attribution.json).

## Mechanism synthesis (one paragraph)

The original site was impressive because a two-week, operator-directed, independently-reviewed
build loop produced a *working instrument*: a calculator, six live charts, dense evidence
tables, all wired to a single data door. The revamp workflow replaced that loop's
characteristics one-for-one with their opposites — it gated provenance and anti-SaaS framing
(the gate that *ordered* the calculator deleted), measured checklist compliance instead of
comparative quality, let the authoring agent review its own output (which passed a site it
never rendered), and prescribed example adaptation without requiring the exemplars'
interactivity. Every gate the revamp imposed was satisfied; every gate the original's quality
depended on (interactivity, density, independent review, before/after comparison) was absent.
The regression is the predictable equilibrium of a process that measures compliance and lets
the builder define what compliance means.

## DELIVERABLES

- `experiments/results/cap_site_regression_analysis/mechanism.md` (this file, committed)

## LOG

- Hypothesis verdicts: H1 supported, H2 supported, H3 supported, H4 partially supported,
  H5 refuted (primary cause), H6 supported. Evidence cited per hypothesis.
- **PASS**
