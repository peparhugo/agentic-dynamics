# Game Report: inject_alien_vocab_s0.5-perturbed

**Model:** deepseek/deepseek-v4-pro  |  **Task:** [inject_alien_vocab_s0.5] task_manager...
**Operator:** perturbed (process_perturbation, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-17T19:29:07

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** EFFICIENT
**Score:** 0.912

**Verdict:** EFFICIENT — model solved correctly (100%) with minimal resources ($0.0199, ~5005J, 9% thinking). Thermodynamically optimal.

**Recommendation:** This operator+model combination is production-ready.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | 0.329 |
| Architecture div [H] | 0.333 |
| Structure div [H] | 0.051 |
| Thinking ratio [C] | 9.3% |
| Quality/$ [C] | 50 |
| Quality/J [C] | 0.0002 |
| Converged back [H] | False |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) [H] |
| Constraint satisfaction [H] | 57% (4/7 constraints) |
| Lines of code [M] | 926 |
| Cyclomatic complexity [C] | 115.0 |
| Code quality [H] | 0.108 |
| Novelty vs baseline [H] | 0.600 |
| **Composite [H]** | **0.633** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 10,265 |
| Completion tokens [M] | 13,241 |
| Reasoning tokens [M] | 2,423 |
| Cache read tokens [M] | 494,720 |
| Cache write tokens [M] | 0 |
| **Total tokens** | **25,929** |
| Thinking ratio [C] | 9.3% |
| Output efficiency [C] | 51.1% |
| Input cost [M] | $0.004465 |
| Output cost [M] | $0.011520 |
| Reasoning cost [M] | $0.002108 |
| Cache cost [M] | $0.001793 |
| **Total cost** | **$0.019886** |
| **Total energy [X]** | **~5005 J** |
| Solution density [C] | 0.035713 LOC/tok |
| Correctness/$ [C] | 50 |
| Quality/J [C] | 0.000126 |

---

## Headline Metric
**Strategy:** EFFICIENT  |  **Correctness:** 100%  |  **Cost:** $0.0199  |  **Energy:** ~5005J  |  **Thinking:** 9%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Opencode session transcript](./exp_jgikdggu/session.jsonl)
- [Generated code](./exp_jgikdggu/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 17 |
| Total lines (Py) | 926 |
| Functions | 94 |
| Classes | 5 |
| Functions/file | 5.5 |
| Classes/file | 0.3 |
| Avg lines/file | 54 |
| Type hints | 0% |
| Docstrings | 1% |
| Error handlers | 7 |
| Imports | 51 |
| Decorators | 29 |
| Test files | 6 |
| Test file rate | 35% |
| Parse errors | 0 |
