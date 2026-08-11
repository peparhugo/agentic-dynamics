# Coding-Agent Economics Instrument

<p align="center">
  <strong>An open instrument measuring how coding-agent cost and verified outcome change as specification quality degrades.</strong><br>
  249 sessions, 10 perturbation operators, 8 model variants. $64.98 measured API spend.
</p>

<p align="center">
  <a href="https://ai-finops-rulebook.web.app"><img src="https://img.shields.io/badge/website-ai--finops--rulebook.web.app-%236366F1" alt="Website"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-Apache%202.0-blue" alt="License"></a>
</p>

---

## What This Is

A measurement instrument that deliberately degrades engineering specifications — missing constraints, false premises, contradictory requirements, alien vocabulary — then runs coding agents against them and measures:

- **Verified correctness** (agent-authored tests executed against generated artifacts)
- **Task economics** (actual billed cost, token breakdown, cache behavior)
- **Behavioral divergence** (structural escape from baseline solution patterns)

Most coding-agent benchmarks ask: can the model solve a clean task? This instrument asks: **what happens when the specification itself degrades?**

The approach: controlled perturbation as an experimental independent variable. Each of 10 operators applies a specific, repeatable degradation to the prompt before the coding agent sees it. The instrument captures the full execution trace, generated artifact, and cost telemetry.

---

## Three Key Findings

**1. Per-token price does not tell you task economics.**
Models produce similar generated token volumes yet bill at ratios driven by provider pricing architecture, not capability.

**2. Agent reliability changes differently as specification quality degrades.**
When specifications are corrupted, models exhibit materially different recovery behavior, output patterns, and cost trajectories. Grit (Ground-Truth Integrity) measures this: `G(s) = P(verified_success | perturbation_strength=s)`.

**3. Recovery itself has a cost signature.**
When a model succeeds under perturbation, the overhead is measurable — both as extra tokens and as retry/narration cost. Recovery premium varies by provider family and perturbation class.

---

## Operational Framework

Observed from the experiment corpus:

| Metric | Description |
|--------|-------------|
| Cost-per-task variation | Token pricing, cache write policies, and provider economics stack into cost gaps |
| Outcome retention under perturbation | Grit: `G(s) = P(verified_success \| perturbation_strength=s)` |
| Recovery overhead | Explanation Tax — tokens and cost burned returning to familiar patterns |

Derived metrics: WOC ratio (first-pass success), cost per verified outcome.

Modeling extensions: Snowball (N² codebase growth compounding), EPM (energy price projection), batch/cascade/SLA — modeled, not independently tested.

---

## By the Numbers

| Metric | Value |
|--------|-------|
| Experiment sessions | 249 |
| Game reports | 224 |
| Model variants | 8 (3 provider families) |
| Experiment configs | 34 |
| Perturbation operators | 10 (specification corruption, objective mutation, process perturbation) |
| Total experiment cost | $64.98 |

---

## Related Work

