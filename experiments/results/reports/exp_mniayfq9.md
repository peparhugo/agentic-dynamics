# Game Report: invert_constraint_s0.5-perturbed

**Model:** openai/gpt-5.6-sol  |  **Task:** [invert_constraint_s0.5] task_manager...
**Operator:** perturbed (objective_mutation, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-30T18:48:28

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** EFFICIENT
**Score:** 0.920

**Verdict:** EFFICIENT — model solved correctly (100%) with minimal resources ($0.5102, ~4605J, 2% thinking). Thermodynamically optimal.

**Recommendation:** This operator+model combination is production-ready.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | nan |
| Architecture div [H] | nan |
| Structure div [H] | nan |
| Thinking ratio [C] | 1.5% |
| Quality/$ [C] | nan |
| Quality/J [C] | nan |
| Converged back [H] | None |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) [H] |
| Constraint satisfaction [H] | 86% (6/7 constraints) |
| Lines of code [M] | 719 |
| Cyclomatic complexity [C] | 130.0 |
| Code quality [H] | 0.139 |
| Novelty vs baseline [H] | 0.500 |
| **Composite [H]** | **0.710** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 20,621 |
| Completion tokens [M] | 11,824 |
| Reasoning tokens [M] | 501 |
| Cache read tokens [M] | 74,752 |
| Cache write tokens [M] | 0 |
| **Total tokens** | **32,946** |
| Thinking ratio [C] | 1.5% |
| Output efficiency [C] | 35.9% |
| Input cost [C] | $0.103105 |
| Output cost [C] | $0.354720 |
| Reasoning cost [C] | $0.015030 |
| Cache cost [C] | $0.037376 |
| **Total cost** | **$0.510231** |
| **Total energy [X]** | **~4605 J** |
| Solution density [C] | 0.021824 LOC/tok |
| Correctness/$ [C] | 2 |
| Quality/J [C] | 0.000154 |

---

## Headline Metric
**Strategy:** EFFICIENT  |  **Correctness:** 100%  |  **Cost:** $0.5102  |  **Energy:** ~4605J  |  **Thinking:** 2%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Opencode session transcript](./exp_mniayfq9/session.jsonl)
- [Generated code](./exp_mniayfq9/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 12 |
| Total lines (Py) | 719 |
| Functions | 66 |
| Classes | 3 |
| Functions/file | 5.5 |
| Classes/file | 0.2 |
| Avg lines/file | 60 |
| Type hints | 0% |
| Docstrings | 0% |
| Error handlers | 13 |
| Imports | 27 |
| Decorators | 29 |
| Test files | 4 |
| Test file rate | 33% |
| Parse errors | 0 |
