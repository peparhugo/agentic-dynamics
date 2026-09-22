# `apps/website/` — Public Website

Hosted at [ai-finops-rulebook.web.app](https://ai-finops-rulebook.web.app) (canonical, already
shared with peers) and mirrored at [agentic-dynamics.web.app](https://agentic-dynamics.web.app).
Firebase static hosting. The website *source* and the Firebase *deploy config* both live here
(`apps/website/`).

## Deploy Config

| File | Purpose |
|------|---------|
| `.firebaserc` | Projects: `ai-finops-rulebook` (default) + `agentic-dynamics` (mirror) |
| `firebase.json` | Hosting config — `"public": "."` (this directory) |

## Pages + Assets

| File | Page | Content |
|------|------|---------|
| `index.html` | Home | Golden Circle (WHY → HOW → WHAT) hero + key findings |
| `architecture.html` | Architecture | The system as built — eight planes, the instrument → information → policy chain, the spec/compiler pipeline, and the admission gate, as hand-built [P] SVGs |
| `framework.html` | Operational Framework | Golden Circle order: WHY (measured levers) → HOW (engine, architecture, calculator) → WHAT (policy arms, rule cards, playbook) |
| `evidence.html` | The Evidence | Grit spectrum, cost ranking, AST analysis, perturbation response |
| `story.html` | The Story | How a $20 API key became an experimental instrument |
| `methodology.html` | The Instrument | Experiment design, 10 perturbation operators, 7 recovery signals |
| `accelerator.html` | Applications | Operational hypotheses, maturity ladder, projections |
| `databricks.html` | Related Work | Mapping every Databricks claim to calibrated measurements |
| `glossary.html` | Glossary | Terminology reference |
| `app.js` | — | Interactive UI, levers, calculator, charts |
| `base.css` | — | Base stylesheet |
| `data.js` | — | **Generated.** `window.DYNAMICS_DATA` with all measurements, provenance-tagged |

## Data Pipeline

```bash
python scripts/inventory.py refresh       # scan DB + worktrees
python scripts/sync_data.py               # story results → sessions/stories.parquet
python scripts/analyze_worktrees.py       # produce _results_summary.json
python scripts/build_data.py              # generate apps/website/data.js (~179KB)
python scripts/generate_manifest.py       # generate data_manifest.json
```

`data.js` is the sole dynamic file. Every number on the website is live-generated from
experimental data with provenance tags: `[M]` measured, `[C]` computed, `[H]` heuristic, `[X]`
external, `[P]` policy/prior. Run `build_data.py` to refresh after new experiments. Review
metrics are aggregated from `experiments/results/reviews/`. The `deploy` plan in
`scripts/pipeline.py` (refresh → sync → build → deploy) runs this end-to-end.

## Navigation + gates

Every page carries one canonical `topbar` (Home · Instrument · Evidence · Framework ·
Architecture · Story · Question · GitHub), with the current page marked
`style="color:var(--ac)" aria-current="page"`.

- **Preservation census** — `python3 scripts/site_census_check.py`. Its baseline is the
  operator-signed revamp4 contract; the durable copy is tracked at
  `apps/website/verification/incumbent_census.json` (the checker also honors the legacy
  `experiments/results/…` copy when present). A count below the baseline is a failure.
- **Static guards** — `tests/test_static_fallback_guard.py` (data-stat fallbacks equal `data.js`)
  and `tests/test_static_narrative_guard.py` (no retired corpus figures / live `bad_seed`).
- **Render gate** — `apps/website/verify_svg_rendering.py` (playwright; per-SVG size / overflow /
  aspect / balance / contrast / paint / console). `architecture.html` is in `DEFAULT_PAGES`.
  Requires a browser with system libs; the gate is the pre-deploy visual check.

## Deploy surface

`firebase.json` sets `"public": "."` and ignores the internal process artefacts that are not
served: `verification/`, `references/`, `CONTEXT.md`, `verify_svg_rendering.py`,
`verify_svg_report.md`, plus dotfiles and `node_modules`. Only the page assets, `app.js`,
`base.css`, `data.js`, and the two OG/field-map images are published.

## Deploy

```bash
firebase deploy --only hosting                          # canonical (ai-finops-rulebook)
firebase deploy --only hosting --project agentic-dynamics   # mirror — deploy BOTH
```

Both projects serve the same `apps/website/` — never let them drift. Never retire the canonical
`ai-finops-rulebook` project (the URL is already shared with peers).
