# Game Report: baseline-baseline

**Model:** deepseek/deepseek-v4-pro  |  **Task:** [silent_sweep:baseline:natural] DeepSeek_v4_Pro...
**Operator:** baseline (baseline, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-30T18:48:28

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** EFFICIENT
**Score:** 0.876

**Verdict:** EFFICIENT — model solved correctly (100%) with minimal resources ($0.0272, ~7183J, 16% thinking). Thermodynamically optimal.

**Recommendation:** This operator+model combination is production-ready.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | nan |
| Architecture div [H] | nan |
| Structure div [H] | nan |
| Thinking ratio [C] | 16.4% |
| Quality/$ [C] | nan |
| Quality/J [C] | nan |
| Converged back [H] | None |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) [H] |
| Constraint satisfaction [H] | 86% (6/7 constraints) |
| Lines of code [M] | 973 |
| Cyclomatic complexity [C] | 97.0 |
| Code quality [H] | 0.103 |
| Novelty vs baseline [H] | 0.500 |
| **Composite [H]** | **0.703** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 12,592 |
| Completion tokens [M] | 15,565 |
| Reasoning tokens [M] | 5,522 |
| Cache read tokens [M] | 931,712 |
| Cache write tokens [M] | 0 |
| **Total tokens** | **33,679** |
| Thinking ratio [C] | 16.4% |
| Output efficiency [C] | 46.2% |
| Input cost [M] | $0.003204 |
| Output cost [M] | $0.011880 |
| Reasoning cost [M] | $0.004215 |
| Cache cost [M] | $0.007902 |
| **Total cost** | **$0.027201** |
| **Total energy [X]** | **~7183 J** |
| Solution density [C] | 0.028890 LOC/tok |
| Correctness/$ [C] | 14 |
| Quality/J [C] | 0.000098 |

---

## Headline Metric
**Strategy:** EFFICIENT  |  **Correctness:** 100%  |  **Cost:** $0.0272  |  **Energy:** ~7183J  |  **Thinking:** 16%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Generated code](./exp_swp_DeepSeek_nb/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 20 |
| Total lines (Py) | 973 |
| Functions | 108 |
| Classes | 14 |
| Functions/file | 5.4 |
| Classes/file | 0.7 |
| Avg lines/file | 49 |
| Type hints | 0% |
| Docstrings | 0% |
| Error handlers | 11 |
| Imports | 62 |
| Decorators | 29 |
| Test files | 7 |
| Test file rate | 35% |
| Parse errors | 0 |
