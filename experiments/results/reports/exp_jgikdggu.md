# Game Report: inject_alien_vocab_s0.5-perturbed

**Model:** deepseek/deepseek-v4-pro  |  **Task:** [inject_alien_vocab_s0.5] task_manager...
**Operator:** perturbed (process_perturbation, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-27T00:54:04

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** EFFICIENT
**Score:** 0.914

**Verdict:** EFFICIENT — model solved correctly (100%) with minimal resources ($0.0199, ~5005J, 9% thinking). Thermodynamically optimal.

**Recommendation:** This operator+model combination is production-ready.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | 0.348 |
| Architecture div [H] | 0.333 |
| Structure div [H] | 0.101 |
| Thinking ratio [C] | 9.3% |
| Quality/$ [C] | 50 |
| Quality/J [C] | 0.0002 |
| Converged back [H] | False |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) [H] |
| Constraint satisfaction [H] | 71% (5/7 constraints) |
| Lines of code [M] | 926 |
| Cyclomatic complexity [C] | 115.0 |
| Code quality [H] | 0.108 |
| Novelty vs baseline [H] | 0.615 |
| **Composite [H]** | **0.678** |

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
| Input cost [M] | $0.002768 |
| Output cost [M] | $0.010711 |
| Reasoning cost [M] | $0.001960 |
| Cache cost [M] | $0.004447 |
| **Total cost** | **$0.019886** |
| **Total energy [X]** | **~5005 J** |
| Solution density [C] | 0.035713 LOC/tok |
| Correctness/$ [C] | 21 |
| Quality/J [C] | 0.000135 |

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
