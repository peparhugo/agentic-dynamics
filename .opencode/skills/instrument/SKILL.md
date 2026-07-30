# Reasoning Topology Instrument

Run perturbation experiments to measure how language models explore
unfamiliar reasoning trajectories.

## Quick start

```bash
# Install
pip install -e .

# Set API key
export DEEPSEEK_API_KEY="sk-..."

# Run baseline experiment
python scripts/run.py experiments/configs/baseline.yaml
```

## Configuration

Experiments are defined in `experiments/configs/*.yaml`:

```yaml
name: baseline
task: "Design a URL shortener..."
turns:
  - [analyze, "Analyze requirements..."]
  - [design, "Design architecture..."]
  - [implement, "Write implementation..."]
  - [review, "Review design..."]
operators:
  - inject_alien_vocab  # manifold — forces off-manifold exploration
  - inject_phantom_success  # semantic — tests truth-seeking
strengths: [0.5, 0.8]
model: deepseek
model_id: deepseek-v4-pro
```

## Operators

| Operator | Class | Purpose |
|---|---|---|
| inject_alien_vocab | manifold | Cross-domain vocabulary injection |
| shift_framing | manifold | Construction → falsification stance shift |
| reverse_causality | manifold | Effect-before-cause ordering |
| force_abandonment | manifold | Generate-then-discard solutions |
| inject_false_premise | semantic | Plausible incorrect assumptions |
| inject_phantom_success | semantic | False intermediate results |
| remove_critical_constraint | semantic | Silent constraint removal |
| invert_constraint | semantic | Expected paradigm inversion |
| insert_contradiction | semantic | Irreconcilable premises |
| inject_competing_goal | semantic | Conflicting requirements |

## Output

Results are written to:
- `experiments/results/{name}.md` — lab book with YAML frontmatter
- `experiments/results/{name}_{model}.json` — machine-readable results
