# CAP Site Regression Analysis — Adversarial Verification

**Reviewer role:** adversarial verifier — try to falsify the analysis.
**Date:** 2026-08-27. **Campaign:** cap_site_regression_analysis, phase p5.

The attacks targeted all six specified surfaces. Every finding below was either FIXED in the
analysis artifacts or recorded as an accepted limitation with reasoning. A non-falsifying
attack with its evidence is in `cap_site_regression_analysis_known_safe.md`.

---

## Attack 1 — Feature matrix completeness and fairness

### A1-1 FIXED: evidence table count understated (evidence.html ~20 → 30)
- **Attack:** the matrix claimed "~20 JS-populated tables" on main evidence.html; the actual
  committed HTML has **30 `<table>` elements**. Under-counting main's density made main look
  less dense than it is — an unfair-to-main error.
- **Result:** confirmed. `grep -c '<table' evidence.html` = 30.
- **Fix:** `feature_matrix.json` evidence main row updated to "30 JS-populated tables";
  `mechanism.md` H6 corrected; `attribution.json` L5 scope updated.
- **Re-test:** PASS — 30 tables now cited in all three artifacts.

### A1-2 FIXED: glossary card count (14 → 15)
- **Attack:** matrix said 14 glossary cards; committed HTML has **15 `.gcard`**.
- **Result:** confirmed (`grep -c 'class="gcard"' glossary.html` = 15).
- **Fix:** `feature_matrix.json` glossary main row updated to 15; mechanism H6 corrected.
- **Re-test:** PASS.

### A1-3 FIXED (analysis strengthened): main's `labs` corpus is populated, not empty
- **Attack:** a p1 subagent claimed main's data.js had `"labs": {}` empty and that the
  snowball chart does not render. If true, main's evidence interactivity was overstated.
- **Result:** REFUTED — main's data.js (6695 lines) has a **populated** labs corpus
  (cache_economics, condition_effects, grit, quality_frontier, story_arc with 215 sessions),
  so the snowball chart DOES render. The p1 subagent was wrong. This finding goes the
  *other* way: main is more interactive than the matrix claimed.
- **Fix:** corrected the internal record (the committed feature_matrix had not asserted the
  empty-labs claim, so no committed text changed on this point); noted the render-state
  nuance (4 of 5 evidence charts render on current data; the Grit matrix is inert because
  `correctness_escape_quadrants` is `[]`).
- **Re-test:** PASS — data.js verified populated; snowball render path verified
  (`D.labs.story_arc.sessions` non-empty).

### A1-4 FIXED (new losses): the revamp data.js DROPPED the entire labs corpus
- **Attack:** an independent reviewer found revamp1 AND revamp2 data.js both end with
  `"labs": {}` while main's is populated.
- **Result:** CONFIRMED (revamp1 data.js 4825 lines, `"labs": {}`). This is a real loss the
  matrix had not listed.
- **Classification check:** was it editorial or a build artifact? `_load_labs()` in
  scripts/build_data.py is **byte-identical** on revamp and main (`diff` empty) — the drop is
  a build-time registry lineage/freshness gate rejection, NOT a deliberate deletion. Recorded
  as **accidental drop (b)**.
- **Fix:** added as a loss entry in `attribution.json`; mechanism H6/p5 addendum updated.
- **Re-test:** PASS.

### A1-5 FIXED (new losses): OG/social metadata, GitHub linking, field-map image, no-JS fallback, methodology footer
- **Attack:** the independent reviewer enumerated five more real losses the matrix missed:
  og-image referenced on 0/9 revamp2 pages (main 8/8); GitHub links 21 → 2; field-map PNG
  never referenced; revamp pages show literal "not loaded" placeholders (main hardcodes real
  numbers); methodology footer removed.
- **Result:** all five CONFIRMED by grep/byte checks.
- **Fix:** added all five as loss entries in `attribution.json` (L15–L19).
- **Re-test:** PASS — each cited with file evidence.

**Fairness verdict:** the matrix under-counted main (tables, glossary, populated labs) and
over-counted nothing on the revamp side. Every count error favored the revamp; the revamp
side had additional real losses (labs corpus, OG, GitHub, field-map, no-JS) the matrix had
missed. The conclusion (main more impressive) is not only intact but strengthened. No
falsification.

---

