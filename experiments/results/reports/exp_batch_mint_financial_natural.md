# Game Report: mint_financial-baseline

**Model:** deepseek/deepseek-v4-pro  |  **Task:** [batch:mint_financial:baseline] ds_natural...
**Operator:** baseline (baseline, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-27T20:33:46

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** EFFICIENT
**Score:** 0.887

**Verdict:** EFFICIENT — model solved correctly (100%) with minimal resources ($0.0107, ~2955J, 13% thinking). Thermodynamically optimal.

**Recommendation:** This operator+model combination is production-ready.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | nan |
| Architecture div [H] | nan |
| Structure div [H] | nan |
| Thinking ratio [C] | 12.7% |
| Quality/$ [C] | nan |
| Quality/J [C] | nan |
| Converged back [H] | None |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) [H] |
| Constraint satisfaction [H] | 29% (2/7 constraints) |
| Lines of code [M] | 538 |
| Cyclomatic complexity [C] | 105.0 |
| Code quality [H] | 0.186 |
| Novelty vs baseline [H] | 0.500 |
| **Composite [H]** | **0.548** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 6,593 |
| Completion tokens [M] | 6,632 |
| Reasoning tokens [M] | 1,920 |
| Cache read tokens [M] | 103,680 |
| Cache write tokens [M] | 0 |
| **Total tokens** | **15,145** |
| Thinking ratio [C] | 12.7% |
| Output efficiency [C] | 43.8% |
| Input cost [M] | $0.001973 |
| Output cost [M] | $0.005953 |
| Reasoning cost [M] | $0.001724 |
| Cache cost [M] | $0.001034 |
| **Total cost** | **$0.010684** |
| **Total energy [X]** | **~2955 J** |
| Solution density [C] | 0.035523 LOC/tok |
| Correctness/$ [C] | 42 |
| Quality/J [C] | 0.000185 |

---

## Headline Metric
**Strategy:** EFFICIENT  |  **Correctness:** 100%  |  **Cost:** $0.0107  |  **Energy:** ~2955J  |  **Thinking:** 13%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Generated code](./exp_batch_mint_financial_natural/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 6 |
| Total lines (Py) | 538 |
| Functions | 64 |
| Classes | 26 |
| Functions/file | 10.7 |
| Classes/file | 4.3 |
| Avg lines/file | 90 |
| Type hints | 92% |
| Docstrings | 22% |
| Error handlers | 10 |
| Imports | 29 |
| Decorators | 10 |
| Test files | 0 |
| Test file rate | 0% |
| Parse errors | 0 |
