# Game Report: exp_37z0nq68-baseline

**Model:** deepseek/deepseek-v4-pro  |  **Task:** Flask task management API with JWT and tests...
**Operator:** baseline (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-06T00:40:53

---

## Strategy
**Classification:** CONSERVATIVE
**Score:** 0.769

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=100%, quality=0.62) with moderate resource use ($0.0217, ~4993J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score | 0.000 |
| Architecture div | 0.000 |
| Structure div | 0.000 |
| Thinking ratio | 3.2% |
| Quality/$ | 50 |
| Quality/J | 0.0002 |
| Converged back | True |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) |
| Constraint satisfaction | 57% (4/7 constraints) |
| Lines of code | 796 |
| Cyclomatic complexity | 117.0 |
| Code quality | 0.126 |
| Novelty vs baseline | 0.500 |
| **Composite** | **0.622** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens | 16,060 |
| Completion tokens | 14,111 |
| Reasoning tokens | 984 |
| **Total tokens** | **31,155** |
| Thinking ratio | 3.2% |
| Output efficiency | 45.3% |
| Input cost | $0.004336 |
| Output cost | $0.015522 |
| Reasoning cost | $0.000138 |
| **Total cost** | **$0.021712** |
| **Total energy** | **~4993 J** |
| Solution density | 0.025550 LOC/tok |
| Correctness/$ | 50 |
| Quality/J | 0.000124 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 100%  |  **Cost:** $0.0217  |  **Energy:** ~4993J  |  **Thinking:** 3%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Generated code](./exp_37z0nq68/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 9 |
| Total lines (Py) | 796 |
| Functions | 85 |
| Classes | 14 |
| Functions/file | 9.4 |
| Classes/file | 1.6 |
| Avg lines/file | 88 |
| Type hints | 0% |
| Docstrings | 4% |
| Error handlers | 2 |
| Imports | 26 |
| Decorators | 19 |
| Test files | 3 |
| Test file rate | 33% |
| Parse errors | 0 |
