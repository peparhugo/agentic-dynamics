# Game Report: inject_competing_goal_s0.5-perturbed

**Model:** openai/gpt-5.6-sol  |  **Task:** [inject_competing_goal_s0.5] task_manager...
**Operator:** perturbed (objective_mutation, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-30T18:48:21

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** EFFICIENT
**Score:** 0.928

**Verdict:** EFFICIENT — model solved correctly (100%) with minimal resources ($0.5197, ~4714J, 2% thinking). Thermodynamically optimal.

**Recommendation:** This operator+model combination is production-ready.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | 0.187 |
| Architecture div [H] | 0.000 |
| Structure div [H] | 0.068 |
| Thinking ratio [C] | 1.7% |
| Quality/$ [C] | 26 |
| Quality/J [C] | 0.0002 |
| Converged back [H] | True |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) [H] |
| Constraint satisfaction [H] | 71% (5/7 constraints) |
| Lines of code [M] | 697 |
| Cyclomatic complexity [C] | 129.0 |
| Code quality [H] | 0.143 |
| Novelty vs baseline [H] | 0.554 |
| **Composite [H]** | **0.676** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 21,941 |
| Completion tokens [M] | 11,691 |
| Reasoning tokens [M] | 575 |
| Cache read tokens [M] | 83,968 |
| Cache write tokens [M] | 0 |
| **Total tokens** | **34,207** |
| Thinking ratio [C] | 1.7% |
| Output efficiency [C] | 34.2% |
| Input cost [C] | $0.109705 |
| Output cost [C] | $0.350730 |
| Reasoning cost [C] | $0.017250 |
| Cache cost [C] | $0.041984 |
| **Total cost** | **$0.519669** |
| **Total energy [X]** | **~4714 J** |
| Solution density [C] | 0.020376 LOC/tok |
| Correctness/$ [C] | 2 |
| Quality/J [C] | 0.000143 |

---

## Headline Metric
**Strategy:** EFFICIENT  |  **Correctness:** 100%  |  **Cost:** $0.5197  |  **Energy:** ~4714J  |  **Thinking:** 2%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Opencode session transcript](./exp_9u5r2dl0/session.jsonl)
- [Generated code](./exp_9u5r2dl0/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 13 |
| Total lines (Py) | 697 |
| Functions | 59 |
| Classes | 0 |
| Functions/file | 4.5 |
| Classes/file | 0.0 |
| Avg lines/file | 54 |
| Type hints | 0% |
| Docstrings | 0% |
| Error handlers | 10 |
| Imports | 40 |
| Decorators | 32 |
| Test files | 5 |
| Test file rate | 38% |
| Parse errors | 0 |
