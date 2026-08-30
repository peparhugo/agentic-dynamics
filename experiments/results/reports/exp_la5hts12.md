# Game Report: inject_alien_vocab_s0.5-perturbed

**Model:** deepseek/deepseek-v4-flash  |  **Task:** [inject_alien_vocab_s0.5] task_manager...
**Operator:** perturbed (process_perturbation, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-30T18:48:28

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** EFFICIENT
**Score:** 0.888

**Verdict:** EFFICIENT — model solved correctly (100%) with minimal resources ($0.0082, ~6211J, 12% thinking). Thermodynamically optimal.

**Recommendation:** This operator+model combination is production-ready.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | nan |
| Architecture div [H] | nan |
| Structure div [H] | nan |
| Thinking ratio [C] | 12.3% |
| Quality/$ [C] | nan |
| Quality/J [C] | nan |
| Converged back [H] | None |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) [H] |
| Constraint satisfaction [H] | 71% (5/7 constraints) |
| Lines of code [M] | 1349 |
| Cyclomatic complexity [C] | 153.0 |
| Code quality [H] | 0.074 |
| Novelty vs baseline [H] | 0.500 |
| **Composite [H]** | **0.654** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 9,051 |
| Completion tokens [M] | 16,516 |
| Reasoning tokens [M] | 3,592 |
| Cache read tokens [M] | 464,000 |
| Cache write tokens [M] | 0 |
| **Total tokens** | **29,159** |
| Thinking ratio [C] | 12.3% |
| Output efficiency [C] | 56.6% |
| Input cost [M] | $0.000882 |
| Output cost [M] | $0.004827 |
| Reasoning cost [M] | $0.001050 |
| Cache cost [M] | $0.001438 |
| **Total cost** | **$0.008197** |
| **Total energy [X]** | **~6211 J** |
| Solution density [C] | 0.046264 LOC/tok |
| Correctness/$ [C] | 54 |
| Quality/J [C] | 0.000105 |

---

## Headline Metric
**Strategy:** EFFICIENT  |  **Correctness:** 100%  |  **Cost:** $0.0082  |  **Energy:** ~6211J  |  **Thinking:** 12%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Opencode session transcript](./exp_la5hts12/session.jsonl)
- [Generated code](./exp_la5hts12/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 10 |
| Total lines (Py) | 1349 |
| Functions | 133 |
| Classes | 9 |
| Functions/file | 13.3 |
| Classes/file | 0.9 |
| Avg lines/file | 135 |
| Type hints | 0% |
| Docstrings | 0% |
| Error handlers | 15 |
| Imports | 30 |
| Decorators | 49 |
| Test files | 4 |
| Test file rate | 40% |
| Parse errors | 0 |