## Attack 2 — Attribution cites the right commits/phases

### A2-1 PASS: pages removal at `54201491a`
- **Attack:** could the calculator/charts have been removed earlier (e.g. in the base commit
  or p1)?
- **Result:** verified `git show 54201491a^:framework.html` has 19 range/canvas/Chart
  matches → after 0; evidence.html 10 canvas/Chart matches → 0. p1 (`564641ffc`) touched only
  _design.html + design-components.js + base.css. Attribution stands.

### A2-2 PASS: app.js rewrite at `80a3bd9af`
- **Attack:** was app.js rewritten in p2 with the pages instead?
- **Result:** at `54201491a` (p2) app.js is still v0.5 (renderDiagrams count 0 — the pages
  referenced data-ad slots before app.js knew them); `80a3bd9af` (p3) rewrites app.js
  (211 → 100 lines, 307 diff lines). Attribution stands.

### A2-3 PASS: research doc (the calculator deletion order) committed at p0 `47f639201`
- **Attack:** was the "delete calculator as SaaS" decision made by terra, or did it pre-date
  the campaign?
- **Result:** the research doc with :78/:146 (delete calculator) was committed in `47f639201`
  (p0). It did not exist on main's base. Attribution of the *decision* to terra's p0 stands.

### A2-4 PASS: revamp2 base = revamp1 tip
- **Attack:** could revamp2 have independently re-introduced or re-removed things?
- **Result:** `git merge-base edeb2a7e5 f13161f3b` = edeb2a7e5 (revamp1 tip). Revamp2 is a
  strict child of revamp1; inherited losses confirmed.

**Attribution verdict:** every cited commit/phase verified. No misattribution found.

---

## Attack 3 — Mechanism verdicts evidence-backed

### A3-1 PASS: H1/H2 supported — chains are direct
- **Attack:** is "interactive-layer loss" tautological? The chain is: census (14→0→1 sliders,
  6→0→0 charts) → attribution (two commits) → gate ordering (research doc :78/:146). Direct,
  file-cited, not inferred. Strong.

### A3-2 PASS: H3 — "an independent reviewer would flag" is now genuinely tested
- **Attack:** the p3 "independent reviewer" enumeration was performed by the analysis author —
  a weak form of independence.
- **Result:** FIXED by running a **separate agent with no exposure to the analysis** in p5.
  It reproduced the loss list AND found additional losses. The p4 self-review's silence on all
  of them is now independently confirmed. H3 evidence upgraded from author-enumerated to
  externally-enumerated.

### A3-3 PASS: H5 refuted — counterfactual holds
- **Attack:** "process not model" could be the spec's self-serving claim.
- **Result:** independent evidence supports it: terra DID implement interactivity when gated
  (beta slider, rule cards — p3 code), and gpt-5.6-sol's `framework_facelift` (same-tier
  model) preserved the calculator because ITS gate said "preserve" (spec text verified).
  H5 refuted as primary cause stands on behavior, not the spec's claim.

### A3-4 PASS: H6 — original's goodness concrete
- **Attack:** "impressive" is subjective. The p1/p2 measurements (interactivity, density,
  tables, charts, build iteration count 54-83 commits) are the concrete properties; the
  independent gpt56 UX review independently praised the same charts. Supported.

**Mechanism verdict:** no "supported" verdict had a weak chain; the one weak spot (H3
independence) was hardened in p5.

---

## Attack 4 — Would the recommendations actually fire?

### A4-1 PASS: R1 (preserve-interactive-features) fires against revamp2
- **Walk:** pre-change matrix (main) has 14 sliders / 6 canvases / 30 tables / 21 GitHub
  links; post-change (revamp2) has 1 slider / 0 canvases / 0 committed tables / 2 links. R1
  would block on the first diff line. The gate artifact (a JSON like diagram_inventory.json
  but for incumbent features) is mechanically constructible from this analysis's
  feature_matrix.json. **Fires.**

### A4-2 PASS: R2 (independent review) fires against revamp2
- **Walk:** revamp2's p4 reviewer was terra (same model, same workflow). R2 requires a
  different model/session. The p5 independent reviewer — run as a separate agent — found 23
  findings the p4 review missed. **Fires.**

