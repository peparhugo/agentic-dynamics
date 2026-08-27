# CAP Site Revamp 4 — p3 Implementation Census Log

**Campaign:** `cap_site_revamp4`
**Phase:** `p3_implement_augmentation`
**Executor:** deepseek/deepseek-v4-flash
**Gate artifact:** `experiments/results/cap_site_revamp3/incumbent_census.json` (p1, verified)
**Checker:** `scripts/site_census_check.py` (mechanical re-count, PASS = current ≥ baseline per axis)
**Rule:** a count below the incumbent census is a FAILED increment; restore before proceeding.

## Baseline (incumbent census)

| Axis | Baseline |
|---|---:|
| sliders | 14 |
| canvas_hosts | 6 |
| chart_construction_sites | 6 (census method: 7 literal `new Chart(` expressions for 6 chart ids — reconciliation already recorded in the census) |
| semantic_tables | 38 |
| handler_attachment_sites | 50 |
| theme_toggles | 1 |
| data_stat_literal_attributes | 64 |
| data_stat_unique_markup_keys | 22 |
| data_stat_fmt_literal_attributes | 3 |
| data_stat_supported_keys | 33 |
| data_anal_literal_attributes | 84 |
| data_anal_unique_keys | 12 |

## Per-increment census

| Increment | Commit | Axis count after increment (current) | Result |
|---|---|---|---|
| 1 — data door (`build_data.py` + `data.js` verdicts block) | `cbe2890a1` | all axes ≥ baseline (no counts touched; data.js regenerated) | PASS |
| 2 — `base.css` field-layer type/color system | `6cb016836` | all axes ≥ baseline (stylesheet only) | PASS |
| 3 — `question.html` route + nav wiring + sitemap | `d4043e65d` | all axes ≥ baseline; data-stat literal 64 → 68 (question.html adds 4 slots) | PASS |
| 4 — Home: field statement, receipt, instrument-cycle, Question CTA | `5cb0dc18b` | all axes ≥ baseline | PASS |
| 5 — Story: origin bridge + Question cross-link | `eb8edee5e` | all axes ≥ baseline | PASS |
| 6 — Framework: receipt, eight-planes, instrument-cycle, two-modes, bounded-autonomy, ten rule-status cards | `389f31880` | all axes ≥ baseline | PASS |
| 7 — Evidence: receipt, verdicts (cap_2b, escalation, calibration), honest-nulls | `cd037583a` | all axes ≥ baseline; data-stat literal 68 → 72 | PASS |
| 8 — Methodology: receipt, cost-curve explorable, honest-nulls | `e2ae206ae` | all axes ≥ baseline; sliders 14 → 15 (scenario control added, not incumbent) | PASS |
| 9 — Applications: bounded reframe + open questions | `4cd4a82d8` | all axes ≥ baseline | PASS |
| 10 — Related Work: [X] scope labels | `42932fa3e` | all axes ≥ baseline | PASS |
| 11 — Glossary: source anchors + evidence-class lines + receipt | `9b9ff5314` | all axes ≥ baseline | PASS |

## Final census after all increments

```
  PASS sliders                            baseline=  14 current=  15   (+1: methodology scenario control — an ADD, not a drop)
  PASS canvas_hosts                       baseline=   6 current=   6
  PASS chart_construction_sites           baseline=   6 current=   7   (7 literal new Chart( for 6 chart ids — census reconciliation)
  PASS semantic_tables                    baseline=  38 current=  38
  PASS handler_attachment_sites           baseline=  50 current=  50
  PASS theme_toggles                      baseline=   1 current=   1
  PASS data_stat_literal_attributes       baseline=  64 current=  72   (+8: receipts/evidence slots added — all supported by statMap)
  PASS data_stat_unique_markup_keys       baseline=  22 current=  22
  PASS data_stat_fmt_literal_attributes   baseline=   3 current=   3
  PASS data_stat_supported_keys           baseline=  33 current=  33
  PASS data_anal_literal_attributes       baseline=  84 current=  84
  PASS data_anal_unique_keys              baseline=  12 current=  12
RESULT: PASS
```

## ADD-surface verification (the revamp3 field-layer lesson)

Every approved ADD row is present as a checkable surface (verified mechanically, 2026-08-27):

- `question.html` served and linked from every page; Home leads with the field statement
- provenance receipt (`field-receipt`) on Home, Evidence, Methodology, Framework, Glossary
- instrument-cycle figure on Home AND Framework
- N×M figure on Question; Story links to Question
- origin-to-instrument bridge on Story ([H] preserved, dated)
- honest-null states on Evidence, Methodology, Applications
- cap_2b decision card (arms, n, CPVO ratio, CI, decision rule, authorization boundary) — hydrated from `data.js.verdicts`
- escalation E_x figure (baseline $0.008949, Sol 11.4671, Sonnet 12.5134, n=1)
- calibration arc (0/3 → 2/3 Wilson [0.2077, 0.9385] → 2b)
- eight-planes field map (Framework, INSTRUMENTED/PROPOSED/DECIDED)
- one-engine/two-modes figure (distinct from eight-planes)
- bounded-autonomy envelope (proposed capability visually distinct from not-run state)
- cost-curve explorable (Methodology, [C] N² scenario, separate from the live calculator)
- ten rule cards grouped by instrumented/proposed/decided
- typography/color system in shared `base.css`, both themes
- Applications bounded reframe + open questions
- Related Work [X] scope labels
- Glossary per-card source anchors + evidence-class lines

**LOG: PASS — 11 increments, 11/11 census checks PASS, 19/19 ADD surfaces present.**
