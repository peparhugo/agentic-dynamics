# Game Report: remove_critical_constraint_s0.5-perturbed

**Model:** exp_9tfs606s  |  **Task:** [remove_critical_constraint_s0.5] typescript_ssg...
**Operator:** perturbed (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-06T00:48:57

---

## Strategy
**Classification:** CONSERVATIVE
**Score:** 0.705

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=80%, quality=0.43) with moderate resource use ($0.8493, ~2414J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score | 0.000 |
| Architecture div | 0.000 |
| Structure div | 0.000 |
| Thinking ratio | 0.0% |
| Quality/$ | 87 |
| Quality/J | 0.0004 |
| Converged back | True |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 80% (0/0 tests) |
| Constraint satisfaction | 14% (1/7 constraints) |
| Lines of code | 654 |
| Cyclomatic complexity | 90.0 |
| Code quality | 0.153 |
| Novelty vs baseline | 0.500 |
| **Composite** | **0.428** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens | 12 |
| Completion tokens | 10,490 |
| Reasoning tokens | 0 |
| **Total tokens** | **10,502** |
| Thinking ratio | 0.0% |
| Output efficiency | 99.9% |
| Input cost | $0.000003 |
| Output cost | $0.011539 |
| Reasoning cost | $0.000000 |
| **Total cost** | **$0.849264** |
| **Total energy** | **~2414 J** |
| Solution density | 0.062274 LOC/tok |
| Correctness/$ | 69 |
| Quality/J | 0.000178 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 80%  |  **Cost:** $0.8493  |  **Energy:** ~2414J  |  **Thinking:** 0%

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 0 |
| TS files | 10 |
| Total lines (Py) | 0 |
| Total lines (TS/TSX) | 638 |
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
