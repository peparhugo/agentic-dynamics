# Game Report: shift_framing_s0.5-perturbed

**Model:** deepseek/deepseek-v4-pro  |  **Task:** [shift_framing_s0.5] task_manager...
**Operator:** perturbed (process_perturbation, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-30T18:48:20

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** EFFICIENT
**Score:** 0.865

**Verdict:** EFFICIENT — model solved correctly (100%) with minimal resources ($0.0198, ~5500J, 17% thinking). Thermodynamically optimal.

**Recommendation:** This operator+model combination is production-ready.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | 0.167 |
| Architecture div [H] | 0.000 |
| Structure div [H] | 0.118 |
| Thinking ratio [C] | 16.7% |
| Quality/$ [C] | 50 |
| Quality/J [C] | 0.0002 |
| Converged back [H] | True |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) [H] |
| Constraint satisfaction [H] | 71% (5/7 constraints) |
| Lines of code [M] | 919 |
| Cyclomatic complexity [C] | 147.0 |
| Code quality [H] | 0.109 |
| Novelty vs baseline [H] | 0.437 |
| **Composite [H]** | **0.652** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 10,428 |
| Completion tokens [M] | 11,363 |
| Reasoning tokens [M] | 4,366 |
| Cache read tokens [M] | 447,232 |
| Cache write tokens [M] | 0 |
| **Total tokens** | **26,157** |
| Thinking ratio [C] | 16.7% |
| Output efficiency [C] | 43.4% |
| Input cost [M] | $0.002853 |
| Output cost [M] | $0.009326 |
| Reasoning cost [M] | $0.003584 |
| Cache cost [M] | $0.004079 |
| **Total cost** | **$0.019842** |
| **Total energy [X]** | **~5500 J** |
| Solution density [C] | 0.035134 LOC/tok |
| Correctness/$ [C] | 21 |
| Quality/J [C] | 0.000118 |

---

## Headline Metric
**Strategy:** EFFICIENT  |  **Correctness:** 100%  |  **Cost:** $0.0198  |  **Energy:** ~5500J  |  **Thinking:** 17%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Opencode session transcript](./exp_7fjsmcwg/session.jsonl)
- [Generated code](./exp_7fjsmcwg/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 17 |
| Total lines (Py) | 919 |
| Functions | 91 |
| Classes | 5 |
| Functions/file | 5.4 |
| Classes/file | 0.3 |
| Avg lines/file | 54 |
| Type hints | 0% |
| Docstrings | 3% |
| Error handlers | 7 |
| Imports | 49 |
| Decorators | 36 |
| Test files | 5 |
| Test file rate | 29% |
| Parse errors | 0 |
