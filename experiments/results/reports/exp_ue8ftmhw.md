# Game Report: inject_alien_vocab_s0.5-perturbed

**Model:** deepseek/deepseek-v4-flash  |  **Task:** [inject_alien_vocab_s0.5] url_shortener...
**Operator:** perturbed (process_perturbation, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-17T19:29:08

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** EFFICIENT
**Score:** 0.895

**Verdict:** EFFICIENT — model solved correctly (100%) with minimal resources ($0.0033, ~2461J, 10% thinking). Thermodynamically optimal.

**Recommendation:** This operator+model combination is production-ready.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | nan |
| Architecture div [H] | nan |
| Structure div [H] | nan |
| Thinking ratio [C] | 9.9% |
| Quality/$ [C] | nan |
| Quality/J [C] | nan |
| Converged back [H] | None |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) [H] |
| Constraint satisfaction [H] | 67% (4/6 constraints) |
| Lines of code [M] | 313 |
| Cyclomatic complexity [C] | 39.0 |
| Code quality [H] | 0.319 |
| Novelty vs baseline [H] | 0.500 |
| **Composite [H]** | **0.689** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 7,078 |
| Completion tokens [M] | 5,432 |
| Reasoning tokens [M] | 1,374 |
| Cache read tokens [M] | 137,984 |
| Cache write tokens [M] | 0 |
| **Total tokens** | **13,884** |
| Thinking ratio [C] | 9.9% |
| Output efficiency [C] | 39.1% |
| Input cost [M] | $0.000991 |
| Output cost [M] | $0.001521 |
| Reasoning cost [M] | $0.000385 |
| Cache cost [M] | $0.000386 |
| **Total cost** | **$0.003283** |
| **Total energy [X]** | **~2461 J** |
| Solution density [C] | 0.022544 LOC/tok |
| Correctness/$ [C] | 305 |
| Quality/J [C] | 0.000280 |

---

## Headline Metric
**Strategy:** EFFICIENT  |  **Correctness:** 100%  |  **Cost:** $0.0033  |  **Energy:** ~2461J  |  **Thinking:** 10%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Opencode session transcript](./exp_ue8ftmhw/session.jsonl)
- [Generated code](./exp_ue8ftmhw/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 2 |
| Total lines (Py) | 313 |
| Functions | 35 |
| Classes | 1 |
| Functions/file | 17.5 |
| Classes/file | 0.5 |
| Avg lines/file | 156 |
| Type hints | 0% |
| Docstrings | 0% |
| Error handlers | 3 |
| Imports | 11 |
| Decorators | 6 |
| Test files | 1 |
| Test file rate | 50% |
| Parse errors | 0 |
