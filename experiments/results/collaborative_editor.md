---
experiment_id: collaborative_editor
timestamp: '2026-07-30T20:54:10.715598+00:00'
model: deepseek-v4-pro
task: Design the frontend architecture for a real-time collaborative document editor
  like Google Docs. Multiple users edit simultaneously. Must handle cursor positions,
  real-time sync, conflict resolution (
operators:
- inject_alien_vocab
- shift_framing
- reverse_causality
- inject_false_premise
strengths:
- 0.5
- 0.8
total_tokens: 18000
total_cost_usd: 0.00486
null_hypothesis: Under perturbation at strengths [0.5, 0.8], no systematic difference
  in trajectory deviation between manifold and semantic perturbation classes.
alternative_hypothesis: Manifold perturbations produce higher trajectory deviation
  and slower recovery than semantic perturbations because semantic perturbations operate
  within the model's existing concept manifold.
null_status: not_rejected
conclusion_reasoning: 'Manifold avg: 1.000, Semantic avg: 1.000, Delta: +0.000.'
---

# Experiment: collaborative_editor

**Model:** deepseek-v4-pro | **Cost:** 18000 tokens, $0.0049

## Results

| Operator | Strength | Escape | Recovery | Class | Verdict |
|----------|----------|--------|----------|-------|---------|
| inject_alien_vocab | 0.5 | 1.000 | 1.000 | manifold | over-escaped — model over-reacted to a known patte |
| inject_alien_vocab | 0.8 | 1.000 | 0.000 | manifold | over-escaped — model over-reacted to a known patte |
| shift_framing | 0.5 | 1.000 | 1.000 | manifold | over-escaped — model over-reacted to a known patte |
| shift_framing | 0.8 | 1.000 | 0.000 | manifold | over-escaped — model over-reacted to a known patte |
| reverse_causality | 0.5 | 1.000 | 1.000 | manifold | over-escaped — model over-reacted to a known patte |
| reverse_causality | 0.8 | 1.000 | 1.000 | manifold | over-escaped — model over-reacted to a known patte |
| inject_false_premise | 0.5 | 1.000 | 1.000 | semantic | over-escaped — model over-reacted to a known patte |
| inject_false_premise | 0.8 | 1.000 | 0.000 | semantic | over-escaped — model over-reacted to a known patte |

**Manifold avg escape:** 1.000  **Semantic avg escape:** 1.000  **Delta:** +0.000

## Conclusion
**Null hypothesis:** not_rejected
**Reasoning:** Manifold avg: 1.000, Semantic avg: 1.000, Delta: +0.000.