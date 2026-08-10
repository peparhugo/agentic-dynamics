# AI FinOps Framework — Routing Guide

Calibrated measurement instrument for AI inference costs. 227 stress tests across 8 models.
Measures **Grit** (Ground-Truth Integrity): correctness under degraded/contradictory input.

## Decision Tree

```
What are you doing?
├─ Modifying measurement logic (perturb.py, basin.py, etc.)
│  └─ Read: src/instrument/CONTEXT.md
├─ Running experiments against a model
│  └─ Load skill: instrument
├─ Analyzing experiment results / generating game reports
│  └─ Load skill: analyze
├─ Running a lab book analysis (Grit Matrix, Claude audit, etc.)
│  └─ Load skill: lab-books
├─ Working on the public website
│  └─ Read: firebase/CONTEXT.md
├─ Understanding experiment configs, results, or review docs
│  └─ Read: experiments/CONTEXT.md
├─ Debugging a script (which does what)
│  └─ Read: scripts/CONTEXT.md
├─ Running the full data pipeline (inventory → analyze → build)
│  └─ Read: scripts/CONTEXT.md (inventory.py, analyze_worktrees.py, build_data.py)
└─ General overview or first visit
   └─ Read: README.md (the full document)
```

## Key Glossary

| Term | Meaning |
|------|---------|
| **Grit** | Ground-Truth Integrity — correctness maintained under degraded input |
| **Perturbation** | Deliberate prompt degradation to stress-test model reasoning |
| **Manifold operators** | Push model off linguistic surface (vocab swap, framing shift, etc.) |
| **Semantic operators** | Probe reasoning coherence (false premises, contradictions, etc.) |
| **Basin** | Attractor basin — the solution space a model defaults to. Escape = divergence from baseline. |
| **Recovery** | Tokens burned returning to familiar patterns after perturbation |
| **Strategy archetype** | Conservative / Exploratory / Exploitative / Flailing (from basin + cost + correctness) |
| **Explanation Tax** | Overhead cost of narrated reasoning (Claude ~50%, DeepSeek ~3%) |
| **Game Report** | Markdown artifact summarizing a single experiment run's dynamics + cost + quality |

## Data Pipeline

```
opencode.db ──→ inventory.py refresh          ──→ inventory.json
       │
       ├──→ analyze_worktrees.py ──→ _results_summary.json ──┐
       │         │                                             │
/tmp/exp_* ──┘   ├──→ reports/*.md (game reports)            │
                 └──→ reports/*/session.jsonl                 │
                                       │                      │
                                       ↓                      ↓
                          analyze_trajectories.py      build_data.py
                                       │                      │
                                       ↓                      ↓
                          _trajectory_aggregate.json   firebase/public/data.js
```

## Project Map

| Directory | Contains | CONTEXT |
|-----------|----------|---------|
| `src/instrument/` | 16 Python modules — measurement apparatus | `src/instrument/CONTEXT.md` |
| `scripts/` | 25 scripts (24 `.py` + 1 `.sh`) — runners, analyzers, pipeline, 8 lab books | `scripts/CONTEXT.md` |
| `experiments/` | 34 YAML configs, results, 8 lab books, 6 reviews | `experiments/CONTEXT.md` |
| `firebase/` | Public website (7 HTML pages + data.js) | `firebase/CONTEXT.md` |
| `tests/` | pytest suite for adapter, perturb, pricing, recovery | — |
| `infrastructure/` | Test suite (4 modules), Docker Compose (Neo4j + ChromaDB) | — |
| `.opencode/skills/` | 3 opencode skills for common workflows | — |

## Quick Commands

```bash
python scripts/run.py --config experiments/configs/<name>.yaml    # Run experiment
python scripts/analyze_worktrees.py                               # Post-hoc analysis
python scripts/inventory.py list                                  # List experiments
python scripts/build_data.py                                      # Build website data.js
```
