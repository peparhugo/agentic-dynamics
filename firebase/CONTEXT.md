# `firebase/` — Public Website

Hosted at [ai-finops-rulebook.web.app](https://ai-finops-rulebook.web.app). Firebase static hosting.

## Config Files

| File | Purpose |
|------|---------|
| `.firebaserc` | Project: `ai-finops-rulebook` |
| `firebase.json` | Hosting config (source: `public/`) |

## `public/` — 8 Pages + 3 Assets

| File | Page | Content |
|------|------|---------|
| `index.html` | Home | AI FinOps Dynamics hero + key findings |
| `framework.html` | Operational Framework | 10 principles, levers, interactive calculator, provider playbook |
| `evidence.html` | The Evidence | Grit spectrum, cost ranking, AST analysis, perturbation response |
| `story.html` | The Story | How a $20 API key became an experimental instrument |
| `methodology.html` | The Instrument | Experiment design, 10 perturbation operators, 6 recovery signals |
| `accelerator.html` | Applications | Operational hypotheses, maturity ladder, projections |
| `databricks.html` | Related Work | Mapping every Databricks claim to calibrated measurements |
| `glossary.html` | Glossary | Terminology reference |
| `app.js` | — | Interactive UI, levers, calculator, charts |
| `base.css` | — | Base stylesheet |
| `data.js` | — | **Generated.** `window.DYNAMICS_DATA` with all measurements, provenance-tagged |

## Data Pipeline

```bash
python scripts/inventory.py refresh       # scan DB + worktrees
python scripts/analyze_worktrees.py       # produce _results_summary.json
python scripts/build_data.py              # generate public/data.js (~31KB)
```

`data.js` is the sole dynamic file. Every number on the website is live-generated from experimental data with provenance tags: `[M]` measured, `[C]` computed, `[H]` heuristic, `[X]` external. Run `build_data.py` to refresh after new experiments.

## Deploy

```bash
firebase deploy --only hosting
```
