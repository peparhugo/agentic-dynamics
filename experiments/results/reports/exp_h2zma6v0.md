# Game Report: inject_competing_goal_s0.5-perturbed

**Model:** deepseek/deepseek-v4-pro  |  **Task:** [inject_competing_goal_s0.5] typescript_ssg...
**Operator:** perturbed (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-06T21:48:43

---

## Strategy
**Classification:** EXPLORATORY
**Score:** 0.758

**Verdict:** EXPLORATORY — model escaped attractor (escape=0.73) and found a novel correct solution (novelty=0.97, correctness=80%). Cost: $0.0127, ~3314J.

**Recommendation:** Promote this operator. The perturbation succeeded.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score | 0.729 |
| Architecture div | 0.857 |
| Structure div | 0.322 |
| Thinking ratio | 8.6% |
| Quality/$ | 78 |
| Quality/J | 0.0003 |
| Converged back | False |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 80% (0/0 tests) |
| Constraint satisfaction | 29% (2/7 constraints) |
| Lines of code | 662 |
| Cyclomatic complexity | 64.0 |
| Code quality | 0.151 |
| Novelty vs baseline | 0.967 |
| **Composite** | **0.541** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens | 8,926 |
| Completion tokens | 8,052 |
| Reasoning tokens | 1,591 |
| **Total tokens** | **18,569** |
| Thinking ratio | 8.6% |
| Output efficiency | 43.4% |
| **Total cost** | **$0.012747** |
| **Total energy** | **~3314 J** |
| Solution density | 0.035651 LOC/tok |
| Correctness/$ | 70 |
| Quality/J | 0.000163 |

---

## Headline Metric
**Strategy:** EXPLORATORY  |  **Correctness:** 80%  |  **Cost:** $0.0127  |  **Energy:** ~3314J  |  **Thinking:** 9%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Opencode session transcript](./exp_h2zma6v0/session.jsonl)
- [Generated code](./exp_h2zma6v0/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 0 |
| TS files | 8 |
| Total lines (Py) | 0 |
| Total lines (TS/TSX) | 628 |
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
