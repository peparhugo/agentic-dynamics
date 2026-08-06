# AI FinOps Framework

<p align="center">
  <strong>The first open framework for measuring and predicting AI inference costs.</strong><br>
  Not a benchmark. An instrument — a calibrated measurement apparatus that probes how language models explore unfamiliar reasoning topologies, how they recover from perturbation, and what that costs.
</p>

<p align="center">
  <a href="https://ai-finops-rulebook.web.app"><img src="https://img.shields.io/badge/website-ai--finops--rulebook.web.app-%236366F1" alt="Website"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue" alt="License"></a>
  <a href="CONTRIBUTING.md"><img src="https://img.shields.io/badge/contributions-welcome-brightgreen" alt="Contributions"></a>
</p>

---

## The 30-Second Pitch

You're spending money on AI models. How do you know it's the *right* amount? Most teams measure cost per prompt — a metric that ignores pass rates, codebase growth compounding, and energy price inflation.

**This framework gives you a predictive equation.** Enter your assumptions — team size, velocity, energy scenario — and receive a cost projection, model selection rules, and an energy risk forecast. Every parameter is empirically grounded in 248 instrumented experiment sessions across 8 model variants and 3 architectures.

> *"Your AI bill is a black box. This framework opens it."* — The homepage

---

## The Five Rules

Each rule names a concept we measured. Each maps to a lever you control.

| # | Rule | What It Tells You |
|---|------|-------------------|
| 1 | **The Silent Inference Rule** | Default to the cheapest model that passes your tests. If it produces correct code without narration, route to it. |
| 2 | **The Explanation Tax Rule** | Narration has a measurable cost (24–120% more per session). Pay for it only when you need auditable reasoning. |
| 3 | **The Snowball Rule** | Codebase growth compounds quadratically through the N² term. Model the curve before architectural commitments. |
| 4 | **The EPM Horizon Rule** | Energy costs are the inflation rate of AI compute. Find the year your local energy prices flip your model selection. |
| 5 | **The Cost-Per-Pass Rule** | Price the outcome, not the prompt. A model at half the cost but half the pass rate costs the same per working outcome. |

---

## What's In This Repo

```
├── src/instrument/           # Python measurement apparatus
│   ├── perturb.py            # 10 perturbation operators (4 manifold, 6 semantic)
│   ├── trajectory.py         # Reasoning trajectory capture
│   ├── recovery.py           # Recovery classification (6 detection signals)
│   ├── recovery_cost.py      # Cost of recovering from perturbation
│   ├── basin.py              # Attractor basin escape measurement
│   ├── strategy.py           # Strategy archetype classification (4 types)
│   ├── efficiency.py         # Token / cost / energy efficiency measurement
│   ├── solution.py           # Solution quality evaluation
│   ├── constraint_detection.py   # Dual-signal constraint verification
│   ├── semantic_validation.py    # AST analysis, marker profiling
│   ├── game_report.py        # Markdown game report generation
│   ├── experiment.py         # Full experiment runner
│   ├── adapter.py            # LLM adapter instrumentation
│   ├── opencode.py           # Agentic session runner + JSONL parser
│   └── lab_book.py           # YAML-frontmatter markdown persistence
├── experiments/
│   ├── configs/              # 34 YAML experiment definitions
│   └── results/              # Experiment output (generated, not tracked)
├── scripts/
│   ├── run.py                # Single experiment runner
│   ├── batch_run.py          # Parallel batch experiments
│   ├── sweep_silent_mode.py  # Silent-mode Explanation Tax sweep
│   ├── sweep_parallel.py     # Parallel silent-mode sweep
│   ├── finish_sweep.py       # Resume incomplete sweep cells
│   ├── remaining_batch.py    # Sequential batch runner
│   ├── multi_phase.py        # Iterative multi-phase builds
│   ├── recovery_cost_table.py    # DB-based recovery cost analysis
│   ├── validate_session.py   # Post-hoc pytest validation
│   └── inventory.py          # Experiment/worktree inventory CLI
├── firebase/public/          # Website source (HTML/CSS/JS)
├── pyproject.toml            # Python package config
├── CONTRIBUTING.md           # How to contribute
└── CODE_OF_CONDUCT.md       # Community standards
```

---

## Quick Links

