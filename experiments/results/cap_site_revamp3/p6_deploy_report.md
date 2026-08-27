# CAP Site Revamp 4 — p6 Deploy Report

**Campaign:** `cap_site_revamp4`
**Phase:** `p6_deploy` (the ONLY deploy-allowed phase, hard rule 8)
**Executor:** deepseek/deepseek-v4-flash
**Incumbent census:** `experiments/results/cap_site_revamp3/incumbent_census.json` (p1)
**Date:** 2026-08-27

## Jobs (this phase only — no re-narration of the census)

1. Run the data chain fresh
2. Deploy BOTH Firebase projects from `apps/website/`
3. Verify the DEPLOYED pages against the preservation census + comparison delta
4. Both URLs 200 + mirror identical

## 1. Fresh data chain

| Step | Command | Result |
|---|---|---|
| sync | `python3 scripts/sync_data.py` | Synced 1,067 sessions, 215 stories → `experiments/data/{sessions,stories}.parquet` |
| build | `python3 scripts/build_data.py` | Wrote `apps/website/data.js` (188,969 bytes); verdicts block present (cap_2b, escalation, calibration) |
| manifest | `python3 scripts/generate_manifest.py` | `experiments/data_manifest.json` (12,658 entities compacted); data.js sha256 `39133c2e3c7e…` |

The registry had grown since the p1–p5 data.js was committed (12,485 → 12,658 rows via the main
merge). A fresh `build_data.py` therefore rejected the 7 committed lab outputs as stale
(`lab-gate`, registry identity mismatch) — the naive fresh chain dropped the lab section from
data.js. That is a deploy-blocking regression (evidence.html renders grit/story_arc/
quality_frontier/condition_effects from `D.labs.*`), so the 7 publication-eligible labs were
re-run against the current registry before building. Their `lab_contract` now matches
(`data-manifest/1.0+12658rows`); the regenerated data.js is byte-identical to the committed
artifact in every measured value — only the 7 `registry_version` contract lines changed.

## 2. Deploy (BOTH projects, from `apps/website/`)

| Project | Command | Result |
|---|---|---|
| canonical `ai-finops-rulebook` | `firebase deploy --only hosting` | ✔ Deploy complete → https://ai-finops-rulebook.web.app |
| mirror `agentic-dynamics` | `firebase deploy --only hosting --project agentic-dynamics` | ✔ Deploy complete → https://agentic-dynamics.web.app |

Both project IDs were available from `firebase projects:list` — no STOP-and-ask was needed.

## 3. Deployed-census verification (instrument is live on the deployed URLs)

Fetched every route + shared asset from both hosts and re-ran the preservation census
(`scripts/site_census_check.py` counting rules, SITE_ROOT pointed at the fetched canonical
files) against the DEPLOYED source:

| Axis | Incumbent baseline | Deployed | Result |
|---|---|---:|---:|---|
| sliders | 14 | 15 (+1 ADD: methodology cost-curve control) | PASS |
| canvas hosts | 6 | 6 | PASS |
| chart construction sites | 6 | 7 (literal; 6 chart ids) | PASS |
| semantic tables | 38 | 38 | PASS |
| handler attachment sites | 50 | 50 | PASS |
| theme toggles | 1 | 1 | PASS |
| data-stat literal attributes | 64 | 72 (+8 ADD) | PASS |
| data-stat unique markup keys | 22 | 22 | PASS |
| data-stat-fmt literal attributes | 3 | 3 | PASS |
| data-stat supported statMap keys | 33 | 33 | PASS |
| data-anal literal attributes | 84 | 84 | PASS |
| data-anal unique keys | 12 | 12 | PASS |

**Per-item identity (deployed vs incumbent census):** all 14 incumbent slider ids present with
`oninput="updateROI()"` (the 15th is the approved ADD); all 6 canvas ids present; theme toggle
persists `ai-finops-theme` + `body.light` via localStorage; verdicts block + all 7 canonical
labs present in the deployed `data.js`.

**Deployed instrument operation:** framework inline `on*` = 31 (incumbent 31), evidence
`addEventListener` = 7 (incumbent 7), `new Chart(` = framework 2 + evidence 5. A visitor on
the live URL can still drag every lever.

**Deployed ADD surfaces:** receipts on 5 pages, question route, instrument-cycle Home+Framework,
honest-nulls on 3 pages, cap_2b card + escalation + calibration with all hydration ids,
verdicts block in deployed data.js, eight planes + ten rule cards, cost-curve explorable,
Applications reframe, Related Work [X] labels, Glossary anchors — all present.

## 4. URL + mirror verification

| Check | Result |
|---|---|
| canonical 12/12 files HTTP 200 (9 pages + base.css + app.js + data.js) | PASS |
| mirror 12/12 files HTTP 200 | PASS |
| mirror byte-identical to canonical (12/12 `cmp -s`) | PASS |

## PASS / FAIL

| Axis | Verdict |
|---|---|
| Fresh data chain (labs refreshed against current registry) | PASS |
| Deploy both projects | PASS |
| Deployed census (instrument preserved) | PASS |
| Deployed per-item identity | PASS |
| Deployed ADD surfaces | PASS |
| Both URLs 200 | PASS |
| Mirror identical | PASS |

## Result

**DEPLOY: PASS.** Both Firebase projects serve the revamped site; the deployed pages preserve
the full instrument census (no regression, mechanically re-counted on the live URLs), carry
every approved ADD surface, hydrate verdicts from the deployed `data.js`, both URLs return 200,
and the mirror is byte-identical. The deploy succeeded from the final phase only, per hard rule 8.
