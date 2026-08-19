# Game Report: inject_competing_goal_s0.5-perturbed

**Model:** openai/gpt-5.6-luna  |  **Task:** [inject_competing_goal_s0.5] task_manager...
**Operator:** perturbed (objective_mutation, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-17T19:29:09

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** EFFICIENT
**Score:** 0.814

**Verdict:** EFFICIENT — model solved correctly (70%) with minimal resources ($0.0168, ~3586J, 2% thinking). Thermodynamically optimal.

**Recommendation:** This operator+model combination is production-ready.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | nan |
| Architecture div [H] | nan |
| Structure div [H] | nan |
| Thinking ratio [C] | 1.9% |
| Quality/$ [C] | nan |
| Quality/J [C] | nan |
| Converged back [H] | None |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 70% (0/0 tests) [H] |
| Constraint satisfaction [H] | 0% (0/7 constraints) |
| Lines of code [M] | 282 |
| Cyclomatic complexity [C] | 70.0 |
| Code quality [H] | 0.355 |
| Novelty vs baseline [H] | 0.500 |
| **Composite [H]** | **0.391** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 20,079 |
| Completion tokens [M] | 7,511 |
| Reasoning tokens [M] | 536 |
| Cache read tokens [M] | 157,184 |
| Cache write tokens [M] | 0 |
| **Total tokens** | **28,126** |
| Thinking ratio [C] | 1.9% |
| Output efficiency [C] | 26.7% |
| Input cost [C] | $0.004016 |
| Output cost [C] | $0.009013 |
| Reasoning cost [C] | $0.000643 |
| Cache cost [C] | $0.003144 |
| **Total cost** | **$0.016816** |
| **Total energy [X]** | **~3586 J** |
| Solution density [C] | 0.010026 LOC/tok |
| Correctness/$ [C] | 42 |
| Quality/J [C] | 0.000169 |

---

## Headline Metric
**Strategy:** EFFICIENT  |  **Correctness:** 70%  |  **Cost:** $0.0168  |  **Energy:** ~3586J  |  **Thinking:** 2%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Opencode session transcript](./exp_w0fiexd7/session.jsonl)
- [Generated code](./exp_w0fiexd7/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 9 |
| Total lines (Py) | 282 |
| Functions | 41 |
| Classes | 0 |
| Functions/file | 4.6 |
| Classes/file | 0.0 |
| Avg lines/file | 31 |
| Type hints | 0% |
| Docstrings | 0% |
| Error handlers | 7 |
| Imports | 27 |
| Decorators | 19 |
| Test files | 3 |
| Test file rate | 33% |
| Parse errors | 0 |

## Narration Assessment

**Narration penalty:** 30%

| Metric | Value |
|--------|-------|
| Output tokens | 7,511 |
| Python files | 9 |
| Non-Python files | 0 |
| Code density | 0.0375 LOC/tok |
| **Assessment** | Low code density — narration exceeded code output |

