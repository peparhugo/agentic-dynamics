# Game Report: exp_m3c9h6l0-baseline

**Model:** deepseek/deepseek-v4-pro  |  **Task:** [baseline] constraint_detection_3rep...
**Operator:** baseline (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-06T21:50:26

---

## Strategy
**Classification:** CONSERVATIVE
**Score:** 0.768

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=100%, quality=0.75) with moderate resource use ($0.0169, ~4110J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score | 0.000 |
| Architecture div | 0.000 |
| Structure div | 0.000 |
| Thinking ratio | 3.6% |
| Quality/$ | 59 |
| Quality/J | 0.0002 |
| Converged back | True |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) |
| Constraint satisfaction | 100% (7/7 constraints) |
| Lines of code | 891 |
| Cyclomatic complexity | 74.0 |
| Code quality | 0.112 |
| Novelty vs baseline | 0.500 |
| **Composite** | **0.747** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens | 10,139 |
| Completion tokens | 12,622 |
| Reasoning tokens | 843 |
| **Total tokens** | **23,604** |
| Thinking ratio | 3.6% |
| Output efficiency | 53.5% |
| **Total cost** | **$0.016892** |
| **Total energy** | **~4110 J** |
| Solution density | 0.037748 LOC/tok |
| Correctness/$ | 60 |
| Quality/J | 0.000182 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 100%  |  **Cost:** $0.0169  |  **Energy:** ~4110J  |  **Thinking:** 4%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Generated code](./exp_m3c9h6l0/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 28 |
| Total lines (Py) | 891 |
| Functions | 86 |
| Classes | 22 |
| Functions/file | 3.1 |
| Classes/file | 0.8 |
| Avg lines/file | 32 |
| Type hints | 0% |
| Docstrings | 0% |
| Error handlers | 7 |
| Imports | 63 |
| Decorators | 59 |
| Test files | 6 |
| Test file rate | 21% |
| Parse errors | 0 |
