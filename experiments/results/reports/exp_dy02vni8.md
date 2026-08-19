# Game Report: inject_phantom_success_s0.5-perturbed

**Model:** deepseek/deepseek-v4-flash  |  **Task:** [inject_phantom_success_s0.5] task_manager...
**Operator:** perturbed (specification_corruption, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-17T19:29:06

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** EFFICIENT
**Score:** 0.878

**Verdict:** EFFICIENT — model solved correctly (100%) with minimal resources ($0.0108, ~7956J, 16% thinking). Thermodynamically optimal.

**Recommendation:** This operator+model combination is production-ready.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | nan |
| Architecture div [H] | nan |
| Structure div [H] | nan |
| Thinking ratio [C] | 15.7% |
| Quality/$ [C] | nan |
| Quality/J [C] | nan |
| Converged back [H] | None |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) [H] |
| Constraint satisfaction [H] | 71% (5/7 constraints) |
| Lines of code [M] | 1253 |
| Cyclomatic complexity [C] | 186.0 |
| Code quality [H] | 0.080 |
| Novelty vs baseline [H] | 0.500 |
| **Composite [H]** | **0.655** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 11,253 |
| Completion tokens [M] | 19,127 |
| Reasoning tokens [M] | 5,653 |
| Cache read tokens [M] | 815,488 |
| Cache write tokens [M] | 0 |
| **Total tokens** | **36,033** |
| Thinking ratio [C] | 15.7% |
| Output efficiency [C] | 53.1% |
| Input cost [M] | $0.001575 |
| Output cost [M] | $0.005356 |
| Reasoning cost [M] | $0.001583 |
| Cache cost [M] | $0.002283 |
| **Total cost** | **$0.010797** |
| **Total energy [X]** | **~7956 J** |
| Solution density [C] | 0.034774 LOC/tok |
| Correctness/$ [C] | 93 |
| Quality/J [C] | 0.000082 |

---

## Headline Metric
**Strategy:** EFFICIENT  |  **Correctness:** 100%  |  **Cost:** $0.0108  |  **Energy:** ~7956J  |  **Thinking:** 16%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Opencode session transcript](./exp_dy02vni8/session.jsonl)
- [Generated code](./exp_dy02vni8/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 16 |
| Total lines (Py) | 1253 |
| Functions | 124 |
| Classes | 2 |
| Functions/file | 7.8 |
| Classes/file | 0.1 |
| Avg lines/file | 78 |
| Type hints | 0% |
| Docstrings | 0% |
| Error handlers | 11 |
| Imports | 46 |
| Decorators | 39 |
| Test files | 6 |
| Test file rate | 38% |
| Parse errors | 0 |
