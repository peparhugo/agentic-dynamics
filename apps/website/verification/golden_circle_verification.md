# Golden Circle site revamp — verification record (execute phase)

**Campaign:** `site_golden_circle_revamp` (the 2026-09-22 website campaign).
**Scope of this record:** the execute phase's gate outputs. **No deploy runs here** — both
Firebase deploys are the controller's P0 acts.

## Gates that ran

| Gate | Command | Result |
|---|---|---|
| Preservation census | `python3 scripts/site_census_check.py` | **PASS** — 12/12 headline axes ≥ baseline |
| Static fallback guard | `pytest tests/test_static_fallback_guard.py` | PASS |
| Static narrative guard | `pytest tests/test_static_narrative_guard.py` | PASS |
| Publication door | `pytest tests/test_publication_singular_door.py` | PASS |
| Stale-path guard | `pytest tests/test_stale_path_guard.py` | PASS |
| Data builder | `pytest tests/test_build_data.py` | PASS |
| Link / anchor scan | regex scan of every `*.html` | clean — no broken internal link or fragment |
| SVG structural scan | inline-`<svg>` parse (below) | 13/13 rendered figures: valid XML, `viewBox`, `<title>`, no external image refs, text ≤ 1.5× shape markup |

Combined static run: `45 passed, 4 skipped`.

## Census (12/12 PASS)

Baseline: `apps/website/verification/incumbent_census.json` (the tracked revamp4 contract;
the checker also honors the legacy `experiments/results/…` copy when present).
`data_stat_literal_attributes` 72 → 78 and `data_stat_unique_markup_keys` 22 → 23: the
additions are the new prose `data-stat` slots (the index N×M receipt gained `architectures`,
`stories_total`, `variants`; the framework WHY hero gained `story_sessions`). **No axis
dropped.** Sliders 15 ≥ 14, chart sites 7 ≥ 6, tables 38 = 38, handlers 50 = 50.

## SVG structural scan (browser-independent)

Every rendered `role="img"` SVG on `architecture / index / framework / question / evidence /
methodology` parses as well-formed XML, carries a `viewBox` and a `<title>`, contains shape
elements, has text length ≤ 1.5× shape-markup length, and references **no external image**
(hand-built assets only). The new `architecture.html` figures:

| figure | viewBox | shapes | text | shape markup | balance |
|---|---|---|---|---|---|
| A1 eight planes | 0 0 1440 560 | 28 | 1231 | 1763 | PASS |
| A2 instrument → policy | 0 0 1440 580 | 21 | 976 | 1462 | PASS |
| A3 spec → DAG → cells | 0 0 1440 560 | 22 | 1367 | 1393 | PASS |
| A4 admission gate | 0 0 1440 520 | 18 | 1117 | 1146 | PASS |

## Blocker: the browser render gate could not execute in this environment

The documented visual gate is `apps/website/verify_svg_rendering.py` (playwright). This
sandbox has no browser system libraries and no root/apt to install them, so chromium cannot
launch:

```
chrome-headless-shell: error while loading shared libraries: libglib-2.0.so.0:
cannot open shared object file: No such file or directory
```

`apt-get` cannot populate package lists without root, and no `libglib`/`libcairo` exists
anywhere on the host. The gate script and page list were updated (`architecture.html` is now
in `DEFAULT_PAGES`), so the gate is ready to run where playwright's system deps are present —
**the controller should run it before deploying**:

```bash
python3 apps/website/verify_svg_rendering.py \
  --pages framework.html,architecture.html,question.html,evidence.html,methodology.html
python3 apps/website/verify_svg_rendering.py --mobile
```

This is an environment limitation, not a code defect; it is recorded rather than worked
around (no parallel render mechanism was invented).

## The controller's deploy commands (prepared, NOT run)

```bash
cd apps/website
firebase deploy --only hosting                         # canonical ai-finops-rulebook
firebase deploy --only hosting --project agentic-dynamics   # mirror — deploy BOTH
```
