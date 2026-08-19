# Game Report: shift_framing_s0.5-perturbed

**Model:** deepseek/deepseek-v4-flash  |  **Task:** [shift_framing_s0.5] task_manager...
**Operator:** perturbed (process_perturbation, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-17T19:29:05

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** EFFICIENT
**Score:** 0.910

**Verdict:** EFFICIENT — model solved correctly (100%) with minimal resources ($0.0076, ~5486J, 12% thinking). Thermodynamically optimal.

**Recommendation:** This operator+model combination is production-ready.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | 0.202 |
| Architecture div [H] | 0.000 |
| Structure div [H] | 0.044 |
| Thinking ratio [C] | 11.5% |
| Quality/$ [C] | 132 |
| Quality/J [C] | 0.0002 |
| Converged back [H] | False |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) [H] |
| Constraint satisfaction [H] | 57% (4/7 constraints) |
| Lines of code [M] | 948 |
| Cyclomatic complexity [C] | 111.0 |
| Code quality [H] | 0.105 |
| Novelty vs baseline [H] | 0.628 |
| **Composite [H]** | **0.637** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 9,031 |
| Completion tokens [M] | 14,446 |
| Reasoning tokens [M] | 3,065 |
| Cache read tokens [M] | 504,320 |
| Cache write tokens [M] | 0 |
| **Total tokens** | **26,542** |
| Thinking ratio [C] | 11.5% |
| Output efficiency [C] | 54.4% |
| Input cost [M] | $0.001264 |
| Output cost [M] | $0.004045 |
| Reasoning cost [M] | $0.000858 |
| Cache cost [M] | $0.001412 |
| **Total cost** | **$0.007580** |
| **Total energy [X]** | **~5486 J** |
| Solution density [C] | 0.035717 LOC/tok |
| Correctness/$ [C] | 132 |
| Quality/J [C] | 0.000116 |

---

## Headline Metric
**Strategy:** EFFICIENT  |  **Correctness:** 100%  |  **Cost:** $0.0076  |  **Energy:** ~5486J  |  **Thinking:** 12%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Opencode session transcript](./exp_8an6dhoh/session.jsonl)
- [Generated code](./exp_8an6dhoh/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 13 |
| Total lines (Py) | 948 |
| Functions | 95 |
| Classes | 2 |
| Functions/file | 7.3 |
| Classes/file | 0.2 |
| Avg lines/file | 73 |
| Type hints | 0% |
| Docstrings | 2% |
| Error handlers | 6 |
| Imports | 32 |
| Decorators | 33 |
| Test files | 4 |
| Test file rate | 31% |
| Parse errors | 0 |
