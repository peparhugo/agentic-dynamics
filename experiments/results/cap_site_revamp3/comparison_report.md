# CAP Site Revamp 4 — p4 Comparison Gate Report

**Campaign:** `cap_site_revamp4`
**Phase:** `p4_comparison_gate`
**Executor:** deepseek/deepseek-v4-flash
**Incumbent census:** `experiments/results/cap_site_revamp3/incumbent_census.json` (p1, `40691ff0b`)
**Checker:** `scripts/site_census_check.py` (mechanical re-count) + the per-feature id/key delta below (mechanical)
**Date:** 2026-08-27

## Gate definition

The revamp FAILS the comparison gate if **any** of these hold:

1. Any incumbent feature is lost without the operator's committed waiver.
2. Any axis the revamp claims to improve regressed.
3. The instrument's operation changed — a visitor who could drag the levers must still be able to (handlers tested structurally).

"Specification satisfied" is not a pass; only the feature-by-feature delta table is.

## Delta table (incumbent → revamp)

| Feature class | Incumbent | Revamp | Delta | Axis verdict |
|---|---:|---:|---|---|
| sliders (`input[type=range]`) | 14 | 15 | **+1** (Methodology N² scenario control — an ADD, not a replacement) | KEPT + ADD |
| canvas hosts | 6 | 6 | 0 | KEPT |
| chart construction sites (`new Chart(`) | 6 (chart ids) / 7 (literal expressions) | 7 (literal) | 0 | KEPT |
| semantic tables | 38 | 38 | 0 | KEPT |
| handler attachment sites | 50 | 50 | 0 | KEPT |
| theme toggles | 1 | 1 | 0 | KEPT |
| data-stat literal attributes | 64 | 72 | **+8** (receipts + evidence slots) | KEPT + ADD |
| data-stat unique markup keys | 22 | 22 | 0 | KEPT |
| data-stat-fmt literal attributes | 3 | 3 | 0 | KEPT |
| data-stat supported statMap keys | 33 | 33 | 0 | KEPT |
| data-anal literal attributes | 84 | 84 | 0 | KEPT |
| data-anal unique keys | 12 | 12 | 0 | KEPT |

### Per-item identity check (incumbent item → still present by id/key)

| Incumbent item | Check | Result |
|---|---|---|
| All 14 sliders (r_eng … r_arate) with `oninput="updateROI()"` | id + binding | KEPT |
| All 6 canvas ids (costChart, snowballChart, gritMatrixChart, narrationChart, costBarChart, locVsCostChart) | `<canvas id=…>` | KEPT |
| Chart construction per page (framework ≥ 2, evidence ≥ 5) | literal `new Chart(` | KEPT |
| 38 semantic tables across pages (framework 3, evidence 30, methodology 2, accelerator 3) | `<table` per page ≥ incumbent | KEPT |
| 22 literal data-stat markup keys | present in markup | KEPT |
| 33 supported statMap keys in `app.js` | present in `statMap` | KEPT |
| 12 data-anal keys | present in markup | KEPT |
| Theme toggle (`ai-finops-theme`, `classList`, `localStorage`) | `app.js` | KEPT |

## Instrument operation — structural handler test (axis 3)

A visitor who could drag the levers must still be able to. Verified structurally on the revamped source:

| Control | Verification | Result |
|---|---|---|
| Framework inline `on*` handlers | 31 present (10 onclick + 7 onkeydown + 14 oninput) — matches the census's 31 | KEPT |
| Slider → `updateROI()` | every slider id carries `oninput="updateROI()"` | KEPT |
| Calculator mode toggle (augmented/autonomous) | `calcAugmented` + `calcAutonomous` present; `updateROI` defined | KEPT |
| Cost/throughput view + 3/10/25-year horizon + energy path | `chartView`, `chartYears`, mode controls + `buildChart` defined | KEPT |
| How-computed disclosure | `howComputedToggle` + `toggleHow()` defined | KEPT |
| Evidence addEventListener sites | ≥ 7 present | KEPT |
| Evidence `.onclick` assignments | ≥ 2 present | KEPT |
| Framework addEventListener sites | ≥ 3 present | KEPT |
| app.js addEventListener / `.onclick` assignments | ≥ 4 / ≥ 3 present | KEPT |
| Evidence disclosures | ≥ 6 `<details>` present | KEPT |
| Archive redraw hook | `precursorCharts` present | KEPT |
| Fragment reveal | `hashchange` → `revealFragment(location.hash)` present (evidence.html:1918) | KEPT |
| Theme + ToC runtime | `toc-overlay`, `scrollIntoView` present in app.js | KEPT |

No instrument control was replaced by a static approximation; every interactive surface remains wired.

## ADD surfaces (the revamp's claims — presence verified, not self-certified)

| Approved ADD | Surface | Result |
|---|---|---|
| Verdicts block through `data.js` (the only data door) | `"verdicts"`, `"cap_2b"`, `"escalation"`, `"calibration"` in data.js | ADDED |
| `question.html` route served + linked from every page | link in all 8 incumbent pages | ADDED |
| Provenance receipt on Home, Evidence, Methodology, Framework, Glossary | `class="field-receipt"` on all five | ADDED |
| Instrument-cycle figure on Home AND Framework | figure on both | ADDED |
| Honest-null states on Evidence, Methodology, Applications | `class="null-state"` on all three | ADDED |
| cap_2b decision card | `cap2b-card` on Evidence | ADDED |
| Escalation E_x figure | on Evidence | ADDED |
| Calibration arc | on Evidence | ADDED |
| Eight-planes field map | on Framework | ADDED |
| Ten rule-status cards | on Framework | ADDED |
| Cost-curve explorable (N² scenario) | `cc-beta` control on Methodology | ADDED |
| Applications bounded reframe + open questions | on accelerator.html | ADDED |
| Related Work [X] scope labels | on databricks.html | ADDED |
| Glossary per-card source anchors + evidence-class lines | `gmeta` on glossary.html | ADDED |

## Waivers

The approved design (`docs/designs/current/cap_site_revamp3_design.md`, operator-signed
`approvals/cap_site_revamp4/p2_design_with_human_checkpoint_approval.md`, peparhugo 2026-08-27)
proposed **zero removals** and granted no waivers. No incumbent feature was lost, so no waiver is
required. The only numerical increases (slider 14→15, data-stat 64→72) are additions consumed by
new field-layer surfaces; no axis regressed.

## PASS / FAIL per axis

| Axis | Verdict |
|---|---|
| Incumbent features lost without waiver | **PASS** — 0 lost (all kept by count and by id/key) |
| Claimed-improvement axes regressed | **PASS** — no axis dropped; the data layer and sliders only grew |
| Instrument operation (handlers) unchanged | **PASS** — 50 handler sites intact; every control structurally wired |
| ADD surfaces present (revamp3's failed axis) | **PASS** — 14/14 verified present |

## Result

**COMPARISON GATE: PASS.** The revamp is augmentation-only: every incumbent feature survives by
count and by identity, the instrument remains operable (levers draggable, disclosures expandable,
filters filterable, charts constructible), and every approved ADD surface is present. The delta
table above — not "spec satisfied" — is the pass.
