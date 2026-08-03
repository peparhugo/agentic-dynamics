# AI FinOps Framework — v0.1

The first open framework for measuring and predicting AI inference costs. Not a benchmark. An instrument you can extend, debate, and improve.

> *"The one job of a v1.0 framework: establish vocabulary, measurement apparatus, and replicable methodology. By that standard, this is an A-."* — External review, August 2026

## What This Is

- **10 perturbation operators** (5 manifold, 5 semantic) that probe reasoning topology
- **6 recovery detection signals** that classify how models respond to disruption
- **4 strategy archetypes** (Conservative, Exploratory, Wasteful, Efficient)
- **One unified equation** that projects AI inference costs under any assumptions
- **178 experiment sessions** across 8 models, 22 configs, 5 domains

## Quick Links

| Page | What |
|------|------|
| [The Framework](https://ai-finops-rulebook.web.app) | Rules, calculator, decision framework |
| [The Story](https://ai-finops-rulebook.web.app/story.html) | How a $20 API key became this |
| [The Methodology](https://ai-finops-rulebook.web.app/methodology.html) | Experiment design and instrument |
| [The Evidence](https://ai-finops-rulebook.web.app/evidence.html) | 186 worktrees, full data, AST analysis |

## Repo Structure

```
├── src/instrument/         # Python measurement apparatus
│   ├── perturb.py          # 10 perturbation operators
│   ├── trajectory.py       # Reasoning trajectory capture
│   ├── recovery.py         # Recovery classification (6 signals)
│   ├── basin.py            # Basin escape measurement
│   ├── strategy.py         # Strategy archetype classification
│   ├── efficiency.py       # Token/cost/energy efficiency
│   └── experiment.py       # Full experiment runner
├── experiments/
│   ├── configs/            # 22 YAML experiment definitions
│   └── results/            # Raw experiment output
├── scripts/                # Run, batch, sweep scripts
├── firebase/public/        # Website source
└── pyproject.toml          # Python package config
```

## How to Run

```bash
# Install
pip install -e .

# Run a single experiment
python scripts/run.py --config experiments/configs/task_manager.yaml

# Run a batch
python scripts/batch_run.py
```

## Current Scope (v0.1)

**Covered today:**
- 8 models across Python/Flask REST APIs, CRUD apps, real-time collaboration frontends
- 10 prompt-level perturbation operators
- IEA-baseline EPM projection (linear, 1.6%/year)
- Inference cost measurement (tokens, dollars, joules)

**Planned for v0.2+ (pull requests welcome):**
- TypeScript, Rust, Go validation
- Structural perturbation operators (broken deps, AST corruption)
- EPM sensitivity analysis (aggressive/optimistic/volatile scenarios)
- Human maintenance cost modeling

**Not in scope:**
The framework does not judge whether narration is "wasteful" or "valuable" — it measures the cost. If your team needs auditable reasoning trails, the Explanation Tax is insurance, not overhead. The instrument is model-agnostic. DeepSeek was chosen as the anchor case study, not an endorsement.

## License

MIT
