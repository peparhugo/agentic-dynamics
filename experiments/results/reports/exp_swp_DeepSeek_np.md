# Game Report: perturbed-baseline

**Model:** deepseek/deepseek-v4-pro  |  **Task:** [silent_sweep:perturbed:natural] DeepSeek_v4_Pro...
**Operator:** baseline (baseline, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-30T18:48:28

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** EFFICIENT
**Score:** 0.851

**Verdict:** EFFICIENT — model solved correctly (100%) with minimal resources ($0.0484, ~13102J, 25% thinking). Thermodynamically optimal.

**Recommendation:** This operator+model combination is production-ready.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | nan |
| Architecture div [H] | nan |
| Structure div [H] | nan |
| Thinking ratio [C] | 24.6% |
| Quality/$ [C] | nan |
| Quality/J [C] | nan |
| Converged back [H] | None |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) [H] |
| Constraint satisfaction [H] | 71% (5/7 constraints) |
| Lines of code [M] | 946 |
| Cyclomatic complexity [C] | 112.0 |
| Code quality [H] | 0.106 |
| Novelty vs baseline [H] | 0.500 |
| **Composite [H]** | **0.660** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 29,959 |
| Completion tokens [M] | 15,923 |
| Reasoning tokens [M] | 14,986 |
| Cache read tokens [M] | 2,344,960 |
| Cache write tokens [M] | 0 |
| **Total tokens** | **60,868** |
| Thinking ratio [C] | 24.6% |
| Output efficiency [C] | 26.2% |
| Input cost [M] | $0.007223 |
| Output cost [M] | $0.011517 |
| Reasoning cost [M] | $0.010839 |
| Cache cost [M] | $0.018845 |
| **Total cost** | **$0.048423** |
| **Total energy [X]** | **~13102 J** |
| Solution density [C] | 0.015542 LOC/tok |
| Correctness/$ [C] | 8 |
| Quality/J [C] | 0.000050 |

---

## Headline Metric
**Strategy:** EFFICIENT  |  **Correctness:** 100%  |  **Cost:** $0.0484  |  **Energy:** ~13102J  |  **Thinking:** 25%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Generated code](./exp_swp_DeepSeek_np/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 21 |
| Total lines (Py) | 946 |
| Functions | 111 |
| Classes | 13 |
| Functions/file | 5.3 |
| Classes/file | 0.6 |
| Avg lines/file | 45 |
| Type hints | 0% |
| Docstrings | 1% |
| Error handlers | 9 |
| Imports | 59 |
| Decorators | 29 |
| Test files | 8 |
| Test file rate | 38% |
| Parse errors | 0 |
