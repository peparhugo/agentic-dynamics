# Game Report: inject_competing_goal_s0.5-perturbed

**Model:** deepseek/deepseek-v4-pro  |  **Task:** [inject_competing_goal_s0.5] typescript_ssg...
**Operator:** perturbed (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-07T14:20:56

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** EXPLORATORY
**Score:** 0.758

**Verdict:** EXPLORATORY — model escaped attractor (escape=0.73) and found a novel correct solution (novelty=0.97, correctness=80%). Cost: $0.0127, ~3314J.

**Recommendation:** Promote this operator. The perturbation succeeded.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | 0.729 |
| Architecture div [H] | 0.857 |
| Structure div [H] | 0.322 |
| Thinking ratio [C] | 8.6% |
| Quality/$ [C] | 78 |
| Quality/J [C] | 0.0003 |
| Converged back [H] | False |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 80% (0/0 tests) [H] |
| Constraint satisfaction [H] | 29% (2/7 constraints) |
| Lines of code [M] | 662 |
| Cyclomatic complexity [C] | 64.0 |
| Code quality [H] | 0.151 |
| Novelty vs baseline [H] | 0.967 |
| **Composite [H]** | **0.541** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 8,926 |
| Completion tokens [M] | 8,052 |
| Reasoning tokens [M] | 1,591 |
| Cache read tokens [M] | 131,072 |
| Cache write tokens [M] | 0 |
| **Total tokens** | **18,569** |
| Thinking ratio [C] | 8.6% |
| Output efficiency [C] | 43.4% |
| Input cost [M] | $0.001030 |
| Output cost [M] | $0.003784 |
| Reasoning cost [M] | $0.000095 |
| Cache cost [M] | $0.007839 |
| **Total cost** | **$0.012747** |
| **Total energy [X]** | **~3314 J** |
| Solution density [C] | 0.035651 LOC/tok |
| Correctness/$ [C] | 27 |
| Quality/J [C] | 0.000163 |

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
