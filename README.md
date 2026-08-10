# AI FinOps Framework

<p align="center">
  <strong>Grit = Ground-Truth Integrity. An open framework for measuring and governing AI inference costs.</strong><br>
  Not a benchmark. Not a cost tracker. A calibrated measurement instrument backed by 227 stress tests across 8 models.
</p>

<p align="center">
  <a href="https://ai-finops-rulebook.web.app"><img src="https://img.shields.io/badge/website-ai--finops--rulebook.web.app-%236366F1" alt="Website"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-Apache%202.0-blue" alt="License"></a>
  <a href="https://ai-finops-rulebook.web.app/databricks.html"><img src="https://img.shields.io/badge/independently%20arrived%20at-Databricks%20conclusions-%2306B6D4" alt="Databricks"></a>
</p>

---

## What This Is

On August 7, 2026, Databricks published their playbook for reducing AI coding costs at scale — arriving at the same four conclusions through surveys of Stripe, Coinbase, Uber, and Ramp. We arrived at the same conclusions independently through **227 controlled stress tests** across 8 models and 3 architectures.

They call the core concept the **Efficiency Frontier.** We call it **Grit (Ground-Truth Integrity):** how well a model maintains correctness when given degraded, contradictory, or incomplete instructions.

Both models produce ~11,000 generated tokens per session. Same computational effort. One costs **$0.016.** The other costs **$1.08.** That's a **69× gap** on comparable output. DeepSeek produces 1.26× more code per session (713 vs 568 LOC) at 88.7% correctness vs Claude's 88%.

This framework provides the calibrated measurements, governance rules, and reproducible methodology behind those numbers.

---

## The 10 Rules

| # | Rule | What It Tells You |
|---|------|-------------------|
| 1 | **Grit (Ground-Truth Integrity)** | Default to models that maintain correctness under degraded input. If a model flails — producing zero code — it has low Grit. |
| 2 | **The Explanation Tax** | Rule 1 selects models that CAN code. Rule 2 measures what resilience COSTS. Measured: Claude flails on 11% of sessions (zero code), 8.5% narration penalty when successful. DeepSeek: 8% flail, 0.0% penalty. |
| 3 | **The Snowball Rule** | Codebase growth compounds quadratically (N²). Model the curve before architectural commitments. |
| 4 | **The EPM Horizon Rule** | Energy costs are the inflation rate of AI compute. Find the year your local prices flip your model selection. |
| 5 | **The First-Pass Rule** | Price the outcome, not the prompt. WOC = 1/(1+r). Track by task type, model, and time of day. |
| 6 | **The Batch Discount** | Batch processing is 50% cheaper. 72-hour horizon. Measure queue depth. |
| 7 | **The Budget Ceiling** | Max jobs/day = Budget / (Cost × (1 + retry_rate)). Throughput is budget-constrained, not infra-constrained. |
| 8 | **The Cascade Rule** | Failures auto-escalate through model tiers. Design for <1% escalation to human. |
| 9 | **The SLA Buffer** | Batch completion = queue depth × avg time + retry buffer. Never batch within 2× queue depth of SLA. |
| 10 | **The Outcome Multiplier** | Maximize outcomes per dollar. BVI = Total Successful Outcomes / Total AI + Human Cost. |

---

## By the Numbers

| Metric | Value |
|--------|-------|
| Experiment sessions | 249 |
| Worktrees analyzed | 251 |
| Game reports | 224 |
| Models tested | 8 (3 architectures) |
| Experiment configs | 34 |
| Perturbation operators | 10 (4 manifold, 6 semantic) |
| Recovery signals | 6 |
| Strategy archetypes | 4 |
| Measured cost gap | 69× |
| Total experiment cost | $64.98 |
| Session transcripts analyzed | 255 |
| Lab books completed | 13 |

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
│   └── lab_books/            # 8 structured experiment plans
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
