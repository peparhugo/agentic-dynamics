# Game Report: inject_phantom_success_s0.5-perturbed

**Model:** deepseek/deepseek-v4-pro  |  **Task:** [inject_phantom_success_s0.5] typescript_ssg...
**Operator:** perturbed (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-06T21:44:03

---

## Strategy
**Classification:** EXPLORATORY
**Score:** 0.760

**Verdict:** EXPLORATORY — model escaped attractor (escape=0.77) and found a novel correct solution (novelty=0.97, correctness=80%). Cost: $0.0200, ~5136J.

**Recommendation:** Promote this operator. The perturbation succeeded.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score | 0.768 |
| Architecture div | 0.900 |
| Structure div | 0.392 |
| Thinking ratio | 7.8% |
| Quality/$ | 50 |
| Quality/J | 0.0002 |
| Converged back | False |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 80% (0/0 tests) |
| Constraint satisfaction | 14% (1/7 constraints) |
| Lines of code | 1048 |
| Cyclomatic complexity | 69.0 |
| Code quality | 0.095 |
| Novelty vs baseline | 0.970 |
| **Composite** | **0.487** |

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
| **Total cost** | **$0.020037** |
| **Total energy** | **~5136 J** |
| Solution density | 0.035305 LOC/tok |
| Correctness/$ | 45 |
| Quality/J | 0.000095 |

---

## Headline Metric
**Strategy:** EXPLORATORY  |  **Correctness:** 80%  |  **Cost:** $0.0200  |  **Energy:** ~5136J  |  **Thinking:** 8%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Opencode session transcript](./exp_7l_2qyd3/session.jsonl)
- [Generated code](./exp_7l_2qyd3/code/)

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