| Page | What |
|------|------|
| [The Framework](https://ai-finops-rulebook.web.app) | Rules, interactive calculator, decision framework |
| [The Story](https://ai-finops-rulebook.web.app/story.html) | How a $20 API key became this |
| [The Methodology](https://ai-finops-rulebook.web.app/methodology.html) | Experiment design and instrument architecture |
| [The Evidence](https://ai-finops-rulebook.web.app/evidence.html) | 186 worktrees, full AST analysis, all data |
| [The Roadmap](https://ai-finops-rulebook.web.app/roadmap.html) | Public research agenda, help-wanted items |

---

## By the Numbers

| Metric | Value |
|--------|-------|
| Experiment sessions | 248 |
| Worktrees analyzed | 251 |
| Models tested | 8 (3 architectures) |
| Experiment configs | 34 |
| Perturbation operators | 10 |
| Recovery signals | 6 |
| Strategy archetypes | 4 |
| Measured cost gap | 65× |
| Total experiment cost | $64.98 |
| Lines of generated code | 202,000+ |
| AST-verified Python files | 2,416 |

Run `python scripts/inventory.py list` for a live breakdown of all experiments, worktrees, and costs. Result files in `experiments/results/` are generated at runtime and not tracked in git — the inventory is the authoritative record.

---

## Installation

**Prerequisites:**
- Python 3.10+
- An [opencode](https://opencode.ai) installation (the CLI used to spawn agentic sessions)
- LLM API credentials (DeepSeek, OpenAI, or Anthropic)

```bash
git clone https://github.com/peparhugo/ai-finops-framework.git
cd ai-finops-framework
pip install -e .
```

---

## Usage

### Run a Single Experiment

```bash
python scripts/run.py --config experiments/configs/task_manager.yaml
```

This will:
1. Parse the YAML config
2. Generate perturbed prompts using the specified operators
3. Spawn an isolated opencode worktree with the perturbed prompt
4. Capture the full reasoning trajectory
5. Run multi-dimensional analysis (solution quality, basin escape, recovery classification, efficiency)
6. Save results to `experiments/results/{name}_{model}.json`

### Run a Batch

```bash
python scripts/batch_run.py
```

### Run a Silent-Mode Sweep

```bash
python scripts/sweep_silent_mode.py
```

This toggles the Explanation Tax on/off by controlling whether the model is allowed to externalize reasoning into billable tokens.

### Inspect the Inventory

```bash
# Rebuild inventory from all data sources
python scripts/inventory.py refresh

# List all experiments with model breakdown
python scripts/inventory.py list

# Show aggregate statistics
python scripts/inventory.py stats

# List worktrees and their sessions
python scripts/inventory.py worktrees

# Print numbers formatted for the evidence page
python scripts/inventory.py report
```

### Validate a Worktree

```bash
python scripts/validate_session.py /tmp/exp_xyz
```

Runs pytest in the worktree and reports pass/fail/error results.

---

## How It Works

### The Experiment Pipeline

```
Experiment Config (YAML)
  │
  ├─► Perturbation Engine (10 operators × 3 strengths)
  │     └─► Perturbed Prompts
  │
  ├─► Opencode Agentic Session
  │     ├─► Isolated worktree (/tmp/exp_*)
  │     ├─► Model receives (perturbed) prompt
  │     └─► Captures: full reasoning trace, tool calls, tokens, cost
  │
  ├─► Multi-Dimensional Analysis
  │     ├─► solution.py      → Correctness, constraints met, novelty
  │     ├─► efficiency.py    → Token/cost/energy efficiency
  │     ├─► basin.py         → Attractor basin escape score
  │     ├─► recovery.py      → 6-signal recovery classification
  │     ├─► strategy.py      → Archetype: Conservative/Exploratory/Wasteful/Efficient
  │     ├─► constraint_detection.py → Dual-signal constraint verification
  │     └─► recovery_cost.py → Recovery cost multiplier
  │
  └─► Results
        ├─► JSON (experiments/results/)
        └─► Markdown Game Reports (experiments/results/reports/)
```

### The Unified Cost Equation

Every parameter is measured empirically — none are theoretical.

```
C₀   = baseline session cost
P    = pass rate
ε    = Explanation Tax (narration overhead)
β    = context inflation rate
v    = velocity (lines generated per session)
EPM  = Energy Price Multiplier

Per session:  c(t) = C₀ × EPM(t) × (1 + β·v·t)
Cumulative:   C(N,v) = C₀ × EPM(N) × [N + β·v·N(N−1)/2]
Per outcome:  CostPerOutcome(K,v) = C(K/P, v) / K
```

### The 10 Perturbation Operators

**Manifold** (probe linguistic surface — test search dynamics):

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

## Current Scope & Roadmap

### v0.3 (Current)

- 8 models across Python/Flask REST APIs, CRUD apps, real-time collaboration frontends
- 10 prompt-level perturbation operators
- IEA-baseline linear EPM projection (1.6%/yr)
- Inference cost measurement (tokens, dollars, joules)

### v0.2+ (Help Wanted)

| Pillar | Description | Status |
|--------|-------------|--------|
| Multi-Language AST | TypeScript, Go, Rust, Java validation | 🟢 1/5 |
| Task Archetypes | Bug-fixing, refactoring, security hardening, ETL | 🟢 1/5 |
| Model Diversity | Gemini, Llama-4, Mistral validation | 🟡 2/6 |
| Structural Perturbations | Dependency injection, AST corruption, incident simulation | 🟢 1/5 |
| Maintenance Tax | 6-month code evolution, blind preference testing | 🔵 0/2 |

See the [full roadmap](https://ai-finops-rulebook.web.app/roadmap.html) and [CONTRIBUTING.md](CONTRIBUTING.md).

---

## Citation

If you use this framework in your research or decision-making:

```bibtex
@misc{ai-finops-framework-2026,
  title  = {The AI FinOps Framework: A Predictive Model for AI Inference Costs},
  author = {Hugo Pepar},
  year   = {2026},
  url    = {https://ai-finops-rulebook.web.app},
  note   = {v0.3. 248 experiment sessions, 8 models, 10 perturbation operators.}
}
```

---

## License

MIT — see [LICENSE](LICENSE). The instrument is model-agnostic. DeepSeek was chosen as the anchor case study, not an endorsement. The framework does not judge whether narration is "wasteful" or "valuable" — it measures the cost.
