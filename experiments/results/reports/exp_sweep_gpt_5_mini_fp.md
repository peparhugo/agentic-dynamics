# Game Report: perturbed-baseline

**Model:** openai/gpt-5-mini  |  **Task:** [silent_sweep:perturbed:forced] gpt_5_mini...
**Operator:** baseline (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-04T02:56:59

---

## Strategy
**Classification:** CONSERVATIVE
**Score:** 0.764

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=100%, quality=0.71) with moderate resource use ($0.0323, ~5369J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score | 0.000 |
| Architecture div | 0.000 |
| Structure div | 0.000 |
| Thinking ratio | 5.4% |
| Quality/$ | 61 |
| Quality/J | 0.0002 |
| Converged back | True |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) |
| Constraint satisfaction | 71% (5/7 constraints) |
| Lines of code | 281 |
| Cyclomatic complexity | 52.0 |
| Code quality | 0.356 |
| Novelty vs baseline | 0.500 |
| **Composite** | **0.710** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens | 36,992 |
| Completion tokens | 5,507 |
| Reasoning tokens | 2,432 |
| **Total tokens** | **44,931** |
| Thinking ratio | 5.4% |
| Output efficiency | 12.3% |
| Input cost | $0.009988 |
| Output cost | $0.006058 |
| Reasoning cost | $0.000340 |
| **Total cost** | **$0.032320** |
| **Total energy** | **~5369 J** |
| Solution density | 0.006254 LOC/tok |
| Correctness/$ | 61 |
| Quality/J | 0.000132 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 100%  |  **Cost:** $0.0323  |  **Energy:** ~5369J  |  **Thinking:** 5%

---

## AST Code Quality

| Metric | Value |
|--------|-------|
| Python files | 7 |
| Total lines | 281 |
| Functions | 27 |
| Classes | 5 |
| Functions/file | 3.9 |
| Classes/file | 0.7 |
| Avg lines/file | 40 |
| Type hints | 0% |
| Docstrings | 0% |
| Error handlers | 7 |
| Imports | 27 |
| Decorators | 18 |
| Test files | 2 |
| Test file rate | 29% |
| Parse errors | 0 |
