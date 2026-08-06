# Game Report: perturbed-baseline

**Model:** deepseek/deepseek-v4-pro  |  **Task:** [silent_sweep:perturbed:forced-silent] deepseek_v4_pro...
**Operator:** baseline (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-06T21:48:53

---

## Strategy
**Classification:** CONSERVATIVE
**Score:** 0.764

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=100%, quality=0.75) with moderate resource use ($0.0159, ~4065J). Attractor basin held. Perturbation was handled in-manifold.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score | 0.000 |
| Architecture div | 0.000 |
| Structure div | 0.000 |
| Thinking ratio | 5.6% |
| Quality/$ | 63 |
| Quality/J | 0.0002 |
| Converged back | True |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) |
| Constraint satisfaction | 100% (7/7 constraints) |
| Lines of code | 726 |
| Cyclomatic complexity | 72.0 |
| Code quality | 0.138 |
| Novelty vs baseline | 0.500 |
| **Composite** | **0.753** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens | 10,057 |
| Completion tokens | 11,544 |
| Reasoning tokens | 1,288 |
| **Total tokens** | **22,889** |
| Thinking ratio | 5.6% |
| Output efficiency | 50.4% |
| **Total cost** | **$0.015897** |
| **Total energy** | **~4065 J** |
| Solution density | 0.031718 LOC/tok |
| Correctness/$ | 64 |
| Quality/J | 0.000185 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 100%  |  **Cost:** $0.0159  |  **Energy:** ~4065J  |  **Thinking:** 6%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Generated code](./exp_hn0qqsuf/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 13 |
| Total lines (Py) | 726 |
| Functions | 76 |
| Classes | 13 |
| Functions/file | 5.8 |
| Classes/file | 1.0 |
| Avg lines/file | 56 |
| Type hints | 0% |
| Docstrings | 0% |
| Error handlers | 9 |
| Imports | 40 |
| Decorators | 29 |
| Test files | 4 |
| Test file rate | 31% |
| Parse errors | 0 |