- [Databricks coding-agent benchmark](https://www.databricks.com/blog/benchmarking-coding-agents-databricks-multi-million-line-codebase) (July 2026) — enterprise-scale coding-agent evaluation using held-out tests
- [FinOps Foundation: AI tools & services](https://www.finops.org/wg/finops-for-ai-tools-services-considerations/) — use-case economics and model right-sizing

Run `python scripts/inventory.py list` for a live breakdown.

---

## Repository Structure

```
├── src/instrument/           # Python measurement apparatus
│   ├── perturb.py            # 10 perturbation operators
│   ├── basin.py              # Attractor basin escape measurement
│   ├── efficiency.py         # Token / cost / energy efficiency
│   ├── solution.py           # Solution quality evaluation
│   ├── strategy.py           # Strategy archetype classification
│   ├── recovery.py           # Recovery classification (6 signals)
│   ├── recovery_cost.py      # Cost of recovering from perturbation
│   ├── trajectory.py         # Reasoning trajectory capture
│   ├── constraint_detection.py   # Dual-signal constraint verification
│   ├── semantic_validation.py    # AST analysis, marker profiling
│   ├── game_report.py        # Markdown game report generation
│   ├── experiment.py         # Full experiment runner
│   ├── adapter.py            # LLM adapter instrumentation
│   ├── opencode.py           # Opencode session runner
│   └── lab_book.py           # YAML-frontmatter persistence
├── scripts/
│   ├── analyze_worktrees.py  # Post-hoc analysis → game reports
│   ├── analyze_trajectories.py   # 255 session.jsonl transcripts
│   ├── build_data.py         # Generate data.js for the website
│   ├── inventory.py          # Experiment/worktree inventory CLI
│   ├── lab_claude_audit.py   # Lab 1: Claude cost breakdown
│   ├── lab_grit_matrix.py    # Lab 2: Grit Matrix chart data
│   ├── lab_correctness_premium.py # Lab 3: Head-to-head correctness
│   ├── lab_flail_triggers.py # Lab 4: Narration failure patterns
│   ├── lab_tool_archetypes.py    # Lab 5: Write vs patch vs bash
│   ├── lab_task_routing.py   # Lab 6: Optimal model routing
│   ├── lab_basin_topology.py # Lab 7: Attractor basin classification
│   ├── lab_survival_horizon.py   # Lab 8: Sessions-to-bankruptcy
│   ├── run.py                # Single experiment runner
│   └── ...
├── experiments/
│   ├── configs/              # 34 YAML experiment definitions
│   ├── results/              # Game reports, summaries, lab outputs
│   └── lab_books/            # 13 structured experiment plans
├── firebase/public/          # Website source (8 pages, data pipeline)
├── pyproject.toml
├── CONTRIBUTING.md
└── CODE_OF_CONDUCT.md
```

---

## The Data Pipeline

The website at [ai-finops-rulebook.web.app](https://ai-finops-rulebook.web.app) is powered by a live data pipeline:

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
                          _trajectory_aggregate.json   firebase/public/data.js (~31KB)
```

All numbers on the website are live-generated. Every measurement is provenance-tagged: [M] measured, [C] computed, [H] heuristic, [X] external.

---

## Quick Links

| Page | What |
|------|------|
| [Home](https://ai-finops-rulebook.web.app) | The diagnosis + Databricks validation |
| [The Framework](https://ai-finops-rulebook.web.app/framework.html) | 10 rules, levers, interactive calculator, provider playbook |
| [The Evidence](https://ai-finops-rulebook.web.app/evidence.html) | Grit spectrum, cost ranking, AST analysis, perturbation response |
| [The Story](https://ai-finops-rulebook.web.app/story.html) | How a $20 API key became this |
| [The Methodology](https://ai-finops-rulebook.web.app/methodology.html) | Experiment design, perturbation operators, recovery signals |
| [The Accelerator](https://ai-finops-rulebook.web.app/accelerator.html) | Enterprise bridge, maturity ladder, projections, autonomous workloads |
| [Databricks Comparison](https://ai-finops-rulebook.web.app/databricks.html) | Mapping every Databricks claim to calibrated measurements |

---

## Installation

**Prerequisites:** Python 3.10+, [opencode](https://opencode.ai) CLI, LLM API credentials.

```bash
git clone https://github.com/peparhugo/ai-finops-framework.git
cd ai-finops-framework
pip install -e .
```

**Note:** The core library (`src/instrument/`) is pip-installable. The scripts in `scripts/` are analysis tools that depend on your local opencode installation and experiment data.

---

## Usage

### Run a Single Experiment

```bash
python scripts/run.py --config experiments/configs/task_manager.yaml
```

### Run Post-Hoc Analysis

```bash
# Analyze all worktrees → game reports + _results_summary.json
python scripts/analyze_worktrees.py
python scripts/analyze_worktrees.py --no-tests   # Skip pytest (faster)
python scripts/analyze_worktrees.py --worktree /tmp/exp_xyz  # Single worktree

# Analyze session transcripts
python scripts/analyze_trajectories.py

# Build website data
python scripts/build_data.py
```

### Inspect the Inventory

```bash
python scripts/inventory.py refresh    # Rebuild from DB + worktrees
python scripts/inventory.py list       # List experiments
python scripts/inventory.py stats      # Aggregate statistics
python scripts/inventory.py report     # Evidence page numbers
```

### Run Lab Book Analyses

```bash
python scripts/lab_claude_audit.py     # Claude cost breakdown
python scripts/lab_grit_matrix.py      # Grit Matrix chart data
python scripts/lab_correctness_premium.py  # Head-to-head correctness
python scripts/lab_flail_triggers.py   # Narration failure patterns
python scripts/lab_tool_archetypes.py  # Write vs patch vs bash
python scripts/lab_task_routing.py     # Optimal model routing
python scripts/lab_basin_topology.py   # Attractor basin classification
python scripts/lab_survival_horizon.py # Sessions-to-bankruptcy
```

---

## The 10 Perturbation Operators

**Manifold** (push model off linguistic surface — test search dynamics):

| Operator | What It Does |
|----------|--------------|
| Inject Alien Vocabulary | Replace domain terms with unrelated field vocabulary |
| Shift Framing | Reframe from "build this" to "find the flaws in this" |
| Reverse Causality | Present solution before the problem |
| Force Abandonment | Force generation and discard of solutions |

**Semantic** (probe reasoning coherence — test truth-seeking):

| Operator | What It Does |
|----------|--------------|
| Inject False Premise | Insert a plausible but incorrect assumption |
| Invert Constraint | Flip a requirement to its opposite |
| Insert Contradiction | Place two mutually exclusive requirements |
| Remove Critical Constraint | Silently drop a defining requirement |
| Inject Phantom Success | Assert an intermediate step passed when it hasn't |
| Inject Competing Goal | Add a conflicting requirement |

---

## Current Scope

**Validated:** Python/Flask REST APIs, CRUD apps, real-time collaboration frontends, TypeScript/Node.js (21 cross-model runs). 10 prompt-level perturbation operators. IEA-baseline energy projection (1.6%/yr). Cost measurement in tokens, dollars, and joules.

**In progress:** Rust, Go validation. Structural perturbation operators (dependency injection, AST corruption). Multi-language AST expansion.

**Not in scope:** The framework measures cost — it does not judge whether narration is "wasteful" or "valuable." The instrument is model-agnostic. DeepSeek was chosen as the anchor case study, not an endorsement.

---

## Citation

```bibtex
@misc{ai-finops-framework-2026,
  title  = {The AI FinOps Framework: A Predictive Model for AI Inference Costs},
  author = {Hugo Pepar},
  year   = {2026},
  url    = {https://ai-finops-rulebook.web.app},
  note   = {v0.4. 249 experiment sessions, 8 models, 10 perturbation operators.}
}
```

---

## License

Apache 2.0 — see [LICENSE](LICENSE).
