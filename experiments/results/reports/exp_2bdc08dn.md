# Game Report: invert_constraint_s0.5-perturbed

**Model:** deepseek/deepseek-v4-flash  |  **Task:** [invert_constraint_s0.5] task_manager...
**Operator:** perturbed (objective_mutation, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-30T18:48:20

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** EFFICIENT
**Score:** 0.859

**Verdict:** EFFICIENT — model solved correctly (100%) with minimal resources ($0.0078, ~6421J, 22% thinking). Thermodynamically optimal.

**Recommendation:** This operator+model combination is production-ready.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | nan |
| Architecture div [H] | nan |
| Structure div [H] | nan |
| Thinking ratio [C] | 21.9% |
| Quality/$ [C] | nan |
| Quality/J [C] | nan |
| Converged back [H] | None |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) [H] |
| Constraint satisfaction [H] | 71% (5/7 constraints) |
| Lines of code [M] | 929 |
| Cyclomatic complexity [C] | 133.0 |
| Code quality [H] | 0.108 |
| Novelty vs baseline [H] | 0.500 |
| **Composite [H]** | **0.661** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 8,831 |
| Completion tokens [M] | 12,600 |
| Reasoning tokens [M] | 5,992 |
| Cache read tokens [M] | 475,776 |
| Cache write tokens [M] | 0 |
| **Total tokens** | **27,423** |
| Thinking ratio [C] | 21.9% |
| Output efficiency [C] | 45.9% |
| Input cost [M] | $0.000861 |
| Output cost [M] | $0.003685 |
| Reasoning cost [M] | $0.001752 |
| Cache cost [M] | $0.001476 |
| **Total cost** | **$0.007774** |
| **Total energy [X]** | **~6421 J** |
| Solution density [C] | 0.033877 LOC/tok |
| Correctness/$ [C] | 57 |
| Quality/J [C] | 0.000103 |

---

## Headline Metric
**Strategy:** EFFICIENT  |  **Correctness:** 100%  |  **Cost:** $0.0078  |  **Energy:** ~6421J  |  **Thinking:** 22%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Opencode session transcript](./exp_2bdc08dn/session.jsonl)
- [Generated code](./exp_2bdc08dn/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 13 |
| Total lines (Py) | 929 |
| Functions | 88 |
| Classes | 3 |
| Functions/file | 6.8 |
| Classes/file | 0.2 |
| Avg lines/file | 71 |
| Type hints | 0% |
| Docstrings | 1% |
| Error handlers | 5 |
| Imports | 30 |
| Decorators | 28 |
| Test files | 4 |
| Test file rate | 31% |
| Parse errors | 0 |
