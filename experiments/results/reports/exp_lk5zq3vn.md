# Game Report: inject_competing_goal_s0.5-perturbed

**Model:** anthropic/claude-fable-5  |  **Task:** [inject_competing_goal_s0.5] typescript_ssg...
**Operator:** perturbed (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-06T21:50:10

---

## Strategy
**Classification:** EXPLORATORY
**Score:** 0.773

**Verdict:** EXPLORATORY — model escaped attractor (escape=0.66) and found a novel correct solution (novelty=0.95, correctness=80%). Cost: $1.6062, ~4516J.

**Recommendation:** Promote this operator. The perturbation succeeded.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score | 0.664 |
| Architecture div | 0.750 |
| Structure div | 0.263 |
| Thinking ratio | 0.0% |
| Quality/$ | 1 |
| Quality/J | 0.0002 |
| Converged back | False |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 80% (0/0 tests) |
| Constraint satisfaction | 29% (2/7 constraints) |
| Lines of code | 904 |
| Cyclomatic complexity | 119.0 |
| Code quality | 0.111 |
| Novelty vs baseline | 0.951 |
| **Composite** | **0.530** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens | 24 |
| Completion tokens | 19,627 |
| Reasoning tokens | 0 |
| **Total tokens** | **19,651** |
| Thinking ratio | 0.0% |
| Output efficiency | 99.9% |
| **Total cost** | **$1.606180** |
| **Total energy** | **~4516 J** |
| Solution density | 0.046003 LOC/tok |
| Correctness/$ | 37 |
| Quality/J | 0.000117 |

---

## Headline Metric
**Strategy:** EXPLORATORY  |  **Correctness:** 80%  |  **Cost:** $1.6062  |  **Energy:** ~4516J  |  **Thinking:** 0%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Opencode session transcript](./exp_lk5zq3vn/session.jsonl)
- [Generated code](./exp_lk5zq3vn/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 0 |
| TS files | 24 |
| JS files | 9 |
| Total lines (Py) | 0 |
| Total lines (TS/TSX) | 1488 |
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
