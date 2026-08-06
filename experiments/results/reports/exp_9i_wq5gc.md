# Game Report: remove_critical_constraint_s0.5-perturbed

**Model:** exp_9i_wq5gc  |  **Task:** [remove_critical_constraint_s0.5] typescript_ssg...
**Operator:** perturbed (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-06T00:50:13

---

## Strategy
**Classification:** CONSERVATIVE
**Score:** 0.673

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=80%, quality=0.48) with moderate resource use ($0.2067, ~6159J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score | 0.000 |
| Architecture div | 0.000 |
| Structure div | 0.000 |
| Thinking ratio | 15.9% |
| Quality/$ | 62 |
| Quality/J | 0.0002 |
| Converged back | True |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 80% (0/0 tests) |
| Constraint satisfaction | 29% (2/7 constraints) |
| Lines of code | 525 |
| Cyclomatic complexity | 89.0 |
| Code quality | 0.190 |
| Novelty vs baseline | 0.500 |
| **Composite** | **0.479** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens | 18,710 |
| Completion tokens | 9,414 |
| Reasoning tokens | 5,312 |
| **Total tokens** | **33,436** |
| Thinking ratio | 15.9% |
| Output efficiency | 28.2% |
| Input cost | $0.005052 |
| Output cost | $0.010355 |
| Reasoning cost | $0.000744 |
| **Total cost** | **$0.206743** |
| **Total energy** | **~6159 J** |
| Solution density | 0.015702 LOC/tok |
| Correctness/$ | 50 |
| Quality/J | 0.000078 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 80%  |  **Cost:** $0.2067  |  **Energy:** ~6159J  |  **Thinking:** 16%

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 0 |
| TS files | 9 |
| Total lines (Py) | 0 |
| Total lines (TS/TSX) | 495 |
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
