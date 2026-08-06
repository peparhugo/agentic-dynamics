# Game Report: remove_critical_constraint_s0.5_r1-perturbed

**Model:** openai/gpt-5.6-fast  |  **Task:** [remove_critical_constraint_s0.5_r1] gpt_gather_gpt_5_6_fast...
**Operator:** perturbed (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-06T21:43:25

---

## Strategy
**Classification:** EXPLORATORY
**Score:** 0.838

**Verdict:** EXPLORATORY — model escaped attractor (escape=0.74) and found a novel correct solution (novelty=0.97, correctness=100%). Cost: $0.6163, ~1443J.

**Recommendation:** Promote this operator. The perturbation succeeded.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score | 0.736 |
| Architecture div | 0.800 |
| Structure div | 0.417 |
| Thinking ratio | 3.8% |
| Quality/$ | 2 |
| Quality/J | 0.0007 |
| Converged back | False |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) |
| Constraint satisfaction | 100% (7/7 constraints) |
| Lines of code | 305 |
| Cyclomatic complexity | 50.0 |
| Code quality | 0.328 |
| Novelty vs baseline | 0.970 |
| **Composite** | **0.861** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens | 33 |
| Completion tokens | 5,792 |
| Reasoning tokens | 230 |
| **Total tokens** | **6,055** |
| Thinking ratio | 3.8% |
| Output efficiency | 95.7% |
| **Total cost** | **$0.616274** |
| **Total energy** | **~1443 J** |
| Solution density | 0.050372 LOC/tok |
| Correctness/$ | 156 |
| Quality/J | 0.000597 |

---

## Headline Metric
**Strategy:** EXPLORATORY  |  **Correctness:** 100%  |  **Cost:** $0.6163  |  **Energy:** ~1443J  |  **Thinking:** 4%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Generated code](./exp_4jvdqhzs/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 4 |
| Total lines (Py) | 305 |
| Functions | 36 |
| Classes | 0 |
| Functions/file | 9.0 |
| Classes/file | 0.0 |
| Avg lines/file | 76 |
| Type hints | 31% |
| Docstrings | 0% |
| Error handlers | 4 |
| Imports | 17 |
| Decorators | 19 |
| Test files | 2 |
| Test file rate | 50% |
| Parse errors | 0 |
