---
status: accepted
---

# Agentic Dynamics

<p align="center">
  <strong>A research operating system for agent experimentation and control.</strong><br>
  Six cooperating systems — measurement, experimentation, execution, knowledge, control,
  publication — for studying how AI agents behave, adapt, recover, and produce value under change.
</p>

<p align="center">
  <a href="https://ai-finops-rulebook.web.app"><img src="https://img.shields.io/badge/website-Agentic%20Dynamics-%236366F1" alt="Website"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-Apache%202.0-blue" alt="License"></a>
</p>

---

## What This Is

**Agentic Dynamics is the empirical study of how AI agents behave under change — measured as
business outcomes.** The repository is a *research operating system*: six cooperating systems,
not a single tool. The perturbation instrument is **one** of the six.

> **AI agents don't have a price — they have dynamics.** Cost, reliability, and debt are
> properties of how the agent behaves under change, and we measured them.

1,027 story sessions, 10 perturbation operators, 7 model variants across 3 providers. $309.17
story-corpus measured spend.

---

## The Six Systems

| System | What it is |
|---|---|
| **1. Measurement apparatus** | The perturbation instrument: 10 operators degrade engineering specifications (missing constraints, false premises, contradictory requirements, alien vocabulary), then the full chain — decisions, correctness evidence, task economics, behavioral divergence — is measured. It asks: *does your AI assistant make your system better, or just bigger?* |
| **2. Experiment platform** | `ExperimentSpec` + the `requires`/`produces` gate: `spec → compile → DAG → cells → jobs → attempts → ledger → information → policy → grid → campaign`. **To make policies, we need information** — the compiler refuses a control rule whose inputs aren't yet measured. |
| **3. Agent execution runtime** | The opencode + Claude CLI backends, the workflow runner (phase execution inside a git worktree), the independent test runner, and the multi-session story orchestrator. |
| **4. Knowledge & augmentation** | The runtime-RAG knowledge base: canonical identity/authority, the nine ingestion producers, deterministic retrieval, and the `retrieve → construct → render` prompt-construction seam. |
| **5. Control** | The implemented control plane — per-task/per-step model routing (`routing.py`, `step_routing.py`), the fact plane (`facts.py` + the reducers: spec-status, attempt/job/workflow/policy/story/pattern facts), the context compiler (`context_compiler.py`), the shadow-mode controller + validator (`rules.py`, `validator.py`, `decisions.py`), the observe-only supervisor, Redis telemetry, and queue steering. Consumed by live campaigns (cap_2a/2b, cap_escalation_measurement, cap_session_routing_*). The "telemetry up, decisions down" seam. |
| **6. Research & publication** | Game reports, the cross-model review pool, and the publication surface — the website (provenance-tagged live data) and the Control Room portal. |

The dependency direction is enforced by a lint (`tests/test_dependency_direction.py`): `core ←
experiment/measurement/runtime/knowledge ← control ← apps`. See [`ARCHITECTURE.md`](ARCHITECTURE.md)
— the single architectural authority — and the `agentic-dynamics` CLI for the command surface.

---

## Key Findings

**1. Per-token price does not tell you task economics.**
Models produce similar generated token volumes yet bill at ratios driven by provider pricing
architecture, not capability.

**2. Agent reliability changes differently as specification quality degrades.**
When specifications are corrupted, models exhibit materially different recovery behavior, output
patterns, and cost trajectories. Grit (Ground-Truth Integrity) measures this:
`G(s) = P(test_executed_success | perturbation_strength=s)`.

**3. Recovery itself has a cost signature.**
When a model succeeds under perturbation, the overhead is measurable — both as extra tokens and
as retry/narration cost. Recovery premium varies by provider family and perturbation class.

**4. Success isn't value.**
An agent can pass its own tests at low cost while making architectural decisions that increase
future maintenance burden. The instrument captures correctness evidence; the FinOps question is
whether each outcome increases or decreases the system's durable value.

---

## Observed Dynamics

Observed from the experiment corpus:

| Metric | Description |
|--------|-------------|
| Cost-per-task variation | Token pricing, cache write policies, and provider economics stack into cost gaps |
| Outcome retention under perturbation | Grit: `G(s) = P(test_executed_success \| perturbation_strength=s)` — measured by `scripts/lab_grit.py`; this is the **only** meaning of Grit in the repo |
| Recovery overhead | Output decomposition — tokens and cost burned returning to familiar patterns |

Derived metrics: WOC ratio (first-pass success), cost per test-executed outcome, AI Value
Efficiency (durable outcome value / total cost).

---

## By the Numbers

| Metric | Value |
|--------|-------|
| Story sessions | 1,027 (6,333 DB sessions total) |
| Game reports | 348 |
| Model variants | 7 (3 providers: DeepSeek, Anthropic, OpenAI) |
| Experiment configs | 0 |
| Experiment + workflow specs | 170 (11 experiments + 159 workflows) |
| Perturbation operators | 10 (specification corruption, objective mutation, process perturbation) |
| Lab books | 20 (8 canonical + 12 quarantined) |
| Story-corpus measured spend | $309.17 |

These figures are the canonical public dataset: they mirror the `public_statistics`
block of `apps/website/data.js` (story sessions = canonical resolved story corpus; the spec
count = the generated lifecycle index `experiments/specs/index.json`; spend = the story
corpus's total measured cost). The spend figure is **story-corpus scoped**: workflow-run
ledger spend is not published (the run ledgers under `experiments/results/workflows/` are
gitignored, local-transient), so it must never be read as the whole-repo total. The DB
session total (6,333) is the broader raw session count from the opencode database, reported
separately from the 1,027 canonical story sessions.

---

## Repository Structure

```
├── src/agentic_dynamics/    # the modular monorepo — 8 bounded planes
│   ├── core/                # foundation: language, paths, session vocabulary, streaming
│   ├── experiment/          # ExperimentSpec + requires/produces gate + spec→DAG compiler
│   ├── measurement/         # the measurement apparatus (perturb, solution, basin, entropy, …)
│   ├── runtime/             # workflow runner, independent test runner, story orchestrator
│   ├── adapters/            # opencode + Claude CLI backends
│   ├── knowledge/           # identity/authority, retrieval, the nine ingestion producers, RAG
│   ├── control/             # routing, supervisor, telemetry, queue steering
│   └── reporting/           # game reports, review pool, analyzers
├── scripts/                 # 72 command scripts (37 maintained, 20 lab books, 15 archived)
├── experiments/             # definitions/ (specs + configs), campaigns/, results/
├── workflows/               # repository/, operations/, research/, examples/
├── apps/                    # the applications (consume the system, contain no domain rules)
│   ├── control_room/        # the Control Room portal (Flask + static dashboard)
│   └── website/             # the public website source (provenance-tagged data pipeline)
├── agent_config/            # the single instruction source → generates .opencode/ + .claude/
└── docs/                    # ARCHITECTURE.md (authority), designs, review records
```

---

## The Data Pipeline

The website at [ai-finops-rulebook.web.app](https://ai-finops-rulebook.web.app) is powered by a
live data pipeline:

```
opencode.db ──→ inventory.py refresh ──→ inventory.json

/tmp/exp_* ──→ analyze_worktrees.py ──→ reports/*.md (game reports)
              └──→ reports/*/session.jsonl ──→ analyze_trajectories.py ──→ _trajectory_aggregate.json

stories/*.json ──→ sync_data.py ──→ sessions.parquet + stories.parquet

canonical registry (data_manifest.json) + lab books + inventory.json
              ──→ build_data.py ──→ apps/website/data.js
```

All numbers on the website are live-generated. Every measurement is provenance-tagged: [M]
measured, [C] computed, [H] heuristic, [X] external.

---

## Quick Links

| Page | What |
|------|------|
| [Home](https://ai-finops-rulebook.web.app) | The field + key findings |
| [The Instrument](https://ai-finops-rulebook.web.app/methodology.html) | Experiment design, perturbation operators, recovery signals |
| [The Evidence](https://ai-finops-rulebook.web.app/evidence.html) | Grit spectrum, cost ranking, AST analysis, perturbation response |
| [Operational Framework](https://ai-finops-rulebook.web.app/framework.html) | Dynamics → business outcomes, levers, provider playbook |
| [The Story](https://ai-finops-rulebook.web.app/story.html) | How a $20 API key became this |
| [Related Work](https://ai-finops-rulebook.web.app/databricks.html) | Databricks benchmark, FinOps Foundation |

---

## Installation

**Prerequisites:** Python 3.10+, [opencode](https://opencode.ai) CLI, LLM API credentials.

```bash
git clone https://github.com/peparhugo/agentic-dynamics.git
cd agentic-dynamics
pip install -e .                  # installs the agentic_dynamics package + the agentic-dynamics CLI
```

The core library is `agentic_dynamics/` (pip-installable). The scripts in `scripts/` are analysis
tools that depend on your local opencode installation and experiment data.

---

## Usage

One entry point — `agentic-dynamics` (a thin dispatcher over the maintained `scripts/`):

```bash
agentic-dynamics experiment run task_manager.yaml --model deepseek/deepseek-v4-pro
agentic-dynamics story run task_manager_api --model deepseek/deepseek-v4-pro --condition clean
agentic-dynamics workflow run experiments/definitions/<spec>.yaml --goal "…"
agentic-dynamics queue enqueue --model deepseek/deepseek-v4-flash --missing-only
agentic-dynamics queue worker && agentic-dynamics queue monitor
agentic-dynamics analyze worktrees                 # → game reports
agentic-dynamics data build                        # → apps/website/data.js
agentic-dynamics analyze lab grit                  # → G(s), the formal Grit metric
agentic-dynamics spec status                       # → regenerated spec index
```

The full subcommand tree: `agentic-dynamics --help`; the per-script reference: `scripts/CONTEXT.md`.
The backing scripts can also be run directly (`python scripts/<script>.py …`).

---

## The 10 Perturbation Operators

**Specification corruption** (push model off the linguistic surface — test search dynamics):

| Operator | What It Does |
|----------|--------------|
| Inject Alien Vocabulary | Replace domain terms with unrelated field vocabulary |
| Shift Framing | Reframe from "build this" to "find the flaws in this" |
| Reverse Causality | Present solution before the problem |
| Force Abandonment | Force generation and discard of solutions |

**Objective mutation** (probe reasoning coherence — test truth-seeking):

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

The library has moved from a linear pipeline to a closed loop (see
[`docs/architecture/current/2026-08-14_experiment-spec-and-compiler-design.md`](docs/architecture/current/2026-08-14_experiment-spec-and-compiler-design.md)):

```
spec (ExperimentSpec) ──compile──▶ DAG ──▶ cells ──▶ jobs ──▶ attempts
      ▲                                          │              │
      └──adapt (tweak one factor)── compare ◀── information ◀── measure ◀── ledger
```

The load-bearing rule: **to make policies, we need information.** Measurement rules produce
information; control rules consume it. The compiler refuses a control rule (like
`model_cascade`/`dynamics`) whose `requires` (e.g. `confidence`) are not yet instrumented.
`experiment_spec.py` and `compile_experiment.py` are written; the instrumented fields
(`confidence`, `perturbation_strength`, `test_executed_success`, the `answer`/`explanation`
split) are measured, so the gated policy arms are now writable.

---

## Current Scope

**Validated:** Python/Flask REST APIs, CRUD apps, real-time collaboration frontends, and
TypeScript/Node.js. Go and Rust configs are defined and under validation. 10 prompt-level
perturbation operators. IEA-baseline energy projection (1.6%/yr). Cost measurement in tokens,
dollars, and joules. Multi-session story orchestration, independent test execution, and a
Redis-queue parallel transport.

**In progress:** The spec/compiler campaign loop (adapt → next grid) and the policy arms.

**Not in scope:** The instrument measures cost — it does not judge whether narration is
"wasteful" or "valuable." The instrument is model-agnostic. DeepSeek was chosen as the anchor
case study, not an endorsement.

---

## Citation

```bibtex
@misc{agentic-dynamics-2026,
  title  = {Agentic Dynamics: A research operating system for agent experimentation and control},
  author = {Hugo Pepar},
  year   = {2026},
  url    = {https://ai-finops-rulebook.web.app},
  note   = {1,067 story sessions, 7 models, 10 perturbation operators.}
}
```

---

## License

Apache 2.0 — see [LICENSE](LICENSE).
