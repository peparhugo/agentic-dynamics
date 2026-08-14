# Agentic Dynamics

<p align="center">
  <strong>Success isn't value. An experimental instrument measuring what drives the cost and value of agentic AI outcomes.</strong><br>
  1,097 story sessions, 10 perturbation operators, 7 model variants across 3 providers. $288.69 measured spend.
</p>

<p align="center">
  <a href="https://ai-finops-rulebook.web.app"><img src="https://img.shields.io/badge/website-Agentic%20Dynamics-%236366F1" alt="Website"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-Apache%202.0-blue" alt="License"></a>
</p>

---

## What This Is

**Agentic Dynamics is the empirical study of how AI agents behave, adapt, interact, recover, and produce outcomes across changing tasks, environments, workflows, and time.**

Economics, verification, recovery, resilience, behavior, coordination, and governance are dimensions and research areas within Agentic Dynamics. This repository currently measures a bounded subset through coding-agent experiments; it does not yet claim broad evidence about swarms or organizational outcomes.

A measurement instrument that deliberately degrades engineering specifications — missing constraints, false premises, contradictory requirements, alien vocabulary — then runs coding agents against them and measures the full chain:

- **Decisions made** (observable execution trace: tool calls, file operations, reasoning)
- **Correctness evidence** (agent-authored tests executed against generated artifacts)
- **Task economics** (actual billed cost, token breakdown, cache behavior)
- **Behavioral divergence** (structural escape from baseline solution patterns)

Most coding-agent benchmarks ask: can the model solve a clean task? This instrument asks: **does your AI assistant make your system better, or just bigger?**

The approach: controlled perturbation as an experimental independent variable. Each of 10 operators applies a specific, repeatable degradation to the prompt before the coding agent sees it. The instrument captures the full execution trace, generated artifact, and cost telemetry.

---

## Key Findings

**1. Per-token price does not tell you task economics.**
Models produce similar generated token volumes yet bill at ratios driven by provider pricing architecture, not capability.

**2. Agent reliability changes differently as specification quality degrades.**
When specifications are corrupted, models exhibit materially different recovery behavior, output patterns, and cost trajectories. Grit (Ground-Truth Integrity) measures this: `G(s) = P(test_executed_success | perturbation_strength=s)`.

**3. Recovery itself has a cost signature.**
When a model succeeds under perturbation, the overhead is measurable — both as extra tokens and as retry/narration cost. Recovery premium varies by provider family and perturbation class.

**4. Success isn't value.**
An agent can pass its own tests at low cost while making architectural decisions that increase future maintenance burden. The instrument captures correctness evidence; the FinOps question is whether each outcome increases or decreases the system's durable value.

---

## Observed Dynamics

Observed from the experiment corpus:

| Metric | Description |
|--------|-------------|
| Cost-per-task variation | Token pricing, cache write policies, and provider economics stack into cost gaps |
| Outcome retention under perturbation | Grit: `G(s) = P(test_executed_success \| perturbation_strength=s)` |
| Recovery overhead | Explanation Tax — tokens and cost burned returning to familiar patterns |

Derived metrics: WOC ratio (first-pass success), cost per test-executed outcome, AI Value Efficiency (durable outcome value / total cost).

Modeling extensions: Snowball (N² codebase growth compounding), EPM (energy price projection), batch/cascade/SLA — modeled, not independently tested.

---

## By the Numbers

| Metric | Value |
|--------|-------|
| Story sessions | 1,097 (3,370 DB sessions total) |
| Game reports | 224 |
| Model variants | 7 (3 providers: DeepSeek, Anthropic, OpenAI) |
| Experiment configs | 35 (34 task definitions + pipeline plan) |
| Perturbation operators | 10 (specification corruption, objective mutation, process perturbation) |
| Lab books | 21 (19 active scripts, 8 deprecated) |
| Total measured spend | $288.69 |

---

## Related Work

