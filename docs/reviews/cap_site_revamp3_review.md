---
status: accepted
---
# CAP Site Revamp 4 — Independent Review (cap_site_revamp3_review)

**Campaign:** `cap_site_revamp4`
**Phase:** `p5_independent_review` (independent of `p3_implement_augmentation` and `p4_comparison_gate`)
**Reviewer:** deepseek/deepseek-v4-flash (separate session — did NOT implement; does NOT treat the executor's self-assessment or the comparison report as evidence)
**Reviewed tree:** `feature/site-revamp4` @ `e32388e2e82c2527029f24484600661054ced9ba`
**Census baseline:** `experiments/results/cap_site_revamp3/incumbent_census.json` (p1, `40691ff0b`)
**Comparison report under review:** `experiments/results/cap_site_revamp3/comparison_report.md`
**Approval artifact:** `approvals/cap_site_revamp4/p2_design_with_human_checkpoint_approval.md` (signed `peparhugo`, 2026-08-27)
**Design:** `docs/designs/current/cap_site_revamp3_design.md`
**Date:** 2026-08-27
**Method:** read-only re-measurement of the served source (`apps/website/`) via `grep -o | wc -l`, fixed-string matching; per-feature id/key presence checks; diff inspection against the census sha `2a58408a`; provenance cross-checks of `data.js` against committed score JSONs. No site file was modified.

**Preservation rule (from census):** "Any later count below this census is a failure unless an operator-signed waiver is committed." The approval proposed **zero removals** and granted **no waivers** (approval line 24: "REMOVE — None proposed"; notes: "none"). A count below baseline is therefore a FAILED finding. A lost identity (id/key) below baseline is likewise a FAILED finding.

---

## 1. Survival-verdict table (every incumbent feature)

All counts below are my own re-measurements of the current files. Where a count exceeds the census it is an approved ADD (addition, not replacement); where it matches it is KEPT. **No incumbent feature was lost.**

| Incumbent feature (census) | Baseline | Reviewer's count | Verdict | Evidence |
|---|---|---|---|---|
| 14 sliders (`input[type=range]`) on framework, each `oninput="updateROI()"` | 14 | **15** total = 14 framework + 1 methodology `cc-beta` (approved ADD) | **KEPT + ADD** | `framework.html`: 14 `type="range"` elements (grep count), 14 `oninput="updateROI()"` (framework.html:873-881), all 14 census ids present (`r_ac0, r_arate, r_batch, r_budget, r_cost, r_day, r_eng, r_epm, r_escalation, r_rate, r_retry, r_ses, r_vel, r_workload`); `methodology.html:292` adds `id="cc-beta"` (approved cost-curve ADD) |
| 6 canvas hosts | 6 | **6** (framework `costChart` 1 + evidence 5) | **KEPT** | `framework.html` `<canvas id="costChart">`; `evidence.html` `snowballChart`, `gritMatrixChart`, `narrationChart`, `costBarChart`, `locVsCostChart` (canvas id grep) |
| 6 chart construction sites (`new Chart(`) | 6 ids / 7 literal | **7 literal** `new Chart(` (framework 2 + evidence 5); 6 chart ids | **KEPT** | framework.html:1178 (cost + throughput branches of `buildChart`, one `costChart` instance); evidence.html:440, 1262, 1302, 1348, 1515 |
| Data-gated Grit chart host (not removable) | 6th host | host present; construction data-gated | **KEPT** | evidence.html:1380-1388 `if (!gritData) { … hide; return; }` before construction at 1515 — matches census "live_on_load: false" |
| 38 semantic tables | 38 | **38** (framework 3 + evidence 30 + methodology 2 + accelerator 3) | **KEPT** | `grep -oF '<table'` per page: framework=3, evidence=30, methodology=2, accelerator=3 |
| 50 handler attachment sites | 50 | **50** (31 inline `on*` + 14 `addEventListener` + 5 `.onclick`) | **KEPT** | inline `on*`: framework 31 (14 `oninput` + 10 `onclick` + 7 `onkeydown`; the meta `content=`/`controls=` hits are false positives) + evidence 0 real; `addEventListener`: app.js 4 (13,24,190,210) + framework 3 (1179,1183,1185) + evidence 7 (296,360,1237,1567,1906,1918,1920) = 14; `.onclick` assignment: app.js 3 (196,197,201) + evidence 2 (1442,1454) = 5 |
| Framework inline `on*` breakdown | 31 | **31** (7 chart-control onclick + 7 chart-control onkeydown + 2 calculator-mode onclick + 14 slider oninput + 1 disclosure onclick) | **KEPT** | framework.html `onclick`: `rebuildChart`×3 + `buildChart`×4 = 7 chart controls; `setCalcMode`×2; `toggleHow`×1; `onkeydown`×7; `oninput`×14 |
| Theme toggle (`body.light`, `ai-finops-theme`, localStorage) | 1 | **1** | **KEPT** | app.js:5-20 byte-identical to census fingerprint `69d78221…` (sha256 match) |
| Floating ToC runtime | present | present | **KEPT** | app.js:156-211 unchanged (app.js fingerprint identical) |
| 22 data-stat unique markup keys | 22 | **22** literal (excluding `ci95`, which exists only in the JS template at evidence.html:1660/1662 — census definition excludes it) | **KEPT** | unique `data-stat="…"` keys from all pages (grep sort -u) = 23 including `ci95`, 22 without |
| 33 supported statMap keys | 33 | **33** | **KEPT** | app.js:65-102 `statMap` — exact 33-key set matches census list |
| 3 data-stat-fmt literal attributes | 3 | **3** (accelerator 2 + databricks 1, all `woc`) | **KEPT** | accelerator.html + databricks.html `data-stat-fmt=` grep |
| 12 data-anal unique keys | 12 | **12** | **KEPT** | evidence.html unique `data-anal="…"` keys (grep sort -u) |
| 84 data-anal literal attributes | 84 | **84** | **KEPT** | evidence.html `data-anal=` count |
| 14 data-anal model rows | 14 | **14** | **KEPT** | evidence.html `data-anal-model=` count |
| data-stat literal attributes | 64 | **72** (64 incumbent + 8: evidence +4 receipts/verdict slots, question +4 new page) | **KEPT + ADD** | per-page counts: index 8, framework 4, evidence 22 literal (24 minus 2 script-template `ci95`), story 9, methodology 5, accelerator 6, databricks 6, glossary 8, question 4 = 72 |

**Framework/evidence interactive controls (census `framework_controls` / `evidence_controls`):**

| Control | Baseline | Reviewer's check | Verdict | Evidence |
|---|---|---|---|---|
| 3/10/25-year horizon | present | `yr3`, `yr10`, `yr25` ids present | **KEPT** | framework.html ids + inline `rebuildChart(3/10/25)` |
| baseline / DS-scenarios energy path | present | `epmBase`, `epmSens` ids present | **KEPT** | framework.html |
| cost/throughput view | present | `vwCost`, `vwThroughput` ids present; `updateChartToggle` defined | **KEPT** | framework.html:1183-1185 |
| augmented/autonomous calculator modes | present | `calcAugmented`, `calcAutonomous` ids; `setCalcMode` defined | **KEPT** | framework.html |
| how-computed disclosure | present | `howComputedToggle` + `toggleHow()` defined | **KEPT** | framework.html:887, 1176 |
| Grit model filters (data-gated) | present | `grit-model-filters` div + runtime model filter buttons (`btn.onclick` at evidence.html:1442) | **KEPT** | evidence.html:539, 1430-1448 |
| Two perturbation-class filters (data-gated) | present | `selectedPC` button `.onclick` at evidence.html:1454, calls `buildChart()` | **KEPT** | evidence.html:1454 |
| Six native details disclosures | 6 | **7** = 6 incumbent + 1 new "Method and limits" on cap_2b card (ADD) | **KEPT + ADD** | evidence.html `<details>` at 114, 478, 489, 1045, 1072, 1093 + new 1150; only 1150 is in the revamp diff |
| Archive details redraw hook | present | `perturbation-archive` details + `precursorCharts` Map + `toggle` listener resizing/redrawing each chart | **KEPT** | evidence.html:478, 1233, 1262/1302/1348/1558 (Map.set), 1564-1572 |
| Fragment reveal | present | `hashchange` → `revealFragment(location.hash)`; DOMContentLoaded reveal | **KEPT** | evidence.html:1883-1890, 1918, 1920 |
| Calculator data door | present | `window.DYNAMICS_DATA.calculator.model_costs` read (fallback array only if absent) | **KEPT** | framework.html:1132 |
| wfm-panel details (framework) | 1 | `wfm-panel` present (framework now 11 `<details>` = 1 incumbent + 10 new rule cards) | **KEPT + ADD** | framework.html:813 + rule-card details 923-986 |

**Verdict:** no incumbent feature lost; no identity (slider id, canvas id, stat key, anal key, handler site) lost; all interactive controls structurally wired. **0 FAILED findings on survival.**

---

## 2. Field-layer quality assessment

### 2a. Editorial quality

| Element | Present | Assessment |
|---|---|---|
| Field statement | Yes | index.html:67-68 — "Agentic Dynamics is the empirical study of how AI agents behave, adapt, interact, recover, and produce outcomes across changing tasks, environments, workflows, and time." Scoped as the field's question, not a best-practice claim (index.html:99 field-receipt "Limitation"). Coherent. |
| Named question | Yes | New `question.html` route (11,978 bytes) served and linked from all 8 incumbent pages. Names the N×M cumulative problem and an explicit open-problems list. |
| Origin-to-instrument bridge | Yes | story.html:99-111 — dated (2026-08-27), keeps the $20/Rome account as first-person `[H]` historical context, separates it from the 1,067-session corpus, and names the question it became. Correctly scoped. |
| Provenance receipts | Yes | `field-receipt` present on all five named pages: index (index.html:85), evidence (evidence.html:98 + escalation 1172 + calibration 1200 = 3), methodology (methodology.html:56, 280 = 2), framework (framework.html:277), glossary (glossary.html:37). Each carries class/source/corpus/date/limitation fields. |
| Honest-null states | Yes | `null-state` present on all three named pages: evidence (evidence.html:1211-1213, 3), methodology (methodology.html:298-300, 2), accelerator (accelerator.html:122 + open-questions 443-455, 5). Also question.html:104-108. States are named (`not measured`, `untriggered`, `underpowered`, `no canonical output`) — never `0`, never an unexplained dash, never a historical fallback. Evidence LSP null explicitly says "never '0 errors'" (evidence.html:1212). |
| Anti-SaaS guard | Pass | New copy contains no pricing/tiers/demo/"get started"/sign-up/free-trial/contact-sales conversion language. The `pricing` hits are per-token provider-rate data tables (incumbent, `[X]`/`[M]`) and the `enterprise`/`get started` hits on accelerator are the anti-SaaS guard note itself (accelerator.html:117) plus incumbent content re-labeled as bounded hypotheses (accelerator.html:122 "not validated", 127). `question.html` "tiers" is a research-tier reference. No conversion CTA in new copy. |
| Field test (reads as research field) | Pass | Field statement → named question → instrument cycle → receipts → honest nulls → verdicts with authorization boundaries → open problems. The calculator is reframed as a transparent `[C]` explorable with a "what is measured / computed / modeled" receipt (framework.html:277-285). Not a product funnel. |

### 2b. Provenance (data.js as the only data door)

**Verdicts block in data.js — present and generated.** `data.js:6695-6799` carries `verdicts.sources` (cap_2b / escalation / calibration) plus the full per-arm payloads. It is produced by the generator, not hand-typed: `scripts/build_data.py:1903-1990` (`CAP_2B_SCORE_PATH`, `ESCALATION_SCORE_PATH`, `_load_verdicts()`) reads the committed score JSONs. I cross-checked every headline value against the source artifacts:

| Claimed value | data.js | Source artifact | Match |
|---|---|---|---|
| cap_2b cpvo_ratio 0.785746 / margin 1.1 / NON_INFERIOR | data.js:6702-6708 | cap_2b_score_20260826T160018Z.json (`"cpvo_ratio": 0.785746`, `"margin_cpvo_ratio_le": 1.1`, `"decision": "NON_INFERIOR"`) | ✓ |
| escalation baseline $0.008949 | data.js:6766 | cap_escalation_measurement_score (line 9 `original_cell_cost_usd: 0.008949`) | ✓ |
| escalation Sol $0.102619 / E_x 11.4671 | data.js:6771-6774 | escalation score (lines 18/23) | ✓ |
| escalation Sonnet $0.111982 / E_x 12.5134 | data.js:6779-6782 | escalation score (lines 31/E_x 12.5134) | ✓ |
| calibration 2/3 = 0.6667, Wilson [0.2077, 0.9385], n=3 | data.js:6791-6797 | cap_2a_rerun2_score (`"hit_rate": 0.6667`, `wilson_95_ci: [0.2077, 0.9385]`, `n=3`) | ✓ |

**Hydration — partial (finding F1).** The **cap_2b decision card IS hydrated from data.js**: evidence.html:2040-2066 reads `D.verdicts.cap_2b` and `setIf(...)`-writes 10 live spans (`cap2b-decision`, `-ratio`, `-ci-lo/hi`, `-static-cost/cpvo/ok`, `-adaptive-cost/cpvo/ok`). The authored text in markup (evidence.html:1144-1147) is a no-JS fallback that matches today's values.

The **escalation E_x figure and calibration arc are NOT hydrated**: their values are hard-coded SVG `<text>` nodes (evidence.html:1161-1164 for baseline/fix/E_x; 1191-1195 for Wilson/2b panels). The comment at evidence.html:1133-1134 claims "Every value flows through data.js (window.DYNAMICS_DATA.verdicts)", but no JS reads `verdicts.escalation` or `verdicts.calibration` (grep confirms zero references; `setIf` ids cover cap_2b only). Today's hard-coded values all match data.js (cross-checked: 0.008949, 0.102619, 0.111982, 11.4671, 12.5134, 0.2077, 0.9385, 0.6842, 0.9105 present in both), so there is **no current data error** — but the "only data door" rule is only partially honored for the verdict figures. **Marked fix-on-branch (F1).**

**Footer label inconsistency (finding F2).** The $309.17 total is labeled "measured" in index.html:227, question.html:121, framework.html:1125, story.html:236, but "computed [C]" in evidence.html:1227 and the evidence body states "$309.1685 in total ([C], displayed as $309.17)" (evidence.html:87). The index/framework/story footers are **incumbent** (confirmed unchanged in the revamp diff — the "measured" label predates the campaign), but **question.html is new copy** and propagates the same mislabel for a `[C]` value. Minor — **mark as accepted-limitation/fix-on-branch (F2).**

### 2c. Visual system (base.css)

- **Typography/color system in shared base.css, both themes:** `:root` dark tokens (base.css:6-18) + `body.light` full override (base.css:26-27, 44-77); editorial serif (`--font-serif` = Source Serif 4) on `.essay`/`.lead` (base.css:394-423), mono for receipts (`--font-mono` JetBrains Mono), sans UI. The system lives in `base.css`, not page-local-only styles — the ADD requirement is met.
- **Evidence-class badges:** `.ev-badge` with textual + color encoding (base.css:433-450) — `[M] measured`, `[C] computed`, `[H] heuristic`, `[X] external`, `[P] policy`, each with a non-color `::before` text label and a `:focus-visible` outline. Color is never the only channel.
- **Reduced motion:** `@media(prefers-reduced-motion:reduce)` (base.css:554-558) kills `.pulse`/`animate`/`svg animate` animation and sets `scroll-behavior:auto`. Static meaning survives.
- **Theme toggle honored:** app.js unchanged (fingerprint match) and base.css defines both palettes; no page-local-only styling of the system.

### 2d. Anti-SaaS and field tests — see 2a (Pass / Pass).

---

## 3. Comparison verdict (my re-measurement vs incumbent census)

I re-ran every census count myself on the current files (grep fixed-string, `wc -l`), independent of `comparison_report.md`. My counts vs the incumbent census:

| Feature | Incumbent census | My count | Δ |
|---|---:|---:|---|
| sliders (`input[type=range]`) | 14 | 15 (14 framework + 1 methodology cc-beta) | +1 ADD |
| canvas hosts | 6 | 6 | 0 |
| chart construction sites | 6 ids / 7 literal `new Chart(` | 7 literal (6 ids) | 0 |
| semantic tables | 38 | 38 | 0 |
| handler attachment sites | 50 | 50 (31 inline + 14 addEventListener + 5 .onclick) | 0 |
| theme toggles | 1 | 1 | 0 |
| data-stat literal attributes | 64 | 72 | +8 ADD |
| data-stat unique markup keys | 22 | 22 | 0 |
| data-stat-fmt literal | 3 | 3 | 0 |
| statMap keys | 33 | 33 | 0 |
| data-anal literal | 84 | 84 | 0 |
| data-anal unique keys | 12 | 12 | 0 |
| data-anal model rows | 14 | 14 | 0 |

**Per-item identity checks (my own):** all 14 slider ids + `oninput="updateROI()"` binding; all 6 canvas ids; all 22 literal data-stat keys; all 33 statMap keys; all 12 data-anal keys; theme toggle (`localStorage['ai-finops-theme']`, `body.light`) at app.js:5-20; framework controls (yr3/yr10/yr25, epmBase/epmSens, vwCost/vwThroughput, calcAugmented/calcAutonomous, howComputedToggle/toggleHow); evidence controls (grit filters, perturbation-class filters, 6 disclosures, `precursorCharts` redraw, `hashchange` fragment reveal). All present.

**All 14 approved ADD surfaces verified present** (comparison_report.md's claim, independently re-checked):
1. verdicts block in data.js ✓ (data.js:6695-6799, generated)
2. question.html route + linked from every page ✓ (all 8 pages)
3. field-receipt on Home/Evidence/Methodology/Framework/Glossary ✓
4. instrument-cycle figure on Home AND Framework ✓ (index.html:151; framework.html:605)
5. honest-null states on Evidence/Methodology/Applications ✓
6. cap_2b decision card ✓ (evidence.html:1140)
7. escalation E_x figure ✓ (evidence.html:1154)
8. calibration arc ✓ (evidence.html:1183)
9. eight-planes field map ✓ (framework.html:576)
10. ten rule cards ✓ (framework.html:919-982 — 3 measured + 7 proposed; 0 "decided", which is honest: no rule is yet run-and-compared as an arm, per the design's own definition)
11. cost-curve explorable ✓ (methodology.html:292 `cc-beta` + `cc-plot` redraw script)
12. Applications bounded reframe + open questions ✓ (accelerator.html:107-124, 443-457)
13. Related Work `[X]` scope labels ✓ (databricks.html scope-labels receipt + `ev-badge x` on each external claim)
14. Glossary source anchors + evidence-class lines ✓ (glossary.html `gmeta` on all 15 `.gcard`s)

**Comparison verdict: PASS.** The revamp is augmentation-only; every incumbent feature survives by count and by identity; the instrument remains operable (14 levers draggable → 15, disclosures expandable, filters filterable, charts constructible, archive redraw and fragment reveal live); every approved ADD surface is present. The delta table above — not "spec satisfied" — is the basis. This matches the comparison report's PASS, now independently corroborated.

**Findings:** 0 FAILED (nothing lost, no waiver needed). 2 non-failing items:
- **F1 (fix-on-branch):** escalation/calibration figures are hard-coded markup, not hydrated from `data.js`, contradicting the comment at evidence.html:1133-1134. Values currently match data.js (verified) so no data error; wire them to `D.verdicts` so regeneration cannot drift.
- **F2 (accepted-limitation / fix-on-branch):** new `question.html` footer labels the `[C]` total $309.17 as "measured"; evidence labels it "computed [C]". Inherited from incumbent footers, but the new page could have corrected it.

---

## 4. Known-safe list

**Verified safe (mechanical preservation, byte/count identity):**
- All 14 incumbent sliders + `updateROI()` oninput bindings; methodology `cc-beta` (new, additive).
- All 6 canvases; all 7 `new Chart(` construction expressions (6 chart ids); Grit host data-gated, not removed.
- All 38 semantic tables (3/30/2/3 across framework/evidence/methodology/accelerator).
- All 50 handler attachment sites (31 inline + 14 addEventListener + 5 .onclick); framework inline breakdown 7/7/2/14/1 matches census.
- Theme toggle + floating ToC: app.js byte-identical to census fingerprint `69d78221…` — statMap (33 keys), data-stat/data-anal injection, theme persistence all preserved verbatim.
- All 22 data-stat markup keys, 33 statMap keys, 3 data-stat-fmt (`woc`), 12 data-anal keys, 84 data-anal cells, 14 model rows.
- All framework controls (horizon, energy path, cost/throughput, calculator modes, how-computed) and all evidence controls (grit filters, class filters, disclosures, archive redraw, fragment reveal).

**Verified safe (field layer):**
- `data.js` verdicts block is generator-produced (`build_data.py _load_verdicts`) and matches committed score artifacts; cap_2b card hydrated from it.
- Receipts on all five named pages; honest-null states on all three named pages (plus question.html); instrument-cycle on Home and Framework; eight planes; one-engine/two-modes; bounded-autonomy envelope; ten rule cards; N×M figure on question.html; cost-curve explorable; Applications bounded reframe; Related Work `[X]` labels; Glossary `gmeta` anchors.
- base.css typography/color system in both themes; ev-badge textual+color classes; reduced-motion block.

**Fix-on-branch:** F1 (escalation/calibration figure hydration), F2 (question.html `[C]`-as-"measured" footer).

**Accepted limitation:** the two "decided"-state gaps — zero rule cards marked "decided" (honest: no arm run-and-compared) and zero currently-constructed Grit instance (data-gated by absence of canonical quadrant data; host and construction site preserved).

---

## Reviewer attestation

I verified the comparison report's claims against the files, not the executor's self-assessment. Every count, id, key, binding, and ADD surface above was re-derived independently. The review is read-only; no site file was modified.

**Not signed as an aggregate PASS** — signed as: **PASS with 0 FAILED findings, 2 fix-on-branch items (F1, F2).**
