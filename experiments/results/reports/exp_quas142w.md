# Game Report: inject_phantom_success_s0.5_r1-perturbed

**Model:** deepseek/deepseek-v4-pro  |  **Task:** [inject_phantom_success_s0.5_r1] constraint_detection_3rep...
**Operator:** perturbed (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-04T02:56:38

---

## Strategy
**Classification:** CONSERVATIVE
**Score:** 0.789

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=100%, quality=0.69) with moderate resource use ($0.0154, ~3774J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score | 0.309 |
| Architecture div | 0.250 |
| Structure div | 0.060 |
| Thinking ratio | 3.4% |
| Quality/$ | 65 |
| Quality/J | 0.0003 |
| Converged back | False |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) |
| Constraint satisfaction | 71% (5/7 constraints) |
| Lines of code | 770 |
| Cyclomatic complexity | 79.0 |
| Code quality | 0.130 |
| Novelty vs baseline | 0.638 |
| **Composite** | **0.686** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens | 9,166 |
| Completion tokens | 11,728 |
| Reasoning tokens | 730 |
| **Total tokens** | **21,624** |
| Thinking ratio | 3.4% |
| Output efficiency | 54.2% |
| Input cost | $0.002475 |
| Output cost | $0.012901 |
| Reasoning cost | $0.000102 |
| **Total cost** | **$0.015379** |
| **Total energy** | **~3774 J** |
| Solution density | 0.035609 LOC/tok |
| Correctness/$ | 65 |
| Quality/J | 0.000182 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 100%  |  **Cost:** $0.0154  |  **Energy:** ~3774J  |  **Thinking:** 3%

---

## AST Code Quality

| Metric | Value |
|--------|-------|
| Python files | 26 |
| Total lines | 770 |
| Functions | 79 |
| Classes | 13 |
| Functions/file | 3.0 |
| Classes/file | 0.5 |
| Avg lines/file | 30 |
| Type hints | 0% |
| Docstrings | 0% |
| Error handlers | 16 |
| Imports | 65 |
| Decorators | 57 |
| Test files | 6 |
| Test file rate | 23% |
| Parse errors | 0 |
