# Game Report: inject_competing_goal_s0.5-perturbed

**Model:** openai/gpt-5.6-terra  |  **Task:** [inject_competing_goal_s0.5] task_manager...
**Operator:** perturbed (objective_mutation, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-17T19:29:07

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** EFFICIENT
**Score:** 0.817

**Verdict:** EFFICIENT — model solved correctly (70%) with minimal resources ($0.2646, ~4544J, 3% thinking). Thermodynamically optimal.

**Recommendation:** This operator+model combination is production-ready.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | 0.218 |
| Architecture div [H] | 0.000 |
| Structure div [H] | 0.191 |
| Thinking ratio [C] | 2.8% |
| Quality/$ [C] | 35 |
| Quality/J [C] | 0.0002 |
| Converged back [H] | False |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 70% (0/0 tests) [H] |
| Constraint satisfaction [H] | 0% (0/7 constraints) |
| Lines of code [M] | 386 |
| Cyclomatic complexity [C] | 94.0 |
| Code quality [H] | 0.259 |
| Novelty vs baseline [H] | 0.535 |
| **Composite [H]** | **0.377** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 26,203 |
| Completion tokens [M] | 8,607 |
| Reasoning tokens [M] | 997 |
| Cache read tokens [M] | 220,160 |
| Cache write tokens [M] | 0 |
| **Total tokens** | **35,807** |
| Thinking ratio [C] | 2.8% |
| Output efficiency [C] | 24.0% |
| Input cost [C] | $0.065507 |
| Output cost [C] | $0.129105 |
| Reasoning cost [C] | $0.014955 |
| Cache cost [C] | $0.055040 |
| **Total cost** | **$0.264607** |
| **Total energy [X]** | **~4544 J** |
| Solution density [C] | 0.010780 LOC/tok |
| Correctness/$ [C] | 3 |
| Quality/J [C] | 0.000121 |

---

## Headline Metric
**Strategy:** EFFICIENT  |  **Correctness:** 70%  |  **Cost:** $0.2646  |  **Energy:** ~4544J  |  **Thinking:** 3%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Opencode session transcript](./exp_iwqmgxf0/session.jsonl)
- [Generated code](./exp_iwqmgxf0/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 2 |
| Total lines (Py) | 386 |
| Functions | 41 |
| Classes | 0 |
| Functions/file | 20.5 |
| Classes/file | 0.0 |
| Avg lines/file | 193 |
| Type hints | 0% |
| Docstrings | 0% |
| Error handlers | 8 |
| Imports | 19 |
| Decorators | 21 |
| Test files | 1 |
| Test file rate | 50% |
| Parse errors | 0 |

## Narration Assessment

**Narration penalty:** 30%

| Metric | Value |
|--------|-------|
| Output tokens | 8,607 |
| Python files | 2 |
| Non-Python files | 0 |
| Code density | 0.0448 LOC/tok |
| **Assessment** | Low code density — narration exceeded code output |

