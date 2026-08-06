# Game Report: invert_constraint_s0.5-perturbed

**Model:** deepseek/deepseek-v4-pro  |  **Task:** [invert_constraint_s0.5] typescript_ssg...
**Operator:** perturbed (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-06T21:44:00

---

## Strategy
**Classification:** EXPLORATORY
**Score:** 0.760

**Verdict:** EXPLORATORY — model escaped attractor (escape=0.73) and found a novel correct solution (novelty=0.97, correctness=80%). Cost: $0.0236, ~5484J.

**Recommendation:** Promote this operator. The perturbation succeeded.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score | 0.735 |
| Architecture div | 0.857 |
| Structure div | 0.341 |
| Thinking ratio | 7.6% |
| Quality/$ | 42 |
| Quality/J | 0.0002 |
| Converged back | False |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 80% (0/0 tests) |
| Constraint satisfaction | 14% (1/7 constraints) |
| Lines of code | 632 |
| Cyclomatic complexity | 59.0 |
| Code quality | 0.158 |
| Novelty vs baseline | 0.966 |
| **Composite** | **0.499** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens | 16,931 |
| Completion tokens | 12,948 |
| Reasoning tokens | 2,450 |
| **Total tokens** | **32,329** |
| Thinking ratio | 7.6% |
| Output efficiency | 40.1% |
| **Total cost** | **$0.023633** |
| **Total energy** | **~5484 J** |
| Solution density | 0.019549 LOC/tok |
| Correctness/$ | 42 |
| Quality/J | 0.000091 |

---

## Headline Metric
**Strategy:** EXPLORATORY  |  **Correctness:** 80%  |  **Cost:** $0.0236  |  **Energy:** ~5484J  |  **Thinking:** 8%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Opencode session transcript](./exp_7eo89cdf/session.jsonl)
- [Generated code](./exp_7eo89cdf/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 0 |
| TS files | 15 |
| JS files | 6 |
| Total lines (Py) | 0 |
| Total lines (TS/TSX) | 1009 |
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
