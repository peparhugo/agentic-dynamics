# `apps/website/` — Public Website

Hosted at [ai-finops-rulebook.web.app](https://ai-finops-rulebook.web.app) (canonical, already
shared with peers) and mirrored at [agentic-dynamics.web.app](https://agentic-dynamics.web.app).
Firebase static hosting. The website *source* lives here (`apps/website/`); the Firebase *deploy
config* lives in `firebase/` (`firebase.json`, `.firebaserc`).

## Deploy Config (in `firebase/`)

| File | Purpose |
|------|---------|
| `firebase/.firebaserc` | Projects: `ai-finops-rulebook` (default) + `agentic-dynamics` (mirror) |
| `firebase/firebase.json` | Hosting config — `"public": "../apps/website"` |

## Pages + Assets

| File | Page | Content |
|------|------|---------|
| `index.html` | Home | Agentic Dynamics hero + key findings |
| `framework.html` | Operational Framework | Dynamics → business outcomes, levers, calculator, provider playbook |
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
external. Run `build_data.py` to refresh after new experiments. Review metrics are aggregated
from `experiments/results/reviews/`. The `deploy` plan in `scripts/pipeline.py` (refresh → sync →
build → deploy) runs this end-to-end.

## Deploy

```bash
firebase deploy --only hosting                          # canonical (ai-finops-rulebook)
firebase deploy --only hosting --project agentic-dynamics   # mirror — deploy BOTH
```

Both projects serve the same `apps/website/` — never let them drift. Never retire the canonical
`ai-finops-rulebook` project (the URL is already shared with peers).
