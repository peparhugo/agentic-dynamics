# Game Report: standardized_build-perturbed

**Model:** deepseek/deepseek-v4-pro  |  **Task:** [standardized_build] deepseek...
**Operator:** perturbed (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-06T21:48:38

---

## Strategy
**Classification:** EXPLORATORY
**Score:** 0.786

**Verdict:** EXPLORATORY — model escaped attractor (escape=0.50) and found a novel correct solution (novelty=0.72, correctness=100%). Cost: $0.0200, ~5226J.

**Recommendation:** Promote this operator. The perturbation succeeded.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score | 0.501 |
| Architecture div | 0.667 |
| Structure div | 0.059 |
| Thinking ratio | 11.0% |
| Quality/$ | 50 |
| Quality/J | 0.0002 |
| Converged back | False |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) |
| Constraint satisfaction | 43% (3/7 constraints) |
| Lines of code | 558 |
| Cyclomatic complexity | 69.0 |
| Code quality | 0.179 |
| Novelty vs baseline | 0.723 |
| **Composite** | **0.623** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens | 22,492 |
| Completion tokens | 7,345 |
| Reasoning tokens | 3,696 |
| **Total tokens** | **33,533** |
| Thinking ratio | 11.0% |
| Output efficiency | 21.9% |
| **Total cost** | **$0.020049** |
| **Total energy** | **~5226 J** |
| Solution density | 0.016640 LOC/tok |
| Correctness/$ | 68 |
| Quality/J | 0.000119 |

---

## Headline Metric
**Strategy:** EXPLORATORY  |  **Correctness:** 100%  |  **Cost:** $0.0200  |  **Energy:** ~5226J  |  **Thinking:** 11%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Generated code](./exp_gmnl5d6g/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 6 |
| Total lines (Py) | 558 |
| Functions | 47 |
| Classes | 5 |
| Functions/file | 7.8 |
| Classes/file | 0.8 |
| Avg lines/file | 93 |
| Type hints | 6% |
| Docstrings | 0% |
| Error handlers | 9 |
| Imports | 25 |
| Decorators | 2 |
| Test files | 1 |
| Test file rate | 17% |
| Parse errors | 0 |
