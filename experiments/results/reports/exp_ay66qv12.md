# Game Report: inject_competing_goal_s0.5-perturbed

**Model:** deepseek/deepseek-v4-pro  |  **Task:** [inject_competing_goal_s0.5] typescript_ssg...
**Operator:** perturbed (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-06T21:44:55

---

## Strategy
**Classification:** EXPLORATORY
**Score:** 0.745

**Verdict:** EXPLORATORY — model escaped attractor (escape=0.73) and found a novel correct solution (novelty=0.97, correctness=80%). Cost: $0.0177, ~5038J.

**Recommendation:** Promote this operator. The perturbation succeeded.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score | 0.728 |
| Architecture div | 0.833 |
| Structure div | 0.348 |
| Thinking ratio | 15.3% |
| Quality/$ | 56 |
| Quality/J | 0.0002 |
| Converged back | False |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 80% (0/0 tests) |
| Constraint satisfaction | 29% (2/7 constraints) |
| Lines of code | 763 |
| Cyclomatic complexity | 80.0 |
| Code quality | 0.131 |
| Novelty vs baseline | 0.968 |
| **Composite** | **0.537** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens | 8,035 |
| Completion tokens | 11,792 |
| Reasoning tokens | 3,580 |
| **Total tokens** | **23,407** |
| Thinking ratio | 15.3% |
| Output efficiency | 50.4% |
| **Total cost** | **$0.017712** |
| **Total energy** | **~5038 J** |
| Solution density | 0.032597 LOC/tok |
| Correctness/$ | 51 |
| Quality/J | 0.000107 |

---

## Headline Metric
**Strategy:** EXPLORATORY  |  **Correctness:** 80%  |  **Cost:** $0.0177  |  **Energy:** ~5038J  |  **Thinking:** 15%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Opencode session transcript](./exp_ay66qv12/session.jsonl)
- [Generated code](./exp_ay66qv12/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 0 |
| TS files | 12 |
| Total lines (Py) | 0 |
| Total lines (TS/TSX) | 752 |
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
