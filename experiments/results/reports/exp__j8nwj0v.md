# Game Report: shift_framing_s0.5-perturbed

**Model:** openai/gpt-5.6-sol  |  **Task:** [shift_framing_s0.5] task_manager...
**Operator:** perturbed (process_perturbation, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-27T20:33:42

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** EFFICIENT
**Score:** 0.935

**Verdict:** EFFICIENT — model solved correctly (100%) with minimal resources ($0.4277, ~3993J, 1% thinking). Thermodynamically optimal.

**Recommendation:** This operator+model combination is production-ready.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | 0.266 |
| Architecture div [H] | 0.000 |
| Structure div [H] | 0.295 |
| Thinking ratio [C] | 1.3% |
| Quality/$ [C] | 30 |
| Quality/J [C] | 0.0003 |
| Converged back [H] | False |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) [H] |
| Constraint satisfaction [H] | 71% (5/7 constraints) |
| Lines of code [M] | 498 |
| Cyclomatic complexity [C] | 92.0 |
| Code quality [H] | 0.201 |
| Novelty vs baseline [H] | 0.592 |
| **Composite [H]** | **0.693** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 22,825 |
| Completion tokens [M] | 8,549 |
| Reasoning tokens [M] | 427 |
| Cache read tokens [M] | 88,576 |
| Cache write tokens [M] | 0 |
| **Total tokens** | **31,801** |
| Thinking ratio [C] | 1.3% |
| Output efficiency [C] | 26.9% |
| Input cost [C] | $0.114125 |
| Output cost [C] | $0.256470 |
| Reasoning cost [C] | $0.012810 |
| Cache cost [C] | $0.044288 |
| **Total cost** | **$0.427693** |
| **Total energy [X]** | **~3993 J** |
| Solution density [C] | 0.015660 LOC/tok |
| Correctness/$ [C] | 2 |
| Quality/J [C] | 0.000174 |

---

## Headline Metric
**Strategy:** EFFICIENT  |  **Correctness:** 100%  |  **Cost:** $0.4277  |  **Energy:** ~3993J  |  **Thinking:** 1%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Opencode session transcript](./exp__j8nwj0v/session.jsonl)
- [Generated code](./exp__j8nwj0v/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 8 |
| Total lines (Py) | 498 |
| Functions | 43 |
| Classes | 0 |
| Functions/file | 5.4 |
| Classes/file | 0.0 |
| Avg lines/file | 62 |
| Type hints | 0% |
| Docstrings | 0% |
| Error handlers | 5 |
| Imports | 23 |
| Decorators | 20 |
| Test files | 3 |
| Test file rate | 38% |
| Parse errors | 0 |