### A4-3 PASS: R3 (before/after comparison) fires
- **Walk:** the p1 feature matrix IS the comparison. Revamp2 regresses on interactivity
  (14→1), charts (6→0), tables (30→0), depth (455KB→44KB), OG/GitHub/field-map. R3 fails the
  revamp on the majority of axes. **Fires.**

### A4-4 PASS with note: R6 (scoped-crusade guard) — would have blocked the calculator deletion
- **Walk:** the anti-SaaS gate deleted the calculator because "looks SaaS-adjacent". R6 says
  an anti-SaaS gate may constrain framing, not remove a transparent data-wired tool. Under
  R6 the calculator could not be deleted for that reason; terra would have had to re-frame.
  **Fires.** (Note: R6's carve-out is an editorial standard — it requires the operator to
  accept "transparent interactive tools are permitted" as a policy. Acceptable as a
  recommendation, flagged for operator sign-off.)

### A4-5 LIMITATION: R1/R3 depend on a matrix existing at campaign start
- **Attack:** R1/R3 presume a pre-change feature matrix exists. In the actual revamp2 run,
  no such matrix existed, so "would the gate have fired" is counterfactual.
- **Result:** accepted as a limitation. The fix is that the matrix is produced at campaign
  START (p0) as a required artifact, which is exactly what R1/R3 specify. The p1 matrix built
  in this campaign is the template.

---

## Attack 5 — Is the "independent reviewer" genuinely independent?

### A5-1 FIXED: true independence obtained in p5
- **Attack:** p3's H3 independent-reviewer enumeration was the analysis author's own list.
- **Result:** FIXED. A `general` subagent with **no prior exposure to this analysis** was
  given only the three file trees and the task. It independently produced a 24-point review:
  reproduced all 8 original losses, added 6 new ones (labs corpus, OG, GitHub, field-map,
  no-JS, methodology footer), fairly credited the additions (question.html, campaign
  receipts, provenance, a11y), and concluded "No — I would not have passed revamp2."
  This is a genuine second opinion, not the author's view.
- **Re-test:** PASS.

---

## Attack 6 — Was the operator's judgment used as data, not argued with?

### A6-1 PASS
- **Attack:** does any artifact argue with the operator ("you're wrong, the revamp is fine")
  or substitute the analyst's taste?
- **Result:** no. Every artifact treats "the current site is more impressive" and "trash" as
  ground-truth inputs to be explained, and the mechanism analysis explains *why* (H1-H6)
  without contesting the verdict. The p4 findings document explicitly states the operator's
  judgment is the exception bar for R1. PASS.

---

## Finding table

| ID | Check | Result | Disposition | Re-test |
|---|---|---|---|---|
| A1-1 | evidence tables count | **CONFIRMED error (30, not ~20)** | FIXED in feature_matrix.json + mechanism.md + attribution.json | PASS |
| A1-2 | glossary card count | **CONFIRMED error (15, not 14)** | FIXED in feature_matrix.json + mechanism.md | PASS |
| A1-3 | main labs empty? | **REFUTED — labs populated; subagent wrong** | Noted; strengthens main | PASS |
| A1-4 | revamp data.js labs dropped | **CONFIRMED (new loss)** | Added to attribution.json (accidental drop — build-gate artifact, `_load_labs` byte-identical) | PASS |
| A1-5 | OG/GitHub/field-map/no-JS/footer losses | **CONFIRMED (5 new losses)** | Added to attribution.json | PASS |
| A2-1..4 | commit/phase attribution | **all verified correct** | no fix | PASS |
| A3-1..4 | mechanism evidence chains | **all held**; H3 independence hardened | p5 independent agent added | PASS |
| A4-1..4 | R1/R2/R3/R6 fire against revamp2 | **all fire** | no fix | PASS |
| A4-5 | R1/R3 need pre-existing matrix | **LIMITATION** | accepted; matrix now a p0 artifact | — |
| A5-1 | independent reviewer truly independent | **FIXED** — separate agent ran | mechanism.md H3/p5 addendum updated | PASS |
| A6-1 | operator judgment as data | **PASS** | no fix | PASS |

**Overall adversarial verdict: FAILED to falsify.** The analysis survived all six attack
surfaces; four errors were found and fixed (all in the direction of UNDER-counting main),
six new losses were added (strengthening the case), and the independence of the H3 test was
upgraded from author-enumerated to a separate-agent review with identical conclusions.
