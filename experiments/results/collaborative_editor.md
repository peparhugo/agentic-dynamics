---
experiment_id: collaborative_editor
timestamp: '2026-07-30T21:38:54.554875+00:00'
model: deepseek-v4-pro
task: Design the frontend architecture for a real-time collaborative document editor
  like Google Docs. Multiple users edit simultaneously. Must handle cursor positions,
  real-time sync, conflict resolution (
operators:
- inject_alien_vocab
- shift_framing
strengths:
- 0.5
- 0.8
total_tokens: 15000
total_cost_usd: 0.018132
null_hypothesis: Under perturbation at strengths [0.5, 0.8], no systematic difference
  in trajectory deviation between manifold and semantic perturbation classes.
alternative_hypothesis: Manifold perturbations produce higher trajectory deviation
  and slower recovery than semantic perturbations because semantic perturbations operate
  within the model's existing concept manifold.
null_status: rejected
conclusion_reasoning: 'Manifold avg: 1.000, Semantic avg: 0.000, Delta: +1.000.'
---

# Experiment: collaborative_editor

**Model:** deepseek-v4-pro | **Cost:** 15000 tokens, $0.0181

## Results

| Operator | Strength | Escape | Recovery | Class | Verdict |
|----------|----------|--------|----------|-------|---------|
| inject_alien_vocab | 0.5 | 1.000 | 1.000 | manifold | escaped — model explored novel territory and prese |
| inject_alien_vocab | 0.8 | 1.000 | 0.000 | manifold | escaped — model explored novel territory and prese |
| shift_framing | 0.5 | 1.000 | 1.000 | manifold | escaped — model explored novel territory and prese |
| shift_framing | 0.8 | 1.000 | 0.000 | manifold | escaped — model explored novel territory and prese |

**Manifold avg escape:** 1.000  **Semantic avg escape:** 0.000  **Delta:** +1.000

## Conclusion
**Null hypothesis:** rejected
**Reasoning:** Manifold avg: 1.000, Semantic avg: 0.000, Delta: +1.000.