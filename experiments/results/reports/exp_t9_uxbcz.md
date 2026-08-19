# Game Report: inject_phantom_success_s0.5-perturbed

**Model:** deepseek/deepseek-v4-pro  |  **Task:** [inject_phantom_success_s0.5] task_manager...
**Operator:** perturbed (specification_corruption, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-17T19:29:08

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** EFFICIENT
**Score:** 0.887

**Verdict:** EFFICIENT — model solved correctly (100%) with minimal resources ($0.0188, ~4633J, 8% thinking). Thermodynamically optimal.

**Recommendation:** This operator+model combination is production-ready.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | 0.138 |
| Architecture div [H] | 0.000 |
| Structure div [H] | 0.054 |
| Thinking ratio [C] | 7.8% |
| Quality/$ [C] | 53 |
| Quality/J [C] | 0.0002 |
| Converged back [H] | True |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) [H] |
| Constraint satisfaction [H] | 86% (6/7 constraints) |
| Lines of code [M] | 1004 |
| Cyclomatic complexity [C] | 143.0 |
| Code quality [H] | 0.100 |
| Novelty vs baseline [H] | 0.406 |
| **Composite [H]** | **0.688** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 10,598 |
| Completion tokens [M] | 12,448 |
| Reasoning tokens [M] | 1,961 |
| Cache read tokens [M] | 450,304 |
| Cache write tokens [M] | 0 |
| **Total tokens** | **25,007** |
| Thinking ratio [C] | 7.8% |
| Output efficiency [C] | 49.8% |
| Input cost [M] | $0.004610 |
| Output cost [M] | $0.010830 |
| Reasoning cost [M] | $0.001706 |
| Cache cost [M] | $0.001632 |
| **Total cost** | **$0.018778** |
| **Total energy [X]** | **~4633 J** |
| Solution density [C] | 0.040149 LOC/tok |
| Correctness/$ [C] | 53 |
| Quality/J [C] | 0.000148 |

---

## Headline Metric
**Strategy:** EFFICIENT  |  **Correctness:** 100%  |  **Cost:** $0.0188  |  **Energy:** ~4633J  |  **Thinking:** 8%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Opencode session transcript](./exp_t9_uxbcz/session.jsonl)
- [Generated code](./exp_t9_uxbcz/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 14 |
| Total lines (Py) | 1004 |
| Functions | 96 |
| Classes | 5 |
| Functions/file | 6.9 |
| Classes/file | 0.4 |
| Avg lines/file | 72 |
| Type hints | 0% |
| Docstrings | 3% |
| Error handlers | 7 |
| Imports | 44 |
| Decorators | 37 |
| Test files | 4 |
| Test file rate | 29% |
| Parse errors | 0 |
