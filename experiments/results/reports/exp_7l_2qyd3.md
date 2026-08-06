# Game Report: inject_phantom_success_s0.5-perturbed

**Model:** exp_7l_2qyd3  |  **Task:** [inject_phantom_success_s0.5] typescript_ssg...
**Operator:** perturbed (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-06T00:48:02

---

## Strategy
**Classification:** CONSERVATIVE
**Score:** 0.689

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=80%, quality=0.42) with moderate resource use ($0.0200, ~5136J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score | 0.000 |
| Architecture div | 0.000 |
| Structure div | 0.000 |
| Thinking ratio | 7.8% |
| Quality/$ | 56 |
| Quality/J | 0.0002 |
| Converged back | True |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 80% (0/0 tests) |
| Constraint satisfaction | 14% (1/7 constraints) |
| Lines of code | 1048 |
| Cyclomatic complexity | 69.0 |
| Code quality | 0.095 |
| Novelty vs baseline | 0.500 |
| **Composite** | **0.417** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens | 14,993 |
| Completion tokens | 12,367 |
| Reasoning tokens | 2,324 |
| **Total tokens** | **29,684** |
| Thinking ratio | 7.8% |
| Output efficiency | 41.7% |
| Input cost | $0.004048 |
| Output cost | $0.013604 |
| Reasoning cost | $0.000325 |
| **Total cost** | **$0.020037** |
| **Total energy** | **~5136 J** |
| Solution density | 0.035305 LOC/tok |
| Correctness/$ | 45 |
| Quality/J | 0.000081 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 80%  |  **Cost:** $0.0200  |  **Energy:** ~5136J  |  **Thinking:** 8%

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 0 |
| TS files | 14 |
| Total lines (Py) | 0 |
| Total lines (TS/TSX) | 1035 |
| Functions | 0 |
| Classes | 0 |
| Functions/file | 0 |
| Classes/file | 0 |
| Avg lines/file | 0 |
| Type hints | 0% |
| Docstrings | 0% |
| Error handlers | 0 |
| Imports | 0 |
| Decorators | 0 |
| Test files | 0 |
| Test file rate | 0% |
| Parse errors | 0 |
