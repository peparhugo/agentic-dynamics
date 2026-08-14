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

### I Found a Bug or Have a Feature Idea
Open a GitHub issue. Be specific: what you expected, what happened, and how to reproduce it.

### I Want to Improve the Website
The site lives in `firebase/public/`. Pure HTML/CSS/JS — no build step. Edit and open a PR.

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
python scripts/run.py --config experiments/configs/task_manager.yaml
```

If this succeeds and produces a result JSON in `experiments/results/`, you're ready.

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

model: deepseek                    # provider shorthand
model_id: deepseek/deepseek-v4-pro # full model identifier
```

See existing configs in `experiments/configs/` for more examples.

### 2. Run It

```bash
python scripts/run.py --config experiments/configs/your_experiment.yaml
```

### 3. Check Results

```bash
python scripts/inventory.py refresh
python scripts/inventory.py list
```

Results are saved to `experiments/results/your_experiment_{model}.json`.

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

### Silent Mode Sweep (Explanation Tax)

Tests every model in both natural and forced-silent mode:

```bash
python scripts/sweep_silent_mode.py
```

### Parallel Batch

```bash
python scripts/batch_run.py
```

All scripts use **title-based deduplication** — they query the opencode DB to skip sessions already completed. You can safely re-run them; completed cells are skipped.

---

## Repository Conventions

### Python
- Follow existing patterns in `src/instrument/`
- Use `dataclass` for data structures
- Use type hints throughout
- No new dependencies without discussion

### Website
- No framework — vanilla HTML/CSS/JS
- Dark theme using CSS custom properties in `:root`
- Use `var(--ac)` for accent, `var(--bg)`/`var(--bg2)` for backgrounds
- JetBrains Mono for code, system font stack for body text

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
