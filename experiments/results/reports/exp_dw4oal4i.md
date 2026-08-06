# Game Report: invert_constraint_s0.5-perturbed

**Model:** deepseek/deepseek-v4-pro  |  **Task:** [invert_constraint_s0.5] typescript_ssg...
**Operator:** perturbed (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-06T00:52:03

---

## Strategy
**Classification:** EXPLORATORY
**Score:** 0.759

**Verdict:** EXPLORATORY — model escaped attractor (escape=0.68) and found a novel correct solution (novelty=0.97, correctness=80%). Cost: $0.0136, ~3348J.

**Recommendation:** Promote this operator. The perturbation succeeded.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score | 0.685 |
| Architecture div | 0.833 |
| Structure div | 0.202 |
| Thinking ratio | 8.5% |
| Quality/$ | 93 |
| Quality/J | 0.0003 |
| Converged back | False |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 80% (0/0 tests) |
| Constraint satisfaction | 29% (2/7 constraints) |
| Lines of code | 353 |
| Cyclomatic complexity | 75.0 |
| Code quality | 0.283 |
| Novelty vs baseline | 0.970 |
| **Composite** | **0.568** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens | 12,858 |
| Completion tokens | 6,433 |
| Reasoning tokens | 1,786 |
| **Total tokens** | **21,077** |
| Thinking ratio | 8.5% |
| Output efficiency | 30.5% |
| Input cost | $0.003472 |
| Output cost | $0.007076 |
| Reasoning cost | $0.000250 |
| **Total cost** | **$0.013559** |
| **Total energy** | **~3348 J** |
| Solution density | 0.016748 LOC/tok |
| Correctness/$ | 74 |
| Quality/J | 0.000170 |

---

## Headline Metric
**Strategy:** EXPLORATORY  |  **Correctness:** 80%  |  **Cost:** $0.0136  |  **Energy:** ~3348J  |  **Thinking:** 8%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Opencode session transcript](./exp_dw4oal4i/session.jsonl)
- [Generated code](./exp_dw4oal4i/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 0 |
| TS files | 5 |
| Total lines (Py) | 0 |
| Total lines (TS/TSX) | 346 |
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