- [Databricks coding-agent benchmark](https://www.databricks.com/blog/benchmarking-coding-agents-databricks-multi-million-line-codebase) (July 2026) — enterprise-scale coding-agent evaluation using held-out tests
- [FinOps Foundation: AI tools & services](https://www.finops.org/wg/finops-for-ai-tools-services-considerations/) — use-case economics and model right-sizing

Run `python scripts/inventory.py stats` for a live breakdown.

---

## Repository Structure

```
├── src/instrument/           # Python measurement apparatus (pip-installable, 40 modules)
│   ├── perturb.py            # 10 perturbation operators
│   ├── opencode.py           # opencode session runner (the primary backend)
│   ├── backends.py           # backend routing: opencode vs Claude CLI
│   ├── claude_adapter.py     # Claude CLI (stream-json) → opencode events
│   ├── streaming.py          # shared line-by-line subprocess runner
│   ├── trajectory.py         # reasoning trajectory capture
│   ├── solution.py           # solution quality evaluation
│   ├── basin.py              # attractor basin escape measurement
│   ├── efficiency.py         # token / cost / energy efficiency
│   ├── recovery.py           # recovery classification (7 signals)
│   ├── recovery_cost.py      # cost of recovering from perturbation
│   ├── strategy.py           # strategy archetype classification
│   ├── constraint_detection.py   # dual-signal constraint verification
│   ├── semantic_validation.py    # AST analysis, marker profiling
│   ├── game_report.py        # markdown game report generation
│   ├── language.py           # multi-language tree-sitter parsing (Py/TS/Go/Rust)
│   ├── sonar.py              # SonarQube static analysis
│   ├── embeddings.py         # embeddings + vector search (ChromaDB/Ollama)
│   ├── graph.py              # Neo4j experiment knowledge graph
│   ├── story.py              # multi-session story orchestrator
│   ├── mutation.py           # semantic spec/code mutation compiler
│   ├── commit_analysis.py    # per-commit AST/Sonar/convention analysis
│   ├── review.py             # LLM code review pool
│   ├── entropy.py            # architectural entropy
│   ├── codebase_graph.py     # import-graph structural metrics
│   ├── lsp_diagnostics.py    # language-server diagnostics
│   ├── supervisor.py         # Redis flag/session↔cell contracts (observe-only)
│   ├── workflow_runner.py    # agent_task workflow executor (the execute phase)
│   ├── test_runner.py        # independent pytest/jest/go/cargo runner
│   ├── routing.py            # per-task model routing + strategy simulation
│   ├── signal_store.py       # per-step routing signal store
│   ├── step_routing.py       # per-step model routing
│   ├── live.py               # Redis pub/sub telemetry
│   ├── experiment_spec.py    # ExperimentSpec dataclasses + YAML loader
│   ├── compile_experiment.py # spec → DAG compiler (the cycle)
│   ├── experiment.py         # [deprecated] full experiment runner
│   ├── adapter.py            # [deprecated] LLM adapter instrumentation
│   └── lab_book.py           # [deprecated] YAML-frontmatter persistence
├── scripts/                  # 78 scripts: runners, analysis, labs, queue, admin
│   ├── run.py                # single experiment runner
│   ├── run_story.py          # multi-session story runner
│   ├── pipeline.py           # YAML-driven phase orchestration (ci/deploy/...)
│   ├── enqueue.py / worker.py / monitor.py   # Redis queue transport
│   ├── analyze_worktrees.py  # post-hoc analysis → game reports
│   ├── analyze_trajectories.py  # session transcript parsing
│   ├── sync_data.py          # story results → parquet
│   ├── build_data.py         # generate data.js for the website
│   ├── inventory.py          # experiment/worktree inventory CLI
│   ├── lab_*.py              # 19 active lab books (+ 8 deprecated)
│   └── ...
├── experiments/
│   ├── configs/              # 35 YAML experiment definitions
│   ├── specs/                # ExperimentSpec YAMLs (spec/compiler layer)
│   ├── stories/              # story result JSONs
│   ├── codebases/            # starter codebases per language
│   ├── results/              # game reports, summaries, lab outputs
│   ├── lab_books/            # 21 experiment plans
│   └── reviews/              # 6 peer review documents
├── firebase/public/          # website source (8 pages, data pipeline)
├── admin/                    # Control Room portal (Flask + static dashboard)
├── docs/                     # design docs, specs, review records
├── code_reviews/             # dated architecture/design review records
├── .opencode/                # opencode agents, skills, tools, instructions
├── .claude/                  # parallel Claude Code surface (ported from opencode)
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
       │         │                                            │
/tmp/exp_* ──┘   ├──→ reports/*.md (game reports)            │
                 └──→ reports/*/session.jsonl                │
                                       │                     │
                                       ↓                     ↓
                           analyze_trajectories.py    sync_data.py (stories → parquet)
                                       │                     │
                                       ↓                     ↓
                           _trajectory_aggregate.json  build_data.py
                                                                │
                                                                ↓
                                                   firebase/public/data.js (~179KB)
```

All numbers on the website are live-generated. Every measurement is provenance-tagged: [M] measured, [C] computed, [H] heuristic, [X] external.

---

## Quick Links

| Page | What |
|------|------|
| [Home](https://ai-finops-rulebook.web.app) | The instrument + key findings |
| [The Instrument](https://ai-finops-rulebook.web.app/methodology.html) | Experiment design, perturbation operators, recovery signals |
| [The Evidence](https://ai-finops-rulebook.web.app/evidence.html) | Grit spectrum, cost ranking, AST analysis, perturbation response |
| [Operational Framework](https://ai-finops-rulebook.web.app/framework.html) | 10 principles, levers, interactive calculator, provider playbook |
| [The Story](https://ai-finops-rulebook.web.app/story.html) | How a $20 API key became this |
| [Related Work](https://ai-finops-rulebook.web.app/databricks.html) | Databricks benchmark, FinOps Foundation |

---

## Installation

**Prerequisites:** Python 3.10+, [opencode](https://opencode.ai) CLI, LLM API credentials.

```bash
git clone https://github.com/peparhugo/agentic-dynamics.git
cd agentic-dynamics
pip install -e .
```

**Note:** The core library (`src/instrument/`) is pip-installable. The scripts in `scripts/` are analysis tools that depend on your local opencode installation and experiment data.

---

## Usage

### Run a Single Experiment

```bash
python scripts/run.py experiments/configs/task_manager.yaml
python scripts/run.py experiments/configs/task_manager.yaml --model deepseek/deepseek-v4-pro
python scripts/run.py experiments/configs/task_manager.yaml --backend claude_cli
```

### Run a Multi-Session Story

```bash
python scripts/run_story.py task_manager_api --model deepseek/deepseek-v4-pro --condition clean
```

### Run the Pipeline (YAML-driven phases)

```bash
python scripts/pipeline.py --plan ci          # lint → test → build
python scripts/pipeline.py --plan full_matrix # matrix → analyze → review → deploy
```

### Parallel Queue Transport

```bash
python scripts/enqueue.py --model deepseek/deepseek-v4-flash --missing-only
python scripts/worker.py        # run N workers in parallel
python scripts/monitor.py       # queue dashboard
```

### Run Post-Hoc Analysis

```bash
python scripts/analyze_worktrees.py                  # → game reports + _results_summary.json
python scripts/analyze_trajectories.py               # → trajectory aggregates
python scripts/sync_data.py                          # story results → parquet
python scripts/build_data.py                         # → firebase/public/data.js
```

### Inspect the Inventory

```bash
python scripts/inventory.py refresh    # rebuild from DB + worktrees
python scripts/inventory.py list       # list experiments
python scripts/inventory.py stats      # aggregate statistics
python scripts/inventory.py report     # evidence page numbers
```

### Run Lab Book Analyses

```bash
python scripts/lab_grit_matrix.py         # Grit Matrix chart data
python scripts/lab_correctness_premium.py # head-to-head correctness
python scripts/lab_flail_triggers.py      # failure patterns
python scripts/lab_task_routing.py        # optimal model routing
python scripts/lab_survival_horizon.py    # sessions-to-bankruptcy
# ...and 14 more — see scripts/CONTEXT.md
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

## The Spec / Compiler Layer

The library is transitioning from a linear pipeline to a closed loop (see
`code_reviews/2026-08-14_experiment-spec-and-compiler-design.md`):

```
spec (ExperimentSpec) ──compile──▶ DAG ──▶ cells ──▶ jobs ──▶ attempts
      ▲                                          │              │
      └──adapt (tweak one factor)── compare ◀── information ◀── measure ◀── ledger
```

The load-bearing rule: **to make policies, we need information.** Measurement rules
produce information; control rules consume it. The compiler refuses a control rule
(like `model_cascade`/`dynamics`) whose `requires` (e.g. `confidence`) are not yet
instrumented. `experiment_spec.py` and `compile_experiment.py` are written; the open
gap is instrumenting `confidence`, `perturbation_strength`, and `test_executed_success`
before authoring the policy arms that consume them.

---

## Current Scope

**Validated:** Python/Flask REST APIs, CRUD apps, real-time collaboration frontends, and TypeScript/Node.js. Go and Rust configs are defined and under validation. 10 prompt-level perturbation operators. IEA-baseline energy projection (1.6%/yr). Cost measurement in tokens, dollars, and joules. Multi-session story orchestration, independent test execution, and a Redis-queue parallel transport.

**In progress:** The spec/compiler campaign loop (adapt → next grid) and the policy arms gated on instrumenting `confidence` / `perturbation_strength` / `test_executed_success`.

**Not in scope:** The instrument measures cost — it does not judge whether narration is "wasteful" or "valuable." The instrument is model-agnostic. DeepSeek was chosen as the anchor case study, not an endorsement.

---

## Citation

```bibtex
@misc{agentic-dynamics-2026,
  title  = {Agentic Dynamics: An experimental instrument for the economics of agentic AI},
  author = {Hugo Pepar},
  year   = {2026},
  url    = {https://ai-finops-rulebook.web.app},
  note   = {1,097 story sessions, 7 models, 10 perturbation operators.}
}
```

---

## License

Apache 2.0 — see [LICENSE](LICENSE).
