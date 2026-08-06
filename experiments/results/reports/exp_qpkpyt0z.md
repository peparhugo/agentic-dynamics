# Game Report: inject_competing_goal_s0.5-perturbed

**Model:** deepseek/deepseek-v4-pro  |  **Task:** [inject_competing_goal_s0.5] typescript_ssg...
**Operator:** perturbed (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-06T22:30:21

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** EXPLORATORY
**Score:** 0.832

**Verdict:** EXPLORATORY — model escaped attractor (escape=0.74) and found a novel correct solution (novelty=0.97, correctness=100%). Cost: $0.0168, ~4320J.

**Recommendation:** Promote this operator. The perturbation succeeded.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | 0.743 |
| Architecture div [H] | 0.833 |
| Structure div [H] | 0.398 |
| Thinking ratio [C] | 6.3% |
| Quality/$ [C] | 60 |
| Quality/J [C] | 0.0002 |
| Converged back [H] | False |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) [H] |
| Constraint satisfaction [H] | 29% (2/7 constraints) |
| Lines of code [M] | 948 |
| Cyclomatic complexity [C] | 70.0 |
| Code quality [H] | 0.105 |
| Novelty vs baseline [H] | 0.966 |
| **Composite [H]** | **0.602** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 7,436 |
| Completion tokens [M] | 13,346 |
| Reasoning tokens [M] | 1,395 |
| Cache read tokens [M] | 191,872 |
| Cache write tokens [M] | 0 |
| **Total tokens** | **22,177** |
| Thinking ratio [C] | 6.3% |
| Output efficiency [C] | 60.2% |
| Input cost [M] | $0.000769 |
| Output cost [M] | $0.005623 |
| Reasoning cost [M] | $0.000075 |
| Cache cost [M] | $0.010288 |
| **Total cost** | **$0.016755** |
| **Total energy [X]** | **~4320 J** |
| Solution density [C] | 0.042747 LOC/tok |
| Correctness/$ [C] | 23 |
| Quality/J [C] | 0.000139 |

---

## Headline Metric
**Strategy:** EXPLORATORY  |  **Correctness:** 100%  |  **Cost:** $0.0168  |  **Energy:** ~4320J  |  **Thinking:** 6%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Opencode session transcript](./exp_qpkpyt0z/session.jsonl)
- [Generated code](./exp_qpkpyt0z/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 0 |
| TS files | 28 |
| JS files | 10 |
| Total lines (Py) | 0 |
| Total lines (TS/TSX) | 1439 |
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
