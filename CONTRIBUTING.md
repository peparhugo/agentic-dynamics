---
status: accepted
---
# Contributing to Agentic Dynamics

Thanks for your interest in contributing. This is a research instrument — every contribution adds data points that make the cost model more robust and the instrument more universal.

---

## Ways to Contribute

### I Have API Credits
The highest-impact contribution: **run experiments on models or languages we haven't tested yet.** Check the experiment configs in `experiments/configs/` for available task types.

### I Know a Stack We Haven't Tested
Add a new experiment config in `experiments/configs/`. TypeScript/Node.js, Go, Rust, and Java/Spring are all priorities.

### I Have a Novel Perturbation Idea
Add a new perturbation operator to `src/instrument/perturb.py`. The operator registry is designed for extensibility.

### I Want to Add a New Story or ExperimentSpec
Multi-session stories live in `src/instrument/story.py` (`BUILTIN_STORIES`); the spec/compiler layer (`experiments/specs/*.yaml`) declares `workflow`, `factors`, `rules`, and `adapt`. Note the load-bearing rule: a control rule (policy arm) whose `requires` are not yet instrumented will be refused by the compiler — instrument the fields first.

### I Want to Add a Lab Book
Lab books are `experiments/lab_books/lab_*.md` (the plan) + `scripts/lab_*.py` (the implementation), consuming `_results_summary.json` and trajectory data.

### I Found a Bug or Have a Feature Idea
Open a GitHub issue. Be specific: what you expected, what happened, and how to reproduce it.

### I Want to Improve the Website
The site lives in `apps/website/`. Pure HTML/CSS/JS — no build step. Edit and open a PR.

---

## Getting Started

### 1. Fork and Clone

```bash
git clone https://github.com/YOUR_USERNAME/agentic-dynamics.git
cd agentic-dynamics
pip install -e .
```

### 2. Set Up Opencode

You need the [opencode](https://opencode.ai) CLI installed and available on your `PATH` (configure the path in `src/instrument/opencode.py` if needed). Set up your LLM API keys per the opencode documentation.

### 3. Verify the Instrument Works

```bash
python scripts/run.py experiments/configs/task_manager.yaml --model deepseek/deepseek-v4-pro
```

If this succeeds and produces a result in `experiments/results/`, you're ready.

---

## Adding a New Experiment

### 1. Create a Config File

Create `experiments/configs/your_experiment.yaml`:

```yaml
name: your_experiment
task: >
  Your task description here. Be specific about constraints.
  Include what the model should build, the tech stack, and
  any non-functional requirements.

constraints:
  - Constraint 1 (e.g., "User authentication with JWT tokens")
  - Constraint 2 (e.g., "Rate limiting on all endpoints")
  - Constraint 3

operators:
  - inject_alien_vocab
  - inject_false_premise
  - remove_critical_constraint

strengths: [0.5, 0.8]

# Model is passed at run time as provider/model (no shorthand):
#   python scripts/run.py experiments/configs/your_experiment.yaml --model deepseek/deepseek-v4-pro
```

See existing configs in `experiments/configs/` for more examples.

### 2. Run It

```bash
python scripts/run.py experiments/configs/your_experiment.yaml --model deepseek/deepseek-v4-pro
```

### 3. Check Results

```bash
python scripts/inventory.py refresh
python scripts/inventory.py list
```

Results are saved under `experiments/results/`.

### 4. Submit a PR

Include:
- The config YAML
- A brief description of what you tested and any findings
- Run `python scripts/inventory.py refresh && python scripts/inventory.py report` and include the output in your PR description

---

## Adding a New Perturbation Operator

Edit `src/instrument/perturb.py`. An operator has two parts:

### 1. The Apply Function

```python
def my_operator(prompt: str, strength: float, rng: random.Random) -> str:
    """Describe what this operator does."""
    # strength is in [0.0, 1.0]
    # rng is a seeded Random instance for reproducibility
    # Return the perturbed prompt
    ...
```

### 2. Register It

Add to the `build_operators()` function:

```python
operators["my_operator"] = PerturbationOperator(
    name="my_operator",
    description="A one-line description of what this does",
    apply_fn=my_operator,
    perturbation_class="semantic"  # or "manifold"
)
```

- `"semantic"` — probes truth-seeking and coherence (contradiction, false premises, inverted constraints)
- `"manifold"` — probes search dynamics on the linguistic surface (alien vocabulary, framing shifts, causality reversal)

---

## Running Sweeps

### Single Experiment (positional config, model as `provider/model`)

```bash
python scripts/run.py experiments/configs/task_manager.yaml --model deepseek/deepseek-v4-pro
python scripts/run.py experiments/configs/task_manager.yaml --model anthropic/claude-sonnet-5 --backend claude_cli
```

### Silent Mode Sweep (Explanation Tax)

Tests every model in both natural and forced-silent mode:

```bash
python scripts/sweep_silent_mode.py
```

### Parallel Batch

```bash
python scripts/batch_run.py
```

### Redis Queue (parallel story cells)

```bash
python scripts/enqueue.py --model deepseek/deepseek-v4-flash --missing-only  # fill queue
python scripts/worker.py    # BRPOP worker — run N in parallel
python scripts/monitor.py   # queue dashboard
```

### Pipeline Plans

```bash
python scripts/pipeline.py --plan ci            # lint → test → build
python scripts/pipeline.py --plan full_matrix   # matrix → analyze → review → deploy
```

All scripts use **title-based deduplication** — they query the opencode DB to skip sessions already completed. You can safely re-run them; completed cells are skipped.

**Note on Redis:** the framework queue lives on port **6380** (`FINOPS_REDIS_PORT`). Story agents build Flask/Celery apps against port 6379 and call `flushdb()`/`flushall()` while testing, so they can never reach the framework queue. Never run the queue on 6379.

---

## Repository Conventions

### Python
- Follow existing patterns in `src/instrument/`
- Use `dataclass` for data structures
- Use type hints throughout
- No new dependencies without discussion
- Deprecated: `experiment.py`, `adapter.py`, `lab_book.py` — use `opencode.py` / `run_opencode_agentic()` instead

### Website
- No framework — vanilla HTML/CSS/JS
- Dark theme using CSS custom properties in `:root`
- Use `var(--ac)` for accent, `var(--bg)`/`var(--bg2)` for backgrounds
- JetBrains Mono for code, system font stack for body text

### Agent Surfaces
- `.opencode/` is the primary agent surface (`AGENTS.md`, `opencode.json`, instructions, skills, tools)
- `.claude/` is a hand-ported parallel surface — keep both in sync by hand (see `docs/claude_code_port.md`); there is no build step

### Commits
- Write descriptive commit messages
- Reference issue numbers when applicable
- Keep PRs focused — one concern per PR

---

## Review Process

1. **Open an issue first** for anything beyond a typo fix. We'll discuss scope and approach.
2. **Keep PRs small.** A 500-line PR that does one thing is better than a 2000-line PR that does three things.
3. **Include results.** If you're adding a config or running experiments, attach the output JSON.
4. **Be patient.** This is a community-driven research project. Reviews may take a few days.

---

## Questions?

Open a GitHub issue or reach out on the [project discussions](https://github.com/peparhugo/agentic-dynamics/issues). If you want to coordinate on a specific pillar, mention it in the issue and we'll help you get set up.
