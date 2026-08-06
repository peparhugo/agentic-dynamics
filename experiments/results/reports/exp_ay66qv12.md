# Game Report: inject_competing_goal_s0.5-perturbed

**Model:** deepseek/deepseek-v4-pro  |  **Task:** [inject_competing_goal_s0.5] typescript_ssg...
**Operator:** perturbed (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-06T22:17:52

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** EXPLORATORY
**Score:** 0.745

**Verdict:** EXPLORATORY — model escaped attractor (escape=0.73) and found a novel correct solution (novelty=0.97, correctness=80%). Cost: $0.0177, ~5038J.

**Recommendation:** Promote this operator. The perturbation succeeded.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | 0.728 |
| Architecture div [H] | 0.833 |
| Structure div [H] | 0.348 |
| Thinking ratio [C] | 15.3% |
| Quality/$ [C] | 56 |
| Quality/J [C] | 0.0002 |
| Converged back [H] | False |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 80% (0/0 tests) [H] |
| Constraint satisfaction [H] | 29% (2/7 constraints) |
| Lines of code [M] | 763 |
| Cyclomatic complexity [C] | 80.0 |
| Code quality [H] | 0.131 |
| Novelty vs baseline [H] | 0.968 |
| **Composite [H]** | **0.537** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 8,035 |
| Completion tokens [M] | 11,792 |
| Reasoning tokens [M] | 3,580 |
| Cache read tokens [M] | 232,704 |
| Cache write tokens [M] | 0 |
| **Total tokens** | **23,407** |
| Thinking ratio [C] | 15.3% |
| Output efficiency [C] | 50.4% |
| Input cost [M] | $0.000797 |
| Output cost [M] | $0.004765 |
| Reasoning cost [M] | $0.000184 |
| Cache cost [M] | $0.011967 |
| **Total cost** | **$0.017712** |
| **Total energy [X]** | **~5038 J** |
| Solution density [C] | 0.032597 LOC/tok |
| Correctness/$ [C] | 17 |
| Quality/J [C] | 0.000107 |

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
