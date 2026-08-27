# Game Report: inject_competing_goal_s0.5-perturbed

**Model:** deepseek/deepseek-v4-pro  |  **Task:** [inject_competing_goal_s0.5] task_manager...
**Operator:** perturbed (objective_mutation, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-27T00:54:04

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** CONSERVATIVE
**Score:** 0.851

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=100%, quality=0.68) with moderate resource use ($0.0267, ~8704J). Model absorbed the perturbation without divergence.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | 0.285 |
| Architecture div [H] | 0.200 |
| Structure div [H] | 0.060 |
| Thinking ratio [C] | 31.0% |
| Quality/$ [C] | 37 |
| Quality/J [C] | 0.0001 |
| Converged back [H] | False |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) [H] |
| Constraint satisfaction [H] | 71% (5/7 constraints) |
| Lines of code [M] | 1085 |
| Cyclomatic complexity [C] | 171.0 |
| Code quality [H] | 0.092 |
| Novelty vs baseline [H] | 0.625 |
| **Composite [H]** | **0.676** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 8,418 |
| Completion tokens [M] | 14,197 |
| Reasoning tokens [M] | 10,139 |
| Cache read tokens [M] | 521,216 |
| Cache write tokens [M] | 0 |
| **Total tokens** | **32,754** |
| Thinking ratio [C] | 31.0% |
| Output efficiency [C] | 43.3% |
| Input cost [M] | $0.002277 |
| Output cost [M] | $0.011520 |
| Reasoning cost [M] | $0.008227 |
| Cache cost [M] | $0.004699 |
| **Total cost** | **$0.026724** |
| **Total energy [X]** | **~8704 J** |
| Solution density [C] | 0.033126 LOC/tok |
| Correctness/$ [C] | 15 |
| Quality/J [C] | 0.000078 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 100%  |  **Cost:** $0.0267  |  **Energy:** ~8704J  |  **Thinking:** 31%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Opencode session transcript](./exp_hw5wger9/session.jsonl)
- [Generated code](./exp_hw5wger9/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 15 |
| Total lines (Py) | 1085 |
| Functions | 112 |
| Classes | 5 |
| Functions/file | 7.5 |
| Classes/file | 0.3 |
| Avg lines/file | 72 |
| Type hints | 0% |
| Docstrings | 0% |
| Error handlers | 14 |
| Imports | 47 |
| Decorators | 32 |
| Test files | 5 |
| Test file rate | 33% |
| Parse errors | 0 |
