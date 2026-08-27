# Game Report: invert_constraint_s0.5-perturbed

**Model:** deepseek/deepseek-v4-pro  |  **Task:** [invert_constraint_s0.5] task_manager...
**Operator:** perturbed (objective_mutation, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-27T20:33:43

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** EFFICIENT
**Score:** 0.840

**Verdict:** EFFICIENT — model solved correctly (100%) with minimal resources ($0.0227, ~6987J, 26% thinking). Thermodynamically optimal.

**Recommendation:** This operator+model combination is production-ready.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | 0.189 |
| Architecture div [H] | 0.000 |
| Structure div [H] | 0.169 |
| Thinking ratio [C] | 26.4% |
| Quality/$ [C] | 44 |
| Quality/J [C] | 0.0001 |
| Converged back [H] | True |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) [H] |
| Constraint satisfaction [H] | 100% (7/7 constraints) |
| Lines of code [M] | 892 |
| Cyclomatic complexity [C] | 148.0 |
| Code quality [H] | 0.112 |
| Novelty vs baseline [H] | 0.461 |
| **Composite [H]** | **0.742** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 9,995 |
| Completion tokens [M] | 11,309 |
| Reasoning tokens [M] | 7,631 |
| Cache read tokens [M] | 528,768 |
| Cache write tokens [M] | 0 |
| **Total tokens** | **28,935** |
| Thinking ratio [C] | 26.4% |
| Output efficiency [C] | 39.1% |
| Input cost [M] | $0.002692 |
| Output cost [M] | $0.009138 |
| Reasoning cost [M] | $0.006166 |
| Cache cost [M] | $0.004747 |
| **Total cost** | **$0.022742** |
| **Total energy [X]** | **~6987 J** |
| Solution density [C] | 0.030828 LOC/tok |
| Correctness/$ [C] | 18 |
| Quality/J [C] | 0.000106 |

---

## Headline Metric
**Strategy:** EFFICIENT  |  **Correctness:** 100%  |  **Cost:** $0.0227  |  **Energy:** ~6987J  |  **Thinking:** 26%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Opencode session transcript](./exp_a3eztkke/session.jsonl)
- [Generated code](./exp_a3eztkke/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 16 |
| Total lines (Py) | 892 |
| Functions | 85 |
| Classes | 3 |
| Functions/file | 5.3 |
| Classes/file | 0.2 |
| Avg lines/file | 56 |
| Type hints | 0% |
| Docstrings | 2% |
| Error handlers | 10 |
| Imports | 46 |
| Decorators | 27 |
| Test files | 4 |
| Test file rate | 25% |
| Parse errors | 0 |
